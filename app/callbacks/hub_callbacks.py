"""
Hub callbacks for workflow navigation.

Phase 1: Hub and Navigation Foundation

Provides:
- Step unlock logic based on project state
- Step status computation
- Navigation callbacks
- Progress update callbacks
"""
from typing import Dict, List, Optional, Any

from dash import callback, Output, Input, State, no_update, clientside_callback
from dash.exceptions import PreventUpdate

from app.logging_config import get_logger

logger = get_logger(__name__)


class StepDependencies:
    """
    Step dependency definitions per PRD Section 1.5.

    Step Dependencies:
    | Step                    | Unlocks When                      |
    |-------------------------|-----------------------------------|
    | 1. Define Constructs    | Project created                   |
    | 2. Plan IVT Reaction    | Project created (optional step)   |
    | 3. Create Layout        | At least one construct defined    |
    | 4. Upload Data          | Layout exists                     |
    | 5. Review QC            | Data uploaded                     |
    | 6. Run Analysis         | All QC issues addressed           |
    | 7. Export Results       | Analysis completed                |
    """

    DEPENDENCIES = {
        1: ["project_exists"],
        2: ["project_exists"],  # Optional step
        3: ["project_exists", "has_constructs"],
        4: ["project_exists", "has_constructs", "has_layouts"],
        5: ["project_exists", "has_constructs", "has_layouts", "has_data"],
        6: ["project_exists", "has_constructs", "has_layouts", "has_data", "qc_passed"],
        7: ["project_exists", "has_constructs", "has_layouts", "has_data", "qc_passed", "has_analysis"],
    }

    # Steps that are optional (don't block subsequent steps)
    OPTIONAL_STEPS = {2}

    @classmethod
    def get_dependencies(cls, step_number: int) -> List[str]:
        """
        Get the dependencies for a step.

        Args:
            step_number: Step number (1-7)

        Returns:
            List of dependency keys
        """
        return cls.DEPENDENCIES.get(step_number, [])

    @classmethod
    def is_optional(cls, step_number: int) -> bool:
        """
        Check if a step is optional.

        Args:
            step_number: Step number (1-7)

        Returns:
            True if step is optional
        """
        return step_number in cls.OPTIONAL_STEPS


def check_step_unlock(
    step_number: int,
    project_state: Optional[Dict[str, Any]],
) -> bool:
    """
    Check if a step should be unlocked based on project state.

    Args:
        step_number: Step number (1-7)
        project_state: Dict containing project state information

    Returns:
        True if step is unlocked, False otherwise
    """
    if project_state is None:
        return False

    dependencies = StepDependencies.get_dependencies(step_number)

    for dep in dependencies:
        if not _check_dependency(dep, project_state):
            return False

    return True


def _check_dependency(dependency: str, project_state: Dict[str, Any]) -> bool:
    """
    Check if a single dependency is met.

    Args:
        dependency: Dependency key
        project_state: Project state dict

    Returns:
        True if dependency is met
    """
    if dependency == "project_exists":
        return project_state.get("project_id") is not None

    elif dependency == "has_constructs":
        return project_state.get("construct_count", 0) > 0

    elif dependency == "has_layouts":
        return project_state.get("layout_count", 0) > 0

    elif dependency == "has_data":
        return project_state.get("data_count", 0) > 0

    elif dependency == "qc_passed":
        return project_state.get("qc_passed", False)

    elif dependency == "has_analysis":
        return project_state.get("analysis_count", 0) > 0

    return False


def get_step_blockers(
    step_number: int,
    project_state: Optional[Dict[str, Any]],
) -> List[str]:
    """
    Get the list of blockers preventing a step from unlocking.

    Args:
        step_number: Step number (1-7)
        project_state: Project state dict

    Returns:
        List of human-readable blocker messages
    """
    if project_state is None:
        return ["No project selected"]

    blockers = []
    dependencies = StepDependencies.get_dependencies(step_number)

    blocker_messages = {
        "project_exists": "Project must be created",
        "has_constructs": "At least one construct must be defined",
        "has_layouts": "A plate layout must be created",
        "has_data": "Experimental data must be uploaded",
        "qc_passed": f"{project_state.get('sessions_pending_qc', project_state.get('qc_issues_count', 0))} session(s) pending QC approval",
        "has_analysis": "Analysis must be completed",
    }

    for dep in dependencies:
        if not _check_dependency(dep, project_state):
            message = blocker_messages.get(dep, f"Requirement '{dep}' not met")
            blockers.append(message)

    return blockers


def compute_step_statuses(
    project_state: Optional[Dict[str, Any]],
) -> Dict[int, str]:
    """
    Compute the status for all workflow steps.

    Status values:
    - "locked": Step is not accessible
    - "pending": Step is accessible but not started
    - "in_progress": Step has been started but not completed
    - "completed": Step is finished

    Args:
        project_state: Project state dict

    Returns:
        Dict mapping step number to status string
    """
    if project_state is None:
        return {i: "locked" for i in range(1, 8)}

    statuses = {}

    for step_num in range(1, 8):
        is_unlocked = check_step_unlock(step_num, project_state)

        if not is_unlocked:
            statuses[step_num] = "locked"
        else:
            # Determine if step is completed, in progress, or pending
            status = _compute_step_completion(step_num, project_state)
            statuses[step_num] = status

    return statuses


def _compute_step_completion(
    step_number: int,
    project_state: Dict[str, Any],
) -> str:
    """
    Compute whether a step is pending, in progress, or completed.

    Args:
        step_number: Step number
        project_state: Project state dict

    Returns:
        Status string: "pending", "in_progress", or "completed"
    """
    # Step completion criteria
    if step_number == 1:  # Define Constructs
        count = project_state.get("construct_count", 0)
        if count > 0:
            return "completed"
        return "pending"

    elif step_number == 2:  # Plan IVT (optional)
        count = project_state.get("ivt_plan_count", 0)
        if count > 0:
            # Use in_progress (blue) instead of completed (green) since
            # users create multiple protocols - this is an ongoing activity
            return "in_progress"
        # Optional step - show as pending but don't block
        return "pending"

    elif step_number == 3:  # Create Layout
        count = project_state.get("layout_count", 0)
        if count > 0:
            return "completed"
        return "pending"

    elif step_number == 4:  # Upload Data
        count = project_state.get("data_count", 0)
        if count > 0:
            return "completed"
        return "pending"

    elif step_number == 5:  # Review QC
        if project_state.get("qc_passed", False):
            return "completed"
        if project_state.get("data_count", 0) > 0:
            # Has data but QC not passed yet - sessions are pending review
            sessions_pending = project_state.get("sessions_pending_qc", 0)
            if sessions_pending > 0:
                return "in_progress"
            return "pending"
        return "pending"

    elif step_number == 6:  # Run Analysis
        count = project_state.get("analysis_count", 0)
        if count > 0:
            return "completed"
        # Check if analysis is running
        if project_state.get("analysis_running", False):
            return "in_progress"
        return "pending"

    elif step_number == 7:  # Export Results
        count = project_state.get("export_count", 0)
        if count > 0:
            return "completed"
        return "pending"

    return "pending"


def register_hub_callbacks(app):
    """
    Register all hub-related callbacks.

    Args:
        app: Dash application instance
    """
    @app.callback(
        [
            Output("hub-step-statuses-store", "data"),
            Output("hub-steps-container", "children"),
            Output("hub-progress-container", "children"),
        ],
        [
            Input("hub-project-store", "data"),
        ],
        prevent_initial_call=False,
    )
    def update_hub_display(project_store):
        """Update the hub display when project data changes."""
        from app.layouts.hub import (
            create_workflow_steps_grid,
            create_workflow_stepper,
        )
        from app.services import ProjectService

        if not project_store or not project_store.get("project_id"):
            # No project - show default state
            statuses = {i: "locked" for i in range(1, 8)}
            grid = create_workflow_steps_grid(project_id=None, step_statuses=statuses)
            progress = create_workflow_stepper(step_statuses=statuses)
            return statuses, grid, progress

        project_id = project_store["project_id"]

        try:
            # Get project statistics from service
            stats = ProjectService.get_project_statistics(project_id)

            # Build project state for status computation
            project_state = {
                "project_id": project_id,
                "construct_count": stats.get("construct_count", 0),
                "layout_count": stats.get("layout_count", 0),
                "data_count": stats.get("well_count", 0),
                "qc_passed": stats.get("qc_passed", False),
                "qc_issues_count": stats.get("qc_issues_count", 0),
                "sessions_pending_qc": stats.get("sessions_pending_qc", 0),
                "analysis_count": stats.get("analysis_count", 0),
                "ivt_plan_count": stats.get("reaction_count", 0),
                "export_count": stats.get("export_count", 0),
            }

            # Compute step statuses
            statuses = compute_step_statuses(project_state)

            # Build item counts
            # Step 5: Show sessions pending QC review
            sessions_pending = stats.get("sessions_pending_qc", 0)
            item_counts = {
                1: stats.get("construct_count", 0),
                2: stats.get("reaction_count", 0),
                3: stats.get("layout_count", 0),
                4: stats.get("file_count", 0),
                5: sessions_pending,  # Sessions pending QC review
                6: stats.get("analysis_count", 0),
                7: stats.get("export_count", 0),
            }

            # Count completed steps
            completed_count = sum(1 for s in statuses.values() if s == "completed")

            # Create updated components
            grid = create_workflow_steps_grid(
                project_id=project_id,
                step_statuses=statuses,
                item_counts=item_counts,
            )
            progress = create_workflow_stepper(
                step_statuses=statuses,
            )

            return statuses, grid, progress

        except Exception as e:
            # Handle error - show empty state with error
            import dash_mantine_components as dmc

            logger.exception("Error loading project hub data")
            statuses = {i: "locked" for i in range(1, 8)}
            grid = dmc.Alert(
                title="Error loading project",
                children="An unexpected error occurred while loading the project dashboard.",
                color="red",
            )
            progress = create_workflow_stepper(step_statuses=statuses)
            return statuses, grid, progress

    @app.callback(
        Output("hub-title-container", "children"),
        Input("hub-project-store", "data"),
        prevent_initial_call=False,
    )
    def update_hub_title(project_store):
        """Update the hub title with project name."""
        import dash_mantine_components as dmc

        if not project_store or not project_store.get("project_id"):
            return [
                dmc.Title("Select a Project", order=3),
                dmc.Text("Project Dashboard", size="sm", c="dimmed"),
            ]

        project_id = project_store["project_id"]

        try:
            from app.services import ProjectService

            project = ProjectService.get_project(project_id)
            if project:
                return [
                    dmc.Title(project.name, order=3),
                    dmc.Text("Project Dashboard", size="sm", c="dimmed"),
                ]
        except Exception:
            pass

        return [
            dmc.Title(f"Project #{project_id}", order=3),
            dmc.Text("Project Dashboard", size="sm", c="dimmed"),
        ]

    # Navigation callbacks
    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("hub-back-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def navigate_back(n_clicks):
        """Navigate back to project list."""
        if n_clicks:
            return "/projects"
        raise PreventUpdate

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("hub-settings-btn", "n_clicks"),
        State("hub-project-store", "data"),
        prevent_initial_call=True,
    )
    def navigate_to_settings(n_clicks, project_store):
        """Navigate to project settings."""
        if n_clicks and project_store and project_store.get("project_id"):
            project_id = project_store["project_id"]
            return f"/project/{project_id}/settings"
        raise PreventUpdate

    # Quick action callbacks
    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("quick-run-analysis-btn", "n_clicks"),
        State("hub-project-store", "data"),
        prevent_initial_call=True,
    )
    def quick_run_analysis(n_clicks, project_store):
        """Navigate to analysis page."""
        if n_clicks and project_store and project_store.get("project_id"):
            project_id = project_store["project_id"]
            return f"/project/{project_id}/analysis"
        raise PreventUpdate

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("quick-view-curves-btn", "n_clicks"),
        State("hub-project-store", "data"),
        prevent_initial_call=True,
    )
    def quick_view_curves(n_clicks, project_store):
        """Navigate to curve browser."""
        if n_clicks and project_store and project_store.get("project_id"):
            project_id = project_store["project_id"]
            return f"/project/{project_id}/curves"
        raise PreventUpdate

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("quick-export-btn", "n_clicks"),
        State("hub-project-store", "data"),
        prevent_initial_call=True,
    )
    def quick_export(n_clicks, project_store):
        """Navigate to export page."""
        if n_clicks and project_store and project_store.get("project_id"):
            project_id = project_store["project_id"]
            return f"/project/{project_id}/export"
        raise PreventUpdate

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("quick-precision-btn", "n_clicks"),
        State("hub-project-store", "data"),
        prevent_initial_call=True,
    )
    def quick_precision(n_clicks, project_store):
        """Navigate to precision dashboard."""
        if n_clicks and project_store and project_store.get("project_id"):
            project_id = project_store["project_id"]
            return f"/project/{project_id}/precision"
        raise PreventUpdate
