"""Shared data structure detection and model tier selection.

Consolidates duplicated logic previously in both bayesian.py and
frequentist.py into a single module.
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

import pandas as pd

logger = logging.getLogger(__name__)


class ModelTier(Enum):
    """Hierarchical model complexity tiers based on data structure."""
    TIER_1_RESIDUAL_ONLY = "tier_1"
    TIER_2A_SESSION = "tier_2a"
    TIER_2B_PLATE = "tier_2b"
    TIER_3_FULL = "tier_3"


@dataclass
class ModelMetadata:
    """Metadata about the selected model tier and variance components."""
    tier: ModelTier
    n_sessions: int
    n_plates: int
    max_plates_per_session: int

    # Which variance components are estimated
    estimates_session_variance: bool
    estimates_plate_variance: bool
    estimates_residual_variance: bool = True  # Always estimated

    # User-facing message
    user_message: str = ""

    # Components pending more data
    pending_components: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'tier': self.tier.value,
            'tier_name': self._tier_display_name(),
            'n_sessions': self.n_sessions,
            'n_plates': self.n_plates,
            'max_plates_per_session': self.max_plates_per_session,
            'estimates_session_variance': self.estimates_session_variance,
            'estimates_plate_variance': self.estimates_plate_variance,
            'estimates_residual_variance': self.estimates_residual_variance,
            'user_message': self.user_message,
            'pending_components': self.pending_components
        }

    def _tier_display_name(self) -> str:
        """Human-readable tier name."""
        names = {
            ModelTier.TIER_1_RESIDUAL_ONLY: "Tier 1 (residual only)",
            ModelTier.TIER_2A_SESSION: "Tier 2a (session + residual)",
            ModelTier.TIER_2B_PLATE: "Tier 2b (plate + residual)",
            ModelTier.TIER_3_FULL: "Tier 3 (full hierarchy)"
        }
        return names.get(self.tier, str(self.tier))


@dataclass
class DataStructure:
    """Summary of hierarchical data structure."""
    n_sessions: int
    n_plates: int
    max_plates_per_session: int
    plates_per_session: Dict[Any, int] = field(default_factory=dict)


class DataStructureAnalyzer:
    """Detects data structure and selects the appropriate model tier."""

    @staticmethod
    def detect(fold_changes: pd.DataFrame) -> DataStructure:
        """
        Detect data structure from fold-change DataFrame.

        Expected columns: session_id, plate_id.

        Returns:
            DataStructure with counts of sessions, plates, and nesting.
        """
        df = fold_changes

        n_sessions = df['session_id'].nunique()

        plates_per_session = (
            df.groupby('session_id')['plate_id']
            .nunique()
            .to_dict()
        )
        max_plates_per_session = max(plates_per_session.values()) if plates_per_session else 0

        n_plates = df['plate_id'].nunique()

        return DataStructure(
            n_sessions=n_sessions,
            n_plates=n_plates,
            max_plates_per_session=max_plates_per_session,
            plates_per_session=plates_per_session
        )

    @staticmethod
    def select_model_tier(
        structure: DataStructure,
        method: str = "bayesian"
    ) -> ModelMetadata:
        """
        Select appropriate model tier based on data structure.

        Tier Selection Logic:
        - Tier 1 (residual only): 1 session AND 1 plate
        - Tier 2a (session + residual): 2+ sessions AND max 1 plate/session
        - Tier 2b (plate + residual): 1 session AND 2+ plates
        - Tier 3 (full hierarchy): 2+ sessions AND 2+ plates in any session

        Args:
            structure: Output from detect().
            method: "bayesian" or "frequentist" (affects user-facing message).

        Returns:
            ModelMetadata with tier and user message.
        """
        n_sessions = structure.n_sessions
        max_plates = structure.max_plates_per_session
        n_plates = structure.n_plates

        if n_sessions == 0 or n_plates == 0:
            raise ValueError(
                "Cannot select model tier for empty data: "
                f"n_sessions={n_sessions}, n_plates={n_plates}"
            )

        if n_sessions == 1 and max_plates <= 1:
            tier = ModelTier.TIER_1_RESIDUAL_ONLY
            estimates_session = False
            estimates_plate = False
            pending = ['session variance', 'plate variance']
            if method == "frequentist":
                message = (
                    "Current model: Tier 1 (residual only). "
                    "Using simple OLS — no random effects estimable with single session/plate."
                )
            else:
                message = (
                    "Current model: Tier 1 (residual only). "
                    "Session-level and plate-level variance cannot be estimated "
                    "with data from a single session and plate. "
                    "Collect data from additional sessions to enable hierarchical decomposition."
                )
        elif n_sessions >= 2 and max_plates <= 1:
            tier = ModelTier.TIER_2A_SESSION
            estimates_session = True
            estimates_plate = False
            pending = ['plate variance']
            if method == "frequentist":
                message = (
                    "Current model: Tier 2a (session + residual). "
                    "Plate-level variance cannot yet be estimated."
                )
            else:
                message = (
                    "Current model: Tier 2a (session + residual). "
                    "Plate-level variance cannot yet be estimated — "
                    "collect multiple plates per session to enable full hierarchical decomposition."
                )
        elif n_sessions == 1 and max_plates >= 2:
            tier = ModelTier.TIER_2B_PLATE
            estimates_session = False
            estimates_plate = True
            pending = ['session variance']
            if method == "frequentist":
                message = (
                    "Current model: Tier 2b (plate + residual). "
                    "Session-level variance cannot yet be estimated."
                )
            else:
                message = (
                    "Current model: Tier 2b (plate + residual). "
                    "Session-level variance cannot yet be estimated — "
                    "collect data from additional sessions to enable full hierarchical decomposition."
                )
        else:  # n_sessions >= 2 and max_plates >= 2
            tier = ModelTier.TIER_3_FULL
            estimates_session = True
            estimates_plate = True
            pending = []
            message = (
                "Current model: Tier 3 (full hierarchy). "
                "All variance components are being estimated."
            )

        label = "Frequentist" if method == "frequentist" else "Bayesian"
        logger.info(
            f"{label} selected {tier.value}: n_sessions={n_sessions}, "
            f"max_plates_per_session={max_plates}, n_plates={n_plates}"
        )

        return ModelMetadata(
            tier=tier,
            n_sessions=n_sessions,
            n_plates=n_plates,
            max_plates_per_session=max_plates,
            estimates_session_variance=estimates_session,
            estimates_plate_variance=estimates_plate,
            user_message=message,
            pending_components=pending
        )
