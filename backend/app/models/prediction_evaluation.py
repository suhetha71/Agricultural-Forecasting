from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Index, func
from app.database import Base


class PredictionEvaluationRecord(Base):
    """
    Stores individual prediction-versus-actual matching records for both
    empirical walk-forward backtests and live saved forecasts.
    Guarantees strict auditability, model-vs-baseline comparisons,
    and prevents future-data leakage.
    """
    __tablename__ = "prediction_evaluations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    record_type = Column(String(50), nullable=False, default="WALK_FORWARD_BACKTEST", index=True)  # "WALK_FORWARD_BACKTEST" or "SAVED_LIVE_FORECAST"
    commodity = Column(String(100), nullable=False, index=True)
    variety = Column(String(100), nullable=True, default="Other")
    market = Column(String(150), nullable=False, index=True)
    state = Column(String(100), nullable=True)

    forecast_date = Column(Date, nullable=False, index=True)  # Simulated forecast date / cutoff date
    target_date = Column(Date, nullable=False, index=True)    # Target observation date
    horizon_days = Column(Integer, nullable=False, index=True)  # 7, 15, 30

    predicted_price = Column(Float, nullable=False)
    actual_price = Column(Float, nullable=False)
    absolute_error = Column(Float, nullable=False)
    percentage_error = Column(Float, nullable=False)

    baseline_predicted_price = Column(Float, nullable=False)
    baseline_absolute_error = Column(Float, nullable=False)

    model_name = Column(String(100), nullable=False)
    model_version = Column(String(50), nullable=False, default="v1.0")
    price_unit = Column(String(50), nullable=False, default="INR/Quintal")
    data_source = Column(String(100), nullable=False, default="Agmarknet")
    # Null on older evaluation rows whose training availability mode is unknown.
    availability_mode = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_eval_comm_mkt_hz", "commodity", "market", "horizon_days"),
        Index("idx_eval_target_match", "commodity", "market", "target_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<PredictionEvaluationRecord {self.record_type}: {self.commodity} @ {self.market} "
            f"for {self.target_date} (H={self.horizon_days}d): Pred=₹{self.predicted_price}, "
            f"Act=₹{self.actual_price}, Err=₹{self.absolute_error}>"
        )
