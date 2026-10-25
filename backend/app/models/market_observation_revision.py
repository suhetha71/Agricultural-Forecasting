from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    event,
)

from app.database import Base


class MarketObservationRevision(Base):
    """Immutable imported value version for a current market observation."""

    __tablename__ = "market_observation_revisions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    observation_id = Column(
        Integer,
        ForeignKey("market_observations.id"),
        nullable=False,
        index=True,
    )
    revision_number = Column(Integer, nullable=False)

    modal_price = Column(Float, nullable=False)
    min_price = Column(Float, nullable=True)
    max_price = Column(Float, nullable=True)
    arrivals_in_qtl = Column(Float, nullable=True)
    unit = Column(String(50), nullable=False, default="INR/Quintal")
    original_unit = Column(String(50), nullable=True)
    source = Column(String(50), nullable=False)

    # When this value version was ingested by this application. Null is retained
    # for a legacy value whose ingestion time cannot be established.
    ingested_at = Column(DateTime, nullable=True)
    source_available_at = Column(DateTime, nullable=True)
    availability_status = Column(
        String(32), nullable=False, default="UNKNOWN", server_default="UNKNOWN"
    )
    recorded_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint(
            "observation_id", "revision_number", name="uq_observation_revision_number"
        ),
        Index("idx_observation_revision_recorded", "observation_id", "recorded_at"),
    )


@event.listens_for(MarketObservationRevision, "before_update")
@event.listens_for(MarketObservationRevision, "before_delete")
def prevent_revision_mutation(mapper, connection, target):
    """Keep revision rows append-only through the application ORM."""
    raise ValueError("Market observation revisions are immutable")
