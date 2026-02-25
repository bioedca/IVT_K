"""Figure export service for IVT Kinetics Analyzer.

Phase 3: Service Layer Decomposition
Handles figure export in multiple formats (PNG, SVG, PDF) including
single-figure and multi-figure combined exports.
Extracted from ExportService to follow single-responsibility principle.
"""
import logging
from typing import Optional, Dict, List, Any
from io import BytesIO

logger = logging.getLogger(__name__)


class FigureExportService:
    """Service for exporting Plotly figures as PNG, SVG, and PDF."""

    @staticmethod
    def export_figure_png(
        fig,
        width: int = 1200,
        height: int = 800,
        scale: float = 2.5,
    ) -> bytes:
        """
        Export Plotly figure as PNG at 300 DPI.

        Args:
            fig: Plotly figure object
            width: Image width in pixels
            height: Image height in pixels
            scale: Scale factor for resolution (2.5 = ~300 DPI for screen)

        Returns:
            PNG bytes
        """
        try:
            return fig.to_image(
                format="png",
                width=width,
                height=height,
                scale=scale,
            )
        except Exception as e:
            raise RuntimeError(
                f"PNG export failed: {e}. Ensure kaleido and Chrome are installed."
            )

    @staticmethod
    def export_figure_svg(
        fig,
        width: int = 1200,
        height: int = 800,
    ) -> str:
        """
        Export Plotly figure as SVG (vector format).

        Args:
            fig: Plotly figure object
            width: Image width in pixels
            height: Image height in pixels

        Returns:
            SVG string
        """
        try:
            svg_bytes = fig.to_image(
                format="svg",
                width=width,
                height=height,
            )
            return svg_bytes.decode("utf-8")
        except Exception as e:
            raise RuntimeError(
                f"SVG export failed: {e}. Ensure kaleido and Chrome are installed."
            )

    @staticmethod
    def export_figure_pdf(
        fig,
        width: int = 1200,
        height: int = 800,
    ) -> bytes:
        """
        Export Plotly figure as PDF.

        Args:
            fig: Plotly figure object
            width: Image width in pixels
            height: Image height in pixels

        Returns:
            PDF bytes
        """
        try:
            return fig.to_image(
                format="pdf",
                width=width,
                height=height,
            )
        except Exception as e:
            raise RuntimeError(
                f"PDF export failed: {e}. Ensure kaleido and Chrome are installed."
            )

    @staticmethod
    def export_figures_combined_pdf(
        figures: List[Any],
        titles: Optional[List[str]] = None,
    ) -> bytes:
        """
        Export multiple figures to a single PDF.

        Args:
            figures: List of Plotly figure objects
            titles: Optional titles for each figure

        Returns:
            Combined PDF bytes
        """
        if not figures:
            return b""

        try:
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.platypus import SimpleDocTemplate, Image, Spacer, Paragraph, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch
            import tempfile
            import os

            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=landscape(letter),
                rightMargin=36,
                leftMargin=36,
                topMargin=36,
                bottomMargin=36,
            )

            styles = getSampleStyleSheet()
            story = []

            for i, fig in enumerate(figures):
                # Add title if provided
                if titles and i < len(titles):
                    story.append(Paragraph(titles[i], styles['Heading2']))
                    story.append(Spacer(1, 12))

                # Export figure to temporary PNG
                png_bytes = FigureExportService.export_figure_png(fig, width=900, height=600, scale=2)

                # Write to temp file (reportlab needs file path)
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(png_bytes)
                    tmp_path = tmp.name

                try:
                    # Add image to PDF
                    img = Image(tmp_path, width=9*inch, height=6*inch)
                    story.append(img)
                finally:
                    # Clean up temp file
                    os.unlink(tmp_path)

                # Page break between figures (except last)
                if i < len(figures) - 1:
                    story.append(PageBreak())

            doc.build(story)
            buffer.seek(0)
            return buffer.read()

        except ImportError:
            # Fallback: export first figure only as PDF
            logger.warning(
                "reportlab not available for combined PDF export; "
                "falling back to single-figure PDF"
            )
            if figures:
                return FigureExportService.export_figure_pdf(figures[0])
            return b""

    @staticmethod
    def export_figures_separate_pdfs(
        figures: List[Any],
        base_filename: str = "figure",
    ) -> Dict[str, bytes]:
        """
        Export each figure as a separate PDF.

        Args:
            figures: List of Plotly figure objects
            base_filename: Base name for files

        Returns:
            Dict mapping filename to PDF bytes
        """
        result = {}
        for i, fig in enumerate(figures):
            filename = f"{base_filename}_{i+1:02d}.pdf"
            try:
                pdf_bytes = FigureExportService.export_figure_pdf(fig)
                result[filename] = pdf_bytes
            except Exception as e:
                logger.error(f"Failed to export {filename}: {e}")
        return result

    @staticmethod
    def get_figure_dimensions(
        fig,
    ) -> Dict[str, int]:
        """
        Get current figure dimensions.

        Args:
            fig: Plotly figure object

        Returns:
            Dict with width, height
        """
        layout = fig.layout
        return {
            "width": layout.width or 700,
            "height": layout.height or 450,
        }
