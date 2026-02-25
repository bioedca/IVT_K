"""
Curve fitting background tasks.

PRD Reference: Phase 4, F8.6, F17.1
Implements batch curve fitting with Joblib parallelization and progress tracking.
"""
import traceback
from typing import List, Optional, Callable

from app.tasks.huey_config import huey
from app.extensions import db
from app.models.task_progress import TaskProgress, TaskType
from app.models.experiment import Plate, Well, FitStatus

# Note: TaskService is imported lazily inside functions to avoid circular import
# (task_service.py imports huey_config, which triggers __init__.py, which imports this file)


def enqueue_curve_fitting(
    project_id: int,
    plate_ids: List[int],
    username: str = None,
    model_type: str = "delayed_exponential",
    force_refit: bool = False
) -> str:
    """
    Enqueue a curve fitting task for batch processing.

    PRD Reference: F8.6 - Continue-always policy for mass failures.

    Args:
        project_id: Project to fit curves for
        plate_ids: List of plate IDs to process
        username: User who initiated the task
        model_type: Kinetic model to use (default: delayed_exponential)
        force_refit: If True, refit wells even if they already have results

    Returns:
        task_id: ID for tracking progress via TaskProgress model
    """
    # Lazy import to avoid circular import
    from app.services.task_service import TaskService

    name = f"Curve fitting: {len(plate_ids)} plate(s)"
    if force_refit:
        name += " (force refit)"

    progress = TaskService.create_task_progress(
        task_type=TaskType.CURVE_FITTING,
        name=name,
        project_id=project_id,
        username=username,
        total_steps=len(plate_ids),
        extra_data={
            "plate_ids": plate_ids,
            "model_type": model_type,
            "force_refit": force_refit
        }
    )

    # Queue the actual task
    _curve_fitting_task(progress.task_id, project_id, plate_ids, model_type, force_refit)

    return progress.task_id


def enqueue_single_plate_fitting(
    project_id: int,
    plate_id: int,
    username: str = None,
    model_type: str = "delayed_exponential"
) -> str:
    """
    Enqueue curve fitting for a single plate.

    Convenience wrapper for single-plate operations.

    Args:
        project_id: Project ID
        plate_id: Single plate to fit
        username: User who initiated
        model_type: Kinetic model to use

    Returns:
        task_id: ID for progress tracking
    """
    return enqueue_curve_fitting(
        project_id=project_id,
        plate_ids=[plate_id],
        username=username,
        model_type=model_type
    )


@huey.task()
def _curve_fitting_task(
    task_id: str,
    project_id: int,
    plate_ids: List[int],
    model_type: str,
    force_refit: bool = False
):
    """
    Background task for batch curve fitting.

    PRD Reference: F8.6 - Fit failure handling with continue-always policy.
    Failures are logged and flagged for QC review, but batch continues.

    Args:
        task_id: TaskProgress ID for updates
        project_id: Project being processed
        plate_ids: Plates to fit
        model_type: Kinetic model type
        force_refit: If True, refit wells even if they already have results
    """
    # Use lightweight worker app — only Flask + SQLAlchemy, no Dash/callbacks
    from app import create_worker_app
    server = create_worker_app()

    with server.app_context():
        progress = TaskProgress.get_by_task_id(task_id)
        if progress is None:
            return {"error": f"TaskProgress not found for {task_id}"}

        try:
            progress.start()

            # Import here to avoid circular imports
            from app.services.fitting_service import FittingService, BatchFitResult

            total_plates = len(plate_ids)
            total_wells_fitted = 0
            total_failures = 0
            total_skipped = 0

            for i, plate_id in enumerate(plate_ids):
                # Update progress with current stats in extra_data
                progress.extra_data = {
                    **(progress.extra_data or {}),
                    "successful_fits": total_wells_fitted,
                    "failed_fits": total_failures,
                    "skipped_wells": total_skipped,
                }

                progress.update_progress(
                    progress=i / total_plates,
                    current_step=f"Fitting plate {i + 1}/{total_plates}",
                    completed_steps=i
                )

                try:
                    # Fit all wells on this plate
                    result: BatchFitResult = FittingService.fit_plate(
                        plate_id=plate_id,
                        model_type=model_type,
                        force_refit=force_refit,
                    )

                    total_wells_fitted += result.successful_fits
                    total_failures += result.failed_fits
                    total_skipped += result.skipped_wells

                except Exception as e:
                    # Log plate-level error but continue with next plate
                    # PRD: Continue-always policy
                    total_failures += 1
                    import logging
                    logging.error(f"Error fitting plate {plate_id}: {e}")

            # Final progress update with complete stats
            progress.extra_data = {
                **(progress.extra_data or {}),
                "successful_fits": total_wells_fitted,
                "failed_fits": total_failures,
                "skipped_wells": total_skipped,
            }

            progress.update_progress(
                progress=1.0,
                current_step="Fitting complete",
                completed_steps=total_plates
            )

            summary = f"Fitted {total_wells_fitted} wells across {total_plates} plate(s)"
            if total_failures > 0:
                summary += f" ({total_failures} failures flagged for review)"
            if total_skipped > 0:
                summary += f" ({total_skipped} skipped)"

            progress.complete(result_summary=summary)

            return {
                "task_id": task_id,
                "wells_fitted": total_wells_fitted,
                "failures": total_failures,
                "skipped": total_skipped,
                "plates_processed": total_plates
            }

        except Exception as e:
            progress.fail(str(e), traceback.format_exc())
            return {"task_id": task_id, "error": str(e)}


@huey.task()
def refit_failed_wells_task(
    task_id: str,
    project_id: int,
    well_ids: List[int],
    model_type: str = "delayed_exponential"
):
    """
    Background task to refit specific failed wells.

    PRD Reference: F8.6 - User can retry fitting after reviewing failures.

    Args:
        task_id: TaskProgress ID
        project_id: Project ID
        well_ids: Specific wells to refit
        model_type: Model to use for refitting
    """
    # Use lightweight worker app — only Flask + SQLAlchemy, no Dash/callbacks
    from app import create_worker_app
    server = create_worker_app()

    with server.app_context():
        progress = TaskProgress.get_by_task_id(task_id)
        if progress is None:
            return {"error": f"TaskProgress not found for {task_id}"}

        try:
            progress.start()

            from app.services.fitting_service import FittingService

            fitting_service = FittingService()

            total = len(well_ids)
            successes = 0
            failures = 0

            for i, well_id in enumerate(well_ids):
                progress.update_progress(
                    progress=i / total,
                    current_step=f"Refitting well {i + 1}/{total}",
                    completed_steps=i
                )

                try:
                    result = fitting_service.fit_well(
                        well_id=well_id,
                        model_type=model_type
                    )
                    if result.get('success'):
                        successes += 1
                    else:
                        failures += 1
                except Exception:
                    failures += 1

            summary = f"Refit {successes}/{total} wells successfully"
            if failures > 0:
                summary += f" ({failures} still failed)"

            progress.complete(result_summary=summary)

            return {
                "task_id": task_id,
                "successes": successes,
                "failures": failures
            }

        except Exception as e:
            progress.fail(str(e), traceback.format_exc())
            return {"task_id": task_id, "error": str(e)}


def enqueue_refit_failed_wells(
    project_id: int,
    well_ids: List[int],
    username: str = None,
    model_type: str = "delayed_exponential"
) -> str:
    """
    Enqueue a task to refit specific failed wells.

    Args:
        project_id: Project ID
        well_ids: Wells to refit
        username: User who initiated
        model_type: Model to use

    Returns:
        task_id: ID for progress tracking
    """
    # Lazy import to avoid circular import
    from app.services.task_service import TaskService

    name = f"Refit failed wells: {len(well_ids)} well(s)"

    progress = TaskService.create_task_progress(
        task_type=TaskType.CURVE_FITTING,
        name=name,
        project_id=project_id,
        username=username,
        total_steps=len(well_ids),
        extra_data={
            "well_ids": well_ids,
            "model_type": model_type,
            "is_refit": True
        }
    )

    refit_failed_wells_task(progress.task_id, project_id, well_ids, model_type)

    return progress.task_id
