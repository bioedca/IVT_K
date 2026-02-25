"""Protocol export service for IVT Kinetics Analyzer.

Phase 3: Service Layer Decomposition
Handles protocol export in multiple formats (text, CSV, PDF).
Extracted from ExportService to follow single-responsibility principle.
"""
from io import BytesIO

from app.calculator import PipettingProtocol, format_protocol_text, format_protocol_csv


class ProtocolExportService:
    """Service for exporting pipetting protocols in text, CSV, and PDF formats."""

    @staticmethod
    def export_protocol_text(protocol: PipettingProtocol) -> str:
        """
        Export protocol as plain text.

        Args:
            protocol: PipettingProtocol to export

        Returns:
            Formatted text string
        """
        return format_protocol_text(protocol)

    @staticmethod
    def export_protocol_csv(protocol: PipettingProtocol) -> str:
        """
        Export protocol as CSV.

        Args:
            protocol: PipettingProtocol to export

        Returns:
            CSV string
        """
        return format_protocol_csv(protocol)

    @staticmethod
    def export_protocol_pdf(
        protocol: PipettingProtocol,
        include_summary: bool = True,
    ) -> bytes:
        """
        Export protocol as PDF.

        Uses basic PDF generation if reportlab is available,
        otherwise falls back to text-based PDF.

        Args:
            protocol: PipettingProtocol to export
            include_summary: Whether to include experiment summary

        Returns:
            PDF bytes
        """
        try:
            import importlib.util
            if importlib.util.find_spec("reportlab") is None:
                raise ImportError("reportlab not installed")

            return ProtocolExportService._generate_pdf_reportlab(
                protocol, include_summary
            )
        except ImportError:
            # Fallback to simple text-based PDF
            return ProtocolExportService._generate_pdf_simple(protocol)

    @staticmethod
    def _generate_pdf_reportlab(
        protocol: PipettingProtocol,
        include_summary: bool,
    ) -> bytes:
        """Generate PDF using reportlab library."""
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        )
        from reportlab.lib import colors

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
        )

        styles = getSampleStyleSheet()
        story = []

        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=12,
        )
        story.append(Paragraph(protocol.title, title_style))

        # Metadata
        meta_style = styles['Normal']
        story.append(Paragraph(
            f"Created: {protocol.created_at.strftime('%Y-%m-%d %H:%M')}",
            meta_style
        ))
        if protocol.created_by:
            story.append(Paragraph(f"Created by: {protocol.created_by}", meta_style))
        if protocol.project_name:
            story.append(Paragraph(f"Project: {protocol.project_name}", meta_style))
        if protocol.session_name:
            story.append(Paragraph(f"Session: {protocol.session_name}", meta_style))

        story.append(Spacer(1, 12))

        # Summary section
        if include_summary:
            story.append(Paragraph("Experiment Summary", styles['Heading2']))

            calc = protocol.calculation
            summary_data = [
                ["Parameter", "Value"],
                ["Number of reactions", str(calc.n_reactions)],
                ["Reaction volume", f"{calc.single_reaction.reaction_volume_ul:.1f} \u00b5L"],
                ["Overage", f"{(calc.overage_factor - 1) * 100:.0f}%"],
                ["Master mix per tube", f"{calc.master_mix_per_tube_ul:.2f} \u00b5L"],
            ]

            summary_table = Table(summary_data, colWidths=[2.5*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 12))

        # Master Mix Table
        story.append(Paragraph("Master Mix Components", styles['Heading2']))

        mm_data = [["Component", "Stock", "Per Rxn (\u00b5L)", "Total (\u00b5L)"]]
        for comp in protocol.calculation.components:
            mm_data.append([
                comp.name,
                f"{comp.stock_concentration} {comp.stock_unit}" if comp.stock_concentration > 0 else "-",
                f"{comp.single_reaction_volume_ul:.2f}",
                f"{comp.master_mix_volume_ul:.2f}",
            ])

        mm_table = Table(mm_data, colWidths=[2*inch, 1.25*inch, 1.25*inch, 1.25*inch])
        mm_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
        ]))
        story.append(mm_table)
        story.append(Spacer(1, 12))

        # Protocol Steps
        story.append(Paragraph("Step-by-Step Protocol", styles['Heading2']))

        current_section = ""
        for step in protocol.steps:
            if step.section != current_section:
                current_section = step.section
                story.append(Spacer(1, 6))
                story.append(Paragraph(
                    f"<b>{current_section}</b>",
                    styles['Normal']
                ))
                story.append(Spacer(1, 4))

            step_text = f"{step.step_number}. {step.action}"
            if step.volume_ul and step.volume_ul > 0:
                step_text += f": {step.volume_ul:.2f} \u00b5L"
            if step.component:
                step_text += f" {step.component}"
            if step.destination:
                step_text += f" \u2192 {step.destination}"

            story.append(Paragraph(step_text, styles['Normal']))

            if step.notes:
                story.append(Paragraph(
                    f"    <i>({step.notes})</i>",
                    styles['Normal']
                ))

        story.append(Spacer(1, 12))

        # Notes
        if protocol.notes:
            story.append(Paragraph("Notes", styles['Heading2']))
            for note in protocol.notes:
                story.append(Paragraph(f"\u2022 {note}", styles['Normal']))
            story.append(Spacer(1, 12))

        # Warnings
        if protocol.warnings:
            story.append(Paragraph("Warnings", styles['Heading2']))
            for warning in protocol.warnings:
                story.append(Paragraph(
                    f"\u26a0 {warning}",
                    ParagraphStyle('Warning', parent=styles['Normal'], textColor=colors.red)
                ))

        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.read()

    @staticmethod
    def _generate_pdf_simple(protocol: PipettingProtocol) -> bytes:
        """
        Generate simple PDF from text (fallback when reportlab not available).

        This creates a basic text file with .pdf extension.
        Not a true PDF but allows the export to proceed.
        """
        text = format_protocol_text(protocol)
        return text.encode('utf-8')
