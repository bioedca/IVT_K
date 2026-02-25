"""
Callbacks for the Precision Dashboard.

Phase 7.1: Precision Tracking Dashboard (F12.1)

Handles:
- Construct filtering and pagination
- View mode switching (simple/advanced)
- Precision metrics updates
- History chart updates
- Recommendation generation
"""
from typing import Dict, Any, List, Optional
from dash import callback, Input, Output, State, ctx, no_update, ALL
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go

from app.theme import apply_plotly_theme
from app.logging_config import get_logger

logger = get_logger(__name__)

from app.layouts.precision_dashboard import (
    create_precision_table_simple,
    create_precision_table_advanced,
    create_overall_progress,
    create_recommendations_panel,
    create_precision_history_chart,
)


def register_precision_callbacks(app):
    """Register all precision dashboard callbacks."""

    @app.callback(
        Output("precision-construct-filter", "data"),
        Input("precision-project-store", "data"),
        prevent_initial_call=False,  # Allow initial call to load on page load
    )
    def load_constructs(project_id):
        """Load constructs for filtering."""
        if not project_id:
            return []

        try:
            from app.models import Construct

            constructs = Construct.query.filter_by(
                project_id=project_id,
                is_draft=False,
            ).order_by(Construct.identifier).all()

            return [
                {"value": str(c.id), "label": c.identifier}
                for c in constructs
            ]
        except Exception:
            return []

    @app.callback(
        Output("precision-target-input", "value"),
        Input("precision-project-store", "data"),
        prevent_initial_call=False,
    )
    def init_precision_target_from_project(project_id):
        """Initialize precision target input from project settings."""
        if not project_id:
            return no_update

        try:
            from app.models.project import Project
            project = Project.query.get(project_id)
            if not project:
                return no_update
            return project.precision_target or 0.3
        except Exception:
            return no_update

    @app.callback(
        Output("precision-data-store", "data"),
        Input("precision-project-store", "data"),
        Input("precision-refresh-btn", "n_clicks"),
        Input("precision-target-input", "value"),  # React to target changes
        prevent_initial_call=False,  # Allow initial call to load data on page load
    )
    def load_precision_data(project_id, refresh_clicks, target_half_width):
        """Load precision data for all constructs."""
        if not project_id:
            return None

        try:
            from app.models import Construct, Well, Plate, ExperimentalSession
            from app.models.analysis_version import AnalysisVersion, HierarchicalResult, AnalysisStatus
            from app.models.comparison import ComparisonGraph, PrecisionWeight
            from app.models.plate_layout import WellType
            from app.services.comparison_service import ComparisonService

            # Calculate target width from half-width input (±0.3 means full width 0.6)
            target_width = (target_half_width or 0.3) * 2

            # Get latest completed analysis version
            latest_version = AnalysisVersion.query.filter_by(
                project_id=project_id,
                status=AnalysisStatus.COMPLETED,
            ).order_by(AnalysisVersion.created_at.desc()).first()

            if not latest_version:
                return {"constructs": [], "history": [], "scope": "none", "target_width": target_width}

            # Get analysis scope
            scope = ComparisonService.validate_graph_connectivity(project_id)

            # Get all Bayesian results for log_fc_fmax (primary precision metric)
            results = HierarchicalResult.query.filter_by(
                analysis_version_id=latest_version.id,
                parameter_type="log_fc_fmax",
                analysis_type="bayesian",
            ).all()

            # Build construct data
            constructs_data = []
            for result in results:
                construct = Construct.query.get(result.construct_id)
                if not construct:
                    continue

                ci_width = result.ci_width  # Use the property

                # Determine status
                if ci_width <= target_width:
                    status = "met"
                elif ci_width <= target_width * 1.5:
                    status = "close"
                else:
                    status = "not_met"

                # Get comparison path info from ComparisonGraph
                # source_construct_id is the "test" construct being compared
                comparison = ComparisonGraph.query.filter_by(
                    project_id=project_id,
                    source_construct_id=construct.id,
                ).first()

                # Determine path type
                path_type = None
                vif = 1.0

                # Check if comparison graph exists for this project
                has_comparison_data = ComparisonGraph.query.filter_by(
                    project_id=project_id
                ).first() is not None

                if has_comparison_data:
                    # Check if this is the reference construct (target of comparisons, not source)
                    is_reference = ComparisonGraph.query.filter_by(
                        project_id=project_id,
                        target_construct_id=construct.id,
                    ).first() is not None and comparison is None

                    if is_reference:
                        path_type = "reference"
                    elif comparison and comparison.path_type:
                        path_type = comparison.path_type.value

                    # Get VIF from PrecisionWeight if available
                    if comparison:
                        precision_weight = PrecisionWeight.query.filter_by(
                            analysis_version_id=latest_version.id,
                            comparison_graph_id=comparison.id,
                        ).first()
                        if precision_weight:
                            vif = precision_weight.variance_inflation_factor
                else:
                    # No comparison graph - check if this looks like a reference by name
                    if construct.identifier.lower() in ('wt', 'wildtype', 'wild-type', 'reference', 'ref'):
                        path_type = "reference"
                    else:
                        path_type = "direct"  # Assume direct comparison when no graph

                # Count replicates (wells with this construct)
                n_replicates = Well.query.join(Plate).join(ExperimentalSession).filter(
                    ExperimentalSession.project_id == project_id,
                    Well.construct_id == construct.id,
                    Well.well_type == WellType.SAMPLE,
                    Well.is_excluded == False,
                ).count()

                # Calculate effective N (accounting for VIF)
                effective_n = round(n_replicates / vif, 1) if vif > 0 else n_replicates

                constructs_data.append({
                    "construct_id": result.construct_id,
                    "construct_name": construct.identifier,
                    "family": construct.family,
                    "ci_width": round(ci_width, 3),
                    "ci_lower": result.ci_lower,
                    "ci_upper": result.ci_upper,
                    "mean": result.mean,
                    "std": result.std,
                    "target_width": target_width,
                    "status": status,
                    "n_replicates": n_replicates,
                    "effective_n": effective_n,
                    "path_type": path_type,
                    "vif": vif,
                    "r_hat": result.r_hat,
                    "ess_bulk": result.ess_bulk,
                })

            # Load history from previous versions (per-construct for filtering)
            history = []
            # Also build per-construct history for sparklines
            construct_history = {}  # construct_id -> list of ci_widths

            versions = AnalysisVersion.query.filter_by(
                project_id=project_id,
                status=AnalysisStatus.COMPLETED,
            ).order_by(AnalysisVersion.created_at).limit(10).all()

            for version in versions:
                version_results = HierarchicalResult.query.filter_by(
                    analysis_version_id=version.id,
                    parameter_type="log_fc_fmax",
                    analysis_type="bayesian",
                ).all()

                # Add per-construct history records for the chart
                for result in version_results:
                    construct = Construct.query.get(result.construct_id)
                    if construct:
                        history.append({
                            "version_id": version.id,
                            "version_name": version.name,
                            "date": version.created_at.isoformat(),
                            "construct_id": result.construct_id,
                            "construct_name": construct.identifier,
                            "ci_width": result.ci_width,
                        })
                        # Track per-construct history for sparklines
                        if result.construct_id not in construct_history:
                            construct_history[result.construct_id] = []
                        construct_history[result.construct_id].append(result.ci_width)

            # Attach history to each construct for sparkline display
            for c in constructs_data:
                c["history"] = construct_history.get(c["construct_id"], [])

            return {
                "constructs": constructs_data,
                "history": history,
                "scope": scope.scope if scope else "none",
                "version_id": latest_version.id,
                "version_name": latest_version.name,
                "target_width": target_width,  # CI width target (±0.3 = 0.6 total)
            }

        except Exception as e:
            print(f"Error loading precision data: {e}")
            return None

    @app.callback(
        Output("precision-overall-progress", "children"),
        Output("precision-summary-badge", "children"),
        Output("precision-summary-badge", "color"),
        Input("precision-data-store", "data"),
    )
    def update_overall_progress(data):
        """Update overall progress display and summary badge."""
        target_width = 0.6  # Default target CI width (±0.3)

        if not data:
            return create_overall_progress(0, 0, 0.0, target_width / 2), "0/0 at target", "gray"

        constructs = data.get("constructs", [])
        if not constructs:
            return create_overall_progress(0, 0, 0.0, target_width / 2), "0/0 at target", "gray"

        total = len(constructs)
        at_target = sum(1 for c in constructs if c.get("status") == "met")

        # Calculate average CI width (data stores full width, display as half-width)
        ci_widths = [c.get("ci_width", 0) for c in constructs]
        average_ci_full = sum(ci_widths) / len(ci_widths) if ci_widths else 0.0
        average_ci_half = average_ci_full / 2  # Convert to half-width for ± display

        # Get target from data if available (stored as full width, convert to half)
        target_width_full = data.get("target_width", 0.6)
        target_half = target_width_full / 2

        # Badge color based on percentage at target
        pct = (at_target / total * 100) if total > 0 else 0
        badge_color = "green" if pct >= 80 else ("yellow" if pct >= 50 else "red")
        badge_text = f"{at_target}/{total} at target"

        return (
            create_overall_progress(at_target, total, average_ci_half, target_half),
            badge_text,
            badge_color,
        )

    @app.callback(
        Output("precision-target-input", "disabled"),
        Output("precision-target-input", "description"),
        Input("precision-view-mode", "value"),
    )
    def toggle_target_input(view_mode):
        """Enable/disable target input based on view mode."""
        if view_mode == "advanced":
            return False, "95% confidence interval half-width (editable)"
        else:
            return True, "Switch to Advanced mode to edit target"

    @app.callback(
        Output("precision-table-container", "children"),
        Input("precision-data-store", "data"),
        Input("precision-view-mode", "value"),
        Input("precision-construct-filter", "value"),
        Input("precision-show-met-only", "checked"),
        Input("precision-family-filter", "value"),
    )
    def update_precision_table(data, view_mode, construct_filter, show_unmet_only, family_filter):
        """Update precision table based on filters and view mode."""
        if not data:
            import dash_mantine_components as dmc
            return dmc.Text("No precision data available", c="dimmed", ta="center")

        constructs = data.get("constructs", [])
        # Get target half-width (full width / 2) for table display
        target_half_width = data.get("target_width", 0.6) / 2

        # Apply filters
        if construct_filter:
            filter_ids = set(str(c) for c in construct_filter) if isinstance(construct_filter, list) else {str(construct_filter)}
            constructs = [c for c in constructs if str(c.get("construct_id")) in filter_ids]

        if show_unmet_only:
            # Show only constructs not meeting target (not_met or close)
            constructs = [c for c in constructs if c.get("status") in ("not_met", "close")]

        if family_filter:
            constructs = [c for c in constructs if c.get("family") == family_filter]

        # Sort by CI width (widest first for prioritization)
        constructs = sorted(constructs, key=lambda x: x.get("ci_width", 0), reverse=True)

        if view_mode == "advanced":
            return create_precision_table_advanced(constructs, target_half_width)
        else:
            return create_precision_table_simple(constructs, target_half_width)

    @app.callback(
        Output("precision-history-chart", "figure"),
        Input("precision-data-store", "data"),
        Input("precision-construct-filter", "value"),
        Input("color-scheme-store", "data"),
    )
    def update_history_chart(data, construct_filter, scheme):
        """Update precision history chart with optional construct filtering."""
        dark_mode = (scheme == "dark")
        if not data:
            fig = go.Figure()
            apply_plotly_theme(fig, dark_mode=dark_mode)
            return fig

        history = data.get("history", [])
        if not history:
            fig = go.Figure()
            apply_plotly_theme(fig, dark_mode=dark_mode)
            return fig

        # Filter history by selected constructs if filter is active
        if construct_filter:
            # Convert filter values to set for O(1) lookup
            filter_ids = set(str(c) for c in construct_filter)
            history = [
                h for h in history
                if str(h.get("construct_id")) in filter_ids
            ]
            # If filter results in no data, return empty figure with message
            if not history:
                fig = go.Figure()
                fig.add_annotation(
                    text="No history for selected constructs",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5,
                    showarrow=False,
                    font=dict(color="gray"),
                )
                fig.update_layout(margin=dict(l=40, r=20, t=30, b=30))
                apply_plotly_theme(fig, dark_mode=dark_mode)
                return fig

        # Get target from data, default to 0.6 (±0.3 CI width)
        target = data.get("target_width", 0.6)

        fig = create_precision_history_chart(history, target)
        apply_plotly_theme(fig, dark_mode=dark_mode)
        return fig

    @app.callback(
        Output("precision-recommendations", "children"),
        Input("precision-data-store", "data"),
    )
    def update_recommendations(data):
        """
        Generate smart recommendations for improving precision.

        Uses variance-based calculations to estimate additional replicates needed:
        - CI width ≈ 2 * 1.96 * σ / √(n_effective)
        - n_effective = n_replicates / VIF
        - To achieve target CI: n_needed = n_current * (CI_current / CI_target)²
        """
        if not data:
            import dash_mantine_components as dmc
            return dmc.Text("No recommendations available", c="dimmed", ta="center")

        constructs = data.get("constructs", [])
        target_width = data.get("target_width", 0.6)  # Full CI width
        target_half = target_width / 2  # Half-width for display

        # Find constructs not meeting target (exclude user-accepted overrides)
        needs_improvement = [
            c for c in constructs
            if c.get("status") in ("not_met", "close")
            and not c.get("has_override")
        ]

        if not needs_improvement:
            return create_recommendations_panel([])

        # Sort by gap from target (largest gap first = highest priority)
        needs_improvement = sorted(
            needs_improvement,
            key=lambda x: x.get("ci_width", 0) - target_width,
            reverse=True
        )

        recommendations = []
        for construct in needs_improvement[:5]:
            ci_width = construct.get("ci_width", 0)  # Full width
            ci_half = ci_width / 2  # Half-width for display
            current_n = construct.get("n_replicates") or 3
            vif = construct.get("vif", 1.0)
            std = construct.get("std", 0)

            # Calculate effective sample size accounting for VIF
            # VIF inflates variance, so effective n = n / VIF
            n_effective = current_n / vif if vif > 0 else current_n

            # Estimate additional replicates needed
            # CI width scales as 1/√n, so: CI_new = CI_current * √(n_current/n_new)
            # Solving for n_new: n_new = n_current * (CI_current / CI_target)²
            if ci_width > target_width and ci_width > 0:
                # Account for VIF in the calculation
                ratio = ci_width / target_width
                n_needed_effective = n_effective * (ratio ** 2)
                # Convert back to actual replicates needed (accounting for VIF)
                n_needed_actual = n_needed_effective * vif
                additional_n = max(0, int(n_needed_actual - current_n + 0.5))

                # Calculate expected CI after adding replicates
                if additional_n > 0:
                    new_n = current_n + additional_n
                    new_n_effective = new_n / vif
                    # CI scales as 1/√n
                    expected_ci_width = ci_width * (n_effective / new_n_effective) ** 0.5
                    expected_ci_half = expected_ci_width / 2
                else:
                    expected_ci_half = ci_half
            else:
                additional_n = 0
                expected_ci_half = ci_half

            # Determine priority based on gap
            gap = ci_width - target_width
            if gap > target_width * 0.5:  # More than 50% over target
                priority = "high"
            elif gap > 0:
                priority = "medium"
            else:
                priority = "low"

            # VIF-based recommendations
            vif_note = ""
            if vif >= 2.0:
                vif_note = f"High VIF ({vif:.1f}×) - consider direct comparison path"
            elif vif > 1.0:
                vif_note = f"VIF={vif:.1f}× increases replicates needed"

            recommendations.append({
                "construct_name": construct.get("construct_name"),
                "construct_id": construct.get("construct_id"),
                "current_ci": ci_half,  # Half-width for ± display
                "target_ci": target_half,
                "expected_ci": expected_ci_half,
                "current_n": current_n,
                "additional_n": additional_n,
                "priority": priority,
                "vif": vif,
                "vif_note": vif_note,
                "path_type": construct.get("path_type"),
            })

        return create_recommendations_panel(recommendations)

    @app.callback(
        Output("precision-family-filter", "data"),
        Input("precision-data-store", "data"),
    )
    def populate_family_filter(data):
        """Populate family filter options from data."""
        if not data:
            return []

        constructs = data.get("constructs", [])
        families = set()

        for c in constructs:
            family = c.get("family")
            if family:
                families.add(family)

        return [
            {"value": f, "label": f}
            for f in sorted(families)
        ]

    @app.callback(
        Output("precision-construct-filter", "data", allow_duplicate=True),
        Input("precision-data-store", "data"),
        prevent_initial_call=True,
    )
    def populate_construct_filter(data):
        """Populate construct filter options from data."""
        if not data:
            return []

        constructs = data.get("constructs", [])
        return [
            {"value": str(c.get("construct_id")), "label": c.get("construct_name", "Unknown")}
            for c in constructs
            if c.get("construct_id")
        ]

    @app.callback(
        Output("precision-export-download", "data"),
        Input("precision-export-btn", "n_clicks"),
        State("precision-data-store", "data"),
        prevent_initial_call=True,
    )
    def export_precision_data(n_clicks, data):
        """Export precision data to CSV."""
        if not n_clicks or not data:
            raise PreventUpdate

        try:
            import pandas as pd
            from dash import dcc
            import io

            constructs = data.get("constructs", [])
            if not constructs:
                raise PreventUpdate

            df = pd.DataFrame(constructs)

            # Select and rename columns for export
            columns = {
                "construct_name": "Construct",
                "family": "Family",
                "mean": "Mean (log2 FC)",
                "ci_lower": "CI Lower",
                "ci_upper": "CI Upper",
                "ci_width": "CI Width",
                "target_width": "Target Width",
                "status": "Status",
                "n_replicates": "N Replicates",
                "path_type": "Comparison Path",
                "vif": "VIF",
                "r_hat": "R-hat",
                "ess_bulk": "ESS Bulk",
            }

            export_df = df[[c for c in columns.keys() if c in df.columns]]
            export_df = export_df.rename(columns={k: v for k, v in columns.items() if k in export_df.columns})

            # Convert to CSV
            csv_buffer = io.StringIO()
            export_df.to_csv(csv_buffer, index=False)

            return {
                "content": csv_buffer.getvalue(),
                "filename": f"precision_data_{data.get('version_name', 'export')}.csv",
                "type": "text/csv",
            }

        except Exception as e:
            print(f"Error exporting precision data: {e}")
            raise PreventUpdate

    @app.callback(
        Output("precision-detail-modal", "opened"),
        Output("precision-detail-content", "children"),
        Input({"type": "precision-detail-btn", "index": ALL}, "n_clicks"),
        Input("precision-detail-close", "n_clicks"),
        State("precision-data-store", "data"),
        State("precision-detail-modal", "opened"),
        prevent_initial_call=True,
    )
    def show_construct_detail(detail_clicks, close_click, data, is_open):
        """Show detailed precision info for a construct."""
        import dash_mantine_components as dmc
        from dash import ALL

        triggered = ctx.triggered_id

        if triggered == "precision-detail-close":
            return False, no_update

        if isinstance(triggered, dict) and triggered.get("type") == "precision-detail-btn":
            construct_id = triggered.get("index")

            if data and construct_id:
                constructs = data.get("constructs", [])
                construct = next(
                    (c for c in constructs if str(c.get("construct_id")) == str(construct_id)),
                    None
                )

                if construct:
                    content = dmc.Stack([
                        dmc.Title(construct.get("construct_name", "Unknown"), order=4),
                        dmc.Divider(),
                        dmc.SimpleGrid(cols=2, children=[
                            dmc.Stack([
                                dmc.Text("Posterior Mean", fw=500),
                                dmc.Text(f"{construct.get('mean', 0):.3f}"),
                            ], gap="xs"),
                            dmc.Stack([
                                dmc.Text("Posterior Std", fw=500),
                                dmc.Text(f"{construct.get('std', 0):.3f}"),
                            ], gap="xs"),
                            dmc.Stack([
                                dmc.Text("95% CI", fw=500),
                                dmc.Text(f"[{construct.get('ci_lower', 0):.3f}, {construct.get('ci_upper', 0):.3f}]"),
                            ], gap="xs"),
                            dmc.Stack([
                                dmc.Text("CI Width", fw=500),
                                dmc.Text(f"{construct.get('ci_width', 0):.3f}"),
                            ], gap="xs"),
                        ]),
                        dmc.Divider(),
                        dmc.Text("Diagnostics", fw=600),
                        dmc.SimpleGrid(cols=3, children=[
                            dmc.Stack([
                                dmc.Text("R-hat", fw=500),
                                dmc.Text(f"{construct.get('r_hat', 0):.3f}"),
                            ], gap="xs"),
                            dmc.Stack([
                                dmc.Text("ESS Bulk", fw=500),
                                dmc.Text(f"{construct.get('ess_bulk', 0):.0f}"),
                            ], gap="xs"),
                            dmc.Stack([
                                dmc.Text("VIF", fw=500),
                                dmc.Text(f"{construct.get('vif', 1.0):.2f}"),
                            ], gap="xs"),
                        ]),
                        dmc.Divider(),
                        dmc.Text("Comparison Path", fw=600),
                        dmc.Text(construct.get("path_type", "Unknown"), c="dimmed"),
                    ], gap="md")

                    return True, content

        raise PreventUpdate

    # =========================================================================
    # Sprint 4: Precision Override Workflow (F12.6, Task 7.1)
    # =========================================================================

    @app.callback(
        Output("precision-override-modal", "opened"),
        Output("precision-override-construct-name", "children"),
        Output("precision-override-construct-store", "data"),
        Output("precision-override-target", "value"),
        Input({"type": "precision-override-btn", "index": ALL}, "n_clicks"),
        Input("precision-override-cancel", "n_clicks"),
        Input("precision-override-save", "n_clicks"),
        State("precision-data-store", "data"),
        State("precision-override-modal", "opened"),
        prevent_initial_call=True,
    )
    def toggle_override_modal(override_clicks, cancel_click, save_click, data, is_open):
        """Toggle the precision override modal and populate data."""
        import dash_mantine_components as dmc

        triggered = ctx.triggered_id

        # Close modal
        if triggered in ["precision-override-cancel", "precision-override-save"]:
            return False, "", None, 0.3

        # Open modal for specific construct
        if isinstance(triggered, dict) and triggered.get("type") == "precision-override-btn":
            construct_id = triggered.get("index")

            if data and construct_id:
                constructs = data.get("constructs", [])
                construct = next(
                    (c for c in constructs if str(c.get("construct_id")) == str(construct_id)),
                    None
                )

                if construct:
                    name = construct.get("construct_name", "Unknown")
                    target = construct.get("target_width", 0.6) / 2  # Convert full width to half-width

                    return True, name, construct_id, target

        raise PreventUpdate

    @app.callback(
        Output("precision-override-result", "children"),
        Output("precision-data-store", "data", allow_duplicate=True),
        Input("precision-override-save", "n_clicks"),
        State("precision-override-construct-store", "data"),
        State("precision-override-target", "value"),
        State("precision-override-justification", "value"),
        State("precision-data-store", "data"),
        State("precision-project-store", "data"),
        prevent_initial_call=True,
    )
    def save_precision_override(n_clicks, construct_id, new_target, justification, current_data, project_id):
        """Save precision override with justification validation."""
        import dash_mantine_components as dmc
        from dash_iconify import DashIconify

        if not n_clicks or not construct_id:
            raise PreventUpdate

        # Validate justification (min 20 characters)
        if not justification or len(justification.strip()) < 20:
            return dmc.Alert(
                title="Invalid Justification",
                children="Justification must be at least 20 characters to document why this precision target is acceptable.",
                color="red",
                icon=DashIconify(icon="mdi:alert-circle"),
            ), no_update

        try:
            from app.models.comparison import PrecisionOverride
            from app.models import Construct
            from app.models.analysis_version import AnalysisVersion, AnalysisStatus
            from app.extensions import db
            from app.services.audit_service import AuditService
            from datetime import datetime, timezone

            # Get construct and latest analysis version
            construct = Construct.query.get(int(construct_id))
            if not construct:
                return dmc.Alert(
                    title="Error",
                    children="Construct not found.",
                    color="red",
                ), no_update

            latest_version = AnalysisVersion.query.filter_by(
                project_id=project_id,
                status=AnalysisStatus.COMPLETED,
            ).order_by(AnalysisVersion.created_at.desc()).first()

            if not latest_version:
                return dmc.Alert(
                    title="Error",
                    children="No completed analysis version found.",
                    color="red",
                ), no_update

            # Find actual CI width from current data
            construct_data = next(
                (c for c in current_data.get("constructs", [])
                 if str(c.get("construct_id")) == str(construct_id)),
                None
            )

            ci_width_actual = construct_data.get("ci_width", 0) if construct_data else 0
            ci_width_target = new_target * 2  # Convert half-width to full width

            # Check for existing override
            existing = PrecisionOverride.query.filter_by(
                construct_id=construct.id,
                analysis_version_id=latest_version.id,
            ).first()

            if existing:
                # Update existing override
                existing.ci_width_actual = ci_width_actual
                existing.ci_width_target = ci_width_target
                existing.justification = justification.strip()
                existing.override_by = "current_user"  # Would be replaced with actual user
                existing.override_at = datetime.now(timezone.utc)
            else:
                # Create new override
                override = PrecisionOverride(
                    construct_id=construct.id,
                    analysis_version_id=latest_version.id,
                    ci_width_actual=ci_width_actual,
                    ci_width_target=ci_width_target,
                    is_acceptable=True,
                    justification=justification.strip(),
                    override_by="current_user",  # Would be replaced with actual user
                    override_at=datetime.now(timezone.utc),
                )
                db.session.add(override)

            db.session.commit()

            # Log to audit trail
            try:
                AuditService.log_action(
                    action='precision_override',
                    entity_type='construct',
                    entity_id=construct.id,
                    details={
                        'justification': justification.strip(),
                        'ci_width_actual': ci_width_actual,
                        'ci_width_target': ci_width_target,
                        'analysis_version_id': latest_version.id,
                    }
                )
            except Exception:
                pass  # Audit logging is best-effort

            # Update the local data to reflect the override
            if current_data:
                for c in current_data.get("constructs", []):
                    if str(c.get("construct_id")) == str(construct_id):
                        c["has_override"] = True
                        c["override_justification"] = justification.strip()
                        c["status"] = "user_accepted"
                        break

            return dmc.Alert(
                title="Override Saved",
                children=f"Precision target override saved for {construct.identifier}. This is logged in the audit trail.",
                color="green",
                icon=DashIconify(icon="mdi:check-circle"),
            ), current_data

        except Exception as e:
            logger.exception("Error saving precision override")
            return dmc.Alert(
                title="Error",
                children="An unexpected error occurred while saving the override. Please try again.",
                color="red",
            ), no_update

    @app.callback(
        Output("precision-override-justification", "error"),
        Input("precision-override-justification", "value"),
    )
    def validate_justification_length(justification):
        """Validate justification meets minimum length requirement."""
        if justification and len(justification.strip()) < 20:
            chars_needed = 20 - len(justification.strip())
            return f"Need {chars_needed} more characters (minimum 20)"
        return None
