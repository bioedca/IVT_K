"""
Callbacks for the Negative Control Dashboard.

Phase 3.5.8: Negative Control Dashboard (F19.13)

Handles:
- Session/plate selection
- Background summary computation
- Detection limit display
- Time series and heatmap visualization
"""
from typing import Dict, Any, List, Optional
from dash import callback, Input, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate

from app.theme import apply_plotly_theme
from app.logging_config import get_logger

logger = get_logger(__name__)

from app.layouts.negative_control_dashboard import (
    create_background_summary_table,
    create_detection_limits_display,
    create_detection_status_display,
    create_background_timeseries_plot,
    create_plate_heatmap,
    create_empty_dashboard_message,
    create_qc_status_badge,
)


def register_negative_control_callbacks(app):
    """Register all negative control dashboard callbacks."""

    @app.callback(
        Output("neg-ctrl-session-select", "data"),
        Input("neg-ctrl-project-store", "data"),
        prevent_initial_call=False,  # Must fire on initial load to populate sessions
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
        Output("neg-ctrl-plate-select", "data"),
        Output("neg-ctrl-heatmap-plate", "data"),
        Output("neg-ctrl-heatmap-plate", "value"),
        Input("neg-ctrl-session-select", "value"),
        State("neg-ctrl-project-store", "data"),
        prevent_initial_call=True,
    )
    def load_plates(session_id, project_id):
        """Load plates for the selected session."""
        if not session_id:
            return [], [], None

        try:
            from app.models import Plate

            plates = Plate.query.filter_by(
                session_id=int(session_id)
            ).order_by(Plate.plate_number).all()

            plate_options = [
                {"value": str(p.id), "label": f"Plate {p.plate_number}"}
                for p in plates
            ]

            # Auto-select first plate for heatmap
            first_plate_value = plate_options[0]["value"] if plate_options else None

            return plate_options, plate_options, first_plate_value
        except Exception:
            return [], [], None

    @app.callback(
        Output("neg-ctrl-data-store", "data"),
        Input("neg-ctrl-refresh-btn", "n_clicks"),
        Input("neg-ctrl-session-select", "value"),
        Input("neg-ctrl-plate-select", "value"),
        State("neg-ctrl-project-store", "data"),
        prevent_initial_call=True,
    )
    def compute_negative_control_analysis(n_clicks, session_id, plate_ids, project_id):
        """Compute negative control analysis for selected plates."""
        if not session_id:
            raise PreventUpdate

        try:
            from app.models import Plate, Well, RawDataPoint, Project
            from app.models.plate_layout import WellType
            from app.analysis import NegativeControlAnalyzer

            # Build analyzer with project-specific thresholds
            analyzer_kwargs = {}
            if project_id:
                project = Project.query.get(project_id)
                if project:
                    analyzer_kwargs = dict(
                        k_lod=project.lod_coverage_factor,
                        k_loq=project.loq_coverage_factor,
                        bsi_threshold=project.qc_bsi_threshold,
                        cv_threshold=project.qc_neg_cv_threshold,
                    )
            analyzer = NegativeControlAnalyzer(**analyzer_kwargs)

            # Get plates
            if plate_ids:
                plates = Plate.query.filter(Plate.id.in_([int(p) for p in plate_ids])).all()
            else:
                plates = Plate.query.filter_by(session_id=int(session_id)).all()

            if not plates:
                return None

            plate_summaries = []
            all_lods = []
            all_loqs = []
            total_samples = 0
            below_lod_count = 0
            below_loq_count = 0
            aggregated_bg_data = {}
            aggregated_timepoints = []

            for plate in plates:
                # Get negative control wells
                neg_wells = Well.query.filter_by(plate_id=plate.id).filter(
                    Well.well_type.in_([
                        WellType.NEGATIVE_CONTROL_NO_TEMPLATE,
                        WellType.NEGATIVE_CONTROL_NO_DYE,
                    ])
                ).all()

                if not neg_wells:
                    continue

                # Get well data
                neg_control_data = {}
                timepoints = None

                for well in neg_wells:
                    data_points = RawDataPoint.query.filter_by(
                        well_id=well.id
                    ).order_by(RawDataPoint.timepoint).all()

                    if data_points:
                        values = [dp.fluorescence_raw for dp in data_points]
                        neg_control_data[well.position] = values

                        if timepoints is None:
                            timepoints = [dp.timepoint for dp in data_points]

                if not neg_control_data:
                    continue

                # Run analysis
                report = analyzer.run_full_analysis(
                    neg_control_data,
                    timepoints=timepoints,
                )

                stats = report.background_stats
                limits = report.detection_limits

                plate_summaries.append({
                    "plate_id": plate.id,
                    "plate_name": f"P{plate.plate_number}",
                    "n_controls": stats.n_controls,
                    "mean_bg": stats.mean_background,
                    "sd_bg": stats.sd_background,
                    "cv": stats.cv,
                    "bsi": stats.bsi,
                    "correction_method": report.correction_method.value,
                })

                all_lods.append(limits.lod)
                all_loqs.append(limits.loq)

                # Aggregate timepoints and background data
                if not aggregated_timepoints and stats.timepoints:
                    aggregated_timepoints = stats.timepoints

                for pos, values in neg_control_data.items():
                    aggregated_bg_data[f"{plate.plate_number}_{pos}"] = values

                # Count samples relative to detection limits
                sample_wells = Well.query.filter_by(plate_id=plate.id).filter(
                    Well.well_type == WellType.SAMPLE
                ).all()

                for well in sample_wells:
                    # Get max fluorescence as signal proxy
                    data_points = RawDataPoint.query.filter_by(
                        well_id=well.id
                    ).all()

                    if data_points:
                        max_signal = max(dp.fluorescence_raw for dp in data_points)
                        total_samples += 1

                        if max_signal < limits.lod:
                            below_lod_count += 1
                        elif max_signal < limits.loq:
                            below_loq_count += 1

            # Compute aggregate statistics
            if all_lods:
                avg_lod = sum(all_lods) / len(all_lods)
                avg_loq = sum(all_loqs) / len(all_loqs)
            else:
                avg_lod = 0
                avg_loq = 0

            # Compute mean/SD across all plates
            if plate_summaries:
                avg_mean_bg = sum(p["mean_bg"] for p in plate_summaries) / len(plate_summaries)
                avg_sd_bg = sum(p["sd_bg"] for p in plate_summaries) / len(plate_summaries)
                min_fc = avg_lod / avg_mean_bg if avg_mean_bg > 0 else 1.0
            else:
                avg_mean_bg = 0
                avg_sd_bg = 0
                min_fc = 1.0

            # Compute aggregated mean by timepoint
            n_timepoints = len(aggregated_timepoints) if aggregated_timepoints else 0
            mean_by_tp = []
            sd_by_tp = []

            if n_timepoints > 0 and aggregated_bg_data:
                for t_idx in range(n_timepoints):
                    values_at_t = []
                    for well_values in aggregated_bg_data.values():
                        if t_idx < len(well_values):
                            values_at_t.append(well_values[t_idx])

                    if values_at_t:
                        mean_by_tp.append(sum(values_at_t) / len(values_at_t))
                        if len(values_at_t) > 1:
                            import numpy as np
                            sd_by_tp.append(float(np.std(values_at_t, ddof=1)))
                        else:
                            sd_by_tp.append(0.0)

            return {
                "plate_summaries": plate_summaries,
                "detection": {
                    "lod": avg_lod,
                    "loq": avg_loq,
                    "min_detectable_fc": min_fc,
                },
                "status": {
                    "total_samples": total_samples,
                    "below_lod": below_lod_count,
                    "below_loq": below_loq_count,
                },
                "timeseries": {
                    "timepoints": aggregated_timepoints,
                    "mean_values": mean_by_tp,
                    "sd_values": sd_by_tp,
                    "individual_wells": aggregated_bg_data,
                },
            }

        except Exception as e:
            print(f"Error computing negative control analysis: {e}")
            return None

    @app.callback(
        Output("neg-ctrl-summary-table", "children"),
        Input("neg-ctrl-data-store", "data"),
    )
    def update_summary_table(data):
        """Update the background summary table."""
        if not data:
            return create_empty_dashboard_message()

        plate_summaries = data.get("plate_summaries", [])
        return create_background_summary_table(plate_summaries)

    @app.callback(
        Output("neg-ctrl-detection-limits", "children"),
        Input("neg-ctrl-data-store", "data"),
    )
    def update_detection_limits(data):
        """Update detection limits display."""
        if not data:
            return create_empty_dashboard_message()

        detection = data.get("detection", {})
        return create_detection_limits_display(
            lod=detection.get("lod", 0),
            loq=detection.get("loq", 0),
            min_detectable_fc=detection.get("min_detectable_fc", 1.0),
        )

    @app.callback(
        Output("neg-ctrl-detection-status", "children"),
        Input("neg-ctrl-data-store", "data"),
    )
    def update_detection_status(data):
        """Update detection status display."""
        if not data:
            return create_empty_dashboard_message()

        status = data.get("status", {})
        return create_detection_status_display(
            total_samples=status.get("total_samples", 0),
            below_lod=status.get("below_lod", 0),
            below_loq=status.get("below_loq", 0),
        )

    @app.callback(
        Output("neg-ctrl-timeseries-plot", "figure"),
        Input("neg-ctrl-data-store", "data"),
        Input("neg-ctrl-timeseries-type", "value"),
        Input("color-scheme-store", "data"),
    )
    def update_timeseries_plot(data, plot_type, scheme):
        """Update background time series plot."""
        import plotly.graph_objects as go

        dark_mode = (scheme == "dark")

        if not data:
            fig = go.Figure()
            apply_plotly_theme(fig, dark_mode=dark_mode)
            return fig

        timeseries = data.get("timeseries", {})
        timepoints = timeseries.get("timepoints", [])
        mean_values = timeseries.get("mean_values", [])
        sd_values = timeseries.get("sd_values", [])
        individual_wells = timeseries.get("individual_wells", {})

        if not timepoints or not mean_values:
            fig = go.Figure()
            apply_plotly_theme(fig, dark_mode=dark_mode)
            return fig

        fig = create_background_timeseries_plot(
            timepoints=timepoints,
            mean_values=mean_values,
            sd_values=sd_values,
            individual_wells=individual_wells,
            show_all=(plot_type == "all"),
        )
        apply_plotly_theme(fig, dark_mode=dark_mode)
        return fig

    @app.callback(
        Output("neg-ctrl-heatmap", "figure"),
        Input("neg-ctrl-heatmap-plate", "value"),
        Input("neg-ctrl-data-store", "data"),
        Input("color-scheme-store", "data"),
        prevent_initial_call=True,
    )
    def update_heatmap(plate_id, data, scheme):
        """Update plate heatmap."""
        import plotly.graph_objects as go

        dark_mode = (scheme == "dark")

        if not plate_id or not data:
            fig = go.Figure()
            apply_plotly_theme(fig, dark_mode=dark_mode)
            return fig

        try:
            from app.models import Plate, Well, RawDataPoint
            from app.models.plate_layout import WellType

            plate = Plate.query.get(int(plate_id))
            if not plate:
                fig = go.Figure()
                apply_plotly_theme(fig, dark_mode=dark_mode)
                return fig

            # Get all wells with mean background values
            wells = Well.query.filter_by(plate_id=plate.id).all()
            well_values = {}

            for well in wells:
                # Only show negative control wells on heatmap
                if well.well_type in [
                    WellType.NEGATIVE_CONTROL_NO_TEMPLATE,
                    WellType.NEGATIVE_CONTROL_NO_DYE,
                ]:
                    data_points = RawDataPoint.query.filter_by(
                        well_id=well.id
                    ).all()

                    if data_points:
                        mean_val = sum(dp.fluorescence_raw for dp in data_points) / len(data_points)
                        well_values[well.position] = mean_val

            # Determine plate format from project
            plate_format = 96
            if plate.session and plate.session.project:
                plate_format = int(plate.session.project.plate_format.value)

            fig = create_plate_heatmap(
                well_values=well_values,
                plate_format=plate_format,
                title="Mean BG (RFU)",
                dark_mode=dark_mode,
            )
            return fig

        except Exception as e:
            print(f"Error creating heatmap: {e}")
            fig = go.Figure()
            apply_plotly_theme(fig, dark_mode=dark_mode)
            return fig

    @app.callback(
        Output("neg-ctrl-next-issue-btn", "disabled"),
        Input("neg-ctrl-project-store", "data"),
        prevent_initial_call=False,
    )
    def init_next_issue_button(project_id):
        """Initialize Next Issue button state on page load."""
        if not project_id:
            return True

        try:
            from app.models import ExperimentalSession
            from app.models.experiment import QCStatus

            # Enable if there are any unresolved sessions
            unresolved_count = ExperimentalSession.query.filter(
                ExperimentalSession.project_id == project_id,
                ExperimentalSession.qc_status.in_([QCStatus.PENDING, QCStatus.IN_REVIEW])
            ).count()
            return unresolved_count == 0

        except Exception:
            return True

    @app.callback(
        [
            Output("neg-ctrl-qc-status-badge", "children"),
            Output("neg-ctrl-qc-status-store", "data"),
            Output("neg-ctrl-approve-btn", "disabled"),
            Output("neg-ctrl-reject-btn", "disabled"),
            Output("neg-ctrl-qc-notes", "value"),
            Output("neg-ctrl-next-issue-btn", "disabled", allow_duplicate=True),
        ],
        Input("neg-ctrl-session-select", "value"),
        State("neg-ctrl-project-store", "data"),
        prevent_initial_call=True,
    )
    def load_qc_status(session_id, project_id):
        """Load QC status for the selected session."""
        # Check for unresolved sessions (needed for Next Issue button)
        next_issue_disabled = True
        try:
            from app.models import ExperimentalSession
            from app.models.experiment import QCStatus

            if project_id:
                unresolved_count = ExperimentalSession.query.filter(
                    ExperimentalSession.project_id == project_id,
                    ExperimentalSession.qc_status.in_([QCStatus.PENDING, QCStatus.IN_REVIEW])
                ).count()
                next_issue_disabled = unresolved_count == 0
        except Exception:
            pass

        if not session_id:
            # No session selected - disable approve/reject but enable Next Issue if there are pending sessions
            return None, None, True, True, "", next_issue_disabled

        try:
            from app.models import ExperimentalSession
            from app.models.experiment import QCStatus

            session = ExperimentalSession.query.get(int(session_id))
            if not session:
                return None, None, True, True, "", next_issue_disabled

            qc_status = session.qc_status.value if session.qc_status else "pending"
            reviewed_by = session.qc_reviewed_by
            reviewed_at = session.qc_reviewed_at.strftime("%Y-%m-%d %H:%M") if session.qc_reviewed_at else None
            qc_notes = session.qc_notes or ""

            badge = create_qc_status_badge(qc_status, reviewed_by, reviewed_at)

            # Approve/reject buttons are always enabled when a session is selected
            # This allows users to change their decision if needed
            buttons_disabled = False

            return (
                badge,
                {"session_id": session_id, "status": qc_status},
                buttons_disabled,
                buttons_disabled,
                qc_notes,
                next_issue_disabled,
            )

        except Exception as e:
            print(f"Error loading QC status: {e}")
            return None, None, True, True, "", next_issue_disabled

    @app.callback(
        [
            Output("neg-ctrl-notification-container", "children"),
            Output("neg-ctrl-qc-status-badge", "children", allow_duplicate=True),
            Output("neg-ctrl-qc-status-store", "data", allow_duplicate=True),
            Output("neg-ctrl-approve-btn", "disabled", allow_duplicate=True),
            Output("neg-ctrl-reject-btn", "disabled", allow_duplicate=True),
            Output("neg-ctrl-next-issue-btn", "disabled", allow_duplicate=True),
        ],
        [
            Input("neg-ctrl-approve-btn", "n_clicks"),
            Input("neg-ctrl-reject-btn", "n_clicks"),
        ],
        [
            State("neg-ctrl-session-select", "value"),
            State("neg-ctrl-qc-notes", "value"),
            State("neg-ctrl-project-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def handle_qc_action(approve_clicks, reject_clicks, session_id, qc_notes, project_id):
        """Handle QC approve or reject action."""
        import dash_mantine_components as dmc
        from dash_iconify import DashIconify
        from datetime import datetime, timezone
        from flask import request

        if not session_id:
            raise PreventUpdate

        triggered = ctx.triggered_id
        if not triggered:
            raise PreventUpdate

        try:
            from app.models import ExperimentalSession, AuditLog
            from app.models.experiment import QCStatus
            from app.extensions import db

            session = ExperimentalSession.query.get(int(session_id))
            if not session:
                raise PreventUpdate

            # Determine action
            if triggered == "neg-ctrl-approve-btn":
                new_status = QCStatus.APPROVED
                action_type = "qc_approve"
                message = "QC approved successfully!"
                color = "green"
            elif triggered == "neg-ctrl-reject-btn":
                new_status = QCStatus.REJECTED
                action_type = "qc_reject"
                message = "QC rejected. Please review the data."
                color = "red"
            else:
                raise PreventUpdate

            # Update session
            old_status = session.qc_status.value if session.qc_status else "pending"
            session.qc_status = new_status
            session.qc_reviewed_at = datetime.now(timezone.utc)
            session.qc_reviewed_by = request.headers.get("X-Username", "unknown")
            session.qc_notes = qc_notes

            # Audit log
            AuditLog.log_action(
                username=session.qc_reviewed_by,
                action_type=action_type,
                entity_type="experimental_session",
                entity_id=session.id,
                project_id=session.project_id,
                changes=[
                    {"field": "qc_status", "old": old_status, "new": new_status.value},
                    {"field": "qc_notes", "old": None, "new": qc_notes},
                ]
            )

            db.session.commit()

            # Check if there are more unresolved sessions
            unresolved_count = ExperimentalSession.query.filter(
                ExperimentalSession.project_id == project_id,
                ExperimentalSession.qc_status.in_([QCStatus.PENDING, QCStatus.IN_REVIEW])
            ).count()
            next_issue_disabled = unresolved_count == 0

            # Create notification with hint about next issue
            if not next_issue_disabled:
                message += f" ({unresolved_count} session(s) still pending review)"

            notification = dmc.Alert(
                message,
                title="QC Review Complete" if new_status == QCStatus.APPROVED else "QC Rejected",
                color=color,
                icon=DashIconify(icon="mdi:check-circle" if new_status == QCStatus.APPROVED else "mdi:alert"),
                withCloseButton=True,
                style={"marginBottom": "1rem"},
            )

            # Create updated badge
            badge = create_qc_status_badge(
                new_status.value,
                session.qc_reviewed_by,
                session.qc_reviewed_at.strftime("%Y-%m-%d %H:%M"),
            )

            return (
                notification,
                badge,
                {"session_id": session_id, "status": new_status.value},
                False,  # Keep approve button enabled (allow changing decision)
                False,  # Keep reject button enabled (allow changing decision)
                next_issue_disabled,  # Enable "Next Issue" if there are more
            )

        except Exception as e:
            logger.exception("Error handling QC action")

            notification = dmc.Alert(
                "An unexpected error occurred during QC review. Please try again.",
                title="QC Review Failed",
                color="red",
                icon=DashIconify(icon="mdi:alert-circle"),
                withCloseButton=True,
                style={"marginBottom": "1rem"},
            )

            return notification, no_update, no_update, no_update, no_update, no_update

    @app.callback(
        Output("neg-ctrl-session-select", "value", allow_duplicate=True),
        Input("neg-ctrl-next-issue-btn", "n_clicks"),
        [
            State("neg-ctrl-project-store", "data"),
            State("neg-ctrl-session-select", "value"),
        ],
        prevent_initial_call=True,
    )
    def navigate_to_next_issue(n_clicks, project_id, current_session_id):
        """Navigate to the next unresolved session when 'Next Issue' is clicked."""
        if not n_clicks or not project_id:
            raise PreventUpdate

        try:
            from app.models import ExperimentalSession
            from app.models.experiment import QCStatus

            # Find the next unresolved session (PENDING or IN_REVIEW)
            # Order by date ascending so we process oldest first
            next_session = ExperimentalSession.query.filter(
                ExperimentalSession.project_id == project_id,
                ExperimentalSession.qc_status.in_([QCStatus.PENDING, QCStatus.IN_REVIEW])
            ).order_by(ExperimentalSession.date.asc()).first()

            if next_session:
                return str(next_session.id)
            else:
                # No more unresolved sessions
                raise PreventUpdate

        except Exception as e:
            print(f"Error navigating to next issue: {e}")
            raise PreventUpdate
