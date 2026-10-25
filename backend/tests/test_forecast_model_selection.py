import math
import re
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models.forecast_record import ForecastRecord
from app.models.market_observation import MarketObservation
from app.models.market_observation_revision import MarketObservationRevision
from app.models.prediction_evaluation import PredictionEvaluationRecord
from app.services.forecasting_service import ForecastingService


@pytest.fixture
def isolated_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def _seasonal_history(size=35):
    index = np.arange(size, dtype=float)
    return 1200.0 + 4.0 * index + 35.0 * np.sin(2.0 * np.pi * index / 7.0)


@pytest.mark.parametrize("preference", ["auto", "holt-winters"])
def test_each_advertised_model_preference_executes_a_real_fit(preference):
    name, predictions, residual_std = ForecastingService._fit_and_predict(
        _seasonal_history(), steps=7, model_pref=preference
    )
    assert name == "Holt-Winters Triple Exponential Smoothing (Additive)"
    assert len(predictions) == 7
    assert all(math.isfinite(value) for value in predictions)
    assert math.isfinite(residual_std)


def test_holt_winters_insufficient_history_discloses_holt_linear_fallback():
    name, predictions, residual_std = ForecastingService._fit_and_predict(
        _seasonal_history(15), steps=3, model_pref="holt-winters"
    )
    assert name.startswith("Holt's Linear Trend Exponential Smoothing")
    assert "fallback: insufficient Holt-Winters history" in name
    assert len(predictions) == 3
    assert all(math.isfinite(value) for value in predictions)
    assert math.isfinite(residual_std)


def test_holt_winters_very_short_history_discloses_damped_fallback():
    name, predictions, residual_std = ForecastingService._fit_and_predict(
        _seasonal_history(8), steps=3, model_pref="holt-winters"
    )
    assert name.startswith("Baseline Rolling Trend with Damped Momentum")
    assert "fallback: insufficient Holt-Winters history" in name
    assert all(math.isfinite(value) for value in predictions)
    assert math.isfinite(residual_std)


def test_auto_uses_low_data_fallback_and_ignores_nonfinite_history():
    name, predictions, residual_std = ForecastingService._fit_and_predict(
        np.array([100.0, np.nan, 108.0, np.inf, 112.0, 115.0, 119.0, 122.0]),
        steps=4,
        model_pref="auto",
    )
    assert name.startswith("Baseline Rolling Trend with Damped Momentum")
    assert "low-data fallback" in name
    assert len(predictions) == 4
    assert all(math.isfinite(value) for value in predictions)
    assert math.isfinite(residual_std)


def test_empty_history_is_rejected_and_unimplemented_preferences_are_not_accepted():
    with pytest.raises(ValueError, match="finite historical price"):
        ForecastingService._fit_and_predict(np.array([np.nan, np.inf]), steps=2)
    for unsupported in ("sarimax", "ridge-lag"):
        with pytest.raises(ValueError, match="model_preference"):
            ForecastingService._fit_and_predict(_seasonal_history(), steps=2, model_pref=unsupported)


def test_holt_winters_fit_failure_uses_and_names_holt_linear(monkeypatch):
    from statsmodels.tsa import holtwinters

    actual_implementation = holtwinters.ExponentialSmoothing

    def fail_only_seasonal(*args, **kwargs):
        if kwargs.get("seasonal") == "add":
            raise RuntimeError("simulated seasonal fitting failure")
        return actual_implementation(*args, **kwargs)

    monkeypatch.setattr(holtwinters, "ExponentialSmoothing", fail_only_seasonal)
    name, predictions, residual_std = ForecastingService._fit_and_predict(
        _seasonal_history(), steps=5, model_pref="holt-winters"
    )
    assert name.startswith("Holt's Linear Trend Exponential Smoothing")
    assert "fallback: Holt-Winters fit failed" in name
    assert all(math.isfinite(value) for value in predictions)
    assert math.isfinite(residual_std)


def test_fitting_errors_fall_back_to_finite_damped_trend(monkeypatch):
    from statsmodels.tsa import holtwinters

    def fail_fit(*args, **kwargs):
        raise RuntimeError("simulated model fitting failure")

    monkeypatch.setattr(holtwinters, "ExponentialSmoothing", fail_fit)
    name, predictions, residual_std = ForecastingService._fit_and_predict(
        _seasonal_history(), steps=6, model_pref="auto"
    )
    assert name.startswith("Baseline Rolling Trend with Damped Momentum")
    assert "fallback: statistical model fit failed" in name
    assert len(predictions) == 6
    assert all(math.isfinite(value) for value in predictions)
    assert math.isfinite(residual_std)


def test_frontend_model_selectors_match_supported_model_preferences():
    project = Path(__file__).resolve().parents[2]
    pages = (
        project / "frontend/src/pages/ForecastingPage.tsx",
        project / "frontend/src/pages/ModelValidationPage.tsx",
    )
    for page in pages:
        source = page.read_text(encoding="utf-8")
        selected = source.index("value={selectedModel}")
        start = source.rfind("<select", 0, selected)
        end = source.index("</select>", selected)
        options = set(re.findall(r'<option value="([^"]+)"', source[start:end]))
        assert options == {"auto", "holt-winters"}, page.name


def test_forecast_response_and_saved_records_report_actual_fitted_model(isolated_db):
    start = date(2026, 1, 1)
    for day, price in enumerate(_seasonal_history()):
        isolated_db.add(MarketObservation(
            state="State",
            district="District",
            market="ModelNameMandi",
            commodity="ModelNameCrop",
            variety="Other",
            observation_date=start + timedelta(days=day),
            modal_price=float(price),
            unit="INR/Quintal",
            source="TEST",
        ))
    isolated_db.commit()

    response = ForecastingService.generate_forecast(
        isolated_db,
        commodity="ModelNameCrop",
        market="ModelNameMandi",
        horizon_days=7,
        model_preference="holt-winters",
    )
    assert response.is_sufficient_data
    assert response.model_used == "Holt-Winters Triple Exponential Smoothing (Additive)"
    assert response.metrics is not None
    assert response.metrics.model_name == response.model_used
    assert len(response.forecasts) == 7
    assert all(math.isfinite(point.predicted_price) for point in response.forecasts)
    assert all(
        math.isfinite(bound)
        for point in response.forecasts
        for bound in (point.lower_ci_80, point.upper_ci_80, point.lower_ci_95, point.upper_ci_95)
        if bound is not None
    )
    saved = isolated_db.query(ForecastRecord).filter_by(
        commodity="ModelNameCrop", market="ModelNameMandi"
    ).all()
    assert len(saved) == 7
    assert {record.model_name for record in saved} == {response.model_used}
    assert all(record.metrics_mae is not None for record in saved)




def test_regular_forecast_reports_insufficient_finite_history(isolated_db):
    start = date(2026, 1, 1)
    isolated_db.add_all([
        MarketObservation(
            state="State",
            district="District",
            market="ShortHistoryMandi",
            commodity="ShortHistoryCrop",
            variety="Other",
            observation_date=start + timedelta(days=day),
            modal_price=100.0 + day,
            unit="INR/Quintal",
            source="TEST",
        )
        for day in range(6)
    ])
    isolated_db.commit()

    response = ForecastingService.generate_forecast(
        isolated_db,
        commodity="ShortHistoryCrop",
        market="ShortHistoryMandi",
        model_preference="auto",
    )
    assert response.is_sufficient_data is False
    assert response.model_used == "None"
    assert response.forecasts == []


def test_regular_forecast_requires_seven_unique_dates_after_duplicate_removal(isolated_db):
    start = date(2026, 1, 1)
    isolated_db.add_all([
        MarketObservation(
            state="State",
            district="District",
            market="DuplicateDateMandi",
            commodity="DuplicateDateCrop",
            variety=f"Variety{variety}",
            observation_date=start + timedelta(days=day),
            modal_price=100.0 + day + variety,
            unit="INR/Quintal",
            source="TEST",
        )
        for day in range(3)
        for variety in range(3)
    ])
    isolated_db.commit()

    response = ForecastingService.generate_forecast(
        isolated_db,
        commodity="DuplicateDateCrop",
        market="DuplicateDateMandi",
        model_preference="auto",
    )

    assert response.is_sufficient_data is False
    assert response.model_used == "None"
    assert response.forecasts == []
    assert "3 unique observation dates" in response.message
