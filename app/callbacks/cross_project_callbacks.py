"""
Callbacks for the Cross-Project Comparison dashboard.

Sprint 8: Cross-Project Features (PRD Section 3.20)

Handles:
- Construct selection across projects
- Project selection for comparison
- Forest plot generation
- Posterior overlay generation
- Summary table updates
- CSV export
"""
from typing import Dict, Any, List, Optional
from dash import callback, Input, Output, State, ctx, no_update, ALL
from dash.exceptions import PreventUpdate
import dash_mantine_components as dmc
from dash import html
import json

from app.theme import apply_plotly_theme
from app.logging_config import get_logger

logger = get_logger(__name__)

from app.layouts.cross_project_comparison import (
    create_project_checkbox_item,
    create_summary_table,
)
from app.components.forest_plot import create_cross_project_forest_plot


def register_cross_project_callbacks(app):
    """Register all cross-project comparison callbacks."""

    @app.callback(
        Output("cross-project-construct-select", "data"),
        Input("url", "pathname"),
        prevent_initial_call=False,
    )
    def load_shared_constructs(pathname):
        """Load construct identifiers that appear in multiple projects."""
        if pathname != "/cross-project":
            raise PreventUpdate

        try:
            from app.services.cross_project_service import CrossProjectComparisonService

            shared = CrossProjectComparisonService.get_shared_construct_identifiers(
                min_projects=2
            )

            return [
                {
                    "value": item["identifier"],
                    "label": f"{item['identifier']} ({item['project_count']} projects)"
                }
                for item in shared
            ]
        except Exception as e:
            logger.exception("Error loading shared constructs")
            return []

    @app.callback(
        Output("cross-project-project-list", "children"),
        Output("cross-project-selected-projects", "data"),
        Input("cross-project-construct-select", "value"),
        prevent_initial_call=True,
    )
    def load_projects_for_construct(construct_identifier):
        """Load projects containing the selected construct."""
        if not construct_identifier:
            return (
                dmc.Text(
                    "Select a construct to see available projects",
                    c="dimmed",
                    size="sm",
                    fs="italic"
                ),
                []
            )

        try:
            from app.services.cross_project_service import CrossProjectComparisonService

            matches = CrossProjectComparisonService.find_matching_constructs(
                identifier=construct_identifier
            )

            if not matches:
                return (
                    dmc.Text(
                        "No projects found with this construct",
                        c="dimmed",
                        size="sm"
                    ),
                    []
                )

            # Create checkbox list
            checkboxes = []
            selected_ids = []

            for match in matches:
                checkbox = create_project_checkbox_item(
                    project_id=match.project_id,
                    project_name=match.project_name,
                    plate_count=match.plate_count,
                    replicate_count=match.replicate_count,
                    has_analysis=match.has_analysis,
                    analysis_date=match.latest_analysis_date.isoformat() if match.latest_analysis_date else None,
                    checked=match.has_analysis
                )
                checkboxes.append(checkbox)

                if match.has_analysis:
                    selected_ids.append(match.project_id)

            return (
                dmc.Stack(children=checkboxes, gap="xs"),
                selected_ids
            )

        except Exception as e:
            logger.exception("Error loading projects for construct")
            return (
                dmc.Alert(
                    "An unexpected error occurred while loading projects.",
                    color="red",
                    variant="light"
                ),
                []
            )

    @app.callback(
        Output("cross-project-selected-projects", "data", allow_duplicate=True),
        Input({"type": "cross-project-checkbox", "index": ALL}, "checked"),
        State({"type": "cross-project-checkbox", "index": ALL}, "id"),
        prevent_initial_call=True,
    )
    def update_selected_projects(checked_values, checkbox_ids):
        """Update selected projects when checkboxes change."""
        if not checkbox_ids:
            raise PreventUpdate

        selected = [
            cb_id["index"]
            for cb_id, is_checked in zip(checkbox_ids, checked_values)
            if is_checked
        ]

        return selected

    @app.callback(
        Output("cross-project-comparison-data", "data"),
        Input("cross-project-selected-projects", "data"),
        Input("cross-project-parameter-select", "value"),
        Input("cross-project-analysis-type", "value"),
        State("cross-project-construct-select", "value"),
        prevent_initial_call=True,
    )
    def load_comparison_data(project_ids, parameter_type, analysis_type, construct_identifier):
        """Load comparison data for selected projects."""
        if not project_ids or not construct_identifier:
            return None

        try:
            from app.services.cross_project_service import CrossProjectComparisonService

            comparison = CrossProjectComparisonService.get_comparison_data(
                construct_identifier=construct_identifier,
                project_ids=project_ids,
                parameter_type=parameter_type,
                analysis_type=analysis_type
            )

            # Convert to dict for JSON serialization
            return {
                "construct_identifier": comparison.construct_identifier,
                "parameter_type": comparison.parameter_type,
                "projects": comparison.projects
            }

        except Exception as e:
            logger.exception("Error loading comparison data")
            return None

    @app.callback(
        Output("cross-project-forest-plot", "figure"),
        Input("cross-project-comparison-data", "data"),
        Input("color-scheme-store", "data"),
        prevent_initial_call=True,
    )
    def update_forest_plot(comparison_data, scheme):
        """Update the forest plot with comparison data."""
        import plotly.graph_objects as go

        dark_mode = (scheme == "dark")

        if not comparison_data or not comparison_data.get("projects"):
            fig = go.Figure()
            fig.add_annotation(
                text="Select a construct and projects to compare",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14, color="gray")
            )
            fig.update_layout(
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                height=400
            )
            apply_plotly_theme(fig, dark_mode=dark_mode)
            return fig

        fig = create_cross_project_forest_plot(
            projects=comparison_data["projects"],
            construct_identifier=comparison_data["construct_identifier"],
            parameter_type=comparison_data["parameter_type"],
            show_summary=True,
            dark_mode=dark_mode,
        )
        return fig

    @app.callback(
        Output("cross-project-posterior-plot", "figure"),
        Input("cross-project-comparison-data", "data"),
        Input("color-scheme-store", "data"),
        prevent_initial_call=True,
    )
    def update_posterior_plot(comparison_data, scheme):
        """Update the posterior overlay plot."""
        import plotly.graph_objects as go

        dark_mode = (scheme == "dark")

        if not comparison_data or not comparison_data.get("projects"):
            fig = go.Figure()
            fig.add_annotation(
                text="Select a construct and projects to compare",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14, color="gray")
            )
            fig.update_layout(
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                height=300
            )
            apply_plotly_theme(fig, dark_mode=dark_mode)
            return fig

        try:
            from app.services.cross_project_service import (
                CrossProjectComparisonService,
                ConstructComparisonData
            )

            # Reconstruct comparison data object
            comparison = ConstructComparisonData(
                construct_identifier=comparison_data["construct_identifier"],
                parameter_type=comparison_data["parameter_type"],
                projects=comparison_data["projects"]
            )

            fig = CrossProjectComparisonService.generate_posterior_overlay_plot(
                comparison_data=comparison
            )
            apply_plotly_theme(fig, dark_mode=dark_mode)
            return fig

        except Exception as e:
            logger.exception("Error generating posterior plot")
            fig = go.Figure()
            fig.add_annotation(
                text="Error generating plot. Please try again.",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False
            )
            apply_plotly_theme(fig, dark_mode=dark_mode)
            return fig

    @app.callback(
        Output("cross-project-summary-table", "children"),
        Input("cross-project-comparison-data", "data"),
        State("cross-project-analysis-type", "value"),
        prevent_initial_call=True,
    )
    def update_summary_table(comparison_data, analysis_type):
        """Update the summary table with comparison data."""
        if not comparison_data or not comparison_data.get("projects"):
            return dmc.Text(
                "Select a construct and projects to see comparison data",
                c="dimmed",
                ta="center",
                py="xl"
            )

        return create_summary_table(
            projects=comparison_data["projects"],
            show_bayesian=(analysis_type == "bayesian")
        )

    @app.callback(
        Output("cross-project-download-csv", "data"),
        Input("cross-project-export-btn", "n_clicks"),
        State("cross-project-comparison-data", "data"),
        prevent_initial_call=True,
    )
    def export_comparison_csv(n_clicks, comparison_data):
        """Export comparison data as CSV."""
        if not n_clicks or not comparison_data or not comparison_data.get("projects"):
            raise PreventUpdate

        try:
            from app.services.cross_project_service import (
                CrossProjectComparisonService,
                ConstructComparisonData
            )
            import io

            # Reconstruct comparison data object
            comparison = ConstructComparisonData(
                construct_identifier=comparison_data["construct_identifier"],
                parameter_type=comparison_data["parameter_type"],
                projects=comparison_data["projects"]
            )

            df = CrossProjectComparisonService.export_comparison_table(
                comparison_data=comparison,
                include_diagnostics=True
            )

            # Convert to CSV
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)

            filename = f"cross_project_{comparison_data['construct_identifier']}_{comparison_data['parameter_type']}.csv"

            return {
                "content": csv_buffer.getvalue(),
                "filename": filename,
                "type": "text/csv"
            }

        except Exception as e:
            logger.exception("Error exporting CSV")
            raise PreventUpdate
