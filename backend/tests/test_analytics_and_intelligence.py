import datetime
import pytest
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import get_db, SessionLocal
from app.models.market_observation import MarketObservation
from app.services.analytics_service import AnalyticsService
from app.services.forecasting_service import ForecastingService
from app.services.weather_service import WeatherService

client = TestClient(app)


# ---------------------------------------------------------------------------
# FIXTURES FOR SYNTHETIC EDGE CASES & ANOMALIES
# (Explicitly isolated and tagged to avoid presenting as real market observations)
# ---------------------------------------------------------------------------
@pytest.fixture
def synthetic_anomaly_data(db_session: Session):
    """
    Inserts a strictly labeled synthetic series to test anomaly detection
    with known high spikes, low crashes, and data entry errors.
    Cleans up after test execution.
    """
    tag_commodity = "SyntheticTestCrop"
    tag_market = "SyntheticMandi"
    base_date = datetime.date(2025, 1, 1)

    records = []
    # 30 days of baseline stable prices around 2000
    for i in range(30):
        records.append(
            MarketObservation(
                commodity=tag_commodity,
                market=tag_market,
                state="Maharashtra",
                district="Nashik",
                observation_date=base_date + datetime.timedelta(days=i),
                modal_price=2000.0 + (i % 3) * 20.0,
                min_price=1900.0,
                max_price=2100.0,
                arrivals_in_qtl=500.0,
                source="SYNTHETIC_TEST_FIXTURE",
            )
        )

    # Day 30: High Spike (Modal = 4800, well above 2.5 sigma)
    records.append(
        MarketObservation(
            commodity=tag_commodity,
            market=tag_market,
            state="Maharashtra",
            district="Nashik",
            observation_date=base_date + datetime.timedelta(days=30),
            modal_price=4800.0,
            min_price=4600.0,
            max_price=5000.0,
            arrivals_in_qtl=200.0,
            source="SYNTHETIC_TEST_FIXTURE",
        )
    )

    # Day 31: Low Crash (Modal = 600, well below 2.5 sigma)
    records.append(
        MarketObservation(
            commodity=tag_commodity,
            market=tag_market,
            state="Maharashtra",
            district="Nashik",
            observation_date=base_date + datetime.timedelta(days=31),
            modal_price=600.0,
            min_price=500.0,
            max_price=700.0,
            arrivals_in_qtl=1200.0,
            source="SYNTHETIC_TEST_FIXTURE",
        )
    )

    # Day 32: Inverted price boundary data error (Min 3000 > Max 2500)
    records.append(
        MarketObservation(
            commodity=tag_commodity,
            market=tag_market,
            state="Maharashtra",
            district="Nashik",
            observation_date=base_date + datetime.timedelta(days=32),
            modal_price=2700.0,
            min_price=3000.0,
            max_price=2500.0,
            arrivals_in_qtl=400.0,
            source="SYNTHETIC_TEST_FIXTURE",
        )
    )

    # Day 33: Non-positive price data error (Modal = 0.0)
    records.append(
        MarketObservation(
            commodity=tag_commodity,
            market=tag_market,
            state="Maharashtra",
            district="Nashik",
            observation_date=base_date + datetime.timedelta(days=33),
            modal_price=0.0,
            min_price=0.0,
            max_price=0.0,
            arrivals_in_qtl=100.0,
            source="SYNTHETIC_TEST_FIXTURE",
        )
    )

    db_session.add_all(records)
    db_session.commit()

    yield {"commodity": tag_commodity, "market": tag_market, "total_records": len(records)}

    # Cleanup: Never leave synthetic fixture data in DB
    db_session.query(MarketObservation).filter(
        MarketObservation.commodity == tag_commodity,
        MarketObservation.market == tag_market
    ).delete()
    db_session.commit()


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 1. HISTORICAL PRICE AND SEASONAL ANALYSIS TESTS
# ---------------------------------------------------------------------------
def test_historical_views_daily_weekly_monthly(db_session: Session):
    """Test daily, weekly, and monthly resampled historical views using real Lasalgaon Onion data."""
    # Daily view
    daily_res = AnalyticsService.get_historical_views(
        db=db_session, commodity="Onion", market="Lasalgaon", granularity="daily"
    )
    assert daily_res.total_observations > 0
    assert daily_res.granularity == "daily"
    assert len(daily_res.points) == daily_res.total_observations
    assert daily_res.period_start is not None
    assert daily_res.period_end is not None

    # Check rolling averages exist on daily points
    assert any(pt.rolling_7d_avg is not None for pt in daily_res.points)
    assert any(pt.rolling_14d_avg is not None for pt in daily_res.points)
    assert any(pt.rolling_30d_avg is not None for pt in daily_res.points)

    # Weekly view
    weekly_res = AnalyticsService.get_historical_views(
        db=db_session, commodity="Onion", market="Lasalgaon", granularity="weekly"
    )
    assert weekly_res.granularity == "weekly"
    assert 0 < len(weekly_res.points) <= len(daily_res.points)

    # Monthly view
    monthly_res = AnalyticsService.get_historical_views(
        db=db_session, commodity="Onion", market="Lasalgaon", granularity="monthly"
    )
    assert monthly_res.granularity == "monthly"
    assert 0 < len(monthly_res.points) <= len(weekly_res.points)


def test_missing_dates_are_not_filled_with_zeros(db_session: Session):
    """
    STRICT REQUIREMENT: Missing dates must not be interpreted as zero prices.
    Verify that in daily granularity, all price points have genuine non-zero prices.
    """
    res = AnalyticsService.get_historical_views(
        db=db_session, commodity="Onion", market="Lasalgaon", granularity="daily"
    )
    for pt in res.points:
        assert pt.modal_price_avg > 0.0, f"Found zero or negative price at {pt.period_label}"


def test_price_change_calculations(db_session: Session):
    """Verify 1-day, 7-day, and 30-day price shift calculations."""
    res = AnalyticsService.get_historical_views(
        db=db_session, commodity="Onion", market="Lasalgaon", granularity="daily"
    )
    assert len(res.price_changes) > 0
    windows = [c.window_days for c in res.price_changes]
    assert 1 in windows

    one_day = next(c for c in res.price_changes if c.window_days == 1)
    assert one_day.start_price > 0
    assert one_day.end_price > 0
    expected_diff = round(one_day.end_price - one_day.start_price, 2)
    assert abs(one_day.absolute_change - expected_diff) < 0.05
    expected_pct = round((expected_diff / one_day.start_price) * 100.0, 2)
    assert abs(one_day.percentage_change - expected_pct) < 0.05


def test_current_vs_historical_baselines(db_session: Session):
    """Verify current price comparison with 7d, 30d, 90d, and all-time averages."""
    res = AnalyticsService.get_historical_views(
        db=db_session, commodity="Onion", market="Lasalgaon", granularity="daily"
    )
    assert "vs_7d_mean" in res.current_vs_historical
    assert "vs_30d_mean" in res.current_vs_historical
    assert "vs_all_time_mean" in res.current_vs_historical
    assert res.current_vs_historical["vs_all_time_mean"]["baseline_mean"] > 0


def test_seasonal_analysis_and_multiyear_sufficiency(db_session: Session):
    """
    STRICT REQUIREMENT: Do not claim a recurring seasonal pattern from insufficient historical data.
    If historical span < 730 days (24 months), has_sufficient_multiyear_data MUST be False.
    """
    seasonal_res = AnalyticsService.get_seasonal_analysis(
        db=db_session, commodity="Onion", market="Lasalgaon"
    )
    assert seasonal_res.total_observations > 0
    assert len(seasonal_res.monthly_patterns) > 0
    assert len(seasonal_res.season_patterns) > 0

    # Since current database span is ~297 days (< 730 days), multi-year must be False
    if seasonal_res.historical_span_days < 730:
        assert seasonal_res.has_sufficient_multiyear_data is False
        assert "at least 2 complete annual cycles" in seasonal_res.data_sufficiency_explanation
    else:
        assert seasonal_res.has_sufficient_multiyear_data is True


def test_seasonal_insufficient_data_empty(db_session: Session):
    """Verify seasonal analysis handles non-existent or empty commodities gracefully."""
    empty_res = AnalyticsService.get_seasonal_analysis(
        db=db_session, commodity="NonExistentCrop", market="NonExistentMandi"
    )
    assert empty_res.total_observations == 0
    assert empty_res.has_sufficient_multiyear_data is False
    assert len(empty_res.monthly_patterns) == 0


# ---------------------------------------------------------------------------
# 2. PRICE ANOMALY DETECTION TESTS
# ---------------------------------------------------------------------------
def test_anomaly_detection_with_synthetic_fixtures(db_session: Session, synthetic_anomaly_data):
    """
    Detect unusually high or low observations and distinguish data errors from statistical anomalies.
    Uses synthetic fixture and verifies no observations are deleted.
    """
    comm = synthetic_anomaly_data["commodity"]
    mkt = synthetic_anomaly_data["market"]

    # Rolling Z-score method (threshold = 2.5)
    res_z = AnalyticsService.detect_anomalies(
        db=db_session, commodity=comm, market=mkt, threshold_multiplier=2.5, method="rolling_zscore"
    )
    assert res_z.total_observations_analyzed == synthetic_anomaly_data["total_records"]
    assert res_z.anomaly_count > 0

    types = [a.anomaly_type for a in res_z.anomalies]
    # Check that high spike was detected
    assert "HIGH_SPIKE" in types
    # Check that low crash was detected
    assert "LOW_CRASH" in types
    # Check that data errors were detected and distinguished
    assert "SUSPECTED_DATA_ERROR" in types

    high_spike = next(a for a in res_z.anomalies if a.anomaly_type == "HIGH_SPIKE")
    assert high_spike.modal_price == 4800.0
    assert high_spike.is_verified_data_error is False
    assert "exceeded upper bound" in high_spike.explanation

    low_crash = next(a for a in res_z.anomalies if a.anomaly_type == "LOW_CRASH")
    assert low_crash.modal_price == 600.0
    assert low_crash.is_verified_data_error is False
    assert "fell below lower bound" in low_crash.explanation

    data_errors = [a for a in res_z.anomalies if a.anomaly_type == "SUSPECTED_DATA_ERROR"]
    assert len(data_errors) >= 2
    # Verify non-positive modal price flagged
    zero_price_err = next((e for e in data_errors if e.modal_price == 0.0), None)
    assert zero_price_err is not None
    assert zero_price_err.is_verified_data_error is True

    # Verify inverted price boundary flagged
    inverted_err = next((e for e in data_errors if e.modal_price == 2700.0), None)
    assert inverted_err is not None
    assert "Inverted price boundary" in inverted_err.explanation

    # Verify STRICT RULE: Anomaly detection must NOT delete records from DB
    remaining_count = (
        db_session.query(MarketObservation)
        .filter(
            MarketObservation.commodity == comm,
            MarketObservation.market == mkt,
        )
        .count()
    )
    assert remaining_count == synthetic_anomaly_data["total_records"], "Observations were deleted!"


def test_anomaly_detection_threshold_configurability(db_session: Session, synthetic_anomaly_data):
    """Verify that changing the threshold multiplier alters detection sensitivity."""
    comm = synthetic_anomaly_data["commodity"]
    mkt = synthetic_anomaly_data["market"]

    # Stricter threshold (3.5 sigma) vs relaxed threshold (1.8 sigma)
    res_strict = AnalyticsService.detect_anomalies(
        db=db_session, commodity=comm, market=mkt, threshold_multiplier=3.5, method="rolling_zscore"
    )
    res_relaxed = AnalyticsService.detect_anomalies(
        db=db_session, commodity=comm, market=mkt, threshold_multiplier=1.8, method="rolling_zscore"
    )

    # Relaxed threshold should flag >= anomalies than strict threshold
    assert res_relaxed.anomaly_count >= res_strict.anomaly_count


def test_anomaly_detection_iqr_method(db_session: Session, synthetic_anomaly_data):
    """Verify Tukey's IQR anomaly detection method."""
    comm = synthetic_anomaly_data["commodity"]
    mkt = synthetic_anomaly_data["market"]

    res_iqr = AnalyticsService.detect_anomalies(
        db=db_session, commodity=comm, market=mkt, threshold_multiplier=1.5, method="iqr"
    )
    assert res_iqr.detection_method == "iqr"
    assert res_iqr.anomaly_count > 0
    assert "Tukey's IQR Anomaly Detection" in res_iqr.method_explanation


def test_anomaly_detection_insufficient_data(db_session: Session):
    """Test anomaly detection handles < 5 records gracefully."""
    res = AnalyticsService.detect_anomalies(
        db=db_session, commodity="RareCrop", market="TinyMandi", threshold_multiplier=2.5
    )
    assert res.total_observations_analyzed == 0
    assert res.anomaly_count == 0
    assert "Minimum 5 observations required" in res.method_explanation


# ---------------------------------------------------------------------------
# 3. EXPLAINABLE MACHINE LEARNING TESTS
# ---------------------------------------------------------------------------
def test_explain_model_trained_with_shap(db_session: Session):
    """
    Test explainable ML feature importance with real data.
    Verifies SHAP linear explainer execution, feature weights summing to ~100%,
    directions (positive/negative), and causality disclaimer.
    """
    res = ForecastingService.explain_model(
        db=db_session, commodity="Onion", market="Lasalgaon"
    )
    assert res.is_explainable is True
    assert res.total_training_samples >= 20
    assert len(res.features) > 0
    assert res.shap_summary_available is True
    assert res.shap_base_value is not None

    # Check sum of percentage importances is ~100%
    total_pct = sum(f.importance_pct for f in res.features)
    assert 99.0 <= total_pct <= 101.0

    # Check required feature elements
    feature_names = [f.feature_name for f in res.features]
    assert "lag_1" in feature_names
    assert "rolling_mean_7" in feature_names
    assert "arrivals" in feature_names

    # Check directions are valid
    for f in res.features:
        assert f.direction in ("positive", "negative", "neutral")
        assert len(f.description) > 10

    # Check causality disclaimer
    assert "They do NOT prove economic or physical causality" in res.causality_disclaimer


def test_explain_model_insufficient_data(db_session: Session):
    """
    STRICT REQUIREMENT: If a model lacks enough training data, explain why its
    feature importance cannot yet be calculated. Never fabricate feature importance.
    """
    res = ForecastingService.explain_model(
        db=db_session, commodity="ExoticCrop", market="SparseMandi"
    )
    assert res.is_explainable is False
    assert len(res.features) == 0
    assert res.shap_summary_available is False
    assert "Minimum 20 daily observations are required" in res.message


# ---------------------------------------------------------------------------
# 4. FORECAST UNCERTAINTY AND RISK TESTS
# ---------------------------------------------------------------------------
def test_forecast_uncertainty_horizons(db_session: Session):
    """
    Test uncertainty estimation across 7d, 14d, 30d horizons.
    Checks empirical holdout RMSE/MAE/MAPE, confidence spreads, and disclaimers.
    """
    res = ForecastingService.get_forecast_uncertainty(
        db=db_session, commodity="Onion", market="Lasalgaon"
    )
    assert res.is_sample_sufficient is True
    assert res.evaluation_sample_size > 0
    assert len(res.horizons) == 3

    horizon_days = [h.horizon_days for h in res.horizons]
    assert horizon_days == [7, 14, 30]

    for h in res.horizons:
        assert h.holdout_mae >= 0.0
        assert h.holdout_rmse >= 0.0
        assert h.holdout_mape >= 0.0
        assert h.confidence_spread_pct > 0.0
        assert h.reliability_tier in ("High", "Moderate", "Extrapolated")

    # STRICT REQUIREMENT: Prediction intervals must NOT be called guaranteed ranges
    assert "do NOT constitute guaranteed future price limits" in res.disclaimer


def test_forecast_uncertainty_insufficient_data(db_session: Session):
    """Verify uncertainty handling when historical depth is < 14 observations."""
    res = ForecastingService.get_forecast_uncertainty(
        db=db_session, commodity="RareCrop", market="SparseMandi"
    )
    assert res.is_sample_sufficient is False
    assert len(res.horizons) == 0
    assert "minimum of 14 continuous historical observations is required" in res.methodology_explanation


# ---------------------------------------------------------------------------
# 5. WEATHER AND MARKET ARRIVALS TESTS
# ---------------------------------------------------------------------------
def test_arrivals_weather_analysis(db_session: Session, monkeypatch):
    """
    Verify market arrivals coverage and Pearson correlation calculation.
    Verify documented weather source (Open-Meteo Historical Archive) and causality caveat.
    """
    market_records = (
        db_session.query(MarketObservation)
        .filter(MarketObservation.commodity == "Onion", MarketObservation.market == "Lasalgaon")
        .all()
    )
    weather_rows = [
        {
            "observation_date": record.observation_date,
            "temperature_max_c": 24.0,
            "temperature_min_c": 13.0,
            "precipitation_mm": 0.0,
        }
        for record in market_records
    ]
    monkeypatch.setattr(
        WeatherService,
        "get_daily_weather",
        lambda *args: {"status": "AVAILABLE", "records": weather_rows, "message": "mocked"},
    )
    res = AnalyticsService.get_arrivals_weather_analysis(
        db=db_session, commodity="Onion", market="Lasalgaon"
    )
    assert res.total_observations > 0
    assert 0.0 <= res.arrivals_coverage_pct <= 100.0
    if res.price_arrival_correlation is not None:
        assert -1.0 <= res.price_arrival_correlation <= 1.0

    # Check documented weather source metadata
    assert "Open-Meteo Historical Weather API" in res.weather_source
    assert res.weather_available is True
    assert res.weather_aligned_count == len(weather_rows)

    # Check causality caveat
    assert "arrival" in res.correlation_interpretation.lower()
    assert "weather" in res.weather_data_notes.lower()
    assert "no price-weather correlation" in res.weather_data_notes.lower()


# ---------------------------------------------------------------------------
# 6. FASTAPI ENDPOINTS INTEGRATION TESTS
# ---------------------------------------------------------------------------
def test_api_historical_views_endpoint():
    response = client.get("/api/analytics/historical-views?commodity=Onion&market=Lasalgaon&granularity=daily")
    assert response.status_code == 200
    data = response.json()
    assert data["commodity"] == "Onion"
    assert data["granularity"] == "daily"
    assert "points" in data
    assert "price_changes" in data
    assert "current_vs_historical" in data


def test_api_seasonal_endpoint():
    response = client.get("/api/analytics/seasonal?commodity=Onion&market=Lasalgaon")
    assert response.status_code == 200
    data = response.json()
    assert data["commodity"] == "Onion"
    assert "has_sufficient_multiyear_data" in data
    assert "monthly_patterns" in data
    assert "season_patterns" in data


def test_api_anomalies_endpoint():
    response = client.get("/api/analytics/anomalies?commodity=Onion&market=Lasalgaon&threshold=2.5&method=rolling_zscore")
    assert response.status_code == 200
    data = response.json()
    assert data["commodity"] == "Onion"
    assert data["detection_method"] == "rolling_zscore"
    assert "anomalies" in data
    assert "method_explanation" in data


def test_api_arrivals_weather_endpoint(monkeypatch):
    monkeypatch.setattr(
        WeatherService,
        "get_daily_weather",
        lambda *args: {"status": "NO_DATA", "records": [], "message": "mocked"},
    )
    response = client.get("/api/analytics/arrivals-weather?commodity=Onion&market=Lasalgaon")
    assert response.status_code == 200
    data = response.json()
    assert data["commodity"] == "Onion"
    assert "weather_source" in data
    assert "arrivals_coverage_pct" in data


def test_api_model_explainability_endpoint():
    response = client.get("/api/forecasts/explainability?commodity=Onion&market=Lasalgaon")
    assert response.status_code == 200
    data = response.json()
    assert data["commodity"] == "Onion"
    assert "is_explainable" in data
    assert "features" in data
    assert "causality_disclaimer" in data


def test_api_forecast_uncertainty_endpoint():
    response = client.get("/api/forecasts/uncertainty?commodity=Onion&market=Lasalgaon")
    assert response.status_code == 200
    data = response.json()
    assert data["commodity"] == "Onion"
    assert "is_sample_sufficient" in data
    assert "horizons" in data
    assert "disclaimer" in data
