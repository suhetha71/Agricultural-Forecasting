from datetime import datetime, timezone
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="Application operational health")
    app_name: str = Field(description="Exact project name")
    version: str = Field(default="1.0.0")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    database_connected: bool = Field(description="Database connectivity status")
    total_observations: int = Field(default=0, description="Total observed market price records in DB")
    total_forecasts: int = Field(default=0, description="Total stored forecast records in DB")
