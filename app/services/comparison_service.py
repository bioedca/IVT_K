"""
Comparison service - backwards-compatible facade.

This module delegates to three specialized sub-services split out during
Phase 3 refactoring:

- ``FoldChangeService`` -- pairwise fold change computation
- ``ComparisonGraphService`` -- graph construction, validation, derived comparisons
- ``PrecisionWeightService`` -- variance inflation / precision weight storage

All public names that were previously importable from this module
(``ComparisonService``, ``ComparisonError``, ``ExclusionImpact``,
``ComparisonSummary``) remain importable here so that existing callers
are unaffected.
"""

from app.services.fold_change_service import FoldChangeService
from app.services.comparison_graph_service import (
    ComparisonGraphService,
    ComparisonError,
    ExclusionImpact,
    ComparisonSummary,
)
from app.services.precision_weight_service import PrecisionWeightService


class ComparisonService:
    """Unified comparison service delegating to specialized sub-services."""

    # -- Fold change methods --------------------------------------------------
    compute_plate_fold_changes = FoldChangeService.compute_plate_fold_changes
    _compute_well_pair_fc = FoldChangeService._compute_well_pair_fc

    # -- Graph methods --------------------------------------------------------
    build_comparison_graph = ComparisonGraphService.build_comparison_graph
    save_comparison_graph = ComparisonGraphService.save_comparison_graph
    validate_graph_connectivity = ComparisonGraphService.validate_graph_connectivity
    propagate_wt_exclusion = ComparisonGraphService.propagate_wt_exclusion
    get_orphaned_wells = ComparisonGraphService.get_orphaned_wells
    compute_derived_comparisons = ComparisonGraphService.compute_derived_comparisons
    _get_primary_fold_changes = ComparisonGraphService._get_primary_fold_changes
    _get_secondary_fold_changes = ComparisonGraphService._get_secondary_fold_changes
    get_comparison_summary = ComparisonGraphService.get_comparison_summary

    # -- Precision weight methods ---------------------------------------------
    _store_precision_weights = PrecisionWeightService.store_precision_weights


__all__ = [
    "ComparisonService",
    "ComparisonError",
    "ExclusionImpact",
    "ComparisonSummary",
]
