"""Recommendation engine for Smart Experiment Planner.

Provides ranked recommendations for which constructs to test next,
based on precision gaps, untested status, and co-plating benefits.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum
from datetime import datetime, timedelta

from .power_analysis import (
    calculate_precision_gap_score,
    calculate_untested_score,
    estimate_coplating_benefit,
    calculate_sample_size_for_precision,
)
from .constants import (
    MIN_REPLICATES,
    MAX_TEMPLATES_RECOMMENDED,
    MAX_TEMPLATES_ABSOLUTE,
    DEFAULT_PRECISION_TARGET,
    DEFAULT_NEGATIVE_TEMPLATE_REPLICATES,
    DEFAULT_NEGATIVE_DYE_REPLICATES,
    TARGET_EFFECT_PROBABILITY,
)


class RecommendationConfidence(Enum):
    """Confidence level for recommendations."""
    REQUIRED = "required"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"


@dataclass
class ConstructStats:
    """Statistics for a construct used in recommendations."""
    construct_id: int
    name: str
    family: Optional[str]
    is_wildtype: bool
    is_unregulated: bool
    replicate_count: int
    ci_width: Optional[float]  # Current CI width for fold change
    has_data: bool
    plasmid_size_bp: Optional[int] = None
    prob_meaningful: Optional[float] = None  # P(|FC| > θ) from Bayesian analysis

    @property
    def meets_precision_target(self) -> bool:
        """Check if construct meets precision target."""
        if self.ci_width is None:
            return False
        return self.ci_width <= DEFAULT_PRECISION_TARGET


@dataclass
class ConstructRecommendation:
    """A single construct recommendation with scoring details."""
    construct_id: int
    name: str
    family: Optional[str]
    is_wildtype: bool
    is_unregulated: bool
    is_anchor: bool  # WT or unregulated
    total_score: float
    precision_gap_score: float
    untested_score: float
    coplating_score: float
    brief_reason: str
    detailed_reason: str
    current_ci_width: Optional[float]
    target_ci_width: float
    replicates_needed: int
    plates_estimate: int
    plasmid_size_bp: Optional[int] = None
    prob_meaningful: Optional[float] = None  # P(|FC| > θ) from Bayesian analysis


@dataclass
class DFHBIRecommendation:
    """Recommendation for -DFHBI control inclusion."""
    include: bool
    confidence: RecommendationConfidence
    reason: str
    recent_control_count: int
    recent_mean_signal: Optional[float]
    typical_fmax: Optional[float]


@dataclass
class ExperimentPlan:
    """A complete experiment plan with constructs and controls."""
    constructs: List[ConstructRecommendation]
    auto_added_anchors: List[ConstructRecommendation]
    negative_template_count: int
    negative_dye_count: int
    dfhbi_recommendation: DFHBIRecommendation
    total_wells: int
    total_templates: int
    template_limit_exceeded: bool
    capacity_exceeded: bool
    warnings: List[str] = field(default_factory=list)


# Fixed recommendation weights (from PRD)
WEIGHT_PRECISION_GAP = 0.50
WEIGHT_UNTESTED = 0.30
WEIGHT_COPLATING = 0.20


class RecommendationEngine:
    """Engine for generating construct recommendations.

    Scores represent each construct's share of remaining experimental need.
    Untested constructs get raw_need=100. Tested constructs get a precision
    gap component (0-50+) plus an effect probability gap component (0-50).
    After computing raw needs, rank_constructs() normalizes scores so the
    total sums to ~100%, giving each construct a percentage share.
    """

    def __init__(
        self,
        target_ci_width: float = DEFAULT_PRECISION_TARGET,
    ):
        """
        Initialize recommendation engine.

        Args:
            target_ci_width: Target CI width for precision calculations
        """
        self.target_ci_width = target_ci_width

    def _compute_raw_need(self, construct: ConstructStats) -> float:
        """
        Compute unbounded raw need score for a construct.

        Returns a positive float representing how much experimental
        attention this construct still requires:
        - Untested: 100.0
        - Tested with analysis: precision_gap (0-50+) + effect_prob_gap (0-50)
        - Tested but no analysis: precision_gap + 25 (moderate penalty)

        Args:
            construct: Construct statistics

        Returns:
            Raw need score (unbounded positive float)
        """
        if not construct.has_data:
            return 100.0

        # Precision gap component: how far CI is above target (0-50+)
        precision_gap = 0.0
        if construct.ci_width is not None and construct.ci_width > self.target_ci_width:
            gap_ratio = (construct.ci_width - self.target_ci_width) / self.target_ci_width
            precision_gap = min(50.0, gap_ratio * 50.0)

        # Effect probability gap component
        effect_gap = 0.0
        if construct.prob_meaningful is not None:
            if construct.prob_meaningful < TARGET_EFFECT_PROBABILITY:
                # Scale: 0% prob → 50 gap, 95% prob → 0 gap
                effect_gap = (1.0 - construct.prob_meaningful / TARGET_EFFECT_PROBABILITY) * 50.0
        elif construct.has_data and construct.ci_width is not None:
            # Has data but no Bayesian analysis yet — moderate penalty
            effect_gap = 25.0

        return precision_gap + effect_gap

    def _classify_construct(
        self,
        construct: ConstructStats,
        raw_need: float,
    ) -> tuple:
        """
        Classify a construct into a recommendation category.

        Hierarchy:
        1. Untested → "Untested construct"
        2. P(|FC|>θ) < 95% → "Effect not yet established (X%)"
        3. CI > target → "X% precision gap"
        4. Both met → "Maintenance testing"

        Args:
            construct: Construct statistics
            raw_need: Raw need score from _compute_raw_need

        Returns:
            Tuple of (brief_reason, detailed_reason)
        """
        if not construct.has_data:
            return (
                "Untested construct",
                "This construct has no uploaded data. "
                "Testing it will establish baseline measurements.",
            )

        # Check effect probability gap
        if construct.prob_meaningful is not None and construct.prob_meaningful < TARGET_EFFECT_PROBABILITY:
            pct = construct.prob_meaningful * 100
            return (
                f"Effect not yet established ({pct:.0f}%)",
                f"P(|FC| > θ) = {pct:.0f}%, below the {TARGET_EFFECT_PROBABILITY * 100:.0f}% target. "
                f"Additional replicates will help establish whether this construct "
                f"has a meaningful effect.",
            )

        # Check precision gap
        if construct.ci_width is not None and construct.ci_width > self.target_ci_width:
            gap_ratio = (construct.ci_width - self.target_ci_width) / self.target_ci_width
            gap_pct = min(100, int(gap_ratio * 100))
            return (
                f"{gap_pct}% precision gap",
                f"Current CI width (±{construct.ci_width / 2:.2f}) "
                f"exceeds target (±{self.target_ci_width / 2:.2f}). "
                f"Additional replicates will improve precision.",
            )

        # Both targets met
        return (
            "Maintenance testing",
            "Construct meets precision and effect probability targets. "
            "Additional data would provide incremental benefit.",
        )

    def score_construct(
        self,
        construct: ConstructStats,
        current_plan_families: Set[str],
    ) -> ConstructRecommendation:
        """
        Score a single construct for recommendation.

        Used standalone by create_experiment_plan and get_required_anchors.
        Returns raw_need as total_score (not normalized).

        Args:
            construct: Construct statistics
            current_plan_families: Families already in plan

        Returns:
            ConstructRecommendation with scores
        """
        raw_need = self._compute_raw_need(construct)

        # Legacy component scores for backward compatibility
        precision_score = calculate_precision_gap_score(
            construct.ci_width,
            self.target_ci_width,
        )
        untested_score = calculate_untested_score(construct.has_data)
        coplating_score = estimate_coplating_benefit(
            constructs_on_plate=[],
            new_construct_family=construct.family or "",
            families_on_plate=current_plan_families,
        )

        brief, detailed = self._classify_construct(construct, raw_need)

        # Estimate replicates needed
        sample_result = calculate_sample_size_for_precision(
            current_ci_width=construct.ci_width,
            current_n=construct.replicate_count,
            target_ci_width=self.target_ci_width,
        )

        return ConstructRecommendation(
            construct_id=construct.construct_id,
            name=construct.name,
            family=construct.family,
            is_wildtype=construct.is_wildtype,
            is_unregulated=construct.is_unregulated,
            is_anchor=construct.is_wildtype or construct.is_unregulated,
            total_score=raw_need,
            precision_gap_score=precision_score,
            untested_score=untested_score,
            coplating_score=coplating_score,
            brief_reason=brief,
            detailed_reason=detailed,
            current_ci_width=construct.ci_width,
            target_ci_width=self.target_ci_width,
            replicates_needed=sample_result.additional_needed,
            plates_estimate=(sample_result.additional_needed + 3) // 4,
            prob_meaningful=construct.prob_meaningful,
        )

    def rank_constructs(
        self,
        constructs: List[ConstructStats],
        exclude_ids: Optional[Set[int]] = None,
    ) -> List[ConstructRecommendation]:
        """
        Rank all constructs by recommendation score.

        Two-pass approach:
        1. Compute raw needs for all constructs
        2. Normalize so scores sum to ~100%

        Args:
            constructs: List of construct statistics
            exclude_ids: Construct IDs to exclude from ranking

        Returns:
            Sorted list of recommendations (highest score first)
        """
        exclude_ids = exclude_ids or set()
        current_families: Set[str] = set()

        # Pass 1: compute raw recommendations
        recommendations = []
        for construct in constructs:
            if construct.construct_id in exclude_ids:
                continue

            rec = self.score_construct(construct, current_families)
            recommendations.append(rec)

            if construct.family:
                current_families.add(construct.family)

        # Pass 2: normalize non-WT scores to sum to ~100%
        # WT constructs are required on every plate and don't compete for priority
        total_raw = sum(r.total_score for r in recommendations if not r.is_wildtype)
        if total_raw > 0:
            for rec in recommendations:
                if rec.is_wildtype:
                    rec.total_score = 0.0
                    rec.brief_reason = "Required anchor (WT)"
                    rec.detailed_reason = (
                        "Wild-type construct is required on every plate as the "
                        "reference for fold-change calculations."
                    )
                else:
                    rec.total_score = (rec.total_score / total_raw) * 100.0
        else:
            # All non-WT have zero need — just zero out WT too
            for rec in recommendations:
                if rec.is_wildtype:
                    rec.total_score = 0.0
                    rec.brief_reason = "Required anchor (WT)"
                    rec.detailed_reason = (
                        "Wild-type construct is required on every plate as the "
                        "reference for fold-change calculations."
                    )

        # Sort: WT first (required), then by total score (descending)
        recommendations.sort(key=lambda r: (not r.is_wildtype, -r.total_score))

        return recommendations

    def get_required_anchors(
        self,
        selected_constructs: List[ConstructStats],
        all_constructs: List[ConstructStats],
    ) -> List[ConstructRecommendation]:
        """
        Get anchor constructs that must be added.

        Every experiment requires:
        1. Reporter-only (unregulated) construct
        2. WT for each family with selected mutants

        Args:
            selected_constructs: User-selected constructs
            all_constructs: All available constructs

        Returns:
            List of anchor constructs to auto-add
        """
        anchors = []
        selected_ids = {c.construct_id for c in selected_constructs}

        # Find unregulated construct
        unregulated = next(
            (c for c in all_constructs if c.is_unregulated),
            None
        )
        if unregulated and unregulated.construct_id not in selected_ids:
            rec = self.score_construct(unregulated, set())
            rec.brief_reason = "Required anchor (reporter-only)"
            anchors.append(rec)

        # Find families needing WT
        selected_families = {
            c.family for c in selected_constructs
            if c.family and not c.is_wildtype and not c.is_unregulated
        }

        for family in selected_families:
            # Check if WT already selected
            wt_selected = any(
                c.construct_id in selected_ids and c.is_wildtype and c.family == family
                for c in all_constructs
            )
            if wt_selected:
                continue

            # Find WT for this family
            wt = next(
                (c for c in all_constructs if c.is_wildtype and c.family == family),
                None
            )
            if wt:
                rec = self.score_construct(wt, set())
                rec.brief_reason = f"Required anchor (WT for {family})"
                anchors.append(rec)

        return anchors


def recommend_dfhbi_controls(
    recent_controls: List[Dict],
    typical_fmax: Optional[float],
    lookback_days: int = 14,
) -> DFHBIRecommendation:
    """
    Generate -DFHBI control recommendation based on history.

    Args:
        recent_controls: List of recent -DFHBI control results with 'signal' and 'date'
        typical_fmax: Typical F_max value for this project
        lookback_days: Number of days to look back (default 14)

    Returns:
        DFHBIRecommendation
    """
    if not recent_controls:
        return DFHBIRecommendation(
            include=True,
            confidence=RecommendationConfidence.REQUIRED,
            reason=(
                f"No -DFHBI controls found in the past {lookback_days} days. "
                "Including this control will establish baseline autofluorescence for your reaction components."
            ),
            recent_control_count=0,
            recent_mean_signal=None,
            typical_fmax=typical_fmax,
        )

    # Calculate mean signal
    signals = [c.get('signal', 0) for c in recent_controls]
    mean_signal = sum(signals) / len(signals) if signals else 0

    # Check against 5% threshold
    if typical_fmax and typical_fmax > 0:
        threshold = 0.05 * typical_fmax
        if mean_signal > threshold:
            return DFHBIRecommendation(
                include=True,
                confidence=RecommendationConfidence.RECOMMENDED,
                reason=(
                    f"Recent -DFHBI controls ({len(recent_controls)} in past {lookback_days} days) "
                    f"show elevated signal ({mean_signal:.0f} RFU), exceeding 5% of typical F_max ({threshold:.0f} RFU). "
                    "Consider including to monitor autofluorescence."
                ),
                recent_control_count=len(recent_controls),
                recent_mean_signal=mean_signal,
                typical_fmax=typical_fmax,
            )

    return DFHBIRecommendation(
        include=False,
        confidence=RecommendationConfidence.OPTIONAL,
        reason=(
            f"Your recent -DFHBI controls ({len(recent_controls)} in past {lookback_days} days) "
            f"show stable, low background ({mean_signal:.0f} RFU). "
            "You can safely skip this control for routine experiments."
        ),
        recent_control_count=len(recent_controls),
        recent_mean_signal=mean_signal,
        typical_fmax=typical_fmax,
    )


def check_template_limit(
    template_count: int,
) -> tuple[bool, Optional[str]]:
    """
    Check if template count exceeds limits.

    Args:
        template_count: Number of DNA templates

    Returns:
        Tuple of (exceeds_limit, warning_message)
    """
    if template_count <= MAX_TEMPLATES_RECOMMENDED:
        return (False, None)

    if template_count <= MAX_TEMPLATES_ABSOLUTE:
        return (
            False,
            f"{template_count} templates exceeds recommended maximum of {MAX_TEMPLATES_RECOMMENDED}. "
            f"Consider splitting into multiple experiments.",
        )

    return (
        True,
        f"{template_count} templates exceeds maximum of {MAX_TEMPLATES_ABSOLUTE}. "
        f"Split into multiple experiments.",
    )


def calculate_wells_needed(
    constructs: List[ConstructRecommendation],
    replicates: int,
    negative_template_count: int,
    negative_dye_count: int,
) -> int:
    """
    Calculate total wells needed for experiment.

    Args:
        constructs: Selected constructs
        replicates: Replicates per construct
        negative_template_count: -Template control wells
        negative_dye_count: -DFHBI control wells

    Returns:
        Total well count
    """
    construct_wells = len(constructs) * replicates
    control_wells = negative_template_count + negative_dye_count
    return construct_wells + control_wells


def check_capacity(
    wells_needed: int,
    plate_format: str = "96",
    is_checkerboard: bool = False,
) -> tuple[bool, int, Optional[str]]:
    """
    Check if wells fit on plate and suggest splits.

    Args:
        wells_needed: Total wells needed
        plate_format: "96" or "384"
        is_checkerboard: Whether using checkerboard pattern (384 only)

    Returns:
        Tuple of (exceeds_capacity, plates_needed, warning_message)
    """
    if plate_format == "384":
        max_wells = 192 if is_checkerboard else 384
    else:
        max_wells = 96

    if wells_needed <= max_wells:
        return (False, 1, None)

    plates_needed = (wells_needed + max_wells - 1) // max_wells

    return (
        True,
        plates_needed,
        f"Requires {wells_needed} wells (capacity: {max_wells}). "
        f"Consider splitting across {plates_needed} plates with same constructs "
        f"for improved precision.",
    )
