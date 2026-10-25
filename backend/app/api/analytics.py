from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.analytics_service import AnalyticsService
from app.schemas.analytics import (
    HistoricalSeriesView,
    SeasonalAnalysisResponse,
    AnomalyDetectionResponse,
    ArrivalsWeatherResponse,
)

router = APIRouter(prefix="/analytics", tags=["Market Intelligence & Analytics"])


@router.get("/historical-views", response_model=HistoricalSeriesView)
def get_historical_views(
    commodity: str = Query(..., description="Crop name"),
    market: str = Query(..., description="Mandi name"),
    granularity: str = Query("daily", description="Aggregation granularity: daily, weekly, or monthly"),
    db: Session = Depends(get_db),
):
    """
    Returns aggregated price views (daily, weekly, monthly) with 7d, 14d, 30d rolling averages,
    percentage and absolute price changes, and historical period comparisons.
    Missing dates are never interpreted as zero prices.
    """
    return AnalyticsService.get_historical_views(
        db, commodity=commodity, market=market, granularity=granularity
    )


@router.get("/seasonal", response_model=SeasonalAnalysisResponse)
def get_seasonal_analysis(
    commodity: str = Query(..., description="Crop name"),
    market: str = Query(..., description="Mandi name"),
    db: Session = Depends(get_db),
):
    """
    Analyzes monthly modal prices and Indian crop season groups (Kharif, Rabi, Zaid).
    Strictly evaluates historical span to require at least 2 full annual cycles (730 days)
    before claiming recurring seasonal patterns.
    """
    return AnalyticsService.get_seasonal_analysis(db, commodity=commodity, market=market)


@router.get("/anomalies", response_model=AnomalyDetectionResponse)
def get_anomalies(
    commodity: str = Query(..., description="Crop name"),
    market: str = Query(..., description="Mandi name"),
    threshold_multiplier: float = Query(2.5, ge=1.5, le=4.0, description="Anomaly sensitivity multiplier (sigma or IQR)"),
    method: str = Query("rolling_zscore", description="Method: rolling_zscore or iqr"),
    db: Session = Depends(get_db),
):
    """
    Detects statistical price anomalies and distinguishes them from verified data errors.
    Configurable threshold multiplier. Never deletes anomalies automatically.
    """
    return AnalyticsService.detect_anomalies(
        db,
        commodity=commodity,
        market=market,
        threshold_multiplier=threshold_multiplier,
        method=method,
    )


@router.get("/arrivals-weather", response_model=ArrivalsWeatherResponse)
def get_arrivals_weather(
    commodity: str = Query(..., description="Crop name"),
    market: str = Query(..., description="Mandi name"),
    db: Session = Depends(get_db),
):
    """
    Reports market arrival volumes, statistical price-arrival correlation, and
    aligned agro-meteorological reanalysis context from Open-Meteo archive.
    """
    return AnalyticsService.get_arrivals_weather_analysis(db, commodity=commodity, market=market)
