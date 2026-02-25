"""
Task progress service for state transitions on background tasks.

Provides service-layer entry points for TaskProgress state management,
extracted from model instance methods (Phase 2 refactoring).
"""
import logging
from typing import Optional

from app.extensions import db
from app.models.task_progress import TaskProgress, TaskStatus

logger = logging.getLogger(__name__)


class TaskProgressService:
    """
    Service for TaskProgress state transitions.

    Wraps model instance methods to provide consistent service-layer API.
    The model methods remain available for backwards compatibility, but
    callers should prefer this service for new code.
    """

    @staticmethod
    def get_by_task_id(task_id: str) -> Optional[TaskProgress]:
        """Get task progress by Huey task ID."""
        return TaskProgress.query.filter_by(task_id=task_id).first()

    @staticmethod
    def get_active_for_project(project_id: int) -> list:
        """Get all active (pending or running) tasks for a project."""
        return TaskProgress.query.filter(
            TaskProgress.project_id == project_id,
            TaskProgress.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING])
        ).order_by(TaskProgress.created_at.desc()).all()

    @staticmethod
    def get_recent(limit: int = 10) -> list:
        """Get recent tasks across all projects."""
        return TaskProgress.query.order_by(
            TaskProgress.created_at.desc()
        ).limit(limit).all()

    @staticmethod
    def start(task_id: str) -> Optional[TaskProgress]:
        """
        Mark a task as running.

        Args:
            task_id: Huey task ID

        Returns:
            Updated TaskProgress or None if not found
        """
        progress = TaskProgress.query.filter_by(task_id=task_id).first()
        if progress is None:
            return None
        progress.start()
        return progress

    @staticmethod
    def update_progress(
        task_id: str,
        progress_value: float,
        current_step: str = None,
        completed_steps: int = None
    ) -> Optional[TaskProgress]:
        """
        Update task progress.

        Args:
            task_id: Huey task ID
            progress_value: Progress value (0.0 to 1.0)
            current_step: Description of current operation
            completed_steps: Number of completed steps

        Returns:
            Updated TaskProgress or None if not found
        """
        progress = TaskProgress.query.filter_by(task_id=task_id).first()
        if progress is None:
            return None
        progress.update_progress(progress_value, current_step, completed_steps)
        return progress

    @staticmethod
    def complete(task_id: str, result_summary: str = None) -> Optional[TaskProgress]:
        """
        Mark a task as successfully completed.

        Args:
            task_id: Huey task ID
            result_summary: Brief summary of results

        Returns:
            Updated TaskProgress or None if not found
        """
        progress = TaskProgress.query.filter_by(task_id=task_id).first()
        if progress is None:
            return None
        progress.complete(result_summary)
        return progress

    @staticmethod
    def fail(task_id: str, error_message: str, traceback: str = None) -> Optional[TaskProgress]:
        """
        Mark a task as failed.

        Args:
            task_id: Huey task ID
            error_message: Error description
            traceback: Full traceback string

        Returns:
            Updated TaskProgress or None if not found
        """
        progress = TaskProgress.query.filter_by(task_id=task_id).first()
        if progress is None:
            return None
        progress.fail(error_message, traceback)
        return progress

    @staticmethod
    def cancel(task_id: str) -> Optional[TaskProgress]:
        """
        Mark a task as cancelled.

        Args:
            task_id: Huey task ID

        Returns:
            Updated TaskProgress or None if not found
        """
        progress = TaskProgress.query.filter_by(task_id=task_id).first()
        if progress is None:
            return None
        progress.cancel()
        return progress
