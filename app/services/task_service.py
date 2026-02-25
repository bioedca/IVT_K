"""
Task service for managing background task execution.

Phase 1.7: Implements F17.1 - Task enqueueing with progress tracking.
"""
import uuid
import traceback
import logging
from typing import Optional, Callable, Any
from functools import wraps

from app.extensions import db
from app.models.task_progress import TaskProgress, TaskStatus, TaskType
from app.tasks.huey_config import huey

logger = logging.getLogger(__name__)


class TaskService:
    """
    Service for managing background tasks with progress tracking.

    Provides methods to enqueue tasks and create associated TaskProgress
    records for UI progress display.
    """

    @staticmethod
    def create_task_progress(
        task_type: TaskType,
        name: str,
        project_id: int = None,
        username: str = None,
        total_steps: int = None,
        extra_data: dict = None
    ) -> TaskProgress:
        """
        Create a TaskProgress record for a new task.

        Args:
            task_type: Type of background task
            name: Human-readable task name
            project_id: Optional project association
            username: User who initiated the task
            total_steps: Total number of steps if known
            extra_data: Additional task extra_data

        Returns:
            TaskProgress: Created progress record
        """
        task_id = str(uuid.uuid4())

        progress = TaskProgress(
            task_id=task_id,
            task_type=task_type,
            name=name,
            status=TaskStatus.PENDING,
            project_id=project_id,
            username=username,
            total_steps=total_steps,
            extra_data=extra_data or {}
        )

        db.session.add(progress)
        db.session.commit()

        return progress

    @staticmethod
    def get_task_progress(task_id: str) -> Optional[TaskProgress]:
        """Get task progress by ID."""
        return TaskProgress.get_by_task_id(task_id)

    @staticmethod
    def get_active_tasks(project_id: int = None) -> list:
        """
        Get active (pending or running) tasks.

        Args:
            project_id: Optional filter by project

        Returns:
            List of TaskProgress records
        """
        query = TaskProgress.query.filter(
            TaskProgress.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING])
        )

        if project_id is not None:
            query = query.filter_by(project_id=project_id)

        return query.order_by(TaskProgress.created_at.desc()).all()

    @staticmethod
    def get_recent_tasks(limit: int = 20, project_id: int = None) -> list:
        """
        Get recent tasks for display.

        Args:
            limit: Maximum number of tasks to return
            project_id: Optional filter by project

        Returns:
            List of TaskProgress records
        """
        query = TaskProgress.query

        if project_id is not None:
            query = query.filter_by(project_id=project_id)

        return query.order_by(TaskProgress.created_at.desc()).limit(limit).all()

    @staticmethod
    def cancel_task(task_id: str) -> bool:
        """
        Cancel a pending or running task.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if cancelled, False if not found or already complete
        """
        progress = TaskProgress.get_by_task_id(task_id)
        if progress is None:
            return False

        if progress.is_complete:
            return False

        # Revoke from Huey queue if possible
        try:
            result = huey.get_storage().peek_data(task_id)
            if result:
                huey.get_storage().delete_data(task_id)
        except Exception:
            pass  # Task may already be running

        progress.cancel()
        return True


def tracked_task(task_type: TaskType):
    """
    Decorator to create tracked Huey tasks with automatic progress management.

    The decorated function should accept a `progress_callback` keyword argument
    for updating progress during execution.

    Usage:
        @tracked_task(TaskType.CURVE_FITTING)
        def fit_curves(plate_id, progress_callback=None):
            for i, well in enumerate(wells):
                # ... do work ...
                if progress_callback:
                    progress_callback(i / len(wells), f"Fitting well {well.position}")

    Args:
        task_type: Type of task for categorization
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def create_progress_wrapper(
            name: str,
            project_id: int = None,
            username: str = None,
            total_steps: int = None,
            **kwargs
        ) -> str:
            """
            Create TaskProgress and enqueue the actual task.

            Returns the task_id for progress tracking.
            """
            # Create progress record
            progress = TaskService.create_task_progress(
                task_type=task_type,
                name=name,
                project_id=project_id,
                username=username,
                total_steps=total_steps,
                extra_data=kwargs.get('extra_data', {})
            )

            # Enqueue the Huey task with task_id
            huey_task = _create_huey_task(func, progress.task_id)
            huey_task(**kwargs)

            return progress.task_id

        return create_progress_wrapper

    return decorator


def _create_huey_task(func: Callable, task_id: str) -> Callable:
    """
    Create a Huey task wrapper that manages progress updates.
    """
    @huey.task()
    def huey_wrapper(**kwargs):
        """Huey task wrapper with progress management."""
        from flask import current_app

        # Get the progress record
        progress = TaskProgress.get_by_task_id(task_id)
        if progress is None:
            return {"error": f"TaskProgress not found for {task_id}"}

        # Create progress callback
        def progress_callback(progress_value: float, current_step: str = None,
                              completed_steps: int = None):
            """Update progress from within task."""
            progress.update_progress(progress_value, current_step, completed_steps)

        try:
            # Start the task
            progress.start()

            # Run the actual function with progress callback
            result = func(progress_callback=progress_callback, **kwargs)

            # Mark complete
            summary = str(result) if result else "Task completed successfully"
            progress.complete(result_summary=summary[:1000])

            return {"task_id": task_id, "result": result}

        except Exception as e:
            # Mark failed with error details (server-side DB storage keeps str(e))
            logger.exception(f"Task {task_id} failed")
            progress.fail(
                error_message=str(e),
                traceback=traceback.format_exc()
            )
            return {"task_id": task_id, "error": "Task failed. Please try again."}

    return huey_wrapper


# Example task definitions that will be expanded in later phases
def enqueue_curve_fitting(
    project_id: int,
    plate_ids: list,
    username: str = None,
    model_type: str = "delayed_exponential"
) -> str:
    """
    Enqueue a curve fitting task.

    Args:
        project_id: Project to fit curves for
        plate_ids: List of plate IDs to process
        username: User who initiated the task
        model_type: Kinetic model to use

    Returns:
        task_id: ID for tracking progress
    """
    name = f"Curve fitting: {len(plate_ids)} plate(s)"

    progress = TaskService.create_task_progress(
        task_type=TaskType.CURVE_FITTING,
        name=name,
        project_id=project_id,
        username=username,
        total_steps=len(plate_ids),
        extra_data={"plate_ids": plate_ids, "model_type": model_type}
    )

    # Queue the actual task
    _curve_fitting_task(progress.task_id, project_id, plate_ids, model_type)

    return progress.task_id


@huey.task()
def _curve_fitting_task(task_id: str, project_id: int, plate_ids: list, model_type: str):
    """
    Background task for curve fitting.

    This is a placeholder - actual implementation will be in Phase 4.
    """
    progress = TaskProgress.get_by_task_id(task_id)
    if progress is None:
        return

    try:
        progress.start()

        # Placeholder for actual curve fitting logic
        import time
        total = len(plate_ids)
        for i, plate_id in enumerate(plate_ids):
            progress.update_progress(
                progress=i / total,
                current_step=f"Fitting plate {plate_id}",
                completed_steps=i
            )
            # Simulate work (will be replaced with actual fitting)
            time.sleep(0.1)

        progress.complete(
            result_summary=f"Fitted {total} plate(s) with {model_type} model"
        )

    except Exception as e:
        progress.fail(str(e), traceback.format_exc())


def enqueue_mcmc_sampling(
    project_id: int,
    analysis_version_id: int,
    username: str = None,
    num_samples: int = 2000,
    num_chains: int = 4
) -> str:
    """
    Enqueue an MCMC sampling task.

    Args:
        project_id: Project for analysis
        analysis_version_id: Analysis version to run
        username: User who initiated
        num_samples: Number of MCMC samples
        num_chains: Number of chains

    Returns:
        task_id: ID for tracking progress
    """
    name = f"MCMC sampling: {num_samples} samples x {num_chains} chains"

    progress = TaskService.create_task_progress(
        task_type=TaskType.MCMC_SAMPLING,
        name=name,
        project_id=project_id,
        username=username,
        total_steps=num_samples * num_chains,
        extra_data={
            "analysis_version_id": analysis_version_id,
            "num_samples": num_samples,
            "num_chains": num_chains
        }
    )

    # Queue the actual task (placeholder)
    _mcmc_sampling_task(progress.task_id, project_id, analysis_version_id,
                        num_samples, num_chains)

    return progress.task_id


@huey.task()
def _mcmc_sampling_task(task_id: str, project_id: int, analysis_version_id: int,
                        num_samples: int, num_chains: int):
    """
    Background task for MCMC sampling.

    This is a placeholder - actual implementation will be in Phase 5.
    """
    progress = TaskProgress.get_by_task_id(task_id)
    if progress is None:
        return

    try:
        progress.start()

        # Placeholder for actual MCMC logic
        import time
        total = num_samples * num_chains
        for i in range(0, total, 100):  # Simulate updates every 100 samples
            progress.update_progress(
                progress=min(1.0, i / total),
                current_step=f"Sampling: {i}/{total}",
                completed_steps=i
            )
            time.sleep(0.05)

        progress.complete(
            result_summary=f"Completed {num_samples} samples on {num_chains} chains"
        )

    except Exception as e:
        progress.fail(str(e), traceback.format_exc())
