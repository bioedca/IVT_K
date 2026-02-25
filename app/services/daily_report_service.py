"""
Daily report service for IVT Kinetics Analyzer.

Phase 9.6: Generates self-contained HTML daily reports with interactive charts.

Sections:
- Curve fits with data + fit overlay
- Fold change summary table
- Hierarchical analysis results with forest plot
- Plate layout visualization
- QC summary of flagged/excluded wells
- Calculator protocol
- Audit trail with change diffs
"""
from typing import Dict, List, Optional
from datetime import datetime
from html import escape
import base64
import logging

from app.models.enums import FoldChangeCategory, LigandCondition

logger = logging.getLogger(__name__)


def _esc(value) -> str:
    """Escape a value for safe HTML embedding. Handles None and non-string types."""
    if value is None:
        return "-"
    return escape(str(value))


def _fmt(value, fmt_spec: str, fallback: str = "-") -> str:
    """Format a numeric value with a format spec, returning fallback if None."""
    if value is None:
        return fallback
    try:
        return format(value, fmt_spec)
    except (TypeError, ValueError):
        return fallback


def _fig_to_static_img(fig, width: int = 900, height: int = 450) -> str:
    """Convert a Plotly figure to a base64-encoded PNG <img> tag for PDF rendering."""
    try:
        png_bytes = fig.to_image(format="png", width=width, height=height, scale=2)
        b64 = base64.b64encode(png_bytes).decode("ascii")
        return (
            f'<img src="data:image/png;base64,{b64}" '
            f'style="width:100%; max-width:{width}px;" />'
        )
    except Exception:
        logger.debug("Failed to render static image from Plotly figure", exc_info=True)
        return '<p class="empty-note">Chart could not be rendered as image.</p>'


class DailyReportService:
    """Service for generating self-contained HTML daily reports."""

    MAX_TOTAL_CURVES = 20

    @staticmethod
    def generate_report(
        project_id: int,
        sections: Dict[str, bool],
        plate_ids: List[int] = None,
        analysis_version_id: int = None,
        setup_id: int = None,
        render_static: bool = False,
    ) -> str:
        """
        Generate a self-contained HTML daily report.

        Args:
            project_id: Project ID
            sections: Dict of section_name -> include_bool
            plate_ids: Optional list of plate IDs to include (None = all)
            analysis_version_id: Optional analysis version ID (None = latest)
            setup_id: Optional reaction setup ID (None = latest)
            render_static: If True, render Plotly charts as static PNG images
                           (required for PDF conversion)

        Returns:
            Complete HTML string
        """
        from app.models import Project

        project = Project.query.get(project_id)
        if not project:
            return DailyReportService._build_html_wrapper(
                "Report Error", datetime.now().strftime("%Y-%m-%d %H:%M"),
                ["<p>Project not found.</p>"], [],
            )

        title = f"Daily Report - {_esc(project.name)}"
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        section_html = []
        toc_entries = []
        plotlyjs_included = False

        if sections.get("curves"):
            html, had_plots = DailyReportService._generate_curves_section(
                project_id, not plotlyjs_included, plate_ids=plate_ids,
                render_static=render_static,
            )
            if html:
                toc_entries.append(("curves", "Curve Fits"))
                section_html.append(html)
                if had_plots:
                    plotlyjs_included = True

        if sections.get("fold_changes"):
            html = DailyReportService._generate_fold_change_section(
                project_id, plate_ids=plate_ids,
            )
            if html:
                toc_entries.append(("fold-changes", "Fold Changes"))
                section_html.append(html)

        if sections.get("hierarchical"):
            html, had_plots = DailyReportService._generate_hierarchical_section(
                project_id, not plotlyjs_included,
                analysis_version_id=analysis_version_id,
                render_static=render_static,
            )
            if html:
                toc_entries.append(("hierarchical", "Hierarchical Results"))
                section_html.append(html)
                if had_plots:
                    plotlyjs_included = True

        if sections.get("plate_layout"):
            html, had_plots = DailyReportService._generate_plate_layout_section(
                project_id, not plotlyjs_included, plate_ids=plate_ids,
                render_static=render_static,
            )
            if html:
                toc_entries.append(("plate-layout", "Plate Layout"))
                section_html.append(html)
                if had_plots:
                    plotlyjs_included = True

        if sections.get("qc"):
            html = DailyReportService._generate_qc_section(
                project_id, plate_ids=plate_ids,
            )
            if html:
                toc_entries.append(("qc-summary", "QC Summary"))
                section_html.append(html)

        if sections.get("protocol"):
            html = DailyReportService._generate_protocol_section(
                project_id, setup_id=setup_id,
            )
            if html:
                toc_entries.append(("protocol", "Protocol"))
                section_html.append(html)

        if sections.get("audit"):
            html = DailyReportService._generate_audit_section(project_id)
            if html:
                toc_entries.append(("audit-trail", "Audit Trail"))
                section_html.append(html)

        if not section_html:
            section_html.append(
                '<div class="section"><p>No data available for the selected sections.</p></div>'
            )

        return DailyReportService._build_html_wrapper(
            title, generated_at, section_html, toc_entries,
        )

    @staticmethod
    def generate_pdf(
        project_id: int,
        sections: Dict[str, bool],
        plate_ids: List[int] = None,
        analysis_version_id: int = None,
        setup_id: int = None,
    ) -> bytes:
        """
        Generate a PDF daily report.

        Renders charts as static images and converts the HTML to PDF
        via weasyprint.

        Returns:
            PDF file contents as bytes
        """
        html_content = DailyReportService.generate_report(
            project_id, sections,
            plate_ids=plate_ids,
            analysis_version_id=analysis_version_id,
            setup_id=setup_id,
            render_static=True,
        )

        import weasyprint
        pdf_bytes = weasyprint.HTML(
            string=html_content, media_type='screen',
        ).write_pdf()
        return pdf_bytes

    @staticmethod
    def _build_html_wrapper(
        title: str,
        generated_at: str,
        section_html: List[str],
        toc_entries: List[tuple],
    ) -> str:
        """Build complete HTML document with inline CSS."""
        toc_html = ""
        if toc_entries:
            toc_items = "".join(
                f'<li><a href="#{_esc(anchor)}">{_esc(label)}</a></li>'
                for anchor, label in toc_entries
            )
            toc_html = f"""
            <nav class="toc">
                <h3>Contents</h3>
                <ol>{toc_items}</ol>
            </nav>"""

        sections_joined = "\n".join(section_html)
        # title is already escaped by the caller
        esc_title = _esc(title) if "&" not in title and "<" not in title else title

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc_title}</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        line-height: 1.6;
        color: #333;
        max-width: 1100px;
        margin: 0 auto;
        padding: 24px;
        background: #fafafa;
    }}
    .header {{
        background: linear-gradient(135deg, #1a73e8, #0d47a1);
        color: white;
        padding: 24px 32px;
        border-radius: 8px;
        margin-bottom: 24px;
    }}
    .header h1 {{ font-size: 1.6em; margin-bottom: 4px; }}
    .header .meta {{ opacity: 0.85; font-size: 0.9em; }}
    .toc {{
        background: #fff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 16px 24px;
        margin-bottom: 24px;
    }}
    .toc h3 {{ font-size: 1em; margin-bottom: 8px; color: #555; }}
    .toc ol {{ padding-left: 20px; }}
    .toc li {{ margin-bottom: 4px; }}
    .toc a {{ color: #1a73e8; text-decoration: none; }}
    .toc a:hover {{ text-decoration: underline; }}
    .section {{
        background: #fff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 24px;
        margin-bottom: 20px;
    }}
    .section h2 {{
        font-size: 1.3em;
        color: #1a73e8;
        border-bottom: 2px solid #e3f2fd;
        padding-bottom: 8px;
        margin-bottom: 16px;
    }}
    .section h3 {{ font-size: 1.1em; color: #444; margin: 16px 0 8px; }}
    table {{
        width: 100%;
        border-collapse: collapse;
        margin: 12px 0;
        font-size: 0.85em;
        table-layout: auto;
        word-wrap: break-word;
        overflow-wrap: break-word;
    }}
    th, td {{
        padding: 8px 10px;
        text-align: left;
        border-bottom: 1px solid #e0e0e0;
        overflow-wrap: break-word;
        word-break: break-word;
    }}
    th {{
        background: #f5f5f5;
        font-weight: 600;
        color: #555;
    }}
    tr:hover {{ background: #fafafa; }}
    .hierarchical-table th, .hierarchical-table td {{
        padding: 6px 8px;
        font-size: 0.92em;
    }}
    .hierarchical-table {{ font-size: 0.82em; }}
    .badge {{
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8em;
        font-weight: 500;
    }}
    .badge-green {{ background: #e8f5e9; color: #2e7d32; }}
    .badge-yellow {{ background: #fff8e1; color: #f57f17; }}
    .badge-red {{ background: #ffebee; color: #c62828; }}
    .badge-blue {{ background: #e3f2fd; color: #1565c0; }}
    .badge-gray {{ background: #f5f5f5; color: #616161; }}
    .badge-teal {{ background: #e0f2f1; color: #00695c; }}
    .badge-orange {{ background: #fff3e0; color: #e65100; }}
    .badge-violet {{ background: #f3e5f5; color: #7b1fa2; }}
    .stat-grid {{
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin-bottom: 16px;
    }}
    .stat-card {{
        flex: 1 1 120px;
        min-width: 100px;
        max-width: 200px;
        background: #f8f9fa;
        border-radius: 6px;
        padding: 12px;
        text-align: center;
    }}
    .stat-card .value {{ font-size: 1.5em; font-weight: 700; color: #1a73e8; }}
    .stat-card .label {{ font-size: 0.8em; color: #666; }}
    .plot-container {{ margin: 12px 0; }}
    .plot-container img {{ max-width: 100%; height: auto; }}
    .change-diff {{
        font-family: monospace;
        font-size: 0.85em;
        padding: 4px 8px;
        background: #f5f5f5;
        border-radius: 4px;
        margin: 2px 0;
        overflow-wrap: break-word;
        word-break: break-word;
    }}
    .audit-table {{
        table-layout: fixed;
    }}
    .audit-table td, .audit-table th {{
        overflow-wrap: break-word;
        word-break: break-word;
    }}
    .change-old {{ color: #c62828; text-decoration: line-through; }}
    .change-new {{ color: #2e7d32; font-weight: 500; }}
    .empty-note {{ color: #999; font-style: italic; padding: 16px; text-align: center; }}
    .protocol-step {{
        margin: 3px 0;
        padding: 2px 0;
        font-size: 0.9em;
    }}
    .protocol-step .step-num {{
        font-weight: 600;
        color: #1a73e8;
        display: inline-block;
        min-width: 28px;
    }}
    .protocol-step .step-note {{
        color: #666;
        font-style: italic;
        margin-left: 28px;
        font-size: 0.92em;
    }}
    .protocol-section-title {{
        font-weight: 600;
        color: #1a73e8;
        margin: 14px 0 6px;
        padding: 4px 0;
        border-bottom: 1px solid #e3f2fd;
    }}
    /* --- Print / PDF pagination rules --- */
    @media print {{
        body {{ background: white; padding: 0; }}
        .section {{ border: 1px solid #ccc; }}
        .header {{ background: #1a73e8 !important; -webkit-print-color-adjust: exact; }}
    }}
    @page {{
        size: A4 portrait;
        margin: 1.8cm 1.5cm;
    }}
    /* Page-break rules are in global scope (not @media print) because
       WeasyPrint renders with media_type='screen'. Browsers ignore
       page-break properties for screen display. */

    /* Each major section starts on a new page */
    .section {{
        page-break-before: always;
        page-break-inside: auto;
    }}
    /* First section (after header or TOC) stays on page 1 */
    .toc + .section,
    .header + .section {{
        page-break-before: auto;
    }}
    /* Keep section headings with following content */
    .section h2, .section h3 {{
        page-break-after: avoid;
    }}
    /* Keep stat cards together */
    .stat-grid {{
        page-break-inside: avoid;
    }}
    /* Keep individual table rows together */
    tr {{
        page-break-inside: avoid;
    }}
    /* Keep plot with its caption/title */
    .plot-container {{
        page-break-inside: avoid;
    }}
    /* Keep TOC on first page with header */
    .toc {{
        page-break-inside: avoid;
        page-break-after: auto;
    }}
    .header {{
        page-break-after: avoid;
    }}
</style>
</head>
<body>
<div class="header">
    <h1>{esc_title}</h1>
    <div class="meta">Generated: {_esc(generated_at)}</div>
</div>
{toc_html}
{sections_joined}
<div style="text-align:center; color:#999; font-size:0.8em; margin-top:24px; padding:12px;">
    Generated by IVT Kinetics Analyzer
</div>
</body>
</html>"""

    @staticmethod
    def _generate_curves_section(
        project_id: int, include_plotlyjs: bool, plate_ids: List[int] = None,
        render_static: bool = False,
    ) -> tuple:
        """Generate curve fits section with per-plate overlay plots.

        Returns (html_str, had_plotly_plots).
        """
        from app.models import (
            Plate, Well, FitResult, ExperimentalSession,
        )

        # Base query for fits, optionally filtered by plate
        base_q = FitResult.query.join(Well).join(Plate).join(
            ExperimentalSession
        ).filter(ExperimentalSession.project_id == project_id)
        if plate_ids:
            base_q = base_q.filter(Plate.id.in_(plate_ids))

        # Summary stats
        total = base_q.count()
        if total == 0:
            return (
                '<div class="section" id="curves">'
                '<h2>Curve Fits</h2>'
                '<p class="empty-note">No curve fits available.</p></div>',
                False,
            )

        good = base_q.filter(FitResult.r_squared >= 0.9).count()
        acceptable = base_q.filter(
            FitResult.r_squared >= 0.8, FitResult.r_squared < 0.9,
        ).count()
        poor = total - good - acceptable

        stats_html = f"""
        <div class="stat-grid">
            <div class="stat-card">
                <div class="value">{total}</div>
                <div class="label">Total Fits</div>
            </div>
            <div class="stat-card">
                <div class="value" style="color:#2e7d32">{good}</div>
                <div class="label">Good (R2 &gt;= 0.9)</div>
            </div>
            <div class="stat-card">
                <div class="value" style="color:#f57f17">{acceptable}</div>
                <div class="label">Acceptable</div>
            </div>
            <div class="stat-card">
                <div class="value" style="color:#c62828">{poor}</div>
                <div class="label">Poor (R2 &lt; 0.8)</div>
            </div>
        </div>"""

        # Get plates to iterate over
        plate_q = Plate.query.join(ExperimentalSession).filter(
            ExperimentalSession.project_id == project_id,
        )
        if plate_ids:
            plate_q = plate_q.filter(Plate.id.in_(plate_ids))
        plates = plate_q.order_by(Plate.plate_number).all()

        had_plots = False
        plots_html = []
        all_fit_rows = []

        # Color palette matching create_overlay_plot
        colors = [
            "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
            "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
        ]

        for plate in plates:
            # Get converged fits for this plate
            plate_fits = FitResult.query.join(Well).filter(
                Well.plate_id == plate.id,
                FitResult.converged.is_(True),
            ).order_by(FitResult.r_squared.desc()).all()

            if not plate_fits:
                continue

            # Build per-(construct, ligand) color mapping so +Lig/-Lig
            # wells of the same construct get distinct colors.
            trace_color = {}
            color_idx = 0
            for fit in plate_fits:
                w = fit.well
                if not w:
                    continue
                key = (w.construct_id or 0, w.ligand_condition or "")
                if key not in trace_color:
                    trace_color[key] = colors[color_idx % len(colors)]
                    color_idx += 1

            # Build overlay figure for this plate
            try:
                import plotly.graph_objects as go
                from app.components.curve_plot import compute_fit_curve
                import numpy as np

                fig = go.Figure()
                # Track which constructs already have a legend entry
                legend_shown = set()
                for fit in plate_fits:
                    w = fit.well
                    if not w or not w.raw_data:
                        continue

                    times = sorted([p.timepoint for p in w.raw_data])
                    fluor = [p.fluorescence_raw for p in
                             sorted(w.raw_data, key=lambda p: p.timepoint)]
                    color_key = (w.construct_id or 0, w.ligand_condition or "")
                    color = trace_color.get(color_key, "#999999")
                    construct_name = w.construct.identifier if w.construct else "Unknown"

                    # Build legend label condensed by construct + ligand condition
                    lig = w.ligand_condition or ""
                    legend_key = f"{construct_name} {lig}".strip()
                    show_in_legend = legend_key not in legend_shown
                    if show_in_legend:
                        legend_shown.add(legend_key)

                    # Raw data points
                    fig.add_trace(go.Scatter(
                        x=times, y=fluor, mode="markers",
                        name=legend_key,
                        marker=dict(color=color, size=5, opacity=0.7),
                        legendgroup=legend_key,
                        showlegend=show_in_legend,
                    ))

                    # Fit curve (smooth line)
                    if times:
                        t_smooth = np.linspace(min(times), max(times), 200).tolist()
                        fit_vals = compute_fit_curve(
                            t_smooth,
                            k_obs=fit.k_obs,
                            F_max=fit.f_max,
                            t_lag=fit.t_lag or 0.0,
                            F_0=fit.f_baseline or 0.0,
                        )
                        fig.add_trace(go.Scatter(
                            x=t_smooth, y=fit_vals, mode="lines",
                            name=legend_key,
                            line=dict(color=color, width=2),
                            legendgroup=legend_key,
                            showlegend=False,
                        ))

                plate_name = f"Plate {plate.plate_number}"
                session = plate.session
                if session:
                    plate_name += f" ({session.batch_identifier})"

                fig.update_layout(
                    template="simple_white",
                    title=dict(text=f"{plate_name} — Kinetic Curves", x=0.5),
                    xaxis_title="Time (min)",
                    yaxis_title="Fluorescence (RFU)",
                    showlegend=True,
                    legend=dict(
                        orientation="v",
                        yanchor="top", y=1.0,
                        xanchor="left", x=1.02,
                        font=dict(size=10),
                        bgcolor="rgba(255,255,255,0.9)",
                        tracegroupgap=2,
                    ),
                    height=450,
                    margin=dict(l=60, r=180, t=50, b=40),
                    hovermode="x unified",
                )

                if render_static:
                    plot_html = _fig_to_static_img(fig, width=900, height=450)
                else:
                    js_setting = True if (include_plotlyjs and not had_plots) else False
                    plot_html = fig.to_html(
                        full_html=False, include_plotlyjs=js_setting,
                    )
                plots_html.append(f'<div class="plot-container">{plot_html}</div>')
                had_plots = True

            except Exception:
                plots_html.append(f'<h3>Plate {plate.plate_number}</h3>'
                                  '<p class="empty-note">Could not render plot.</p>')

            # Collect table rows for this plate's fits
            for fit in plate_fits:
                w = fit.well
                if not w:
                    continue
                construct_name = _esc(w.construct.identifier) if w.construct else "-"
                r2_class = "badge-green" if (fit.r_squared or 0) >= 0.9 else (
                    "badge-yellow" if (fit.r_squared or 0) >= 0.8 else "badge-red"
                )
                all_fit_rows.append(
                    f"<tr><td>Plate {plate.plate_number}</td>"
                    f"<td>{_esc(w.position)}</td><td>{construct_name}</td>"
                    f"<td>{_fmt(fit.k_obs, '.4f')}</td><td>{_fmt(fit.f_max, '.1f')}</td>"
                    f"<td>{_fmt(fit.t_lag, '.2f', '0.00')}</td>"
                    f'<td><span class="badge {r2_class}">{_fmt(fit.r_squared, ".3f")}</span></td></tr>'
                )

        table_html = """
        <h3>Fitted Parameters</h3>
        <table>
            <thead><tr>
                <th>Plate</th><th>Well</th><th>Construct</th><th>k_obs</th>
                <th>F_max</th><th>t_lag</th><th>R2</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>""".format(rows="\n".join(all_fit_rows))

        return (
            f'<div class="section" id="curves"><h2>Curve Fits</h2>'
            f'{stats_html}{"".join(plots_html)}{table_html}</div>',
            had_plots,
        )

    @staticmethod
    def _generate_fold_change_section(
        project_id: int, plate_ids: List[int] = None,
    ) -> str:
        """Generate aggregated fold change summary table.

        Groups fold changes by (construct, comparison_type, ligand_condition)
        and shows N pairs with mean +/- SD — matching the analysis interface.
        """
        import statistics
        from sqlalchemy.orm import aliased
        from app.models import (
            Plate, Well, Construct, FoldChange, ExperimentalSession,
        )

        TestWell = aliased(Well, name="test_well")
        TestPlate = aliased(Plate, name="test_plate")
        TestSession = aliased(ExperimentalSession, name="test_session")

        fc_q = (
            FoldChange.query
            .join(TestWell, FoldChange.test_well_id == TestWell.id)
            .join(TestPlate, TestWell.plate_id == TestPlate.id)
            .join(TestSession, TestPlate.session_id == TestSession.id)
            .filter(TestSession.project_id == project_id)
        )
        if plate_ids:
            fc_q = fc_q.filter(TestPlate.id.in_(plate_ids))
        fcs = fc_q.all()

        if not fcs:
            return (
                '<div class="section" id="fold-changes">'
                '<h2>Fold Changes</h2>'
                '<p class="empty-note">No fold change data available.</p></div>'
            )

        # Batch-load constructs for display names
        cids = set()
        for fc in fcs:
            if fc.test_well and fc.test_well.construct_id:
                cids.add(fc.test_well.construct_id)
        constructs_by_id = {
            c.id: c for c in Construct.query.filter(Construct.id.in_(cids)).all()
        } if cids else {}

        # Derive comparison type label from construct properties + fc.comparison_type
        def _comp_label(fc_obj):
            if fc_obj.comparison_type == FoldChangeCategory.LIGAND_EFFECT:
                return "Ligand Effect"
            tc = constructs_by_id.get(
                fc_obj.test_well.construct_id if fc_obj.test_well else None
            )
            if tc and tc.is_wildtype:
                return "WT \u2192 Unreg"
            if tc and not tc.is_wildtype and not tc.is_unregulated:
                return "Mutant \u2192 WT"
            return "Other"

        # Group by (construct_name, comparison_type_label, ligand_condition,
        #           fc.comparison_type enum value)
        groups: Dict[tuple, list] = {}
        for fc in fcs:
            tw = fc.test_well
            tc = constructs_by_id.get(tw.construct_id if tw else None)
            name = tc.identifier if tc else "Unknown"
            comp = _comp_label(fc)
            groups.setdefault((name, comp, fc.ligand_condition, fc.comparison_type), []).append(fc)

        has_ligand = any(fc.ligand_condition for fc in fcs)

        # Sort: Mutant→WT first, then WT→Unreg, then Ligand Effect
        type_order = {"Mutant \u2192 WT": 0, "WT \u2192 Unreg": 1, "Ligand Effect": 2}
        sorted_keys = sorted(groups.keys(), key=lambda k: (type_order.get(k[1], 9), k[0]))

        def _mean_sd(vals, decimals=2):
            if not vals:
                return "\u2014"
            m = statistics.mean(vals)
            fmt = f".{decimals}f"
            if len(vals) >= 2:
                sd = statistics.stdev(vals)
                return f"{m:{fmt}} \u00b1 {sd:{fmt}}"
            return f"{m:{fmt}}"

        rows = []
        total_pairs = 0
        for key in sorted_keys:
            construct_name, comp_type, ligand_cond, fc_comp_type = key
            group = groups[key]
            n = len(group)
            total_pairs += n

            fmax_vals = [fc.fc_fmax for fc in group if fc.fc_fmax is not None]
            kobs_vals = [fc.fc_kobs for fc in group if fc.fc_kobs is not None]
            tlag_vals = [fc.delta_tlag for fc in group if fc.delta_tlag is not None]

            # Comparison type badge
            if comp_type == "Mutant \u2192 WT":
                type_badge = '<span class="badge badge-blue">Mutant \u2192 WT</span>'
            elif comp_type == "WT \u2192 Unreg":
                type_badge = '<span class="badge badge-green">WT \u2192 Unreg</span>'
            elif comp_type == "Ligand Effect":
                type_badge = '<span class="badge badge-violet">Ligand Effect</span>'
            else:
                type_badge = _esc(comp_type)

            # Ligand condition badge
            lig_cell = ""
            if has_ligand:
                if fc_comp_type == FoldChangeCategory.LIGAND_EFFECT:
                    lig_cell = '<td><span class="badge badge-violet">+Lig/-Lig</span></td>'
                elif ligand_cond == LigandCondition.PLUS_LIG:
                    lig_cell = '<td><span class="badge badge-teal">+Lig</span></td>'
                elif ligand_cond == LigandCondition.MINUS_LIG:
                    lig_cell = '<td><span class="badge badge-orange">-Lig</span></td>'
                else:
                    lig_cell = "<td>\u2014</td>"

            rows.append(
                f"<tr><td>{_esc(construct_name)}</td>"
                f"<td>{type_badge}</td>"
                f"<td>{n}</td>"
                f"{lig_cell}"
                f"<td>{_mean_sd(fmax_vals)}</td>"
                f"<td>{_mean_sd(kobs_vals)}</td>"
                f"<td>{_mean_sd(tlag_vals, decimals=1)}</td></tr>"
            )

        # Stats summary cards
        mutant_wt = sum(
            len(g) for k, g in groups.items() if k[1] == "Mutant \u2192 WT"
        )
        wt_unreg = sum(
            len(g) for k, g in groups.items() if k[1] == "WT \u2192 Unreg"
        )
        stats_html = f"""
        <div class="stat-grid">
            <div class="stat-card">
                <div class="value">{mutant_wt}</div>
                <div class="label">Mutant \u2192 WT Pairs</div>
            </div>
            <div class="stat-card">
                <div class="value">{wt_unreg}</div>
                <div class="label">WT \u2192 Unreg Pairs</div>
            </div>
            <div class="stat-card">
                <div class="value">{total_pairs}</div>
                <div class="label">Total FC Records</div>
            </div>
        </div>"""

        # Build header
        cond_th = "<th>Condition</th>" if has_ligand else ""
        table_html = f"""
        <table>
            <thead><tr>
                <th>Construct</th><th>Type</th><th>N pairs</th>
                {cond_th}
                <th>FC_Fmax (mean \u00b1 SD)</th>
                <th>FC_kobs (mean \u00b1 SD)</th>
                <th>\u0394t_lag (mean \u00b1 SD)</th>
            </tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table>"""

        return (
            f'<div class="section" id="fold-changes"><h2>Fold Changes</h2>'
            f'{stats_html}{table_html}</div>'
        )

    @staticmethod
    def _generate_hierarchical_section(
        project_id: int, include_plotlyjs: bool,
        analysis_version_id: int = None,
        render_static: bool = False,
    ) -> tuple:
        """Generate hierarchical results section. Returns (html_str, had_plots)."""
        from app.models.analysis_version import (
            AnalysisVersion, HierarchicalResult, AnalysisStatus,
        )
        from app.models import Construct

        if analysis_version_id:
            latest_version = AnalysisVersion.query.filter_by(
                id=analysis_version_id,
                project_id=project_id,
                status=AnalysisStatus.COMPLETED,
            ).first()
            if not latest_version:
                return (
                    '<div class="section" id="hierarchical">'
                    '<h2>Hierarchical Results</h2>'
                    '<p class="empty-note">Requested analysis version not found '
                    'or not completed.</p></div>',
                    False,
                )
        else:
            latest_version = AnalysisVersion.query.filter_by(
                project_id=project_id, status=AnalysisStatus.COMPLETED,
            ).order_by(AnalysisVersion.created_at.desc()).first()

        if not latest_version:
            return (
                '<div class="section" id="hierarchical">'
                '<h2>Hierarchical Results</h2>'
                '<p class="empty-note">No completed analysis found.</p></div>',
                False,
            )

        results = HierarchicalResult.query.filter_by(
            analysis_version_id=latest_version.id,
            parameter_type="log_fc_fmax",
        ).all()

        if not results:
            return (
                '<div class="section" id="hierarchical">'
                '<h2>Hierarchical Results</h2>'
                '<p class="empty-note">No hierarchical results available.</p></div>',
                False,
            )

        rows = []
        forest_data = []
        for r in results:
            construct = Construct.query.get(r.construct_id) if r.construct_id else None
            name = _esc(construct.identifier) if construct else f"ID:{r.construct_id}"
            # construct.family is a string column, not a relationship
            family = _esc(construct.family) if construct and construct.family else "-"

            type_badge = (
                '<span class="badge badge-blue">Bayesian</span>'
                if r.analysis_type == "bayesian"
                else '<span class="badge badge-green">Freq</span>'
            )

            rhat_val = r.r_hat or 0
            rhat_class = "badge-green" if rhat_val < 1.05 else (
                "badge-yellow" if rhat_val < 1.1 else "badge-red"
            )
            rhat_html = f'<span class="badge {rhat_class}">{rhat_val:.3f}</span>' if rhat_val else "-"

            lig_html = ""
            if r.ligand_condition == LigandCondition.PLUS_LIG:
                lig_html = '<span class="badge badge-teal">+Lig</span>'
            elif r.ligand_condition == LigandCondition.MINUS_LIG:
                lig_html = '<span class="badge badge-orange">-Lig</span>'

            ci_str = f"[{_fmt(r.ci_lower, '.3f')}, {_fmt(r.ci_upper, '.3f')}]" if r.ci_lower is not None else "-"

            rows.append(
                f"<tr><td>{name}</td><td>{family}</td><td>{type_badge}</td>"
                f"<td>{_fmt(r.mean, '.3f')}</td><td>{_fmt(r.std, '.3f')}</td>"
                f"<td>{ci_str}</td><td>{rhat_html}</td>"
                f"<td>{lig_html}</td></tr>"
            )

            if r.analysis_type == "bayesian" and r.ci_lower is not None:
                forest_data.append({
                    "name": construct.identifier if construct else f"ID:{r.construct_id}",
                    "family": construct.family if construct and construct.family else "",
                    "mean": r.mean,
                    "ci_lower": r.ci_lower,
                    "ci_upper": r.ci_upper,
                    "vif": 1.0,
                    "is_wt": False,
                })

        table_html = f"""
        <table class="hierarchical-table">
            <thead><tr>
                <th>Construct</th><th>Family</th><th>Method</th>
                <th>Mean</th><th>SD</th><th>95% CI</th>
                <th>R-hat</th><th>Condition</th>
            </tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table>"""

        plot_html = ""
        had_plots = False
        if forest_data:
            try:
                from app.components.forest_plot import create_forest_plot
                fig = create_forest_plot(
                    constructs=forest_data,
                    sort_by="effect_size",
                    group_by="family" if any(d.get("family") for d in forest_data) else None,
                    show_reference_line=True,
                    show_95_ci=True,
                    show_vif_badges=False,
                    title="Posterior Fold Change Estimates",
                )

                if render_static:
                    img_html = _fig_to_static_img(fig, width=900, height=500)
                    plot_html = f'<div class="plot-container">{img_html}</div>'
                else:
                    plot_html = '<div class="plot-container">' + fig.to_html(
                        full_html=False, include_plotlyjs=include_plotlyjs,
                    ) + '</div>'
                had_plots = True
            except Exception:
                pass

        version_name = _esc(latest_version.name)
        completed = latest_version.completed_at.strftime("%Y-%m-%d %H:%M") if latest_version.completed_at else "N/A"
        version_info = (
            f'<p style="color:#666;font-size:0.9em;">'
            f'Analysis: {version_name} (completed {completed})</p>'
        )

        return (
            f'<div class="section" id="hierarchical"><h2>Hierarchical Results</h2>'
            f'{version_info}{plot_html}{table_html}</div>',
            had_plots,
        )

    @staticmethod
    def _generate_plate_layout_section(
        project_id: int, include_plotlyjs: bool, plate_ids: List[int] = None,
        render_static: bool = False,
    ) -> tuple:
        """Generate plate layout section. Returns (html_str, had_plots)."""
        from app.models import Plate, Well, ExperimentalSession

        plate_q = Plate.query.join(ExperimentalSession).filter(
            ExperimentalSession.project_id == project_id,
        )
        if plate_ids:
            plate_q = plate_q.filter(Plate.id.in_(plate_ids))
        plates = plate_q.all()

        if not plates:
            return (
                '<div class="section" id="plate-layout">'
                '<h2>Plate Layout</h2>'
                '<p class="empty-note">No plates found.</p></div>',
                False,
            )

        plots_html = []
        had_plots = False

        for plate in plates:
            wells = Well.query.filter_by(plate_id=plate.id).all()
            if not wells:
                continue

            well_data = {}
            for w in wells:
                if w.construct:
                    label = w.construct.identifier
                    if w.ligand_condition == LigandCondition.PLUS_LIG:
                        label = f"{label} +Lig"
                    elif w.ligand_condition == LigandCondition.MINUS_LIG:
                        label = f"{label} -Lig"
                elif w.well_type and w.well_type.value != "empty":
                    label = w.well_type.value
                else:
                    continue  # skip empty wells — render as transparent
                well_data[w.position] = label

            try:
                from app.components.plate_heatmap import create_plate_heatmap_categorical
                pf = 96  # default
                if plate.session and plate.session.project and plate.session.project.plate_format:
                    pf = int(plate.session.project.plate_format.value)
                fig = create_plate_heatmap_categorical(
                    well_data, plate_format=pf,
                    title=f"Plate {plate.plate_number}",
                    height=280 if pf == 96 else 500,
                )
                if render_static:
                    h = 280 if pf == 96 else 500
                    plot_html = _fig_to_static_img(fig, width=900, height=h)
                else:
                    # Include Plotly.js only in the first plot in the document
                    js_setting = True if (include_plotlyjs and not had_plots) else False
                    plot_html = fig.to_html(
                        full_html=False, include_plotlyjs=js_setting,
                    )
                plots_html.append(f'<div class="plot-container">{plot_html}</div>')
                had_plots = True
            except Exception:
                grid_rows = []
                for w in sorted(wells, key=lambda w: (w.row_letter, w.col_number)):
                    construct = _esc(w.construct.identifier) if w.construct else "-"
                    wtype = _esc(w.well_type.value) if w.well_type else "-"
                    grid_rows.append(
                        f"<tr><td>{_esc(w.position)}</td><td>{construct}</td>"
                        f"<td>{wtype}</td></tr>"
                    )
                plots_html.append(
                    f'<h3>Plate {plate.plate_number}</h3>'
                    f'<table><thead><tr><th>Position</th><th>Construct</th>'
                    f'<th>Type</th></tr></thead>'
                    f'<tbody>{"".join(grid_rows)}</tbody></table>'
                )

        return (
            f'<div class="section" id="plate-layout"><h2>Plate Layout</h2>'
            f'{"".join(plots_html)}</div>',
            had_plots,
        )

    @staticmethod
    def _generate_qc_section(project_id: int, plate_ids: List[int] = None) -> str:
        """Generate QC summary of flagged/excluded wells."""
        from app.models import Plate, Well, ExperimentalSession

        excl_q = Well.query.join(Plate).join(ExperimentalSession).filter(
            ExperimentalSession.project_id == project_id,
            Well.is_excluded.is_(True),
        )
        fc_excl_q = Well.query.join(Plate).join(ExperimentalSession).filter(
            ExperimentalSession.project_id == project_id,
            Well.exclude_from_fc.is_(True),
        )
        if plate_ids:
            excl_q = excl_q.filter(Plate.id.in_(plate_ids))
            fc_excl_q = fc_excl_q.filter(Plate.id.in_(plate_ids))

        excluded_wells = excl_q.all()
        fc_excluded = fc_excl_q.all()

        if not excluded_wells and not fc_excluded:
            return (
                '<div class="section" id="qc-summary">'
                '<h2>QC Summary</h2>'
                '<p class="empty-note">No excluded or flagged wells.</p></div>'
            )

        stats_html = f"""
        <div class="stat-grid">
            <div class="stat-card">
                <div class="value" style="color:#c62828">{len(excluded_wells)}</div>
                <div class="label">Excluded Wells</div>
            </div>
            <div class="stat-card">
                <div class="value" style="color:#f57f17">{len(fc_excluded)}</div>
                <div class="label">Excluded from FC</div>
            </div>
        </div>"""

        rows = []
        seen = set()
        for w in excluded_wells + fc_excluded:
            if w.id in seen:
                continue
            seen.add(w.id)
            construct = _esc(w.construct.identifier) if w.construct else "-"
            reason = _esc(w.exclusion_reason) if w.exclusion_reason else "-"
            badges = []
            if w.is_excluded:
                badges.append('<span class="badge badge-red">Excluded</span>')
            if w.exclude_from_fc:
                badges.append('<span class="badge badge-yellow">FC Excluded</span>')

            rows.append(
                f"<tr><td>{_esc(w.position)}</td><td>Plate {w.plate.plate_number}</td>"
                f"<td>{construct}</td><td>{''.join(badges)}</td>"
                f"<td>{reason}</td></tr>"
            )

        table_html = f"""
        <table>
            <thead><tr>
                <th>Well</th><th>Plate</th><th>Construct</th>
                <th>Status</th><th>Reason</th>
            </tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table>"""

        return (
            f'<div class="section" id="qc-summary"><h2>QC Summary</h2>'
            f'{stats_html}{table_html}</div>'
        )

    @staticmethod
    def _generate_protocol_section(
        project_id: int, setup_id: int = None,
    ) -> str:
        """Generate protocol section with PDF-style structured HTML layout."""
        from app.models.reaction_setup import ReactionSetup

        if setup_id:
            setup = ReactionSetup.query.filter_by(
                id=setup_id, project_id=project_id,
            ).first()
        else:
            setup = ReactionSetup.query.filter_by(
                project_id=project_id,
            ).order_by(ReactionSetup.created_at.desc()).first()

        if not setup:
            return (
                '<div class="section" id="protocol">'
                '<h2>Protocol</h2>'
                '<p class="empty-note">No reaction setup found.</p></div>'
            )

        # --- Metadata header ---
        created_date = (
            setup.created_at.strftime("%Y-%m-%d %H:%M") if setup.created_at else "-"
        )
        created_by = _esc(setup.created_by) if setup.created_by else "-"
        meta_html = (
            f'<p style="color:#666; font-size:0.9em; margin-bottom:16px;">'
            f'<strong>{_esc(setup.name)}</strong> &mdash; '
            f'Created {_esc(created_date)}'
            f'{f" by {created_by}" if setup.created_by else ""}'
            f'</p>'
        )

        # --- Experiment summary stat cards ---
        n_constructs = setup.n_constructs or 0
        n_replicates = setup.n_replicates or 0
        rxn_vol = _fmt(setup.total_reaction_volume_ul, '.1f')
        overage = _fmt(setup.overage_percent, '.0f')
        total_mm = _fmt(setup.total_master_mix_volume_ul, '.1f')

        summary_html = f"""
        <h3>Experiment Summary</h3>
        <div class="stat-grid">
            <div class="stat-card">
                <div class="value">{n_constructs}</div>
                <div class="label">Constructs</div>
            </div>
            <div class="stat-card">
                <div class="value">{n_replicates}</div>
                <div class="label">Replicates</div>
            </div>
            <div class="stat-card">
                <div class="value">{rxn_vol} &micro;L</div>
                <div class="label">Reaction Volume</div>
            </div>
            <div class="stat-card">
                <div class="value">{overage}%</div>
                <div class="label">Overage</div>
            </div>
            <div class="stat-card">
                <div class="value">{total_mm} &micro;L</div>
                <div class="label">Total Master Mix</div>
            </div>
        </div>"""

        # --- Master mix components table ---
        mm_html = ""
        mm_volumes = setup.master_mix_volumes
        if mm_volumes and isinstance(mm_volumes, dict):
            mm_rows = []
            for comp_name, comp_data in mm_volumes.items():
                if not isinstance(comp_data, dict):
                    continue
                stock_conc = comp_data.get("stock_concentration", 0)
                stock_unit = _esc(comp_data.get("stock_unit", ""))
                stock_str = (
                    f"{stock_conc} {stock_unit}" if stock_conc else "-"
                )
                per_rxn = _fmt(comp_data.get("single_ul"), ".2f")
                total = _fmt(comp_data.get("total_ul"), ".2f")
                mm_rows.append(
                    f"<tr><td>{_esc(comp_name)}</td><td>{stock_str}</td>"
                    f'<td style="text-align:right">{per_rxn}</td>'
                    f'<td style="text-align:right">{total}</td></tr>'
                )

            if mm_rows:
                mm_html = f"""
        <h3>Master Mix Components</h3>
        <table>
            <thead><tr>
                <th>Component</th><th>Stock</th>
                <th style="text-align:right">Per Rxn (&micro;L)</th>
                <th style="text-align:right">Total (&micro;L)</th>
            </tr></thead>
            <tbody>{"".join(mm_rows)}</tbody>
        </table>"""

        # --- DNA additions table ---
        dna_html = ""
        dna_additions = setup.dna_additions
        if dna_additions:
            dna_rows = []
            for da in dna_additions:
                name = _esc(da.construct_name)
                badge = ""
                if da.is_negative_control:
                    ctrl_type = _esc(da.negative_control_type or "control")
                    badge = f' <span class="badge badge-gray">{ctrl_type}</span>'

                dna_vol = _fmt(da.dna_volume_ul, ".2f")
                water_vol = _fmt(da.water_adjustment_ul, ".2f")
                total_vol = _fmt(da.total_addition_ul, ".2f")

                dna_rows.append(
                    f"<tr><td>{name}{badge}</td>"
                    f'<td style="text-align:right">{dna_vol}</td>'
                    f'<td style="text-align:right">{water_vol}</td>'
                    f'<td style="text-align:right">{total_vol}</td></tr>'
                )

            dna_html = f"""
        <h3>DNA Additions</h3>
        <table>
            <thead><tr>
                <th>Construct</th>
                <th style="text-align:right">DNA Vol (&micro;L)</th>
                <th style="text-align:right">Water (&micro;L)</th>
                <th style="text-align:right">Total (&micro;L)</th>
            </tr></thead>
            <tbody>{"".join(dna_rows)}</tbody>
        </table>"""

        # --- Protocol steps (parsed from protocol_text) ---
        steps_html = ""
        protocol_text = setup.protocol_text
        if protocol_text:
            steps_html = DailyReportService._parse_protocol_steps(protocol_text)

        return (
            f'<div class="section" id="protocol"><h2>Protocol</h2>'
            f'{meta_html}{summary_html}{mm_html}{dna_html}{steps_html}</div>'
        )

    @staticmethod
    def _parse_protocol_steps(protocol_text: str) -> str:
        """Parse protocol_text into styled HTML for the step-by-step portion.

        The protocol text contains multiple sections (metadata, summary, tables,
        steps, notes). Since metadata/summary/tables are already rendered from
        structured DB data, we extract only the step-by-step protocol and notes.

        The step-by-step section starts after ``STEP-BY-STEP PROTOCOL`` and
        contains numbered steps like ``1. Action...`` with parenthetical notes
        ``(note text)``. Section sub-headers appear as ``### SECTION NAME ###``.
        """
        import re

        # Extract the step-by-step portion (skip summary/table sections)
        # Look for "STEP-BY-STEP PROTOCOL" marker; if absent, use full text
        step_start = None
        for marker in ("STEP-BY-STEP PROTOCOL", "STEP BY STEP PROTOCOL"):
            idx = protocol_text.find(marker)
            if idx >= 0:
                step_start = idx + len(marker)
                break

        if step_start is not None:
            working_text = protocol_text[step_start:]
        else:
            working_text = protocol_text

        # Trim after "END OF PROTOCOL" if present
        end_idx = working_text.find("END OF PROTOCOL")
        if end_idx >= 0:
            working_text = working_text[:end_idx]

        lines = working_text.split("\n")
        parts = ['<h3>Protocol Steps</h3>']
        notes_section = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Skip divider lines (===, ---)
            if re.match(r'^[=\-]{3,}$', stripped):
                continue

            # Detect section sub-headers: ### SECTION NAME ###
            m_section = re.match(r'^#{2,}\s*(.+?)\s*#{2,}$', stripped)
            if m_section:
                title = m_section.group(1).strip()
                parts.append(
                    f'<div class="protocol-section-title">{_esc(title)}</div>'
                )
                notes_section = False
                continue

            # Detect NOTES header
            if stripped == "NOTES":
                parts.append(
                    '<div class="protocol-section-title">Notes</div>'
                )
                notes_section = True
                continue

            # Detect all-caps sub-headers that aren't step lines
            # (e.g. bare "MASTER MIX PREPARATION" without ### markers)
            if (
                re.match(r'^[A-Z][A-Z \-/&]+$', stripped)
                and len(stripped) > 4
                and not re.match(r'^\d+\.', stripped)
            ):
                parts.append(
                    f'<div class="protocol-section-title">{_esc(stripped)}</div>'
                )
                notes_section = False
                continue

            # Bullet note lines (in NOTES section)
            if notes_section:
                bullet = stripped.lstrip("•·- ").strip()
                if bullet:
                    parts.append(
                        f'<div class="protocol-step">'
                        f'<span class="step-num">&bull;</span> {_esc(bullet)}'
                        f'</div>'
                    )
                continue

            # Numbered step: "1. Action text..."
            m_step = re.match(r'^(\d+)\.\s+(.+)$', stripped)
            if m_step:
                num = m_step.group(1)
                text = m_step.group(2)
                parts.append(
                    f'<div class="protocol-step">'
                    f'<span class="step-num">{_esc(num)}.</span> {_esc(text)}'
                    f'</div>'
                )
                continue

            # Parenthetical note line: "(note text)"
            if stripped.startswith("(") and stripped.endswith(")"):
                parts.append(
                    f'<div class="protocol-step">'
                    f'<div class="step-note">{_esc(stripped)}</div>'
                    f'</div>'
                )
                continue

            # Other content — render as plain text
            parts.append(f'<div class="protocol-step">{_esc(stripped)}</div>')

        if len(parts) <= 1:
            # No steps found — fallback
            return (
                '<h3>Protocol Steps</h3>'
                '<pre style="background:#f5f5f5; padding:16px; border-radius:6px; '
                'overflow-x:auto; font-size:0.85em; line-height:1.5;">'
                f'{_esc(protocol_text)}</pre>'
            )

        return "\n".join(parts)

    @staticmethod
    def _generate_audit_section(project_id: int) -> str:
        """Generate audit trail section with change diffs."""
        from app.models import AuditLog
        from collections import Counter

        events = AuditLog.query.filter_by(
            project_id=project_id,
        ).order_by(AuditLog.timestamp.desc()).all()

        if not events:
            return (
                '<div class="section" id="audit-trail">'
                '<h2>Audit Trail</h2>'
                '<p class="empty-note">No audit events recorded.</p></div>'
            )

        action_counts = Counter(e.action_type for e in events)
        user_counts = Counter(e.username for e in events)

        summary_items = " / ".join(
            f"{_esc(action)}: {count}" for action, count in action_counts.most_common()
        )
        user_items = ", ".join(
            f"{_esc(user)} ({count})" for user, count in user_counts.most_common(5)
        )

        summary_html = f"""
        <div style="margin-bottom:16px; font-size:0.9em; color:#555;">
            <strong>Total events:</strong> {len(events)} |
            <strong>Actions:</strong> {summary_items}<br>
            <strong>Users:</strong> {user_items}
        </div>"""

        rows = []
        for event in events[:100]:  # Limit to 100 most recent
            timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M") if event.timestamp else "-"

            changes_html = ""
            changes = event.changes
            if changes and isinstance(changes, list):
                diff_parts = []
                for change in changes:
                    field = _esc(change.get("field", "?"))
                    old = _esc(change.get("old", "N/A"))
                    new = _esc(change.get("new", "N/A"))
                    diff_parts.append(
                        f'<div class="change-diff">'
                        f'<strong>{field}:</strong> '
                        f'<span class="change-old">{old}</span> '
                        f'&rarr; <span class="change-new">{new}</span></div>'
                    )
                changes_html = "".join(diff_parts)

            details_html = ""
            details = event.details
            if details and isinstance(details, dict):
                detail_text = ", ".join(
                    f"{_esc(k)}: {_esc(v)}" for k, v in details.items()
                    if k not in ("changes",)
                )
                if detail_text:
                    details_html = f'<div style="font-size:0.85em;color:#666;">{detail_text}</div>'

            entity_info = f"{_esc(event.entity_type)}#{event.entity_id}" if event.entity_type else "-"

            rows.append(
                f"<tr><td>{timestamp}</td><td>{_esc(event.username)}</td>"
                f"<td><span class='badge badge-blue'>{_esc(event.action_type)}</span></td>"
                f"<td>{entity_info}</td>"
                f"<td>{changes_html}{details_html}</td></tr>"
            )

        table_html = f"""
        <table class="audit-table">
            <colgroup>
                <col style="width:14%">
                <col style="width:10%">
                <col style="width:12%">
                <col style="width:20%">
                <col style="width:44%">
            </colgroup>
            <thead><tr>
                <th>Time</th><th>User</th><th>Action</th>
                <th>Entity</th><th>Changes</th>
            </tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table>"""

        return (
            f'<div class="section" id="audit-trail"><h2>Audit Trail</h2>'
            f'{summary_html}{table_html}</div>'
        )
