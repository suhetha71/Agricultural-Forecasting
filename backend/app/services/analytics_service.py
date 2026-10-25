import logging
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any, Tuple
import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy.orm import Session
from sqlalchemy import func, asc

from app.models.market_observation import MarketObservation
from app.schemas.analytics import (
    PriceChangeMetric,
    AggregatedPricePoint,
    HistoricalSeriesView,
    MonthlySeasonalityPoint,
    SeasonGroupPoint,
    SeasonalAnalysisResponse,
    AnomalyItem,
    AnomalyDetectionResponse,
    ArrivalsWeatherResponse,
)
from app.services.weather_service import (
    WEATHER_ATTRIBUTION_URL,
    WEATHER_SOURCE,
    WeatherService,
)

logger = logging.getLogger(__name__)

# Coordinates lookup for Indian Mandi Districts
DISTRICT_COORDINATES: Dict[str, Tuple[float, float]] = {
    "nashik": (19.9975, 73.7898),
    "lasalgaon": (20.1472, 74.2256),
    "pune": (18.5204, 73.8567),
    "kolar": (13.1367, 78.1340),
    "bangalore": (12.9716, 77.5946),
    "ludhiana": (30.9010, 75.8573),
    "khanna": (30.7071, 76.2167),
    "agra": (27.1767, 78.0081),
    "rajkot": (22.3039, 70.8022),
    "indore": (22.7196, 75.8577),
    "alwar": (27.5530, 76.6346),
    "jaipur": (26.9124, 75.7873),
    "nagpur": (21.1458, 79.0882),
    "delhi": (28.6139, 77.2090),
}


class AnalyticsService:
    @staticmethod
    def get_historical_views(
        db: Session,
        commodity: str,
        market: str,
        granularity: str = "daily",
    ) -> HistoricalSeriesView:
        """
        Calculates daily, weekly, and monthly historical price aggregations,
        rolling averages (7d, 14d, 30d), price changes, and period comparisons.
        Strict rule: Missing dates are never interpreted as zero prices.
        """
        records = (
            db.query(MarketObservation)
            .filter(
                func.lower(MarketObservation.commodity) == commodity.lower(),
                func.lower(MarketObservation.market) == market.lower(),
            )
            .order_by(asc(MarketObservation.observation_date))
            .all()
        )

        if not records:
            return HistoricalSeriesView(
                commodity=commodity,
                market=market,
                granularity=granularity,
                total_observations=0,
                period_start=None,
                period_end=None,
                points=[],
                price_changes=[],
                current_vs_historical={},
            )

        df = pd.DataFrame([
            {
                "date": pd.to_datetime(r.observation_date),
                "modal_price": float(r.modal_price),
                "min_price": float(r.min_price) if r.min_price is not None else float(r.modal_price),
                "max_price": float(r.max_price) if r.max_price is not None else float(r.modal_price),
                "arrivals": float(r.arrivals_in_qtl) if r.arrivals_in_qtl is not None else np.nan,
            }
            for r in records
        ])
        df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)

        # 1. Price Changes (1-day, 7-day, 30-day)
        price_changes: List[PriceChangeMetric] = []
        latest_idx = len(df) - 1
        latest_date = df.loc[latest_idx, "date"].date()
        latest_price = float(df.loc[latest_idx, "modal_price"])

        # 1-day change
        if len(df) >= 2:
            prev_idx = latest_idx - 1
            p1_price = float(df.loc[prev_idx, "modal_price"])
            p1_date = df.loc[prev_idx, "date"].date()
            diff_1d = latest_price - p1_price
            pct_1d = (diff_1d / p1_price * 100.0) if p1_price > 0 else 0.0
            price_changes.append(
                PriceChangeMetric(
                    window_days=1,
                    window_label="1-Day Shift",
                    absolute_change=round(diff_1d, 2),
                    percentage_change=round(pct_1d, 2),
                    start_date=p1_date,
                    end_date=latest_date,
                    start_price=round(p1_price, 2),
                    end_price=round(latest_price, 2),
                )
            )

        # 7-day & 30-day changes based on calendar lookback
        for days, label in [(7, "7-Day Shift"), (30, "30-Day Shift")]:
            target_dt = pd.to_datetime(latest_date) - timedelta(days=days)
            prior_df = df[df["date"] <= target_dt]
            if not prior_df.empty:
                prior_row = prior_df.iloc[-1]
                p_price = float(prior_row["modal_price"])
                p_date = prior_row["date"].date()
                diff = latest_price - p_price
                pct = (diff / p_price * 100.0) if p_price > 0 else 0.0
                price_changes.append(
                    PriceChangeMetric(
                        window_days=days,
                        window_label=label,
                        absolute_change=round(diff, 2),
                        percentage_change=round(pct, 2),
                        start_date=p_date,
                        end_date=latest_date,
                        start_price=round(p_price, 2),
                        end_price=round(latest_price, 2),
                    )
                )

        # 2. Rolling Averages (7d, 14d, 30d) along observed series
        # We do not fill missing calendar dates with 0.
        df["rolling_7d"] = df["modal_price"].rolling(window=7, min_periods=1).mean()
        df["rolling_14d"] = df["modal_price"].rolling(window=14, min_periods=1).mean()
        df["rolling_30d"] = df["modal_price"].rolling(window=30, min_periods=1).mean()

        # 3. Aggregations based on requested granularity
        points: List[AggregatedPricePoint] = []
        granularity = granularity.lower().strip()

        if granularity == "weekly":
            # Group by year and ISO week
            df["year_week"] = df["date"].dt.strftime("%Y-W%U")
            for yw, group in df.groupby("year_week", sort=True):
                s_date = group["date"].min().date()
                e_date = group["date"].max().date()
                arrivals_sum = group["arrivals"].sum() if group["arrivals"].notna().any() else None
                points.append(
                    AggregatedPricePoint(
                        period_label=yw,
                        start_date=s_date,
                        end_date=e_date,
                        modal_price_avg=round(float(group["modal_price"].mean()), 2),
                        modal_price_min=round(float(group["min_price"].min()), 2),
                        modal_price_max=round(float(group["max_price"].max()), 2),
                        total_arrivals_qtl=round(float(arrivals_sum), 1) if arrivals_sum is not None else None,
                        observation_count=len(group),
                        rolling_7d_avg=round(float(group["rolling_7d"].iloc[-1]), 2),
                        rolling_14d_avg=round(float(group["rolling_14d"].iloc[-1]), 2),
                        rolling_30d_avg=round(float(group["rolling_30d"].iloc[-1]), 2),
                    )
                )

        elif granularity == "monthly":
            # Group by year-month
            df["year_month"] = df["date"].dt.strftime("%Y-%m")
            for ym, group in df.groupby("year_month", sort=True):
                s_date = group["date"].min().date()
                e_date = group["date"].max().date()
                arrivals_sum = group["arrivals"].sum() if group["arrivals"].notna().any() else None
                points.append(
                    AggregatedPricePoint(
                        period_label=ym,
                        start_date=s_date,
                        end_date=e_date,
                        modal_price_avg=round(float(group["modal_price"].mean()), 2),
                        modal_price_min=round(float(group["min_price"].min()), 2),
                        modal_price_max=round(float(group["max_price"].max()), 2),
                        total_arrivals_qtl=round(float(arrivals_sum), 1) if arrivals_sum is not None else None,
                        observation_count=len(group),
                        rolling_7d_avg=round(float(group["rolling_7d"].iloc[-1]), 2),
                        rolling_14d_avg=round(float(group["rolling_14d"].iloc[-1]), 2),
                        rolling_30d_avg=round(float(group["rolling_30d"].iloc[-1]), 2),
                    )
                )

        else:
            # Daily granularity
            for _, row in df.iterrows():
                dt = row["date"].date()
                arr = row["arrivals"] if pd.notna(row["arrivals"]) else None
                points.append(
                    AggregatedPricePoint(
                        period_label=dt.isoformat(),
                        start_date=dt,
                        end_date=dt,
                        modal_price_avg=round(float(row["modal_price"]), 2),
                        modal_price_min=round(float(row["min_price"]), 2),
                        modal_price_max=round(float(row["max_price"]), 2),
                        total_arrivals_qtl=round(float(arr), 1) if arr is not None else None,
                        observation_count=1,
                        rolling_7d_avg=round(float(row["rolling_7d"]), 2),
                        rolling_14d_avg=round(float(row["rolling_14d"]), 2),
                        rolling_30d_avg=round(float(row["rolling_30d"]), 2),
                    )
                )

        # 4. Current vs Historical Periods Comparison
        all_time_mean = float(df["modal_price"].mean())
        # Past 7 days
        recent_7d_df = df[df["date"] >= (pd.to_datetime(latest_date) - timedelta(days=7))]
        mean_7d = float(recent_7d_df["modal_price"].mean()) if not recent_7d_df.empty else latest_price

        # Past 30 days
        recent_30d_df = df[df["date"] >= (pd.to_datetime(latest_date) - timedelta(days=30))]
        mean_30d = float(recent_30d_df["modal_price"].mean()) if not recent_30d_df.empty else latest_price

        # Past 90 days
        recent_90d_df = df[df["date"] >= (pd.to_datetime(latest_date) - timedelta(days=90))]
        mean_90d = float(recent_90d_df["modal_price"].mean()) if not recent_90d_df.empty else latest_price

        current_comparisons = {
            "current_price": round(latest_price, 2),
            "latest_observation_date": latest_date.isoformat(),
            "vs_7d_mean": {
                "baseline_mean": round(mean_7d, 2),
                "absolute_diff": round(latest_price - mean_7d, 2),
                "percent_diff": round(((latest_price - mean_7d) / mean_7d) * 100.0, 2) if mean_7d > 0 else 0.0,
                "observation_count": len(recent_7d_df),
                "period_label": "Past 7 Calendar Days",
            },
            "vs_30d_mean": {
                "baseline_mean": round(mean_30d, 2),
                "absolute_diff": round(latest_price - mean_30d, 2),
                "percent_diff": round(((latest_price - mean_30d) / mean_30d) * 100.0, 2) if mean_30d > 0 else 0.0,
                "observation_count": len(recent_30d_df),
                "period_label": "Past 30 Calendar Days",
            },
            "vs_90d_mean": {
                "baseline_mean": round(mean_90d, 2),
                "absolute_diff": round(latest_price - mean_90d, 2),
                "percent_diff": round(((latest_price - mean_90d) / mean_90d) * 100.0, 2) if mean_90d > 0 else 0.0,
                "observation_count": len(recent_90d_df),
                "period_label": "Past 90 Calendar Days",
            },
            "vs_all_time_mean": {
                "baseline_mean": round(all_time_mean, 2),
                "absolute_diff": round(latest_price - all_time_mean, 2),
                "percent_diff": round(((latest_price - all_time_mean) / all_time_mean) * 100.0, 2) if all_time_mean > 0 else 0.0,
                "observation_count": len(df),
                "period_label": f"All Available Records ({df['date'].min().date().isoformat()} to {latest_date.isoformat()})",
            },
        }

        return HistoricalSeriesView(
            commodity=commodity,
            market=market,
            granularity=granularity,
            total_observations=len(df),
            period_start=df["date"].min().date(),
            period_end=latest_date,
            points=points,
            price_changes=price_changes,
            current_vs_historical=current_comparisons,
        )

    @staticmethod
    def get_seasonal_analysis(
        db: Session,
        commodity: str,
        market: str,
    ) -> SeasonalAnalysisResponse:
        """
        Analyzes monthly price distributions and Indian crop season groups.
        Evaluates historical span strictly: At least 2 full annual cycles (730 days)
        are required to claim recurring seasonal patterns.
        """
        records = (
            db.query(MarketObservation)
            .filter(
                func.lower(MarketObservation.commodity) == commodity.lower(),
                func.lower(MarketObservation.market) == market.lower(),
            )
            .order_by(asc(MarketObservation.observation_date))
            .all()
        )

        if not records:
            return SeasonalAnalysisResponse(
                commodity=commodity,
                market=market,
                total_observations=0,
                historical_span_days=0,
                historical_span_months=0.0,
                has_sufficient_multiyear_data=False,
                data_sufficiency_explanation="No historical observations found for this crop and mandi.",
                monthly_patterns=[],
                season_patterns=[],
            )

        df = pd.DataFrame([
            {
                "date": pd.to_datetime(r.observation_date),
                "modal_price": float(r.modal_price),
            }
            for r in records
        ])
        df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)

        min_date = df["date"].min().date()
        max_date = df["date"].max().date()
        span_days = (max_date - min_date).days + 1
        span_months = round(span_days / 30.4375, 1)

        # Multi-year requirement: >= 730 days (24 months)
        has_sufficient_multiyear = span_days >= 730
        if has_sufficient_multiyear:
            explanation = (
                f"Historical series spans {span_months} months across multiple annual cycles ({min_date} to {max_date}). "
                "Sufficient multi-year depth is available to compute empirical recurring seasonal indices without single-year bias."
            )
        else:
            explanation = (
                f"Historical observations span {span_months} months ({span_days} days from {min_date} to {max_date}). "
                "Recurring seasonal decomposition strictly requires at least 2 complete annual cycles (24 months / 730 days) "
                "to isolate true harvest calendar patterns from single-season supply shocks. Monthly figures below represent "
                "observed intra-sample averages for the current available period."
            )

        # 1. Monthly Pattern (Months 1 to 12)
        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        df["month"] = df["date"].dt.month
        monthly_patterns: List[MonthlySeasonalityPoint] = []

        for m in range(1, 13):
            m_group = df[df["month"] == m]
            if not m_group.empty:
                prices = m_group["modal_price"]
                std_val = float(prices.std()) if len(prices) > 1 else 0.0
                monthly_patterns.append(
                    MonthlySeasonalityPoint(
                        month_number=m,
                        month_name=month_names[m - 1],
                        avg_modal_price=round(float(prices.mean()), 2),
                        min_modal_price=round(float(prices.min()), 2),
                        max_modal_price=round(float(prices.max()), 2),
                        std_modal_price=round(std_val, 2),
                        observation_count=len(m_group),
                    )
                )

        # 2. Indian Crop Seasons
        # Kharif: July - October (7 to 10)
        # Rabi: November - March (11, 12, 1, 2, 3)
        # Zaid: April - June (4 to 6)
        season_groups = [
            {
                "name": "Kharif Season",
                "months": "July – October",
                "filter": df["month"].isin([7, 8, 9, 10]),
                "context": "Monsoon crop cycle: high precipitation, sowing in July, harvesting in autumn.",
            },
            {
                "name": "Rabi Season",
                "months": "November – March",
                "filter": df["month"].isin([11, 12, 1, 2, 3]),
                "context": "Winter crop cycle: post-monsoon sub-soil moisture, cooler temperatures, spring harvest.",
            },
            {
                "name": "Zaid / Summer Season",
                "months": "April – June",
                "filter": df["month"].isin([4, 5, 6]),
                "context": "Summer pre-monsoon cycle: warm temperatures, irrigated riverbed cultivation.",
            },
        ]

        season_patterns: List[SeasonGroupPoint] = []
        for sg in season_groups:
            s_df = df[sg["filter"]]
            if not s_df.empty:
                season_patterns.append(
                    SeasonGroupPoint(
                        season_name=sg["name"],
                        months_included=sg["months"],
                        avg_modal_price=round(float(s_df["modal_price"].mean()), 2),
                        observation_count=len(s_df),
                        crop_season_context=sg["context"],
                    )
                )

        return SeasonalAnalysisResponse(
            commodity=commodity,
            market=market,
            total_observations=len(df),
            historical_span_days=span_days,
            historical_span_months=span_months,
            has_sufficient_multiyear_data=has_sufficient_multiyear,
            data_sufficiency_explanation=explanation,
            monthly_patterns=monthly_patterns,
            season_patterns=season_patterns,
        )

    @staticmethod
    def detect_anomalies(
        db: Session,
        commodity: str,
        market: str,
        threshold_multiplier: float = 2.5,
        method: str = "rolling_zscore",
    ) -> AnomalyDetectionResponse:
        """
        Detects unusually high or low observations relative to an empirical historical baseline.
        Configurable threshold (default 2.5 sigma).
        Distinguishes statistical price spikes from verified data errors (negative prices, inverted bounds).
        Crucial: Never deletes observations automatically.
        """
        records = (
            db.query(MarketObservation)
            .filter(
                func.lower(MarketObservation.commodity) == commodity.lower(),
                func.lower(MarketObservation.market) == market.lower(),
            )
            .order_by(asc(MarketObservation.observation_date))
            .all()
        )

        method = method.lower().strip()
        if method not in ("rolling_zscore", "iqr"):
            method = "rolling_zscore"

        threshold_multiplier = max(1.5, min(4.0, float(threshold_multiplier)))

        if not records or len(records) < 5:
            return AnomalyDetectionResponse(
                commodity=commodity,
                market=market,
                detection_method=method,
                threshold_multiplier=threshold_multiplier,
                total_observations_analyzed=len(records),
                anomaly_count=0,
                data_error_count=0,
                anomalies=[],
                method_explanation=f"Minimum 5 observations required to compute statistical anomaly bounds. Currently {len(records)} found.",
            )

        df = pd.DataFrame([
            {
                "id": r.id,
                "date": pd.to_datetime(r.observation_date),
                "modal_price": float(r.modal_price),
                "min_price": float(r.min_price) if r.min_price is not None else float(r.modal_price),
                "max_price": float(r.max_price) if r.max_price is not None else float(r.modal_price),
                "arrivals": float(r.arrivals_in_qtl) if r.arrivals_in_qtl is not None else None,
            }
            for r in records
        ])
        df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)

        n = len(df)
        anomalies: List[AnomalyItem] = []
        data_error_count = 0

        # Method 1: Rolling Z-Score
        if method == "rolling_zscore":
            window_size = min(30, max(5, n))
            df["baseline"] = df["modal_price"].rolling(window=window_size, min_periods=3, center=False).mean()
            df["rolling_std"] = df["modal_price"].rolling(window=window_size, min_periods=3, center=False).std()
            # Forward-fill initial points where rolling std is undefined
            df["baseline"] = df["baseline"].bfill().fillna(df["modal_price"].mean())
            df["rolling_std"] = df["rolling_std"].bfill().fillna(df["modal_price"].std())
            # Floor standard deviation to prevent division by zero in flat periods
            df["rolling_std"] = df["rolling_std"].clip(lower=10.0)

            method_explanation = (
                f"Rolling Z-Score Anomaly Detection ({window_size}-day trailing window, {threshold_multiplier}σ threshold). "
                f"Flags prices diverging by more than {threshold_multiplier} standard deviations from the rolling wholesale baseline."
            )

            for _, row in df.iterrows():
                obs_date = row["date"].date()
                price = row["modal_price"]
                min_p = row["min_price"]
                max_p = row["max_price"]
                baseline = row["baseline"]
                std_dev = row["rolling_std"]

                upper_thresh = baseline + threshold_multiplier * std_dev
                lower_thresh = max(0.0, baseline - threshold_multiplier * std_dev)
                z = (price - baseline) / std_dev
                diff = price - baseline

                # Check for verified data error first
                is_data_error = False
                error_reasons = []

                if price <= 0:
                    is_data_error = True
                    error_reasons.append("Non-positive modal price (reporting zero/negative rate)")
                if min_p > max_p:
                    is_data_error = True
                    error_reasons.append(f"Inverted price boundary (Min ₹{min_p} > Max ₹{max_p})")
                if abs(z) >= 5.0 and (row["arrivals"] is None or row["arrivals"] == 0):
                    is_data_error = True
                    error_reasons.append(f"Implausibly extreme price deviation ({z:+.1f}σ) with zero reported market arrivals")

                if is_data_error:
                    data_error_count += 1
                    anomalies.append(
                        AnomalyItem(
                            observation_date=obs_date,
                            commodity=commodity,
                            market=market,
                            modal_price=round(price, 2),
                            baseline_price=round(baseline, 2),
                            threshold_upper=round(upper_thresh, 2),
                            threshold_lower=round(lower_thresh, 2),
                            deviation_amount=round(diff, 2),
                            z_score=round(z, 2),
                            anomaly_type="SUSPECTED_DATA_ERROR",
                            severity="EXTREME",
                            explanation=f"Suspected Data Error: {'; '.join(error_reasons)}.",
                            is_verified_data_error=True,
                        )
                    )
                elif price > upper_thresh or price < lower_thresh:
                    # Valid statistical price anomaly
                    a_type = "HIGH_SPIKE" if price > upper_thresh else "LOW_CRASH"
                    abs_z = abs(z)
                    severity = "EXTREME" if abs_z >= 3.5 else "MODERATE" if abs_z >= 2.5 else "MILD"

                    direction_text = "exceeded upper bound" if a_type == "HIGH_SPIKE" else "fell below lower bound"
                    explanation = (
                        f"Modal price ₹{price:,.0f} {direction_text} of ₹{upper_thresh if a_type == 'HIGH_SPIKE' else lower_thresh:,.0f} "
                        f"by ₹{abs(diff):,.0f} (Z-Score: {z:+.2f}). "
                        f"Deviation exceeds {threshold_multiplier}σ threshold relative to {window_size}-day baseline (₹{baseline:,.0f})."
                    )

                    anomalies.append(
                        AnomalyItem(
                            observation_date=obs_date,
                            commodity=commodity,
                            market=market,
                            modal_price=round(price, 2),
                            baseline_price=round(baseline, 2),
                            threshold_upper=round(upper_thresh, 2),
                            threshold_lower=round(lower_thresh, 2),
                            deviation_amount=round(diff, 2),
                            z_score=round(z, 2),
                            anomaly_type=a_type,
                            severity=severity,
                            explanation=explanation,
                            is_verified_data_error=False,
                        )
                    )

        # Method 2: IQR (Interquartile Range)
        else:
            q1 = float(df["modal_price"].quantile(0.25))
            q3 = float(df["modal_price"].quantile(0.75))
            iqr = q3 - q1
            median_val = float(df["modal_price"].median())
            upper_thresh = q3 + threshold_multiplier * iqr
            lower_thresh = max(0.0, q1 - threshold_multiplier * iqr)

            method_explanation = (
                f"Tukey's IQR Anomaly Detection (Multiplier: {threshold_multiplier}×IQR). "
                f"Q1=₹{q1:,.0f}, Median=₹{median_val:,.0f}, Q3=₹{q3:,.0f}, IQR=₹{iqr:,.0f}. "
                f"Flags prices outside [₹{lower_thresh:,.0f}, ₹{upper_thresh:,.0f}]."
            )

            for _, row in df.iterrows():
                obs_date = row["date"].date()
                price = row["modal_price"]
                min_p = row["min_price"]
                max_p = row["max_price"]
                diff = price - median_val

                # Check data error
                is_data_error = price <= 0 or min_p > max_p
                if is_data_error:
                    data_error_count += 1
                    anomalies.append(
                        AnomalyItem(
                            observation_date=obs_date,
                            commodity=commodity,
                            market=market,
                            modal_price=round(price, 2),
                            baseline_price=round(median_val, 2),
                            threshold_upper=round(upper_thresh, 2),
                            threshold_lower=round(lower_thresh, 2),
                            deviation_amount=round(diff, 2),
                            z_score=None,
                            anomaly_type="SUSPECTED_DATA_ERROR",
                            severity="EXTREME",
                            explanation="Suspected Data Error: Non-positive price or inverted min/max bounds.",
                            is_verified_data_error=True,
                        )
                    )
                elif price > upper_thresh or price < lower_thresh:
                    a_type = "HIGH_SPIKE" if price > upper_thresh else "LOW_CRASH"
                    anomalies.append(
                        AnomalyItem(
                            observation_date=obs_date,
                            commodity=commodity,
                            market=market,
                            modal_price=round(price, 2),
                            baseline_price=round(median_val, 2),
                            threshold_upper=round(upper_thresh, 2),
                            threshold_lower=round(lower_thresh, 2),
                            deviation_amount=round(diff, 2),
                            z_score=None,
                            anomaly_type=a_type,
                            severity="MODERATE",
                            explanation=f"Price ₹{price:,.0f} diverged outside IQR threshold limits by ₹{abs(diff):,.0f}.",
                            is_verified_data_error=False,
                        )
                    )

        # Sort anomalies latest date first
        anomalies.sort(key=lambda x: x.observation_date, reverse=True)

        return AnomalyDetectionResponse(
            commodity=commodity,
            market=market,
            detection_method=method,
            threshold_multiplier=threshold_multiplier,
            total_observations_analyzed=len(df),
            anomaly_count=len(anomalies),
            data_error_count=data_error_count,
            anomalies=anomalies,
            method_explanation=method_explanation,
        )

    @staticmethod
    def get_arrivals_weather_analysis(
        db: Session,
        commodity: str,
        market: str,
    ) -> ArrivalsWeatherResponse:
        """
        Analyzes authentic reported market arrivals, calculates price-volume correlation,
        and provides location-aligned weather integration via Open-Meteo Historical Archive.
        Strict rule: Does not fabricate weather observations or claim unproven causation.
        """
        records = (
            db.query(MarketObservation)
            .filter(
                func.lower(MarketObservation.commodity) == commodity.lower(),
                func.lower(MarketObservation.market) == market.lower(),
            )
            .order_by(asc(MarketObservation.observation_date))
            .all()
        )

        total_obs = len(records)
        if total_obs == 0:
            return ArrivalsWeatherResponse(
                commodity=commodity,
                market=market,
                total_observations=0,
                arrivals_reported_count=0,
                arrivals_coverage_pct=0.0,
                price_arrival_correlation=None,
                correlation_significance=None,
                correlation_interpretation="No observations available for analysis.",
                weather_source=WEATHER_SOURCE,
                weather_available=False,
                weather_data_notes="No market records to align coordinates.",
                weather_status="NO_MARKET_DATES",
                weather_attribution_url=WEATHER_ATTRIBUTION_URL,
            )

        # 1. Market Arrivals Evaluation
        valid_arrivals = [r for r in records if r.arrivals_in_qtl is not None and r.arrivals_in_qtl > 0]
        arrivals_count = len(valid_arrivals)
        coverage_pct = round((arrivals_count / total_obs) * 100.0, 1)

        corr_val: Optional[float] = None
        corr_sig: Optional[str] = None
        corr_interp = ""

        if arrivals_count >= 5:
            arr_vals = np.array([r.arrivals_in_qtl for r in valid_arrivals], dtype=float)
            price_vals = np.array([r.modal_price for r in valid_arrivals], dtype=float)

            # Avoid division by zero if prices or arrivals are completely constant
            if np.std(arr_vals) > 0 and np.std(price_vals) > 0:
                r_coeff, p_val = stats.pearsonr(arr_vals, price_vals)
                corr_val = round(float(r_coeff), 3)
                corr_sig = f"p={p_val:.4f} ({'Statistically Significant' if p_val < 0.05 else 'Not Statistically Significant'})"

                if corr_val < -0.2:
                    corr_interp = (
                        f"Inverse relationship (r = {corr_val:+.3f}): Days with higher reported mandi arrival volumes "
                        "statistically coincide with softer wholesale prices (supply absorption pressure). "
                        "Note: Market arrivals reflect physical intake at this APMC and do not directly measure consumer demand."
                    )
                elif corr_val > 0.2:
                    corr_interp = (
                        f"Positive co-movement (r = {corr_val:+.3f}): Higher arrivals coincide with firm prices, "
                        "commonly observed during the early harvest window when high volume of premium fresh arrivals enters the mandi. "
                        "Correlation does not imply that volume causes price appreciation."
                    )
                else:
                    corr_interp = (
                        f"Neutral correlation (r = {corr_val:+.3f}): Daily arrival volumes show minimal linear association "
                        "with daily modal price variations across the observed sample."
                    )
            else:
                corr_interp = "Arrivals or prices lack sufficient variance across the sample to estimate correlation."
        else:
            corr_interp = (
                f"Limited arrival volume reporting ({arrivals_count} of {total_obs} records contain arrival figures). "
                "Minimum 5 valid volume observations required to calculate statistical correlation."
            )

        # 2. Weather Data Alignment
        market_clean = market.lower().strip()
        coords = DISTRICT_COORDINATES.get(market_clean)
        if not coords:
            # Check state/district if available in record
            district_clean = records[0].district.lower().strip() if records[0].district else ""
            coords = DISTRICT_COORDINATES.get(district_clean)

        weather_status = "NO_COORDINATES"
        weather_location = None
        aligned_weather = []
        missing_weather_dates = len({r.observation_date for r in records})
        if coords:
            lat, lon = coords
            market_coordinate = market_clean in DISTRICT_COORDINATES
            location_name = market if market_coordinate else (records[0].district or market)
            weather_location = {
                "name": location_name,
                "latitude": lat,
                "longitude": lon,
                "coordinate_precision": "Approximate market or district metadata; not a station location",
            }
            unique_market_dates = {r.observation_date for r in records}
            fetched = WeatherService.get_daily_weather(
                lat,
                lon,
                min(unique_market_dates),
                max(unique_market_dates),
            )
            weather_by_date = {
                item["observation_date"]: item
                for item in fetched["records"]
            }
            aligned_weather = [
                weather_by_date[day]
                for day in sorted(unique_market_dates)
                if day in weather_by_date
            ]
            missing_weather_dates = len(unique_market_dates) - len(aligned_weather)
            weather_status = fetched["status"]
            if aligned_weather:
                weather_status = "AVAILABLE" if missing_weather_dates == 0 else "PARTIAL"
            elif fetched["status"] == "AVAILABLE":
                weather_status = "NO_DATA"

        weather_available = bool(aligned_weather)
        if weather_status in ("AVAILABLE", "PARTIAL"):
            weather_notes = (
                f"Retrieved {len(aligned_weather)} daily ERA5 reanalysis rows aligned to market observation dates; "
                f"{missing_weather_dates} of {len({r.observation_date for r in records})} market dates have no aligned weather row. "
                "Values represent gridded historical reanalysis at approximate market/district coordinates, not on-site station measurements. "
                "Weather is shown as context; no price-weather correlation or causal effect is calculated."
            )
        elif weather_status == "NO_COORDINATES":
            weather_notes = (
                f"No supported coordinate metadata is available for mandi '{market}'. "
                "No weather request was made; existing market analytics remain available."
            )
        else:
            weather_notes = (
                f"Weather data is currently unavailable ({weather_status.lower().replace('_', ' ')}). "
                "No weather values were substituted or inferred; existing market analytics remain available."
            )

        return ArrivalsWeatherResponse(
            commodity=commodity,
            market=market,
            total_observations=total_obs,
            arrivals_reported_count=arrivals_count,
            arrivals_coverage_pct=coverage_pct,
            price_arrival_correlation=corr_val,
            correlation_significance=corr_sig,
            correlation_interpretation=corr_interp,
            weather_source=WEATHER_SOURCE,
            weather_available=weather_available,
            weather_data_notes=weather_notes,
            weather_status=weather_status,
            weather_location=weather_location,
            weather_observations=aligned_weather,
            weather_aligned_count=len(aligned_weather),
            weather_missing_date_count=missing_weather_dates,
            weather_attribution_url=WEATHER_ATTRIBUTION_URL,
        )
