"""Export service - backwards-compatible facade.

Phase 3: Service Layer Decomposition
This module maintains backward compatibility by delegating to specialized sub-services:
- ProtocolExportService: Protocol export (text, CSV, PDF)
- FigureExportService: Figure export (PNG, SVG, PDF)
- DataExportService: Data export (CSV, JSON, Excel) and publication data retrieval
"""
from app.services.protocol_export_service import ProtocolExportService
from app.services.figure_export_service import FigureExportService
from app.services.data_export_service import DataExportService


class ExportService:
    """Unified export service delegating to specialized sub-services."""

    # Protocol export methods
    export_protocol_text = ProtocolExportService.export_protocol_text
    export_protocol_csv = ProtocolExportService.export_protocol_csv
    export_protocol_pdf = ProtocolExportService.export_protocol_pdf
    _generate_pdf_reportlab = ProtocolExportService._generate_pdf_reportlab
    _generate_pdf_simple = ProtocolExportService._generate_pdf_simple

    # Figure export methods
    export_figure_png = FigureExportService.export_figure_png
    export_figure_svg = FigureExportService.export_figure_svg
    export_figure_pdf = FigureExportService.export_figure_pdf
    export_figures_combined_pdf = FigureExportService.export_figures_combined_pdf
    export_figures_separate_pdfs = FigureExportService.export_figures_separate_pdfs
    get_figure_dimensions = FigureExportService.get_figure_dimensions

    # Data export methods
    export_data_csv = DataExportService.export_data_csv
    export_data_json = DataExportService.export_data_json
    generate_filename = DataExportService.generate_filename
    export_excel_multisheet = DataExportService.export_excel_multisheet
    export_analysis_excel = DataExportService.export_analysis_excel
    export_json_archive = DataExportService.export_json_archive
    export_results_summary_csv = DataExportService.export_results_summary_csv
    export_plate_data_csv = DataExportService.export_plate_data_csv
    get_raw_data_for_export = DataExportService.get_raw_data_for_export
    get_results_for_export = DataExportService.get_results_for_export
    get_mcmc_traces_for_export = DataExportService.get_mcmc_traces_for_export
