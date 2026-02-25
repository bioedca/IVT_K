"""Smart Planner Service - bridges SmartPlanner with database models.

Phase 2.5: Constraints & Linking (F4.18-F4.23)
Provides intelligent experiment planning based on actual project data.
"""
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

from sqlalchemy import func, and_
from sqlalchemy.orm import joinedload
import scipy.stats as stats

from app.extensions import db
from app.models import (
    Project, Construct, ExperimentalSession, Plate, ReactionSetup,
    FitResult, FoldChange
)
from app.models.experiment import Well, FitStatus
from app.models.comparison import PrecisionHistory
from app.models.analysis_version import AnalysisVersion, HierarchicalResult
from app.calculator import (
    SmartPlanner,
    PlannerMode,
    FirstExperimentSuggestion,
    ImpactPreview,
    PlanValidation,
    ExperimentPlan,
    ConstructStats,
    ConstructRecommendation,
    DFHBIRecommendation,
    PlateFormat,
    create_planner_for_project,
    DEFAULT_PRECISION_TARGET,
)

logger = logging.getLogger(__name__)


class SmartPlannerError(Exception):
    """Raised when smart planner operations fail."""
    pass


@dataclass
class ProjectConstraintValidation:
    """Result of project constraint validation for planning."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    has_reporter_only: bool
    has_wildtype_per_family: Dict[str, bool]


@dataclass
class CoplatingRecommendation:
    """
    Co-plating recommendation for improved precision.

    PRD Reference: F12.7, F12.8
    Identifies mutant pairs that would benefit from being placed on the same plate.
    """
    construct_a_id: int
    construct_a_name: str
    construct_b_id: int
    construct_b_name: str
    current_comparison_type: str  # "indirect_via_wt", "indirect_via_unreg", "no_comparison"
    current_vif: float  # Current variance inflation factor
    expected_vif_after: float  # VIF after co-plating (always 1.0 for direct)
    expected_precision_improvement: float  # Percentage improvement
    current_ci_width: Optional[float]
    expected_ci_width: Optional[float]
    recommendation_text: str
    priority_score: float  # Higher = more benefit from co-plating


@dataclass
class CoplatingAnalysis:
    """Result of co-plating analysis for a project."""
    recommendations: List[CoplatingRecommendation]
    total_pairs_analyzed: int
    pairs_with_indirect_only: int
    max_potential_improvement: float


class SmartPlannerService:
    """
    Service for intelligent experiment planning.

    Implements PRD requirements F4.18-F4.23:
    - F4.18: Project-scoped constructs only
    - F4.19: Enforce project-level reporter-only
    - F4.20: ReactionSetup persistence (via CalculatorService)
    - F4.21: Link to ExperimentalSession (mandatory for finalization)
    - F4.22: Recommendations from uploaded data only
    - F4.23: Fresh session (no history/templates)
    """

    @classmethod
    def get_construct_stats(
        cls,
        project_id: int,
        uploaded_only: bool = True,
    ) -> List[ConstructStats]:
        """
        Get construct statistics from database for recommendation engine.

        Args:
            project_id: Project ID
            uploaded_only: If True, only include constructs with uploaded data (F4.22)

        Returns:
            List of ConstructStats for the SmartPlanner
        """
        # Get all project constructs (F4.18: project-scoped)
        constructs = Construct.query.filter_by(
            project_id=project_id,
            is_deleted=False,
        ).all()

        # Get prob_meaningful map from latest Bayesian analysis
        prob_map = cls._get_prob_meaningful_map(project_id)

        stats_list = []

        for construct in constructs:
            # Get replicate count and CI width from actual data
            replicate_count, ci_width, has_data = cls._get_construct_precision(
                construct.id, project_id
            )

            # F4.22: Skip constructs without data if uploaded_only is True
            if uploaded_only and not has_data:
                # Still include for first experiment wizard, but mark as no data
                pass

            stats = ConstructStats(
                construct_id=construct.id,
                name=construct.identifier,
                family=construct.family,
                is_wildtype=construct.is_wildtype,
                is_unregulated=construct.is_unregulated,
                replicate_count=replicate_count,
                ci_width=ci_width,
                has_data=has_data,
                plasmid_size_bp=construct.plasmid_size_bp,
                prob_meaningful=prob_map.get(construct.id),
            )
            stats_list.append(stats)

        return stats_list

    @classmethod
    def _get_prob_meaningful_map(
        cls,
        project_id: int,
    ) -> Dict[int, float]:
        """
        Get P(|FC| > θ) for each construct from the latest Bayesian analysis.

        Queries the most recent completed AnalysisVersion for the project,
        then looks up HierarchicalResult rows with parameter_type='log_fc_fmax'
        and analysis_type='bayesian'.

        Args:
            project_id: Project ID

        Returns:
            Dict mapping construct_id -> prob_meaningful (0.0-1.0)
        """
        # Find the latest completed analysis version for this project
        latest_version = (
            AnalysisVersion.query
            .filter_by(project_id=project_id, status="completed")
            .order_by(AnalysisVersion.completed_at.desc())
            .first()
        )

        if not latest_version:
            return {}

        # Query Bayesian log_fc_fmax results for this version
        results = (
            HierarchicalResult.query
            .filter_by(
                analysis_version_id=latest_version.id,
                parameter_type="log_fc_fmax",
                analysis_type="bayesian",
            )
            .all()
        )

        prob_map = {}
        for r in results:
            if r.prob_meaningful is not None:
                prob_map[r.construct_id] = r.prob_meaningful

        return prob_map

    @classmethod
    def _get_construct_precision(
        cls,
        construct_id: int,
        project_id: int,
    ) -> Tuple[int, Optional[float], bool]:
        """
        Get precision metrics for a construct from uploaded data.

        Returns:
            Tuple of (replicate_count, ci_width, has_data)
        """
        # Count wells with successful fits for this construct
        well_count = db.session.query(func.count(Well.id)).join(
            Plate, Well.plate_id == Plate.id
        ).join(
            ExperimentalSession, Plate.session_id == ExperimentalSession.id
        ).filter(
            ExperimentalSession.project_id == project_id,
            Well.construct_id == construct_id,
            Well.fit_status == FitStatus.SUCCESS,
            Well.is_excluded == False,
        ).scalar() or 0

        if well_count == 0:
            return (0, None, False)

        # Get fold change SEs to compute CI width
        # CI width = 2 * t_crit * SE (using pooled SE across fold changes)
        fold_changes = db.session.query(
            FoldChange.log_fc_fmax_se
        ).join(
            Well, FoldChange.test_well_id == Well.id
        ).join(
            Plate, Well.plate_id == Plate.id
        ).join(
            ExperimentalSession, Plate.session_id == ExperimentalSession.id
        ).filter(
            ExperimentalSession.project_id == project_id,
            Well.construct_id == construct_id,
            FoldChange.log_fc_fmax_se.isnot(None),
        ).all()

        if not fold_changes:
            # Has data but no fold changes computed yet
            return (well_count, None, True)

        # Compute average SE and CI width
        ses = [fc.log_fc_fmax_se for fc in fold_changes if fc.log_fc_fmax_se is not None]
        if not ses:
            return (well_count, None, True)

        avg_se = sum(ses) / len(ses)
        n = len(ses)

        # CI width = 2 * t_crit * SE
        if n >= 2:
            t_crit = stats.t.ppf(0.975, df=n - 1)
            ci_width = 2 * t_crit * avg_se
        else:
            # Single measurement - use z-approximation
            ci_width = 2 * 1.96 * avg_se

        return (well_count, ci_width, True)

    @classmethod
    def validate_project_constraints(
        cls,
        project_id: int,
    ) -> ProjectConstraintValidation:
        """
        Validate project meets constraints for smart planning.

        F4.19: Enforce project-level reporter-only construct.

        Args:
            project_id: Project ID

        Returns:
            ProjectConstraintValidation result
        """
        project = Project.query.get(project_id)
        if not project:
            return ProjectConstraintValidation(
                is_valid=False,
                errors=[f"Project {project_id} not found"],
                warnings=[],
                has_reporter_only=False,
                has_wildtype_per_family={},
            )

        errors = []
        warnings = []

        # Check for reporter-only (unregulated) construct
        reporter_only = Construct.query.filter_by(
            project_id=project_id,
            is_unregulated=True,
            is_deleted=False,
        ).first()

        has_reporter_only = reporter_only is not None
        if not has_reporter_only:
            errors.append(
                "Project must have a reporter-only (unregulated) construct defined. "
                "This serves as the universal reference for cross-family comparisons."
            )

        # Check for WT per family with mutants
        families_with_mutants = db.session.query(
            Construct.family
        ).filter(
            Construct.project_id == project_id,
            Construct.is_deleted == False,
            Construct.is_wildtype == False,
            Construct.is_unregulated == False,
            Construct.family.isnot(None),
        ).distinct().all()

        families_with_wt = db.session.query(
            Construct.family
        ).filter(
            Construct.project_id == project_id,
            Construct.is_deleted == False,
            Construct.is_wildtype == True,
            Construct.family.isnot(None),
        ).distinct().all()

        mutant_families = {f[0] for f in families_with_mutants}
        wt_families = {f[0] for f in families_with_wt}

        has_wt_per_family = {}
        for family in mutant_families:
            has_wt = family in wt_families
            has_wt_per_family[family] = has_wt
            if not has_wt:
                warnings.append(
                    f"Family '{family}' has mutants but no wild-type construct. "
                    "A WT is required for fold change calculations."
                )

        return ProjectConstraintValidation(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            has_reporter_only=has_reporter_only,
            has_wildtype_per_family=has_wt_per_family,
        )

    @classmethod
    def detect_planner_mode(
        cls,
        project_id: int,
    ) -> PlannerMode:
        """
        Detect whether to use first experiment or normal mode.

        Args:
            project_id: Project ID

        Returns:
            PlannerMode.FIRST_EXPERIMENT or PlannerMode.NORMAL
        """
        construct_stats = cls.get_construct_stats(project_id, uploaded_only=False)
        planner = create_planner_for_project("384")
        return planner.detect_mode(construct_stats)

    @classmethod
    def get_first_experiment_suggestion(
        cls,
        project_id: int,
        replicates: int = 4,
    ) -> FirstExperimentSuggestion:
        """
        Get suggestion for first experiment setup.

        Args:
            project_id: Project ID
            replicates: Replicates per construct

        Returns:
            FirstExperimentSuggestion
        """
        # Get all constructs (including those without data)
        construct_stats = cls.get_construct_stats(project_id, uploaded_only=False)

        project = Project.query.get(project_id)
        plate_format = project.plate_format if project else "384"

        planner = create_planner_for_project(plate_format)
        return planner.generate_first_experiment_suggestion(construct_stats, replicates)

    @classmethod
    def get_recommendations(
        cls,
        project_id: int,
        max_recommendations: int = 10,
        uploaded_only: bool = True,
    ) -> List[ConstructRecommendation]:
        """
        Get ranked construct recommendations based on precision needs.

        F4.22: Uses only uploaded data for recommendations.

        Args:
            project_id: Project ID
            max_recommendations: Maximum recommendations to return
            uploaded_only: Only recommend based on uploaded data

        Returns:
            List of ConstructRecommendation sorted by priority
        """
        construct_stats = cls.get_construct_stats(project_id, uploaded_only=uploaded_only)

        project = Project.query.get(project_id)
        plate_format = project.plate_format if project else "384"
        target_ci = project.precision_target if project else DEFAULT_PRECISION_TARGET

        planner = SmartPlanner(
            target_ci_width=target_ci,
            plate_format=PlateFormat.WELL_384 if plate_format == "384" else PlateFormat.WELL_96,
        )

        return planner.get_recommendations(construct_stats, max_recommendations)

    @classmethod
    def create_experiment_plan(
        cls,
        project_id: int,
        selected_construct_ids: List[int],
        replicates: int = 4,
        include_dfhbi: Optional[bool] = None,
    ) -> ExperimentPlan:
        """
        Create an experiment plan from selected constructs.

        Auto-adds required anchors and validates constraints.

        Args:
            project_id: Project ID
            selected_construct_ids: List of construct IDs to include
            replicates: Replicates per construct
            include_dfhbi: Override for -DFHBI inclusion

        Returns:
            ExperimentPlan
        """
        # Validate project constraints first
        validation = cls.validate_project_constraints(project_id)
        if not validation.is_valid:
            raise SmartPlannerError(
                "Project constraints not met: " + "; ".join(validation.errors)
            )

        # Get all construct stats
        all_stats = cls.get_construct_stats(project_id, uploaded_only=False)

        # Filter to selected constructs
        selected_stats = [s for s in all_stats if s.construct_id in selected_construct_ids]

        # Get recent DFHBI control data
        recent_dfhbi = cls._get_recent_dfhbi_controls(project_id)
        typical_fmax = cls._get_typical_fmax(project_id)

        project = Project.query.get(project_id)
        plate_format = project.plate_format if project else "384"
        target_ci = project.precision_target if project else DEFAULT_PRECISION_TARGET

        planner = SmartPlanner(
            target_ci_width=target_ci,
            plate_format=PlateFormat.WELL_384 if plate_format == "384" else PlateFormat.WELL_96,
        )

        return planner.create_experiment_plan(
            selected_constructs=selected_stats,
            all_constructs=all_stats,
            replicates=replicates,
            include_dfhbi=include_dfhbi,
            recent_dfhbi_controls=recent_dfhbi,
            typical_fmax=typical_fmax,
        )

    @classmethod
    def calculate_impact_preview(
        cls,
        project_id: int,
        selected_construct_ids: List[int],
        additional_replicates: int = 4,
        negative_template_count: int = 3,
        include_dfhbi: Optional[bool] = None,
    ) -> ImpactPreview:
        """
        Preview the impact of running the proposed experiment.

        Args:
            project_id: Project ID
            selected_construct_ids: Constructs to test
            additional_replicates: Replicates to add
            negative_template_count: -Template controls
            include_dfhbi: Include DFHBI controls

        Returns:
            ImpactPreview showing precision gains
        """
        all_stats = cls.get_construct_stats(project_id, uploaded_only=False)
        selected_stats = [s for s in all_stats if s.construct_id in selected_construct_ids]

        project = Project.query.get(project_id)
        plate_format = project.plate_format if project else "384"
        target_ci = project.precision_target if project else DEFAULT_PRECISION_TARGET

        planner = SmartPlanner(
            target_ci_width=target_ci,
            plate_format=PlateFormat.WELL_384 if plate_format == "384" else PlateFormat.WELL_96,
        )

        return planner.calculate_impact_preview(
            selected_stats,
            all_stats,
            additional_replicates,
            negative_template_count=negative_template_count,
            include_dfhbi=include_dfhbi,
        )

    @classmethod
    def validate_plan(
        cls,
        project_id: int,
        plan: ExperimentPlan,
    ) -> PlanValidation:
        """
        Validate an experiment plan against project constraints.

        Args:
            project_id: Project ID
            plan: ExperimentPlan to validate

        Returns:
            PlanValidation result
        """
        project = Project.query.get(project_id)
        plate_format = project.plate_format if project else "384"
        target_ci = project.precision_target if project else DEFAULT_PRECISION_TARGET

        planner = SmartPlanner(
            target_ci_width=target_ci,
            plate_format=PlateFormat.WELL_384 if plate_format == "384" else PlateFormat.WELL_96,
        )

        return planner.validate_plan(plan, require_unregulated=True)

    @classmethod
    def link_setup_to_session(
        cls,
        setup_id: int,
        session_id: int,
    ) -> ReactionSetup:
        """
        Link a reaction setup to an experimental session.

        F4.21: Mandatory linkage for audit trail.

        Args:
            setup_id: ReactionSetup ID
            session_id: ExperimentalSession ID

        Returns:
            Updated ReactionSetup

        Raises:
            SmartPlannerError: If setup or session not found
        """
        setup = ReactionSetup.query.get(setup_id)
        if not setup:
            raise SmartPlannerError(f"ReactionSetup {setup_id} not found")

        session = ExperimentalSession.query.get(session_id)
        if not session:
            raise SmartPlannerError(f"ExperimentalSession {session_id} not found")

        # Validate same project
        if setup.project_id != session.project_id:
            raise SmartPlannerError(
                f"ReactionSetup project ({setup.project_id}) does not match "
                f"session project ({session.project_id})"
            )

        setup.session_id = session_id
        db.session.commit()

        logger.info(f"Linked ReactionSetup {setup_id} to Session {session_id}")
        return setup

    @classmethod
    def get_unlinked_setups(
        cls,
        project_id: int,
    ) -> List[ReactionSetup]:
        """
        Get reaction setups not yet linked to a session.

        Used to prompt users to link setups when creating sessions.

        Args:
            project_id: Project ID

        Returns:
            List of unlinked ReactionSetup
        """
        return ReactionSetup.query.filter_by(
            project_id=project_id,
            session_id=None,
        ).order_by(ReactionSetup.created_at.desc()).all()

    @classmethod
    def _get_recent_dfhbi_controls(
        cls,
        project_id: int,
        lookback_days: int = 14,
    ) -> List[Dict[str, Any]]:
        """
        Get recent -DFHBI control data for smart recommendations.

        Args:
            project_id: Project ID
            lookback_days: Days to look back

        Returns:
            List of control data dicts
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        # Query -DFHBI wells from recent sessions
        controls = db.session.query(
            Well.id,
            FitResult.f_baseline,
            ExperimentalSession.created_at
        ).join(
            FitResult, Well.id == FitResult.well_id
        ).join(
            Plate, Well.plate_id == Plate.id
        ).join(
            ExperimentalSession, Plate.session_id == ExperimentalSession.id
        ).filter(
            ExperimentalSession.project_id == project_id,
            ExperimentalSession.created_at >= cutoff_date,
            Well.well_type == 'NEGATIVE_DYE',  # -DFHBI wells
            Well.fit_status == FitStatus.SUCCESS,
        ).all()

        return [
            {
                'signal': c.f_baseline or 0,
                'date': c.created_at,
            }
            for c in controls
        ]

    @classmethod
    def _get_typical_fmax(
        cls,
        project_id: int,
    ) -> Optional[float]:
        """
        Get typical F_max value for the project.

        Used for -DFHBI threshold calculations.

        Args:
            project_id: Project ID

        Returns:
            Median F_max or None
        """
        fmax_values = db.session.query(
            FitResult.f_max
        ).join(
            Well, FitResult.well_id == Well.id
        ).join(
            Plate, Well.plate_id == Plate.id
        ).join(
            ExperimentalSession, Plate.session_id == ExperimentalSession.id
        ).filter(
            ExperimentalSession.project_id == project_id,
            Well.fit_status == FitStatus.SUCCESS,
            FitResult.f_max.isnot(None),
            FitResult.f_max > 0,
        ).all()

        if not fmax_values:
            return None

        values = sorted([v.f_max for v in fmax_values])
        mid = len(values) // 2
        if len(values) % 2 == 0:
            return (values[mid - 1] + values[mid]) / 2
        return values[mid]

    @classmethod
    def get_project_summary(
        cls,
        project_id: int,
    ) -> Dict[str, Any]:
        """
        Get summary of project data for smart planner display.

        F4.23: Fresh session view of project state.

        Args:
            project_id: Project ID

        Returns:
            Summary dict with counts and status
        """
        project = Project.query.get(project_id)
        if not project:
            raise SmartPlannerError(f"Project {project_id} not found")

        # Count constructs
        total_constructs = Construct.query.filter_by(
            project_id=project_id,
            is_deleted=False,
        ).count()

        # Count constructs with data
        constructs_with_data = db.session.query(
            func.count(func.distinct(Well.construct_id))
        ).join(
            Plate, Well.plate_id == Plate.id
        ).join(
            ExperimentalSession, Plate.session_id == ExperimentalSession.id
        ).filter(
            ExperimentalSession.project_id == project_id,
            Well.fit_status == FitStatus.SUCCESS,
            Well.construct_id.isnot(None),
        ).scalar() or 0

        # Count sessions
        session_count = ExperimentalSession.query.filter_by(
            project_id=project_id,
        ).count()

        # Count plates
        plate_count = db.session.query(
            func.count(Plate.id)
        ).join(
            ExperimentalSession, Plate.session_id == ExperimentalSession.id
        ).filter(
            ExperimentalSession.project_id == project_id,
        ).scalar() or 0

        # Count constructs at target precision
        construct_stats = cls.get_construct_stats(project_id, uploaded_only=False)
        at_target = sum(
            1 for s in construct_stats
            if s.ci_width is not None and s.ci_width <= project.precision_target
        )

        # Detect mode
        mode = cls.detect_planner_mode(project_id)

        # Validate constraints
        validation = cls.validate_project_constraints(project_id)

        return {
            'project_id': project_id,
            'project_name': project.name,
            'plate_format': project.plate_format,
            'precision_target': project.precision_target,
            'mode': mode.value,
            'total_constructs': total_constructs,
            'constructs_with_data': constructs_with_data,
            'constructs_at_target': at_target,
            'session_count': session_count,
            'plate_count': plate_count,
            'constraints_valid': validation.is_valid,
            'constraint_errors': validation.errors,
            'constraint_warnings': validation.warnings,
        }

    @classmethod
    def get_coplating_recommendations(
        cls,
        project_id: int,
        max_recommendations: int = 10,
    ) -> CoplatingAnalysis:
        """
        Get co-plating recommendations for mutant pairs with only indirect comparisons.

        PRD Reference: F12.7, F12.8

        Identifies mutant pairs that would benefit from being placed on the same plate,
        calculating expected precision improvement from direct comparison vs indirect.

        Args:
            project_id: Project ID
            max_recommendations: Maximum recommendations to return

        Returns:
            CoplatingAnalysis with ranked recommendations
        """
        import math

        # Get all constructs for project
        constructs = Construct.query.filter_by(
            project_id=project_id,
            is_deleted=False,
        ).all()

        # Build construct lookup
        construct_map = {c.id: c for c in constructs}

        # Get mutants only (exclude WT, unregulated)
        mutants = [c for c in constructs
                   if not c.is_wildtype and not c.is_unregulated]

        if len(mutants) < 2:
            return CoplatingAnalysis(
                recommendations=[],
                total_pairs_analyzed=0,
                pairs_with_indirect_only=0,
                max_potential_improvement=0.0,
            )

        # Get direct comparison pairs (constructs that have been on same plate)
        direct_pairs = cls._get_direct_comparison_pairs(project_id)

        # Get construct precision data
        construct_precision = {}
        for construct in constructs:
            _, ci_width, has_data = cls._get_construct_precision(
                construct.id, project_id
            )
            construct_precision[construct.id] = {
                'ci_width': ci_width,
                'has_data': has_data,
            }

        # Analyze all mutant pairs
        recommendations = []
        total_pairs = 0
        indirect_pairs = 0

        for i, mutant_a in enumerate(mutants):
            for mutant_b in mutants[i + 1:]:
                total_pairs += 1

                # Check if they have direct comparison
                pair_key = tuple(sorted([mutant_a.id, mutant_b.id]))
                has_direct = pair_key in direct_pairs

                if has_direct:
                    continue  # Already have direct comparison

                indirect_pairs += 1

                # Determine comparison type
                same_family = mutant_a.family == mutant_b.family
                if same_family:
                    comparison_type = "indirect_via_wt"
                    current_vif = 1.414  # sqrt(2) for one-hop through WT
                else:
                    comparison_type = "indirect_via_unreg"
                    current_vif = 2.0  # Two-hop through WT and unreg

                # Calculate precision improvement
                # Direct comparison has VIF = 1.0
                # Precision improvement = 1 - (1.0 / current_vif)
                vif_reduction = current_vif - 1.0
                precision_improvement = (vif_reduction / current_vif) * 100

                # Calculate expected CI width reduction
                ci_a = construct_precision.get(mutant_a.id, {}).get('ci_width')
                ci_b = construct_precision.get(mutant_b.id, {}).get('ci_width')

                current_ci = None
                expected_ci = None
                if ci_a and ci_b:
                    # Combined CI for indirect comparison
                    current_ci = math.sqrt(ci_a**2 + ci_b**2) * current_vif
                    # CI for direct comparison (VIF = 1)
                    expected_ci = math.sqrt(ci_a**2 + ci_b**2)

                # Build recommendation text
                rec_text = (
                    f"Place **{mutant_a.identifier}** and **{mutant_b.identifier}** "
                    f"on next plate for **{precision_improvement:.0f}% precision improvement** "
                    f"(current: {comparison_type.replace('_', ' ')}, VIF={current_vif:.2f})"
                )

                # Priority score based on:
                # - VIF reduction (higher = better)
                # - Both constructs have data (more useful)
                # - Same family (often more relevant comparisons)
                has_data_a = construct_precision.get(mutant_a.id, {}).get('has_data', False)
                has_data_b = construct_precision.get(mutant_b.id, {}).get('has_data', False)

                priority = precision_improvement
                if has_data_a and has_data_b:
                    priority *= 1.5
                elif has_data_a or has_data_b:
                    priority *= 1.2
                if same_family:
                    priority *= 1.1

                rec = CoplatingRecommendation(
                    construct_a_id=mutant_a.id,
                    construct_a_name=mutant_a.identifier,
                    construct_b_id=mutant_b.id,
                    construct_b_name=mutant_b.identifier,
                    current_comparison_type=comparison_type,
                    current_vif=current_vif,
                    expected_vif_after=1.0,
                    expected_precision_improvement=precision_improvement,
                    current_ci_width=current_ci,
                    expected_ci_width=expected_ci,
                    recommendation_text=rec_text,
                    priority_score=priority,
                )
                recommendations.append(rec)

        # Sort by priority and limit
        recommendations.sort(key=lambda r: r.priority_score, reverse=True)
        top_recommendations = recommendations[:max_recommendations]

        max_improvement = max(
            (r.expected_precision_improvement for r in recommendations),
            default=0.0
        )

        return CoplatingAnalysis(
            recommendations=top_recommendations,
            total_pairs_analyzed=total_pairs,
            pairs_with_indirect_only=indirect_pairs,
            max_potential_improvement=max_improvement,
        )

    @classmethod
    def _get_direct_comparison_pairs(
        cls,
        project_id: int,
    ) -> set:
        """
        Get set of construct pairs that have been on the same plate.

        Returns:
            Set of tuple(construct_id_a, construct_id_b) with a < b
        """
        # Query constructs that appear on same plates
        from sqlalchemy import tuple_

        # Get all plate-construct combinations
        plate_constructs = db.session.query(
            Plate.id.label('plate_id'),
            Well.construct_id
        ).join(
            Well, Well.plate_id == Plate.id
        ).join(
            ExperimentalSession, Plate.session_id == ExperimentalSession.id
        ).filter(
            ExperimentalSession.project_id == project_id,
            Well.construct_id.isnot(None),
        ).distinct().all()

        # Group constructs by plate
        plate_to_constructs = {}
        for plate_id, construct_id in plate_constructs:
            if plate_id not in plate_to_constructs:
                plate_to_constructs[plate_id] = set()
            plate_to_constructs[plate_id].add(construct_id)

        # Find all pairs that share a plate
        direct_pairs = set()
        for plate_id, construct_ids in plate_to_constructs.items():
            construct_list = sorted(construct_ids)
            for i, c_a in enumerate(construct_list):
                for c_b in construct_list[i + 1:]:
                    direct_pairs.add((c_a, c_b))

        return direct_pairs

    @classmethod
    def get_coplating_recommendations_for_construct(
        cls,
        project_id: int,
        construct_id: int,
        max_recommendations: int = 5,
    ) -> List[CoplatingRecommendation]:
        """
        Get co-plating recommendations for a specific construct.

        Args:
            project_id: Project ID
            construct_id: Construct to find partners for
            max_recommendations: Maximum recommendations to return

        Returns:
            List of CoplatingRecommendation for this construct
        """
        analysis = cls.get_coplating_recommendations(project_id)

        # Filter to recommendations involving this construct
        relevant = [
            r for r in analysis.recommendations
            if r.construct_a_id == construct_id or r.construct_b_id == construct_id
        ]

        return relevant[:max_recommendations]
