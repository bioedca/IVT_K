"""
Task progress API endpoints.

Phase 1.8: Implements F17.5 - Progress polling endpoint (2s interval).
Phase 3.3: Rate limiting applied consistently
"""
from flask import Blueprint, jsonify, request

from app.models.task_progress import TaskProgress, TaskStatus
from app.services.task_service import TaskService
from app.api.middleware import api_protection
from app.utils.validation import validate_enum_value, parse_bool_param

# Create Blueprint for task API
task_api = Blueprint('task_api', __name__, url_prefix='/api/tasks')


@task_api.route('/<task_id>', methods=['GET'])
@api_protection(limiter_type="read")
def get_task_progress(task_id: str):
    """
    Get progress for a specific task.

    Returns task status, progress percentage, ETA, and other details.
    UI should poll this endpoint every 2 seconds while task is active.

    Args:
        task_id: The task ID to query

    Returns:
        JSON response with task progress data
    """
    progress = TaskProgress.get_by_task_id(task_id)

    if progress is None:
        return jsonify({
            "error": "Task not found",
            "task_id": task_id
        }), 404

    return jsonify(progress.to_dict())


@task_api.route('/', methods=['GET'])
@api_protection(limiter_type="read")
def list_tasks():
    """
    List tasks with optional filtering.

    Query parameters:
        - project_id: Filter by project
        - status: Filter by status (pending, running, completed, failed)
        - limit: Maximum number of results (default 20)
        - active_only: If "true", only return pending/running tasks

    Returns:
        JSON array of task progress data
    """
    project_id = request.args.get('project_id', type=int)
    status_filter = request.args.get('status')
    limit = request.args.get('limit', 20, type=int)
    active_only = parse_bool_param(request.args.get('active_only'), default=False)

    query = TaskProgress.query

    # Apply filters
    if project_id is not None:
        query = query.filter_by(project_id=project_id)

    if active_only:
        query = query.filter(
            TaskProgress.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING])
        )
    elif status_filter:
        status, error = validate_enum_value(status_filter, TaskStatus, "status")
        if error:
            return jsonify({"error": error}), 400
        query = query.filter_by(status=status)

    # Order and limit
    tasks = query.order_by(TaskProgress.created_at.desc()).limit(limit).all()

    return jsonify({
        "tasks": [t.to_dict() for t in tasks],
        "count": len(tasks)
    })


@task_api.route('/active', methods=['GET'])
@api_protection(limiter_type="read")
def get_active_tasks():
    """
    Get all currently active (pending or running) tasks.

    Query parameters:
        - project_id: Optional filter by project

    Returns:
        JSON array of active task progress data
    """
    project_id = request.args.get('project_id', type=int)

    if project_id is not None:
        tasks = TaskProgress.get_active_for_project(project_id)
    else:
        tasks = TaskService.get_active_tasks()

    return jsonify({
        "tasks": [t.to_dict() for t in tasks],
        "count": len(tasks)
    })


@task_api.route('/<task_id>/cancel', methods=['POST'])
@api_protection(limiter_type="write")
def cancel_task(task_id: str):
    """
    Cancel a pending or running task.

    Args:
        task_id: The task ID to cancel

    Returns:
        JSON response indicating success or failure
    """
    success = TaskService.cancel_task(task_id)

    if success:
        return jsonify({
            "success": True,
            "message": "Task cancelled",
            "task_id": task_id
        })
    else:
        progress = TaskProgress.get_by_task_id(task_id)
        if progress is None:
            return jsonify({
                "success": False,
                "error": "Task not found",
                "task_id": task_id
            }), 404
        else:
            return jsonify({
                "success": False,
                "error": "Task already complete or cannot be cancelled",
                "task_id": task_id,
                "status": progress.status.value
            }), 400


@task_api.route('/poll', methods=['GET'])
@api_protection(limiter_type="read")
def poll_multiple_tasks():
    """
    Poll progress for multiple tasks at once.

    Efficient endpoint for UIs that need to track multiple tasks.
    Recommended polling interval: 2000ms

    Phase 3.4: Returns timeout hints for client-side handling.

    Query parameters:
        - task_ids: Comma-separated list of task IDs

    Returns:
        JSON object mapping task IDs to their progress data,
        plus recommended polling interval and timeout hints
    """
    from app.config import Config

    task_ids_param = request.args.get('task_ids', '')
    task_ids = [tid.strip() for tid in task_ids_param.split(',') if tid.strip()]

    if not task_ids:
        return jsonify({
            "error": "No task IDs provided",
            "usage": "?task_ids=id1,id2,id3"
        }), 400

    results = {}
    for task_id in task_ids:
        progress = TaskProgress.get_by_task_id(task_id)
        if progress:
            task_data = progress.to_dict()
            # Add expected timeout based on task type
            task_type = task_data.get("task_type", "")
            if "mcmc" in task_type.lower():
                task_data["expected_duration"] = Config.OPERATION_TIMES.get("mcmc_analysis", {})
            elif "curve" in task_type.lower() or "fitting" in task_type.lower():
                task_data["expected_duration"] = Config.OPERATION_TIMES.get("curve_fitting", {})
            results[task_id] = task_data
        else:
            results[task_id] = {"error": "not_found"}

    return jsonify({
        "tasks": results,
        "poll_interval_ms": Config.PROGRESS_POLL_INTERVAL,
        "timeout_hints": {
            "mcmc_analysis_max_ms": Config.REQUEST_TIMEOUT_ANALYSIS * 1000,
            "general_max_ms": Config.REQUEST_TIMEOUT_DEFAULT * 1000,
        }
    })


def register_task_api(app):
    """Register the task API blueprint with the Flask app."""
    app.register_blueprint(task_api)
