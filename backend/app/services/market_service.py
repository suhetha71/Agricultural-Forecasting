import io
import csv
from datetime import datetime, date, timezone
from typing import List, Optional, Tuple, Dict, Any
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_

from app.models.market_observation import MarketObservation
from app.services.observation_revision_service import (
    append_current_revision,
    ensure_initial_revision,
)
from app.schemas.market_data import (
    MarketObservationCreate,
    MarketSummary,
    MandiComparisonItem,
    DataSourceStats,
    ImportResult,
)


class MarketService:
    @staticmethod
    def get_observations(
        db: Session,
        commodity: Optional[str] = None,
        market: Optional[str] = None,
        state: Optional[str] = None,
        district: Optional[str] = None,
        variety: Optional[str] = None,
        source: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[MarketObservation], int]:
        """Fetch filtered market observations with total count."""
        query = db.query(MarketObservation)

        if commodity:
            query = query.filter(func.lower(MarketObservation.commodity) == commodity.lower())
        if market:
            query = query.filter(func.lower(MarketObservation.market) == market.lower())
        if state:
            query = query.filter(func.lower(MarketObservation.state) == state.lower())
        if district:
            query = query.filter(func.lower(MarketObservation.district) == district.lower())
        if variety:
            query = query.filter(func.lower(MarketObservation.variety) == variety.lower())
        if source:
            query = query.filter(MarketObservation.source == source)
        if start_date:
            query = query.filter(MarketObservation.observation_date >= start_date)
        if end_date:
            query = query.filter(MarketObservation.observation_date <= end_date)

        total = query.count()
        results = query.order_by(desc(MarketObservation.observation_date)).offset(offset).limit(limit).all()
        return results, total

    @staticmethod
    def get_filter_options(db: Session) -> Dict[str, List[str]]:
        """Return distinct commodities, states, districts, markets, and data sources."""
        commodities = [r[0] for r in db.query(MarketObservation.commodity).distinct().order_by(MarketObservation.commodity).all()]
        states = [r[0] for r in db.query(MarketObservation.state).distinct().order_by(MarketObservation.state).all()]
        districts = [r[0] for r in db.query(MarketObservation.district).distinct().order_by(MarketObservation.district).all()]
        markets = [r[0] for r in db.query(MarketObservation.market).distinct().order_by(MarketObservation.market).all()]
        sources = [r[0] for r in db.query(MarketObservation.source).distinct().order_by(MarketObservation.source).all()]
        return {
            "commodities": commodities,
            "states": states,
            "districts": districts,
            "markets": markets,
            "sources": sources,
        }

    @staticmethod
    def get_data_source_stats(db: Session) -> DataSourceStats:
        """Returns verified breakdown of records by provenance and freshness date bounds."""
        counts = dict(
            db.query(MarketObservation.source, func.count(MarketObservation.id))
            .group_by(MarketObservation.source)
            .all()
        )
        total = db.query(MarketObservation).count()
        dates = db.query(
            func.min(MarketObservation.observation_date),
            func.max(MarketObservation.observation_date),
            func.max(MarketObservation.retrieval_timestamp),
        ).first()

        return DataSourceStats(
            official_api_records=counts.get("OFFICIAL_GOV_API", 0),
            user_csv_records=counts.get("USER_CSV_IMPORT", 0),
            demo_seed_records=counts.get("DEMO_SEED_DATA", 0) + counts.get("SEED_DATA", 0),
            total_records=total,
            oldest_observation_date=dates[0] if dates else None,
            newest_observation_date=dates[1] if dates else None,
            last_retrieval_timestamp=dates[2] if dates else None,
        )

    @staticmethod
    def get_market_summary(
        db: Session,
        commodity: str,
        market: str,
    ) -> Optional[MarketSummary]:
        """Compute 30-day summary statistics for a given commodity and market."""
        records = (
            db.query(MarketObservation)
            .filter(
                func.lower(MarketObservation.commodity) == commodity.lower(),
                func.lower(MarketObservation.market) == market.lower(),
            )
            .order_by(desc(MarketObservation.observation_date))
            .limit(30)
            .all()
        )

        if not records:
            return None

        latest_record = records[0]
        prices = [r.modal_price for r in records]

        # 7-day price change
        price_change_7d = None
        if len(records) >= 7:
            p_now = records[0].modal_price
            p_past = records[6].modal_price
            if p_past > 0:
                price_change_7d = round(((p_now - p_past) / p_past) * 100.0, 2)

        return MarketSummary(
            commodity=latest_record.commodity,
            market=latest_record.market,
            state=latest_record.state,
            latest_date=latest_record.observation_date,
            latest_modal_price=latest_record.modal_price,
            min_modal_price_30d=min(prices),
            max_modal_price_30d=max(prices),
            avg_modal_price_30d=round(sum(prices) / len(prices), 2),
            price_change_7d_pct=price_change_7d,
            total_records=len(records),
            source=latest_record.source,
        )

    @staticmethod
    def compare_mandis(
        db: Session,
        commodity: str,
        reference_market: Optional[str] = None,
        state: Optional[str] = None,
        cost_per_km_qtl: float = 1.5,
    ) -> List[MandiComparisonItem]:
        """
        Compare current modal prices across various mandis for the same crop,
        calculating net realization after estimated freight transport costs.
        """
        # Find latest record per market for this commodity
        subquery = (
            db.query(
                MarketObservation.market,
                func.max(MarketObservation.observation_date).label("max_date")
            )
            .filter(func.lower(MarketObservation.commodity) == commodity.lower())
        )
        if state:
            subquery = subquery.filter(func.lower(MarketObservation.state) == state.lower())
        subquery = subquery.group_by(MarketObservation.market).subquery()

        query = (
            db.query(MarketObservation)
            .join(
                subquery,
                and_(
                    MarketObservation.market == subquery.c.market,
                    MarketObservation.observation_date == subquery.c.max_date
                )
            )
            .filter(func.lower(MarketObservation.commodity) == commodity.lower())
        )

        latest_mandis = query.all()
        if not latest_mandis:
            return []

        # Find reference market price if given
        ref_price = 0.0
        if reference_market:
            for m in latest_mandis:
                if m.market.lower() == reference_market.lower():
                    ref_price = m.modal_price
                    break

        comparison_list: List[MandiComparisonItem] = []
        for obs in latest_mandis:
            # Deterministic pseudo-distance for demonstration based on whether it's local
            is_local = reference_market and obs.market.lower() == reference_market.lower()
            distance_km = 0.0 if is_local else 35.0  # Estimated average inter-mandi transit distance
            transport_cost = round(distance_km * cost_per_km_qtl, 2)
            net_realization = round(obs.modal_price - transport_cost, 2)
            price_diff = round(obs.modal_price - ref_price, 2) if ref_price > 0 else 0.0

            comparison_list.append(
                MandiComparisonItem(
                    market=obs.market,
                    district=obs.district,
                    state=obs.state,
                    latest_date=obs.observation_date,
                    modal_price=obs.modal_price,
                    min_price=obs.min_price,
                    max_price=obs.max_price,
                    distance_km_estimate=distance_km,
                    estimated_transport_cost_qtl=transport_cost,
                    net_realization_qtl=net_realization,
                    price_difference_vs_local=price_diff,
                )
            )

        # Sort descending by net realization
        comparison_list.sort(key=lambda x: x.net_realization_qtl, reverse=True)
        return comparison_list

    @staticmethod
    def import_csv_records(
        db: Session,
        csv_content: str,
        source_label: str = "USER_CSV_IMPORT"
    ) -> ImportResult:
        """
        Parses CSV data matching Agmarknet export schema, validates fields,
        detects duplicates, safely upserts updated prices, and tags origin.
        """
        imported_count = 0
        duplicate_count = 0
        skipped_count = 0
        errors: List[str] = []
        now_utc = datetime.now(timezone.utc)

        try:
            reader = csv.DictReader(io.StringIO(csv_content))
            if not reader.fieldnames:
                return ImportResult(
                    success=False,
                    message="CSV file is empty or has no header row."
                )

            headers = {h.strip().lower(): h for h in reader.fieldnames}

            # Map typical variations of Agmarknet CSV columns
            state_col = headers.get("state")
            district_col = headers.get("district")
            market_col = headers.get("market") or headers.get("mandi")
            commodity_col = headers.get("commodity") or headers.get("crop")
            variety_col = headers.get("variety")
            date_col = headers.get("arrival_date") or headers.get("date") or headers.get("reported_date")
            min_col = headers.get("min_price") or headers.get("min")
            max_col = headers.get("max_price") or headers.get("max")
            modal_col = headers.get("modal_price") or headers.get("modal") or headers.get("price")
            arrivals_col = headers.get("arrivals_in_qtl") or headers.get("arrivals")
            unit_col = headers.get("unit") or headers.get("original_unit") or headers.get("price_unit")
            source_available_col = headers.get("source_available_at")

            missing_headers = []
            if not state_col: missing_headers.append("State")
            if not district_col: missing_headers.append("District")
            if not market_col: missing_headers.append("Market/Mandi")
            if not commodity_col: missing_headers.append("Commodity/Crop")
            if not date_col: missing_headers.append("Arrival_Date/Date")
            if not modal_col: missing_headers.append("Modal_Price/Price")

            if missing_headers:
                return ImportResult(
                    success=False,
                    message=f"CSV is missing required headers: {', '.join(missing_headers)}",
                    errors=[f"Detected headers in file: {list(reader.fieldnames)}"]
                )

            for line_idx, row in enumerate(reader, start=2):
                try:
                    state_val = str(row[state_col]).strip()
                    dist_val = str(row[district_col]).strip()
                    mkt_val = str(row[market_col]).strip()
                    comm_val = str(row[commodity_col]).strip()
                    var_val = str(row[variety_col]).strip() if variety_col and row.get(variety_col) else "Other"
                    raw_date = str(row[date_col]).strip()
                    raw_modal = str(row[modal_col]).strip()
                    unit_val = str(row[unit_col]).strip() if unit_col and row.get(unit_col) else "Rs/Quintal"
                    source_available_at = None
                    if source_available_col and str(row.get(source_available_col) or "").strip():
                        raw_available_at = str(row[source_available_col]).strip()
                        try:
                            source_available_at = datetime.fromisoformat(
                                raw_available_at.replace("Z", "+00:00")
                            )
                            if source_available_at.tzinfo is None:
                                raise ValueError("source_available_at must include a timezone")
                            source_available_at = source_available_at.astimezone(timezone.utc)
                            if source_available_at > now_utc:
                                raise ValueError("source_available_at cannot be in the future")
                        except ValueError as timestamp_error:
                            skipped_count += 1
                            errors.append(
                                f"Row {line_idx}: Invalid source_available_at ({timestamp_error})"
                            )
                            continue

                    if not (state_val and dist_val and mkt_val and comm_val and raw_date and raw_modal):
                        skipped_count += 1
                        errors.append(f"Row {line_idx}: Blank required field")
                        continue

                    # Parse date supporting ISO YYYY-MM-DD or Indian DD/MM/YYYY
                    parsed_date = None
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                        try:
                            parsed_date = datetime.strptime(raw_date, fmt).date()
                            break
                        except ValueError:
                            pass

                    if not parsed_date:
                        errors.append(f"Row {line_idx}: Unrecognized date format '{raw_date}'")
                        skipped_count += 1
                        continue

                    try:
                        modal_val = float(raw_modal.replace(",", ""))
                    except ValueError:
                        errors.append(f"Row {line_idx}: Non-numeric modal price '{raw_modal}'")
                        skipped_count += 1
                        continue

                    if modal_val <= 0:
                        errors.append(f"Row {line_idx}: Non-positive modal price ({modal_val})")
                        skipped_count += 1
                        continue

                    min_val = None
                    if min_col and row.get(min_col) and row[min_col].strip():
                        try:
                            min_val = float(row[min_col].replace(",", ""))
                            if min_val < 0: min_val = None
                        except ValueError:
                            pass

                    max_val = None
                    if max_col and row.get(max_col) and row[max_col].strip():
                        try:
                            max_val = float(row[max_col].replace(",", ""))
                            if max_val < 0: max_val = None
                        except ValueError:
                            pass

                    arrivals_val = None
                    if arrivals_col and row.get(arrivals_col) and row[arrivals_col].strip():
                        try:
                            arrivals_val = float(row[arrivals_col].replace(",", ""))
                            if arrivals_val < 0: arrivals_val = None
                        except ValueError:
                            pass

                    # Check for duplicate observation
                    existing = (
                        db.query(MarketObservation)
                        .filter(
                            MarketObservation.state == state_val,
                            MarketObservation.district == dist_val,
                            MarketObservation.market == mkt_val,
                            MarketObservation.commodity == comm_val,
                            MarketObservation.variety == var_val,
                            MarketObservation.observation_date == parsed_date,
                        )
                        .first()
                    )

                    if existing:
                        # If price or volume differs, perform safe upsert
                        if (
                            existing.modal_price != modal_val or
                            existing.min_price != min_val or
                            existing.max_price != max_val or
                            existing.arrivals_in_qtl != arrivals_val
                        ):
                            ensure_initial_revision(db, existing)
                            existing.modal_price = modal_val
                            existing.min_price = min_val
                            existing.max_price = max_val
                            existing.arrivals_in_qtl = arrivals_val
                            existing.source = source_label
                            existing.retrieval_timestamp = now_utc
                            existing.original_unit = unit_val
                            existing.source_available_at = source_available_at
                            existing.availability_status = (
                                "SOURCE_TIMESTAMP"
                                if source_available_at
                                else "INGESTION_TIME_ONLY"
                            )
                            append_current_revision(db, existing)
                            imported_count += 1
                        else:
                            duplicate_count += 1
                        continue

                    new_obs = MarketObservation(
                        state=state_val,
                        district=dist_val,
                        market=mkt_val,
                        commodity=comm_val,
                        variety=var_val,
                        observation_date=parsed_date,
                        min_price=min_val,
                        max_price=max_val,
                        modal_price=modal_val,
                        arrivals_in_qtl=arrivals_val,
                        unit="INR/Quintal",
                        original_unit=unit_val,
                        source=source_label,
                        retrieval_timestamp=now_utc,
                        first_ingested_at=now_utc,
                        source_available_at=source_available_at,
                        availability_status=(
                            "SOURCE_TIMESTAMP"
                            if source_available_at
                            else "INGESTION_TIME_ONLY"
                        ),
                    )
                    db.add(new_obs)
                    db.flush()
                    ensure_initial_revision(db, new_obs)
                    imported_count += 1

                except Exception as row_err:
                    skipped_count += 1
                    errors.append(f"Row {line_idx} error: {str(row_err)}")

            db.commit()
            return ImportResult(
                success=True,
                imported_count=imported_count,
                duplicate_count=duplicate_count,
                skipped_count=skipped_count,
                errors=errors[:10],
                message=f"Processed CSV: {imported_count} records imported/updated, {duplicate_count} duplicates skipped, {skipped_count} invalid rows rejected."
            )

        except Exception as e:
            db.rollback()
            return ImportResult(
                success=False,
                errors=[str(e)],
                message=f"Failed to process CSV: {str(e)}"
            )
