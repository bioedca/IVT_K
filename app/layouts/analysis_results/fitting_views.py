"""Curve fit plots, parameter displays, and results tables for the fitting workflow."""
from typing import Optional, List, Dict, Any, Union
import dash_mantine_components as dmc
from dash import html
from dash_iconify import DashIconify
import plotly.graph_objects as go

from app.theme import apply_plotly_theme
from app.analysis.fit_reliability import reasons_to_label
from app.layouts.analysis_results.components import _format_with_se


def create_curve_fit_plot(
    timepoints: List[float],
    raw_values: List[float],
    fit_timepoints: Optional[List[float]] = None,
    fit_values: Optional[List[float]] = None,
    well_name: str = "",
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a curve fit visualization plot.

    Args:
        timepoints: Raw data timepoints
        raw_values: Raw fluorescence values
        fit_timepoints: Fitted curve timepoints (smoother)
        fit_values: Fitted curve values
        well_name: Well identifier for title

    Returns:
        Plotly figure
    """
    fig = go.Figure()

    # Raw data points
    fig.add_trace(go.Scatter(
        x=timepoints,
        y=raw_values,
        mode='markers',
        name='Raw Data',
        marker=dict(size=6, color='#228be6', opacity=0.7),
        hovertemplate='Time: %{x:.1f} min<br>Fluorescence: %{y:.0f}<extra></extra>',
    ))

    # Fitted curve
    if fit_timepoints and fit_values:
        fig.add_trace(go.Scatter(
            x=fit_timepoints,
            y=fit_values,
            mode='lines',
            name='Fit',
            line=dict(color='#fa5252', width=2),
            hovertemplate='Time: %{x:.1f} min<br>Fit: %{y:.0f}<extra></extra>',
        ))

    fig.update_layout(
        title=dict(text=f"Well {well_name}" if well_name else "Curve Fit", x=0.5),
        xaxis_title="Time (min)",
        yaxis_title="Fluorescence (RFU)",
        height=300,
        margin=dict(l=60, r=30, t=40, b=40),
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0.5, xanchor='center'),
    )
    apply_plotly_theme(fig, dark_mode=dark_mode)

    return fig


def create_fit_params_display(
    params: Optional[Dict[str, Any]] = None,
    statistics: Optional[Dict[str, Any]] = None,
) -> Union[dmc.Table, dmc.Text]:
    """
    Create a table displaying fitted parameters and statistics.

    Args:
        params: Dict with F_baseline, F_max, k_obs, t_lag (each with value and se)
        statistics: Dict with r_squared, rmse, aic, converged

    Returns:
        Table component
    """
    if not params:
        return dmc.Text("No fit parameters available", c="dimmed", ta="center")

    rows = []

    # Parameter rows
    param_labels = {
        "F_baseline": ("F_baseline", "RFU"),
        "F_max": ("F_max", "RFU"),
        "k_obs": ("k_obs", "min\u207b\u00b9"),
        "t_lag": ("t_lag", "min"),
    }

    for param_key, (label, unit) in param_labels.items():
        param_data = params.get(param_key, {})
        value = param_data.get("value")
        se = param_data.get("se")

        if value is not None:
            value_str = f"{value:.3f}"
            se_str = f"\u00b1 {se:.3f}" if se else ""
            rows.append(
                html.Tr([
                    html.Td(label),
                    html.Td(value_str),
                    html.Td(se_str, style={"color": "gray"}),
                    html.Td(unit, style={"color": "gray"}),
                ])
            )

    # Statistics section
    if statistics:
        rows.append(html.Tr([html.Td(html.Hr(), colSpan=4)]))

        r_squared = statistics.get("r_squared")
        if r_squared is not None:
            r_color = "green" if r_squared >= 0.9 else ("yellow" if r_squared >= 0.8 else "red")
            rows.append(
                html.Tr([
                    html.Td("R\u00b2"),
                    html.Td(dmc.Badge(f"{r_squared:.4f}", color=r_color, size="sm")),
                    html.Td(""),
                    html.Td(""),
                ])
            )

        rmse = statistics.get("rmse")
        if rmse is not None:
            rows.append(
                html.Tr([
                    html.Td("RMSE"),
                    html.Td(f"{rmse:.2f}"),
                    html.Td(""),
                    html.Td("RFU"),
                ])
            )

        converged = statistics.get("converged")
        if converged is not None:
            rows.append(
                html.Tr([
                    html.Td("Converged"),
                    html.Td(dmc.Badge("Yes" if converged else "No", color="green" if converged else "red", size="sm")),
                    html.Td(""),
                    html.Td(""),
                ])
            )

    return dmc.Table(
        striped=True,
        children=[
            html.Thead(
                html.Tr([
                    html.Th("Parameter"),
                    html.Th("Value"),
                    html.Th("SE"),
                    html.Th("Unit"),
                ])
            ),
            html.Tbody(rows),
        ],
    )


_RELIABILITY_BADGE_COLORS = {
    "GOOD": "green",
    "OK": "gray",
    "WEAK": "orange",
    "BAD": "red",
}


def build_fit_results_table(
    fits: List,
    selected_well_ids: List[int],
    reliability_results: Optional[Dict[int, Any]] = None,
) -> Union[dmc.Table, dmc.Text]:
    """
    Build the fit results table with clickable rows, selection highlighting, and FC inclusion checkbox.

    Args:
        fits: List of FitResult model instances
        selected_well_ids: List of currently selected well IDs
        reliability_results: Optional dict mapping fit.id -> ReliabilityResult.
            When provided, adds a colored Reliability badge column with a tooltip
            listing the failing criteria.

    Returns:
        dmc.Table component with clickable rows and FC inclusion checkboxes
    """
    if not fits:
        return dmc.Text("No fit results available", c="dimmed", ta="center")

    reliability_results = reliability_results or {}
    table_rows = []

    for fit in fits:
        well = fit.well
        construct_name = well.construct.identifier if well.construct else "\u2014"
        is_selected = well.id in selected_well_ids
        is_included_in_fc = not well.exclude_from_fc

        # Format R\u00b2 with color indicator
        r2 = fit.r_squared or 0
        r2_color = "green" if r2 >= 0.9 else ("yellow" if r2 >= 0.8 else "red")

        # Row styling - highlight selected rows, dim excluded rows
        row_style = {
            "cursor": "pointer",
            "backgroundColor": "var(--bg-hover)" if is_selected else ("transparent" if is_included_in_fc else "var(--bg-surface)"),
            "borderLeft": "3px solid #228be6" if is_selected else "3px solid transparent",
            "opacity": "1" if is_included_in_fc else "0.6",
        }

        # Text style for excluded wells
        text_style = {"textDecoration": "line-through"} if not is_included_in_fc else {}

        rel_result = reliability_results.get(getattr(fit, "id", None))
        if rel_result is not None:
            flag_value = getattr(rel_result.flag, "value", str(rel_result.flag))
            badge_color = _RELIABILITY_BADGE_COLORS.get(flag_value, "gray")
            tooltip_label = reasons_to_label(rel_result.reasons)
            reliability_cell = html.Td(
                dmc.Tooltip(
                    label=tooltip_label,
                    children=dmc.Badge(flag_value, color=badge_color, size="sm", variant="light"),
                ),
            )
        else:
            reliability_cell = html.Td(dmc.Badge("\u2014", color="gray", size="sm", variant="light"))

        # Clickable row with pattern-matching ID
        table_rows.append(
            html.Tr(
                [
                    # FC inclusion checkbox column
                    # Syncs with Curve Browser's FC inclusion buttons
                    # See: curve_browser_callbacks.py handle_fc_inclusion()
                    # Both use FittingService.set_well_fc_inclusion() for consistency
                    html.Td(
                        dmc.Checkbox(
                            id={"type": "fc-inclusion-checkbox", "index": well.id},
                            checked=is_included_in_fc,
                            size="xs",
                        ),
                        style={"width": "40px", "textAlign": "center"},
                        # Stop click propagation so checkbox click doesn't select row
                        **{"data-no-row-select": "true"},
                    ),
                    html.Td(
                        dmc.Group([
                            dmc.ThemeIcon(
                                DashIconify(icon="mdi:check", width=14),
                                size="xs",
                                color="blue",
                                variant="light",
                            ) if is_selected else html.Span(style={"width": "18px", "display": "inline-block"}),
                            html.Span(construct_name, style={"fontWeight": "500", **text_style}),
                        ], gap="xs"),
                    ),
                    html.Td(html.Span(well.position, style=text_style)),
                    html.Td(html.Span(f"{fit.k_obs:.4f}" if fit.k_obs is not None else "\u2014", style=text_style)),
                    html.Td(html.Span(f"{fit.f_max:.1f}" if fit.f_max is not None else "\u2014", style=text_style)),
                    html.Td(html.Span(f"{fit.t_lag:.1f}" if fit.t_lag is not None else "\u2014", style=text_style)),
                    html.Td(
                        dmc.Badge(f"{r2:.3f}", color=r2_color, size="sm", variant="light"),
                    ),
                    reliability_cell,
                ],
                id={"type": "fitting-result-row", "index": well.id},
                style=row_style,
            )
        )

    return dmc.Table(
        striped=False,  # Disable striping to show selection highlighting better
        highlightOnHover=True,
        withTableBorder=True,
        withColumnBorders=True,
        children=[
            html.Thead(
                html.Tr([
                    html.Th("FC", style={"width": "40px", "textAlign": "center"}),  # FC inclusion column
                    html.Th("Construct"),
                    html.Th("Well"),
                    html.Th("k_obs (1/min)"),
                    html.Th("F_max"),
                    html.Th("t_lag (min)"),
                    html.Th("R\u00b2"),
                    html.Th("Reliability"),
                ])
            ),
            html.Tbody(table_rows),
        ],
    )


def create_multi_well_curve_plot(
    all_fit_data: List[Dict[str, Any]],
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a curve fit visualization plot for multiple wells.

    Args:
        all_fit_data: List of fit data dicts, each with timepoints, fluorescence_corrected,
                      fit_curve, position, plate_number

    Returns:
        Plotly figure with multiple curves
    """
    # Color palette for multiple wells
    colors = [
        '#228be6', '#40c057', '#fa5252', '#fab005', '#7950f2',
        '#15aabf', '#e64980', '#82c91e', '#fd7e14', '#be4bdb',
    ]

    fig = go.Figure()

    for i, fit_data in enumerate(all_fit_data):
        color = colors[i % len(colors)]
        position = fit_data.get("position", f"Well {i+1}")
        plate_num = fit_data.get("plate_number", "?")
        label = f"P{plate_num}-{position}"

        timepoints = fit_data.get("timepoints", [])
        raw_values = fit_data.get("fluorescence_corrected", [])
        fit_curve = fit_data.get("fit_curve", {})

        # Raw data points - only first trace per well shows in legend
        fig.add_trace(go.Scatter(
            x=timepoints,
            y=raw_values,
            mode='markers',
            name=label,
            marker=dict(size=5, color=color, opacity=0.6),
            hovertemplate=f'{label}<br>Time: %{{x:.1f}} min<br>Fluorescence: %{{y:.0f}}<extra></extra>',
            legendgroup=label,
        ))

        # Fitted curve - hidden from legend (same legendgroup toggles both)
        if fit_curve.get("timepoints") and fit_curve.get("values"):
            fig.add_trace(go.Scatter(
                x=fit_curve["timepoints"],
                y=fit_curve["values"],
                mode='lines',
                name=label,
                line=dict(color=color, width=2),
                hovertemplate=f'{label}<br>Time: %{{x:.1f}} min<br>Fit: %{{y:.0f}}<extra></extra>',
                legendgroup=label,
                showlegend=False,  # Only show one entry per well
            ))

    n_wells = len(all_fit_data)
    title = f"{n_wells} Well{'s' if n_wells != 1 else ''} Selected"

    # Dynamic height based on wells (min 300, grows with more wells for legend space)
    height = max(300, min(500, 250 + n_wells * 15))

    # Adjust right margin for side legend (more wells = wider legend area)
    right_margin = max(100, min(150, 80 + n_wells * 5))

    fig.update_layout(
        title=dict(text=title, x=0.5),
        xaxis_title="Time (min)",
        yaxis_title="Fluorescence (RFU)",
        height=height,
        margin=dict(l=60, r=right_margin, t=60, b=40),
        showlegend=True,
        legend=dict(
            orientation='v',
            yanchor='top',
            y=1,
            xanchor='left',
            x=1.02,
            font=dict(size=10),
            bgcolor='rgba(30,42,42,0.9)' if dark_mode else 'rgba(255,255,255,0.9)',
            bordercolor='rgba(255,255,255,0.12)' if dark_mode else '#e9ecef',
            borderwidth=1,
            tracegroupgap=2,
            itemsizing='constant',
        ),
        # Add annotation explaining dots vs lines
        annotations=[
            dict(
                text="<i>\u25cf dots = data, \u2014 lines = model fit</i>",
                xref="paper", yref="paper",
                x=0.5, y=1.08,
                showarrow=False,
                font=dict(size=10, color="#6b7575" if dark_mode else "#868e96"),
                xanchor="center",
            )
        ],
    )
    apply_plotly_theme(fig, dark_mode=dark_mode)

    return fig


def create_multi_well_params_table(
    all_fit_data: List[Dict[str, Any]],
) -> Union[dmc.Table, dmc.Text]:
    """
    Create a table displaying fitted parameters with SE for multiple wells.

    Args:
        all_fit_data: List of fit data dicts, each with parameters, statistics, position

    Returns:
        Table component
    """
    if not all_fit_data:
        return dmc.Text("No fit parameters available", c="dimmed", ta="center")

    rows = []

    for fit_data in all_fit_data:
        position = fit_data.get("position", "?")
        plate_num = fit_data.get("plate_number", "?")
        params = fit_data.get("parameters", {})
        stats = fit_data.get("statistics", {})

        # Extract parameter values and SEs
        k_obs = params.get("k_obs", {}).get("value")
        k_obs_se = params.get("k_obs", {}).get("se")
        f_max = params.get("F_max", {}).get("value")
        f_max_se = params.get("F_max", {}).get("se")
        t_lag = params.get("t_lag", {}).get("value")
        t_lag_se = params.get("t_lag", {}).get("se")
        r_squared = stats.get("r_squared")

        # R\u00b2 badge color
        r2_color = "green" if r_squared and r_squared >= 0.9 else ("yellow" if r_squared and r_squared >= 0.8 else "red")

        rows.append(
            html.Tr([
                html.Td(f"P{plate_num}-{position}", style={"fontWeight": "500"}),
                html.Td(_format_with_se(k_obs, k_obs_se, decimals=4)),
                html.Td(_format_with_se(f_max, f_max_se, decimals=0)),
                html.Td(_format_with_se(t_lag, t_lag_se, decimals=2)),
                html.Td(
                    dmc.Badge(f"{r_squared:.3f}", color=r2_color, size="sm", variant="light")
                    if r_squared is not None else "\u2014"
                ),
            ])
        )

    return dmc.Table(
        striped=True,
        highlightOnHover=True,
        withTableBorder=True,
        withColumnBorders=True,
        children=[
            html.Thead(
                html.Tr([
                    html.Th("Well"),
                    html.Th("k_obs \u00b1 SE (min\u207b\u00b9)"),
                    html.Th("F_max \u00b1 SE"),
                    html.Th("t_lag \u00b1 SE (min)"),
                    html.Th("R\u00b2"),
                ])
            ),
            html.Tbody(rows),
        ],
    )


def create_fit_quality_histogram(
    r_squared_values: List[float],
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a histogram of R\u00b2 values to show fit quality distribution.

    Args:
        r_squared_values: List of R\u00b2 values from fits

    Returns:
        Plotly figure
    """
    if not r_squared_values:
        fig = go.Figure()
        fig.add_annotation(
            text="No fit data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
        )
        fig.update_layout(height=200)
        apply_plotly_theme(fig, dark_mode=dark_mode)
        return fig

    fig = go.Figure()

    # Calculate range with padding based on actual data
    min_val = min(r_squared_values)
    max_val = max(r_squared_values)
    padding = (max_val - min_val) * 0.1 if max_val > min_val else 0.05
    x_min = max(0, min_val - padding)
    x_max = min(1, max_val + padding)

    # Create bins for R\u00b2 quality categories
    fig.add_trace(go.Histogram(
        x=r_squared_values,
        nbinsx=20,
        marker_color='#228be6',
        opacity=0.8,
        hovertemplate='R\u00b2: %{x:.3f}<br>Count: %{y}<extra></extra>',
    ))

    # Add quality threshold lines only if they're within the visible range
    if x_min <= 0.9 <= x_max:
        fig.add_vline(x=0.9, line=dict(color='green', dash='dash'), annotation_text="Good (0.9)")
    if x_min <= 0.8 <= x_max:
        fig.add_vline(x=0.8, line=dict(color='orange', dash='dash'), annotation_text="Acceptable (0.8)")

    fig.update_layout(
        xaxis=dict(title="R\u00b2", range=[x_min, x_max]),
        yaxis_title="Count",
        height=200,
        margin=dict(l=50, r=30, t=20, b=40),
        bargap=0.1,
    )
    apply_plotly_theme(fig, dark_mode=dark_mode)

    return fig


def build_fold_change_table(fold_changes: List[Dict[str, Any]]) -> Union[dmc.Table, dmc.Text]:
    """
    Build a construct-grouped table displaying fold change results.

    Groups fold changes by (construct, comparison_type, ligand_condition) and
    shows mean +/- SD across well pairs so all constructs are visible.
    Expandable detail rows show individual well pairs.

    Args:
        fold_changes: List of fold change data dicts from FittingService.get_fold_change_summary()

    Returns:
        dmc.Table component
    """
    if not fold_changes:
        return dmc.Text("No fold changes computed yet", c="dimmed", ta="center")

    import statistics

    # Check if any fold changes have ligand conditions
    has_ligand = any(fc.get("ligand_condition") for fc in fold_changes)

    # Group by (construct, comparison_type, ligand/fc_comparison_type)
    groups = {}
    for fc in fold_changes:
        key = (
            fc.get("test_construct_name", "Unknown"),
            fc.get("comparison_type", "Unknown"),
            fc.get("ligand_condition"),
            fc.get("fc_comparison_type"),
        )
        groups.setdefault(key, []).append(fc)

    # Sort groups: Mutant->WT first, then WT->Unreg, then by construct name
    type_order = {"Mutant \u2192 WT": 0, "WT \u2192 Unreg": 1, "Ligand Effect": 2}
    sorted_keys = sorted(groups.keys(), key=lambda k: (type_order.get(k[1], 9), k[0]))

    rows = []
    for key in sorted_keys:
        construct_name, comp_type, ligand_cond, fc_comp_type = key
        fcs = groups[key]
        n = len(fcs)

        # Compute mean and SD for each metric
        fmax_vals = [fc["fc_fmax"] for fc in fcs if fc.get("fc_fmax") is not None]
        kobs_vals = [fc["fc_kobs"] for fc in fcs if fc.get("fc_kobs") is not None]
        tlag_vals = [fc["delta_tlag"] for fc in fcs if fc.get("delta_tlag") is not None]

        def _mean_sd(vals, decimals=2):
            if not vals:
                return "\u2014"
            m = statistics.mean(vals)
            fmt = f".{decimals}f"
            if len(vals) >= 2:
                sd = statistics.stdev(vals)
                return f"{m:{fmt}} \u00b1 {sd:{fmt}}"
            return f"{m:{fmt}}"

        fmax_str = _mean_sd(fmax_vals)
        kobs_str = _mean_sd(kobs_vals)
        tlag_str = _mean_sd(tlag_vals, decimals=1)

        # Comparison type badge
        comp_color = "blue" if comp_type == "Mutant \u2192 WT" else (
            "green" if comp_type == "WT \u2192 Unreg" else (
                "violet" if comp_type == "Ligand Effect" else "gray"
            )
        )

        # Ligand condition cell
        ligand_cells = []
        if has_ligand:
            if fc_comp_type == "ligand_effect":
                ligand_cells.append(
                    html.Td(dmc.Badge("+Lig/-Lig", color="violet", size="xs", variant="light"))
                )
            elif ligand_cond == "+Lig":
                ligand_cells.append(
                    html.Td(dmc.Badge("+Lig", color="teal", size="xs", variant="light"))
                )
            elif ligand_cond == "-Lig":
                ligand_cells.append(
                    html.Td(dmc.Badge("-Lig", color="orange", size="xs", variant="light"))
                )
            else:
                ligand_cells.append(html.Td("\u2014"))

        rows.append(
            html.Tr([
                html.Td(construct_name, style={"fontWeight": 500}),
                html.Td(dmc.Badge(comp_type, color=comp_color, size="xs", variant="light")),
                html.Td(str(n)),
                *ligand_cells,
                html.Td(fmax_str),
                html.Td(kobs_str),
                html.Td(tlag_str),
            ])
        )

    # Build header
    header_cells = [
        html.Th("Construct"),
        html.Th("Type"),
        html.Th("N pairs"),
    ]
    if has_ligand:
        header_cells.append(html.Th("Condition"))
    header_cells.extend([
        html.Th("FC_Fmax (mean \u00b1 SD)"),
        html.Th("FC_kobs (mean \u00b1 SD)"),
        html.Th("\u0394t_lag (mean \u00b1 SD)"),
    ])

    return dmc.Table(
        striped=True,
        highlightOnHover=True,
        withTableBorder=True,
        withColumnBorders=True,
        children=[
            html.Thead(html.Tr(header_cells)),
            html.Tbody(rows),
        ],
    )
