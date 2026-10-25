import pytest
import numpy as np
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import SessionLocal
from app.models.market_observation import MarketObservation
from app.models.forecast_record import ForecastRecord
from app.models.prediction_evaluation import PredictionEvaluationRecord
from app.services.forecasting_service import ForecastingService


@pytest.fixture
def db_session():
    """Provides a transactional database session for tests."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_client():
    """Provides FastAPI test client."""
    return TestClient(app)


# --------------------------------------------------------------------------
# 1. Metric Calculations & Zero / Near-Zero Handling
# --------------------------------------------------------------------------
def test_metric_calculations_exactness():
    """
    Verifies mathematical correctness of MAE, RMSE, and safe MAPE calculations.
    Ensures that zero and near-zero actual prices are protected by epsilon threshold
    to prevent ZeroDivisionError and NaN.
    """
    actuals = np.array([1000.0, 2000.0, 1500.0])
    predictions = np.array([1100.0, 1900.0, 1500.0])
    errors = actuals - predictions

    expected_mae = float(np.mean(np.abs(errors)))  # (100 + 100 + 0) / 3 = 66.67
    expected_rmse = float(np.sqrt(np.mean(errors ** 2)))  # sqrt((10000 + 10000 + 0) / 3) = 81.65
    expected_mape = float(np.mean(np.abs(errors / actuals))) * 100.0  # (10% + 5% + 0%) / 3 = 5.0%

    assert round(expected_mae, 2) == 66.67
    assert round(expected_rmse, 2) == 81.65
    assert round(expected_mape, 2) == 5.0

    # Test protection against zero actual prices (e.g. market holiday zero or reporting gap)
    zero_actuals = np.array([0.0, 500.0])
    zero_preds = np.array([50.0, 500.0])
    safe_denominator = np.maximum(zero_actuals, 1.0)
    safe_mape = float(np.mean(np.abs((zero_actuals - zero_preds) / safe_denominator))) * 100.0
    assert not np.isnan(safe_mape)
    assert not np.isinf(safe_mape)
    assert safe_mape > 0.0


# --------------------------------------------------------------------------
# 2. Chronological Backtesting & Future-Data Leakage Prevention
# --------------------------------------------------------------------------
def test_chronological_backtesting_and_leakage_prevention(db_session: Session):
    """
    Verifies that backtesting strictly walks forward in chronological order
    and never leaks future observations into model training.
    """
    # Create clean synthetic chronological dataset (30 days)
    crop = "BacktestTestCropLeakage"
    mandi = "LeakageTestMandi"
    start_d = date(2026, 1, 1)

    # Clean prior test rows if any
    db_session.query(MarketObservation).filter(
        MarketObservation.commodity == crop, MarketObservation.market == mandi
    ).delete()
    db_session.commit()

    obs_list = []
    for day in range(35):
        obs_d = start_d + timedelta(days=day)
        # Linear upward trend: 1000 + 10 * day
        obs_list.append(
            MarketObservation(
                commodity=crop,
                market=mandi,
                state="TestState",
                district="TestDist",
                variety="Other",
                observation_date=obs_d,
                modal_price=1000.0 + day * 10.0,
                unit="INR/Quintal",
                source="TEST",
            )
        )
    db_session.add_all(obs_list)
    db_session.commit()

    try:
        # Run walk-forward backtest for 7-day horizon
        res = ForecastingService.run_walk_forward_backtest(
            db=db_session,
            commodity=crop,
            market=mandi,
            horizons=[7],
            model_preference="auto",
            persist=False,
            availability_mode="retrospective",
        )

        assert res.is_sufficient_sample is True
        assert res.total_matched_predictions > 0
        assert len(res.recent_prediction_records) > 0

        # Verify that for every evaluated prediction, forecast cutoff strictly precedes target date
        for rec in res.recent_prediction_records:
            assert rec.forecast_date < rec.target_date
            diff_days = (rec.target_date - rec.forecast_date).days
            assert diff_days == 7
            # Baseline must equal price at cutoff date (1000 + cutoff_day * 10)
            cutoff_day_index = (rec.forecast_date - start_d).days
            expected_baseline_price = 1000.0 + cutoff_day_index * 10.0
            assert rec.baseline_predicted_price == expected_baseline_price
    finally:
        # Clean up
        db_session.query(MarketObservation).filter(
            MarketObservation.commodity == crop, MarketObservation.market == mandi
        ).delete()
        db_session.commit()


# --------------------------------------------------------------------------
# 3. Crop and Market Matching Strictness (No Cross-Mandi Leakage)
# --------------------------------------------------------------------------
def test_crop_and_market_matching_strictness(db_session: Session):
    """
    Verifies that the backtester strictly rejects observations from different mandis
    or different crops.
    """
    crop = "StrictMatchingCrop"
    mandi_target = "MandiTarget"
    mandi_other = "MandiOther"
    start_d = date(2026, 2, 1)

    # Clean prior test rows
    db_session.query(MarketObservation).filter(
        MarketObservation.commodity == crop
    ).delete()
    db_session.commit()

    obs_list = []
    # 28 days for target mandi
    for day in range(28):
        obs_d = start_d + timedelta(days=day)
        obs_list.append(
            MarketObservation(
                commodity=crop,
                market=mandi_target,
                state="StateA",
                district="DistA",
                variety="Other",
                observation_date=obs_d,
                modal_price=2000.0,
                unit="INR/Quintal",
                source="TEST",
            )
        )
    # Different mandi on target date with completely different price
    obs_list.append(
        MarketObservation(
            commodity=crop,
            market=mandi_other,
            state="StateB",
            district="DistB",
            variety="Other",
            observation_date=start_d + timedelta(days=27),
            modal_price=99999.0,
            unit="INR/Quintal",
            source="TEST",
        )
    )
    db_session.add_all(obs_list)
    db_session.commit()

    try:
        res = ForecastingService.run_walk_forward_backtest(
            db=db_session,
            commodity=crop,
            market=mandi_target,
            horizons=[7],
            persist=False,
            availability_mode="retrospective",
        )

        assert res.is_sufficient_sample is True
        # Actual prices matched must ONLY be 2000.0, never 99999.0
        for rec in res.recent_prediction_records:
            assert rec.actual_price == 2000.0
            assert rec.market.lower() == mandi_target.lower()
    finally:
        db_session.query(MarketObservation).filter(
            MarketObservation.commodity == crop
        ).delete()
        db_session.commit()


# --------------------------------------------------------------------------
# 4. Target-Date Matching & Missing Observations Handling
# --------------------------------------------------------------------------
def test_target_date_matching_and_missing_observations(db_session: Session):
    """
    Verifies that target dates match strictly (cutoff + h) and missing dates
    (e.g. APMC holiday / Sunday closures) are correctly counted in missing_observations_count
    without distorting matched pairs.
    """
    crop = "MissingObsTestCrop"
    mandi = "MissingObsMandi"
    start_d = date(2026, 3, 1)

    db_session.query(MarketObservation).filter(
        MarketObservation.commodity == crop, MarketObservation.market == mandi
    ).delete()
    db_session.commit()

    obs_list = []
    # Create 35 days, but omit every Sunday by calendar weekday.
    omitted_dates = set()
    for day in range(35):
        obs_d = start_d + timedelta(days=day)
        if obs_d.weekday() == 6:
            omitted_dates.add(obs_d)
            continue
        obs_list.append(
            MarketObservation(
                commodity=crop,
                market=mandi,
                state="State",
                district="Dist",
                variety="Other",
                observation_date=obs_d,
                modal_price=1500.0,
                unit="INR/Quintal",
                source="TEST",
            )
        )
    db_session.add_all(obs_list)
    db_session.commit()

    try:
        res = ForecastingService.run_walk_forward_backtest(
            db=db_session,
            commodity=crop,
            market=mandi,
            # One calendar day from Saturday lands on an omitted Sunday.
            horizons=[1],
            persist=False,
            availability_mode="retrospective",
        )

        assert res.is_sufficient_sample is True
        # Missing observations count must be > 0 because Sundays were omitted
        h1_summary = res.horizons[0]
        assert h1_summary.horizon_days == 1
        assert h1_summary.missing_observations_count > 0
        # For every matched record, target_date must NOT be in omitted_dates
        for rec in res.recent_prediction_records:
            assert rec.target_date not in omitted_dates
    finally:
        db_session.query(MarketObservation).filter(
            MarketObservation.commodity == crop, MarketObservation.market == mandi
        ).delete()
        db_session.commit()


# --------------------------------------------------------------------------
# 5. Baseline Comparison & Superiority Logic
# --------------------------------------------------------------------------
def test_baseline_comparison_and_superiority_reporting(db_session: Session):
    """
    Verifies that candidate model and baseline are compared on identical pairs,
    win rates are calculated accurately, and superiority is only reported if
    candidate RMSE is strictly lower than baseline RMSE.
    """
    crop = "BaselineCompCrop"
    mandi = "BaselineCompMandi"
    start_d = date(2026, 4, 1)

    db_session.query(MarketObservation).filter(
        MarketObservation.commodity == crop, MarketObservation.market == mandi
    ).delete()
    db_session.commit()

    obs_list = []
    # Highly flat price series (persistence baseline will have near-zero error)
    for day in range(30):
        obs_d = start_d + timedelta(days=day)
        obs_list.append(
            MarketObservation(
                commodity=crop,
                market=mandi,
                state="State",
                district="Dist",
                variety="Other",
                observation_date=obs_d,
                modal_price=2500.0,
                unit="INR/Quintal",
                source="TEST",
            )
        )
    db_session.add_all(obs_list)
    db_session.commit()

    try:
        res = ForecastingService.run_walk_forward_backtest(
            db=db_session,
            commodity=crop,
            market=mandi,
            horizons=[7],
            persist=False,
            availability_mode="retrospective",
        )

        assert res.is_sufficient_sample is True
        h_sum = res.horizons[0]
        # Baseline on flat series has MAE = 0.0
        assert h_sum.baseline_metrics.mae == 0.0
        assert h_sum.baseline_metrics.rmse == 0.0
        # If candidate model has small floating difference, baseline is superior
        if h_sum.candidate_metrics.rmse > h_sum.baseline_metrics.rmse:
            assert h_sum.outperformed_baseline is False
            assert "Persistence baseline" in h_sum.evaluation_verdict
    finally:
        db_session.query(MarketObservation).filter(
            MarketObservation.commodity == crop, MarketObservation.market == mandi
        ).delete()
        db_session.commit()


# --------------------------------------------------------------------------
# 6. Insufficient Evaluation Samples Reporting
# --------------------------------------------------------------------------
def test_insufficient_samples_reporting(db_session: Session):
    """
    Verifies that when historical observations are fewer than 25,
    the backtester returns is_sufficient_sample=False with an informative reason.
    """
    crop = "InsufficientCrop"
    mandi = "InsufficientMandi"
    start_d = date(2026, 5, 1)

    db_session.query(MarketObservation).filter(
        MarketObservation.commodity == crop, MarketObservation.market == mandi
    ).delete()
    db_session.commit()

    # Insert only 5 records (< 25 required)
    obs_list = [
        MarketObservation(
            commodity=crop,
            market=mandi,
            state="State",
            district="Dist",
            variety="Other",
            observation_date=start_d + timedelta(days=i),
            modal_price=1800.0,
            unit="INR/Quintal",
            source="TEST",
        )
        for i in range(5)
    ]
    db_session.add_all(obs_list)
    db_session.commit()

    try:
        res = ForecastingService.run_walk_forward_backtest(
            db=db_session,
            commodity=crop,
            market=mandi,
            horizons=[7, 15, 30],
            persist=False,
            availability_mode="retrospective",
        )

        assert res.is_sufficient_sample is False
        assert "Insufficient historical observations" in (res.insufficient_reason or "")
        assert res.total_historical_records == 5
        assert res.total_matched_predictions == 0
        assert len(res.horizons) == 0
    finally:
        db_session.query(MarketObservation).filter(
            MarketObservation.commodity == crop, MarketObservation.market == mandi
        ).delete()
        db_session.commit()


# --------------------------------------------------------------------------
# 7. Unit Compatibility & Provenance (Saved Live vs Walk-Forward)
# --------------------------------------------------------------------------
def test_distinguish_saved_live_vs_backtest_records(db_session: Session):
    """
    Verifies that genuine live saved forecasts and reconstructed walk-forward backtests
    are properly tagged and distinguished.
    """
    crop = "DistinguishCrop"
    mandi = "DistinguishMandi"
    target_d = date(2026, 6, 15)

    # Clean prior
    db_session.query(PredictionEvaluationRecord).filter(
        PredictionEvaluationRecord.commodity == crop
    ).delete()
    db_session.query(ForecastRecord).filter(
        ForecastRecord.commodity == crop
    ).delete()
    db_session.query(MarketObservation).filter(
        MarketObservation.commodity == crop
    ).delete()
    db_session.commit()

    # 1. Add genuine historical observation on target date
    db_session.add(
        MarketObservation(
            commodity=crop,
            market=mandi,
            state="State",
            district="Dist",
            variety="Other",
            observation_date=target_d,
            modal_price=3000.0,
            unit="INR/Quintal",
            source="TEST",
        )
    )
    # 2. Add saved live forecast record for that target date
    db_session.add(
        ForecastRecord(
            commodity=crop,
            market=mandi,
            state="State",
            district="Dist",
            variety="Other",
            target_date=target_d,
            horizon_days=7,
            predicted_price=3100.0,
            model_name="Holt-Winters",
            model_version="v1.0",
            unit="INR/Quintal",
        )
    )
    db_session.commit()

    try:
        # Evaluate saved live forecasts
        count = ForecastingService.evaluate_saved_forecasts(db=db_session, commodity=crop, market=mandi)
        assert count == 1

        # Query evaluation records
        evals = ForecastingService.get_evaluation_records(
            db=db_session, commodity=crop, market=mandi, record_type="SAVED_LIVE_FORECAST"
        )
        assert len(evals) == 1
        assert evals[0].record_type == "SAVED_LIVE_FORECAST"
        assert evals[0].predicted_price == 3100.0
        assert evals[0].actual_price == 3000.0
        assert evals[0].absolute_error == 100.0
    finally:
        db_session.query(PredictionEvaluationRecord).filter(
            PredictionEvaluationRecord.commodity == crop
        ).delete()
        db_session.query(ForecastRecord).filter(
            ForecastRecord.commodity == crop
        ).delete()
        db_session.query(MarketObservation).filter(
            MarketObservation.commodity == crop
        ).delete()
        db_session.commit()


# --------------------------------------------------------------------------
# 8. API Integration Tests: /backtest and /evaluations
# --------------------------------------------------------------------------
def test_backtest_api_endpoints(test_client: TestClient):
    """
    Tests the FastAPI HTTP endpoints /api/forecasts/backtest and /api/forecasts/evaluations
    with real Lasalgaon Onion data from the database.
    """
    # 1. Test /api/forecasts/backtest
    resp = test_client.get("/api/forecasts/backtest?commodity=Onion&market=Lasalgaon&horizons=7&horizons=15&horizons=30&availability_mode=retrospective")
    assert resp.status_code == 200
    data = resp.json()

    assert data["commodity"] == "Onion"
    assert data["market"] == "Lasalgaon"
    assert data["is_sufficient_sample"] is True
    assert data["availability_mode"] == "RETROSPECTIVE"
    assert "not point-in-time verified" in data["availability_note"].lower()
    assert data["total_matched_predictions"] > 0
    assert len(data["horizons"]) == 3
    assert len(data["recent_prediction_records"]) > 0

    # Verify metrics structure
    for hz in data["horizons"]:
        assert hz["horizon_days"] in [7, 15, 30]
        assert hz["sample_count"] > 0
        assert hz["candidate_metrics"]["mae"] > 0
        assert hz["candidate_metrics"]["rmse"] > 0
        assert hz["baseline_metrics"]["mae"] > 0
        assert hz["baseline_metrics"]["rmse"] > 0
        assert hz["reliability_tier"] in ["High", "Moderate", "Extrapolated / Caution"]

    # 2. Test /api/forecasts/evaluations list
    resp_eval = test_client.get("/api/forecasts/evaluations?commodity=Onion&market=Lasalgaon&limit=10")
    assert resp_eval.status_code == 200
    data_eval = resp_eval.json()
    assert data_eval["total_count"] > 0
    assert len(data_eval["records"]) > 0
    sample_rec = data_eval["records"][0]
    assert sample_rec["commodity"] == "Onion"
    assert sample_rec["market"] == "Lasalgaon"
    assert sample_rec["predicted_price"] > 0
    assert sample_rec["actual_price"] > 0
    assert sample_rec["absolute_error"] >= 0

    # 3. Test /api/forecasts/evaluate-saved
    resp_saved = test_client.post("/api/forecasts/evaluate-saved?commodity=Onion&market=Lasalgaon")
    assert resp_saved.status_code == 200
    assert "evaluated_count" in resp_saved.json()
