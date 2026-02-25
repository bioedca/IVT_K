"""REST API endpoints for IVT Kinetics Analyzer."""
from app.api.task_api import task_api, register_task_api
from app.api.project_api import project_api, register_project_api
from app.api.layout_api import layout_bp, register_layout_api
from app.api.calculator_api import calculator_bp, register_calculator_api
from app.api.smart_planner_api import smart_planner_bp, register_smart_planner_api
from app.api.openapi import openapi_bp, register_openapi
# Phase 5: Upload and Results APIs
from app.api.uploads_api import uploads_api, register_uploads_api
from app.api.results_api import results_api, register_results_api
# Phase 3: Health check API
from app.api.health_api import health_bp, register_health_api

__all__ = [
    "task_api",
    "register_task_api",
    "project_api",
    "register_project_api",
    "layout_bp",
    "register_layout_api",
    "calculator_bp",
    "register_calculator_api",
    "smart_planner_bp",
    "register_smart_planner_api",
    "openapi_bp",
    "register_openapi",
    # Phase 5: Upload and Results APIs
    "uploads_api",
    "register_uploads_api",
    "results_api",
    "register_results_api",
    # Phase 3: Health check API
    "health_bp",
    "register_health_api",
]
