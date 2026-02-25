"""
Page routing callbacks.

Handles URL-based navigation by updating page-content based on pathname.
"""
from dash import callback, Input, Output, State, no_update, ctx, ALL
from dash.exceptions import PreventUpdate


def register_routing_callbacks(app):
    """Register page routing callbacks."""

    # Sidebar + breadcrumb population based on current URL
    @app.callback(
        Output("sidebar-nav-content", "children"),
        Output("app-sidebar", "style"),
        Output("breadcrumb-container", "children"),
        Input("url", "pathname"),
        prevent_initial_call=False,
    )
    def update_navigation(pathname):
        """Update sidebar and breadcrumbs based on current page."""
        from app.components.navigation import create_sidebar, create_breadcrumbs, PAGE_LABELS
        from dash import html

        # Default: hide sidebar, no breadcrumbs
        hidden_style = {"display": "none"}
        empty_breadcrumbs = html.Div()

        if not pathname or pathname in ("/", "/projects"):
            return html.Div(), hidden_style, empty_breadcrumbs

        # Non-project pages: hide sidebar, show simple breadcrumbs
        if pathname.startswith("/help/"):
            crumbs = create_breadcrumbs([
                {"label": "Projects", "href": "/projects"},
                "Help",
            ])
            return html.Div(), hidden_style, crumbs

        if pathname.startswith("/tools/"):
            crumbs = create_breadcrumbs([
                {"label": "Projects", "href": "/projects"},
                "Tools",
            ])
            return html.Div(), hidden_style, crumbs

        if pathname.startswith("/admin/"):
            crumbs = create_breadcrumbs([
                {"label": "Projects", "href": "/projects"},
                "Admin",
            ])
            return html.Div(), hidden_style, crumbs

        if pathname == "/cross-project":
            crumbs = create_breadcrumbs([
                {"label": "Projects", "href": "/projects"},
                "Cross-Project Comparison",
            ])
            return html.Div(), hidden_style, crumbs

        # Project pages: show sidebar
        if pathname.startswith("/project/"):
            parts = pathname.strip("/").split("/")
            if len(parts) >= 2:
                try:
                    project_id = int(parts[1])
                except ValueError:
                    return html.Div(), hidden_style, empty_breadcrumbs

                # Determine current subpage
                subpage = parts[2] if len(parts) >= 3 else "hub"

                # Get project name for sidebar header
                project_name = None
                try:
                    from app.services import ProjectService
                    project = ProjectService.get_project(project_id)
                    if project:
                        project_name = project.name
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).debug(
                        "Failed to fetch project name for sidebar: %s", e
                    )

                # Build sidebar
                sidebar_content = create_sidebar(
                    current_page=subpage,
                    project_id=project_id,
                    project_name=project_name,
                )
                visible_style = {}  # Default display (visible)

                # Build breadcrumbs
                crumb_items = [
                    {"label": "Projects", "href": "/projects"},
                    {"label": project_name or f"Project {project_id}", "href": f"/project/{project_id}"},
                ]
                if subpage != "hub":
                    page_label = PAGE_LABELS.get(subpage, subpage.title())
                    crumb_items.append(page_label)
                breadcrumbs = create_breadcrumbs(crumb_items)

                return sidebar_content, visible_style, breadcrumbs

        return html.Div(), hidden_style, empty_breadcrumbs

    @app.callback(
        Output("page-content", "children"),
        Input("url", "pathname"),
        prevent_initial_call=False
    )
    def route_page(pathname):
        """Route to appropriate page based on URL pathname."""
        from app.layouts.project_list import create_project_list_layout
        from app.layouts.hub import create_hub_layout
        from app.layouts.project_settings import create_project_settings_layout
        from app.layouts.calculator import create_calculator_layout
        from app.layouts.curve_browser import create_curve_browser_layout
        from app.layouts.analysis_results import create_analysis_results_layout
        from app.layouts.precision_dashboard import create_precision_dashboard_layout
        from app.layouts.cross_project_comparison import create_cross_project_comparison_layout
        from app.layouts.audit_log import create_audit_log_layout
        from app.layouts.publication_export import create_publication_export_layout
        from app.layouts.construct_registry import create_construct_registry_layout
        from app.layouts.plate_templates import create_plate_templates_layout
        from app.layouts.data_upload import create_upload_layout
        from app.layouts.negative_control_dashboard import create_negative_control_dashboard
        import dash_mantine_components as dmc
        from dash import dcc

        # Default/home page
        if pathname is None or pathname == "/":
            return create_project_list_layout()

        # Project list
        if pathname == "/projects":
            return create_project_list_layout()

        # Cross-project comparison
        if pathname == "/cross-project":
            return create_cross_project_comparison_layout()

        # Standalone tools
        if pathname == "/tools/digestion":
            from app.layouts.digestion_calculator import create_digestion_calculator_layout
            return create_digestion_calculator_layout()

        # Admin pages
        if pathname == "/admin/access-log":
            from app.layouts.access_log import create_access_log_layout
            return create_access_log_layout()

        # Help pages
        if pathname == "/help/getting-started":
            from app.layouts.help_pages import create_getting_started_layout
            return create_getting_started_layout()

        if pathname == "/help/workflow":
            from app.layouts.help_pages import create_workflow_overview_layout
            return create_workflow_overview_layout()

        # Project-specific routes
        if pathname.startswith("/project/"):
            parts = pathname.split("/")
            if len(parts) >= 3:
                try:
                    project_id = int(parts[2])
                except ValueError:
                    return _not_found_page(pathname)

                # /project/{id} - Hub/Dashboard
                if len(parts) == 3:
                    return create_hub_layout(project_id)

                # /project/{id}/{subpage}
                if len(parts) >= 4:
                    subpage = parts[3]

                    if subpage == "settings":
                        return create_project_settings_layout(project_id)
                    elif subpage == "constructs":
                        return create_construct_registry_layout(project_id)
                    elif subpage == "layouts":
                        # Get plate format for initial control state
                        from app.models import Project
                        project = Project.query.get(project_id)
                        plate_format = int(project.plate_format.value) if project else 384
                        return create_plate_templates_layout(project_id, plate_format=plate_format)
                    elif subpage == "upload":
                        return create_upload_layout(project_id)
                    elif subpage == "calculator":
                        return create_calculator_layout(project_id)
                    elif subpage == "curves":
                        return create_curve_browser_layout(project_id)
                    elif subpage == "analysis":
                        return create_analysis_results_layout(project_id)
                    elif subpage == "qc":
                        return create_negative_control_dashboard(project_id)
                    elif subpage == "precision":
                        return create_precision_dashboard_layout(project_id)
                    elif subpage == "export":
                        return create_publication_export_layout(project_id)
                    elif subpage == "audit":
                        return create_audit_log_layout(project_id)
                    else:
                        return _not_found_page(pathname)

        return _not_found_page(pathname)

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("view-projects-btn", "n_clicks"),
        prevent_initial_call=True
    )
    def navigate_to_projects(n_clicks):
        """Navigate to projects page when View Projects button is clicked."""
        if n_clicks:
            return "/projects"
        raise PreventUpdate
    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input({"type": "open-project-btn", "index": ALL}, "n_clicks"),
        prevent_initial_call=True
    )
    def open_project(n_clicks):
        """Navigate to project dashboard when Open button is clicked."""
        if not any(n_clicks):
            raise PreventUpdate
            
        triggered = ctx.triggered_id
        if not triggered or not triggered.get("index"):
            raise PreventUpdate
            
        project_id = triggered["index"]
        return f"/project/{project_id}"

    # Global Back Button - navigates based on current location
    # At project step (upload, qc, analysis, etc.) → go to project hub
    # At project hub → go to project list
    # At project list or home → stay
    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("global-back-btn", "n_clicks"),
        State("url", "pathname"),
        prevent_initial_call=True
    )
    def handle_global_back(n_clicks, pathname):
        """Navigate back based on current page location."""
        if not n_clicks:
            raise PreventUpdate

        if not pathname:
            return "/projects"

        # Parse the current path
        parts = pathname.strip("/").split("/")

        # At project list or home
        if pathname in ["/", "/projects", "/cross-project"]:
            raise PreventUpdate  # Stay on current page

        # At a help, tools, or admin page
        if pathname.startswith("/help/") or pathname.startswith("/tools/") or pathname.startswith("/admin/"):
            return "/projects"

        # At a project page
        if len(parts) >= 2 and parts[0] == "project":
            try:
                project_id = int(parts[1])

                if len(parts) == 2:
                    # At project hub (/project/123) → go to project list
                    return "/projects"
                else:
                    # At a project step (/project/123/upload) → go to project hub
                    return f"/project/{project_id}"

            except (ValueError, IndexError):
                return "/projects"

        # Default: go to project list
        return "/projects"

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("help-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def navigate_to_help(n_clicks):
        if n_clicks:
            return "/help/getting-started"
        return no_update



def _not_found_page(pathname):
    """Return a 404-style not found page."""
    import dash_mantine_components as dmc
    from dash import html, dcc

    return dmc.Container(
        children=[
            dmc.Stack(
                children=[
                    dmc.Title("Page Not Found", order=2),
                    dmc.Text(f"The page '{pathname}' does not exist.", c="dimmed"),
                    dcc.Link(
                        dmc.Button(
                            "Go to Projects",
                            id="go-home-btn",
                            variant="light"
                        ),
                        href="/projects"
                    )
                ],
                align="center",
                style={"paddingTop": "3rem"}
            )
        ],
        size="sm"
    )
