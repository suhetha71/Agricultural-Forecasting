from datetime import datetime, date, timezone
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, Index, func
from app.database import Base


class ForecastRecord(Base):
    """
    Stores generated crop price forecasts, horizons, model details,
    and associated uncertainty intervals (confidence bounds).
    """
    __tablename__ = "forecast_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    commodity = Column(String(100), nullable=False, index=True)
    market = Column(String(150), nullable=False, index=True)
    state = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    variety = Column(String(100), nullable=True, default="Other")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False, index=True)
    target_date = Column(Date, nullable=False, index=True)
    horizon_days = Column(Integer, nullable=False)                 # e.g., 7, 15, 30

    predicted_price = Column(Float, nullable=False)                # Forecast modal price in INR / Quintal
    lower_ci_80 = Column(Float, nullable=True)                     # 80% lower bound
    upper_ci_80 = Column(Float, nullable=True)                     # 80% upper bound
    lower_ci_95 = Column(Float, nullable=True)                     # 95% lower bound
    upper_ci_95 = Column(Float, nullable=True)                     # 95% upper bound

    model_name = Column(String(100), nullable=False)               # Actual fitted model name, including fallback disclosure when applicable
    model_version = Column(String(50), nullable=False, default="v1.0")
    metrics_mae = Column(Float, nullable=True)                     # MAE on holdout test set
    metrics_rmse = Column(Float, nullable=True)                    # RMSE on holdout test set
    metrics_mape = Column(Float, nullable=True)                    # MAPE percentage on holdout test set

    unit = Column(String(50), nullable=False, default="INR/Quintal")
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_forecast_target", "commodity", "market", "target_date"),
    )

    def __repr__(self) -> str:
        return f"<ForecastRecord {self.commodity} @ {self.market} for {self.target_date} (+{self.horizon_days}d): ₹{self.predicted_price} via {self.model_name}>"
