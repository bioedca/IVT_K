"""
Statistics Service - Service layer for statistical analysis operations.

Phase B Implementation: PRD Section 1.2

Provides:
- Fold change computation for project wells
- Assumption checking (normality, homoscedasticity)
- Multiple comparison corrections
"""
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import numpy as np

from sqlalchemy import and_

from app.extensions import db
from app.models import Project, Construct, FoldChange, AnalysisVersion
from app.models.fit_result import FitResult
from app.models.experiment import Well, Plate, ExperimentalSession, FitStatus
from app.analysis.statistical_tests import (
    shapiro_wilk_test,
    levene_test,
    breusch_pagan_test,
    run_assumption_diagnostics,
    bonferroni_correction,
    benjamini_hochberg_correction,
    apply_multiple_comparison_correction as apply_correction,
    NormalityTestResult,
    HomoscedasticityTestResult,
    AssumptionDiagnostics,
    MultipleComparisonResult,
)


logger = logging.getLogger(__name__)


class StatisticsServiceError(Exception):
    """Raised when statistics service operations fail."""
    pass


@dataclass
class AssumptionCheckResult:
    """
    Result of assumption checks for statistical analysis.

    Contains normality and homoscedasticity test results along with
    recommendations for handling violations.
    """
    normality_passed: bool
    homoscedasticity_passed: bool
    diagnostics: Optional[AssumptionDiagnostics]
    recommendations: List[str] = field(default_factory=list)
    residuals_count: int = 0
    groups_checked: int = 0

    @property
    def all_passed(self) -> bool:
        """Check if all assumption tests passed."""
        return self.normality_passed and self.homoscedasticity_passed


@dataclass
class FoldChangeComputeResult:
    """Result of fold change computation."""
    computed_count: int
    skipped_count: int
    error_count: int
    fold_changes: List[FoldChange] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)


class StatisticsService:
    """
    Service layer for statistical analysis operations.

    PRD Reference: Section 1.2
    Wraps statistical analysis functions for use with database models.
    """

    @classmethod
    def compute_fold_changes(
        cls,
        project_id: int,
        overwrite: bool = False
    ) -> List[FoldChange]:
        """
        Compute fold changes for all wells in a project.

        PRD Reference: F6.1-F6.3 - Fold change computation

        This method identifies wells that need fold change computation
        and delegates to the comparison service.

        Args:
            project_id: Project ID
            overwrite: If True, recompute existing fold changes

        Returns:
            List of FoldChange records (new or updated)

        Raises:
            StatisticsServiceError: If project not found
        """
        project = Project.query.get(project_id)
        if not project:
            raise StatisticsServiceError(f"Project {project_id} not found")

        # Use the comparison service for fold change computation
        from app.services.comparison_service import ComparisonService

        fold_changes = []

        # Get all plates for the project
        plates = db.session.query(Plate).join(
            ExperimentalSession, Plate.session_id == ExperimentalSession.id
        ).filter(
            ExperimentalSession.project_id == project_id
        ).all()

        for plate in plates:
            try:
                plate_fcs = ComparisonService.compute_plate_fold_changes(
                    plate.id, overwrite=overwrite
                )
                fold_changes.extend(plate_fcs)
            except Exception as e:
                logger.warning(f"Failed to compute fold changes for plate {plate.id}: {e}")

        return fold_changes

    @classmethod
    def run_assumption_checks(
        cls,
        analysis_version_id: int,
        alpha: float = 0.05,
        family: Optional[str] = None,
    ) -> AssumptionCheckResult:
        """
        Run normality and homoscedasticity checks for an analysis version.

        PRD Reference: T8.15-T8.17 - Statistical assumption diagnostics

        Args:
            analysis_version_id: AnalysisVersion ID
            alpha: Significance level for tests
            family: If provided, scope checks to this construct family.
                    If None, run pooled checks across all families.

        Returns:
            AssumptionCheckResult with test results and recommendations

        Raises:
            StatisticsServiceError: If analysis version not found
        """
        version = AnalysisVersion.query.get(analysis_version_id)
        if not version:
            raise StatisticsServiceError(
                f"AnalysisVersion {analysis_version_id} not found"
            )

        # Prefer stored model residuals (observed - predicted) when available
        model_resids = cls._get_model_residuals(version, family=family)
        has_model_residuals = model_resids is not None and len(model_resids) >= 3

        if has_model_residuals:
            residuals = model_resids
        else:
            # Fallback: raw log fold changes (filtered by family if set)
            residuals = cls._get_log_fold_changes(version.project_id, family=family)

        if len(residuals) < 3:
            return AssumptionCheckResult(
                normality_passed=True,  # Can't reject with insufficient data
                homoscedasticity_passed=True,
                diagnostics=None,
                recommendations=['insufficient_data'],
                residuals_count=len(residuals),
                groups_checked=0,
            )

        # Run normality test
        # With model residuals: pooled Shapiro-Wilk is correct (they should be i.i.d.)
        # Without: test within each construct group and combine via min p-value
        try:
            if has_model_residuals:
                normality_result = shapiro_wilk_test(residuals, alpha=alpha)
                normality_passed = normality_result.is_normal
            else:
                normality_result, normality_passed = cls._within_group_normality(
                    version.project_id, alpha=alpha
                )
        except Exception as e:
            logger.warning(f"Normality test failed: {e}")
            normality_passed = True
            normality_result = None

        # Get grouped residuals for homoscedasticity test
        groups = cls._get_grouped_residuals(version.project_id, family=family)
        groups_checked = len(groups)

        if len(groups) >= 2:
            try:
                homoscedasticity_result = levene_test(*groups, alpha=alpha)
                homoscedasticity_passed = homoscedasticity_result.is_homoscedastic
            except Exception as e:
                logger.warning(f"Homoscedasticity test failed: {e}")
                homoscedasticity_passed = True
                homoscedasticity_result = None
        else:
            homoscedasticity_passed = True
            homoscedasticity_result = None

        # Build diagnostics object
        diagnostics = None
        if normality_result is not None:
            diagnostics = AssumptionDiagnostics(
                normality=normality_result,
                homoscedasticity=homoscedasticity_result,
            )

        # Build recommendations
        recommendations = []
        if not normality_passed:
            recommendations.append(
                "Residuals deviate from normality. Consider using robust "
                "standard errors or bootstrapping for inference."
            )
        if not homoscedasticity_passed:
            recommendations.append(
                "Heteroscedasticity detected. Consider weighted least squares "
                "or heteroscedasticity-consistent standard errors."
            )
        if normality_passed and homoscedasticity_passed:
            recommendations.append(
                "All assumption checks passed. Standard inference methods are appropriate."
            )

        return AssumptionCheckResult(
            normality_passed=normality_passed,
            homoscedasticity_passed=homoscedasticity_passed,
            diagnostics=diagnostics,
            recommendations=recommendations,
            residuals_count=len(residuals),
            groups_checked=groups_checked,
        )

    @classmethod
    def get_model_residuals(
        cls,
        analysis_version_id: int,
        family: Optional[str] = None,
    ) -> Optional[np.ndarray]:
        """
        Get stored model residuals for an analysis version.

        These are the actual residuals (observed - predicted) from the
        Bayesian hierarchical model, computed at sampling time.

        Args:
            analysis_version_id: AnalysisVersion ID
            family: If provided, return residuals for this family only.
                    If None, return pooled residuals across all families.

        Returns:
            numpy array of residuals for log_fc_fmax, or None if not available
        """
        version = AnalysisVersion.query.get(analysis_version_id)
        if not version:
            return None
        return cls._get_model_residuals(version, family=family)

    @classmethod
    def _get_model_residuals(
        cls,
        version: AnalysisVersion,
        family: Optional[str] = None,
    ) -> Optional[np.ndarray]:
        """Extract stored model residuals from an AnalysisVersion.

        Handles both legacy flat format (``{"log_fc_fmax": [...]}``) and
        per-family format (``{"per_family": {"FamA": {"log_fc_fmax": [...]}, ...}}``).

        Args:
            version: AnalysisVersion instance
            family: If provided, return only this family's residuals.
                    If None, flatten all families (pooled diagnostics).
        """
        if not version.model_residuals:
            return None

        # Per-family format
        per_family = version.model_residuals.get("per_family")
        if per_family and isinstance(per_family, dict):
            if family:
                # Return only the requested family's residuals
                family_resids = per_family.get(family)
                if isinstance(family_resids, dict):
                    fam_vals = family_resids.get("log_fc_fmax")
                    if fam_vals:
                        return np.array(fam_vals)
                return None

            # Pooled: flatten all families into one array
            all_residuals = []
            for family_resids in per_family.values():
                if isinstance(family_resids, dict):
                    fam_vals = family_resids.get("log_fc_fmax")
                    if fam_vals:
                        all_residuals.extend(fam_vals)
            if all_residuals:
                return np.array(all_residuals)
            return None

        # Legacy flat format (family filter not applicable)
        residuals = version.model_residuals.get("log_fc_fmax")
        if not residuals:
            return None
        return np.array(residuals)

    @classmethod
    def get_log_fold_changes(
        cls,
        project_id: int,
        family: Optional[str] = None,
    ) -> np.ndarray:
        """
        Get log fold-change values for a project.

        These are the actual data the hierarchical model operates on.
        Prefer get_model_residuals() when an analysis version is available.

        Args:
            project_id: Project ID
            family: If provided, return only fold changes for this family.

        Returns:
            numpy array of log_fc_fmax values
        """
        return cls._get_log_fold_changes(project_id, family=family)

    # Keep old name as alias for backwards compatibility
    get_fit_residuals = get_log_fold_changes

    @classmethod
    def _get_log_fold_changes(
        cls,
        project_id: int,
        family: Optional[str] = None,
    ) -> np.ndarray:
        """
        Extract log fold-change values for a project.

        Queries FoldChange records joined through wells/plates/sessions
        to the project, returning non-null log_fc_fmax values.
        Optionally filters to a specific construct family.
        """
        query = db.session.query(
            FoldChange.log_fc_fmax
        ).join(
            Well, FoldChange.test_well_id == Well.id
        ).join(
            Plate, Well.plate_id == Plate.id
        ).join(
            ExperimentalSession, Plate.session_id == ExperimentalSession.id
        ).filter(
            ExperimentalSession.project_id == project_id,
            FoldChange.log_fc_fmax.isnot(None),
        )

        if family:
            query = query.join(
                Construct, Well.construct_id == Construct.id
            ).filter(
                Construct.family == family,
            )

        results = query.all()

        if not results:
            return np.array([])

        return np.array([r.log_fc_fmax for r in results])

    @classmethod
    def _within_group_normality(
        cls,
        project_id: int,
        alpha: float = 0.05
    ) -> tuple:
        """
        Test normality within each construct group and combine results.

        When model residuals are not available, pooled log fold changes
        can look non-normal simply because different constructs have
        different means. This tests within each construct and reports
        the worst (minimum) p-value.

        Returns:
            (NormalityTestResult or None, normality_passed: bool)
        """
        # Get log fold changes grouped by construct
        results = db.session.query(
            Construct.id,
            FoldChange.log_fc_fmax
        ).join(
            Well, FoldChange.test_well_id == Well.id
        ).join(
            Construct, Well.construct_id == Construct.id
        ).join(
            Plate, Well.plate_id == Plate.id
        ).join(
            ExperimentalSession, Plate.session_id == ExperimentalSession.id
        ).filter(
            ExperimentalSession.project_id == project_id,
            FoldChange.log_fc_fmax.isnot(None),
            Construct.is_unregulated == False,  # noqa: E712
        ).all()

        # Group by construct
        groups: Dict[int, list] = {}
        for construct_id, log_fc in results:
            if construct_id not in groups:
                groups[construct_id] = []
            groups[construct_id].append(log_fc)

        # Test each group with >= 3 observations
        worst_result = None
        all_passed = True
        for values in groups.values():
            if len(values) < 3:
                continue
            result = shapiro_wilk_test(np.array(values), alpha=alpha)
            if worst_result is None or result.p_value < worst_result.p_value:
                worst_result = result
            if not result.is_normal:
                all_passed = False

        if worst_result is None:
            return None, True

        return worst_result, all_passed

    @classmethod
    def _get_grouped_residuals(
        cls,
        project_id: int,
        family: Optional[str] = None,
    ) -> List[np.ndarray]:
        """
        Get log fold changes grouped for homoscedasticity testing.

        When ``family`` is None (pooled): groups by construct family so the
        Levene test checks whether variance differs across families.

        When ``family`` is set: groups by construct *within* that family so the
        Levene test checks whether variance differs across constructs.
        """
        if family:
            # Within-family: group by construct
            results = db.session.query(
                Construct.id,
                FoldChange.log_fc_fmax
            ).join(
                Well, FoldChange.test_well_id == Well.id
            ).join(
                Construct, Well.construct_id == Construct.id
            ).join(
                Plate, Well.plate_id == Plate.id
            ).join(
                ExperimentalSession, Plate.session_id == ExperimentalSession.id
            ).filter(
                ExperimentalSession.project_id == project_id,
                FoldChange.log_fc_fmax.isnot(None),
                Construct.family == family,
                Construct.is_unregulated == False,  # noqa: E712
            ).all()

            construct_values: Dict[int, list] = {}
            for construct_id, log_fc in results:
                if construct_id not in construct_values:
                    construct_values[construct_id] = []
                construct_values[construct_id].append(log_fc)

            groups = []
            for values in construct_values.values():
                if len(values) >= 3:
                    groups.append(np.array(values))
            return groups

        # Pooled: group by family
        results = db.session.query(
            Construct.family,
            FoldChange.log_fc_fmax
        ).join(
            Well, FoldChange.test_well_id == Well.id
        ).join(
            Construct, Well.construct_id == Construct.id
        ).join(
            Plate, Well.plate_id == Plate.id
        ).join(
            ExperimentalSession, Plate.session_id == ExperimentalSession.id
        ).filter(
            ExperimentalSession.project_id == project_id,
            FoldChange.log_fc_fmax.isnot(None),
            Construct.family.isnot(None),
            Construct.is_unregulated == False,  # noqa: E712 — exclude negative control
        ).all()

        # Group by family
        family_values: Dict[str, list] = {}
        for fam, log_fc in results:
            if fam not in family_values:
                family_values[fam] = []
            family_values[fam].append(log_fc)

        # Convert to arrays and filter small groups
        groups = []
        for values in family_values.values():
            if len(values) >= 3:
                groups.append(np.array(values))

        return groups

    @classmethod
    def apply_multiple_comparison_correction(
        cls,
        p_values: List[float],
        method: str = 'benjamini_hochberg',
        alpha: float = 0.05
    ) -> List[bool]:
        """
        Apply multiple comparison correction and return significance flags.

        PRD Reference: T8.18-T8.19 - Multiple comparison corrections

        Args:
            p_values: List of p-values to correct
            method: Correction method ('benjamini_hochberg', 'bonferroni', 'holm')
            alpha: Significance level

        Returns:
            List of boolean significance flags (True = significant after correction)

        Raises:
            ValueError: If method is not recognized
        """
        if not p_values:
            return []

        # Map method names to supported values
        method_map = {
            'benjamini_hochberg': 'fdr',
            'bh': 'fdr',
            'fdr': 'fdr',
            'bonferroni': 'bonferroni',
            'bon': 'bonferroni',
            'holm': 'holm',
            'holm_bonferroni': 'holm',
            'holm-bonferroni': 'holm',
        }

        normalized_method = method.lower().replace('-', '_')
        if normalized_method not in method_map:
            raise ValueError(
                f"Unknown correction method: {method}. "
                f"Supported: {list(method_map.keys())}"
            )

        mapped_method = method_map[normalized_method]

        try:
            result = apply_correction(p_values, method=mapped_method, alpha=alpha)
            return result.significant
        except Exception as e:
            logger.error(f"Failed to apply correction: {e}")
            raise ValueError(f"Failed to apply {method} correction: {e}")

    @classmethod
    def get_multiple_comparison_result(
        cls,
        p_values: List[float],
        method: str = 'benjamini_hochberg',
        alpha: float = 0.05
    ) -> MultipleComparisonResult:
        """
        Apply multiple comparison correction and return full result.

        Args:
            p_values: List of p-values to correct
            method: Correction method
            alpha: Significance level

        Returns:
            MultipleComparisonResult with adjusted p-values and significance
        """
        if not p_values:
            return MultipleComparisonResult(
                method=method,
                original_p_values=[],
                adjusted_p_values=[],
                significant=[],
                alpha=alpha,
                n_comparisons=0,
                n_significant=0,
            )

        method_map = {
            'benjamini_hochberg': 'fdr',
            'bh': 'fdr',
            'fdr': 'fdr',
            'bonferroni': 'bonferroni',
            'holm': 'holm',
        }

        normalized_method = method.lower().replace('-', '_')
        mapped_method = method_map.get(normalized_method, 'fdr')

        return apply_correction(p_values, method=mapped_method, alpha=alpha)

    @classmethod
    def compute_effect_sizes(
        cls,
        project_id: int
    ) -> Dict[str, Any]:
        """
        Compute effect sizes for all pairwise comparisons in project.

        Args:
            project_id: Project ID

        Returns:
            Dict with effect size summary statistics
        """
        from app.analysis.statistical_tests import cohens_d

        project = Project.query.get(project_id)
        if not project:
            raise StatisticsServiceError(f"Project {project_id} not found")

        # Get fold changes for effect size calculation
        fold_changes = db.session.query(FoldChange).join(
            Well, FoldChange.test_well_id == Well.id
        ).join(
            Plate, Well.plate_id == Plate.id
        ).join(
            ExperimentalSession, Plate.session_id == ExperimentalSession.id
        ).filter(
            ExperimentalSession.project_id == project_id,
        ).all()

        if not fold_changes:
            return {
                'mean_effect_size': None,
                'effect_sizes': [],
                'count': 0,
            }

        effect_sizes = []
        for fc in fold_changes:
            if fc.log_fc_fmax is not None and fc.log_fc_fmax_se is not None:
                # Cohen's d = effect / SE (roughly)
                d = abs(fc.log_fc_fmax / fc.log_fc_fmax_se) if fc.log_fc_fmax_se > 0 else 0
                effect_sizes.append(d)

        if effect_sizes:
            return {
                'mean_effect_size': np.mean(effect_sizes),
                'median_effect_size': np.median(effect_sizes),
                'effect_sizes': effect_sizes,
                'count': len(effect_sizes),
            }

        return {
            'mean_effect_size': None,
            'effect_sizes': [],
            'count': 0,
        }

    @classmethod
    def validate_analysis_assumptions(
        cls,
        project_id: int,
        alpha: float = 0.05
    ) -> Dict[str, Any]:
        """
        Comprehensive validation of statistical assumptions for a project.

        Args:
            project_id: Project ID
            alpha: Significance level

        Returns:
            Dict with validation results and recommendations
        """
        project = Project.query.get(project_id)
        if not project:
            raise StatisticsServiceError(f"Project {project_id} not found")

        # Get or create analysis version
        version = AnalysisVersion.query.filter_by(
            project_id=project_id
        ).order_by(
            AnalysisVersion.created_at.desc()
        ).first()

        if not version:
            return {
                'validated': False,
                'reason': 'No analysis version found',
                'assumptions': {},
                'recommendations': ['Run analysis first before validating assumptions'],
            }

        # Run assumption checks
        result = cls.run_assumption_checks(version.id, alpha=alpha)

        return {
            'validated': True,
            'analysis_version_id': version.id,
            'assumptions': {
                'normality': {
                    'passed': result.normality_passed,
                    'residuals_checked': result.residuals_count,
                },
                'homoscedasticity': {
                    'passed': result.homoscedasticity_passed,
                    'groups_checked': result.groups_checked,
                },
            },
            'all_passed': result.all_passed,
            'recommendations': result.recommendations,
        }
