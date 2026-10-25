from typing import Optional, List, Literal
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.forecasting_service import ForecastingService
from app.schemas.forecast import (
    ForecastModelPreference,
    ForecastResponse,
    BacktestEvaluationResponse,
    EvaluationRecordsListResponse,
    PredictionActualRecord,
)
from app.schemas.analytics import ModelExplanationResponse, ForecastUncertaintyResponse

router = APIRouter(prefix="/forecasts", tags=["Forecasting"])


@router.get("", response_model=ForecastResponse)
def get_forecast(
    commodity: str = Query(..., description="Crop name (e.g. Onion, Wheat)"),
    market: str = Query(..., description="Mandi name (e.g. Lasalgaon, Khanna)"),
    horizon_days: int = Query(30, ge=1, le=60, description="Forecast horizon in days"),
    model: ForecastModelPreference = Query(
        "auto", description="auto uses Holt-Winters at 21+ observations, Holt linear at 10-20, and a damped trend below 10 or after fitting errors; holt-winters requests seasonal Holt-Winters with a named fallback"
    ),
    db: Session = Depends(get_db),
):
    """
    Generate real empirical time-series forecasts and return genuine walk-forward holdout metrics.
    Zero mock/hardcoded values.
    """
    return ForecastingService.generate_forecast(
        db=db,
        commodity=commodity,
        market=market,
        horizon_days=horizon_days,
        model_preference=model,
    )


@router.get("/explainability", response_model=ModelExplanationResponse)
def get_model_explainability(
    commodity: str = Query(..., description="Crop name"),
    market: str = Query(..., description="Mandi name"),
    db: Session = Depends(get_db),
):
    """
    Returns genuine feature importances, feature descriptions, and SHAP attributions
    for an autoregressive lag regression model trained on actual historical mandi prices.
    Explains if training data is insufficient (< 20 records).
    """
    return ForecastingService.explain_model(db, commodity=commodity, market=market)


@router.get("/uncertainty", response_model=ForecastUncertaintyResponse)
def get_forecast_uncertainty(
    commodity: str = Query(..., description="Crop name"),
    market: str = Query(..., description="Mandi name"),
    db: Session = Depends(get_db),
):
    """
    Returns empirical multi-horizon holdout risk evaluation across 7-day, 14-day,
    and 30-day forecast windows with reliability tiers and extrapolation warnings.
    """
    return ForecastingService.get_forecast_uncertainty(db, commodity=commodity, market=market)


@router.get("/backtest", response_model=BacktestEvaluationResponse)
def run_historical_backtest(
    commodity: str = Query(..., description="Crop name (e.g. Onion, Wheat)"),
    market: str = Query(..., description="Mandi name (e.g. Lasalgaon, Khanna)"),
    horizons: Optional[List[int]] = Query(None, description="Horizons to evaluate, e.g. 7, 15, 30"),
    model_preference: ForecastModelPreference = Query(
        "auto", description="auto uses Holt-Winters at 21+ observations, Holt linear at 10-20, and a damped trend below 10 or after fitting errors; holt-winters requests seasonal Holt-Winters with a named fallback"
    ),
    persist: bool = Query(True, description="Whether to persist evaluated prediction pairs"),
    availability_mode: Literal["point_in_time", "retrospective"] = Query(
        "point_in_time",
        description=(
            "point_in_time excludes unknown and not-yet-available values; retrospective "
            "uses final stored history and is not point-in-time verified"
        ),
    ),
    db: Session = Depends(get_db),
):
    """
    Performs rigorous chronological walk-forward historical backtesting on available mandi observations.
    - Point-in-time mode filters by version availability; retrospective mode is labelled unverified.
    - Compares candidate models with a naive persistence baseline (P_{t+h} = P_t) on identical sample pairs.
    - Evaluates 7-day, 15-day, and 30-day horizons.
    - Computes genuine MAE, RMSE, safe MAPE, Directional Hit Rate, and Win Rate.
    """
    selected_horizons = horizons if horizons else [7, 15, 30]
    return ForecastingService.run_walk_forward_backtest(
        db=db,
        commodity=commodity,
        market=market,
        horizons=selected_horizons,
        model_preference=model_preference,
        persist=persist,
        availability_mode=availability_mode,
    )


@router.get("/evaluations", response_model=EvaluationRecordsListResponse)
def get_prediction_evaluations(
    commodity: Optional[str] = Query(None, description="Optional commodity filter"),
    market: Optional[str] = Query(None, description="Optional market filter"),
    horizon_days: Optional[int] = Query(None, description="Filter by horizon (7, 15, 30)"),
    record_type: Optional[str] = Query("ALL", description="ALL, WALK_FORWARD_BACKTEST, or SAVED_LIVE_FORECAST"),
    limit: int = Query(150, ge=1, le=500, description="Maximum records to retrieve"),
    db: Session = Depends(get_db),
):
    """
    Retrieves individual prediction-versus-actual evaluation records.
    Distinguishes genuine saved live forecasts from historical walk-forward backtests.
    """
    records = ForecastingService.get_evaluation_records(
        db=db,
        commodity=commodity,
        market=market,
        horizon_days=horizon_days,
        record_type=record_type,
        limit=limit,
    )
    return EvaluationRecordsListResponse(
        commodity=commodity,
        market=market,
        horizon_days=horizon_days,
        record_type=record_type,
        total_count=len(records),
        records=[PredictionActualRecord.model_validate(r) for r in records],
    )


@router.post("/evaluate-saved")
def evaluate_saved_live_forecasts(
    commodity: str = Query(..., description="Crop name"),
    market: str = Query(..., description="Mandi name"),
    db: Session = Depends(get_db),
):
    """
    Matches saved genuine live forecasts from forecast_records against matured actual observations
    in market_observations for the identical commodity, mandi, and target date.
    """
    count = ForecastingService.evaluate_saved_forecasts(db=db, commodity=commodity, market=market)
    return {
        "commodity": commodity,
        "market": market,
        "evaluated_count": count,
        "message": f"Successfully evaluated {count} saved live forecast records against observed actuals.",
    }
