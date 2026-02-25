"""Integration tests for Task API endpoints."""
import pytest
import json

from app.models import TaskProgress, TaskStatus, TaskType
from app.services.task_service import TaskService


class TestTaskAPI:
    """Tests for Task API (Phase 1.8 - Progress polling endpoint)."""

    def test_get_task_progress(self, client, db_session):
        """T1.9: Progress polling returns current status."""
        # Create a task
        progress = TaskProgress(
            task_id="api-test-001",
            task_type=TaskType.CURVE_FITTING,
            name="Test Task",
            status=TaskStatus.RUNNING,
            progress=0.5,
            current_step="Processing plate 3"
        )
        db_session.add(progress)
        db_session.commit()

        # Query the API
        response = client.get('/api/tasks/api-test-001')

        assert response.status_code == 200
        data = json.loads(response.data)

        assert data["task_id"] == "api-test-001"
        assert data["status"] == "running"
        assert data["progress"] == 0.5
        assert data["progress_percent"] == 50
        assert data["current_step"] == "Processing plate 3"

    def test_get_task_progress_not_found(self, client, db_session):
        """Test 404 for nonexistent task."""
        response = client.get('/api/tasks/nonexistent-task')

        assert response.status_code == 404
        data = json.loads(response.data)
        assert "error" in data

    def test_list_tasks(self, client, db_session):
        """Test listing all tasks."""
        # Create several tasks
        for i in range(5):
            progress = TaskProgress(
                task_id=f"list-test-{i}",
                task_type=TaskType.CURVE_FITTING,
                name=f"Task {i}",
                project_id=1
            )
            db_session.add(progress)
        db_session.commit()

        response = client.get('/api/tasks/')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert "tasks" in data
        assert "count" in data
        assert data["count"] == 5

    def test_list_tasks_with_project_filter(self, client, db_session):
        """Test listing tasks filtered by project."""
        # Create tasks for different projects
        for project_id in [1, 1, 2]:
            progress = TaskProgress(
                task_id=f"filter-{project_id}-{id(progress) if 'progress' in dir() else 0}",
                task_type=TaskType.CURVE_FITTING,
                name=f"Task for project {project_id}",
                project_id=project_id
            )
            db_session.add(progress)
        db_session.commit()

        response = client.get('/api/tasks/?project_id=1')
        assert response.status_code == 200
        data = json.loads(response.data)

        # All returned tasks should be for project 1
        for task in data["tasks"]:
            assert task["project_id"] == 1

    def test_list_tasks_with_status_filter(self, client, db_session):
        """Test listing tasks filtered by status."""
        # Create tasks with different statuses
        pending = TaskProgress(
            task_id="status-pending",
            task_type=TaskType.CURVE_FITTING,
            name="Pending Task",
            status=TaskStatus.PENDING
        )
        completed = TaskProgress(
            task_id="status-completed",
            task_type=TaskType.CURVE_FITTING,
            name="Completed Task",
            status=TaskStatus.COMPLETED
        )
        db_session.add_all([pending, completed])
        db_session.commit()

        response = client.get('/api/tasks/?status=pending')
        assert response.status_code == 200
        data = json.loads(response.data)

        # All returned tasks should be pending
        for task in data["tasks"]:
            assert task["status"] == "pending"

    def test_list_tasks_invalid_status(self, client, db_session):
        """Test invalid status filter returns error."""
        response = client.get('/api/tasks/?status=invalid_status')

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
        assert "Invalid status" in data["error"]
        assert "Valid values" in data["error"]

    def test_list_active_tasks(self, client, db_session):
        """Test getting only active tasks."""
        # Create tasks with different statuses
        pending = TaskProgress(
            task_id="active-pending",
            task_type=TaskType.CURVE_FITTING,
            name="Pending Task",
            status=TaskStatus.PENDING
        )
        running = TaskProgress(
            task_id="active-running",
            task_type=TaskType.CURVE_FITTING,
            name="Running Task",
            status=TaskStatus.RUNNING
        )
        completed = TaskProgress(
            task_id="active-completed",
            task_type=TaskType.CURVE_FITTING,
            name="Completed Task",
            status=TaskStatus.COMPLETED
        )
        db_session.add_all([pending, running, completed])
        db_session.commit()

        response = client.get('/api/tasks/?active_only=true')
        assert response.status_code == 200
        data = json.loads(response.data)

        task_ids = [t["task_id"] for t in data["tasks"]]
        assert "active-pending" in task_ids
        assert "active-running" in task_ids
        assert "active-completed" not in task_ids

    def test_get_active_tasks_endpoint(self, client, db_session):
        """Test dedicated active tasks endpoint."""
        pending = TaskProgress(
            task_id="active-endpoint-1",
            task_type=TaskType.CURVE_FITTING,
            name="Active Task",
            status=TaskStatus.PENDING,
            project_id=1
        )
        db_session.add(pending)
        db_session.commit()

        response = client.get('/api/tasks/active')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert "tasks" in data
        assert "count" in data

    def test_cancel_task_endpoint(self, client, db_session):
        """Test cancelling a task via API."""
        progress = TaskProgress(
            task_id="cancel-test",
            task_type=TaskType.CURVE_FITTING,
            name="Task to Cancel",
            status=TaskStatus.PENDING
        )
        db_session.add(progress)
        db_session.commit()

        response = client.post('/api/tasks/cancel-test/cancel')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data["success"] is True

        # Verify task is cancelled
        check = TaskProgress.get_by_task_id("cancel-test")
        assert check.status == TaskStatus.CANCELLED

    def test_cancel_task_not_found(self, client, db_session):
        """Test cancelling nonexistent task."""
        response = client.post('/api/tasks/nonexistent/cancel')

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False

    def test_cancel_completed_task_fails(self, client, db_session):
        """Test that completed tasks cannot be cancelled."""
        progress = TaskProgress(
            task_id="cancel-completed",
            task_type=TaskType.CURVE_FITTING,
            name="Completed Task",
            status=TaskStatus.COMPLETED
        )
        db_session.add(progress)
        db_session.commit()

        response = client.post('/api/tasks/cancel-completed/cancel')
        assert response.status_code == 400
        data = json.loads(response.data)

        assert data["success"] is False

    def test_poll_multiple_tasks(self, client, db_session):
        """Test polling multiple tasks at once."""
        # Create several tasks
        for i in range(3):
            progress = TaskProgress(
                task_id=f"poll-{i}",
                task_type=TaskType.CURVE_FITTING,
                name=f"Task {i}",
                progress=i * 0.3
            )
            db_session.add(progress)
        db_session.commit()

        response = client.get('/api/tasks/poll?task_ids=poll-0,poll-1,poll-2')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert "tasks" in data
        assert "poll_interval_ms" in data
        assert data["poll_interval_ms"] == 2000

        assert "poll-0" in data["tasks"]
        assert "poll-1" in data["tasks"]
        assert "poll-2" in data["tasks"]

    def test_poll_with_missing_tasks(self, client, db_session):
        """Test polling includes error for missing tasks."""
        progress = TaskProgress(
            task_id="poll-exists",
            task_type=TaskType.CURVE_FITTING,
            name="Existing Task"
        )
        db_session.add(progress)
        db_session.commit()

        response = client.get('/api/tasks/poll?task_ids=poll-exists,poll-missing')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data["tasks"]["poll-exists"]["task_id"] == "poll-exists"
        assert data["tasks"]["poll-missing"]["error"] == "not_found"

    def test_poll_no_task_ids(self, client, db_session):
        """Test poll endpoint requires task IDs."""
        response = client.get('/api/tasks/poll')

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    def test_tasks_list_with_limit(self, client, db_session):
        """Test limiting number of returned tasks."""
        # Create many tasks
        for i in range(10):
            progress = TaskProgress(
                task_id=f"limit-{i}",
                task_type=TaskType.CURVE_FITTING,
                name=f"Task {i}"
            )
            db_session.add(progress)
        db_session.commit()

        response = client.get('/api/tasks/?limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert data["count"] == 5
