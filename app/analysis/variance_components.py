"""Shared variance component dataclasses for hierarchical models.

Both Bayesian and Frequentist modules produce variance decompositions
with identical structure (session, plate, residual). This module
provides the shared dataclasses.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class VarianceComponents:
    """Variance decomposition from hierarchical model (Bayesian)."""
    var_session: Optional[float]  # None if not estimated (insufficient data)
    var_plate: Optional[float]    # None if not estimated (insufficient data)
    var_residual: float
    var_total: float

    # Status messages for components not estimated
    session_status: Optional[str] = None  # e.g., "N/A — insufficient data"
    plate_status: Optional[str] = None

    @property
    def icc_session(self) -> Optional[float]:
        """Intraclass correlation for session level."""
        if self.var_session is None or self.var_total <= 0:
            return None
        return self.var_session / self.var_total

    @property
    def icc_plate(self) -> Optional[float]:
        """Intraclass correlation for plate level."""
        if self.var_plate is None or self.var_total <= 0:
            return None
        return self.var_plate / self.var_total

    @property
    def fraction_residual(self) -> float:
        """Fraction of variance at residual level."""
        return self.var_residual / self.var_total if self.var_total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with status messages for missing components."""
        return {
            'var_session': self.var_session if self.var_session is not None else self.session_status,
            'var_plate': self.var_plate if self.var_plate is not None else self.plate_status,
            'var_residual': self.var_residual,
            'var_total': self.var_total,
            'icc_session': self.icc_session,
            'icc_plate': self.icc_plate,
            'fraction_residual': self.fraction_residual
        }


@dataclass
class FrequentistVarianceComponents:
    """Variance components from REML estimation."""
    var_session: Optional[float]  # None if not estimated
    var_plate: Optional[float]    # None if not estimated
    var_residual: float
    var_total: float

    # Standard errors of variance estimates
    var_session_se: Optional[float] = None
    var_plate_se: Optional[float] = None
    var_residual_se: Optional[float] = None

    # Status messages for components not estimated
    session_status: Optional[str] = None
    plate_status: Optional[str] = None

    @property
    def icc_session(self) -> Optional[float]:
        """Intraclass correlation for session level."""
        if self.var_session is None or self.var_total <= 0:
            return None
        return self.var_session / self.var_total

    @property
    def icc_plate(self) -> Optional[float]:
        """Intraclass correlation for plate level."""
        if self.var_plate is None or self.var_total <= 0:
            return None
        return self.var_plate / self.var_total

    @property
    def fraction_residual(self) -> float:
        """Fraction of variance at residual level."""
        return self.var_residual / self.var_total if self.var_total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with status messages for missing components."""
        return {
            'var_session': self.var_session if self.var_session is not None else self.session_status,
            'var_plate': self.var_plate if self.var_plate is not None else self.plate_status,
            'var_residual': self.var_residual,
            'var_total': self.var_total,
            'var_session_se': self.var_session_se,
            'var_plate_se': self.var_plate_se,
            'var_residual_se': self.var_residual_se,
            'icc_session': self.icc_session,
            'icc_plate': self.icc_plate,
            'fraction_residual': self.fraction_residual
        }
