"""
Fit management service for fit result archival, history, quality metrics, and publishing.

Extracted from fitting_service.py (Phase 3 refactoring).

Handles:
- Fit result archival and history
- Signal quality metrics computation
- Well fit data retrieval
- Fitting publication workflow (draft/publish)
- R-squared threshold filtering for FC calculation
- Well FC inclusion/exclusion
"""
import numpy as np
from datetime import datetime, timezone
from typing import Optional, List, Dict, Tuple, Any
import logging

from app.extensions import db
from app.models import (
    Project, Plate, Well, RawDataPoint
)
from app.models.fit_result import FitResult as FitResultModel, FitResultArchive, FoldChange, SignalQualityMetrics

from app.services.fit_computation_service import FittingError

logger = logging.getLogger(__name__)


def _reliability_group_key(fit) -> tuple:
    """Group key for replicate-group MAD outlier detection.

    Wells sharing (construct_id, ligand_condition, plate_id) are treated as a
    replicate set. Used by both apply_reliability_filter and
    get_reliability_preview.
    """
    well = fit.well
    construct_id = well.construct_id if well else None
    ligand = getattr(well, "ligand_condition", None) if well else None
    plate_id = well.plate_id if well else None
    return (construct_id, ligand, plate_id)


class FitManagementService:
    """
    Service for managing fit results.

    Handles archival, history, signal quality metrics,
    publication workflow, and R-squared filtering.
    """

    @classmethod
    def archive_fit_result(
        cls,
        fit_model: FitResultModel,
        superseded_by: Optional[str] = None,
        superseded_reason: Optional[str] = None
    ) -> FitResultArchive:
        """
        Archive a fit result before refitting.

        Creates a historical record preserving the original fit in the
        FitResultArchive table. This maintains a complete audit trail
        of all fits performed on each well.

        PRD Reference: Section 0.20, F8.7

        Args:
            fit_model: The FitResult to archive
            superseded_by: Username who triggered the refit (optional)
            superseded_reason: Reason for refitting (optional)

        Returns:
            The created FitResultArchive record
        """
        # Create archive record from the existing fit
        archive = FitResultArchive.from_fit_result(
            fit_result=fit_model,
            superseded_by=superseded_by,
            superseded_reason=superseded_reason
        )

        db.session.add(archive)
        # Note: We don't commit here - let the caller handle the transaction

        r_squared_str = f"{fit_model.r_squared:.3f}" if fit_model.r_squared else "N/A"
        logger.info(
            f"Archived fit result {fit_model.id} for well {fit_model.well_id} "
            f"(originally fitted at {fit_model.fitted_at}, R²={r_squared_str})"
        )

        return archive

    @classmethod
    def get_well_fit_history(
        cls,
        well_id: int,
        include_current: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get the complete fit history for a well.

        Returns all archived fits plus optionally the current fit,
        ordered by fit date (newest first).

        PRD Reference: Section 0.20, F8.7 - Well history view

        Args:
            well_id: Well ID to get history for
            include_current: Whether to include the current fit

        Returns:
            List of fit records as dictionaries, newest first
        """
        history = []

        # Get current fit if requested
        if include_current:
            current_fit = FitResultModel.query.filter_by(well_id=well_id).first()
            if current_fit:
                history.append({
                    'id': current_fit.id,
                    'is_current': True,
                    'is_archived': False,
                    'model_type': current_fit.model_type,
                    'f_max': current_fit.f_max,
                    'f_max_se': current_fit.f_max_se,
                    'k_obs': current_fit.k_obs,
                    'k_obs_se': current_fit.k_obs_se,
                    't_lag': current_fit.t_lag,
                    't_lag_se': current_fit.t_lag_se,
                    'r_squared': current_fit.r_squared,
                    'rmse': current_fit.rmse,
                    'aic': current_fit.aic,
                    'converged': current_fit.converged,
                    'fitted_at': current_fit.fitted_at,
                    'superseded_at': None,
                    'superseded_by': None,
                    'superseded_reason': None,
                })

        # Get archived fits
        archived_fits = FitResultArchive.query.filter_by(
            well_id=well_id
        ).order_by(
            FitResultArchive.superseded_at.desc()
        ).all()

        for archive in archived_fits:
            history.append({
                'id': archive.id,
                'original_fit_id': archive.original_fit_id,
                'is_current': False,
                'is_archived': True,
                'model_type': archive.model_type,
                'f_max': archive.f_max,
                'f_max_se': archive.f_max_se,
                'k_obs': archive.k_obs,
                'k_obs_se': archive.k_obs_se,
                't_lag': archive.t_lag,
                't_lag_se': archive.t_lag_se,
                'r_squared': archive.r_squared,
                'rmse': archive.rmse,
                'aic': archive.aic,
                'converged': archive.converged,
                'fitted_at': archive.original_fitted_at,
                'superseded_at': archive.superseded_at,
                'superseded_by': archive.superseded_by,
                'superseded_reason': archive.superseded_reason,
            })

        # Sort by fitted_at date (newest first)
        history.sort(key=lambda x: x['fitted_at'] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        return history

    @classmethod
    def get_archive_count(cls, well_id: int) -> int:
        """
        Get the number of archived fits for a well.

        Args:
            well_id: Well ID

        Returns:
            Count of archived fit results
        """
        return FitResultArchive.query.filter_by(well_id=well_id).count()

    @classmethod
    def compute_signal_quality(
        cls,
        fit_model: FitResultModel,
        t: np.ndarray,
        F: np.ndarray
    ) -> SignalQualityMetrics:
        """
        Compute signal quality metrics for a fit.

        Args:
            fit_model: Database fit result model
            t: Timepoints
            F: Fluorescence values

        Returns:
            SignalQualityMetrics database model
        """
        # Get or create metrics record
        metrics = SignalQualityMetrics.query.filter_by(
            fit_result_id=fit_model.id
        ).first()

        if not metrics:
            metrics = SignalQualityMetrics(fit_result_id=fit_model.id)

        # Get background from well's plate
        well = fit_model.well
        background_mean = None
        background_std = None

        # Try to get background from negative control wells on same plate
        from app.models.plate_layout import WellType
        neg_control_wells = Well.query.filter(
            Well.plate_id == well.plate_id,
            Well.well_type.in_([
                WellType.NEGATIVE_CONTROL_NO_TEMPLATE,
                WellType.NEGATIVE_CONTROL_NO_DYE,
                WellType.BLANK
            ])
        ).all()

        if neg_control_wells:
            bg_values = []
            for ncw in neg_control_wells:
                nc_data = RawDataPoint.query.filter_by(well_id=ncw.id).all()
                bg_values.extend([
                    dp.fluorescence_corrected or dp.fluorescence_raw
                    for dp in nc_data
                ])
            if bg_values:
                background_mean = np.mean(bg_values)
                background_std = np.std(bg_values)

        # Compute SNR (Signal-to-Noise Ratio)
        # SNR = (F_max) / std(noise)
        if fit_model.f_max and background_std and background_std > 0:
            metrics.snr = fit_model.f_max / background_std

        # Compute SBR (Signal-to-Background Ratio)
        # SBR = F_max / mean(background)
        if fit_model.f_max and background_mean and background_mean > 0:
            metrics.sbr = fit_model.f_max / background_mean

        # Detection limits
        # LOD = 3 * std(background)
        # LOQ = 10 * std(background)
        if background_std:
            metrics.lod_value = 3 * background_std
            metrics.loq_value = 10 * background_std

            if fit_model.f_max:
                metrics.above_lod = fit_model.f_max > metrics.lod_value
                metrics.above_loq = fit_model.f_max > metrics.loq_value

            # Minimum detectable fold change
            # Based on LOD relative to typical signal
            if fit_model.f_max and fit_model.f_max > 0:
                metrics.min_detectable_fc = metrics.lod_value / fit_model.f_max

        metrics.computed_at = datetime.now(timezone.utc)
        db.session.add(metrics)
        db.session.commit()

        return metrics

    @classmethod
    def get_well_fit_data(cls, well_id: int) -> Dict[str, Any]:
        """
        Get complete fit data for a well including raw data and fit curve.

        Useful for visualization.

        Args:
            well_id: Well ID

        Returns:
            Dict with timepoints, raw_data, fit_curve, parameters, statistics
        """
        well = Well.query.get(well_id)
        if not well:
            raise FittingError(f"Well {well_id} not found")

        # Get raw data
        raw_data = RawDataPoint.query.filter_by(well_id=well_id).order_by(
            RawDataPoint.timepoint
        ).all()

        t = np.array([dp.timepoint for dp in raw_data])
        F_raw = np.array([dp.fluorescence_raw for dp in raw_data])
        F_corrected = np.array([
            dp.fluorescence_corrected if dp.fluorescence_corrected is not None
            else dp.fluorescence_raw
            for dp in raw_data
        ])

        result = {
            "well_id": well_id,
            "position": well.position,
            "plate_number": well.plate.plate_number if well.plate else "?",
            "timepoints": t.tolist(),
            "fluorescence_raw": F_raw.tolist(),
            "fluorescence_corrected": F_corrected.tolist(),
            "fit_curve": None,
            "parameters": None,
            "statistics": None
        }

        # Get fit result
        fit_model = FitResultModel.query.filter_by(well_id=well_id).first()
        if fit_model and fit_model.converged:
            # Generate fit curve
            from app.analysis.kinetic_models import ModelParameters, get_model

            params = ModelParameters()
            params.set("F_baseline", fit_model.f_baseline or 0)
            params.set("F_max", fit_model.f_max or 0)
            params.set("k_obs", fit_model.k_obs or 0)
            params.set("t_lag", fit_model.t_lag or 0)

            model = get_model(fit_model.model_type)

            # Generate smooth curve for plotting
            if len(t) == 0:
                return result
            t_smooth = np.linspace(t.min(), t.max(), 100)
            F_fit = model.evaluate(t_smooth, params)

            result["fit_curve"] = {
                "timepoints": t_smooth.tolist(),
                "values": F_fit.tolist()
            }

            result["parameters"] = {
                "F_baseline": {"value": fit_model.f_baseline, "se": fit_model.f_baseline_se},
                "F_max": {"value": fit_model.f_max, "se": fit_model.f_max_se},
                "k_obs": {"value": fit_model.k_obs, "se": fit_model.k_obs_se},
                "t_lag": {"value": fit_model.t_lag, "se": fit_model.t_lag_se}
            }

            result["statistics"] = {
                "r_squared": fit_model.r_squared,
                "rmse": fit_model.rmse,
                "aic": fit_model.aic,
                "converged": fit_model.converged
            }

            # Add signal quality if available
            if fit_model.signal_quality:
                sq = fit_model.signal_quality
                result["signal_quality"] = {
                    "snr": sq.snr,
                    "sbr": sq.sbr,
                    "above_lod": sq.above_lod,
                    "above_loq": sq.above_loq
                }

        return result

    # ================================================================
    # Fitting Publication Workflow (Draft/Publish)
    # ================================================================

    @classmethod
    def can_publish_fitting(cls, project_id: int) -> Tuple[bool, List[str]]:
        """
        Check if fitting results can be published.

        Requirements:
        - At least one successful fit must exist
        - Fold changes must be computed

        Args:
            project_id: Project ID to check

        Returns:
            Tuple of (can_publish: bool, blockers: List[str])
        """
        blockers = []

        project = Project.query.get(project_id)
        if not project:
            return False, ["Project not found"]

        # Check for at least one successful fit
        from app.models import Well, Plate, ExperimentalSession
        from app.models.plate_layout import WellType

        fit_count = FitResultModel.query.join(Well).join(Plate).join(ExperimentalSession).filter(
            ExperimentalSession.project_id == project_id,
            FitResultModel.converged == True,
            Well.well_type == WellType.SAMPLE
        ).count()

        if fit_count == 0:
            blockers.append("No successful curve fits found")

        # Check for fold changes
        fc_count = FoldChange.query.join(
            Well, FoldChange.test_well_id == Well.id
        ).join(Plate).join(ExperimentalSession).filter(
            ExperimentalSession.project_id == project_id
        ).count()

        if fc_count == 0:
            blockers.append("No fold changes computed")

        return len(blockers) == 0, blockers

    @classmethod
    def publish_fitting(cls, project_id: int, username: str) -> bool:
        """
        Publish fitting results, enabling hierarchical analysis.

        Args:
            project_id: Project ID
            username: User publishing the results

        Returns:
            True if successful

        Raises:
            FittingError: If cannot publish
        """
        can_publish, blockers = cls.can_publish_fitting(project_id)
        if not can_publish:
            raise FittingError(f"Cannot publish fitting: {'; '.join(blockers)}")

        project = Project.query.get(project_id)
        project.fitting_published = True
        project.fitting_published_at = datetime.now(timezone.utc)
        project.fitting_published_by = username

        db.session.commit()

        logger.info(f"Fitting published for project {project_id} by {username}")
        return True

    @classmethod
    def unpublish_fitting(cls, project_id: int, username: str) -> bool:
        """
        Revert fitting results to draft state, invalidating downstream results.

        Args:
            project_id: Project ID
            username: User reverting the results

        Returns:
            True if successful
        """
        project = Project.query.get(project_id)
        if not project:
            raise FittingError(f"Project {project_id} not found")

        project.fitting_published = False
        project.fitting_published_at = None
        project.fitting_published_by = None
        project.results_valid = False  # Invalidate downstream results

        db.session.commit()

        logger.info(f"Fitting unpublished for project {project_id} by {username}")
        return True

    # ================================================================
    # R-squared Threshold Filtering for FC Calculation
    # ================================================================

    @classmethod
    def get_r2_exclusion_preview(
        cls,
        project_id: int,
        threshold: float = 0.8
    ) -> dict[str, Any]:
        """
        Preview which wells would be excluded based on R-squared threshold.

        Args:
            project_id: Project ID
            threshold: R-squared threshold (wells below this will be flagged)

        Returns:
            Dict with:
            - total_wells: Total number of fitted wells
            - below_threshold: Count of wells below threshold
            - well_ids: List of well IDs that would be excluded
            - by_plate: Dict of plate_id -> count below threshold
        """
        from app.models.plate_layout import WellType

        # Get all successful fits for SAMPLE wells in this project
        fits = FitResultModel.query.join(Well).join(Plate).join(
            Plate.session
        ).filter(
            Plate.session.has(project_id=project_id),
            FitResultModel.converged == True,
            Well.well_type == WellType.SAMPLE,
            Well.is_excluded == False,
        ).all()

        total_wells = len(fits)
        below_threshold = []
        by_plate: dict[int, int] = {}

        for fit in fits:
            r2 = fit.r_squared or 0
            if r2 < threshold:
                below_threshold.append(fit.well_id)
                plate_id = fit.well.plate_id
                by_plate[plate_id] = by_plate.get(plate_id, 0) + 1

        return {
            "total_wells": total_wells,
            "below_threshold": len(below_threshold),
            "well_ids": below_threshold,
            "by_plate": by_plate,
            "threshold": threshold,
        }

    @classmethod
    def apply_r2_exclusion(
        cls,
        project_id: int,
        threshold: float = 0.8
    ) -> dict[str, Any]:
        """
        Mark wells with R-squared below threshold as excluded from FC calculation.

        Thin wrapper over apply_reliability_filter for back-compat.

        Args:
            project_id: Project ID
            threshold: R-squared threshold (wells below this will be flagged)

        Returns:
            Dict with count of wells excluded
        """
        from app.analysis.fit_reliability import ReliabilityThresholds

        thresholds = ReliabilityThresholds(
            r2_threshold=threshold,
            check_outliers=False,
            check_shape=False,
            # Disable plateau / fmax-SE gating: this wrapper is R²-only.
            pct_plateau_bad=0.0,
            pct_plateau_weak=0.0,
            pct_plateau_good=0.0,
            f_max_se_pct_bad=float("inf"),
            f_max_se_pct_weak=float("inf"),
            f_max_se_pct_good=float("inf"),
        )
        result = cls.apply_reliability_filter(project_id, thresholds)
        return {
            "excluded_count": result["excluded_count"],
            "excluded_well_ids": result["excluded_well_ids"],
            "threshold": threshold,
        }

    @classmethod
    def get_reliability_preview(
        cls,
        project_id: int,
        thresholds: "ReliabilityThresholds",
    ) -> dict[str, Any]:
        """Preview which wells would be excluded under current thresholds.

        Returns counts and per-reason breakdown without writing to the DB.
        """
        from app.analysis.fit_reliability import (
            ReliabilityFlag,
            FilterReason,
            evaluate_batch,
        )
        from app.models.plate_layout import WellType

        fits = FitResultModel.query.join(Well).join(Plate).join(
            Plate.session
        ).filter(
            Plate.session.has(project_id=project_id),
            FitResultModel.converged == True,  # noqa: E712
            Well.well_type == WellType.SAMPLE,
            Well.is_excluded == False,  # noqa: E712
        ).all()

        if not fits:
            return {
                "total_wells": 0,
                "below_threshold": 0,
                "well_ids": [],
                "by_reason": {},
                "by_flag": {flag.value: 0 for flag in ReliabilityFlag},
            }

        results = evaluate_batch(
            fits, thresholds=thresholds, group_key=_reliability_group_key
        )

        excluded_ids: list[int] = []
        by_reason: dict[str, int] = {}
        by_flag: dict[str, int] = {flag.value: 0 for flag in ReliabilityFlag}

        for fit in fits:
            res = results[fit.id]
            by_flag[res.flag.value] += 1
            if res.is_excluded_by(thresholds):
                excluded_ids.append(fit.well_id)
                for reason in res.reasons:
                    if reason is FilterReason.OK:
                        continue
                    by_reason[reason.value] = by_reason.get(reason.value, 0) + 1

        return {
            "total_wells": len(fits),
            "below_threshold": len(excluded_ids),
            "well_ids": excluded_ids,
            "by_reason": by_reason,
            "by_flag": by_flag,
        }

    @classmethod
    def apply_reliability_filter(
        cls,
        project_id: int,
        thresholds: "ReliabilityThresholds",
    ) -> dict[str, Any]:
        """Mark wells failing the reliability evaluator as excluded from FC.

        Resets all SAMPLE wells in the project to included, then re-applies the
        filter. Action is determined by ``thresholds.exclude_weak``: if True,
        WEAK fits are also excluded; otherwise only BAD fits are excluded.
        """
        from app.analysis.fit_reliability import (
            ReliabilityFlag,
            FilterReason,
            evaluate_batch,
        )
        from app.models.plate_layout import WellType

        wells_to_reset = Well.query.join(Plate).join(
            Plate.session
        ).filter(
            Plate.session.has(project_id=project_id),
            Well.well_type == WellType.SAMPLE,
        ).all()
        for well in wells_to_reset:
            well.exclude_from_fc = False

        fits = FitResultModel.query.join(Well).join(Plate).join(
            Plate.session
        ).filter(
            Plate.session.has(project_id=project_id),
            FitResultModel.converged == True,  # noqa: E712
            Well.well_type == WellType.SAMPLE,
            Well.is_excluded == False,  # noqa: E712
        ).all()

        if not fits:
            db.session.commit()
            return {
                "excluded_count": 0,
                "excluded_well_ids": [],
                "by_reason": {},
                "by_flag": {flag.value: 0 for flag in ReliabilityFlag},
            }

        results = evaluate_batch(
            fits, thresholds=thresholds, group_key=_reliability_group_key
        )

        excluded_ids: list[int] = []
        by_reason: dict[str, int] = {}
        by_flag: dict[str, int] = {flag.value: 0 for flag in ReliabilityFlag}

        for fit in fits:
            res = results[fit.id]
            by_flag[res.flag.value] += 1
            if res.is_excluded_by(thresholds):
                fit.well.exclude_from_fc = True
                excluded_ids.append(fit.well_id)
                for reason in res.reasons:
                    if reason is FilterReason.OK:
                        continue
                    by_reason[reason.value] = by_reason.get(reason.value, 0) + 1

        db.session.commit()

        logger.info(
            "Applied reliability filter to project %s: %d wells excluded "
            "(by_reason=%s)",
            project_id,
            len(excluded_ids),
            by_reason,
        )

        return {
            "excluded_count": len(excluded_ids),
            "excluded_well_ids": excluded_ids,
            "by_reason": by_reason,
            "by_flag": by_flag,
        }

    @classmethod
    def clear_reliability_exclusions(cls, project_id: int) -> int:
        """Alias for clear_r2_exclusions; retained for naming clarity."""
        return cls.clear_r2_exclusions(project_id)

    @classmethod
    def clear_r2_exclusions(cls, project_id: int) -> int:
        """
        Clear all R-squared exclusions for a project (include all wells in FC).

        Args:
            project_id: Project ID

        Returns:
            Count of wells that were un-excluded
        """
        from app.models.plate_layout import WellType

        wells = Well.query.join(Plate).join(
            Plate.session
        ).filter(
            Plate.session.has(project_id=project_id),
            Well.well_type == WellType.SAMPLE,
            Well.exclude_from_fc == True,
        ).all()

        count = len(wells)
        for well in wells:
            well.exclude_from_fc = False

        db.session.commit()

        logger.info(f"Cleared R² exclusions for project {project_id}: {count} wells re-included")

        return count

    @classmethod
    def set_well_fc_inclusion(
        cls,
        well_id: int,
        include: bool
    ) -> bool:
        """
        Toggle individual well inclusion in FC calculation.

        Args:
            well_id: Well ID
            include: True to include in FC, False to exclude

        Returns:
            True if successful
        """
        well = Well.query.get(well_id)
        if not well:
            raise FittingError(f"Well {well_id} not found")

        well.exclude_from_fc = not include
        db.session.commit()

        logger.info(
            f"Well {well_id} {'included in' if include else 'excluded from'} "
            f"FC calculation"
        )

        return True

    @classmethod
    def get_fc_exclusion_status(cls, project_id: int) -> dict[str, Any]:
        """
        Get current FC exclusion status for a project.

        Args:
            project_id: Project ID

        Returns:
            Dict with exclusion counts and details
        """
        from app.models.plate_layout import WellType

        # Get all SAMPLE wells with successful fits
        fits = FitResultModel.query.join(Well).join(Plate).join(
            Plate.session
        ).filter(
            Plate.session.has(project_id=project_id),
            FitResultModel.converged == True,
            Well.well_type == WellType.SAMPLE,
            Well.is_excluded == False,
        ).all()

        total = len(fits)
        excluded = sum(1 for f in fits if f.well.exclude_from_fc)
        included = total - excluded

        # Get R² stats for excluded wells
        excluded_r2_values = [
            f.r_squared for f in fits
            if f.well.exclude_from_fc and f.r_squared is not None
        ]

        return {
            "total_fitted_wells": total,
            "included_in_fc": included,
            "excluded_from_fc": excluded,
            "excluded_r2_range": {
                "min": min(excluded_r2_values) if excluded_r2_values else None,
                "max": max(excluded_r2_values) if excluded_r2_values else None,
            },
        }
