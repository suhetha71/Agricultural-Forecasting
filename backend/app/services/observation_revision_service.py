from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.market_observation import MarketObservation
from app.models.market_observation_revision import MarketObservationRevision


def _revision_values(observation: MarketObservation, revision_number: int):
    return MarketObservationRevision(
        observation_id=observation.id,
        revision_number=revision_number,
        modal_price=observation.modal_price,
        min_price=observation.min_price,
        max_price=observation.max_price,
        arrivals_in_qtl=observation.arrivals_in_qtl,
        unit=observation.unit,
        original_unit=observation.original_unit,
        source=observation.source,
        ingested_at=(
            observation.retrieval_timestamp
            if observation.availability_status != "UNKNOWN"
            else None
        ),
        source_available_at=observation.source_available_at,
        availability_status=observation.availability_status or "UNKNOWN",
        recorded_at=datetime.now(timezone.utc),
    )


def ensure_initial_revision(db: Session, observation: MarketObservation) -> None:
    """Snapshot the current value once, including legacy values as unknown."""
    if observation.id is None:
        db.flush()

    exists = (
        db.query(MarketObservationRevision.id)
        .filter(MarketObservationRevision.observation_id == observation.id)
        .first()
    )
    if exists:
        return

    db.add(_revision_values(observation, revision_number=1))
    db.flush()


def append_current_revision(db: Session, observation: MarketObservation) -> None:
    """Append the current value as a new immutable import revision."""
    latest_number = (
        db.query(func.max(MarketObservationRevision.revision_number))
        .filter(MarketObservationRevision.observation_id == observation.id)
        .scalar()
    )
    db.add(_revision_values(observation, revision_number=(latest_number or 0) + 1))
    db.flush()
