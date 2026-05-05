"""
Fitting service - backwards-compatible facade.

Phase 3 refactoring: The original monolithic FittingService has been split into:
- FitComputationService: Well/plate/project fitting, batch processing
- FoldChangeCalculationService: Fold change computation and summaries
- FitManagementService: Archival, history, quality metrics, publishing, R² filtering

This module re-exports everything under the original FittingService API
so that existing callers continue to work without changes.
"""
from app.services.fit_computation_service import (  # noqa: F401
    FitComputationService,
    FittingError,
    BatchFitProgress,
    BatchFitResult,
    BatchProcessingResult,
)
from app.services.fold_change_calculation_service import FoldChangeCalculationService
from app.services.fit_management_service import FitManagementService


class FittingService:
    """Unified fitting service delegating to specialized sub-services."""

    # Configuration (keep for compatibility)
    MIN_DATAPOINTS = FitComputationService.MIN_DATAPOINTS
    DEFAULT_MODEL = FitComputationService.DEFAULT_MODEL
    BATCH_CHUNK_SIZE = FitComputationService.BATCH_CHUNK_SIZE
    BATCH_COMMIT_INTERVAL = FitComputationService.BATCH_COMMIT_INTERVAL

    # Computation methods
    fit_well = FitComputationService.fit_well
    fit_plate = FitComputationService.fit_plate
    fit_project = FitComputationService.fit_project
    fit_project_batched = FitComputationService.fit_project_batched
    estimate_batch_time = FitComputationService.estimate_batch_time
    aggregate_split_wells = FitComputationService.aggregate_split_wells
    _update_fit_model = FitComputationService._update_fit_model

    # Fold change calculation methods
    compute_fold_change = FoldChangeCalculationService.compute_fold_change
    get_fold_change_summary = FoldChangeCalculationService.get_fold_change_summary

    # Management methods
    _archive_fit_result = FitManagementService.archive_fit_result
    get_well_fit_history = FitManagementService.get_well_fit_history
    get_archive_count = FitManagementService.get_archive_count
    _compute_signal_quality = FitManagementService.compute_signal_quality
    get_well_fit_data = FitManagementService.get_well_fit_data
    can_publish_fitting = FitManagementService.can_publish_fitting
    publish_fitting = FitManagementService.publish_fitting
    unpublish_fitting = FitManagementService.unpublish_fitting
    get_r2_exclusion_preview = FitManagementService.get_r2_exclusion_preview
    apply_r2_exclusion = FitManagementService.apply_r2_exclusion
    clear_r2_exclusions = FitManagementService.clear_r2_exclusions
    get_reliability_preview = FitManagementService.get_reliability_preview
    apply_reliability_filter = FitManagementService.apply_reliability_filter
    clear_reliability_exclusions = FitManagementService.clear_reliability_exclusions
    set_well_fc_inclusion = FitManagementService.set_well_fc_inclusion
    get_fc_exclusion_status = FitManagementService.get_fc_exclusion_status
