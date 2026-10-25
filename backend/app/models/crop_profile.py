from sqlalchemy import Column, Integer, String, Float, Text
from app.database import Base


class CropProfile(Base):
    """
    Reference metadata for agricultural commodities, storage constraints,
    typical monthly deterioration/shrinkage, and cold storage cost baselines.
    """
    __tablename__ = "crop_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    commodity = Column(String(100), unique=True, nullable=False, index=True)
    category = Column(String(50), nullable=False)                  # Perishable, Semi-Perishable, Non-Perishable
    safe_storage_days_ambient = Column(Integer, nullable=False)    # Days without cold chain
    safe_storage_days_cold = Column(Integer, nullable=False)       # Days with modern warehouse/cold storage
    monthly_storage_rent_qtl = Column(Float, nullable=False)       # Typical INR per Quintal per month
    monthly_weight_loss_pct = Column(Float, nullable=False)        # Normal shrinkage / weight loss percentage
    typical_harvest_season = Column(String(100), nullable=True)    # e.g., "Rabi (March-May)", "Kharif (Sept-Nov)"
    description = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<CropProfile {self.commodity} ({self.category})>"
