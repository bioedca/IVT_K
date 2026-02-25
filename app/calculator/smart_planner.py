"""Smart Experiment Planner for IVT reactions.

Provides intelligent experiment planning with:
- Construct recommendations based on precision needs
- First Experiment Wizard for new projects
- Auto-addition of anchor constructs
- Template limit enforcement
- Capacity management
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple
from enum import Enum
from datetime import datetime

from .constants import (
    MIN_REPLICATES,
    MAX_TEMPLATES_RECOMMENDED,
    MAX_TEMPLATES_ABSOLUTE,
    DEFAULT_PRECISION_TARGET,
    DEFAULT_NEGATIVE_TEMPLATE_REPLICATES,
    DEFAULT_NEGATIVE_DYE_REPLICATES,
    CHECKERBOARD_USABLE_WELLS_384,
    TARGET_EFFECT_PROBABILITY,
    PlateFormat,
)
from .recommendation import (
    RecommendationEngine,
    ConstructStats,
    ConstructRecommendation,
    DFHBIRecommendation,
    ExperimentPlan,
    recommend_dfhbi_controls,
    check_template_limit,
    calculate_wells_needed,
    check_capacity,
    RecommendationConfidence,
)
from .power_analysis import calculate_sample_size_for_precision


class PlannerMode(Enum):
    """Operating mode for the planner."""
    FIRST_EXPERIMENT = "first_experiment"  # New project, no data
    NORMAL = "normal"  # Project with existing data


@dataclass
class FirstExperimentSuggestion:
    """Suggestion for first experiment setup."""
    reporter_only: Optional[ConstructStats]
    wildtype: Optional[ConstructStats]
    negative_template_count: int
    negative_dye_count: int
    total_wells: int
    replicates_per_construct: int
    rationale: List[str]


@dataclass
class ImpactPreview:
    """Preview of experiment impact on project progress."""
    constructs_before: int
    constructs_after: int
    constructs_gained: int
    plates_to_target_before: int
    plates_to_target_after: int
    plates_saved: int
    precision_improvement_pct: float
    per_construct_impact: List[Dict]
    total_wells_needed: int = 0


@dataclass
class PlanValidation:
    """Validation result for an experiment plan."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class SmartPlanner:
    """
    Smart Experiment Planner for IVT reactions.

    Provides recommendations and planning assistance based on
    project data and precision targets.
    """

    def __init__(
        self,
        target_ci_width: float = DEFAULT_PRECISION_TARGET,
        plate_format: PlateFormat = PlateFormat.WELL_384,
    ):
        """
        Initialize Smart Planner.

        Args:
            target_ci_width: Target CI width for precision
            plate_format: Plate format (96 or 384-well)
        """
        self.target_ci_width = target_ci_width
        self.plate_format = plate_format
        self.recommendation_engine = RecommendationEngine(target_ci_width)

    def detect_mode(self, constructs: List[ConstructStats]) -> PlannerMode:
        """
        Detect whether this is a first experiment or normal planning.

        Args:
            constructs: Available constructs with stats

        Returns:
            PlannerMode
        """
        has_data = any(c.has_data for c in constructs)
        return PlannerMode.NORMAL if has_data else PlannerMode.FIRST_EXPERIMENT

    def generate_first_experiment_suggestion(
        self,
        constructs: List[ConstructStats],
        replicates: int = MIN_REPLICATES,
    ) -> FirstExperimentSuggestion:
        """
        Generate suggestion for first experiment.

        Strategy: Characterize WT before testing mutants.
        Includes reporter-only + WT + controls.

        Args:
            constructs: Available constructs
            replicates: Replicates per construct (default 4)

        Returns:
            FirstExperimentSuggestion
        """
        # Find reporter-only (unregulated)
        reporter_only = next(
            (c for c in constructs if c.is_unregulated),
            None
        )

        # Find first WT
        wildtype = next(
            (c for c in constructs if c.is_wildtype),
            None
        )

        # Calculate wells
        template_count = sum([
            1 if reporter_only else 0,
            1 if wildtype else 0,
        ])
        construct_wells = template_count * replicates
        control_wells = DEFAULT_NEGATIVE_TEMPLATE_REPLICATES + DEFAULT_NEGATIVE_DYE_REPLICATES
        total_wells = construct_wells + control_wells

        rationale = [
            "Establishes baseline fold change (WT vs reporter-only)",
            "Validates experimental setup and signal quality",
            "Provides reference for interpreting mutant effects",
            "Generates variance estimates for power analysis",
        ]

        return FirstExperimentSuggestion(
            reporter_only=reporter_only,
            wildtype=wildtype,
            negative_template_count=DEFAULT_NEGATIVE_TEMPLATE_REPLICATES,
            negative_dye_count=DEFAULT_NEGATIVE_DYE_REPLICATES,
            total_wells=total_wells,
            replicates_per_construct=replicates,
            rationale=rationale,
        )

    def get_recommendations(
        self,
        constructs: List[ConstructStats],
        max_recommendations: int = 10,
    ) -> List[ConstructRecommendation]:
        """
        Get ranked construct recommendations.

        Args:
            constructs: Available constructs with stats
            max_recommendations: Maximum number to return

        Returns:
            Sorted list of recommendations
        """
        # Exclude anchors from main recommendations (they're auto-added)
        non_anchors = [c for c in constructs if not c.is_unregulated]

        recommendations = self.recommendation_engine.rank_constructs(non_anchors)
        return recommendations[:max_recommendations]

    def create_experiment_plan(
        self,
        selected_constructs: List[ConstructStats],
        all_constructs: List[ConstructStats],
        replicates: int = MIN_REPLICATES,
        include_dfhbi: Optional[bool] = None,
        recent_dfhbi_controls: Optional[List[Dict]] = None,
        typical_fmax: Optional[float] = None,
    ) -> ExperimentPlan:
        """
        Create a complete experiment plan from selected constructs.

        Auto-adds required anchors and validates constraints.

        Args:
            selected_constructs: User-selected constructs
            all_constructs: All available constructs
            replicates: Replicates per construct
            include_dfhbi: Override for DFHBI inclusion (None = use recommendation)
            recent_dfhbi_controls: Recent DFHBI control data
            typical_fmax: Typical F_max for this project

        Returns:
            ExperimentPlan
        """
        # Get DFHBI recommendation
        dfhbi_rec = recommend_dfhbi_controls(
            recent_controls=recent_dfhbi_controls or [],
            typical_fmax=typical_fmax,
        )

        # Override if user specified
        if include_dfhbi is not None:
            dfhbi_rec.include = include_dfhbi

        negative_dye_count = DEFAULT_NEGATIVE_DYE_REPLICATES if dfhbi_rec.include else 0

        # Score selected constructs
        selected_recs = [
            self.recommendation_engine.score_construct(c, set())
            for c in selected_constructs
        ]

        # Get auto-added anchors
        auto_anchors = self.recommendation_engine.get_required_anchors(
            selected_constructs,
            all_constructs,
        )

        # Calculate totals
        all_constructs_in_plan = selected_recs + auto_anchors
        total_templates = len(all_constructs_in_plan)
        total_wells = calculate_wells_needed(
            all_constructs_in_plan,
            replicates,
            DEFAULT_NEGATIVE_TEMPLATE_REPLICATES,
            negative_dye_count,
        )

        # Check template limit
        template_exceeded, template_warning = check_template_limit(total_templates)

        # Check capacity
        if self.plate_format == PlateFormat.WELL_384:
            capacity_exceeded, plates_needed, capacity_warning = check_capacity(
                total_wells,
                plate_format="384",
                is_checkerboard=True,
            )
        else:
            capacity_exceeded, plates_needed, capacity_warning = check_capacity(
                total_wells,
                plate_format="96",
            )

        # Collect warnings
        warnings = []
        if template_warning:
            warnings.append(template_warning)
        if capacity_warning:
            warnings.append(capacity_warning)

        return ExperimentPlan(
            constructs=selected_recs,
            auto_added_anchors=auto_anchors,
            negative_template_count=DEFAULT_NEGATIVE_TEMPLATE_REPLICATES,
            negative_dye_count=negative_dye_count,
            dfhbi_recommendation=dfhbi_rec,
            total_wells=total_wells,
            total_templates=total_templates,
            template_limit_exceeded=template_exceeded,
            capacity_exceeded=capacity_exceeded,
            warnings=warnings,
        )

    def _estimate_plates_to_target(
        self,
        constructs: List[ConstructStats],
        selected_set: Optional[Set[int]] = None,
        additional_replicates: int = 0,
    ) -> int:
        """
        Estimate total plates needed for all constructs to reach targets.

        Counts plates needed across three categories:
        - Untested constructs: 1 plate each (need initial data)
        - Low prob_meaningful (< 95%): 1 plate each (need more evidence)
        - CI above target: sample-size-based calculation

        Args:
            constructs: All constructs in project
            selected_set: Construct IDs being tested this round (for projecting)
            additional_replicates: Replicates being added for selected constructs

        Returns:
            Estimated total plates to reach all targets
        """
        from .power_analysis import estimate_precision_improvement

        selected_set = selected_set or set()
        total_plates = 0

        for c in constructs:
            # Skip anchors (reporter-only) — they don't have independent targets
            if c.is_unregulated:
                continue

            # Project forward if this construct is being tested
            is_selected = c.construct_id in selected_set
            projected_ci = c.ci_width
            projected_n = c.replicate_count
            projected_has_data = c.has_data

            if is_selected:
                projected_has_data = True
                projected_n = c.replicate_count + additional_replicates
                if c.ci_width is not None:
                    projected_ci = estimate_precision_improvement(
                        c.ci_width, c.replicate_count, additional_replicates,
                    )

            if not projected_has_data:
                # Untested: needs at least 1 plate
                total_plates += 1
                continue

            plates_for_construct = 0

            # Check if prob_meaningful is below target
            if c.prob_meaningful is not None and c.prob_meaningful < TARGET_EFFECT_PROBABILITY:
                plates_for_construct = max(plates_for_construct, 1)

            # Check if CI is above target
            if projected_ci is not None and projected_ci > self.target_ci_width:
                result = calculate_sample_size_for_precision(
                    projected_ci, projected_n, self.target_ci_width,
                )
                ci_plates = (result.additional_needed + 3) // 4
                plates_for_construct = max(plates_for_construct, ci_plates)

            # No data on CI yet (just tested, no analysis) — count 1 plate
            if projected_ci is None and projected_has_data:
                plates_for_construct = max(plates_for_construct, 1)

            total_plates += plates_for_construct

        return total_plates

    def calculate_impact_preview(
        self,
        selected_constructs: List[ConstructStats],
        all_constructs: List[ConstructStats],
        additional_replicates: int = MIN_REPLICATES,
        negative_template_count: int = DEFAULT_NEGATIVE_TEMPLATE_REPLICATES,
        include_dfhbi: Optional[bool] = None,
    ) -> ImpactPreview:
        """
        Preview the impact of running this experiment.

        Shows how constructs tested and precision will change.

        Args:
            selected_constructs: Constructs to test
            all_constructs: All constructs in project
            additional_replicates: Replicates to add
            negative_template_count: Number of negative template controls
            include_dfhbi: Whether to include DFHBI controls

        Returns:
            ImpactPreview
        """
        # Count constructs with data before/after
        tested_before = sum(1 for c in all_constructs if c.has_data)
        newly_tested = sum(1 for c in selected_constructs if not c.has_data)
        tested_after = tested_before + newly_tested

        # Estimate precision improvement
        per_construct_impact = []
        total_improvement = 0.0

        for construct in selected_constructs:
            from .power_analysis import estimate_precision_improvement

            if construct.ci_width:
                new_ci = estimate_precision_improvement(
                    construct.ci_width,
                    construct.replicate_count,
                    additional_replicates,
                )
                improvement = (construct.ci_width - new_ci) / construct.ci_width * 100
                total_improvement += improvement

                per_construct_impact.append({
                    'name': construct.name,
                    'current_ci': construct.ci_width,
                    'projected_ci': new_ci,
                    'improvement_pct': improvement,
                })
            else:
                per_construct_impact.append({
                    'name': construct.name,
                    'current_ci': None,
                    'projected_ci': None,
                    'improvement_pct': None,
                    'note': 'New data point',
                })

        avg_improvement = total_improvement / len(selected_constructs) if selected_constructs else 0

        # Estimate plates to target using the new helper
        selected_ids = {c.construct_id for c in selected_constructs}
        plates_before = self._estimate_plates_to_target(all_constructs)
        plates_after = self._estimate_plates_to_target(
            all_constructs,
            selected_set=selected_ids,
            additional_replicates=additional_replicates,
        )

        # Calculate exact wells needed for the proposed plan
        plan = self.create_experiment_plan(
            selected_constructs=selected_constructs,
            all_constructs=all_constructs,
            replicates=additional_replicates,
            include_dfhbi=include_dfhbi,
        )

        total_wells_needed = calculate_wells_needed(
            plan.constructs + plan.auto_added_anchors,
            additional_replicates,
            negative_template_count,
            plan.negative_dye_count,
        )

        return ImpactPreview(
            constructs_before=tested_before,
            constructs_after=tested_after,
            constructs_gained=newly_tested,
            plates_to_target_before=plates_before,
            plates_to_target_after=plates_after,
            plates_saved=max(0, plates_before - plates_after),
            precision_improvement_pct=avg_improvement,
            per_construct_impact=per_construct_impact,
            total_wells_needed=total_wells_needed,
        )

    def validate_plan(
        self,
        plan: ExperimentPlan,
        require_unregulated: bool = True,
    ) -> PlanValidation:
        """
        Validate an experiment plan.

        Args:
            plan: Experiment plan to validate
            require_unregulated: Whether to require reporter-only construct

        Returns:
            PlanValidation result
        """
        errors = []
        warnings = []

        # Check for unregulated
        if require_unregulated:
            has_unregulated = any(
                c.is_anchor and 'reporter' in c.brief_reason.lower()
                for c in plan.auto_added_anchors + plan.constructs
            )
            if not has_unregulated:
                errors.append("Reporter-only (unregulated) construct is required")

        # Check template limit
        if plan.template_limit_exceeded:
            errors.append(
                f"Template count ({plan.total_templates}) exceeds maximum ({MAX_TEMPLATES_ABSOLUTE})"
            )

        # Check for WT per family
        families_with_mutants = set()
        families_with_wt = set()

        for c in plan.constructs + plan.auto_added_anchors:
            if c.family:
                if c.is_wildtype:
                    families_with_wt.add(c.family)
                elif not c.is_anchor and not c.is_unregulated:
                    # Only non-anchor, non-unregulated constructs are mutants needing WT
                    families_with_mutants.add(c.family)

        missing_wt = families_with_mutants - families_with_wt
        for family in missing_wt:
            errors.append(f"Family '{family}' has mutants but no wild-type")

        # Check minimum replicates (per PRD, minimum is 4)
        # This would be checked elsewhere, but add as warning if constructs have few replicates

        # Capacity warnings (not errors - can split)
        if plan.capacity_exceeded:
            warnings.append(
                f"Experiment requires {plan.total_wells} wells. "
                "Consider splitting across multiple plates."
            )

        # Add any plan warnings
        warnings.extend(plan.warnings)

        return PlanValidation(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def suggest_plate_split(
        self,
        plan: ExperimentPlan,
        replicates: int = MIN_REPLICATES,
    ) -> Tuple[ExperimentPlan, ExperimentPlan]:
        """
        Suggest splitting plan across two plates.

        Strategy: Same constructs on both plates to double replicates.

        Args:
            plan: Original experiment plan
            replicates: Replicates per construct per plate

        Returns:
            Tuple of two identical plans (to be run on separate plates)
        """
        # For simplicity, return the same plan twice
        # In practice, each plate would have the same constructs
        return (plan, plan)


def create_planner_for_project(
    plate_format: str,
    target_ci_width: float = DEFAULT_PRECISION_TARGET,
) -> SmartPlanner:
    """
    Create a SmartPlanner configured for a project.

    Args:
        plate_format: "96" or "384"
        target_ci_width: Target CI width

    Returns:
        Configured SmartPlanner
    """
    format_enum = PlateFormat.WELL_384 if plate_format == "384" else PlateFormat.WELL_96
    return SmartPlanner(
        target_ci_width=target_ci_width,
        plate_format=format_enum,
    )
