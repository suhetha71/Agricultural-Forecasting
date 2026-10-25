from datetime import datetime, date, timezone
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, UniqueConstraint, Index, func
from app.database import Base


class MarketObservation(Base):
    """
    Represents an observed agricultural mandi transaction record from Agmarknet or CSV import.
    Enforces uniqueness across (state, district, market, commodity, variety, observation_date)
    to eliminate duplicate imports.
    """
    __tablename__ = "market_observations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    state = Column(String(100), nullable=False, index=True)
    district = Column(String(100), nullable=False, index=True)
    market = Column(String(150), nullable=False, index=True)       # Mandi name, e.g. "Lasalgaon"
    commodity = Column(String(100), nullable=False, index=True)    # e.g. "Onion", "Wheat"
    variety = Column(String(100), nullable=False, default="Other", index=True)
    observation_date = Column(Date, nullable=False, index=True)

    min_price = Column(Float, nullable=True)                       # In INR / Quintal
    max_price = Column(Float, nullable=True)                       # In INR / Quintal
    modal_price = Column(Float, nullable=False)                    # Primary benchmark in INR / Quintal
    arrivals_in_qtl = Column(Float, nullable=True)                 # Arrival volume in Quintals

    unit = Column(String(50), nullable=False, default="INR/Quintal")
    original_unit = Column(String(50), nullable=True, default="Rs/Quintal")
    source = Column(String(50), nullable=False, default="DEMO_SEED_DATA", index=True)  # OFFICIAL_GOV_API, USER_CSV_IMPORT, DEMO_SEED_DATA
    retrieval_timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    # Nullable for legacy observations whose first ingestion time is not recoverable.
    first_ingested_at = Column(DateTime, nullable=True)
    # Optional source-provided publication/availability time for the current value.
    source_available_at = Column(DateTime, nullable=True)
    availability_status = Column(
        String(32), nullable=False, default="UNKNOWN", server_default="UNKNOWN"
    )
    extra_metadata = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "state", "district", "market", "commodity", "variety", "observation_date",
            name="uq_market_commodity_variety_date"
        ),
        Index("idx_comm_mkt_date", "commodity", "market", "observation_date"),
    )

    def __repr__(self) -> str:
        return f"<MarketObservation {self.commodity} @ {self.market} ({self.observation_date}): ₹{self.modal_price}/Qtl>"
