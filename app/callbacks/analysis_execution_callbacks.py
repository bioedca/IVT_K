"""Callbacks for analysis execution (run modal, progress polling, version refresh)."""
from dash import Input, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate


def register_analysis_execution_callbacks(app):
    """Register analysis execution callbacks."""

    @app.callback(
        Output("analysis-run-modal", "opened"),
        Input("analysis-run-btn", "n_clicks"),
        Input("analysis-run-cancel", "n_clicks"),
        Input("analysis-run-confirm", "n_clicks"),
        Input("fc-run-analysis-clicks", "data"),
        State("analysis-run-modal", "opened"),
        prevent_initial_call=True,
    )
    def toggle_run_modal(run_clicks, cancel_clicks, confirm_clicks, fc_run_clicks, is_open):
        """Toggle the run analysis modal."""
        triggered = ctx.triggered_id

        if triggered in ["analysis-run-btn", "fc-run-analysis-clicks"]:
            return True
        elif triggered in ["analysis-run-cancel", "analysis-run-confirm"]:
            return False

        return is_open

    @app.callback(
        Output("analysis-progress-modal", "opened"),
        Output("analysis-progress-bar", "value"),
        Output("analysis-progress-text", "children"),
        Output("analysis-task-id-store", "data"),
        Output("analysis-progress-interval", "disabled"),
        Input("analysis-run-confirm", "n_clicks"),
        Input("analysis-progress-close", "n_clicks"),
        State("analysis-checkpoint-name", "value"),
        State("analysis-checkpoint-description", "value"),
        State("analysis-include-frequentist", "checked"),
        State("analysis-project-store", "data"),
        prevent_initial_call=True,
    )
    def start_analysis(
        confirm_clicks, close_clicks, name, description,
        include_freq, project_id
    ):
        """Start or close analysis progress."""
        triggered = ctx.triggered_id

        if triggered == "analysis-progress-close":
            # Close modal and disable polling
            return False, 0, "", None, True

        if triggered == "analysis-run-confirm" and project_id and name:
            try:
                from flask import request
                from app.tasks.mcmc_tasks import enqueue_hierarchical_analysis

                # Get username
                username = "unknown"
                try:
                    username = request.headers.get("X-Username", "unknown")
                except RuntimeError:
                    pass

                # Queue hierarchical analysis task
                task_id = enqueue_hierarchical_analysis(
                    project_id=project_id,
                    version_name=name,
                    description=description,
                    username=username,
                )

                # Return: open modal, initial progress, text, task_id, enable interval
                return True, 5, "Analysis queued...", task_id, False

            except Exception as e:
                print(f"Error starting analysis: {e}")
                import traceback
                traceback.print_exc()
                return False, 0, "", None, True

        raise PreventUpdate

    @app.callback(
        Output("analysis-progress-bar", "value", allow_duplicate=True),
        Output("analysis-progress-text", "children", allow_duplicate=True),
        Output("analysis-progress-interval", "disabled", allow_duplicate=True),
        Output("analysis-progress-modal", "opened", allow_duplicate=True),
        Output("analysis-task-id-store", "data", allow_duplicate=True),
        Input("analysis-progress-interval", "n_intervals"),
        State("analysis-task-id-store", "data"),
        prevent_initial_call=True,
    )
    def poll_analysis_progress(n_intervals, task_id):
        """Poll task progress and update modal."""
        if not task_id:
            raise PreventUpdate

        # Check if this is a "close pending" state (task_id starts with "done:")
        if isinstance(task_id, str) and task_id.startswith("done:"):
            # Second poll after completion - now close the modal
            return 100, "Analysis complete!", True, False, None

        from app.models.task_progress import TaskProgress, TaskStatus

        progress = TaskProgress.get_by_task_id(task_id)
        if not progress:
            raise PreventUpdate

        # Calculate progress percentage
        pct = int(progress.progress * 100) if progress.progress else 5
        status_text = progress.current_step or "Processing..."

        if progress.status == TaskStatus.COMPLETED:
            # Task completed - show success, mark for close on next poll
            # This gives ~3 seconds (one interval) to see "Analysis complete!"
            return 100, "Analysis complete! Closing...", False, True, f"done:{task_id}"

        elif progress.status == TaskStatus.FAILED:
            # Task failed - keep modal open for user to see error
            error_msg = progress.error_message or "Analysis failed"
            display_msg = f"{error_msg[:50]}..." if len(error_msg) > 50 else error_msg
            return pct, f"Error: {display_msg}", True, True, task_id

        else:
            # Still running
            return pct, status_text, False, True, task_id

    @app.callback(
        Output("analysis-version-select", "data", allow_duplicate=True),
        Output("analysis-version-select", "value", allow_duplicate=True),
        Input("analysis-progress-modal", "opened"),
        State("analysis-project-store", "data"),
        prevent_initial_call=True,
    )
    def refresh_versions_after_analysis(modal_open, project_id):
        """Refresh version list and select latest after analysis completes."""
        if not modal_open and project_id:
            # Modal closed, refresh list and select latest
            try:
                from app.models.analysis_version import AnalysisVersion

                versions = AnalysisVersion.query.filter_by(
                    project_id=project_id
                ).order_by(AnalysisVersion.created_at.desc()).all()

                if versions:
                    options = [
                        {
                            "value": str(v.id),
                            "label": f"{v.name} ({v.created_at.strftime('%Y-%m-%d %H:%M')})"
                        }
                        for v in versions
                    ]
                    return options, str(versions[0].id)
            except Exception:
                pass

        raise PreventUpdate
