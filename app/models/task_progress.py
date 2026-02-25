"""
TaskProgress model for tracking background task execution.

Phase 1.6: Implements F17.4 - status, progress percentage, ETA tracking.
"""
import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, Text, JSON
from sqlalchemy.orm import validates

from app.extensions import db
from app.models.base import TimestampMixin


class TaskStatus(enum.Enum):
    """Background task execution status."""
    PENDING = "pending"      # Queued, not yet started
    RUNNING = "running"      # Currently executing
    COMPLETED = "completed"  # Successfully finished
    FAILED = "failed"        # Execution error
    CANCELLED = "cancelled"  # User cancelled


class TaskType(enum.Enum):
    """Types of background tasks."""
    CURVE_FITTING = "curve_fitting"
    MCMC_SAMPLING = "mcmc_sampling"
    DATA_EXPORT = "data_export"
    PACKAGE_VALIDATION = "package_validation"
    BATCH_PROCESSING = "batch_processing"


class TaskProgress(db.Model, TimestampMixin):
    """
    Track progress of background tasks.

    Created when a task is enqueued, updated during execution,
    and marked complete/failed when done. Used by UI to display
    progress bars and ETA.
    """
    __tablename__ = "task_progress"

    id = Column(Integer, primary_key=True)

    # Task identification
    task_id = Column(String(64), unique=True, nullable=False, index=True)
    task_type = Column(Enum(TaskType), nullable=False)
    name = Column(String(255), nullable=False)  # Human-readable task name

    # Status tracking
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)

    # Progress tracking (0.0 to 1.0)
    progress = Column(Float, default=0.0, nullable=False)
    current_step = Column(String(255))  # Current operation description
    total_steps = Column(Integer)  # Total number of steps if known
    completed_steps = Column(Integer, default=0)  # Steps completed

    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # ETA calculation (seconds from now)
    estimated_remaining_seconds = Column(Float)

    # Context and results
    project_id = Column(Integer, index=True)  # Optional project association
    username = Column(String(100))  # User who started the task

    # Results and errors
    result_summary = Column(Text)  # Brief summary on completion
    error_message = Column(Text)  # Error details if failed
    error_traceback = Column(Text)  # Full traceback for debugging

    # Additional extra_data (JSON for flexibility)
    extra_data = Column(JSON, default=dict)

    @validates('progress')
    def validate_progress(self, key, value):
        """Ensure progress is between 0 and 1."""
        if value is not None:
            return max(0.0, min(1.0, float(value)))
        return value

    @property
    def progress_percent(self) -> int:
        """Progress as percentage (0-100)."""
        return int((self.progress or 0) * 100)

    @property
    def eta_display(self) -> Optional[str]:
        """Human-readable ETA string."""
        if self.estimated_remaining_seconds is None:
            return None

        seconds = int(self.estimated_remaining_seconds)
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}m"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"

    @property
    def duration_seconds(self) -> Optional[float]:
        """Time elapsed since task started."""
        if self.started_at is None:
            return None
        end_time = self.completed_at or datetime.now(timezone.utc)
        started = self.started_at
        # Ensure timezone compatibility (SQLite stores naive UTC)
        if started and started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        return (end_time - started).total_seconds()

    @property
    def is_running(self) -> bool:
        """Check if task is currently running."""
        return self.status == TaskStatus.RUNNING

    @property
    def is_complete(self) -> bool:
        """Check if task finished (success or failure)."""
        return self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)

    def start(self):
        """Mark task as running."""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)
        db.session.commit()

    def update_progress(self, progress: float, current_step: str = None,
                        completed_steps: int = None):
        """
        Update task progress.

        Args:
            progress: Progress value (0.0 to 1.0)
            current_step: Description of current operation
            completed_steps: Number of completed steps
        """
        self.progress = progress
        if current_step is not None:
            self.current_step = current_step
        if completed_steps is not None:
            self.completed_steps = completed_steps

        # Calculate ETA based on progress rate
        if self.started_at and progress > 0:
            started = self.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            if progress < 1.0:
                estimated_total = elapsed / progress
                self.estimated_remaining_seconds = estimated_total - elapsed
            else:
                self.estimated_remaining_seconds = 0

        db.session.commit()

    def complete(self, result_summary: str = None):
        """Mark task as successfully completed."""
        self.status = TaskStatus.COMPLETED
        self.progress = 1.0
        self.completed_at = datetime.now(timezone.utc)
        self.estimated_remaining_seconds = 0
        if result_summary:
            self.result_summary = result_summary
        db.session.commit()

    def fail(self, error_message: str, traceback: str = None):
        """Mark task as failed."""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.error_message = error_message
        if traceback:
            self.error_traceback = traceback
        db.session.commit()

    def cancel(self):
        """Mark task as cancelled."""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.now(timezone.utc)
        db.session.commit()

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "task_type": self.task_type.value if self.task_type else None,
            "name": self.name,
            "status": self.status.value if self.status else None,
            "progress": self.progress,
            "progress_percent": self.progress_percent,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "eta_display": self.eta_display,
            "estimated_remaining_seconds": self.estimated_remaining_seconds,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "project_id": self.project_id,
            "username": self.username,
            "result_summary": self.result_summary,
            "error_message": self.error_message,
            "is_running": self.is_running,
            "is_complete": self.is_complete,
        }

    @classmethod
    def get_by_task_id(cls, task_id: str) -> Optional["TaskProgress"]:
        """Get task progress by Huey task ID."""
        return cls.query.filter_by(task_id=task_id).first()

    @classmethod
    def get_active_for_project(cls, project_id: int) -> list:
        """Get all active (pending or running) tasks for a project."""
        return cls.query.filter(
            cls.project_id == project_id,
            cls.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING])
        ).order_by(cls.created_at.desc()).all()

    @classmethod
    def get_recent(cls, limit: int = 10) -> list:
        """Get recent tasks across all projects."""
        return cls.query.order_by(cls.created_at.desc()).limit(limit).all()

    def __repr__(self):
        return f"<TaskProgress id={self.id} {self.task_id[:8]}... [{self.status.value}] {self.progress_percent}%>"
