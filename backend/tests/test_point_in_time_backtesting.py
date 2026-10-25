from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.database import Base, migrate_prediction_evaluation_availability
from app.models.market_observation import MarketObservation
from app.models.market_observation_revision import MarketObservationRevision
from app.models.prediction_evaluation import PredictionEvaluationRecord
from app.services.forecasting_service import ForecastingService


@pytest.fixture
def isolated_db():
    isolated_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(isolated_engine)
    with Session(isolated_engine) as db:
        yield db
    isolated_engine.dispose()


def _add_observation(
    db,
    obs_date,
    price,
    available_at=None,
    *,
    status="INGESTION_TIME_ONLY",
    variety="Red",
):
    obs = MarketObservation(
        state="State",
        district="District",
        market="PointInTimeMandi",
        commodity="PointInTimeCrop",
        variety=variety,
        observation_date=obs_date,
        modal_price=float(price),
        unit="INR/Quintal",
        source="TEST",
        first_ingested_at=available_at if status == "INGESTION_TIME_ONLY" else None,
        source_available_at=available_at if status == "SOURCE_TIMESTAMP" else None,
        availability_status=status,
    )
    db.add(obs)
    db.flush()
    db.add(MarketObservationRevision(
        observation_id=obs.id,
        revision_number=1,
        modal_price=float(price),
        unit="INR/Quintal",
        source="TEST",
        ingested_at=available_at if status == "INGESTION_TIME_ONLY" else None,
        source_available_at=available_at if status == "SOURCE_TIMESTAMP" else None,
        availability_status=status,
    ))
    return obs


def _populate_daily_series(
    db,
    count=32,
    *,
    unknown_dates=(),
    late_ingestion_dates=None,
    source_availability_dates=None,
    price_overrides=None,
):
    start = date(2026, 1, 1)
    late_ingestion_dates = late_ingestion_dates or {}
    source_availability_dates = source_availability_dates or {}
    price_overrides = price_overrides or {}
    observations = []
    for day in range(count):
        obs_date = start + timedelta(days=day)
        if day in unknown_dates:
            status = "UNKNOWN"
            available_at = None
        elif day in late_ingestion_dates:
            status = "INGESTION_TIME_ONLY"
            available_at = late_ingestion_dates[day]
        elif day in source_availability_dates:
            status = "SOURCE_TIMESTAMP"
            available_at = source_availability_dates[day]
        else:
            status = "INGESTION_TIME_ONLY"
            # Available by that date's documented end-of-day UTC cutoff.
            available_at = datetime.combine(
                obs_date, datetime.min.time(), tzinfo=timezone.utc
            ) + timedelta(hours=20)
        observations.append(
            _add_observation(
                db,
                obs_date,
                price_overrides.get(day, 100 + day),
                available_at,
                status=status,
            )
        )
    db.commit()
    return start, observations


def _capture_fit_histories(monkeypatch):
    histories = []

    def fake_fit(history, steps, model_pref="auto"):
        values = np.asarray(history, dtype=float)
        histories.append(values.copy())
        return "Test persistence", [float(values[-1])] * steps, 1.0

    monkeypatch.setattr(ForecastingService, "_fit_and_predict", fake_fit)
    return histories


def _run(db):
    return ForecastingService.run_walk_forward_backtest(
        db=db,
        commodity="PointInTimeCrop",
        market="PointInTimeMandi",
        horizons=[1],
        persist=False,
    )


def test_late_arriving_historical_observation_is_excluded_from_earlier_cutoff(
    isolated_db, monkeypatch
):
    db = isolated_db
    start, _ = _populate_daily_series(
        db,
        late_ingestion_dates={
            5: datetime.combine(
                date(2026, 1, 26), datetime.min.time(), tzinfo=timezone.utc
            ) + timedelta(hours=8)
        },
    )

    histories = _capture_fit_histories(monkeypatch)
    result = _run(db)

    assert result.availability_mode == "POINT_IN_TIME"
    assert result.is_sufficient_sample is True
    # The model fit for the Jan 23 cutoff ends at price 122. Jan 6's late row
    # (105) must be absent; it arrives after that cutoff.
    earlier_history = next(values for values in histories if values[-1] == 122.0)
    assert len(earlier_history) == 22
    assert 105.0 not in earlier_history


def test_on_time_observations_are_eligible(isolated_db, monkeypatch):
    db = isolated_db
    _populate_daily_series(db)
    histories = _capture_fit_histories(monkeypatch)

    result = _run(db)

    assert result.is_sufficient_sample is True
    history = next(values for values in histories if values[-1] == 120.0)
    assert len(history) == 21
    assert list(history) == [float(100 + day) for day in range(21)]


def test_source_availability_timestamp_is_used_when_declared(isolated_db, monkeypatch):
    db = isolated_db
    start = date(2026, 1, 1)
    _populate_daily_series(
        db,
        source_availability_dates={
            5: datetime.combine(start + timedelta(days=5), datetime.min.time(), tzinfo=timezone.utc)
            + timedelta(hours=8)
        },
    )
    histories = _capture_fit_histories(monkeypatch)

    result = _run(db)

    assert result.is_sufficient_sample is True
    history = next(values for values in histories if values[-1] == 122.0)
    assert 105.0 in history


def test_late_price_revision_does_not_change_earlier_cutoff(isolated_db, monkeypatch):
    db = isolated_db
    start, rows = _populate_daily_series(db)
    revised_observation = rows[5]
    revised_observation.modal_price = 999.0
    revision_time = datetime.combine(
        start + timedelta(days=25), datetime.min.time(), tzinfo=timezone.utc
    ) + timedelta(hours=8)
    db.add(MarketObservationRevision(
        observation_id=revised_observation.id,
        revision_number=2,
        modal_price=999.0,
        unit="INR/Quintal",
        source="TEST",
        ingested_at=revision_time,
        availability_status="INGESTION_TIME_ONLY",
    ))
    db.commit()
    histories = _capture_fit_histories(monkeypatch)

    result = _run(db)

    assert result.is_sufficient_sample is True
    earlier = next(values for values in histories if values[-1] == 122.0)
    later = next(values for values in histories if values[-1] == 127.0)
    assert 105.0 in earlier
    assert 999.0 not in earlier
    assert 999.0 in later


def test_duplicate_dates_are_aggregated_after_availability_filter(isolated_db, monkeypatch):
    db = isolated_db
    start, _ = _populate_daily_series(db)
    late_time = datetime.combine(
        start + timedelta(days=25), datetime.min.time(), tzinfo=timezone.utc
    ) + timedelta(hours=8)
    _add_observation(
        db,
        start + timedelta(days=2),
        302,
        late_time,
        status="INGESTION_TIME_ONLY",
        variety="White",
    )
    db.commit()
    histories = _capture_fit_histories(monkeypatch)

    result = _run(db)

    assert result.is_sufficient_sample is True
    earlier = next(values for values in histories if values[-1] == 122.0)
    later = next(values for values in histories if values[-1] == 127.0)
    # Jan 3's on-time Red price is 102. The later White duplicate must not
    # change the earlier mean to 202.
    assert 102.0 in earlier
    assert 202.0 not in earlier
    assert 202.0 in later


def test_unknown_legacy_availability_is_excluded(isolated_db, monkeypatch):
    db = isolated_db
    _populate_daily_series(db, unknown_dates=range(32))
    histories = _capture_fit_histories(monkeypatch)

    result = _run(db)

    assert result.is_sufficient_sample is False
    assert result.availability_mode == "POINT_IN_TIME"
    assert "UNKNOWN availability records are excluded" in result.insufficient_reason
    assert histories == []


def test_insufficient_point_in_time_history_returns_clear_reason(isolated_db, monkeypatch):
    db = isolated_db
    _populate_daily_series(db, count=19)
    histories = _capture_fit_histories(monkeypatch)

    result = _run(db)

    assert result.is_sufficient_sample is False
    assert "at least 20 are required" in result.insufficient_reason
    assert histories == []


def test_target_actual_is_scoring_only_and_future_dates_never_enter_fit(
    isolated_db, monkeypatch
):
    db = isolated_db
    start, rows = _populate_daily_series(db)
    rows[23].modal_price = 9999.0
    db.commit()
    histories = _capture_fit_histories(monkeypatch)

    result = _run(db)

    target_record = next(
        record for record in result.recent_prediction_records
        if record.forecast_date == start + timedelta(days=22)
    )
    history_for_cutoff = next(values for values in histories if values[-1] == 122.0)
    assert target_record.actual_price == 9999.0
    assert 9999.0 not in history_for_cutoff
    assert max(history_for_cutoff) == 122.0


def test_retrospective_mode_remains_available_and_is_labelled(isolated_db, monkeypatch):
    db = isolated_db
    _populate_daily_series(db, unknown_dates=range(32))
    histories = _capture_fit_histories(monkeypatch)
    result = ForecastingService.run_walk_forward_backtest(
        db=db,
        commodity="PointInTimeCrop",
        market="PointInTimeMandi",
        horizons=[1],
        persist=False,
        availability_mode="retrospective",
    )

    assert result.is_sufficient_sample is True
    assert result.availability_mode == "RETROSPECTIVE"
    assert "not point-in-time verified" in result.availability_note.lower()
    assert histories


def test_backtest_metric_names_all_models_when_auto_uses_multiple_fits(isolated_db, monkeypatch):
    db = isolated_db
    _populate_daily_series(db, count=42)

    def model_changes_with_training_window(history, steps, model_pref="auto"):
        model_name = "Early Window Fit" if len(history) <= 25 else "Later Window Fit"
        return model_name, [float(history[-1])] * steps, 1.0

    monkeypatch.setattr(
        ForecastingService, "_fit_and_predict", model_changes_with_training_window
    )
    response = ForecastingService.run_walk_forward_backtest(
        db=db,
        commodity="PointInTimeCrop",
        market="PointInTimeMandi",
        horizons=[1],
        model_preference="auto",
        persist=True,
    )

    assert response.is_sufficient_sample
    assert response.horizons[0].candidate_metrics.model_name == (
        "Multiple fitted models: Early Window Fit; Later Window Fit"
    )
    assert {record.model_name for record in response.recent_prediction_records} == {
        "Early Window Fit", "Later Window Fit"
    }
    stored = isolated_db.query(PredictionEvaluationRecord).filter_by(
        commodity="PointInTimeCrop",
        market="PointInTimeMandi",
        record_type="WALK_FORWARD_BACKTEST",
    ).all()
    assert {record.model_name for record in stored} == {
        "Early Window Fit", "Later Window Fit"
    }


def test_evaluation_mode_migration_is_additive_and_safe_to_rerun():
    isolated_engine = create_engine("sqlite:///:memory:")
    try:
        with isolated_engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE prediction_evaluations ("
                "id INTEGER PRIMARY KEY, record_type VARCHAR(50), predicted_price FLOAT)"
            ))
            conn.execute(text(
                "INSERT INTO prediction_evaluations (id, record_type, predicted_price) "
                "VALUES (1, 'WALK_FORWARD_BACKTEST', 123.0)"
            ))

            migrate_prediction_evaluation_availability(conn)
            migrate_prediction_evaluation_availability(conn)

            row = conn.execute(text(
                "SELECT record_type, predicted_price, availability_mode "
                "FROM prediction_evaluations WHERE id = 1"
            )).one()
            assert row.record_type == "WALK_FORWARD_BACKTEST"
            assert row.predicted_price == 123.0
            assert row.availability_mode is None
    finally:
        isolated_engine.dispose()
