from datetime import date, datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PriceChangeMetric(BaseModel):
    window_days: int
    window_label: str
    absolute_change: float
    percentage_change: float
    start_date: date
    end_date: date
    start_price: float
    end_price: float


class AggregatedPricePoint(BaseModel):
    period_label: str  # e.g., "2026-W42" or "2026-10" or "2026-10-24"
    start_date: date
    end_date: date
    modal_price_avg: float
    modal_price_min: float
    modal_price_max: float
    total_arrivals_qtl: Optional[float] = None
    observation_count: int
    rolling_7d_avg: Optional[float] = None
    rolling_14d_avg: Optional[float] = None
    rolling_30d_avg: Optional[float] = None


class HistoricalSeriesView(BaseModel):
    commodity: str
    market: str
    granularity: str  # "daily", "weekly", "monthly"
    total_observations: int
    period_start: Optional[date]
    period_end: Optional[date]
    points: List[AggregatedPricePoint]
    price_changes: List[PriceChangeMetric]
    current_vs_historical: Dict[str, Any]


class MonthlySeasonalityPoint(BaseModel):
    month_number: int
    month_name: str
    avg_modal_price: float
    min_modal_price: float
    max_modal_price: float
    std_modal_price: float
    observation_count: int


class SeasonGroupPoint(BaseModel):
    season_name: str  # "Kharif", "Rabi", "Zaid"
    months_included: str
    avg_modal_price: float
    observation_count: int
    crop_season_context: str


class SeasonalAnalysisResponse(BaseModel):
    commodity: str
    market: str
    total_observations: int
    historical_span_days: int
    historical_span_months: float
    has_sufficient_multiyear_data: bool
    data_sufficiency_explanation: str
    monthly_patterns: List[MonthlySeasonalityPoint]
    season_patterns: List[SeasonGroupPoint]


class AnomalyItem(BaseModel):
    observation_date: date
    commodity: str
    market: str
    modal_price: float
    baseline_price: float  # Rolling mean or median
    threshold_upper: float
    threshold_lower: float
    deviation_amount: float
    z_score: Optional[float] = None
    anomaly_type: str  # "HIGH_SPIKE", "LOW_CRASH", "SUSPECTED_DATA_ERROR"
    severity: str  # "MILD", "MODERATE", "EXTREME"
    explanation: str
    is_verified_data_error: bool


class AnomalyDetectionResponse(BaseModel):
    commodity: str
    market: str
    detection_method: str  # "rolling_zscore", "iqr"
    threshold_multiplier: float
    total_observations_analyzed: int
    anomaly_count: int
    data_error_count: int
    anomalies: List[AnomalyItem]
    method_explanation: str


class FeatureImportanceItem(BaseModel):
    feature_name: str
    display_name: str
    importance_pct: float
    direction: str  # "positive", "negative", "neutral"
    description: str
    sample_value: Optional[float] = None


class ModelExplanationResponse(BaseModel):
    commodity: str
    market: str
    model_name: str
    is_explainable: bool
    total_training_samples: int
    features: List[FeatureImportanceItem]
    shap_summary_available: bool
    shap_base_value: Optional[float] = None
    causality_disclaimer: str
    message: Optional[str] = None


class HorizonRiskItem(BaseModel):
    horizon_days: int
    horizon_label: str
    holdout_mae: float
    holdout_rmse: float
    holdout_mape: float
    confidence_spread_pct: float
    reliability_tier: str  # "High", "Moderate", "Extrapolated"
    risk_notes: str


class ForecastUncertaintyResponse(BaseModel):
    commodity: str
    market: str
    evaluation_sample_size: int
    is_sample_sufficient: bool
    horizons: List[HorizonRiskItem]
    methodology_explanation: str
    horizon_extrapolation_warning: Optional[str] = None
    disclaimer: str


class WeatherDailyObservation(BaseModel):
    observation_date: date
    temperature_max_c: Optional[float] = None
    temperature_min_c: Optional[float] = None
    precipitation_mm: Optional[float] = Field(None, ge=0)


class WeatherLocation(BaseModel):
    name: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    coordinate_precision: str


class ArrivalsWeatherResponse(BaseModel):
    commodity: str
    market: str
    total_observations: int
    arrivals_reported_count: int
    arrivals_coverage_pct: float
    price_arrival_correlation: Optional[float] = None
    correlation_significance: Optional[str] = None
    correlation_interpretation: str
    weather_source: str
    weather_available: bool
    weather_data_notes: str
    weather_status: str = "NO_DATA"
    weather_location: Optional[WeatherLocation] = None
    weather_observations: List[WeatherDailyObservation] = Field(default_factory=list)
    weather_aligned_count: int = 0
    weather_missing_date_count: int = 0
    weather_attribution_url: Optional[str] = None
