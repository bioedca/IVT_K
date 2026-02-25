"""BackgroundEstimate model - background correction data."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
import enum

from app.extensions import db


class CorrectionMethod(enum.Enum):
    """Background correction method types."""
    SIMPLE = "simple"
    TIME_DEPENDENT = "time_dependent"
    SPATIAL = "spatial"


class BackgroundEstimate(db.Model):
    """
    Background fluorescence estimate for a plate at each timepoint.

    Used for background subtraction in kinetic analysis.
    """
    __tablename__ = "background_estimates"

    id = Column(Integer, primary_key=True)
    plate_id = Column(Integer, ForeignKey("plates.id"), nullable=False)
    timepoint = Column(Float, nullable=False)  # minutes
    mean_background = Column(Float, nullable=False)
    sd_background = Column(Float, nullable=False)
    n_controls = Column(Integer, nullable=False)
    polynomial_coefficients = Column(JSON, nullable=True)  # [c0, c1, c2] for time-dependent
    correction_method = Column(Enum(CorrectionMethod), default=CorrectionMethod.SIMPLE)
    computed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    plate = relationship("Plate", back_populates="background_estimates")

    def __repr__(self):
        return f"<BackgroundEstimate id={self.id} plate={self.plate_id} t={self.timepoint:.1f}min mean={self.mean_background:.1f}>"
