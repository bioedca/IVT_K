"""
Comparison hierarchy and fold change computation.

Phase 6: Comparison Hierarchy & Partial Analysis
- Primary comparisons (mutant vs WT)
- Secondary comparisons (WT vs unregulated)
- Derived comparisons (mutant vs unregulated)
- Mutant-to-mutant comparisons
- Variance inflation factors
"""
import numpy as np
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

from app.analysis.constants import LOW_PRECISION_CI_WIDTH

logger = logging.getLogger(__name__)


class ComparisonType(Enum):
    """Types of comparisons in the hierarchy."""
    PRIMARY = "primary"           # Mutant vs WT (direct, same plate)
    SECONDARY = "secondary"       # WT vs Unregulated
    TERTIARY = "tertiary"         # Mutant vs Unregulated (derived)
    MUTANT_MUTANT = "mutant_mutant"  # Mutant A vs Mutant B (through shared WT)
    CROSS_FAMILY = "cross_family"    # Across families (through unregulated)


class PathType(Enum):
    """Comparison path types for variance inflation."""
    DIRECT = "direct"       # Same plate pairing (VIF = 1.0)
    ONE_HOP = "one_hop"     # Through one intermediate (VIF = sqrt(2))
    TWO_HOP = "two_hop"     # Through two intermediates (VIF = 2.0)
    FOUR_HOP = "four_hop"   # Cross-family (VIF = 4.0)


# Variance inflation factors by path type
VIF_VALUES = {
    PathType.DIRECT: 1.0,
    PathType.ONE_HOP: np.sqrt(2),  # ~1.414
    PathType.TWO_HOP: 2.0,
    PathType.FOUR_HOP: 4.0
}


@dataclass
class FoldChangeResult:
    """Result of a fold change computation."""
    # Raw fold changes (linear scale)
    fc_fmax: Optional[float] = None
    fc_fmax_se: Optional[float] = None
    fc_kobs: Optional[float] = None
    fc_kobs_se: Optional[float] = None
    delta_tlag: Optional[float] = None
    delta_tlag_se: Optional[float] = None

    # Log-transformed fold changes
    log_fc_fmax: Optional[float] = None
    log_fc_fmax_se: Optional[float] = None
    log_fc_kobs: Optional[float] = None
    log_fc_kobs_se: Optional[float] = None

    # Metadata
    test_construct_id: Optional[int] = None
    control_construct_id: Optional[int] = None
    comparison_type: Optional[ComparisonType] = None
    path_type: PathType = PathType.DIRECT
    variance_inflation_factor: float = 1.0

    # Quality flags
    is_valid: bool = True
    low_precision_warning: bool = False
    warning_message: Optional[str] = None

    @property
    def ci_width_fmax(self) -> Optional[float]:
        """95% CI width for log_fc_fmax."""
        if self.log_fc_fmax_se is not None:
            return 2 * 1.96 * self.log_fc_fmax_se
        return None

    @property
    def ci_width_kobs(self) -> Optional[float]:
        """95% CI width for log_fc_kobs."""
        if self.log_fc_kobs_se is not None:
            return 2 * 1.96 * self.log_fc_kobs_se
        return None


@dataclass
class ComparisonPath:
    """Represents a path through the comparison graph."""
    source_id: int
    target_id: int
    path_type: PathType
    intermediates: List[int] = field(default_factory=list)
    variance_inflation: float = 1.0

    @property
    def hop_count(self) -> int:
        """Number of hops in the comparison path."""
        return len(self.intermediates)


@dataclass
class AnalysisScope:
    """Scope of analysis based on available anchors."""
    can_analyze: bool = True
    scope: str = "full"  # "full", "within_family_only", "none"
    missing_anchors: List[str] = field(default_factory=list)
    affected_families: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class PairedAnalysis:
    """
    Computes fold changes between paired measurements.

    Implements the comparison hierarchy:
    1. Primary: Mutant vs WT (direct, same plate)
    2. Secondary: WT vs Unregulated
    3. Tertiary: Mutant vs Unregulated (derived from 1 & 2)
    4. Mutant-to-Mutant: Through shared WT reference
    """

    # Default threshold for flagging low precision intermediates
    LOW_PRECISION_THRESHOLD = LOW_PRECISION_CI_WIDTH

    def __init__(self, low_precision_threshold: float = LOW_PRECISION_CI_WIDTH):
        """
        Initialize paired analysis.

        Args:
            low_precision_threshold: CI width threshold for warning
        """
        self.low_precision_threshold = low_precision_threshold

    def compute_fold_change(
        self,
        test_fmax: float,
        test_fmax_se: float,
        control_fmax: float,
        control_fmax_se: float,
        test_kobs: Optional[float] = None,
        test_kobs_se: Optional[float] = None,
        control_kobs: Optional[float] = None,
        control_kobs_se: Optional[float] = None,
        test_tlag: Optional[float] = None,
        test_tlag_se: Optional[float] = None,
        control_tlag: Optional[float] = None,
        control_tlag_se: Optional[float] = None,
        test_construct_id: Optional[int] = None,
        control_construct_id: Optional[int] = None,
        comparison_type: ComparisonType = ComparisonType.PRIMARY
    ) -> FoldChangeResult:
        """
        Compute fold change between test and control measurements.

        Uses the delta method for uncertainty propagation:
        SE(log_FC) = sqrt[(SE_test/test)² + (SE_control/control)²]

        Args:
            test_fmax: Test F_max value
            test_fmax_se: Standard error of test F_max
            control_fmax: Control F_max value
            control_fmax_se: Standard error of control F_max
            test_kobs: Optional test k_obs value
            test_kobs_se: Optional standard error of test k_obs
            control_kobs: Optional control k_obs value
            control_kobs_se: Optional standard error of control k_obs
            test_tlag: Optional test t_lag value
            test_tlag_se: Optional standard error of test t_lag
            control_tlag: Optional control t_lag value
            control_tlag_se: Optional standard error of control t_lag
            test_construct_id: ID of test construct
            control_construct_id: ID of control construct
            comparison_type: Type of comparison

        Returns:
            FoldChangeResult with computed values
        """
        result = FoldChangeResult(
            test_construct_id=test_construct_id,
            control_construct_id=control_construct_id,
            comparison_type=comparison_type
        )

        # Validate inputs
        if control_fmax <= 0 or test_fmax <= 0:
            result.is_valid = False
            result.warning_message = "Invalid F_max values (must be positive)"
            return result

        # F_max fold change
        result.fc_fmax = test_fmax / control_fmax
        result.log_fc_fmax = np.log(test_fmax) - np.log(control_fmax)

        # Propagate uncertainty using delta method
        result.fc_fmax_se, result.log_fc_fmax_se = self._propagate_ratio_uncertainty(
            test_fmax, test_fmax_se, control_fmax, control_fmax_se
        )

        # k_obs fold change (if provided)
        if test_kobs is not None and control_kobs is not None:
            if test_kobs > 0 and control_kobs > 0:
                result.fc_kobs = test_kobs / control_kobs
                result.log_fc_kobs = np.log(test_kobs) - np.log(control_kobs)

                if test_kobs_se is not None and control_kobs_se is not None:
                    result.fc_kobs_se, result.log_fc_kobs_se = self._propagate_ratio_uncertainty(
                        test_kobs, test_kobs_se, control_kobs, control_kobs_se
                    )

        # t_lag difference (not a ratio)
        if test_tlag is not None and control_tlag is not None:
            result.delta_tlag = test_tlag - control_tlag

            if test_tlag_se is not None and control_tlag_se is not None:
                # Simple sum of variances for difference
                result.delta_tlag_se = np.sqrt(test_tlag_se**2 + control_tlag_se**2)

        return result

    def _propagate_ratio_uncertainty(
        self,
        numerator: float,
        numerator_se: float,
        denominator: float,
        denominator_se: float
    ) -> Tuple[float, float]:
        """
        Propagate uncertainty for a ratio using delta method.

        For ratio R = A/B:
        SE(R) = R * sqrt[(SE_A/A)² + (SE_B/B)²]

        For log ratio log(R) = log(A) - log(B):
        SE(log_R) = sqrt[(SE_A/A)² + (SE_B/B)²]

        Args:
            numerator: Numerator value
            numerator_se: Standard error of numerator
            denominator: Denominator value
            denominator_se: Standard error of denominator

        Returns:
            Tuple of (ratio_se, log_ratio_se)
        """
        # Relative uncertainties
        rel_var_num = (numerator_se / numerator) ** 2 if numerator > 0 else 0
        rel_var_denom = (denominator_se / denominator) ** 2 if denominator > 0 else 0

        # Combined relative variance
        rel_var_total = rel_var_num + rel_var_denom

        # SE of log ratio
        log_ratio_se = np.sqrt(rel_var_total)

        # SE of ratio (multiply by ratio value)
        if abs(denominator) < 1e-10:
            return 0.0, 0.0
        ratio = numerator / denominator
        ratio_se = ratio * log_ratio_se

        return ratio_se, log_ratio_se

    def compute_derived_fc(
        self,
        fc_primary: FoldChangeResult,
        fc_secondary: FoldChangeResult
    ) -> FoldChangeResult:
        """
        Compute derived fold change (mutant vs unregulated).

        FC_m/unreg = FC_m/WT × FC_WT/unreg
        SE(log_FC_m/unreg) = sqrt[SE(log_FC_m/WT)² + SE(log_FC_WT/unreg)²]

        This is a tertiary comparison through two hops.

        Args:
            fc_primary: Primary comparison (mutant vs WT)
            fc_secondary: Secondary comparison (WT vs unregulated)

        Returns:
            Derived FoldChangeResult
        """
        result = FoldChangeResult(
            test_construct_id=fc_primary.test_construct_id,
            control_construct_id=fc_secondary.control_construct_id,
            comparison_type=ComparisonType.TERTIARY,
            path_type=PathType.TWO_HOP,
            variance_inflation_factor=VIF_VALUES[PathType.TWO_HOP]
        )

        # Check validity of inputs
        if not fc_primary.is_valid or not fc_secondary.is_valid:
            result.is_valid = False
            result.warning_message = "Invalid input comparisons"
            return result

        # Multiply fold changes (add log fold changes)
        if fc_primary.fc_fmax is not None and fc_secondary.fc_fmax is not None:
            result.fc_fmax = fc_primary.fc_fmax * fc_secondary.fc_fmax
            result.log_fc_fmax = fc_primary.log_fc_fmax + fc_secondary.log_fc_fmax

            # Propagate uncertainty (sum of variances in log space)
            if fc_primary.log_fc_fmax_se is not None and fc_secondary.log_fc_fmax_se is not None:
                result.log_fc_fmax_se = np.sqrt(
                    fc_primary.log_fc_fmax_se**2 + fc_secondary.log_fc_fmax_se**2
                )
                result.fc_fmax_se = result.fc_fmax * result.log_fc_fmax_se

        # k_obs
        if fc_primary.fc_kobs is not None and fc_secondary.fc_kobs is not None:
            result.fc_kobs = fc_primary.fc_kobs * fc_secondary.fc_kobs
            result.log_fc_kobs = fc_primary.log_fc_kobs + fc_secondary.log_fc_kobs

            if fc_primary.log_fc_kobs_se is not None and fc_secondary.log_fc_kobs_se is not None:
                result.log_fc_kobs_se = np.sqrt(
                    fc_primary.log_fc_kobs_se**2 + fc_secondary.log_fc_kobs_se**2
                )
                result.fc_kobs_se = result.fc_kobs * result.log_fc_kobs_se

        # t_lag difference (add differences)
        if fc_primary.delta_tlag is not None and fc_secondary.delta_tlag is not None:
            result.delta_tlag = fc_primary.delta_tlag + fc_secondary.delta_tlag

            if fc_primary.delta_tlag_se is not None and fc_secondary.delta_tlag_se is not None:
                result.delta_tlag_se = np.sqrt(
                    fc_primary.delta_tlag_se**2 + fc_secondary.delta_tlag_se**2
                )

        # Check for low precision intermediate
        if self.flag_low_precision_intermediate(fc_secondary):
            result.low_precision_warning = True
            result.warning_message = "Secondary comparison has low precision"

        return result

    def compute_mutant_to_mutant_fc(
        self,
        fc_a_wt: FoldChangeResult,
        fc_b_wt: FoldChangeResult
    ) -> FoldChangeResult:
        """
        Compute mutant A vs mutant B through shared WT reference.

        FC_A/B = FC_A/WT / FC_B/WT
        log_FC_A/B = log_FC_A/WT - log_FC_B/WT
        SE(log_FC_A/B) = sqrt[SE(log_FC_A/WT)² + SE(log_FC_B/WT)²]

        This is a one-hop comparison (VIF = sqrt(2)).

        Args:
            fc_a_wt: Fold change of mutant A vs WT
            fc_b_wt: Fold change of mutant B vs WT

        Returns:
            FoldChangeResult for mutant A vs mutant B
        """
        result = FoldChangeResult(
            test_construct_id=fc_a_wt.test_construct_id,
            control_construct_id=fc_b_wt.test_construct_id,
            comparison_type=ComparisonType.MUTANT_MUTANT,
            path_type=PathType.ONE_HOP,
            variance_inflation_factor=VIF_VALUES[PathType.ONE_HOP]
        )

        # Check validity
        if not fc_a_wt.is_valid or not fc_b_wt.is_valid:
            result.is_valid = False
            result.warning_message = "Invalid input comparisons"
            return result

        # Divide fold changes (subtract log fold changes)
        if fc_a_wt.fc_fmax is not None and fc_b_wt.fc_fmax is not None:
            if fc_b_wt.fc_fmax > 0:
                result.fc_fmax = fc_a_wt.fc_fmax / fc_b_wt.fc_fmax
                if fc_a_wt.log_fc_fmax is not None and fc_b_wt.log_fc_fmax is not None:
                    result.log_fc_fmax = fc_a_wt.log_fc_fmax - fc_b_wt.log_fc_fmax

                if fc_a_wt.log_fc_fmax_se is not None and fc_b_wt.log_fc_fmax_se is not None:
                    result.log_fc_fmax_se = np.sqrt(
                        fc_a_wt.log_fc_fmax_se**2 + fc_b_wt.log_fc_fmax_se**2
                    )
                    result.fc_fmax_se = result.fc_fmax * result.log_fc_fmax_se

        # k_obs
        if fc_a_wt.fc_kobs is not None and fc_b_wt.fc_kobs is not None:
            if fc_b_wt.fc_kobs > 0:
                result.fc_kobs = fc_a_wt.fc_kobs / fc_b_wt.fc_kobs
                if fc_a_wt.log_fc_kobs is not None and fc_b_wt.log_fc_kobs is not None:
                    result.log_fc_kobs = fc_a_wt.log_fc_kobs - fc_b_wt.log_fc_kobs

                if fc_a_wt.log_fc_kobs_se is not None and fc_b_wt.log_fc_kobs_se is not None:
                    result.log_fc_kobs_se = np.sqrt(
                        fc_a_wt.log_fc_kobs_se**2 + fc_b_wt.log_fc_kobs_se**2
                    )
                    result.fc_kobs_se = result.fc_kobs * result.log_fc_kobs_se

        # t_lag (subtract differences)
        if fc_a_wt.delta_tlag is not None and fc_b_wt.delta_tlag is not None:
            result.delta_tlag = fc_a_wt.delta_tlag - fc_b_wt.delta_tlag

            if fc_a_wt.delta_tlag_se is not None and fc_b_wt.delta_tlag_se is not None:
                result.delta_tlag_se = np.sqrt(
                    fc_a_wt.delta_tlag_se**2 + fc_b_wt.delta_tlag_se**2
                )

        return result

    def compute_cross_family_fc(
        self,
        fc_m1_wt1: FoldChangeResult,
        fc_wt1_unreg: FoldChangeResult,
        fc_wt2_unreg: FoldChangeResult,
        fc_m2_wt2: FoldChangeResult
    ) -> FoldChangeResult:
        """
        Compute cross-family comparison (mutant1 vs mutant2 across families).

        Path: M1 → WT1 → Unreg → WT2 → M2
        This is a four-hop comparison (VIF = 4.0).

        Args:
            fc_m1_wt1: Mutant 1 vs WT of family 1
            fc_wt1_unreg: WT family 1 vs unregulated
            fc_wt2_unreg: WT family 2 vs unregulated
            fc_m2_wt2: Mutant 2 vs WT of family 2

        Returns:
            Cross-family FoldChangeResult
        """
        # Compute M1 vs Unreg
        fc_m1_unreg = self.compute_derived_fc(fc_m1_wt1, fc_wt1_unreg)

        # Compute M2 vs Unreg
        fc_m2_unreg = self.compute_derived_fc(fc_m2_wt2, fc_wt2_unreg)

        # Compute M1 vs M2 (through unregulated)
        result = FoldChangeResult(
            test_construct_id=fc_m1_wt1.test_construct_id,
            control_construct_id=fc_m2_wt2.test_construct_id,
            comparison_type=ComparisonType.CROSS_FAMILY,
            path_type=PathType.FOUR_HOP,
            variance_inflation_factor=VIF_VALUES[PathType.FOUR_HOP]
        )

        if not fc_m1_unreg.is_valid or not fc_m2_unreg.is_valid:
            result.is_valid = False
            result.warning_message = "Invalid intermediate comparisons"
            return result

        # Divide: M1/M2 = (M1/Unreg) / (M2/Unreg)
        if fc_m1_unreg.fc_fmax is not None and fc_m2_unreg.fc_fmax is not None:
            if fc_m2_unreg.fc_fmax > 0:
                result.fc_fmax = fc_m1_unreg.fc_fmax / fc_m2_unreg.fc_fmax
                if fc_m1_unreg.log_fc_fmax is not None and fc_m2_unreg.log_fc_fmax is not None:
                    result.log_fc_fmax = fc_m1_unreg.log_fc_fmax - fc_m2_unreg.log_fc_fmax

                if fc_m1_unreg.log_fc_fmax_se is not None and fc_m2_unreg.log_fc_fmax_se is not None:
                    result.log_fc_fmax_se = np.sqrt(
                        fc_m1_unreg.log_fc_fmax_se**2 + fc_m2_unreg.log_fc_fmax_se**2
                    )
                    result.fc_fmax_se = result.fc_fmax * result.log_fc_fmax_se

        # Mark as exploratory with warning
        result.low_precision_warning = True
        result.warning_message = "Cross-family comparison: exploratory only, high VIF"

        return result

    def get_variance_inflation_factor(self, path_type: PathType) -> float:
        """
        Get variance inflation factor for a comparison path type.

        VIF values:
        - Direct (same plate): 1.0
        - One-hop (through shared WT): sqrt(2) ≈ 1.414
        - Two-hop (through WT and unreg): 2.0
        - Four-hop (cross-family): 4.0

        Args:
            path_type: Type of comparison path

        Returns:
            Variance inflation factor
        """
        return VIF_VALUES.get(path_type, 1.0)

    def flag_low_precision_intermediate(
        self,
        intermediate_result: FoldChangeResult,
        threshold: Optional[float] = None
    ) -> bool:
        """
        Flag if an intermediate comparison has low precision.

        Args:
            intermediate_result: The intermediate FoldChangeResult
            threshold: CI width threshold (default: LOW_PRECISION_THRESHOLD)

        Returns:
            True if CI width exceeds threshold
        """
        threshold = threshold or self.low_precision_threshold

        ci_width = intermediate_result.ci_width_fmax
        if ci_width is not None and ci_width > threshold:
            return True

        return False

    def apply_vif_to_se(
        self,
        se: float,
        path_type: PathType
    ) -> float:
        """
        Apply variance inflation factor to standard error.

        SE_inflated = SE * sqrt(VIF)

        Args:
            se: Original standard error
            path_type: Type of comparison path

        Returns:
            Inflated standard error
        """
        vif = self.get_variance_inflation_factor(path_type)
        return se * np.sqrt(vif)


class ComparisonGraph:
    """
    Builds and validates comparison graphs between constructs.

    The graph represents all possible comparison paths in a project,
    tracking which constructs can be compared directly or through
    intermediate references.
    """

    def __init__(self):
        """Initialize empty comparison graph."""
        self.nodes: Dict[int, Dict[str, Any]] = {}  # construct_id -> metadata
        self.edges: Dict[Tuple[int, int], ComparisonPath] = {}
        self.families: Dict[str, List[int]] = {}  # family -> construct_ids
        self.wildtypes: Dict[str, int] = {}  # family -> wt_construct_id
        self.unregulated_id: Optional[int] = None

    def add_construct(
        self,
        construct_id: int,
        family: str,
        is_wildtype: bool = False,
        is_unregulated: bool = False
    ) -> None:
        """
        Add a construct to the graph.

        Args:
            construct_id: Construct ID
            family: Family name
            is_wildtype: Whether this is a wildtype construct
            is_unregulated: Whether this is an unregulated construct
        """
        self.nodes[construct_id] = {
            'family': family,
            'is_wildtype': is_wildtype,
            'is_unregulated': is_unregulated
        }

        # Track family membership
        if family not in self.families:
            self.families[family] = []
        if construct_id not in self.families[family]:
            self.families[family].append(construct_id)

        # Track wildtypes
        if is_wildtype:
            self.wildtypes[family] = construct_id

        # Track unregulated
        if is_unregulated:
            self.unregulated_id = construct_id

    def add_direct_comparison(
        self,
        source_id: int,
        target_id: int,
        co_occurrence_count: int = 1
    ) -> None:
        """
        Add a direct comparison edge (same plate co-occurrence).

        Args:
            source_id: Source construct ID
            target_id: Target construct ID
            co_occurrence_count: Number of plates where both appear
        """
        key = (source_id, target_id)
        self.edges[key] = ComparisonPath(
            source_id=source_id,
            target_id=target_id,
            path_type=PathType.DIRECT,
            variance_inflation=VIF_VALUES[PathType.DIRECT]
        )

    def build_derived_paths(self) -> None:
        """
        Build all derived comparison paths based on direct comparisons.

        This computes:
        - Mutant-to-mutant paths through shared WT
        - Tertiary paths through WT and unregulated
        - Cross-family paths
        """
        # Build mutant-to-mutant paths within families
        for family, construct_ids in self.families.items():
            wt_id = self.wildtypes.get(family)
            if wt_id is None:
                continue

            # Find all mutants in family with direct WT comparison
            mutants_with_wt = []
            for cid in construct_ids:
                if cid == wt_id:
                    continue
                if (cid, wt_id) in self.edges or (wt_id, cid) in self.edges:
                    mutants_with_wt.append(cid)

            # Create mutant-to-mutant paths
            for i, m1 in enumerate(mutants_with_wt):
                for m2 in mutants_with_wt[i+1:]:
                    key = (m1, m2)
                    if key not in self.edges:
                        self.edges[key] = ComparisonPath(
                            source_id=m1,
                            target_id=m2,
                            path_type=PathType.ONE_HOP,
                            intermediates=[wt_id],
                            variance_inflation=VIF_VALUES[PathType.ONE_HOP]
                        )

        # Build tertiary paths (mutant vs unregulated)
        if self.unregulated_id is not None:
            for family, wt_id in self.wildtypes.items():
                # Check if WT has comparison to unregulated
                if (wt_id, self.unregulated_id) not in self.edges and \
                   (self.unregulated_id, wt_id) not in self.edges:
                    continue

                # Add tertiary paths for all mutants in family
                for cid in self.families.get(family, []):
                    if cid == wt_id or cid == self.unregulated_id:
                        continue

                    # Check if mutant has comparison to WT
                    if (cid, wt_id) not in self.edges and (wt_id, cid) not in self.edges:
                        continue

                    key = (cid, self.unregulated_id)
                    if key not in self.edges:
                        self.edges[key] = ComparisonPath(
                            source_id=cid,
                            target_id=self.unregulated_id,
                            path_type=PathType.TWO_HOP,
                            intermediates=[wt_id],
                            variance_inflation=VIF_VALUES[PathType.TWO_HOP]
                        )

        # Build cross-family paths (M1 → WT1 → Unreg → WT2 → M2)
        if self.unregulated_id is not None:
            family_names = list(self.wildtypes.keys())
            for i, f1 in enumerate(family_names):
                wt1 = self.wildtypes[f1]
                # WT1 must have edge to unregulated
                if (wt1, self.unregulated_id) not in self.edges and \
                   (self.unregulated_id, wt1) not in self.edges:
                    continue

                for f2 in family_names[i + 1:]:
                    wt2 = self.wildtypes[f2]
                    # WT2 must have edge to unregulated
                    if (wt2, self.unregulated_id) not in self.edges and \
                       (self.unregulated_id, wt2) not in self.edges:
                        continue

                    # Get mutants with WT edges in each family
                    mutants_f1 = [
                        cid for cid in self.families.get(f1, [])
                        if cid != wt1 and cid != self.unregulated_id
                        and ((cid, wt1) in self.edges or (wt1, cid) in self.edges)
                    ]
                    mutants_f2 = [
                        cid for cid in self.families.get(f2, [])
                        if cid != wt2 and cid != self.unregulated_id
                        and ((cid, wt2) in self.edges or (wt2, cid) in self.edges)
                    ]

                    for m1 in mutants_f1:
                        for m2 in mutants_f2:
                            key = (m1, m2)
                            if key not in self.edges:
                                self.edges[key] = ComparisonPath(
                                    source_id=m1,
                                    target_id=m2,
                                    path_type=PathType.FOUR_HOP,
                                    intermediates=[wt1, self.unregulated_id, wt2],
                                    variance_inflation=VIF_VALUES[PathType.FOUR_HOP]
                                )

    def is_connected(self) -> bool:
        """
        Check if the comparison graph is connected.

        A connected graph means all constructs can be compared
        (directly or through intermediate references).

        Returns:
            True if graph is connected
        """
        if len(self.nodes) <= 1:
            return True

        # Build adjacency list
        adj = {cid: set() for cid in self.nodes}
        for (s, t), path in self.edges.items():
            adj[s].add(t)
            adj[t].add(s)

        # BFS from first node
        start = next(iter(self.nodes))
        visited = {start}
        queue = [start]

        while queue:
            current = queue.pop(0)
            for neighbor in adj[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        return len(visited) == len(self.nodes)

    def get_disconnected_components(self) -> List[List[int]]:
        """
        Get list of disconnected components in the graph.

        Returns:
            List of components, each being a list of construct IDs
        """
        # Build adjacency list
        adj = {cid: set() for cid in self.nodes}
        for (s, t), path in self.edges.items():
            adj[s].add(t)
            adj[t].add(s)

        visited = set()
        components = []

        for start in self.nodes:
            if start in visited:
                continue

            # BFS for this component
            component = []
            queue = [start]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                component.append(current)
                for neighbor in adj[current]:
                    if neighbor not in visited:
                        queue.append(neighbor)

            components.append(component)

        return components

    def determine_analysis_scope(self) -> AnalysisScope:
        """
        Determine what level of analysis is possible.

        Returns:
            AnalysisScope indicating what comparisons can be made
        """
        scope = AnalysisScope()

        # Check for unregulated reference
        if self.unregulated_id is None:
            scope.missing_anchors.append("unregulated")
            scope.warnings.append("No unregulated reference: cross-family comparisons not available")

        # Check each family for WT (skip families that only have unregulated)
        for family, construct_ids in self.families.items():
            # Skip if this family only contains the unregulated construct
            if len(construct_ids) == 1 and self.unregulated_id in construct_ids:
                continue

            if family not in self.wildtypes:
                scope.missing_anchors.append(f"WT_{family}")
                scope.affected_families.append(family)
                scope.warnings.append(f"Family '{family}' has no wildtype: family excluded from analysis")

        # Determine scope
        if scope.affected_families:
            if len(scope.affected_families) == len(self.families):
                scope.can_analyze = False
                scope.scope = "none"
            else:
                scope.scope = "partial"
        elif self.unregulated_id is None:
            scope.scope = "within_family_only"
        else:
            scope.scope = "full"

        # Check graph connectivity
        if not self.is_connected():
            components = self.get_disconnected_components()
            scope.warnings.append(
                f"Graph has {len(components)} disconnected components: "
                "some comparisons not possible"
            )
            if scope.scope == "full":
                scope.scope = "within_family_only"

        return scope

    def get_comparison_path(
        self,
        source_id: int,
        target_id: int
    ) -> Optional[ComparisonPath]:
        """
        Get the comparison path between two constructs.

        Args:
            source_id: Source construct ID
            target_id: Target construct ID

        Returns:
            ComparisonPath if exists, None otherwise
        """
        # Check direct path
        if (source_id, target_id) in self.edges:
            return self.edges[(source_id, target_id)]
        if (target_id, source_id) in self.edges:
            # Reverse path
            path = self.edges[(target_id, source_id)]
            return ComparisonPath(
                source_id=source_id,
                target_id=target_id,
                path_type=path.path_type,
                intermediates=path.intermediates[::-1],
                variance_inflation=path.variance_inflation
            )

        return None


def compute_effective_sample_size(
    n_observations: int,
    variance_inflation_factor: float
) -> float:
    """
    Compute effective sample size given VIF.

    n_eff = n / VIF²

    Args:
        n_observations: Number of actual observations
        variance_inflation_factor: VIF for the comparison type

    Returns:
        Effective sample size
    """
    return n_observations / (variance_inflation_factor ** 2)
