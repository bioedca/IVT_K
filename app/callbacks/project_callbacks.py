"""
Callbacks for project management UI.

Phase 2.8: Project dashboard UI with hub navigation (F2.5)
Phase 2.9: Project settings (F2.1)
"""
from dash import callback, Input, Output, State, ctx, no_update, html, ALL
import dash_mantine_components as dmc
import json

from app.services.project_service import ProjectService, ProjectValidationError
from app.services.construct_service import ConstructService
from app.services.plate_layout_service import PlateLayoutService
from app.layouts.project_list import create_project_card, create_empty_projects_message
from app.logging_config import get_logger

logger = get_logger(__name__)


def register_project_callbacks(app):
    """Register all project-related callbacks."""

    # ==================== Project List Callbacks ====================

    @app.callback(
        Output("project-cards-container", "children"),
        [
            Input("project-filter-status", "value"),
            Input("project-search-input", "value")
        ],
        prevent_initial_call=False
    )
    def load_project_cards(status_filter, search_term):
        """Load project cards based on filters."""

        try:
            # Fetch all non-deleted projects (including archived for filter)
            all_projects = ProjectService.list_projects(include_archived=True)

            # Apply status filter
            if status_filter == "draft":
                projects = [p for p in all_projects if p.is_draft and not p.is_archived]
            elif status_filter == "published":
                projects = [p for p in all_projects if not p.is_draft and not p.is_archived]
            elif status_filter == "archived":
                projects = [p for p in all_projects if p.is_archived]
            else:  # "all" - exclude archived by default
                projects = [p for p in all_projects if not p.is_archived]

            # Apply search
            if search_term:
                search_lower = search_term.lower()
                projects = [
                    p for p in projects
                    if search_lower in p.name.lower() or
                    (p.description and search_lower in p.description.lower())
                ]

            if not projects:
                # Show "no matches" if projects exist but don't match filter,
                # or "create first" if no projects exist at all
                is_filtered = len(all_projects) > 0
                return create_empty_projects_message(is_filtered=is_filtered)

            # Create project cards
            cards = []
            for project in projects:
                stats = ProjectService.get_project_statistics(project.id)
                project_data = {
                    "id": project.id,
                    "name": project.name,
                    "description": project.description,
                    "is_draft": project.is_draft,
                    "is_archived": project.is_archived,
                    "plate_format": project.plate_format.value,
                    "construct_count": stats.get("construct_count", 0),
                    "session_count": stats.get("session_count", 0)
                }
                cards.append(create_project_card(project_data))

            return html.Div(cards)

        except Exception as e:
            logger.exception("Error loading projects")
            return dmc.Alert(
                title="Error loading projects",
                color="red",
                children="An unexpected error occurred while loading projects."
            )

    @app.callback(
        Output("create-project-modal", "opened"),
        [
            Input("create-project-btn", "n_clicks"),
            Input("create-first-project-btn", "n_clicks"),
            Input("cancel-create-project-btn", "n_clicks"),
            Input("submit-create-project-btn", "n_clicks")
        ],
        State("create-project-modal", "opened"),
        prevent_initial_call=True
    )
    def toggle_create_modal(open1, open2, cancel, submit, is_open):
        """Toggle the create project modal."""
        triggered = ctx.triggered_id
        if triggered in ["create-project-btn", "create-first-project-btn"]:
            return True
        return False

    @app.callback(
        [
            Output("project-cards-container", "children", allow_duplicate=True),
            Output("new-project-name", "value"),
            Output("new-project-description", "value")
        ],
        Input("submit-create-project-btn", "n_clicks"),
        [
            State("new-project-name", "value"),
            State("new-project-description", "value"),
            State("new-project-plate-format", "value"),
            State("new-project-reporter", "value"),
            State("user-store", "data")
        ],
        prevent_initial_call=True
    )
    def create_new_project(n_clicks, name, description, plate_format, reporter, user_data):
        """Create a new project."""
        if not n_clicks or not name:
            return no_update, no_update, no_update

        username = (user_data.get("username") if user_data else None) or "anonymous"

        try:
            from app.models.project import PlateFormat
            pf = PlateFormat.PLATE_384 if plate_format == "384" else PlateFormat.PLATE_96

            project = ProjectService.create_project(
                name=name,
                username=username,
                description=description,
                plate_format=pf,
                reporter_system=reporter
            )

            # Reload project list
            projects = ProjectService.list_projects()
            cards = []
            for p in [pr for pr in projects if not pr.is_archived]:
                stats = ProjectService.get_project_statistics(p.id)
                project_data = {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "is_draft": p.is_draft,
                    "is_archived": p.is_archived,
                    "plate_format": p.plate_format.value,
                    "construct_count": stats.get("construct_count", 0),
                    "session_count": stats.get("session_count", 0)
                }
                cards.append(create_project_card(project_data))

            return html.Div(cards), "", ""

        except ProjectValidationError as e:
            logger.warning("Project creation validation error", error=str(e))
            return dmc.Alert(title="Error", color="red", children=str(e)), name, description

    # ==================== Delete Project Callbacks ====================

    @app.callback(
        Output("delete-project-modal", "opened"),
        Output("delete-project-message", "children"),
        Output("delete-project-id-store", "data"),
        Input({"type": "delete-project-btn", "index": ALL}, "n_clicks"),
        Input("cancel-delete-project-btn", "n_clicks"),
        Input("confirm-delete-project-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_delete_modal(delete_clicks, cancel_click, confirm_click):
        """Open/close the delete project confirmation modal."""
        triggered = ctx.triggered_id
        if triggered == "cancel-delete-project-btn" or triggered == "confirm-delete-project-btn":
            return False, no_update, None

        # Pattern-matching trigger from delete-project-btn
        if isinstance(triggered, dict) and triggered.get("type") == "delete-project-btn":
            project_id = triggered["index"]
            # Any click values that are None mean the button wasn't actually clicked
            if not any(c for c in delete_clicks if c):
                return no_update, no_update, no_update
            project = ProjectService.get_project(project_id)
            name = project.name if project else f"Project {project_id}"
            return (
                True,
                f'Are you sure you want to delete "{name}"?',
                project_id,
            )

        return no_update, no_update, no_update

    @app.callback(
        Output("project-cards-container", "children", allow_duplicate=True),
        Input("confirm-delete-project-btn", "n_clicks"),
        State("delete-project-id-store", "data"),
        State("user-store", "data"),
        prevent_initial_call=True,
    )
    def delete_project(n_clicks, project_id, user_data):
        """Delete a project and refresh the list."""
        if not n_clicks or not project_id:
            return no_update

        username = (user_data.get("username") if user_data else None) or "anonymous"

        try:
            ProjectService.delete_project(project_id, username, force=True)

            # Reload project list
            projects = ProjectService.list_projects()
            cards = []
            for p in [pr for pr in projects if not pr.is_archived]:
                stats = ProjectService.get_project_statistics(p.id)
                project_data = {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "is_draft": p.is_draft,
                    "is_archived": p.is_archived,
                    "plate_format": p.plate_format.value,
                    "construct_count": stats.get("construct_count", 0),
                    "session_count": stats.get("session_count", 0)
                }
                cards.append(create_project_card(project_data))

            if not cards:
                return create_empty_projects_message()
            return html.Div(cards)

        except ProjectValidationError as e:
            logger.warning("Project deletion validation error", error=str(e))
            return dmc.Alert(title="Delete Failed", color="red", children=str(e))

    # ==================== Archive/Unarchive from Project List ====================

    @app.callback(
        Output("project-cards-container", "children", allow_duplicate=True),
        Input({"type": "archive-project-btn", "index": ALL}, "n_clicks"),
        State("user-store", "data"),
        State("project-filter-status", "value"),
        prevent_initial_call=True,
    )
    def toggle_archive_from_list(archive_clicks, user_data, status_filter):
        """Archive or unarchive a project from the project list."""
        triggered = ctx.triggered_id
        if not isinstance(triggered, dict) or triggered.get("type") != "archive-project-btn":
            return no_update
        if not any(c for c in archive_clicks if c):
            return no_update

        project_id = triggered["index"]
        username = (user_data.get("username") if user_data else None) or "anonymous"

        try:
            project = ProjectService.get_project(project_id)
            if not project:
                return no_update

            # Toggle archived state via service (handles audit log + commit)
            new_archived = not project.is_archived
            ProjectService.update_project(
                project_id, username, is_archived=new_archived
            )

            # Reload project list with current filter
            all_projects = ProjectService.list_projects(include_archived=True)

            if status_filter == "draft":
                projects = [p for p in all_projects if p.is_draft and not p.is_archived]
            elif status_filter == "published":
                projects = [p for p in all_projects if not p.is_draft and not p.is_archived]
            elif status_filter == "archived":
                projects = [p for p in all_projects if p.is_archived]
            else:
                projects = [p for p in all_projects if not p.is_archived]

            if not projects:
                return create_empty_projects_message(is_filtered=len(all_projects) > 0)

            cards = []
            for p in projects:
                stats = ProjectService.get_project_statistics(p.id)
                project_data = {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "is_draft": p.is_draft,
                    "is_archived": p.is_archived,
                    "plate_format": p.plate_format.value,
                    "construct_count": stats.get("construct_count", 0),
                    "session_count": stats.get("session_count", 0),
                }
                cards.append(create_project_card(project_data))
            return html.Div(cards)

        except Exception as e:
            logger.exception("Error toggling archive from project list")
            return dmc.Alert(title="Error", color="red", children="An unexpected error occurred. Please try again.")

    # ==================== Settings Navigation Callbacks ====================

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        [
            Input("settings-back-btn", "n_clicks"),
            Input("settings-cancel-btn", "n_clicks"),
        ],
        State("settings-project-store", "data"),
        prevent_initial_call=True,
    )
    def navigate_back_from_settings(back_clicks, cancel_clicks, store_data):
        """Navigate back to project hub from settings page."""
        if not store_data or not store_data.get("project_id"):
            return no_update
        return f"/project/{store_data['project_id']}"

    # ==================== Project Settings Callbacks ====================

    @app.callback(
        [
            Output("settings-project-name", "value"),
            Output("settings-project-description", "value"),
            Output("settings-reporter-system", "value"),
            Output("settings-plate-format", "value"),
            Output("settings-plate-format", "disabled"),
            Output("settings-project-notes", "value"),
            Output("settings-precision-target", "value"),
            Output("settings-fc-threshold", "value"),
            Output("settings-kinetic-model", "value"),
            Output("settings-qc-cv-threshold", "value"),
            Output("settings-qc-outlier-threshold", "value"),
            Output("settings-qc-drift-threshold", "value"),
            Output("settings-qc-saturation-threshold", "value"),
            Output("settings-qc-snr-threshold", "value"),
            Output("settings-qc-empty-well-threshold", "value"),
            Output("settings-lod-coverage", "value"),
            Output("settings-loq-coverage", "value"),
            Output("settings-has-ligand", "checked"),
            Output("settings-ligand-name", "value"),
            Output("settings-ligand-unit", "value"),
            Output("settings-ligand-max-conc", "value")
        ],
        Input("settings-project-store", "data"),
        prevent_initial_call=False
    )
    def load_project_settings(store_data):
        """Load project settings into the form."""
        if not store_data or not store_data.get("project_id"):
            return [no_update] * 21

        project_id = store_data["project_id"]
        project = ProjectService.get_project(project_id)

        if not project:
            return [no_update] * 21

        # Check if plate format can be changed (no plates uploaded)
        plate_format_disabled = ProjectService.has_plates(project.id)

        return (
            project.name,
            project.description or "",
            project.reporter_system or "",
            project.plate_format.value,
            plate_format_disabled,
            project.notes or "",
            project.precision_target,
            project.meaningful_fc_threshold,
            project.kinetic_model_type,
            project.qc_cv_threshold,
            project.qc_outlier_threshold,
            project.qc_drift_threshold,
            project.qc_saturation_threshold,
            project.qc_snr_threshold,
            project.qc_empty_well_threshold,
            project.lod_coverage_factor,
            project.loq_coverage_factor,
            project.has_ligand_conditions,
            project.ligand_name or "",
            project.ligand_unit,
            project.ligand_max_concentration
        )

    @app.callback(
        Output("ligand-settings-container", "style"),
        Input("settings-has-ligand", "checked"),
        prevent_initial_call=False
    )
    def toggle_ligand_settings(has_ligand):
        """Show/hide ligand settings based on checkbox."""
        if has_ligand:
            return {"display": "block"}
        return {"display": "none"}

    @app.callback(
        Output("settings-notification-container", "children"),
        Input("settings-save-btn", "n_clicks"),
        [
            State("settings-project-store", "data"),
            State("settings-project-name", "value"),
            State("settings-project-description", "value"),
            State("settings-reporter-system", "value"),
            State("settings-plate-format", "value"),
            State("settings-project-notes", "value"),
            State("settings-precision-target", "value"),
            State("settings-fc-threshold", "value"),
            State("settings-kinetic-model", "value"),
            State("settings-qc-cv-threshold", "value"),
            State("settings-qc-outlier-threshold", "value"),
            State("settings-qc-drift-threshold", "value"),
            State("settings-qc-saturation-threshold", "value"),
            State("settings-qc-snr-threshold", "value"),
            State("settings-qc-empty-well-threshold", "value"),
            State("settings-lod-coverage", "value"),
            State("settings-loq-coverage", "value"),
            State("settings-has-ligand", "checked"),
            State("settings-ligand-name", "value"),
            State("settings-ligand-unit", "value"),
            State("settings-ligand-max-conc", "value"),
            State("user-store", "data")
        ],
        prevent_initial_call=True
    )
    def save_project_settings(
        n_clicks, store_data, name, description, reporter, plate_format, notes,
        precision_target, fc_threshold, kinetic_model,
        qc_cv, qc_outlier, qc_drift, qc_saturation, qc_snr, qc_empty,
        lod_coverage, loq_coverage,
        has_ligand, ligand_name, ligand_unit, ligand_max_conc,
        user_data
    ):
        """Save project settings."""
        if not n_clicks or not store_data or not store_data.get("project_id"):
            return no_update

        username = (user_data.get("username") if user_data else None) or "anonymous"
        project_id = store_data["project_id"]

        try:
            from app.models.project import PlateFormat
            pf = PlateFormat.PLATE_384 if plate_format == "384" else PlateFormat.PLATE_96

            ProjectService.update_project(
                project_id=project_id,
                username=username,
                name=name,
                description=description,
                reporter_system=reporter,
                plate_format=pf,
                notes=notes,
                precision_target=precision_target,
                meaningful_fc_threshold=fc_threshold,
                kinetic_model_type=kinetic_model,
                qc_cv_threshold=qc_cv,
                qc_outlier_threshold=qc_outlier,
                qc_drift_threshold=qc_drift,
                qc_saturation_threshold=qc_saturation,
                qc_snr_threshold=qc_snr,
                qc_empty_well_threshold=qc_empty,
                lod_coverage_factor=lod_coverage,
                loq_coverage_factor=loq_coverage,
                has_ligand_conditions=has_ligand,
                ligand_name=ligand_name if has_ligand else None,
                ligand_unit=ligand_unit if has_ligand else "µM",
                ligand_max_concentration=ligand_max_conc if has_ligand else None
            )

            return dmc.Notification(
                title="Settings Saved",
                message="Project settings have been updated successfully.",
                color="green",
                action="show",
                autoClose=3000
            )

        except ProjectValidationError as e:
            logger.warning("Project settings validation error", error=str(e))
            return dmc.Notification(
                title="Error",
                message=str(e),
                color="red",
                action="show"
            )

    # ==================== Project Dashboard Callbacks ====================

    @app.callback(
        [
            Output("dashboard-title-container", "children"),
            Output("dashboard-construct-count", "children"),
            Output("dashboard-layout-count", "children"),
            Output("dashboard-session-count", "children"),
            Output("dashboard-analysis-count", "children"),
            Output("check-unregulated", "checked"),
            Output("check-families", "checked"),
            Output("check-layout", "checked"),
            Output("check-data", "checked"),
            Output("check-analysis", "checked")
        ],
        Input("dashboard-project-store", "data"),
        prevent_initial_call=False
    )
    def load_dashboard_data(store_data):
        """Load project dashboard data."""
        if not store_data or not store_data.get("project_id"):
            return [no_update] * 10

        project_id = store_data["project_id"]

        try:
            project = ProjectService.get_project(project_id)
            if not project:
                return [no_update] * 10

            stats = ProjectService.get_project_statistics(project_id)

            # Title section
            status_color = "blue" if project.is_draft else "green"
            status_text = "Draft" if project.is_draft else "Published"
            title_content = [
                dmc.Group(
                    children=[
                        dmc.Title(project.name, order=2),
                        dmc.Badge(status_text, color=status_color, variant="light")
                    ],
                    gap="sm"
                ),
                dmc.Text(project.description or "No description", size="sm", c="dimmed")
            ]

            # Completeness checks
            has_unregulated = ConstructService.get_unregulated_construct(project_id) is not None
            families = ConstructService.get_families(project_id)
            has_families = len([f for f in families if not f.get("is_universal")]) > 0
            layouts = PlateLayoutService.list_layouts(project_id, templates_only=True)
            has_valid_layout = any(
                PlateLayoutService.validate_layout(l.id)[0] for l in layouts
            ) if layouts else False
            has_data = stats.get("session_count", 0) > 0
            has_analysis = stats.get("analysis_count", 0) > 0

            return (
                title_content,
                dmc.Text(str(stats.get("construct_count", 0)), fw=700, size="xl"),
                dmc.Text(str(len(layouts)), fw=700, size="xl"),
                dmc.Text(str(stats.get("session_count", 0)), fw=700, size="xl"),
                dmc.Text(str(stats.get("analysis_count", 0)), fw=700, size="xl"),
                has_unregulated,
                has_families,
                has_valid_layout,
                has_data,
                has_analysis
            )

        except Exception as e:
            logger.exception("Error loading dashboard data")
            return [
                dmc.Alert("Unable to load dashboard data. Please try again.", color="red", variant="light"),
            ] + [no_update] * 9

    # ==================== Storage & Archive Callbacks (Phase H.3) ====================

    @app.callback(
        Output("storage-usage-container", "children"),
        Input("settings-tabs", "value"),
        State("settings-project-store", "data"),
        prevent_initial_call=True
    )
    def load_storage_usage(tab_value, store_data):
        """Load storage usage when Storage tab is selected."""
        if tab_value != "storage" or not store_data or not store_data.get("project_id"):
            return no_update

        try:
            from app.services.project_storage_service import ProjectStorageService

            project_id = store_data["project_id"]
            usage = ProjectStorageService.calculate_storage_usage(project_id)

            # Create breakdown display
            breakdown_items = []
            for category, size in usage.breakdown.items():
                if size > 0:
                    if size < 1024:
                        size_str = f"{size} B"
                    elif size < 1024 * 1024:
                        size_str = f"{size / 1024:.1f} KB"
                    else:
                        size_str = f"{size / (1024 * 1024):.1f} MB"

                    breakdown_items.append(
                        dmc.Group(
                            children=[
                                dmc.Text(category.replace("_", " ").title(), size="sm"),
                                dmc.Text(size_str, size="sm", c="dimmed")
                            ],
                            justify="space-between"
                        )
                    )

            return dmc.Stack(
                children=[
                    dmc.Group(
                        children=[
                            dmc.Text("Total Storage:", fw=500),
                            dmc.Badge(
                                usage.total_formatted,
                                size="lg",
                                color="blue"
                            )
                        ]
                    ),
                    dmc.Text(f"{usage.file_count} files", size="sm", c="dimmed"),
                    dmc.Divider(my="sm"),
                    dmc.Text("Breakdown by Category:", size="sm", fw=500),
                    *breakdown_items
                ] if usage.total_bytes > 0 else [
                    dmc.Text("No data files stored for this project.", c="dimmed")
                ],
                gap="xs"
            )

        except Exception as e:
            logger.exception("Error loading storage usage")
            return dmc.Alert(
                "An unexpected error occurred while loading storage usage.",
                color="red"
            )

    @app.callback(
        Output("activity-status-container", "children"),
        Input("settings-tabs", "value"),
        State("settings-project-store", "data"),
        prevent_initial_call=True
    )
    def load_activity_status(tab_value, store_data):
        """Load activity status when Storage tab is selected."""
        if tab_value != "storage" or not store_data or not store_data.get("project_id"):
            return no_update

        try:
            from app.services.project_storage_service import ProjectStorageService

            project_id = store_data["project_id"]
            status = ProjectStorageService.get_activity_status(project_id)

            last_activity_str = "Unknown"
            if status.last_activity:
                last_activity_str = status.last_activity.strftime("%Y-%m-%d %H:%M")

            return dmc.Stack(
                children=[
                    dmc.Group(
                        children=[
                            dmc.Text("Status:", fw=500),
                            dmc.Badge(
                                status.status_label,
                                color=status.status_color,
                                size="lg"
                            )
                        ]
                    ),
                    dmc.Group(
                        children=[
                            dmc.Text("Last Activity:", size="sm"),
                            dmc.Text(last_activity_str, size="sm", c="dimmed")
                        ]
                    ),
                    dmc.Group(
                        children=[
                            dmc.Text("Days Since Activity:", size="sm"),
                            dmc.Text(str(status.days_inactive), size="sm", c="dimmed")
                        ]
                    ),
                    dmc.Alert(
                        "This project has been inactive for 6+ months and may be archived.",
                        color="yellow",
                        title="Inactivity Warning"
                    ) if status.status == "inactive" else None
                ],
                gap="xs"
            )

        except Exception as e:
            logger.exception("Error loading activity status")
            return dmc.Alert(
                "An unexpected error occurred while loading activity status.",
                color="red"
            )

    @app.callback(
        [
            Output("archive-status-container", "children"),
            Output("settings-archive-btn", "style"),
            Output("settings-restore-btn", "style")
        ],
        Input("settings-tabs", "value"),
        State("settings-project-store", "data"),
        prevent_initial_call=True
    )
    def load_archive_status(tab_value, store_data):
        """Load archive status when Storage tab is selected."""
        if tab_value != "storage" or not store_data or not store_data.get("project_id"):
            return no_update, no_update, no_update

        try:
            from app.services.project_storage_service import ProjectStorageService

            project_id = store_data["project_id"]
            status = ProjectStorageService.get_archive_status(project_id)

            if status.get("is_archived"):
                # Project is archived
                archived_at = status.get("archived_at", "Unknown")
                original_size = status.get("original_size", 0)
                compressed_size = status.get("compressed_size", 0)

                if original_size < 1024 * 1024:
                    orig_str = f"{original_size / 1024:.1f} KB"
                else:
                    orig_str = f"{original_size / (1024 * 1024):.1f} MB"

                if compressed_size < 1024 * 1024:
                    comp_str = f"{compressed_size / 1024:.1f} KB"
                else:
                    comp_str = f"{compressed_size / (1024 * 1024):.1f} MB"

                content = dmc.Stack(
                    children=[
                        dmc.Badge("Archived", color="orange", size="lg"),
                        dmc.Text(f"Archived: {archived_at[:10] if archived_at else 'Unknown'}", size="sm"),
                        dmc.Text(f"Original size: {orig_str}", size="sm", c="dimmed"),
                        dmc.Text(f"Compressed size: {comp_str}", size="sm", c="dimmed"),
                        dmc.Text(
                            f"Compression ratio: {status.get('compression_ratio', 0):.1f}%",
                            size="sm",
                            c="dimmed"
                        )
                    ],
                    gap="xs"
                )
                return content, {"display": "none"}, {"display": "block"}
            else:
                # Project is active
                content = dmc.Stack(
                    children=[
                        dmc.Badge("Active", color="green", size="lg"),
                        dmc.Text(
                            f"Current size: {status.get('current_size_formatted', '0 B')}",
                            size="sm",
                            c="dimmed"
                        ),
                        dmc.Text(
                            f"{status.get('file_count', 0)} files",
                            size="sm",
                            c="dimmed"
                        )
                    ],
                    gap="xs"
                )
                can_archive = status.get("can_archive", False)
                archive_style = {"display": "block"} if can_archive else {"display": "none"}
                return content, archive_style, {"display": "none"}

        except Exception as e:
            logger.exception("Error loading archive status")
            return (
                dmc.Alert("An unexpected error occurred while loading archive status.", color="red"),
                {"display": "none"},
                {"display": "none"}
            )

    @app.callback(
        Output("archive-confirm-modal", "opened"),
        [
            Input("settings-archive-btn", "n_clicks"),
            Input("archive-cancel-btn", "n_clicks"),
            Input("archive-confirm-btn", "n_clicks")
        ],
        State("archive-confirm-modal", "opened"),
        prevent_initial_call=True
    )
    def toggle_archive_modal(archive_click, cancel_click, confirm_click, is_open):
        """Toggle the archive confirmation modal."""
        triggered = ctx.triggered_id
        if triggered == "settings-archive-btn":
            return True
        return False

    @app.callback(
        [
            Output("archive-status-container", "children", allow_duplicate=True),
            Output("settings-archive-btn", "style", allow_duplicate=True),
            Output("settings-restore-btn", "style", allow_duplicate=True),
            Output("settings-notification-container", "children", allow_duplicate=True)
        ],
        Input("archive-confirm-btn", "n_clicks"),
        [
            State("settings-project-store", "data"),
            State("archive-reason", "value"),
            State("user-store", "data")
        ],
        prevent_initial_call=True
    )
    def archive_project(n_clicks, store_data, reason, user_data):
        """Archive the project."""
        if not n_clicks or not store_data or not store_data.get("project_id"):
            return no_update, no_update, no_update, no_update

        project_id = store_data["project_id"]
        username = (user_data.get("username") if user_data else None) or "anonymous"

        try:
            from pathlib import Path
            from flask import current_app
            import sys

            # Import archiver
            base_dir = Path(current_app.root_path).parent
            sys.path.insert(0, str(base_dir / "scripts"))
            from archive_project import ProjectArchiver

            # Get project
            project = ProjectService.get_project(project_id)
            if not project:
                return no_update, no_update, no_update, dmc.Notification(
                    title="Error",
                    message="Project not found",
                    color="red",
                    action="show"
                )

            # Archive
            archiver = ProjectArchiver(base_dir)
            result = archiver.archive_project(project_id, project.name, username)

            if result.get("success"):
                # Update project status
                from app.extensions import db
                project.is_archived = True
                db.session.commit()

                # Create archive record
                from app.models.archive import ProjectArchive
                archive = ProjectArchive(
                    project_id=project_id,
                    archive_path=result.get("archive_path", ""),
                    archived_by=username,
                    original_size=result.get("original_size", 0),
                    compressed_size=result.get("compressed_size", 0)
                )
                db.session.add(archive)
                db.session.commit()

                return (
                    dmc.Stack(
                        children=[
                            dmc.Badge("Archived", color="orange", size="lg"),
                            dmc.Text("Project has been archived successfully.", size="sm")
                        ],
                        gap="xs"
                    ),
                    {"display": "none"},
                    {"display": "block"},
                    dmc.Notification(
                        title="Project Archived",
                        message="The project has been archived to cold storage.",
                        color="green",
                        action="show",
                        autoClose=5000
                    )
                )
            else:
                return no_update, no_update, no_update, dmc.Notification(
                    title="Archive Failed",
                    message=result.get("error", "Unknown error"),
                    color="red",
                    action="show"
                )

        except Exception as e:
            logger.exception("Error archiving project")
            return no_update, no_update, no_update, dmc.Notification(
                title="Archive Failed",
                message="An unexpected error occurred while archiving the project.",
                color="red",
                action="show"
            )

    @app.callback(
        [
            Output("archive-status-container", "children", allow_duplicate=True),
            Output("settings-archive-btn", "style", allow_duplicate=True),
            Output("settings-restore-btn", "style", allow_duplicate=True),
            Output("settings-notification-container", "children", allow_duplicate=True)
        ],
        Input("settings-restore-btn", "n_clicks"),
        [
            State("settings-project-store", "data"),
            State("user-store", "data")
        ],
        prevent_initial_call=True
    )
    def restore_project(n_clicks, store_data, user_data):
        """Restore an archived project."""
        if not n_clicks or not store_data or not store_data.get("project_id"):
            return no_update, no_update, no_update, no_update

        project_id = store_data["project_id"]
        username = (user_data.get("username") if user_data else None) or "anonymous"

        try:
            from pathlib import Path
            from flask import current_app
            import sys

            # Import archiver
            base_dir = Path(current_app.root_path).parent
            sys.path.insert(0, str(base_dir / "scripts"))
            from archive_project import ProjectArchiver

            # Restore
            archiver = ProjectArchiver(base_dir)
            result = archiver.restore_project(project_id, username)

            if result.get("success"):
                # Update project status
                from app.extensions import db
                project = ProjectService.get_project(project_id)
                if project:
                    project.is_archived = False
                    ProjectService.update_activity(project.id)
                    db.session.commit()

                # Update archive record
                from app.models.archive import ProjectArchive
                archive = ProjectArchive.query.filter_by(project_id=project_id).first()
                if archive:
                    from datetime import datetime, timezone
                    archive.restored_at = datetime.now(timezone.utc)
                    archive.restored_by = username
                    db.session.commit()

                return (
                    dmc.Stack(
                        children=[
                            dmc.Badge("Active", color="green", size="lg"),
                            dmc.Text("Project has been restored.", size="sm")
                        ],
                        gap="xs"
                    ),
                    {"display": "block"},
                    {"display": "none"},
                    dmc.Notification(
                        title="Project Restored",
                        message="The project has been restored from archive.",
                        color="green",
                        action="show",
                        autoClose=5000
                    )
                )
            else:
                return no_update, no_update, no_update, dmc.Notification(
                    title="Restore Failed",
                    message=result.get("error", "Unknown error"),
                    color="red",
                    action="show"
                )

        except Exception as e:
            logger.exception("Error restoring project")
            return no_update, no_update, no_update, dmc.Notification(
                title="Restore Failed",
                message="An unexpected error occurred while restoring the project.",
                color="red",
                action="show"
            )
