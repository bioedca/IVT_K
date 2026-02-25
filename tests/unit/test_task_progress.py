"""Unit tests for TaskProgress model and TaskService."""
import pytest
from datetime import datetime
import time

from app.models import TaskProgress, TaskStatus, TaskType
from app.services.task_service import TaskService


class TestTaskProgressModel:
    """Tests for TaskProgress model (Phase 1.6)."""

    def test_task_progress_creation(self, db_session):
        """T1.6: TaskProgress created on enqueue with initial status 'pending'."""
        progress = TaskProgress(
            task_id="test-task-001",
            task_type=TaskType.CURVE_FITTING,
            name="Test Fitting Task",
            status=TaskStatus.PENDING
        )
        db_session.add(progress)
        db_session.commit()

        assert progress.id is not None
        assert progress.task_id == "test-task-001"
        assert progress.status == TaskStatus.PENDING
        assert progress.progress == 0.0
        assert progress.is_running is False
        assert progress.is_complete is False

    def test_progress_validation(self, db_session):
        """Test progress value is clamped between 0 and 1."""
        progress = TaskProgress(
            task_id="test-task-002",
            task_type=TaskType.CURVE_FITTING,
            name="Test Task"
        )
        db_session.add(progress)
        db_session.commit()

        # Test clamping above 1
        progress.progress = 1.5
        assert progress.progress == 1.0

        # Test clamping below 0
        progress.progress = -0.5
        assert progress.progress == 0.0

        # Test valid values
        progress.progress = 0.5
        assert progress.progress == 0.5

    def test_progress_percent_property(self, db_session):
        """Test progress_percent returns 0-100 value."""
        progress = TaskProgress(
            task_id="test-task-003",
            task_type=TaskType.CURVE_FITTING,
            name="Test Task",
            progress=0.75
        )
        db_session.add(progress)
        db_session.commit()

        assert progress.progress_percent == 75

    def test_task_start(self, db_session):
        """Test marking task as started."""
        progress = TaskProgress(
            task_id="test-task-004",
            task_type=TaskType.CURVE_FITTING,
            name="Test Task"
        )
        db_session.add(progress)
        db_session.commit()

        progress.start()

        assert progress.status == TaskStatus.RUNNING
        assert progress.started_at is not None
        assert progress.is_running is True

    def test_update_progress(self, db_session):
        """T1.7: Progress updates from worker."""
        progress = TaskProgress(
            task_id="test-task-005",
            task_type=TaskType.CURVE_FITTING,
            name="Test Task"
        )
        db_session.add(progress)
        db_session.commit()

        progress.start()
        progress.update_progress(0.5, "Processing step 5", 5)

        assert progress.progress == 0.5
        assert progress.current_step == "Processing step 5"
        assert progress.completed_steps == 5

    def test_task_completion(self, db_session):
        """Test marking task as completed."""
        progress = TaskProgress(
            task_id="test-task-006",
            task_type=TaskType.CURVE_FITTING,
            name="Test Task"
        )
        db_session.add(progress)
        db_session.commit()

        progress.start()
        progress.complete("Successfully processed 10 items")

        assert progress.status == TaskStatus.COMPLETED
        assert progress.progress == 1.0
        assert progress.completed_at is not None
        assert progress.result_summary == "Successfully processed 10 items"
        assert progress.is_complete is True

    def test_task_failure(self, db_session):
        """T1.10: Worker survives task failure."""
        progress = TaskProgress(
            task_id="test-task-007",
            task_type=TaskType.CURVE_FITTING,
            name="Test Task"
        )
        db_session.add(progress)
        db_session.commit()

        progress.start()
        progress.fail("Division by zero", "Traceback: ...")

        assert progress.status == TaskStatus.FAILED
        assert progress.completed_at is not None
        assert progress.error_message == "Division by zero"
        assert progress.error_traceback == "Traceback: ..."
        assert progress.is_complete is True

    def test_task_cancellation(self, db_session):
        """Test marking task as cancelled."""
        progress = TaskProgress(
            task_id="test-task-008",
            task_type=TaskType.CURVE_FITTING,
            name="Test Task"
        )
        db_session.add(progress)
        db_session.commit()

        progress.start()
        progress.cancel()

        assert progress.status == TaskStatus.CANCELLED
        assert progress.completed_at is not None
        assert progress.is_complete is True

    def test_eta_display(self, db_session):
        """T1.8: ETA computed from progress rate."""
        progress = TaskProgress(
            task_id="test-task-009",
            task_type=TaskType.CURVE_FITTING,
            name="Test Task"
        )
        db_session.add(progress)
        db_session.commit()

        # Test various ETA formats
        progress.estimated_remaining_seconds = 30
        assert progress.eta_display == "30s"

        progress.estimated_remaining_seconds = 90
        assert progress.eta_display == "1m"

        progress.estimated_remaining_seconds = 3700
        assert progress.eta_display == "1h 1m"

    def test_to_dict(self, db_session):
        """Test serialization to dictionary."""
        progress = TaskProgress(
            task_id="test-task-010",
            task_type=TaskType.CURVE_FITTING,
            name="Test Task",
            project_id=1,
            username="test_user",
            progress=0.5
        )
        db_session.add(progress)
        db_session.commit()

        data = progress.to_dict()

        assert data["task_id"] == "test-task-010"
        assert data["task_type"] == "curve_fitting"
        assert data["name"] == "Test Task"
        assert data["status"] == "pending"
        assert data["progress"] == 0.5
        assert data["progress_percent"] == 50
        assert data["project_id"] == 1
        assert data["username"] == "test_user"

    def test_get_by_task_id(self, db_session):
        """Test retrieval by task ID."""
        progress = TaskProgress(
            task_id="test-task-011",
            task_type=TaskType.CURVE_FITTING,
            name="Test Task"
        )
        db_session.add(progress)
        db_session.commit()

        retrieved = TaskProgress.get_by_task_id("test-task-011")
        assert retrieved is not None
        assert retrieved.id == progress.id

        not_found = TaskProgress.get_by_task_id("nonexistent")
        assert not_found is None

    def test_get_active_for_project(self, db_session):
        """Test getting active tasks for a project."""
        # Create tasks in different states
        pending = TaskProgress(
            task_id="active-1",
            task_type=TaskType.CURVE_FITTING,
            name="Pending Task",
            project_id=1,
            status=TaskStatus.PENDING
        )
        running = TaskProgress(
            task_id="active-2",
            task_type=TaskType.MCMC_SAMPLING,
            name="Running Task",
            project_id=1,
            status=TaskStatus.RUNNING
        )
        completed = TaskProgress(
            task_id="active-3",
            task_type=TaskType.CURVE_FITTING,
            name="Completed Task",
            project_id=1,
            status=TaskStatus.COMPLETED
        )
        other_project = TaskProgress(
            task_id="active-4",
            task_type=TaskType.CURVE_FITTING,
            name="Other Project Task",
            project_id=2,
            status=TaskStatus.RUNNING
        )

        db_session.add_all([pending, running, completed, other_project])
        db_session.commit()

        active = TaskProgress.get_active_for_project(1)
        task_ids = [t.task_id for t in active]

        assert "active-1" in task_ids
        assert "active-2" in task_ids
        assert "active-3" not in task_ids  # Completed
        assert "active-4" not in task_ids  # Different project


class TestTaskService:
    """Tests for TaskService (Phase 1.7)."""

    def test_create_task_progress(self, db_session):
        """T1.5: Task enqueues successfully."""
        progress = TaskService.create_task_progress(
            task_type=TaskType.CURVE_FITTING,
            name="Curve Fitting Job",
            project_id=1,
            username="researcher",
            total_steps=10,
            extra_data={"model": "delayed_exponential"}
        )

        assert progress.task_id is not None
        assert progress.task_type == TaskType.CURVE_FITTING
        assert progress.name == "Curve Fitting Job"
        assert progress.project_id == 1
        assert progress.username == "researcher"
        assert progress.total_steps == 10
        assert progress.extra_data == {"model": "delayed_exponential"}
        assert progress.status == TaskStatus.PENDING

    def test_get_task_progress(self, db_session):
        """Test retrieving task progress."""
        progress = TaskService.create_task_progress(
            task_type=TaskType.CURVE_FITTING,
            name="Test Task"
        )

        retrieved = TaskService.get_task_progress(progress.task_id)
        assert retrieved is not None
        assert retrieved.id == progress.id

    def test_get_active_tasks(self, db_session):
        """Test getting all active tasks."""
        # Create tasks in different states
        task1 = TaskService.create_task_progress(
            task_type=TaskType.CURVE_FITTING,
            name="Task 1",
            project_id=1
        )
        task2 = TaskService.create_task_progress(
            task_type=TaskType.MCMC_SAMPLING,
            name="Task 2",
            project_id=2
        )

        # Complete one task
        task1.complete("Done")
        db_session.commit()

        active = TaskService.get_active_tasks()
        task_ids = [t.task_id for t in active]

        assert task1.task_id not in task_ids  # Completed
        assert task2.task_id in task_ids  # Still pending

    def test_get_active_tasks_by_project(self, db_session):
        """Test getting active tasks filtered by project."""
        TaskService.create_task_progress(
            task_type=TaskType.CURVE_FITTING,
            name="Project 1 Task",
            project_id=1
        )
        TaskService.create_task_progress(
            task_type=TaskType.CURVE_FITTING,
            name="Project 2 Task",
            project_id=2
        )

        active = TaskService.get_active_tasks(project_id=1)
        assert len(active) == 1
        assert active[0].project_id == 1

    def test_get_recent_tasks(self, db_session):
        """Test getting recent tasks with limit."""
        for i in range(5):
            TaskService.create_task_progress(
                task_type=TaskType.CURVE_FITTING,
                name=f"Task {i}"
            )

        recent = TaskService.get_recent_tasks(limit=3)
        assert len(recent) == 3

    def test_cancel_task(self, db_session):
        """Test cancelling a task."""
        progress = TaskService.create_task_progress(
            task_type=TaskType.CURVE_FITTING,
            name="Task to Cancel"
        )

        success = TaskService.cancel_task(progress.task_id)
        assert success is True

        # Verify task is cancelled
        cancelled = TaskProgress.get_by_task_id(progress.task_id)
        assert cancelled.status == TaskStatus.CANCELLED

    def test_cancel_nonexistent_task(self, db_session):
        """Test cancelling a task that doesn't exist."""
        success = TaskService.cancel_task("nonexistent-task-id")
        assert success is False

    def test_cancel_completed_task(self, db_session):
        """Test that completed tasks cannot be cancelled."""
        progress = TaskService.create_task_progress(
            task_type=TaskType.CURVE_FITTING,
            name="Completed Task"
        )
        progress.complete("Done")
        db_session.commit()

        success = TaskService.cancel_task(progress.task_id)
        assert success is False

        # Verify status unchanged
        unchanged = TaskProgress.get_by_task_id(progress.task_id)
        assert unchanged.status == TaskStatus.COMPLETED
