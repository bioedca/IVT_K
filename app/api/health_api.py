"""
Health check API endpoint.

Phase 3.2: Health Check Endpoint

Provides health status information for monitoring, deployment verification,
and load balancer health checks.
"""
import os
import time
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, jsonify, current_app

from app.extensions import db
from app.logging_config import get_logger

logger = get_logger(__name__)

# Create Blueprint
health_bp = Blueprint('health', __name__, url_prefix='/api')


def check_database() -> dict[str, Any]:
    """
    Check database connectivity and basic functionality.

    Returns:
        Dict with status and response time in milliseconds
    """
    try:
        start = time.time()
        # Execute a simple query to verify database is accessible
        result = db.session.execute(db.text("SELECT 1")).fetchone()
        elapsed_ms = (time.time() - start) * 1000

        if result and result[0] == 1:
            return {
                "status": "healthy",
                "response_time_ms": round(elapsed_ms, 2),
            }
        else:
            return {
                "status": "unhealthy",
                "error": "Unexpected query result",
            }
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": "Database check failed",
        }


def check_huey_worker() -> dict[str, Any]:
    """
    Check Huey task queue worker status.

    Checks if the Huey database file exists and is accessible.
    Note: This doesn't verify worker is running, only that the queue is accessible.

    Returns:
        Dict with status information
    """
    try:
        from app.config import Config
        huey_db_path = Config.HUEY_DATABASE_PATH

        if not os.path.exists(huey_db_path):
            return {
                "status": "unknown",
                "message": "Huey database not found (worker may not have started)",
            }

        # Check if the database file is accessible
        if os.access(huey_db_path, os.R_OK | os.W_OK):
            # Try to get pending task count
            try:
                from app.tasks.huey_config import huey
                pending_count = huey.pending_count()
                return {
                    "status": "healthy",
                    "pending_tasks": pending_count,
                }
            except Exception:
                return {
                    "status": "degraded",
                    "message": "Queue accessible but count failed",
                }
        else:
            return {
                "status": "unhealthy",
                "error": "Huey database not accessible",
            }
    except Exception as e:
        logger.error("Huey health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": "Huey check failed",
        }


def check_disk_space() -> dict[str, Any]:
    """
    Check available disk space for data directory.

    Returns:
        Dict with disk space information
    """
    try:
        from app.config import Config
        data_dir = Config.DATA_DIR

        if not os.path.exists(data_dir):
            return {
                "status": "unknown",
                "message": "Data directory does not exist",
            }

        stat = os.statvfs(data_dir)
        free_bytes = stat.f_bavail * stat.f_frsize
        total_bytes = stat.f_blocks * stat.f_frsize
        free_gb = free_bytes / (1024 ** 3)
        total_gb = total_bytes / (1024 ** 3)
        used_percent = ((total_bytes - free_bytes) / total_bytes) * 100

        # Consider unhealthy if less than 1GB free or >95% used
        if free_gb < 1.0 or used_percent > 95:
            status = "unhealthy"
        elif free_gb < 5.0 or used_percent > 85:
            status = "degraded"
        else:
            status = "healthy"

        return {
            "status": status,
            "free_gb": round(free_gb, 2),
            "total_gb": round(total_gb, 2),
            "used_percent": round(used_percent, 1),
        }
    except Exception as e:
        logger.error("Disk space check failed", error=str(e))
        return {
            "status": "unknown",
            "error": "Disk space check failed",
        }


@health_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for monitoring and load balancer probes.

    Returns:
        200 OK if healthy, 503 Service Unavailable if unhealthy

    Response body:
        - status: "healthy", "degraded", or "unhealthy"
        - timestamp: ISO 8601 timestamp
        - checks: Individual component check results
        - version: Application version
    """
    checks = {
        "database": check_database(),
        "huey": check_huey_worker(),
        "disk": check_disk_space(),
    }

    # Determine overall status
    statuses = [check.get("status", "unknown") for check in checks.values()]

    if all(s == "healthy" for s in statuses):
        overall_status = "healthy"
        http_status = 200
    elif any(s == "unhealthy" for s in statuses):
        overall_status = "unhealthy"
        http_status = 503
    else:
        overall_status = "degraded"
        http_status = 200  # Degraded is still operational

    # Get version
    try:
        from app import __version__
        version = __version__
    except ImportError:
        version = "unknown"

    response = {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "version": version,
    }

    logger.debug("Health check completed", status=overall_status)
    return jsonify(response), http_status


@health_bp.route('/health/live', methods=['GET'])
def liveness_check():
    """
    Liveness probe endpoint (Kubernetes-style).

    Returns 200 if the application is running.
    This is a minimal check that doesn't verify dependencies.
    """
    return jsonify({
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 200


@health_bp.route('/health/ready', methods=['GET'])
def readiness_check():
    """
    Readiness probe endpoint (Kubernetes-style).

    Returns 200 only if the application is ready to handle requests.
    Checks database connectivity as the critical dependency.
    """
    db_check = check_database()

    if db_check.get("status") == "healthy":
        return jsonify({
            "status": "ready",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 200
    else:
        return jsonify({
            "status": "not_ready",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": db_check.get("error", "Database not available"),
        }), 503


@health_bp.route('/health/timeouts', methods=['GET'])
def get_timeout_info():
    """
    Get expected operation times and timeout configurations.

    Phase 3.4: Request Timeouts for Long-Running Operations

    Returns operation time estimates for client-side timeout configuration.
    """
    from app.config import Config

    return jsonify({
        "poll_interval_ms": Config.PROGRESS_POLL_INTERVAL,
        "default_timeout_seconds": Config.REQUEST_TIMEOUT_DEFAULT,
        "analysis_timeout_seconds": Config.REQUEST_TIMEOUT_ANALYSIS,
        "export_timeout_seconds": Config.REQUEST_TIMEOUT_EXPORT,
        "expected_operation_times": Config.OPERATION_TIMES,
        "recommendations": {
            "mcmc_analysis": "Use async polling - task may take 5-30 minutes",
            "curve_fitting": "May take up to 2 minutes for large datasets",
            "data_export": "Set 2 minute timeout for large exports",
            "general": f"Poll /api/tasks/{{task_id}} every {Config.PROGRESS_POLL_INTERVAL}ms for long operations"
        }
    }), 200


def register_health_api(app):
    """Register the health API blueprint with the Flask app."""
    app.register_blueprint(health_bp)
