"""
Power Analysis Service - Service layer for power analysis and precision tracking.

Phase B Implementation: PRD Section 3.12

Provides:
- Precision dashboard for project overview
- Sample size recommendations based on comparison types
- Co-plating recommendations for improved precision
- Precision history tracking
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import func

from app.calculator.power_analysis import (
    HierarchicalSampleSizeResult,
    VarianceComponentsForPower,
    calculate_power_for_fold_change,
    calculate_precision_gap_score,
    calculate_sample_size_for_precision,
    calculate_tier_aware_sample_size,
    detect_tier_from_data_structure,
)
from app.extensions import db
from app.models import AnalysisVersion, Construct, FoldChange, Project
from app.models.comparison import PrecisionHistory
from app.models.enums import FoldChangeCategory
from app.models.experiment import ExperimentalSession, FitStatus, Plate, Well

logger = logging.getLogger(__name__)


class PowerAnalysisServiceError(Exception):
    """Raised when power analysis service operations fail."""
    pass


@dataclass
class ConstructPrecisionSummary:
    """
    Precision summary for a single construct.

    PRD Reference: F12.5 - Per-construct precision metrics
    """
    construct_id: int
    construct_name: str
    family: str
    is_wildtype: bool
    is_unregulated: bool
    replicate_count: int
    current_ci_width: float | None
    target_ci_width: float
    is_at_target: bool
    gap_score: float  # 0-100 score, higher = more improvement needed
    recommended_additional_n: int
    power_at_current_n: float | None


@dataclass
class PrecisionDashboard:
    """
    Project-wide precision dashboard.

    PRD Reference: Section 3.12 - Precision Dashboard
    """
    project_id: int
    project_name: str
    precision_target: float
    constructs_at_target: int
    constructs_total: int
    overall_progress: float  # Percentage of constructs at target
    construct_summaries: list[ConstructPrecisionSummary] = field(default_factory=list)
    critical_gaps: list[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CoplatingRecommendation:
    """
    Co-plating recommendation for improved precision.

    PRD Reference: F12.7, F12.8
    """
    construct_a_id: int
    construct_a_name: str
    construct_b_id: int
    construct_b_name: str
    current_comparison_type: str
    current_vif: float
    expected_vif_after: float
    expected_precision_improvement: float
    recommendation_text: str
    priority_score: float


# Variance Inflation Factors for different comparison types
VIF_FACTORS = {
    'direct': 1.0,
    'indirect_via_wt': 1.414,  # sqrt(2) for one-hop
    'indirect_via_unreg': 2.0,  # Two-hop through WT and unreg
    'two_hop': 2.0,
    'four_hop': 2.828,  # 2 * sqrt(2)
}


class PowerAnalysisService:
    """
    Service for power analysis and precision tracking.

    PRD Reference: Section 3.12
    Implements F12.1-F12.10 precision dashboard requirements.
    Supports tier-aware power analysis for adaptive model complexity.
    """

    @classmethod
    def detect_project_tier(cls, project_id: int) -> tuple[str, int, int]:
        """
        Detect the model tier from project data structure.

        Returns:
            Tuple of (tier_string, n_sessions, max_plates_per_session)
        """
        # Count sessions
        n_sessions = db.session.query(func.count(ExperimentalSession.id)).filter(
            ExperimentalSession.project_id == project_id
        ).scalar() or 0

        # Find max plates in any session
        max_plates = 0
        if n_sessions > 0:
            plates_per_session = db.session.query(
                func.count(Plate.id)
            ).join(
                ExperimentalSession, Plate.session_id == ExperimentalSession.id
            ).filter(
                ExperimentalSession.project_id == project_id
            ).group_by(
                ExperimentalSession.id
            ).all()

            if plates_per_session:
                max_plates = max(count for (count,) in plates_per_session)

        tier = detect_tier_from_data_structure(n_sessions, max_plates)
        return tier, n_sessions, max_plates

    @classmethod
    def get_project_variance_components(
        cls, project_id: int
    ) -> tuple[VarianceComponentsForPower, str]:
        """
        Get variance components from the latest analysis version.

        Returns:
            Tuple of (VarianceComponentsForPower, tier_string)
        """
        tier, n_sessions, max_plates = cls.detect_project_tier(project_id)

        # Try to get variance components from latest analysis
        latest_analysis = AnalysisVersion.query.filter_by(
            project_id=project_id
        ).order_by(AnalysisVersion.created_at.desc()).first()

        var_session = None
        var_plate = None
        var_residual = 0.09  # Default

        if latest_analysis:
            # Check for hierarchical analysis results
            try:
                from app.models.hierarchical import HierarchicalFoldChange

                # Get a sample hierarchical FC to extract variance components
                hfc = HierarchicalFoldChange.query.filter_by(
                    analysis_version_id=latest_analysis.id
                ).first()

                if hfc and hfc.variance_session is not None:
                    var_session = hfc.variance_session
                if hfc and hfc.variance_plate is not None:
                    var_plate = hfc.variance_plate
                if hfc and hfc.variance_residual is not None:
                    var_residual = hfc.variance_residual
            except Exception as e:
                logger.debug(f"Could not get variance components: {e}")

        components = VarianceComponentsForPower(
            var_session=var_session,
            var_plate=var_plate,
            var_residual=var_residual,
        )

        return components, tier

    @classmethod
    def get_tier_aware_sample_size_recommendation(
        cls,
        project_id: int,
        construct_id: int,
        target_ci_width: float = 0.3,
    ) -> HierarchicalSampleSizeResult:
        """
        Get tier-aware sample size recommendation for a construct.

        Args:
            project_id: Project ID
            construct_id: Construct ID
            target_ci_width: Target CI width

        Returns:
            HierarchicalSampleSizeResult with tier-appropriate recommendations
        """
        # Get tier and variance components
        variance_components, tier = cls.get_project_variance_components(project_id)
        tier_str, n_sessions, max_plates = cls.detect_project_tier(project_id)

        # Get current replicate count for construct
        replicate_count = cls._get_construct_replicate_count(construct_id, project_id)

        # Calculate tier-aware sample size
        result = calculate_tier_aware_sample_size(
            target_ci_width=target_ci_width,
            variance_components=variance_components,
            current_n_sessions=n_sessions,
            current_n_plates_per_session=max_plates or 1,
            current_n_replicates=replicate_count,
            tier=tier_str,
        )

        return result

    @classmethod
    def get_precision_dashboard(cls, project_id: int) -> PrecisionDashboard:
        """
        Get the precision dashboard for a project.

        PRD Reference: F12.1 - Precision Dashboard

        Args:
            project_id: Project ID

        Returns:
            PrecisionDashboard with construct summaries

        Raises:
            PowerAnalysisServiceError: If project not found
        """
        project = Project.query.get(project_id)
        if not project:
            raise PowerAnalysisServiceError(f"Project {project_id} not found")

        target = project.precision_target or 0.3

        # Get all constructs for project
        constructs = Construct.query.filter_by(
            project_id=project_id,
            is_deleted=False,
        ).all()

        construct_summaries = []
        at_target_count = 0
        critical_gaps = []

        for construct in constructs:
            summary = cls._get_construct_precision_summary(construct, target)
            construct_summaries.append(summary)

            if summary.is_at_target:
                at_target_count += 1
            elif summary.gap_score > 75:
                critical_gaps.append(
                    f"{construct.identifier}: CI width far from target "
                    f"(gap score: {summary.gap_score:.0f})"
                )

        total = len(constructs)
        progress = (at_target_count / total * 100) if total > 0 else 0.0

        return PrecisionDashboard(
            project_id=project_id,
            project_name=project.name,
            precision_target=target,
            constructs_at_target=at_target_count,
            constructs_total=total,
            overall_progress=progress,
            construct_summaries=construct_summaries,
            critical_gaps=critical_gaps[:5],  # Top 5 critical gaps
        )

    @classmethod
    def _get_construct_precision_summary(
        cls,
        construct: Construct,
        target_ci_width: float
    ) -> ConstructPrecisionSummary:
        """
        Get precision summary for a single construct.

        Args:
            construct: Construct model instance
            target_ci_width: Target CI width from project settings

        Returns:
            ConstructPrecisionSummary
        """
        # Get replicate count
        replicate_count = cls._get_construct_replicate_count(
            construct.id, construct.project_id
        )

        # Get current CI width from fold changes
        current_ci_width = cls._get_construct_ci_width(
            construct.id, construct.project_id
        )

        # Calculate gap score
        if current_ci_width is not None:
            gap_score = calculate_precision_gap_score(current_ci_width, target_ci_width)
            is_at_target = current_ci_width <= target_ci_width
        else:
            gap_score = 100.0 if replicate_count == 0 else 50.0
            is_at_target = False

        # Calculate recommended additional samples using tier-aware calculation
        # For Tier 1/2a, this represents sessions; for Tier 2b/3, plates
        recommended_n = 4  # Default
        try:
            tier_result = cls.get_tier_aware_sample_size_recommendation(
                construct.project_id, construct.id, target_ci_width
            )
            # Use sessions for Tier 1/2a, plates for Tier 2b/3
            if tier_result.tier in ("tier_1", "tier_2a"):
                recommended_n = tier_result.additional_sessions_needed
            else:
                recommended_n = tier_result.additional_plates_needed
        except Exception:
            # Fall back to simple calculation
            if current_ci_width is not None and replicate_count > 0:
                try:
                    result = calculate_sample_size_for_precision(
                        current_ci_width=current_ci_width,
                        current_n=replicate_count,
                        target_ci_width=target_ci_width,
                    )
                    recommended_n = result.additional_needed
                except Exception:
                    recommended_n = 4
            else:
                recommended_n = 4 if replicate_count == 0 else 2

        # Calculate power at current sample size
        power = None
        if replicate_count >= 2 and current_ci_width is not None:
            try:
                # Estimate sigma from CI width
                sigma = current_ci_width / (2 * 1.96)
                power = calculate_power_for_fold_change(
                    n=replicate_count,
                    effect_size=0.5,  # Moderate effect
                    sigma=sigma,
                )
            except Exception:
                pass

        return ConstructPrecisionSummary(
            construct_id=construct.id,
            construct_name=construct.identifier,
            family=construct.family or 'universal',
            is_wildtype=construct.is_wildtype,
            is_unregulated=construct.is_unregulated,
            replicate_count=replicate_count,
            current_ci_width=current_ci_width,
            target_ci_width=target_ci_width,
            is_at_target=is_at_target,
            gap_score=gap_score,
            recommended_additional_n=recommended_n,
            power_at_current_n=power,
        )

    @classmethod
    def _get_construct_replicate_count(
        cls,
        construct_id: int,
        project_id: int
    ) -> int:
        """Get the number of successful replicates for a construct."""
        count = db.session.query(func.count(Well.id)).join(
            Plate, Well.plate_id == Plate.id
        ).join(
            ExperimentalSession, Plate.session_id == ExperimentalSession.id
        ).filter(
            ExperimentalSession.project_id == project_id,
            Well.construct_id == construct_id,
            Well.fit_status == FitStatus.SUCCESS,
            Well.is_excluded == False,
        ).scalar()

        return count or 0

    @classmethod
    def _get_construct_ci_width(
        cls,
        construct_id: int,
        project_id: int
    ) -> float | None:
        """Get the average CI width from fold changes for a construct."""
        import scipy.stats as stats

        # Get fold change SEs for this construct
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
            return None

        ses = [fc.log_fc_fmax_se for fc in fold_changes if fc.log_fc_fmax_se is not None]
        if not ses:
            return None

        avg_se = sum(ses) / len(ses)
        n = len(ses)

        # CI width = 2 * t_crit * SE
        if n >= 2:
            t_crit = stats.t.ppf(0.975, df=n - 1)
            ci_width = 2 * t_crit * avg_se
        else:
            ci_width = 2 * 1.96 * avg_se

        return ci_width

    @classmethod
    def get_recommendation(
        cls,
        project_id: int,
        target: float = 0.3
    ) -> str:
        """
        Get a text recommendation for improving project precision.

        PRD Reference: F12.4 - Recommendations

        Args:
            project_id: Project ID
            target: Target CI width (default 0.3)

        Returns:
            Recommendation string

        Raises:
            PowerAnalysisServiceError: If project not found
        """
        project = Project.query.get(project_id)
        if not project:
            raise PowerAnalysisServiceError(f"Project {project_id} not found")

        dashboard = cls.get_precision_dashboard(project_id)

        if dashboard.constructs_total == 0:
            return "No constructs defined. Add constructs to begin precision tracking."

        if dashboard.overall_progress >= 100:
            return "All constructs have reached target precision. Project is ready for final analysis."

        # Find constructs needing most attention
        needs_attention = [
            s for s in dashboard.construct_summaries
            if not s.is_at_target
        ]

        if not needs_attention:
            return "All constructs at target precision."

        # Sort by gap score
        needs_attention.sort(key=lambda x: x.gap_score, reverse=True)
        top_priority = needs_attention[:3]

        # Detect tier for appropriate language
        tier, n_sessions, max_plates = cls.detect_project_tier(project_id)

        # Determine recommendation unit based on tier
        if tier in ("tier_1", "tier_2a"):
            # Single-plate-per-session workflow - recommend sessions
            unit = "sessions"
            header = "Priority constructs for additional sessions:"
        else:
            # Multi-plate workflow - may recommend plates
            unit = "plates/sessions"
            header = "Priority constructs for additional data:"

        # Build recommendation
        parts = [
            f"Precision progress: {dashboard.overall_progress:.0f}% "
            f"({dashboard.constructs_at_target}/{dashboard.constructs_total} constructs at target CI ≤ {target}).",
        ]

        # Add tier context
        tier_names = {
            "tier_1": "single session",
            "tier_2a": f"{n_sessions} sessions (single plate each)",
            "tier_2b": f"single session ({max_plates} plates)",
            "tier_3": f"{n_sessions} sessions with multi-plate design",
        }
        parts.append(f"Current structure: {tier_names.get(tier, tier)}")
        parts.append("")
        parts.append(header)

        for summary in top_priority:
            ci_str = f"CI={summary.current_ci_width:.2f}" if summary.current_ci_width else "no data"
            # Get tier-aware recommendation
            try:
                result = cls.get_tier_aware_sample_size_recommendation(
                    project_id, summary.construct_id, target
                )
                if tier in ("tier_1", "tier_2a"):
                    need_str = f"need +{result.additional_sessions_needed} {unit}"
                else:
                    need_str = f"need +{result.additional_plates_needed} plates"
            except Exception:
                need_str = f"need +{summary.recommended_additional_n} {unit}"

            parts.append(f"  - {summary.construct_name}: {ci_str}, {need_str}")

        return "\n".join(parts)

    @classmethod
    def adjust_sample_size_for_comparison_type(
        cls,
        base_n: int,
        comparison_type: str = 'direct',
        target_power: float = 0.8
    ) -> int:
        """
        Adjust sample size based on comparison type's variance inflation.

        PRD Reference: F12.6 - VIF adjustment

        Different comparison paths have different variance inflation factors:
        - direct: VIF = 1.0 (same plate)
        - indirect_via_wt: VIF = sqrt(2) ≈ 1.414 (one-hop through WT)
        - indirect_via_unreg: VIF = 2.0 (two-hop)
        - four_hop: VIF = 2*sqrt(2) ≈ 2.828

        Args:
            base_n: Base sample size for direct comparison
            comparison_type: Type of comparison path
            target_power: Target power level

        Returns:
            Adjusted sample size
        """
        vif = VIF_FACTORS.get(comparison_type, 1.0)

        # Sample size scales with VIF^2 to maintain same precision
        adjusted_n = int(base_n * (vif ** 2))

        return max(adjusted_n, base_n)

    @classmethod
    def get_coplating_recommendations(
        cls,
        project_id: int,
        max_recommendations: int = 10
    ) -> list[CoplatingRecommendation]:
        """
        Get co-plating recommendations for improved precision.

        PRD Reference: F12.7, F12.8

        Identifies mutant pairs that would benefit from being placed on
        the same plate to enable direct comparison.

        Args:
            project_id: Project ID
            max_recommendations: Maximum recommendations to return

        Returns:
            List of CoplatingRecommendation sorted by priority
        """
        # Import from SmartPlannerService which has existing implementation
        from app.services.smart_planner_service import SmartPlannerService

        try:
            analysis = SmartPlannerService.get_coplating_recommendations(
                project_id, max_recommendations
            )

            # Convert to our dataclass format
            recommendations = []
            for rec in analysis.recommendations:
                recommendations.append(CoplatingRecommendation(
                    construct_a_id=rec.construct_a_id,
                    construct_a_name=rec.construct_a_name,
                    construct_b_id=rec.construct_b_id,
                    construct_b_name=rec.construct_b_name,
                    current_comparison_type=rec.current_comparison_type,
                    current_vif=rec.current_vif,
                    expected_vif_after=rec.expected_vif_after,
                    expected_precision_improvement=rec.expected_precision_improvement,
                    recommendation_text=rec.recommendation_text,
                    priority_score=rec.priority_score,
                ))

            return recommendations

        except Exception as e:
            logger.warning(f"Failed to get coplating recommendations: {e}")
            return []

    @classmethod
    def track_precision_history(
        cls,
        project_id: int,
        construct_id: int | None = None
    ) -> list[PrecisionHistory]:
        """
        Get precision history for a project or specific construct.

        PRD Reference: Section 3.12 - Precision History Tracking

        Args:
            project_id: Project ID
            construct_id: Optional construct ID to filter

        Returns:
            List of PrecisionHistory records
        """
        query = db.session.query(PrecisionHistory).join(
            Construct, PrecisionHistory.construct_id == Construct.id
        ).filter(
            Construct.project_id == project_id
        )

        if construct_id:
            query = query.filter(PrecisionHistory.construct_id == construct_id)

        return query.order_by(
            PrecisionHistory.recorded_at.desc()
        ).all()

    @classmethod
    def record_precision_snapshot(
        cls,
        project_id: int,
        analysis_version_id: int
    ) -> list[PrecisionHistory]:
        """
        Record current precision state for all constructs.

        Creates PrecisionHistory records when CI width changes significantly
        or when plates are added.

        Args:
            project_id: Project ID
            analysis_version_id: Analysis version ID

        Returns:
            List of created PrecisionHistory records
        """
        project = Project.query.get(project_id)
        if not project:
            raise PowerAnalysisServiceError(f"Project {project_id} not found")

        constructs = Construct.query.filter_by(
            project_id=project_id,
            is_deleted=False,
        ).all()

        created_records = []

        for construct in constructs:
            # Get current precision metrics
            replicate_count = cls._get_construct_replicate_count(
                construct.id, project_id
            )
            ci_width = cls._get_construct_ci_width(
                construct.id, project_id
            )

            if ci_width is None:
                continue

            # Count plates with this construct
            plate_count = db.session.query(func.count(func.distinct(Plate.id))).join(
                Well, Well.plate_id == Plate.id
            ).join(
                ExperimentalSession, Plate.session_id == ExperimentalSession.id
            ).filter(
                ExperimentalSession.project_id == project_id,
                Well.construct_id == construct.id,
                Well.fit_status == FitStatus.SUCCESS,
            ).scalar() or 0

            # Determine comparison type based on construct type
            if construct.is_unregulated:
                comparison_type = 'unregulated_baseline'
                path_type = 'direct'
            elif construct.is_wildtype:
                comparison_type = FoldChangeCategory.WT_UNREGULATED
                path_type = 'direct'
            else:
                comparison_type = FoldChangeCategory.MUTANT_WT
                path_type = 'one_hop'

            # Check if we should record (>10% change or first record)
            latest = db.session.query(PrecisionHistory).filter_by(
                construct_id=construct.id
            ).order_by(
                PrecisionHistory.recorded_at.desc()
            ).first()

            should_record = False
            if latest is None:
                should_record = True
            elif latest.ci_width == 0:
                should_record = ci_width > 0
            elif abs(ci_width - latest.ci_width) / latest.ci_width > 0.1:
                should_record = True
            elif plate_count > latest.plate_count:
                should_record = True

            if should_record:
                record = PrecisionHistory(
                    construct_id=construct.id,
                    analysis_version_id=analysis_version_id,
                    ci_width=ci_width,
                    comparison_type=comparison_type,
                    path_type=path_type,
                    plate_count=plate_count,
                    replicate_count=replicate_count,
                )
                db.session.add(record)
                created_records.append(record)

        if created_records:
            db.session.commit()

        return created_records

    @classmethod
    def calculate_power_curve(
        cls,
        construct_id: int,
        project_id: int,
        effect_sizes: list[float] | None = None,
        max_n: int = 50
    ) -> dict[str, Any]:
        """
        Calculate power curve for a construct.

        Args:
            construct_id: Construct ID
            project_id: Project ID
            effect_sizes: List of effect sizes to calculate power for
            max_n: Maximum sample size to consider

        Returns:
            Dict with power curve data
        """
        if effect_sizes is None:
            effect_sizes = [0.2, 0.5, 0.8, 1.0, 1.5, 2.0]

        # Get current sigma from data
        ci_width = cls._get_construct_ci_width(construct_id, project_id)
        if ci_width is not None:
            sigma = ci_width / (2 * 1.96)
        else:
            sigma = 0.3  # Default estimate

        curves = {}
        sample_sizes = list(range(2, max_n + 1))

        for effect in effect_sizes:
            powers = []
            for n in sample_sizes:
                try:
                    power = calculate_power_for_fold_change(
                        n=n,
                        effect_size=effect,
                        sigma=sigma,
                    )
                    powers.append(power)
                except Exception:
                    powers.append(None)

            curves[f"effect_{effect}"] = powers

        return {
            'sample_sizes': sample_sizes,
            'effect_sizes': effect_sizes,
            'curves': curves,
            'sigma_used': sigma,
        }
