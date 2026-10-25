from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class MarketObservationBase(BaseModel):
    state: str = Field(..., examples=["Maharashtra"])
    district: str = Field(..., examples=["Nashik"])
    market: str = Field(..., examples=["Lasalgaon"])
    commodity: str = Field(..., examples=["Onion"])
    variety: str = Field(default="Other", examples=["Red"])
    observation_date: date = Field(..., examples=["2026-10-20"])
    min_price: Optional[float] = Field(None, ge=0, examples=[1800.0])
    max_price: Optional[float] = Field(None, ge=0, examples=[2400.0])
    modal_price: float = Field(..., ge=0, examples=[2150.0])
    arrivals_in_qtl: Optional[float] = Field(None, ge=0, examples=[1250.0])
    unit: str = Field(default="INR/Quintal")
    original_unit: Optional[str] = Field(default="Rs/Quintal")
    source: str = Field(default="DEMO_SEED_DATA", examples=["OFFICIAL_GOV_API", "USER_CSV_IMPORT", "DEMO_SEED_DATA"])
    extra_metadata: Optional[str] = None


class MarketObservationCreate(MarketObservationBase):
    pass


class MarketObservationRead(MarketObservationBase):
    id: int
    retrieval_timestamp: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MarketFilterParams(BaseModel):
    commodity: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    market: Optional[str] = None
    variety: Optional[str] = None
    source: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    limit: int = Field(default=100, le=1000)
    offset: int = Field(default=0, ge=0)


class DataSourceStats(BaseModel):
    official_api_records: int = 0
    user_csv_records: int = 0
    demo_seed_records: int = 0
    total_records: int = 0
    oldest_observation_date: Optional[date] = None
    newest_observation_date: Optional[date] = None
    last_retrieval_timestamp: Optional[datetime] = None


class MarketSummary(BaseModel):
    commodity: str
    market: str
    state: str
    latest_date: Optional[date] = None
    latest_modal_price: Optional[float] = None
    min_modal_price_30d: Optional[float] = None
    max_modal_price_30d: Optional[float] = None
    avg_modal_price_30d: Optional[float] = None
    price_change_7d_pct: Optional[float] = None
    total_records: int = 0
    source: str = "DEMO_SEED_DATA"
    retrieval_timestamp: Optional[datetime] = None


class MandiComparisonItem(BaseModel):
    market: str
    district: str
    state: str
    latest_date: date
    modal_price: float
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    distance_km_estimate: float = 0.0
    estimated_transport_cost_qtl: float = 0.0
    net_realization_qtl: float = 0.0
    price_difference_vs_local: float = 0.0


class ImportResult(BaseModel):
    success: bool
    imported_count: int = 0
    duplicate_count: int = 0
    skipped_count: int = 0
    errors: List[str] = []
    message: str


class GovernmentSyncRequest(BaseModel):
    """Sensitive credentials are accepted in the request body, never the URL."""

    api_key: Optional[str] = None


class GovernmentSyncResult(BaseModel):
    """Stable response contract for data.gov.in synchronization."""

    success: bool
    status: str
    message: str
    instructions: Optional[str] = None
    imported_count: int = 0
    updated_count: int = 0
    duplicate_count: int = 0
    skipped_count: int = 0
    fetched_count: int = 0
    total_available_count: Optional[int] = None
    pagination_truncated: bool = False
    errors: List[str] = Field(default_factory=list)
