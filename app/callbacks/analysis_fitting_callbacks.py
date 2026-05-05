"""Callbacks for the curve fitting workflow (plate selection, fitting, progress, results)."""
from dash import Input, Output, State, ctx, no_update, ALL, html
from dash.exceptions import PreventUpdate
import dash_mantine_components as dmc

from app.logging_config import get_logger
from app.layouts.analysis_results import (
    create_step2_fitting_progress,
    create_step3_fit_results,
    create_step4_fold_changes,
)

logger = get_logger(__name__)


def register_analysis_fitting_callbacks(app):
    """Register curve fitting workflow callbacks."""

    @app.callback(
        Output("fitting-step-content", "children", allow_duplicate=True),
        Output("fitting-preselect-plates-store", "data"),
        Output("refit-wells-store", "data", allow_duplicate=True),
        Input("analysis-project-store", "data"),
        State("refit-wells-store", "data"),  # State: read once when project store changes
        State("fitting-workflow-stepper", "active"),
        State("fitting-model-select-store", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def initialize_fitting_step_content(project_id, refit_wells, current_step, model_type):
        """Initialize Step 1 content when page loads."""
        from app.layouts.analysis_results import _create_step1_plate_selection
        from dash import no_update

        if not project_id:
            raise PreventUpdate

        # Only initialize if we're on step 0 (plate selection)
        if current_step is None or current_step == 0:
            preselect_plate_ids = []

            # If we have wells from curve browser, get their plate IDs
            if refit_wells:
                from app.models import Well
                plate_ids_set = set()
                for well_id in refit_wells:
                    well = Well.query.get(well_id)
                    if well:
                        plate_ids_set.add(well.plate_id)
                preselect_plate_ids = list(plate_ids_set)
                # Create content (checkboxes unchecked), store pre-select IDs, clear refit store
                return _create_step1_plate_selection(project_id, model_type=model_type), preselect_plate_ids, None

            # Normal page load without pre-selection
            return _create_step1_plate_selection(project_id, model_type=model_type), [], no_update

        raise PreventUpdate

    # Note: Session filter callback removed - filtering now happens via re-render
    # The session filter is populated but filtering requires page interaction
    # This avoids race conditions with pre-selection from curve browser

    # Apply pre-selection from curve browser after checkboxes are created
    @app.callback(
        Output({"type": "fitting-plate-checkbox", "index": ALL}, "checked", allow_duplicate=True),
        Output("fitting-preselect-plates-store", "data", allow_duplicate=True),
        Input("fitting-preselect-plates-store", "data"),
        State({"type": "fitting-plate-checkbox", "index": ALL}, "id"),
        prevent_initial_call=True,
    )
    def apply_plate_preselection(preselect_plate_ids, checkbox_ids):
        """Apply pre-selection to checkboxes when coming from curve browser."""
        # Only proceed if we have plates to pre-select
        if not preselect_plate_ids or not checkbox_ids:
            raise PreventUpdate

        # Build checked states based on pre-selection
        checked_states = [
            cb_id["index"] in preselect_plate_ids
            for cb_id in checkbox_ids
        ]

        # Clear the pre-select store to prevent re-triggering
        return checked_states, []

    @app.callback(
        Output("fitting-selected-plates-store", "data"),
        Output("fitting-selected-plates-count", "children"),
        Output("fitting-sample-wells-count", "children"),
        Output("fitting-negative-controls-count", "children"),
        Output("fitting-already-fitted-count", "children"),
        Output("fitting-start-btn", "disabled"),
        Input({"type": "fitting-plate-checkbox", "index": ALL}, "checked"),
        State({"type": "fitting-plate-checkbox", "index": ALL}, "id"),
        State("analysis-project-store", "data"),
        prevent_initial_call=True,
    )
    def update_plate_selection(checked_values, checkbox_ids, project_id):
        """Update selection summary when plates are checked/unchecked."""
        if not checkbox_ids or not project_id:
            return [], "0", "0", "0", "0", True

        try:
            from app.models import Well
            from app.models.plate_layout import WellType
            from app.models.fit_result import FitResult

            # Get selected plate IDs
            selected_ids = [
                cb_id["index"]
                for cb_id, checked in zip(checkbox_ids, checked_values)
                if checked
            ]

            if not selected_ids:
                return [], "0", "0", "0", "0", True

            # Calculate totals for selected plates
            sample_count = 0
            negative_count = 0
            fitted_count = 0

            for plate_id in selected_ids:
                sample_count += Well.query.filter(
                    Well.plate_id == plate_id,
                    Well.well_type == WellType.SAMPLE,
                    Well.is_excluded == False
                ).count()

                negative_count += Well.query.filter(
                    Well.plate_id == plate_id,
                    Well.well_type.in_([
                        WellType.NEGATIVE_CONTROL_NO_TEMPLATE,
                        WellType.NEGATIVE_CONTROL_NO_DYE,
                        WellType.BLANK
                    ])
                ).count()

                fitted_count += Well.query.join(FitResult).filter(
                    Well.plate_id == plate_id,
                    Well.well_type == WellType.SAMPLE,
                    FitResult.converged == True
                ).count()

            return (
                selected_ids,
                str(len(selected_ids)),
                str(sample_count),
                str(negative_count),
                str(fitted_count),
                len(selected_ids) == 0,  # Disable button if nothing selected
            )

        except Exception as e:
            print(f"Error updating selection: {e}")
            return [], "0", "0", "0", "0", True

    @app.callback(
        Output({"type": "fitting-plate-checkbox", "index": ALL}, "checked", allow_duplicate=True),
        Input("fitting-select-all-btn", "n_clicks"),
        Input("fitting-clear-all-btn", "n_clicks"),
        State({"type": "fitting-plate-checkbox", "index": ALL}, "id"),
        prevent_initial_call=True,
    )
    def select_all_clear_all(select_all, clear_all, checkbox_ids):
        """Handle select all / clear all buttons."""
        # Guard: Only proceed if buttons were actually clicked
        # This prevents the callback from firing when buttons are dynamically created
        if not select_all and not clear_all:
            raise PreventUpdate

        if not checkbox_ids:
            raise PreventUpdate

        triggered = ctx.triggered_id
        if triggered == "fitting-select-all-btn" and select_all:
            return [True] * len(checkbox_ids)
        elif triggered == "fitting-clear-all-btn" and clear_all:
            return [False] * len(checkbox_ids)

        raise PreventUpdate

    # Sync button clicks to store using clientside callback (tolerates missing elements)
    app.clientside_callback(
        """
        function(n_clicks, current) {
            if (n_clicks && n_clicks > 0) {
                return (current || 0) + 1;
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("fitting-start-btn-clicks", "data"),
        Input("fitting-start-btn", "n_clicks"),
        State("fitting-start-btn-clicks", "data"),
        prevent_initial_call=True,
    )

    # Sync button clicks to persistent stores (avoids issues with dynamic content)
    app.clientside_callback(
        "function(n, current) { return n ? (current || 0) + 1 : window.dash_clientside.no_update; }",
        Output("fitting-continue-fc-clicks", "data"),
        Input("fitting-continue-fc-btn", "n_clicks"),
        State("fitting-continue-fc-clicks", "data"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        "function(n, current) { return n ? (current || 0) + 1 : window.dash_clientside.no_update; }",
        Output("fc-back-clicks", "data"),
        Input("fc-back-btn", "n_clicks"),
        State("fc-back-clicks", "data"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        "function(n, current) { return n ? (current || 0) + 1 : window.dash_clientside.no_update; }",
        Output("fc-compute-clicks", "data"),
        Input("fc-compute-btn", "n_clicks"),
        State("fc-compute-clicks", "data"),
        prevent_initial_call=True,
    )

    # Sync publish/unpublish button clicks to stores
    app.clientside_callback(
        "function(n, current) { return n ? (current || 0) + 1 : window.dash_clientside.no_update; }",
        Output("fc-publish-clicks", "data"),
        Input("fc-publish-btn", "n_clicks"),
        State("fc-publish-clicks", "data"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        "function(n, current) { return n ? (current || 0) + 1 : window.dash_clientside.no_update; }",
        Output("fc-unpublish-clicks", "data"),
        Input("fc-unpublish-btn", "n_clicks"),
        State("fc-unpublish-clicks", "data"),
        prevent_initial_call=True,
    )

    # Sync Step 1 UI values to persistent stores
    app.clientside_callback(
        "function(value) { return value || 'delayed_exponential'; }",
        Output("fitting-model-select-store", "data"),
        Input("fitting-model-select", "value"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        "function(checked) { return checked || false; }",
        Output("fitting-force-refit-store", "data"),
        Input("fitting-force-refit-checkbox", "checked"),
        prevent_initial_call=True,
    )

    @app.callback(
        Output("fitting-step-content", "children"),
        Output("fitting-workflow-stepper", "active"),
        Output("fitting-task-id-store", "data"),
        Output("fitting-progress-interval", "disabled"),
        Output("fitting-accordion-badge", "children"),
        Output("fitting-accordion-badge", "color"),
        Input("fitting-start-btn-clicks", "data"),
        Input("fitting-continue-fc-clicks", "data"),
        Input("fc-back-clicks", "data"),
        Input("fc-compute-clicks", "data"),
        Input("fc-publish-clicks", "data"),
        Input("fc-unpublish-clicks", "data"),
        State("fitting-selected-plates-store", "data"),
        State("fitting-model-select-store", "data"),
        State("fitting-force-refit-store", "data"),
        State("analysis-project-store", "data"),
        State("fitting-workflow-stepper", "active"),
        State("fitting-results-store", "data"),
        State("color-scheme-store", "data"),
        prevent_initial_call=True,
    )
    def handle_fitting_workflow(
        start_clicks, continue_fc, fc_back, fc_compute, fc_publish, fc_unpublish,
        selected_plates, model_type, force_refit, project_id, current_step,
        results_data, scheme
    ):
        """Handle workflow navigation, curve fitting execution, and publish workflow."""
        import dash_mantine_components as dmc

        triggered = ctx.triggered_id

        if triggered == "fitting-start-btn-clicks" and start_clicks:
            # Start curve fitting
            if not selected_plates or not project_id:
                raise PreventUpdate

            try:
                from flask import request
                from app.tasks.fitting_tasks import enqueue_curve_fitting

                # Get username from request headers
                username = "unknown"
                try:
                    username = request.headers.get("X-Username", "unknown")
                except RuntimeError:
                    pass

                # Enqueue the fitting task
                task_id = enqueue_curve_fitting(
                    project_id=project_id,
                    plate_ids=selected_plates,
                    username=username,
                    model_type=model_type or "delayed_exponential",
                    force_refit=force_refit or False
                )

                # Return step 2 (progress) UI
                return (
                    create_step2_fitting_progress(),
                    1,  # Step 2
                    task_id,
                    False,  # Enable polling
                    "Step 2: Fitting",
                    "yellow",
                )

            except Exception as e:
                logger.exception("Error starting fitting")
                raise PreventUpdate

        elif triggered == "fitting-continue-fc-clicks" and continue_fc:
            # Move to fold change step - pass project_id to show existing FC counts
            return (
                create_step4_fold_changes(project_id=project_id),
                3,  # Step 4
                no_update,
                True,  # Disable polling
                "Step 4: Fold Changes",
                "blue",
            )

        elif triggered == "fc-back-clicks" and fc_back:
            # Go back to results - use stored fit summary and project_id to render content
            fit_summary = results_data if results_data else {}
            dark_mode = (scheme == "dark")
            return (
                create_step3_fit_results(fit_summary, project_id=project_id, dark_mode=dark_mode),
                2,  # Step 3
                no_update,
                True,
                "Step 3: Review",
                "green",
            )

        elif triggered == "fc-compute-clicks" and fc_compute:
            # Compute fold changes using the comprehensive StatisticsService
            try:
                from app.services.statistics_service import StatisticsService
                from app.models.fit_result import FoldChange

                # Use StatisticsService which handles plate-level fold change computation
                fold_changes = StatisticsService.compute_fold_changes(
                    project_id=project_id,
                    overwrite=True  # Recompute to ensure fresh results
                )
                computed_count = len(fold_changes)

                # Get total fold change count for this project (including pre-existing)
                from app.models import Well, Plate, ExperimentalSession
                total_fcs = FoldChange.query.join(
                    Well, FoldChange.test_well_id == Well.id
                ).join(Plate).join(ExperimentalSession).filter(
                    ExperimentalSession.project_id == project_id
                ).count()

                # Stay on step 4 but update UI with results
                return (
                    create_step4_fold_changes(project_id=project_id, computed_count=computed_count),
                    3,
                    no_update,
                    True,
                    f"Step 4: {total_fcs} FCs",
                    "green",
                )

            except Exception as e:
                logger.exception("Error computing fold changes")
                # Return error state instead of raising PreventUpdate
                return (
                    create_step4_fold_changes(project_id=project_id, error_message="An unexpected error occurred while computing fold changes."),
                    3,
                    no_update,
                    True,
                    "Step 4: Error",
                    "red",
                )

        elif triggered == "fc-publish-clicks" and fc_publish:
            # Publish fitting results
            try:
                from flask import request
                from app.services.fitting_service import FittingService
                from app.models import Project

                # Get username from request headers
                username = "unknown"
                try:
                    username = request.headers.get("X-Username", "unknown")
                except RuntimeError:
                    pass

                FittingService.publish_fitting(project_id, username)

                # Re-render Step 4 with published state
                return (
                    create_step4_fold_changes(project_id=project_id),
                    3,
                    no_update,
                    True,
                    "Step 4: Published",
                    "green",
                )

            except Exception as e:
                logger.exception("Error publishing fitting")
                return (
                    create_step4_fold_changes(project_id=project_id, error_message="An unexpected error occurred while publishing fitting results."),
                    3,
                    no_update,
                    True,
                    "Step 4: Error",
                    "red",
                )

        elif triggered == "fc-unpublish-clicks" and fc_unpublish:
            # Unpublish fitting results (revert to draft)
            try:
                from flask import request
                from app.services.fitting_service import FittingService

                # Get username from request headers
                username = "unknown"
                try:
                    username = request.headers.get("X-Username", "unknown")
                except RuntimeError:
                    pass

                FittingService.unpublish_fitting(project_id, username)

                # Re-render Step 4 with draft state
                return (
                    create_step4_fold_changes(project_id=project_id),
                    3,
                    no_update,
                    True,
                    "Step 4: Draft",
                    "orange",
                )

            except Exception as e:
                logger.exception("Error unpublishing fitting")
                return (
                    create_step4_fold_changes(project_id=project_id, error_message="An unexpected error occurred while unpublishing fitting results."),
                    3,
                    no_update,
                    True,
                    "Step 4: Error",
                    "red",
                )

        raise PreventUpdate

    @app.callback(
        Output("fitting-progress-bar", "value"),
        Output("fitting-progress-text", "children"),
        Output("fitting-progress-eta", "children"),
        Output("fitting-live-success", "children"),
        Output("fitting-live-failed", "children"),
        Output("fitting-live-skipped", "children"),
        Output("fitting-step-content", "children", allow_duplicate=True),
        Output("fitting-workflow-stepper", "active", allow_duplicate=True),
        Output("fitting-progress-interval", "disabled", allow_duplicate=True),
        Output("fitting-accordion-badge", "children", allow_duplicate=True),
        Output("fitting-accordion-badge", "color", allow_duplicate=True),
        Output("fitting-results-store", "data"),
        Input("fitting-progress-interval", "n_intervals"),
        State("fitting-task-id-store", "data"),
        State("analysis-project-store", "data"),
        State("color-scheme-store", "data"),
        State("fitting-selected-plates-store", "data"),
        prevent_initial_call=True,
    )
    def poll_fitting_progress(n_intervals, task_id, project_id, scheme, selected_plates):
        """Poll fitting task progress and update UI."""
        if not task_id:
            raise PreventUpdate

        try:
            from app.models.task_progress import TaskProgress, TaskStatus

            progress = TaskProgress.get_by_task_id(task_id)
            if not progress:
                raise PreventUpdate

            progress_pct = progress.progress_percent
            current_step = progress.current_step or "Processing..."
            eta_str = progress.eta_display or ""

            # Parse extra data for live stats
            extra = progress.extra_data or {}
            success_count = str(extra.get("successful_fits", 0))
            failed_count = str(extra.get("failed_fits", 0))
            skipped_count = str(extra.get("skipped_wells", 0))

            # Check if complete
            if progress.status == TaskStatus.COMPLETED:
                # Build fit summary for Step 3
                fit_summary = {
                    "successful": int(success_count) if success_count.isdigit() else 0,
                    "failed": int(failed_count) if failed_count.isdigit() else 0,
                    "skipped": int(skipped_count) if skipped_count.isdigit() else 0,
                }
                dark_mode = (scheme == "dark")
                # Load fit results and move to step 3 - filter to plates the user
                # actually selected for fitting so the post-fit view scope matches
                # what was fitted (Bug A: previously defaulted to all plates).
                return (
                    100,
                    "Fitting complete!",
                    "",
                    success_count,
                    failed_count,
                    skipped_count,
                    create_step3_fit_results(
                        fit_summary,
                        project_id=project_id,
                        plate_ids=selected_plates or None,
                        dark_mode=dark_mode,
                    ),
                    2,  # Step 3
                    True,  # Disable polling
                    "Step 3: Review Results",
                    "green",
                    {
                        "task_id": task_id,
                        **fit_summary,
                    },
                )
            elif progress.status == TaskStatus.FAILED:
                return (
                    progress_pct,
                    f"Error: {progress.error_message or 'Unknown error'}",
                    "",
                    success_count,
                    failed_count,
                    skipped_count,
                    no_update,
                    no_update,
                    True,  # Disable polling
                    "Step 2: Failed",
                    "red",
                    None,
                )

            # Still running
            return (
                progress_pct,
                current_step,
                f"ETA: {eta_str}" if eta_str else "",
                success_count,
                failed_count,
                skipped_count,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
            )

        except Exception as e:
            print(f"Error polling progress: {e}")
            raise PreventUpdate

    @app.callback(
        Output("fitting-step-content", "children", allow_duplicate=True),
        Output("fitting-selected-wells-store", "data"),
        Input({"type": "fitting-result-row", "index": ALL}, "n_clicks"),
        State({"type": "fitting-result-row", "index": ALL}, "id"),
        State("fitting-selected-wells-store", "data"),
        State("fitting-results-store", "data"),
        State("analysis-project-store", "data"),
        State("explore-selected-plates-store", "data"),
        State("color-scheme-store", "data"),
        prevent_initial_call=True,
    )
    def handle_row_click(n_clicks_list, row_ids, current_selection, results_data, project_id, plate_ids, scheme):
        """Handle row clicks to toggle well selection and re-render Step 3."""
        if not n_clicks_list or all(n is None for n in n_clicks_list):
            raise PreventUpdate

        # Find which row was clicked
        triggered = ctx.triggered_id
        if not triggered or "index" not in triggered:
            raise PreventUpdate

        if not project_id:
            raise PreventUpdate

        clicked_well_id = triggered["index"]
        current_selection = current_selection or []

        # Toggle selection
        if clicked_well_id in current_selection:
            new_selection = [w for w in current_selection if w != clicked_well_id]
        else:
            new_selection = current_selection + [clicked_well_id]

        # Re-render Step 3 with new selection, preserving plate filter
        fit_summary = results_data if results_data else {}
        dark_mode = (scheme == "dark")
        step3_content = create_step3_fit_results(
            fit_summary,
            project_id=project_id,
            selected_well_ids=new_selection,
            plate_ids=plate_ids if plate_ids else None,
            dark_mode=dark_mode,
        )

        return step3_content, new_selection

    @app.callback(
        Output("fc-mutant-wt-count", "children"),
        Output("fc-wt-unreg-count", "children"),
        Output("fc-total-count", "children"),
        Input("fitting-workflow-stepper", "active"),
        State("analysis-project-store", "data"),
        prevent_initial_call=True,
    )
    def load_fc_stats(active_step, project_id):
        """Load fold change statistics when entering step 4."""
        if active_step != 3 or not project_id:
            raise PreventUpdate

        try:
            from app.models.fit_result import FoldChange
            from app.models import Well, Plate, ExperimentalSession, Construct

            # Count existing fold changes
            total_fc = FoldChange.query.join(
                Well, FoldChange.test_well_id == Well.id
            ).join(Plate).join(ExperimentalSession).filter(
                ExperimentalSession.project_id == project_id
            ).count()

            # Count by comparison type
            mutant_wt_count = FoldChange.query.join(
                Well, FoldChange.test_well_id == Well.id
            ).join(Plate).join(ExperimentalSession).join(
                Construct, Well.construct_id == Construct.id
            ).filter(
                ExperimentalSession.project_id == project_id,
                Construct.is_wildtype.is_(False),
                Construct.is_unregulated.is_(False)
            ).count()

            wt_unreg_count = FoldChange.query.join(
                Well, FoldChange.test_well_id == Well.id
            ).join(Plate).join(ExperimentalSession).join(
                Construct, Well.construct_id == Construct.id
            ).filter(
                ExperimentalSession.project_id == project_id,
                Construct.is_wildtype.is_(True)
            ).count()

            return str(mutant_wt_count), str(wt_unreg_count), str(total_fc)

        except Exception as e:
            print(f"Error loading FC stats: {e}")
            return "0", "0", "0"

    # Sync navigation button clicks to stores
    app.clientside_callback(
        "function(n, current) { return n ? (current || 0) + 1 : window.dash_clientside.no_update; }",
        Output("fitting-open-browser-clicks", "data"),
        Input("fitting-open-browser-btn", "n_clicks"),
        State("fitting-open-browser-clicks", "data"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        "function(n, current) { return n ? (current || 0) + 1 : window.dash_clientside.no_update; }",
        Output("fc-run-analysis-clicks", "data"),
        Input("fc-run-analysis-btn", "n_clicks"),
        State("fc-run-analysis-clicks", "data"),
        prevent_initial_call=True,
    )

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("fitting-open-browser-clicks", "data"),
        Input("fc-run-analysis-clicks", "data"),
        State("analysis-project-store", "data"),
        prevent_initial_call=True,
    )
    def navigate_from_fitting(browser_clicks, analysis_clicks, project_id):
        """Handle navigation from fitting workflow."""
        if not project_id:
            raise PreventUpdate

        triggered = ctx.triggered_id

        if triggered == "fitting-open-browser-clicks" and browser_clicks:
            return f"/project/{project_id}/curves"
        elif triggered == "fc-run-analysis-clicks" and analysis_clicks:
            # Stay on same page but scroll to analysis section
            # The analysis modal will be triggered separately
            raise PreventUpdate

        raise PreventUpdate

    # =========================================================================
    # Explore Previous Fits Panel
    # =========================================================================

    @app.callback(
        Output("previous-fits-content", "children"),
        Output("previous-fits-badge", "children"),
        Output("previous-fits-badge", "color"),
        Output("explore-selected-plates-store", "data"),
        Input("analysis-project-store", "data"),
        Input("fitting-workflow-stepper", "active"),  # Refresh when workflow changes
        State("explore-selected-plates-store", "data"),
        prevent_initial_call=False,
    )
    def load_previous_fits(project_id, _active_step, current_plate_selection):
        """Load and display previous fit results for exploration."""
        import dash_mantine_components as dmc
        from dash import html, no_update
        from dash_iconify import DashIconify

        # Only update the plate store when project changes, not on stepper changes
        triggered = ctx.triggered_id
        should_reset_selection = triggered == "analysis-project-store" or not current_plate_selection

        if not project_id:
            return (
                dmc.Text("No project selected", c="dimmed", ta="center"),
                "No Project",
                "gray",
                [] if should_reset_selection else no_update,
            )

        try:
            from app.models.fit_result import FitResult, FoldChange
            from app.models import Well, Plate, ExperimentalSession, Construct, Project
            from app.models.plate_layout import WellType
            from sqlalchemy import func

            # Get project info
            project = Project.query.get(project_id)
            if not project:
                return (
                    dmc.Text("Project not found", c="dimmed", ta="center"),
                    "Error",
                    "red",
                    [] if should_reset_selection else no_update,
                )

            is_published = getattr(project, 'fitting_published', False)

            # Count fits
            fit_count = FitResult.query.join(Well).join(Plate).join(ExperimentalSession).filter(
                ExperimentalSession.project_id == project_id,
                FitResult.converged == True
            ).count()

            total_sample_wells = Well.query.join(Plate).join(ExperimentalSession).filter(
                ExperimentalSession.project_id == project_id,
                Well.well_type == WellType.SAMPLE,
                Well.is_excluded == False
            ).count()

            # Count fold changes
            fc_count = FoldChange.query.join(
                Well, FoldChange.test_well_id == Well.id
            ).join(Plate).join(ExperimentalSession).filter(
                ExperimentalSession.project_id == project_id
            ).count()

            # Get plates with fit details
            plates = Plate.query.join(ExperimentalSession).filter(
                ExperimentalSession.project_id == project_id
            ).order_by(ExperimentalSession.date.desc(), Plate.plate_number).all()

            # Bug B: when no selection exists yet, default to plates from the
            # most recent session rather than all plates.
            latest_session_plate_ids: set[int] = set()
            if not current_plate_selection:
                latest_session = (
                    ExperimentalSession.query
                    .filter_by(project_id=project_id)
                    .order_by(ExperimentalSession.date.desc())
                    .first()
                )
                if latest_session is not None:
                    latest_session_plate_ids = {p.id for p in latest_session.plates}

            plate_items = []
            selected_plate_ids = []  # Track plate IDs for store initialization
            for plate in plates:
                # Count fits for this plate
                plate_fits = FitResult.query.join(Well).filter(
                    Well.plate_id == plate.id,
                    FitResult.converged == True
                ).count()

                plate_total = Well.query.filter(
                    Well.plate_id == plate.id,
                    Well.well_type == WellType.SAMPLE,
                    Well.is_excluded == False
                ).count()

                # Get average R-squared for this plate
                plate_r2 = FitResult.query.join(Well).filter(
                    Well.plate_id == plate.id,
                    FitResult.converged == True,
                    FitResult.r_squared.isnot(None)
                ).with_entities(func.avg(FitResult.r_squared)).scalar()

                if plate_fits > 0:
                    progress_pct = (plate_fits / plate_total * 100) if plate_total > 0 else 0
                    session_label = plate.session.batch_identifier if plate.session else "Unknown"

                    # Determine if this plate should be checked. With an existing
                    # selection, preserve it; otherwise default to plates from
                    # the latest session only (Bug B).
                    if current_plate_selection:
                        is_checked = plate.id in current_plate_selection
                    else:
                        is_checked = plate.id in latest_session_plate_ids
                    if is_checked:
                        selected_plate_ids.append(plate.id)  # Track for store initialization

                    plate_items.append(
                        dmc.Checkbox(
                            id={"type": "explore-plate-checkbox", "index": plate.id},
                            label=dmc.Stack([
                                dmc.Group([
                                    dmc.Text(f"Plate {plate.plate_number}", fw=500, size="sm"),
                                    dmc.Badge(
                                        f"{plate_fits}/{plate_total}",
                                        color="green" if plate_fits == plate_total else "blue",
                                        size="xs",
                                        variant="light",
                                    ),
                                    dmc.Badge(
                                        f"R\u00b2={plate_r2:.3f}" if plate_r2 else "R\u00b2=N/A",
                                        color="orange" if plate_r2 and plate_r2 > 0.95 else "gray",
                                        size="xs",
                                        variant="outline",
                                    ),
                                ], justify="space-between"),
                                dmc.Group([
                                    dmc.Text(session_label, size="xs", c="dimmed"),
                                    dmc.Progress(
                                        value=progress_pct,
                                        size="xs",
                                        color="green" if progress_pct == 100 else "blue",
                                        style={"width": "100px"},
                                    ),
                                ], justify="space-between"),
                            ], gap=4),
                            value=str(plate.id),
                            checked=is_checked,  # Preserve selection state
                            styles={"root": {"width": "100%"}, "body": {"width": "100%"}},
                        )
                    )

            # Determine badge status
            if fit_count == 0:
                badge_text = "No Fits"
                badge_color = "gray"
            else:
                badge_text = f"{fit_count} Fits"
                if is_published:
                    badge_text += " (Published)"
                    badge_color = "green"
                else:
                    badge_text += " (Draft)"
                    badge_color = "yellow"

            # Build the content
            content = html.Div([
                # Status banner
                dmc.Alert(
                    dmc.Group([
                        DashIconify(
                            icon="mdi:check-circle" if is_published else "mdi:pencil-circle",
                            width=20,
                            color="green" if is_published else "orange",
                        ),
                        dmc.Text([
                            dmc.Text("Published", fw=600, span=True, c="green") if is_published
                            else dmc.Text("Draft", fw=600, span=True, c="orange"),
                            f" \u2014 {fit_count} fits across {len(plate_items)} plates",
                            f", {fc_count} fold changes computed" if fc_count > 0 else "",
                        ], size="sm"),
                    ], gap="xs"),
                    color="green" if is_published else "orange",
                    variant="light",
                    mb="md",
                ),

                # Main content grid
                dmc.Grid([
                    # Left: Plate selection
                    dmc.GridCol([
                        dmc.Paper([
                            dmc.Group([
                                dmc.Text("Select Plates to View", fw=500),
                                dmc.Group([
                                    dmc.Button(
                                        "All",
                                        id="explore-select-all-btn",
                                        variant="subtle",
                                        size="compact-xs",
                                    ),
                                    dmc.Button(
                                        "None",
                                        id="explore-select-none-btn",
                                        variant="subtle",
                                        size="compact-xs",
                                    ),
                                ], gap="xs"),
                            ], justify="space-between", mb="sm"),

                            dmc.ScrollArea(
                                h=250,
                                children=[
                                    dmc.Stack(
                                        gap="xs",
                                        children=plate_items if plate_items else [
                                            dmc.Text("No plates with fits", c="dimmed", ta="center", py="xl"),
                                        ],
                                    ),
                                ],
                            ),
                        ], p="md", withBorder=True),
                    ], span=6),

                    # Right: Actions and summary
                    dmc.GridCol([
                        dmc.Paper([
                            dmc.Text("Quick Actions", fw=500, mb="sm"),

                            dmc.Stack([
                                dmc.Button(
                                    "View Selected Fit Results",
                                    id="explore-view-fits-btn",
                                    leftSection=DashIconify(icon="mdi:table-eye"),
                                    variant="filled",
                                    fullWidth=True,
                                    disabled=fit_count == 0,
                                ),
                                dmc.Button(
                                    "View Fold Changes",
                                    id="explore-view-fc-btn",
                                    leftSection=DashIconify(icon="mdi:compare-horizontal"),
                                    variant="light",
                                    fullWidth=True,
                                    disabled=fc_count == 0,
                                ),
                                dmc.Button(
                                    "Open Curve Browser",
                                    id="explore-curve-browser-btn",
                                    leftSection=DashIconify(icon="mdi:chart-line"),
                                    variant="light",
                                    fullWidth=True,
                                    disabled=fit_count == 0,
                                ),
                            ], gap="sm"),

                            dmc.Divider(my="md"),

                            # Selection summary
                            dmc.Text("Selection Summary", fw=500, mb="xs"),
                            html.Div(id="explore-selection-summary", children=[
                                dmc.Text(
                                    f"{len(plate_items)} plates selected",
                                    size="sm", c="dimmed"
                                ),
                            ]),
                        ], p="md", withBorder=True),
                    ], span=6),
                ]),
            ])

            return content, badge_text, badge_color, selected_plate_ids if should_reset_selection else no_update

        except Exception as e:
            logger.exception("Error loading previous fits")
            return (
                dmc.Text("An unexpected error occurred while loading fits.", c="red", ta="center"),
                "Error",
                "red",
                [] if should_reset_selection else no_update,
            )

    # Clientside callbacks for explore buttons
    app.clientside_callback(
        "function(n, current) { return n ? (current || 0) + 1 : window.dash_clientside.no_update; }",
        Output("explore-view-fits-clicks", "data"),
        Input("explore-view-fits-btn", "n_clicks"),
        State("explore-view-fits-clicks", "data"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        "function(n, current) { return n ? (current || 0) + 1 : window.dash_clientside.no_update; }",
        Output("explore-view-fc-clicks", "data"),
        Input("explore-view-fc-btn", "n_clicks"),
        State("explore-view-fc-clicks", "data"),
        prevent_initial_call=True,
    )

    app.clientside_callback(
        "function(n, current) { return n ? (current || 0) + 1 : window.dash_clientside.no_update; }",
        Output("explore-curve-browser-clicks", "data"),
        Input("explore-curve-browser-btn", "n_clicks"),
        State("explore-curve-browser-clicks", "data"),
        prevent_initial_call=True,
    )

    # Select all/none for explore plates
    @app.callback(
        Output({"type": "explore-plate-checkbox", "index": ALL}, "checked"),
        Input("explore-select-all-btn", "n_clicks"),
        Input("explore-select-none-btn", "n_clicks"),
        State({"type": "explore-plate-checkbox", "index": ALL}, "id"),
        prevent_initial_call=True,
    )
    def explore_select_all_none(select_all, select_none, checkbox_ids):
        """Handle select all/none for explore plates."""
        if not checkbox_ids:
            raise PreventUpdate

        triggered = ctx.triggered_id
        if triggered == "explore-select-all-btn":
            return [True] * len(checkbox_ids)
        elif triggered == "explore-select-none-btn":
            return [False] * len(checkbox_ids)

        raise PreventUpdate

    # Update selection summary and store selected plates
    @app.callback(
        Output("explore-selection-summary", "children"),
        Output("explore-selected-plates-store", "data", allow_duplicate=True),
        Input({"type": "explore-plate-checkbox", "index": ALL}, "checked"),
        State({"type": "explore-plate-checkbox", "index": ALL}, "id"),
        prevent_initial_call=True,
    )
    def update_explore_selection(checked_values, checkbox_ids):
        """Update selection summary when explore plate checkboxes change."""
        if not checkbox_ids:
            return dmc.Text("No plates available", size="sm", c="dimmed"), []

        selected_ids = [
            cb_id["index"]
            for cb_id, checked in zip(checkbox_ids, checked_values)
            if checked
        ]

        if not selected_ids:
            return dmc.Text("No plates selected", size="sm", c="dimmed"), []

        return (
            dmc.Text(f"{len(selected_ids)} plate(s) selected", size="sm", c="blue"),
            selected_ids,
        )

    @app.callback(
        Output("fitting-step-content", "children", allow_duplicate=True),
        Output("fitting-workflow-stepper", "active", allow_duplicate=True),
        Output("fitting-accordion-badge", "children", allow_duplicate=True),
        Output("fitting-accordion-badge", "color", allow_duplicate=True),
        Input("explore-view-fits-clicks", "data"),
        Input("explore-view-fc-clicks", "data"),
        State("analysis-project-store", "data"),
        State("explore-selected-plates-store", "data"),
        State("color-scheme-store", "data"),
        prevent_initial_call=True,
    )
    def handle_explore_buttons(view_fits_clicks, view_fc_clicks, project_id, selected_plates, scheme):
        """Handle explore panel button clicks to show results."""
        triggered = ctx.triggered_id

        if not project_id:
            raise PreventUpdate

        if triggered == "explore-view-fits-clicks" and view_fits_clicks:
            # Show Step 3 (fit results) with selected plates filter
            from app.layouts.analysis_results import create_step3_fit_results
            dark_mode = (scheme == "dark")
            return (
                create_step3_fit_results({}, project_id=project_id, plate_ids=selected_plates, dark_mode=dark_mode),
                2,  # Step 3
                "Viewing Fit Results",
                "blue",
            )

        elif triggered == "explore-view-fc-clicks" and view_fc_clicks:
            # Show Step 4 (fold changes) directly
            from app.layouts.analysis_results import create_step4_fold_changes
            return (
                create_step4_fold_changes(project_id=project_id),
                3,  # Step 4
                "Viewing Fold Changes",
                "blue",
            )

        raise PreventUpdate

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("explore-curve-browser-clicks", "data"),
        State("analysis-project-store", "data"),
        prevent_initial_call=True,
    )
    def navigate_to_curve_browser(clicks, project_id):
        """Navigate to curve browser from explore panel."""
        if clicks and project_id:
            return f"/project/{project_id}/curves"
        raise PreventUpdate

    # ================================================================
    # R-squared Threshold Filtering Callbacks
    # ================================================================

    def _build_thresholds_from_states(
        r2_threshold,
        plateau_threshold,
        fmax_se_threshold,
        check_outliers,
        check_shape,
        action_value,
    ):
        """Build a ReliabilityThresholds dataclass from UI state values."""
        from app.analysis.fit_reliability import ReliabilityThresholds

        thresholds = ReliabilityThresholds()
        if r2_threshold is not None:
            thresholds.r2_threshold = float(r2_threshold)
        if plateau_threshold is not None:
            thresholds.pct_plateau_bad = float(plateau_threshold)
        if fmax_se_threshold is not None:
            thresholds.f_max_se_pct_bad = float(fmax_se_threshold)
        thresholds.check_outliers = bool(check_outliers) if check_outliers is not None else True
        thresholds.check_shape = bool(check_shape) if check_shape is not None else True
        thresholds.exclude_weak = action_value == "exclude_bad_weak"
        return thresholds

    @app.callback(
        Output("r2-filter-preview-badge", "children"),
        Output("r2-filter-preview-badge", "color"),
        Input("r2-threshold-slider", "value"),
        Input("reliability-plateau-slider", "value"),
        Input("reliability-fmax-se-slider", "value"),
        Input("reliability-outlier-toggle", "checked"),
        Input("reliability-shape-toggle", "checked"),
        Input("reliability-action-radio", "value"),
        State("analysis-project-store", "data"),
        prevent_initial_call=True,
    )
    def update_r2_threshold_preview(
        r2_threshold,
        plateau_threshold,
        fmax_se_threshold,
        check_outliers,
        check_shape,
        action_value,
        project_id,
    ):
        """Update the preview badge showing how many wells would be flagged."""
        if not project_id:
            raise PreventUpdate
        try:
            from app.services.fitting_service import FittingService

            thresholds = _build_thresholds_from_states(
                r2_threshold,
                plateau_threshold,
                fmax_se_threshold,
                check_outliers,
                check_shape,
                action_value,
            )
            preview = FittingService.get_reliability_preview(project_id, thresholds)
            count = preview.get("below_threshold", 0)
            color = "orange" if count > 0 else "green"
            return f"{count} wells flagged", color
        except Exception:
            logger.exception("Failed to compute reliability preview")
            return "Error computing preview", "red"

    @app.callback(
        Output("fitting-step-content", "children", allow_duplicate=True),
        Output("r2-threshold-store", "data"),
        Input("r2-apply-threshold-btn", "n_clicks"),
        State("r2-threshold-slider", "value"),
        State("reliability-plateau-slider", "value"),
        State("reliability-fmax-se-slider", "value"),
        State("reliability-outlier-toggle", "checked"),
        State("reliability-shape-toggle", "checked"),
        State("reliability-action-radio", "value"),
        State("analysis-project-store", "data"),
        State("fitting-selected-wells-store", "data"),
        State("explore-selected-plates-store", "data"),
        State("color-scheme-store", "data"),
        prevent_initial_call=True,
    )
    def apply_r2_threshold(
        n_clicks,
        r2_threshold,
        plateau_threshold,
        fmax_se_threshold,
        check_outliers,
        check_shape,
        action_value,
        project_id,
        selected_wells,
        plate_ids,
        scheme,
    ):
        """Apply reliability filter and refresh Step 3 content."""
        if not n_clicks or not project_id:
            raise PreventUpdate

        try:
            from app.services.fitting_service import FittingService
            from app.layouts.analysis_results import create_step3_fit_results

            thresholds = _build_thresholds_from_states(
                r2_threshold,
                plateau_threshold,
                fmax_se_threshold,
                check_outliers,
                check_shape,
                action_value,
            )

            if action_value == "warn":
                # Don't write any exclusions; just refresh the view to surface badges.
                FittingService.clear_reliability_exclusions(project_id)
            else:
                FittingService.apply_reliability_filter(project_id, thresholds)

            status = FittingService.get_fc_exclusion_status(project_id)
            fit_summary = {
                "successful": status["included_in_fc"],
                "failed": 0,
                "skipped": status["excluded_from_fc"],
            }

            dark_mode = (scheme == "dark")
            step3_content = create_step3_fit_results(
                fit_summary=fit_summary,
                project_id=project_id,
                selected_well_ids=selected_wells or [],
                plate_ids=plate_ids or None,
                dark_mode=dark_mode,
            )

            # Persist a snapshot of all threshold values so a future page-load
            # can restore the user's slider state. The store is opportunistic;
            # the panel still falls back to constants.py defaults if missing.
            store_payload = {
                "r2_threshold": r2_threshold,
                "plateau_threshold": plateau_threshold,
                "fmax_se_threshold": fmax_se_threshold,
                "check_outliers": check_outliers,
                "check_shape": check_shape,
                "action": action_value,
            }
            return step3_content, store_payload

        except Exception:
            logger.exception("Error applying reliability filter")
            raise PreventUpdate from None

    @app.callback(
        Output("r2-threshold-slider", "value", allow_duplicate=True),
        Output("reliability-plateau-slider", "value", allow_duplicate=True),
        Output("reliability-fmax-se-slider", "value", allow_duplicate=True),
        Output("reliability-outlier-toggle", "checked", allow_duplicate=True),
        Output("reliability-shape-toggle", "checked", allow_duplicate=True),
        Output("reliability-action-radio", "value", allow_duplicate=True),
        Input("reliability-reset-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_reliability_thresholds(n_clicks):
        """Reset reliability filter sliders / toggles to defaults."""
        if not n_clicks:
            raise PreventUpdate
        from app.analysis import constants as _const

        return (
            _const.DEFAULT_RELIABILITY_R2_THRESHOLD,
            _const.PCT_PLATEAU_BAD,
            _const.F_MAX_SE_PCT_BAD,
            True,    # check_outliers
            False,   # check_shape (DW autocorrelation gate is off by default)
            "exclude_bad",
        )

    @app.callback(
        Output("fitting-step-content", "children", allow_duplicate=True),
        Input("r2-include-all-btn", "n_clicks"),
        State("analysis-project-store", "data"),
        State("fitting-selected-wells-store", "data"),
        State("explore-selected-plates-store", "data"),
        State("color-scheme-store", "data"),
        prevent_initial_call=True,
    )
    def include_all_wells(n_clicks, project_id, selected_wells, plate_ids, scheme):
        """Clear all R-squared exclusions and include all wells in FC calculation."""
        if not n_clicks or not project_id:
            raise PreventUpdate

        try:
            from app.services.fitting_service import FittingService
            from app.layouts.analysis_results import create_step3_fit_results

            # Clear all exclusions
            FittingService.clear_r2_exclusions(project_id)

            # Get fit summary for refreshing the view
            status = FittingService.get_fc_exclusion_status(project_id)
            fit_summary = {
                "successful": status["total_fitted_wells"],
                "failed": 0,
                "skipped": 0,
            }

            # Regenerate Step 3 content
            dark_mode = (scheme == "dark")
            step3_content = create_step3_fit_results(
                fit_summary=fit_summary,
                project_id=project_id,
                selected_well_ids=selected_wells or [],
                plate_ids=plate_ids or None,
                dark_mode=dark_mode,
            )

            return step3_content

        except Exception as e:
            import traceback
            traceback.print_exc()
            raise PreventUpdate

    @app.callback(
        Output("fitting-step-content", "children", allow_duplicate=True),
        Input({"type": "fc-inclusion-checkbox", "index": ALL}, "checked"),
        State({"type": "fc-inclusion-checkbox", "index": ALL}, "id"),
        State("analysis-project-store", "data"),
        State("fitting-selected-wells-store", "data"),
        State("explore-selected-plates-store", "data"),
        State("color-scheme-store", "data"),
        prevent_initial_call=True,
    )
    def toggle_well_fc_inclusion(checked_values, checkbox_ids, project_id, selected_wells, plate_ids, scheme):
        """
        Toggle individual well inclusion in FC calculation.

        This callback syncs with the Curve Browser's FC inclusion buttons.
        See: curve_browser_callbacks.py handle_fc_inclusion()
        Both use FittingService.set_well_fc_inclusion() for consistency.
        The underlying field is Well.exclude_from_fc (Boolean).
        """
        if not checked_values or not checkbox_ids or not project_id:
            raise PreventUpdate

        # Bug D mitigation #3: only proceed when exactly one checkbox triggered
        # this callback. Prevents spurious re-fires after a Step 3 re-render
        # remounts every checkbox (each remount can re-fire the callback with
        # the *previous* well's checked state).
        triggered_props = getattr(ctx, "triggered_prop_ids", None)
        if triggered_props is not None and len(triggered_props) != 1:
            raise PreventUpdate

        # Find which checkbox triggered the callback
        triggered = ctx.triggered_id
        if not triggered or not isinstance(triggered, dict):
            raise PreventUpdate

        well_id = triggered.get("index")
        if well_id is None:
            raise PreventUpdate

        # Find the checked value for this well
        for i, cid in enumerate(checkbox_ids):
            if cid.get("index") == well_id:
                include = checked_values[i]
                break
        else:
            raise PreventUpdate

        try:
            from app.services.fitting_service import FittingService
            from app.layouts.analysis_results import create_step3_fit_results
            from app.models import Well as _Well

            # Bug D mitigation #1: idempotency guard. Short-circuit if the DB
            # already reflects the requested state — stops redundant re-fires
            # from re-asserting state on a different well than the user clicked.
            current_well = _Well.query.get(well_id)
            if current_well is None:
                raise PreventUpdate
            currently_included = not bool(current_well.exclude_from_fc)
            if currently_included == bool(include):
                raise PreventUpdate

            # Toggle the well's FC inclusion
            FittingService.set_well_fc_inclusion(well_id, include)

            # Get fit summary for refreshing the view
            status = FittingService.get_fc_exclusion_status(project_id)
            fit_summary = {
                "successful": status["included_in_fc"],
                "failed": 0,
                "skipped": status["excluded_from_fc"],
            }

            # Regenerate Step 3 content
            dark_mode = (scheme == "dark")
            step3_content = create_step3_fit_results(
                fit_summary=fit_summary,
                project_id=project_id,
                selected_well_ids=selected_wells or [],
                plate_ids=plate_ids or None,
                dark_mode=dark_mode,
            )

            return step3_content

        except Exception as e:
            import traceback
            traceback.print_exc()
            raise PreventUpdate
