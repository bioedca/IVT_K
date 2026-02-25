"""
Callbacks for the Curve Browser.

Phase 4.12: Curve Browser visualization (F8.8, F8.9, F13.2)

Handles:
- Well grid filtering and selection
- Curve display with fit overlay
- Multi-panel comparison views
- Navigation and comparison set management
"""
from typing import Dict, Any, List, Optional, Tuple
from dash import callback, Input, Output, State, ctx, no_update, ALL, MATCH
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go

from app.layouts.curve_browser import (
    create_well_grid_item,
    create_well_details_panel,
    create_fit_params_panel,
    create_empty_plot_message,
)
from app.components.curve_plot import (
    create_curve_plot,
    create_multi_panel_curve_plot,
    create_overlay_plot,
    create_panel_plot,
    compute_fit_curve,
)
from app.theme import apply_plotly_theme


def create_empty_figure(dark_mode=False) -> go.Figure:
    """Create an empty figure with appropriate theme."""
    fig = go.Figure()
    apply_plotly_theme(fig, dark_mode=dark_mode)
    return fig


def register_curve_browser_callbacks(app):
    """Register all curve browser callbacks."""

    @app.callback(
        Output("curve-browser-session-filter", "data"),
        Input("curve-browser-project-store", "data"),
        prevent_initial_call=False,
    )
    def load_sessions(project_id):
        """Load available sessions for the project."""
        if not project_id:
            return []

        try:
            from app.models import ExperimentalSession

            sessions = ExperimentalSession.query.filter_by(
                project_id=project_id
            ).order_by(ExperimentalSession.date.desc()).all()

            return [
                {
                    "value": str(s.id),
                    "label": f"{s.date.strftime('%b %d, %Y')} - {s.batch_identifier or 'Session'}"
                }
                for s in sessions
            ]
        except Exception:
            return []

    @app.callback(
        Output("curve-browser-plate-filter", "data"),
        Input("curve-browser-session-filter", "value"),
        prevent_initial_call=False,
    )
    def load_plates(session_id):
        """Load plates for the selected session."""
        if not session_id:
            return []

        try:
            from app.models import Plate

            plates = Plate.query.filter_by(
                session_id=int(session_id)
            ).order_by(Plate.plate_number).all()

            return [
                {"value": str(p.id), "label": f"Plate {p.plate_number}"}
                for p in plates
            ]
        except Exception:
            return []

    @app.callback(
        Output("curve-browser-construct-filter", "data"),
        Input("curve-browser-project-store", "data"),
        prevent_initial_call=False,
    )
    def load_constructs(project_id):
        """Load constructs for the project."""
        if not project_id:
            return []

        try:
            from app.models import Construct

            constructs = Construct.query.filter_by(
                project_id=project_id
            ).order_by(Construct.identifier).all()

            return [
                {"value": str(c.id), "label": c.identifier}
                for c in constructs
            ]
        except Exception:
            return []

    @app.callback(
        Output("curve-browser-well-grid", "children"),
        Output("curve-browser-well-count", "children"),
        Output("curve-browser-selected-wells", "data"),
        Input("curve-browser-session-filter", "value"),
        Input("curve-browser-plate-filter", "value"),
        Input("curve-browser-construct-filter", "value"),
        Input("curve-browser-qc-filter", "value"),
        Input("curve-browser-show-excluded", "checked"),
        Input("curve-browser-reset-filters", "n_clicks"),
        Input("curve-browser-multi-select", "data"),
        State("curve-browser-comparison-set", "data"),
        State("curve-browser-current-well", "data"),
        prevent_initial_call=True,
    )
    def update_well_grid(
        session_id, plate_id, construct_id, qc_filter,
        show_excluded, reset_clicks, multi_select, comparison_set, current_well
    ):
        """Update the well selection grid based on filters."""
        import dash_mantine_components as dmc
        from dash import html

        triggered = ctx.triggered_id

        # Handle reset
        if triggered == "curve-browser-reset-filters":
            return [], "0 wells", []

        if not session_id:
            return [], "0 wells", []

        multi_select = multi_select or []

        try:
            from app.models import Plate, Well, FitResult
            from app.models.experiment import FitStatus
            from app.models.plate_layout import WellType
            from sqlalchemy import or_

            # Build query - only show wells with construct assigned
            query = Well.query.join(Plate).filter(
                Plate.session_id == int(session_id),
                Well.construct_id.isnot(None),  # Only wells with layout assignment
            )

            if plate_id:
                query = query.filter(Well.plate_id == int(plate_id))

            if construct_id:
                query = query.filter(Well.construct_id == int(construct_id))

            # QC filter - uses Well.fit_status enum
            if qc_filter == "passed":
                query = query.filter(Well.fit_status == FitStatus.SUCCESS)
            elif qc_filter == "failed":
                query = query.filter(Well.fit_status == FitStatus.FAILED)
            elif qc_filter == "review":
                query = query.filter(Well.fit_status == FitStatus.NEEDS_REVIEW)

            # Excluded filter
            if not show_excluded:
                query = query.filter(Well.is_excluded == False)

            wells = query.order_by(Plate.plate_number, Well.position).all()

            if not wells:
                return [], "0 wells", []

            # Build grid items
            comparison_set = comparison_set or []
            grid_items = []

            for well in wells:
                # Get fit status from well's fit_status enum
                fit = FitResult.query.filter_by(well_id=well.id).first()
                status = "pending"
                if well.fit_status == FitStatus.SUCCESS:
                    status = "completed"
                elif well.fit_status == FitStatus.FAILED:
                    status = "failed"
                elif well.fit_status == FitStatus.NEEDS_REVIEW:
                    status = "flagged"
                elif fit:
                    # Fallback: determine from fit result if well status not set
                    if fit.r_squared and fit.r_squared > 0.9 and fit.converged:
                        status = "completed"
                    elif fit.r_squared is not None:
                        status = "failed"

                # Get construct name
                construct_name = None
                if well.construct:
                    construct_name = well.construct.identifier

                grid_items.append(
                    create_well_grid_item(
                        well_id=well.id,
                        position=well.position,
                        construct_name=construct_name,
                        status=status,
                        is_excluded=well.is_excluded,
                        is_selected=(current_well == well.id),
                        is_in_comparison=(well.id in comparison_set),
                        is_multi_selected=(well.id in multi_select),
                    )
                )

            # Arrange in grid
            grid = dmc.SimpleGrid(
                cols={"base": 4, "sm": 6, "md": 8},
                spacing="xs",
                children=grid_items,
            )

            well_ids = [w.id for w in wells]
            return grid, f"{len(wells)} wells", well_ids

        except Exception as e:
            print(f"Error loading well grid: {e}")
            return [], "Error", []

    # Callback to sync active panel selection
    @app.callback(
        Output("curve-browser-active-panel", "data"),
        Input("curve-browser-active-panel-select", "value"),
        prevent_initial_call=True,
    )
    def sync_active_panel(panel_value):
        """Sync active panel selection."""
        return int(panel_value) if panel_value else 0

    # Callback to manage panel wells
    @app.callback(
        Output("curve-browser-panel-wells", "data"),
        Output("curve-browser-multi-select-badge", "children"),
        Output("curve-browser-multi-select-badge", "color"),
        Input({"type": "well-grid-item", "well_id": ALL}, "n_clicks"),
        Input("curve-browser-clear-panels", "n_clicks"),
        Input("curve-browser-clear-multi-select", "n_clicks"),
        State("curve-browser-panel-wells", "data"),
        State("curve-browser-active-panel", "data"),
        State("curve-browser-layout", "value"),
        prevent_initial_call=True,
    )
    def manage_panel_wells(grid_clicks, clear_panels, clear_multi, panel_wells, active_panel, layout_value):
        """Manage which wells are assigned to which panels."""
        triggered = ctx.triggered_id
        panel_wells = panel_wells or [[], [], [], []]
        active_panel = active_panel or 0

        # Handle clear
        if triggered in ["curve-browser-clear-panels", "curve-browser-clear-multi-select"]:
            panel_wells = [[], [], [], []]
            return panel_wells, "0 wells", "gray"

        # Handle well click - add to active panel
        if isinstance(triggered, dict) and triggered.get("type") == "well-grid-item":
            clicked_well_id = triggered.get("well_id")

            # Check if well is already in any panel
            found_in_panel = None
            for panel_idx, wells in enumerate(panel_wells):
                if clicked_well_id in wells:
                    found_in_panel = panel_idx
                    break

            if found_in_panel is not None:
                # Remove from that panel
                panel_wells[found_in_panel] = [w for w in panel_wells[found_in_panel] if w != clicked_well_id]
            else:
                # Add to active panel
                panel_wells[active_panel] = panel_wells[active_panel] + [clicked_well_id]

        # Count total wells
        total_wells = sum(len(p) for p in panel_wells)
        badge_text = f"{total_wells} wells"
        badge_color = "teal" if total_wells > 0 else "gray"

        return panel_wells, badge_text, badge_color

    @app.callback(
        Output("curve-browser-current-well", "data"),
        Output("curve-browser-plot", "figure"),
        Output("curve-browser-details-panel", "children"),
        Output("curve-browser-params-panel", "children"),
        Output("curve-browser-well-position", "children"),
        Input("curve-browser-panel-wells", "data"),
        Input("curve-browser-prev-btn", "n_clicks"),
        Input("curve-browser-next-btn", "n_clicks"),
        Input("curve-browser-layout", "value"),
        Input("curve-browser-show-fit", "checked"),
        Input("curve-browser-show-residuals", "checked"),
        State("curve-browser-current-well", "data"),
        State("curve-browser-selected-wells", "data"),
        Input("color-scheme-store", "data"),
        prevent_initial_call=False,  # Allow initial call to show empty state
    )
    def update_curve_display(
        panel_wells, prev_clicks, next_clicks, layout_value, show_fit, show_residuals,
        current_well, selected_wells, scheme
    ):
        """Update curve display based on panel wells."""
        dark_mode = (scheme == "dark")
        triggered = ctx.triggered_id
        selected_wells = selected_wells or []
        panel_wells = panel_wells or [[], [], [], []]

        # Flatten all panel wells for navigation
        all_panel_wells = []
        for panel in panel_wells:
            all_panel_wells.extend(panel)

        well_id = current_well

        # Handle navigation
        if triggered == "curve-browser-prev-btn" and current_well and all_panel_wells:
            try:
                idx = all_panel_wells.index(current_well)
                well_id = all_panel_wells[max(0, idx - 1)]
            except ValueError:
                well_id = all_panel_wells[0] if all_panel_wells else None
        elif triggered == "curve-browser-next-btn" and current_well and all_panel_wells:
            try:
                idx = all_panel_wells.index(current_well)
                well_id = all_panel_wells[min(len(all_panel_wells) - 1, idx + 1)]
            except ValueError:
                well_id = all_panel_wells[0] if all_panel_wells else None
        elif all_panel_wells and not well_id:
            well_id = all_panel_wells[0]

        if not all_panel_wells:
            return None, create_empty_figure(dark_mode=dark_mode), create_empty_plot_message(), None, ""

        try:
            from app.models import Well, Plate, RawDataPoint, FitResult

            # Build panel data for plot
            panels_data = []
            multi_params = []
            color_idx = 0

            for panel_idx, panel_well_ids in enumerate(panel_wells):
                panel_curves = []
                for pw_id in panel_well_ids:
                    pw = Well.query.get(pw_id)
                    if not pw:
                        continue

                    pw_data = RawDataPoint.query.filter_by(
                        well_id=pw_id
                    ).order_by(RawDataPoint.timepoint).all()

                    if pw_data:
                        construct_id = pw.construct.identifier if pw.construct else ""
                        timepoints_pw = [dp.timepoint for dp in pw_data]
                        # Use corrected fluorescence if available (matches fitting service)
                        values_pw = [
                            dp.fluorescence_corrected if dp.fluorescence_corrected is not None
                            else dp.fluorescence_raw
                            for dp in pw_data
                        ]

                        # Get fit data
                        pw_fit = FitResult.query.filter_by(well_id=pw_id).first()
                        fit_values_pw = None
                        pw_fit_params = {}

                        if pw_fit and pw_fit.k_obs is not None:
                            pw_fit_params = {
                                "k_obs": pw_fit.k_obs,
                                "F_max": pw_fit.f_max or 0,
                                "t_lag": pw_fit.t_lag or 0,
                                "F_0": pw_fit.f_baseline or 0,
                                "R2": pw_fit.r_squared or 0,
                            }
                            if show_fit:
                                fit_values_pw = compute_fit_curve(
                                    timepoints_pw,
                                    pw_fit.k_obs,
                                    pw_fit.f_max or 0,
                                    pw_fit.t_lag or 0,
                                    pw_fit.f_baseline or 0,
                                )

                        panel_curves.append({
                            "timepoints": timepoints_pw,
                            "values": values_pw,
                            "fit_values": fit_values_pw,
                            "name": f"{pw.position} ({construct_id})",
                            "color_index": color_idx,
                        })

                        # Add to multi_params for table
                        multi_params.append({
                            "well_id": pw_id,
                            "position": pw.position,
                            "construct": construct_id,
                            "params": pw_fit_params,
                        })

                        color_idx += 1

                panels_data.append(panel_curves)

            # Create panel plot
            fig = create_panel_plot(
                panels=panels_data,
                layout=layout_value,
                show_fit=show_fit,
                show_residuals=show_residuals,
                dark_mode=dark_mode,
            )

            # Get current well details
            well = Well.query.get(well_id) if well_id else None
            if not well and all_panel_wells:
                well = Well.query.get(all_panel_wells[0])
                well_id = all_panel_wells[0] if well else None

            if not well:
                return None, fig, create_empty_plot_message(), None, ""

            # Get fit data for current well
            fit = FitResult.query.filter_by(well_id=well_id).first()
            fit_params = None
            if fit and fit.k_obs is not None:
                fit_params = {
                    "k_obs": fit.k_obs,
                    "F_max": fit.f_max or 0,
                    "t_lag": fit.t_lag or 0,
                    "F_0": fit.f_baseline or 0,
                    "R2": fit.r_squared or 0,
                }
                if fit.rmse:
                    fit_params["rmse"] = fit.rmse

            # Create details panel
            plate = Plate.query.get(well.plate_id)
            plate_name = f"Plate {plate.plate_number}" if plate else "Unknown"
            construct_name = well.construct.identifier if well.construct else "N/A"
            well_type = well.well_type.value if well.well_type else "sample"

            details = create_well_details_panel(
                well_id=well.id,
                position=well.position,
                plate_name=plate_name,
                construct_name=construct_name,
                well_type=well_type,
                ligand=well.ligand_concentration,
                status="completed" if fit and fit.r_squared and fit.r_squared > 0.9 else "pending",
                exclusion_reason=well.exclusion_reason if well.is_excluded else None,
                include_in_fc=not well.exclude_from_fc,
            )

            # Create params panel - use table for multiple wells
            if len(multi_params) > 1:
                params_panel = create_fit_params_panel(
                    multi_params=multi_params,
                )
            else:
                params_panel = create_fit_params_panel(
                    params=fit_params,
                    uncertainties=None,  # Would come from fit uncertainty estimates
                )

            # Position indicator
            if all_panel_wells and well_id in all_panel_wells:
                idx = all_panel_wells.index(well_id) + 1
                position_text = f"{idx} / {len(all_panel_wells)}"
            else:
                position_text = well.position

            return well_id, fig, details, params_panel, position_text

        except Exception as e:
            print(f"Error displaying curve: {e}")
            import traceback
            traceback.print_exc()
            return well_id, create_empty_figure(dark_mode=dark_mode), None, None, ""

    @app.callback(
        Output("curve-browser-comparison-set", "data"),
        Input("curve-browser-add-comparison-btn", "n_clicks"),
        Input("curve-browser-clear-comparison-btn", "n_clicks"),
        State("curve-browser-current-well", "data"),
        State("curve-browser-comparison-set", "data"),
        prevent_initial_call=True,
    )
    def manage_comparison_set(add_clicks, clear_clicks, current_well, comparison_set):
        """Manage the comparison set."""
        triggered = ctx.triggered_id
        comparison_set = comparison_set or []

        if triggered == "curve-browser-clear-comparison-btn":
            return []

        if triggered == "curve-browser-add-comparison-btn" and current_well:
            if current_well not in comparison_set:
                comparison_set = comparison_set + [current_well]

        return comparison_set

    @app.callback(
        Output("curve-browser-exclusion-modal", "opened"),
        Input("curve-browser-exclude-btn", "n_clicks"),
        Input("curve-browser-exclusion-cancel", "n_clicks"),
        Input("curve-browser-exclusion-confirm", "n_clicks"),
        State("curve-browser-exclusion-modal", "opened"),
        prevent_initial_call=True,
    )
    def toggle_exclusion_modal(exclude_clicks, cancel_clicks, confirm_clicks, is_open):
        """Toggle the exclusion reason modal."""
        triggered = ctx.triggered_id

        if triggered == "curve-browser-exclude-btn":
            return True
        elif triggered in ["curve-browser-exclusion-cancel", "curve-browser-exclusion-confirm"]:
            return False

        return is_open

    @app.callback(
        Output("curve-browser-exclude-btn", "style"),
        Output("curve-browser-include-btn", "style"),
        Input("curve-browser-current-well", "data"),
        prevent_initial_call=True,
    )
    def update_exclusion_buttons(well_id):
        """Update visibility of exclude/include buttons."""
        if not well_id:
            return {"display": "block"}, {"display": "none"}

        try:
            from app.models import Well

            well = Well.query.get(well_id)
            if well and well.is_excluded:
                return {"display": "none"}, {"display": "block"}
            else:
                return {"display": "block"}, {"display": "none"}
        except Exception:
            return {"display": "block"}, {"display": "none"}

    @app.callback(
        Output("curve-browser-current-well", "data", allow_duplicate=True),
        Input("curve-browser-exclusion-confirm", "n_clicks"),
        Input("curve-browser-include-btn", "n_clicks"),
        State("curve-browser-current-well", "data"),
        State("curve-browser-exclusion-reason", "value"),
        prevent_initial_call=True,
    )
    def handle_exclusion(confirm_clicks, include_clicks, well_id, reason):
        """Handle well exclusion/inclusion."""
        if not well_id:
            raise PreventUpdate

        triggered = ctx.triggered_id

        try:
            from app.models import Well
            from app.extensions import db

            well = Well.query.get(well_id)
            if not well:
                raise PreventUpdate

            if triggered == "curve-browser-exclusion-confirm":
                well.is_excluded = True
                well.exclusion_reason = reason or "No reason provided"
                well.exclude_from_fc = True  # Also exclude from FC when excluding well
            elif triggered == "curve-browser-include-btn":
                well.is_excluded = False
                well.exclusion_reason = None
                # Note: don't automatically include in FC when un-excluding

            db.session.commit()

            # Return same well_id to trigger refresh
            return well_id

        except Exception as e:
            print(f"Error updating exclusion: {e}")
            raise PreventUpdate

    @app.callback(
        Output("refit-wells-store", "data"),
        Output("url", "pathname", allow_duplicate=True),
        Input("curve-browser-refit-btn", "n_clicks"),
        State("curve-browser-panel-wells", "data"),
        State("curve-browser-project-store", "data"),
        prevent_initial_call=True,
    )
    def navigate_to_analysis_for_refit(n_clicks, panel_wells, project_id):
        """Navigate to analysis page with selected wells for refitting."""
        if not n_clicks or not project_id:
            raise PreventUpdate

        # Collect all wells from panels
        all_wells = []
        panel_wells = panel_wells or [[], [], [], []]
        for panel in panel_wells:
            all_wells.extend(panel)

        if not all_wells:
            raise PreventUpdate

        # Store wells for analysis page to pick up
        return all_wells, f"/project/{project_id}/analysis"

    # =========================================================================
    # FC (Fold Change) Inclusion Callbacks
    # These callbacks sync with the Analysis tab's FC inclusion checkbox.
    # See: analysis_callbacks.py toggle_well_fc_inclusion()
    # The underlying field is Well.exclude_from_fc (Boolean)
    # =========================================================================

    @app.callback(
        Output("curve-browser-fc-exclude-btn", "style"),
        Output("curve-browser-fc-include-btn", "style"),
        Input("curve-browser-current-well", "data"),
        prevent_initial_call=True,
    )
    def update_fc_buttons(well_id):
        """
        Update visibility of FC exclude/include buttons based on well's FC status.

        Syncs with Analysis tab - see analysis_callbacks.py toggle_well_fc_inclusion()
        """
        if not well_id:
            return {"display": "block"}, {"display": "none"}

        try:
            from app.models import Well

            well = Well.query.get(well_id)
            if well and well.exclude_from_fc:
                # Well is excluded from FC - show "Include in FC" button
                return {"display": "none"}, {"display": "block"}
            else:
                # Well is included in FC - show "Exclude from FC" button
                return {"display": "block"}, {"display": "none"}
        except Exception:
            return {"display": "block"}, {"display": "none"}

    @app.callback(
        Output("curve-browser-current-well", "data", allow_duplicate=True),
        Input("curve-browser-fc-exclude-btn", "n_clicks"),
        Input("curve-browser-fc-include-btn", "n_clicks"),
        State("curve-browser-current-well", "data"),
        prevent_initial_call=True,
    )
    def handle_fc_inclusion(exclude_clicks, include_clicks, well_id):
        """
        Handle FC inclusion/exclusion toggle from curve browser.

        This uses the same service as the Analysis tab to ensure consistency.
        See: analysis_callbacks.py toggle_well_fc_inclusion()
        """
        if not well_id:
            raise PreventUpdate

        triggered = ctx.triggered_id

        try:
            from app.services.fitting_service import FittingService

            if triggered == "curve-browser-fc-exclude-btn":
                # Exclude from FC calculation
                FittingService.set_well_fc_inclusion(well_id, include=False)
            elif triggered == "curve-browser-fc-include-btn":
                # Include in FC calculation
                FittingService.set_well_fc_inclusion(well_id, include=True)

            # Return same well_id to trigger refresh of details panel
            return well_id

        except Exception as e:
            print(f"Error updating FC inclusion: {e}")
            raise PreventUpdate
