"""
Fit computation service for curve fitting operations.

Extracted from fitting_service.py (Phase 3 refactoring).

Handles:
- Individual well fitting
- Batch plate fitting with failure resilience
- Project-level fitting (standard and batched)
- Split well aggregation
"""
import numpy as np
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
import logging

from app.extensions import db
from app.models import (
    Project, Plate, Well, RawDataPoint, ExperimentalSession
)
from app.models.experiment import FitStatus, QCStatus
from app.models.fit_result import FitResult as FitResultModel
from app.analysis.curve_fitting import CurveFitter, FitResult
from app.analysis.kinetic_models import get_model

logger = logging.getLogger(__name__)


class FittingError(Exception):
    """Raised when fitting operations fail."""
    pass


@dataclass
class BatchFitProgress:
    """Progress tracking for batch fitting operations."""
    total_wells: int
    completed_wells: int = 0
    successful_fits: int = 0
    failed_fits: int = 0
    skipped_wells: int = 0
    current_well: Optional[str] = None

    @property
    def progress_fraction(self) -> float:
        """Get progress as fraction 0-1."""
        return self.completed_wells / self.total_wells if self.total_wells > 0 else 0

    @property
    def progress_percent(self) -> float:
        """Get progress as percentage."""
        return self.progress_fraction * 100


@dataclass
class BatchFitResult:
    """Result of a batch fitting operation."""
    plate_id: int
    total_wells: int
    successful_fits: int
    failed_fits: int
    skipped_wells: int
    fit_results: List[int] = field(default_factory=list)  # FitResult IDs
    failed_well_ids: List[int] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Fraction of successful fits."""
        attempted = self.successful_fits + self.failed_fits
        return self.successful_fits / attempted if attempted > 0 else 0


@dataclass
class BatchProcessingResult:
    """
    Result of batched project fitting.

    PRD Reference: Section 0.6 - Batch processing for large projects
    """
    project_id: int
    total_plates: int
    successful_fits: int
    failed_fits: int
    skipped_wells: int
    chunks_processed: int
    plate_results: List[BatchFitResult]
    warnings: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Overall success rate across all plates."""
        total_attempted = self.successful_fits + self.failed_fits
        return self.successful_fits / total_attempted if total_attempted > 0 else 0

    @property
    def has_warnings(self) -> bool:
        """Whether any warnings were generated."""
        return len(self.warnings) > 0


class FitComputationService:
    """
    Service for curve fitting computation.

    Handles individual well fitting, batch plate fitting,
    project-level fitting, and split well aggregation.
    """

    # Configuration
    MIN_DATAPOINTS = 5  # Minimum data points for fitting
    DEFAULT_MODEL = "delayed_exponential"

    # Configuration for batch processing
    BATCH_CHUNK_SIZE = 25  # Process 25 plates per chunk
    BATCH_COMMIT_INTERVAL = 5  # Commit every 5 plates

    @classmethod
    def fit_well(
        cls,
        well_id: int,
        model_type: str = DEFAULT_MODEL,
        force_refit: bool = False,
        archive_existing: bool = True,
        refit_by: Optional[str] = None,
        refit_reason: Optional[str] = None
    ) -> FitResultModel:
        """
        Fit a kinetic model to a single well's data.

        Args:
            well_id: Well ID to fit
            model_type: Model type name
            force_refit: If True, refit even if existing result
            archive_existing: If True, archive existing result before refitting
            refit_by: Username who triggered the refit (for audit trail)
            refit_reason: Reason for refitting (for audit trail)

        Returns:
            FitResult database model

        Raises:
            FittingError: If well not found or fitting fails critically
        """
        well = Well.query.get(well_id)
        if not well:
            raise FittingError(f"Well {well_id} not found")

        # Check for existing fit
        existing_fit = FitResultModel.query.filter_by(well_id=well_id).first()
        if existing_fit and not force_refit:
            return existing_fit

        # Archive existing fit if requested
        if existing_fit and archive_existing:
            from app.services.fit_management_service import FitManagementService
            FitManagementService.archive_fit_result(
                existing_fit,
                superseded_by=refit_by,
                superseded_reason=refit_reason
            )

        # Get raw data
        raw_data = RawDataPoint.query.filter_by(well_id=well_id).order_by(
            RawDataPoint.timepoint
        ).all()

        if len(raw_data) < cls.MIN_DATAPOINTS:
            # Mark well as needing review
            well.fit_status = FitStatus.NEEDS_REVIEW
            db.session.commit()
            raise FittingError(
                f"Insufficient data points: {len(raw_data)} < {cls.MIN_DATAPOINTS}"
            )

        # Prepare data arrays
        t = np.array([dp.timepoint for dp in raw_data])
        # Use corrected fluorescence if available, otherwise raw
        F = np.array([
            dp.fluorescence_corrected if dp.fluorescence_corrected is not None
            else dp.fluorescence_raw
            for dp in raw_data
        ])

        # Perform fit
        model = get_model(model_type)
        fitter = CurveFitter(model)
        fit_result = fitter.fit(t, F)

        # Create or update database record
        if existing_fit:
            fit_model = existing_fit
        else:
            fit_model = FitResultModel(well_id=well_id)

        cls._update_fit_model(fit_model, fit_result, model_type)
        db.session.add(fit_model)

        # Update well status
        if fit_result.converged:
            well.fit_status = FitStatus.SUCCESS
        elif fit_result.recovery_stage >= 3:
            well.fit_status = FitStatus.NEEDS_REVIEW
        else:
            well.fit_status = FitStatus.FAILED

        db.session.commit()

        # Compute signal quality metrics
        from app.services.fit_management_service import FitManagementService
        FitManagementService.compute_signal_quality(fit_model, t, F)

        return fit_model

    @classmethod
    def fit_plate(
        cls,
        plate_id: int,
        model_type: str = DEFAULT_MODEL,
        force_refit: bool = False,
        progress_callback: Optional[Callable[[BatchFitProgress], None]] = None
    ) -> BatchFitResult:
        """
        Fit all wells in a plate with failure resilience.

        The fitting continues even if individual wells fail (continue-always policy).

        Args:
            plate_id: Plate ID to fit
            model_type: Model type name
            force_refit: If True, refit even if existing results
            progress_callback: Optional callback for progress updates

        Returns:
            BatchFitResult with summary statistics
        """
        plate = Plate.query.get(plate_id)
        if not plate:
            raise FittingError(f"Plate {plate_id} not found")

        # Import WellType for filtering - only fit SAMPLE wells
        from app.models.plate_layout import WellType

        wells = Well.query.filter_by(plate_id=plate_id).all()

        # Only fit wells explicitly marked as SAMPLE
        # EMPTY, BLANK, NEGATIVE_CONTROL_* wells are NOT fitted
        sample_wells = [w for w in wells if w.well_type == WellType.SAMPLE]
        non_sample_wells = [w for w in wells if w.well_type != WellType.SAMPLE]

        # Clean up any existing fit results for non-SAMPLE wells (draft cleanup)
        # This removes orphaned fits from wells that were previously fitted
        # but are now identified as controls/blanks
        if non_sample_wells:
            non_sample_ids = [w.id for w in non_sample_wells]
            orphaned_fits = FitResultModel.query.filter(
                FitResultModel.well_id.in_(non_sample_ids)
            ).all()
            for fit in orphaned_fits:
                db.session.delete(fit)
            if orphaned_fits:
                db.session.commit()
                logger.info(f"Cleaned up {len(orphaned_fits)} orphaned fit results for non-SAMPLE wells")

        progress = BatchFitProgress(total_wells=len(sample_wells))
        result = BatchFitResult(
            plate_id=plate_id,
            total_wells=len(wells),
            successful_fits=0,
            failed_fits=0,
            skipped_wells=len(wells) - len(sample_wells)  # Count neg controls as skipped
        )

        for well in sample_wells:
            progress.current_well = well.position

            # Skip excluded wells
            if well.is_excluded:
                progress.skipped_wells += 1
                result.skipped_wells += 1
                progress.completed_wells += 1
                if progress_callback:
                    progress_callback(progress)
                continue

            # Check for sufficient data
            data_count = RawDataPoint.query.filter_by(well_id=well.id).count()
            if data_count < cls.MIN_DATAPOINTS:
                progress.skipped_wells += 1
                result.skipped_wells += 1
                result.warnings.append(f"{well.position}: insufficient data ({data_count} points)")
                progress.completed_wells += 1
                if progress_callback:
                    progress_callback(progress)
                continue

            try:
                fit_model = cls.fit_well(
                    well.id,
                    model_type=model_type,
                    force_refit=force_refit
                )
                progress.successful_fits += 1
                result.successful_fits += 1
                result.fit_results.append(fit_model.id)
            except FittingError as e:
                progress.failed_fits += 1
                result.failed_fits += 1
                result.failed_well_ids.append(well.id)
                result.warnings.append(f"{well.position}: Curve fitting failed for this well")
                logger.warning(f"Fit failed for well {well.position}: {e}")

            progress.completed_wells += 1
            if progress_callback:
                progress_callback(progress)

        return result

    @classmethod
    def fit_project(
        cls,
        project_id: int,
        model_type: str = DEFAULT_MODEL,
        force_refit: bool = False,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[BatchFitResult]:
        """
        Fit all plates in a project.

        Args:
            project_id: Project ID
            model_type: Model type name
            force_refit: If True, refit all wells
            progress_callback: Optional callback(completed_plates, total_plates)

        Returns:
            List of BatchFitResult, one per plate
        """
        project = Project.query.get(project_id)
        if not project:
            raise FittingError(f"Project {project_id} not found")

        # Get all plates from sessions that are NOT QC rejected
        # Plates from rejected sessions are excluded from fitting
        plates = Plate.query.join(Plate.session).filter(
            ExperimentalSession.project_id == project_id,
            ExperimentalSession.qc_status != QCStatus.REJECTED
        ).all()

        results = []
        for i, plate in enumerate(plates):
            result = cls.fit_plate(plate.id, model_type, force_refit)
            results.append(result)

            if progress_callback:
                progress_callback(i + 1, len(plates))

        return results

    @classmethod
    def fit_project_batched(
        cls,
        project_id: int,
        model_type: str = DEFAULT_MODEL,
        force_refit: bool = False,
        chunk_size: Optional[int] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> 'BatchProcessingResult':
        """
        Fit all plates in a large project using chunked batch processing.

        PRD Reference: Section 0.6 - Batch processing mode for 100+ plates

        For projects with many plates (100+), this method processes plates
        in configurable chunks to manage memory and provide better progress
        feedback. Results are committed to database after each chunk.

        Args:
            project_id: Project ID
            model_type: Model type name
            force_refit: If True, refit all wells
            chunk_size: Plates per chunk (default: 25)
            progress_callback: Callback with detailed progress info:
                {
                    'chunk': current_chunk_number,
                    'total_chunks': total_chunk_count,
                    'plate': current_plate_in_chunk,
                    'plates_in_chunk': plates_in_this_chunk,
                    'total_plates': total_plate_count,
                    'completed_plates': total_completed_so_far,
                    'current_plate_id': id_of_plate_being_processed
                }

        Returns:
            BatchProcessingResult with aggregated statistics
        """
        from dataclasses import dataclass, field as dc_field

        @dataclass
        class ChunkResult:
            """Result of processing a single chunk."""
            chunk_number: int
            plates_processed: int
            successful_fits: int
            failed_fits: int
            warnings: List[str] = dc_field(default_factory=list)

        project = Project.query.get(project_id)
        if not project:
            raise FittingError(f"Project {project_id} not found")

        # Get all plates from sessions that are NOT QC rejected
        # Plates from rejected sessions are excluded from fitting
        plates = Plate.query.join(Plate.session).filter(
            ExperimentalSession.project_id == project_id,
            ExperimentalSession.qc_status != QCStatus.REJECTED
        ).order_by(Plate.id).all()

        total_plates = len(plates)

        # For small projects, use regular fit_project
        if total_plates < 50:
            logger.info(
                f"Project {project_id} has {total_plates} plates, "
                "using standard processing"
            )
            results = cls.fit_project(
                project_id, model_type, force_refit,
                lambda completed, total: progress_callback({
                    'chunk': 1,
                    'total_chunks': 1,
                    'plate': completed,
                    'plates_in_chunk': total,
                    'total_plates': total,
                    'completed_plates': completed,
                    'current_plate_id': None
                }) if progress_callback else None
            )

            return BatchProcessingResult(
                project_id=project_id,
                total_plates=total_plates,
                successful_fits=sum(r.successful_fits for r in results),
                failed_fits=sum(r.failed_fits for r in results),
                skipped_wells=sum(r.skipped_wells for r in results),
                chunks_processed=1,
                plate_results=results,
                warnings=[]
            )

        # Use chunked processing for large projects
        chunk_size = chunk_size or cls.BATCH_CHUNK_SIZE
        total_chunks = (total_plates + chunk_size - 1) // chunk_size

        logger.info(
            f"Processing large project {project_id}: {total_plates} plates "
            f"in {total_chunks} chunks of {chunk_size}"
        )

        all_results = []
        chunk_summaries = []
        completed_plates = 0

        for chunk_idx in range(total_chunks):
            chunk_start = chunk_idx * chunk_size
            chunk_end = min(chunk_start + chunk_size, total_plates)
            chunk_plates = plates[chunk_start:chunk_end]

            chunk_successful = 0
            chunk_failed = 0
            chunk_warnings = []

            for plate_idx, plate in enumerate(chunk_plates):
                try:
                    # Report progress
                    if progress_callback:
                        progress_callback({
                            'chunk': chunk_idx + 1,
                            'total_chunks': total_chunks,
                            'plate': plate_idx + 1,
                            'plates_in_chunk': len(chunk_plates),
                            'total_plates': total_plates,
                            'completed_plates': completed_plates,
                            'current_plate_id': plate.id
                        })

                    # Fit the plate
                    result = cls.fit_plate(plate.id, model_type, force_refit)
                    all_results.append(result)

                    chunk_successful += result.successful_fits
                    chunk_failed += result.failed_fits

                    if result.warnings:
                        chunk_warnings.extend(result.warnings)

                    completed_plates += 1

                    # Periodic commit within chunk
                    if (plate_idx + 1) % cls.BATCH_COMMIT_INTERVAL == 0:
                        db.session.commit()

                except Exception as e:
                    logger.error(f"Error fitting plate {plate.id}", exc_info=True)
                    chunk_warnings.append(f"Plate {plate.id}: Fitting encountered an error")
                    chunk_failed += 1
                    completed_plates += 1

            # Commit after each chunk
            db.session.commit()

            chunk_summaries.append(ChunkResult(
                chunk_number=chunk_idx + 1,
                plates_processed=len(chunk_plates),
                successful_fits=chunk_successful,
                failed_fits=chunk_failed,
                warnings=chunk_warnings
            ))

            logger.info(
                f"Completed chunk {chunk_idx + 1}/{total_chunks}: "
                f"{len(chunk_plates)} plates, {chunk_successful} successes, "
                f"{chunk_failed} failures"
            )

        # Aggregate results
        return BatchProcessingResult(
            project_id=project_id,
            total_plates=total_plates,
            successful_fits=sum(r.successful_fits for r in all_results),
            failed_fits=sum(r.failed_fits for r in all_results),
            skipped_wells=sum(r.skipped_wells for r in all_results),
            chunks_processed=total_chunks,
            plate_results=all_results,
            warnings=[w for cs in chunk_summaries for w in cs.warnings]
        )

    @classmethod
    def estimate_batch_time(
        cls,
        project_id: int,
        seconds_per_well: float = 0.5
    ) -> Dict[str, Any]:
        """
        Estimate time required for batch fitting a project.

        PRD Reference: Section 0.6 - Performance expectations

        Args:
            project_id: Project ID
            seconds_per_well: Estimated time per well (default 0.5s)

        Returns:
            Dict with:
            - total_plates: int
            - total_wells: int
            - estimated_seconds: float
            - estimated_minutes: float
            - recommended_chunks: int
            - is_large_project: bool
        """
        from sqlalchemy import func

        # Count plates
        plate_count = Plate.query.join(Plate.session).filter_by(
            project_id=project_id
        ).count()

        # Count wells
        well_count = db.session.query(func.count(Well.id)).join(
            Plate, Well.plate_id == Plate.id
        ).join(
            Plate.session
        ).filter_by(
            project_id=project_id
        ).scalar() or 0

        estimated_seconds = well_count * seconds_per_well
        is_large = plate_count >= 100

        return {
            'total_plates': plate_count,
            'total_wells': well_count,
            'estimated_seconds': estimated_seconds,
            'estimated_minutes': estimated_seconds / 60,
            'recommended_chunks': (plate_count + cls.BATCH_CHUNK_SIZE - 1) // cls.BATCH_CHUNK_SIZE,
            'is_large_project': is_large,
            'use_batched_processing': is_large
        }

    @classmethod
    def aggregate_split_wells(
        cls,
        reaction_id: int,
        model_type: str = DEFAULT_MODEL
    ) -> FitResultModel:
        """
        Aggregate data from split wells and fit as single reaction.

        For split-well designs where one reaction spans multiple wells.

        Args:
            reaction_id: Reaction ID (links multiple wells)
            model_type: Model type name

        Returns:
            FitResult for the aggregated data
        """
        from app.models.experiment import Reaction

        reaction = Reaction.query.get(reaction_id)
        if not reaction:
            raise FittingError(f"Reaction {reaction_id} not found")

        wells = [w for w in reaction.wells if not w.is_excluded]

        if not wells:
            raise FittingError(f"No valid wells for reaction {reaction_id}")

        # Aggregate data
        # For each timepoint, average fluorescence across wells
        timepoints_data = {}

        for well in wells:
            raw_data = RawDataPoint.query.filter_by(well_id=well.id).all()
            for dp in raw_data:
                t = dp.timepoint
                F = dp.fluorescence_corrected or dp.fluorescence_raw
                if t not in timepoints_data:
                    timepoints_data[t] = []
                timepoints_data[t].append(F)

        # Sort by timepoint and compute means
        sorted_times = sorted(timepoints_data.keys())
        t = np.array(sorted_times)
        F = np.array([np.mean(timepoints_data[time]) for time in sorted_times])

        # Fit aggregated data
        model = get_model(model_type)
        fitter = CurveFitter(model)
        fit_result = fitter.fit(t, F)

        # Store result on first well (could also create a separate reaction-level result)
        primary_well = wells[0]
        fit_model = FitResultModel.query.filter_by(well_id=primary_well.id).first()

        if not fit_model:
            fit_model = FitResultModel(well_id=primary_well.id)

        cls._update_fit_model(fit_model, fit_result, model_type)
        db.session.add(fit_model)
        db.session.commit()

        return fit_model

    @classmethod
    def _update_fit_model(
        cls,
        fit_model: FitResultModel,
        fit_result: FitResult,
        model_type: str
    ) -> None:
        """Update database model from fit result."""
        fit_model.model_type = model_type
        fit_model.converged = fit_result.converged

        # Parameters
        fit_model.f_baseline = fit_result.get_param("F_baseline")
        fit_model.f_baseline_se = fit_result.get_param_se("F_baseline")
        fit_model.f_max = fit_result.get_param("F_max")
        fit_model.f_max_se = fit_result.get_param_se("F_max")
        fit_model.k_obs = fit_result.get_param("k_obs")
        fit_model.k_obs_se = fit_result.get_param_se("k_obs")
        fit_model.t_lag = fit_result.get_param("t_lag")
        fit_model.t_lag_se = fit_result.get_param_se("t_lag")

        # Statistics
        fit_model.r_squared = fit_result.statistics.r_squared
        fit_model.rmse = fit_result.statistics.rmse
        fit_model.aic = fit_result.statistics.aic
        fit_model.residual_normality_pvalue = fit_result.statistics.residual_normality_pvalue

        fit_model.fitted_at = datetime.now(timezone.utc)
