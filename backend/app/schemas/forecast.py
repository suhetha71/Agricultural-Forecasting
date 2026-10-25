from datetime import date, datetime
from typing import Optional, List, Dict, Literal
from pydantic import BaseModel, Field, ConfigDict


class ForecastPoint(BaseModel):
    target_date: date
    horizon_days: int
    predicted_price: float
    lower_ci_80: Optional[float] = None
    upper_ci_80: Optional[float] = None
    lower_ci_95: Optional[float] = None
    upper_ci_95: Optional[float] = None


class ModelEvaluationMetrics(BaseModel):
    model_name: str
    model_version: str = "v1.0"
    train_start_date: Optional[date] = None
    train_end_date: Optional[date] = None
    test_start_date: Optional[date] = None
    test_end_date: Optional[date] = None
    holdout_samples: int = 0
    mae: float = Field(..., description="Mean Absolute Error in INR/Quintal")
    rmse: float = Field(..., description="Root Mean Squared Error in INR/Quintal")
    mape: float = Field(..., description="Mean Absolute Percentage Error in %")
    directional_accuracy_pct: Optional[float] = Field(None, description="Percentage of correct trend direction predictions")
    evaluation_method: str = "Walk-Forward Time-Series Split"


ForecastModelPreference = Literal["auto", "holt-winters"]


class ForecastGenerateRequest(BaseModel):
    commodity: str = Field(..., examples=["Onion"])
    market: str = Field(..., examples=["Lasalgaon"])
    state: Optional[str] = None
    horizon_days: int = Field(default=30, ge=1, le=60)
    model_preference: ForecastModelPreference = Field(
        default="auto",
        description="auto selects a supported time-series fit; holt-winters requests seasonal Holt-Winters with an explicitly named fallback when unavailable.",
    )


class ForecastResponse(BaseModel):
    commodity: str
    market: str
    state: str
    last_observed_date: date
    last_observed_price: float
    generated_at: datetime
    model_used: str
    model_version: str
    metrics: Optional[ModelEvaluationMetrics] = None
    forecasts: List[ForecastPoint]
    unit: str = "INR/Quintal"
    is_sufficient_data: bool = True
    message: Optional[str] = None


class PredictionActualRecord(BaseModel):
    id: Optional[int] = None
    record_type: str = Field("WALK_FORWARD_BACKTEST", description="WALK_FORWARD_BACKTEST or SAVED_LIVE_FORECAST")
    commodity: str
    variety: Optional[str] = "Other"
    market: str
    state: Optional[str] = None
    forecast_date: date = Field(..., description="Simulated forecast date / data cutoff t")
    target_date: date = Field(..., description="Target date t + h")
    horizon_days: int = Field(..., description="Forecast horizon in days (7, 15, 30)")
    predicted_price: float
    actual_price: float
    absolute_error: float
    percentage_error: float
    baseline_predicted_price: float
    baseline_absolute_error: float
    model_name: str
    model_version: str = "v1.0"
    price_unit: str = "INR/Quintal"
    data_source: str = "Agmarknet"
    availability_mode: Optional[str] = Field(
        None,
        description="POINT_IN_TIME, RETROSPECTIVE, or null when legacy provenance is unknown",
    )
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ModelAccuracyMetricSet(BaseModel):
    model_name: str
    mae: float = Field(..., description="Mean Absolute Error in INR/Quintal")
    rmse: float = Field(..., description="Root Mean Squared Error in INR/Quintal")
    mape: float = Field(..., description="Mean Absolute Percentage Error in % (safe denominator)")
    sample_count: int
    directional_accuracy_pct: Optional[float] = None
    win_rate_vs_baseline_pct: Optional[float] = Field(
        None, description="Percentage of predictions where model absolute error was lower than baseline"
    )


class HorizonEvaluationSummary(BaseModel):
    horizon_days: int
    horizon_label: str
    sample_count: int
    missing_observations_count: int
    candidate_metrics: ModelAccuracyMetricSet
    baseline_metrics: ModelAccuracyMetricSet
    outperformed_baseline: bool
    evaluation_verdict: str
    reliability_tier: str
    risk_notes: str


class BacktestEvaluationResponse(BaseModel):
    commodity: str
    market: str
    variety: Optional[str] = "All Available"
    state: Optional[str] = None
    price_unit: str = "INR/Quintal"
    data_source: str = "Agmarknet"
    last_observed_date: Optional[date] = None
    last_observed_price: Optional[float] = None
    evaluation_start_date: Optional[date] = None
    evaluation_end_date: Optional[date] = None
    total_historical_records: int = 0
    total_matched_predictions: int = 0
    is_sufficient_sample: bool = True
    insufficient_reason: Optional[str] = None
    horizons: List[HorizonEvaluationSummary] = []
    recent_prediction_records: List[PredictionActualRecord] = []
    metric_explanations: Dict[str, str] = Field(default_factory=dict)
    methodology_notes: str
    historical_reliability_caveats: str
    generated_at: datetime
    availability_mode: str = "POINT_IN_TIME"
    availability_note: Optional[str] = None


class EvaluationRecordsListResponse(BaseModel):
    commodity: Optional[str] = None
    market: Optional[str] = None
    horizon_days: Optional[int] = None
    record_type: Optional[str] = None
    total_count: int
    records: List[PredictionActualRecord]
