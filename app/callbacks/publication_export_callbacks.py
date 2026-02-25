"""
Publication Export callbacks.

Phase 9.4-9.5: Publication package export callbacks (F15.8-F15.10)

Handles:
- Package preview generation
- File exclusion toggling
- Package download
- Package validation
"""
from dash import Input, Output, State, callback, no_update, ctx, ALL
from dash.exceptions import PreventUpdate
import json
import logging

logger = logging.getLogger(__name__)


def register_publication_export_callbacks(app):
    """Register all publication export callbacks."""

    @app.callback(
        [
            Output("export-preview-store", "data"),
            Output("export-preview-content", "children"),
            Output("export-total-size", "children"),
            Output("export-download-btn", "disabled"),
            Output("export-validate-btn", "disabled"),
        ],
        [
            Input("export-preview-btn", "n_clicks"),
            Input("export-refresh-preview", "n_clicks"),
        ],
        [
            State("export-project-store", "data"),
            State("export-include-raw", "checked"),
            State("export-include-traces", "checked"),
            State("export-include-figures", "checked"),
            State("export-include-audit", "checked"),
            State("export-figure-format", "value"),
            State("export-figure-dpi", "value"),
            State("export-excluded-files", "data"),
        ],
        prevent_initial_call=True,
    )
    def generate_preview(
        preview_clicks, refresh_clicks,
        project_id,
        include_raw, include_traces, include_figures, include_audit,
        figure_format, figure_dpi,
        excluded_files,
    ):
        """Generate package preview."""
        import dash_mantine_components as dmc
        from dash_iconify import DashIconify

        if not project_id:
            raise PreventUpdate

        try:
            from app.services.publication_package_service import (
                PublicationPackageService,
                PublicationPackageConfig,
            )
            from app.layouts.publication_export import create_directory_tree

            # Build config
            config = PublicationPackageConfig(
                include_raw_data=include_raw,
                include_mcmc_traces=include_traces,
                include_figures=include_figures,
                include_audit_log=include_audit,
                figure_format=figure_format,
                figure_dpi=figure_dpi,
            )

            # Get preview
            preview = PublicationPackageService.get_package_preview(
                project_id, config
            )

            # Calculate size excluding excluded files
            total_size = preview.get("total_estimated_size", 0)
            excluded = excluded_files or []
            for dir_info in preview.get("directories", []):
                for file_info in dir_info.get("files", []):
                    file_path = f"{dir_info['name']}/{file_info['name']}"
                    if file_path in excluded:
                        total_size -= file_info.get("estimated_size", 0)

            # Format size
            if total_size < 1024:
                size_str = f"{total_size} B"
            elif total_size < 1024 * 1024:
                size_str = f"{total_size / 1024:.1f} KB"
            else:
                size_str = f"{total_size / (1024 * 1024):.1f} MB"

            # Create tree display
            tree = create_directory_tree(preview, excluded)

            return (
                preview,
                tree,
                f"Estimated size: {size_str}",
                False,  # Enable download button
                False,  # Enable validate button
            )

        except Exception as e:
            logger.exception("Error generating package preview")
            error_display = dmc.Alert(
                "Error generating preview. Check server logs for details.",
                color="red",
                icon=DashIconify(icon="mdi:alert-circle"),
            )
            return (
                None,
                error_display,
                "Estimated size: --",
                True,
                True,
            )

    @app.callback(
        Output("export-excluded-files", "data"),
        Input({"type": "export-file-checkbox", "index": ALL}, "checked"),
        State({"type": "export-file-checkbox", "index": ALL}, "id"),
        State("export-excluded-files", "data"),
        prevent_initial_call=True,
    )
    def update_excluded_files(checked_values, checkbox_ids, current_excluded):
        """Update list of excluded files based on checkbox state."""
        if not checkbox_ids:
            raise PreventUpdate

        excluded = set(current_excluded or [])

        for checkbox, is_checked in zip(checkbox_ids, checked_values):
            file_path = checkbox["index"]
            if is_checked:
                excluded.discard(file_path)
            else:
                excluded.add(file_path)

        return list(excluded)

    @app.callback(
        Output("export-config-store", "data"),
        [
            Input("export-title", "value"),
            Input("export-description", "value"),
            Input("export-authors", "value"),
            Input("export-keywords", "value"),
            Input("export-license", "value"),
            Input("export-include-raw", "checked"),
            Input("export-include-traces", "checked"),
            Input("export-include-figures", "checked"),
            Input("export-include-audit", "checked"),
            Input("export-figure-format", "value"),
            Input("export-figure-dpi", "value"),
        ],
    )
    def update_config_store(
        title, description, authors, keywords, license_type,
        include_raw, include_traces, include_figures, include_audit,
        figure_format, figure_dpi,
    ):
        """Update config store when any config value changes."""
        return {
            "title": title or "",
            "description": description or "",
            "authors": [a.strip() for a in (authors or "").split(",") if a.strip()],
            "keywords": [k.strip() for k in (keywords or "").split(",") if k.strip()],
            "license": license_type,
            "include_raw_data": include_raw,
            "include_mcmc_traces": include_traces,
            "include_figures": include_figures,
            "include_audit_log": include_audit,
            "figure_format": figure_format,
            "figure_dpi": figure_dpi,
        }

    @app.callback(
        Output("export-download", "data"),
        Input("export-download-btn", "n_clicks"),
        [
            State("export-project-store", "data"),
            State("export-config-store", "data"),
            State("export-excluded-files", "data"),
        ],
        prevent_initial_call=True,
    )
    def download_package(n_clicks, project_id, config_data, excluded_files):
        """Generate and download publication package."""
        if not n_clicks or not project_id or not config_data:
            raise PreventUpdate

        try:
            from app.services.publication_package_service import (
                PublicationPackageService,
                PublicationPackageConfig,
            )
            from app.services.export_service import ExportService
            from app.models import Project, AuditLog
            from dash import dcc

            project = Project.query.get(project_id)
            if not project:
                raise PreventUpdate

            # Build config
            config = PublicationPackageConfig(
                title=config_data.get("title") or project.name,
                authors=config_data.get("authors", []),
                description=config_data.get("description", ""),
                keywords=config_data.get("keywords", []),
                license=config_data.get("license", "CC-BY-4.0"),
                include_raw_data=config_data.get("include_raw_data", True),
                include_mcmc_traces=config_data.get("include_mcmc_traces", True),
                include_figures=config_data.get("include_figures", True),
                include_audit_log=config_data.get("include_audit_log", True),
                figure_format=config_data.get("figure_format", "png"),
                figure_dpi=config_data.get("figure_dpi", 300),
            )

            # Get data
            raw_data = ExportService.get_raw_data_for_export(project_id)
            results = ExportService.get_results_for_export(project_id)
            mcmc_traces = ExportService.get_mcmc_traces_for_export(project_id) if config.include_mcmc_traces else None

            # Get figures
            figures = None
            if config.include_figures:
                figures = PublicationPackageService.generate_figures_for_package(
                    project_id, config
                )

            # Get audit events
            audit_events = None
            if config.include_audit_log:
                audit_logs = AuditLog.query.filter_by(project_id=project_id).all()
                audit_events = [
                    {
                        "timestamp": log.timestamp.isoformat() if log.timestamp else "",
                        "action": log.action_type,
                        "user": log.username,
                        "details": log.details,
                        "changes": log.changes,
                    }
                    for log in audit_logs
                ]

            # Get analysis config
            plate_fmt = project.plate_format
            analysis_config = {
                "kinetic_model": project.kinetic_model_type,
                "reporter_system": project.reporter_system,
                "plate_format": plate_fmt.value if hasattr(plate_fmt, 'value') else str(plate_fmt),
                "precision_target": project.precision_target or 0.3,
            }

            # Create package
            zip_bytes, manifest = PublicationPackageService.create_publication_package(
                config=config,
                raw_data=raw_data,
                results=results,
                mcmc_traces=mcmc_traces,
                figures=figures,
                audit_events=audit_events,
                analysis_config=analysis_config,
            )

            # Generate filename
            filename = PublicationPackageService.generate_package_filename(
                project.name
            )

            return dcc.send_bytes(zip_bytes, filename)

        except Exception as e:
            logger.exception("Error creating publication package")
            raise PreventUpdate

    @app.callback(
        Output("export-status-badge", "children"),
        Output("export-status-badge", "color"),
        Input("export-validate-btn", "n_clicks"),
        State("export-project-store", "data"),
        prevent_initial_call=True,
    )
    def validate_package(n_clicks, project_id):
        """Validate package can be created."""
        if not n_clicks or not project_id:
            raise PreventUpdate

        try:
            from app.models import (
                Project, Plate, Well, FitResult, FoldChange, ExperimentalSession,
            )

            project = Project.query.get(project_id)
            if not project:
                return "Project not found", "red"

            # Check for required data
            fit_count = FitResult.query.join(Well).join(Plate).join(
                ExperimentalSession
            ).filter(ExperimentalSession.project_id == project_id).count()
            fc_count = FoldChange.query.join(
                Well, FoldChange.test_well_id == Well.id
            ).join(Plate).join(ExperimentalSession).filter(
                ExperimentalSession.project_id == project_id
            ).count()

            if fit_count == 0:
                return "No fit results", "yellow"

            if fc_count == 0:
                return "No fold changes", "yellow"

            return "Valid", "green"

        except Exception as e:
            logger.exception("Error validating publication package")
            return "Validation error", "red"

    # ========== Daily Report Callbacks ==========

    @app.callback(
        [
            Output("report-plate-select", "data"),
            Output("report-plate-select", "value"),
            Output("report-version-select", "data"),
            Output("report-version-select", "value"),
            Output("report-protocol-select", "data"),
            Output("report-protocol-select", "value"),
        ],
        Input("export-project-store", "data"),
    )
    def populate_report_selectors(project_id):
        """Populate plate, analysis version, and protocol selectors when project loads."""
        if not project_id:
            return [], [], [], None, [], None

        try:
            from app.models import Plate, ExperimentalSession
            from app.models.analysis_version import AnalysisVersion, AnalysisStatus
            from app.models.reaction_setup import ReactionSetup

            # Get plates for this project
            plates = Plate.query.join(ExperimentalSession).filter(
                ExperimentalSession.project_id == project_id,
            ).order_by(Plate.plate_number).all()

            plate_options = []
            for p in plates:
                label = f"Plate {p.plate_number}"
                if p.session:
                    label += f" ({p.session.batch_identifier})"
                plate_options.append({"value": str(p.id), "label": label})
            plate_values = []  # Default empty — user selects desired plates

            # Get completed analysis versions
            versions = AnalysisVersion.query.filter_by(
                project_id=project_id, status=AnalysisStatus.COMPLETED,
            ).order_by(AnalysisVersion.created_at.desc()).all()

            version_options = []
            default_version = None
            for v in versions:
                completed = v.completed_at.strftime("%Y-%m-%d %H:%M") if v.completed_at else ""
                label = f"{v.name}"
                if completed:
                    label += f" ({completed})"
                version_options.append({"value": str(v.id), "label": label})

            if versions:
                default_version = str(versions[0].id)

            # Get reaction setups for protocol selector
            setups = ReactionSetup.query.filter_by(
                project_id=project_id,
            ).order_by(ReactionSetup.created_at.desc()).all()

            setup_options = []
            default_setup = None
            for s in setups:
                created = s.created_at.strftime("%Y-%m-%d") if s.created_at else ""
                label = f"{s.name} ({created})" if created else s.name
                setup_options.append({"value": str(s.id), "label": label})

            if setups:
                default_setup = str(setups[0].id)

            return (
                plate_options, plate_values,
                version_options, default_version,
                setup_options, default_setup,
            )

        except Exception:
            logger.exception("Error populating report selectors")
            return [], [], [], None, [], None

    @app.callback(
        [
            Output("report-preview-content", "children"),
            Output("report-html-store", "data"),
            Output("report-download-btn", "disabled"),
        ],
        Input("report-generate-btn", "n_clicks"),
        [
            State("export-project-store", "data"),
            State("report-plate-select", "value"),
            State("report-version-select", "value"),
            State("report-protocol-select", "value"),
            State("report-include-curves", "checked"),
            State("report-include-fc", "checked"),
            State("report-include-hierarchical", "checked"),
            State("report-include-plate-layout", "checked"),
            State("report-include-qc", "checked"),
            State("report-include-protocol", "checked"),
            State("report-include-audit", "checked"),
        ],
        prevent_initial_call=True,
    )
    def generate_daily_report(
        n_clicks, project_id, selected_plates, selected_version, selected_protocol,
        inc_curves, inc_fc, inc_hier, inc_plate, inc_qc, inc_protocol, inc_audit,
    ):
        """Generate a daily report HTML document."""
        import dash_mantine_components as dmc
        from dash_iconify import DashIconify

        if not n_clicks or not project_id:
            raise PreventUpdate

        try:
            from app.services.daily_report_service import DailyReportService

            sections = {
                "curves": inc_curves,
                "fold_changes": inc_fc,
                "hierarchical": inc_hier,
                "plate_layout": inc_plate,
                "qc": inc_qc,
                "protocol": inc_protocol,
                "audit": inc_audit,
            }

            selected = [k for k, v in sections.items() if v]
            if not selected:
                return (
                    dmc.Alert(
                        "Please select at least one section.",
                        color="yellow",
                        icon=DashIconify(icon="mdi:alert"),
                    ),
                    no_update,
                    True,
                )

            # Plate-dependent sections need at least one plate selected
            plate_sections = {"curves", "fold_changes", "plate_layout", "qc"}
            needs_plates = plate_sections & set(selected)
            if needs_plates and not selected_plates:
                return (
                    dmc.Alert(
                        "Please select at least one plate for: "
                        + ", ".join(s.replace("_", " ").title() for s in sorted(needs_plates))
                        + ".",
                        color="yellow",
                        icon=DashIconify(icon="mdi:alert"),
                    ),
                    no_update,
                    True,
                )

            # Convert plate IDs to ints (or None for all)
            plate_ids = None
            if selected_plates:
                plate_ids = [int(pid) for pid in selected_plates]

            # Convert version ID to int (or None for latest)
            analysis_version_id = None
            if selected_version:
                analysis_version_id = int(selected_version)

            # Convert protocol setup ID to int (or None for latest)
            setup_id = None
            if selected_protocol:
                setup_id = int(selected_protocol)

            html_content = DailyReportService.generate_report(
                project_id, sections,
                plate_ids=plate_ids,
                analysis_version_id=analysis_version_id,
                setup_id=setup_id,
            )

            # Build preview summary
            size_kb = len(html_content.encode("utf-8")) / 1024
            plate_note = f"{len(plate_ids)} plates" if plate_ids else "all plates"
            preview = dmc.Stack([
                dmc.Alert(
                    "Report generated successfully!",
                    color="green",
                    icon=DashIconify(icon="mdi:check-circle"),
                ),
                dmc.Group([
                    dmc.Text(f"Sections: {len(selected)}", size="sm"),
                    dmc.Text(f"Size: {size_kb:.1f} KB", size="sm"),
                    dmc.Text(f"Plates: {plate_note}", size="sm"),
                ], gap="lg"),
                dmc.Text(
                    f"Included: {', '.join(s.replace('_', ' ').title() for s in selected)}",
                    size="sm", c="dimmed",
                ),
                dmc.Text(
                    "Click 'Download Report' to save as PDF.",
                    size="sm", c="dimmed",
                ),
            ], gap="sm")

            return preview, html_content, False

        except Exception as e:
            logger.exception("Error generating daily report")
            error_display = dmc.Alert(
                "Error generating report. Check server logs for details.",
                color="red",
                icon=DashIconify(icon="mdi:alert-circle"),
            )
            return error_display, no_update, True

    @app.callback(
        Output("report-download", "data"),
        Input("report-download-btn", "n_clicks"),
        [
            State("report-html-store", "data"),
            State("export-project-store", "data"),
            State("report-plate-select", "value"),
            State("report-version-select", "value"),
            State("report-protocol-select", "value"),
            State("report-include-curves", "checked"),
            State("report-include-fc", "checked"),
            State("report-include-hierarchical", "checked"),
            State("report-include-plate-layout", "checked"),
            State("report-include-qc", "checked"),
            State("report-include-protocol", "checked"),
            State("report-include-audit", "checked"),
        ],
        prevent_initial_call=True,
    )
    def download_daily_report(
        n_clicks, html_content, project_id,
        selected_plates, selected_version, selected_protocol,
        inc_curves, inc_fc, inc_hier, inc_plate, inc_qc, inc_protocol, inc_audit,
    ):
        """Download the generated daily report as PDF."""
        from dash import dcc
        from datetime import datetime

        if not n_clicks or not html_content or not project_id:
            raise PreventUpdate

        from app.models import Project
        project = Project.query.get(project_id)
        project_name = project.name if project else "project"

        import re
        slug = re.sub(r'[^a-zA-Z0-9]+', '_', project_name.lower()).strip('_')
        date_str = datetime.now().strftime("%Y%m%d")

        try:
            from app.services.daily_report_service import DailyReportService

            sections = {
                "curves": inc_curves,
                "fold_changes": inc_fc,
                "hierarchical": inc_hier,
                "plate_layout": inc_plate,
                "qc": inc_qc,
                "protocol": inc_protocol,
                "audit": inc_audit,
            }

            plate_ids = [int(p) for p in selected_plates] if selected_plates else None
            analysis_version_id = int(selected_version) if selected_version else None
            setup_id = int(selected_protocol) if selected_protocol else None

            pdf_bytes = DailyReportService.generate_pdf(
                project_id, sections,
                plate_ids=plate_ids,
                analysis_version_id=analysis_version_id,
                setup_id=setup_id,
            )

            filename = f"IVT_DailyReport_{slug}_{date_str}.pdf"
            return dcc.send_bytes(pdf_bytes, filename)

        except Exception:
            logger.exception("Error generating PDF, falling back to HTML download")
            filename = f"IVT_DailyReport_{slug}_{date_str}.html"
            return dcc.send_string(html_content, filename)
