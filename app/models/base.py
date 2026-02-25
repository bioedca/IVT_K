"""Base model utilities and mixins."""
from datetime import datetime
from sqlalchemy import Column, Float, Boolean, DateTime
from app.extensions import db


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class FitResultMixin:
    """
    Mixin for shared curve fitting result columns.

    Used by both FitResult (current fits) and FitResultArchive (historical fits)
    to eliminate column duplication.
    """
    # Fitted parameters
    f_baseline = Column(Float, nullable=True)
    f_baseline_se = Column(Float, nullable=True)
    f_max = Column(Float, nullable=True)
    f_max_se = Column(Float, nullable=True)
    k_obs = Column(Float, nullable=True)
    k_obs_se = Column(Float, nullable=True)
    t_lag = Column(Float, nullable=True)
    t_lag_se = Column(Float, nullable=True)

    # Goodness of fit
    r_squared = Column(Float, nullable=True)
    rmse = Column(Float, nullable=True)
    aic = Column(Float, nullable=True)

    # Quality flags
    converged = Column(Boolean, default=False)
    residual_normality_pvalue = Column(Float, nullable=True)

    @property
    def is_good_fit(self) -> bool:
        """Check if this is a good quality fit."""
        return (
            self.converged is True and
            self.r_squared is not None and
            self.r_squared >= 0.9
        )


class Base(db.Model):
    """Abstract base class for all models."""
    __abstract__ = True
