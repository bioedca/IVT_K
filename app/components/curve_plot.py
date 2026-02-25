"""
Curve plot component for visualization.

Phase 4.12: Curve Browser visualization (F8.8, F8.9, F13.2)

Creates interactive plots for:
- Raw fluorescence data with fit overlay
- Residuals visualization
- LOD/LOQ reference lines
"""
from typing import Optional, List, Dict, Any, Tuple
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

from app.theme import apply_plotly_theme, get_annotation_bg


def create_curve_plot(
    timepoints: List[float],
    raw_values: List[float],
    fit_values: Optional[List[float]] = None,
    fit_params: Optional[Dict[str, float]] = None,
    show_fit: bool = True,
    show_residuals: bool = False,
    show_lod_loq: bool = False,
    lod: Optional[float] = None,
    loq: Optional[float] = None,
    title: Optional[str] = None,
    well_position: Optional[str] = None,
    construct_name: Optional[str] = None,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a curve plot with optional fit overlay and residuals.

    Args:
        timepoints: Time values (minutes)
        raw_values: Raw fluorescence values
        fit_values: Optional fitted values
        fit_params: Optional fit parameters dict (k_obs, F_max, t_lag, F_0, R2)
        show_fit: Whether to show fit line
        show_residuals: Whether to show residuals panel
        show_lod_loq: Whether to show LOD/LOQ lines
        lod: Limit of detection value
        loq: Limit of quantification value
        title: Plot title
        well_position: Well position for labeling
        construct_name: Construct name for labeling

    Returns:
        Plotly figure
    """
    # Determine subplot layout
    if show_residuals and fit_values:
        fig = make_subplots(
            rows=2, cols=1,
            row_heights=[0.7, 0.3],
            shared_xaxes=True,
            vertical_spacing=0.08,
        )
    else:
        fig = go.Figure()

    # Main curve - raw data
    fig.add_trace(
        go.Scatter(
            x=timepoints,
            y=raw_values,
            mode="markers",
            name="Raw Data",
            marker=dict(
                size=6,
                color="rgba(31, 119, 180, 0.7)",
            ),
        ),
        row=1 if show_residuals and fit_values else None,
        col=1 if show_residuals and fit_values else None,
    )

    # Fit line
    if show_fit and fit_values:
        fig.add_trace(
            go.Scatter(
                x=timepoints,
                y=fit_values,
                mode="lines",
                name="Fit",
                line=dict(color="red", width=2),
            ),
            row=1 if show_residuals else None,
            col=1 if show_residuals else None,
        )

    # LOD/LOQ lines
    if show_lod_loq:
        if lod is not None:
            fig.add_hline(
                y=lod,
                line_dash="dash",
                line_color="orange",
                annotation_text="LOD",
                annotation_position="right",
                row=1 if show_residuals and fit_values else None,
            )
        if loq is not None:
            fig.add_hline(
                y=loq,
                line_dash="dot",
                line_color="green",
                annotation_text="LOQ",
                annotation_position="right",
                row=1 if show_residuals and fit_values else None,
            )

    # Residuals panel
    if show_residuals and fit_values:
        residuals = [r - f for r, f in zip(raw_values, fit_values)]

        fig.add_trace(
            go.Scatter(
                x=timepoints,
                y=residuals,
                mode="markers",
                name="Residuals",
                marker=dict(size=4, color="gray"),
            ),
            row=2, col=1,
        )

        # Zero line for residuals
        fig.add_hline(y=0, line_dash="dash", line_color="black", row=2)

        fig.update_yaxes(title_text="Residuals", row=2, col=1)

    # Build title
    if title:
        plot_title = title
    else:
        parts = []
        if construct_name:
            parts.append(construct_name)
        if well_position:
            parts.append(f"Well {well_position}")
        plot_title = " - ".join(parts) if parts else "Kinetic Curve"

    # Add parameter annotation if available
    if fit_params:
        param_text = []
        if "k_obs" in fit_params:
            param_text.append(f"k_obs: {fit_params['k_obs']:.4f}")
        if "F_max" in fit_params:
            param_text.append(f"F_max: {fit_params['F_max']:.0f}")
        if "R2" in fit_params:
            param_text.append(f"R\u00b2: {fit_params['R2']:.3f}")

        if param_text:
            fig.add_annotation(
                text="<br>".join(param_text),
                xref="paper", yref="paper",
                x=0.02, y=0.98,
                showarrow=False,
                font=dict(size=10),
                align="left",
                bgcolor=get_annotation_bg(dark_mode),
                bordercolor="gray",
                borderwidth=1,
            )

    # Layout
    fig.update_layout(
        title=dict(text=plot_title, x=0.5),
        xaxis_title="Time (min)",
        yaxis_title="Fluorescence (RFU)",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=60, r=20, t=60, b=40),
        hovermode="x unified",
    )

    apply_plotly_theme(fig, dark_mode=dark_mode)
    return fig


def create_multi_panel_curve_plot(
    panels: List[Dict[str, Any]],
    layout: str = "2-panel",  # "single", "2-panel", "4-panel"
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a multi-panel comparison view.

    Args:
        panels: List of panel data dicts with keys:
            - timepoints: List[float]
            - raw_values: List[float]
            - fit_values: Optional[List[float]]
            - title: str
            - fit_params: Optional[Dict]
        layout: Layout type

    Returns:
        Plotly figure
    """
    n_panels = len(panels)

    if layout == "single" or n_panels == 1:
        rows, cols = 1, 1
    elif layout == "2-panel" or n_panels == 2:
        rows, cols = 1, 2
    else:  # 4-panel
        rows, cols = 2, 2

    # Create subplots
    titles = [p.get("title", f"Panel {i+1}") for i, p in enumerate(panels[:4])]

    fig = make_subplots(
        rows=rows, cols=cols,
        subplot_titles=titles[:rows*cols],
        horizontal_spacing=0.08,
        vertical_spacing=0.12,
    )

    # Add traces to each panel
    colors = ["blue", "red", "green", "purple"]

    for i, panel in enumerate(panels[:rows*cols]):
        row = i // cols + 1
        col = i % cols + 1

        timepoints = panel.get("timepoints", [])
        raw_values = panel.get("raw_values", [])
        fit_values = panel.get("fit_values")

        # Raw data
        fig.add_trace(
            go.Scatter(
                x=timepoints,
                y=raw_values,
                mode="markers",
                name=f"Data ({panel.get('title', '')})",
                marker=dict(size=5, color=colors[i % len(colors)]),
                showlegend=False,
            ),
            row=row, col=col,
        )

        # Fit line
        if fit_values:
            fig.add_trace(
                go.Scatter(
                    x=timepoints,
                    y=fit_values,
                    mode="lines",
                    name=f"Fit ({panel.get('title', '')})",
                    line=dict(color="black", width=1.5),
                    showlegend=False,
                ),
                row=row, col=col,
            )

        # Add parameter annotation
        fit_params = panel.get("fit_params", {})
        if fit_params:
            param_text = []
            if "k_obs" in fit_params:
                param_text.append(f"k: {fit_params['k_obs']:.3f}")
            if "F_max" in fit_params:
                param_text.append(f"F: {fit_params['F_max']:.0f}")
            if "R2" in fit_params:
                param_text.append(f"R\u00b2: {fit_params['R2']:.2f}")

            if param_text:
                # Calculate annotation position based on subplot
                x_pos = (col - 1) / cols + 0.02
                y_pos = 1 - (row - 1) / rows - 0.12

                fig.add_annotation(
                    text=" | ".join(param_text),
                    xref="paper", yref="paper",
                    x=x_pos, y=y_pos,
                    showarrow=False,
                    font=dict(size=9),
                    bgcolor=get_annotation_bg(dark_mode),
                )

    # Update layout
    fig.update_layout(
        showlegend=False,
        margin=dict(l=50, r=20, t=60, b=40),
        hovermode="closest",
    )

    # Update all axes
    for i in range(1, rows * cols + 1):
        fig.update_xaxes(title_text="Time (min)", row=(i-1)//cols+1, col=(i-1)%cols+1)
        fig.update_yaxes(title_text="RFU", row=(i-1)//cols+1, col=(i-1)%cols+1)

    apply_plotly_theme(fig, dark_mode=dark_mode)
    return fig


def compute_fit_curve(
    timepoints: List[float],
    k_obs: float,
    F_max: float,
    t_lag: float = 0.0,
    F_0: float = 0.0,
) -> List[float]:
    """
    Compute delayed exponential fit values.

    F(t) = F_0 + F_max * (1 - exp(-k_obs * (t - t_lag))) for t > t_lag
    F(t) = F_0 for t <= t_lag

    Args:
        timepoints: Time values
        k_obs: Observed rate constant
        F_max: Maximum fluorescence amplitude
        t_lag: Lag time
        F_0: Initial fluorescence

    Returns:
        Computed fit values
    """
    fit_values = []
    for t in timepoints:
        if t <= t_lag:
            fit_values.append(F_0)
        else:
            fit_values.append(F_0 + F_max * (1 - np.exp(-k_obs * (t - t_lag))))

    return fit_values


def create_overlay_plot(
    curves: List[Dict[str, Any]],
    normalize: bool = False,
    title: str = "Curve Overlay",
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create an overlay plot of multiple curves.

    Args:
        curves: List of curve dicts with:
            - timepoints: List[float]
            - values: List[float]
            - name: str
            - color: Optional[str]
            - curve_type: "data" (markers) or "fit" (lines)
            - color_index: Optional[int] for consistent coloring
        normalize: Whether to normalize curves to [0, 1]
        title: Plot title

    Returns:
        Plotly figure
    """
    fig = go.Figure()

    # Aesthetically pleasing color palette (ColorBrewer Set2 + custom)
    colors = [
        "#1f77b4",  # muted blue
        "#ff7f0e",  # safety orange
        "#2ca02c",  # cooked asparagus green
        "#d62728",  # brick red
        "#9467bd",  # muted purple
        "#8c564b",  # chestnut brown
        "#e377c2",  # raspberry yogurt pink
        "#7f7f7f",  # middle gray
        "#bcbd22",  # curry yellow-green
        "#17becf",  # blue-teal
    ]

    for i, curve in enumerate(curves):
        timepoints = curve.get("timepoints", [])
        values = curve.get("values", [])
        name = curve.get("name", f"Curve {i+1}")
        curve_type = curve.get("curve_type", "data")
        color_index = curve.get("color_index", i)
        color = curve.get("color", colors[color_index % len(colors)])

        if normalize and values:
            min_val = min(values)
            max_val = max(values)
            if max_val > min_val:
                values = [(v - min_val) / (max_val - min_val) for v in values]

        if curve_type == "fit":
            # Fit curves: solid lines, no markers
            fig.add_trace(go.Scatter(
                x=timepoints,
                y=values,
                mode="lines",
                name=name,
                line=dict(color=color, width=2),
                showlegend=False,  # Don't clutter legend with fit lines
            ))
        else:
            # Data curves: markers only
            fig.add_trace(go.Scatter(
                x=timepoints,
                y=values,
                mode="markers",
                name=name,
                marker=dict(color=color, size=6, opacity=0.8),
            ))

    fig.update_layout(
        title=dict(text=title, x=0.5),
        xaxis_title="Time (min)",
        yaxis_title="Normalized" if normalize else "Fluorescence (RFU)",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
        ),
        margin=dict(l=60, r=20, t=60, b=40),
        hovermode="x unified",
    )

    apply_plotly_theme(fig, dark_mode=dark_mode)
    return fig


def create_panel_plot(
    panels: List[List[Dict[str, Any]]],
    layout: str = "single",
    show_fit: bool = True,
    show_residuals: bool = False,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a panel-based plot for comparing wells.

    Args:
        panels: List of panels, each containing list of curve dicts with:
            - timepoints: List[float]
            - values: List[float]
            - fit_values: Optional[List[float]]
            - name: str
            - color_index: int
        layout: "single", "2-panel", or "4-panel"
        show_fit: Whether to show fit lines
        show_residuals: Whether to show residuals (only for single panel with one curve)

    Returns:
        Plotly figure
    """
    # Aesthetically pleasing color palette
    colors = [
        "#1f77b4",  # muted blue
        "#ff7f0e",  # safety orange
        "#2ca02c",  # cooked asparagus green
        "#d62728",  # brick red
        "#9467bd",  # muted purple
        "#8c564b",  # chestnut brown
        "#e377c2",  # raspberry yogurt pink
        "#7f7f7f",  # middle gray
        "#bcbd22",  # curry yellow-green
        "#17becf",  # blue-teal
    ]

    # Determine grid layout
    if layout == "single" or len(panels) == 1:
        base_rows, cols = 1, 1
        n_panels = 1
    elif layout == "2-panel":
        base_rows, cols = 1, 2
        n_panels = 2
    else:  # 4-panel
        base_rows, cols = 2, 2
        n_panels = 4

    # Pad panels list if needed
    while len(panels) < n_panels:
        panels.append([])

    # Check if any panel has fit data for residuals
    has_fit_data = any(
        any(c.get("fit_values") for c in panel_curves)
        for panel_curves in panels[:n_panels]
        if panel_curves
    )
    can_show_residuals = show_residuals and has_fit_data

    # Create subplots - double rows if showing residuals
    if can_show_residuals:
        rows = base_rows * 2
        # Build row heights: alternating 0.7, 0.3 for each panel row
        row_heights = []
        for _ in range(base_rows):
            row_heights.extend([0.7, 0.3])

        # Build subplot titles
        subplot_titles = []
        for i in range(n_panels):
            subplot_titles.append(f"Panel {i+1}")
            subplot_titles.append("")  # Residuals row has no title

        fig = make_subplots(
            rows=rows,
            cols=cols,
            row_heights=row_heights,
            vertical_spacing=0.06,
            horizontal_spacing=0.1,
            subplot_titles=subplot_titles,
        )
    else:
        rows = base_rows
        subplot_titles = [f"Panel {i+1}" for i in range(n_panels)]
        fig = make_subplots(
            rows=rows,
            cols=cols,
            subplot_titles=subplot_titles[:n_panels],
            horizontal_spacing=0.1,
            vertical_spacing=0.15,
        )

    # Add traces to each panel
    for panel_idx, panel_curves in enumerate(panels[:n_panels]):
        if can_show_residuals:
            # With residuals: panel i is at row (i // cols) * 2 + 1
            base_row = (panel_idx // cols) * 2 + 1
            col = panel_idx % cols + 1
            row = base_row
            residual_row = base_row + 1
        else:
            row = panel_idx // cols + 1
            col = panel_idx % cols + 1
            residual_row = None

        if not panel_curves:
            # Empty panel - add annotation
            fig.add_annotation(
                text="Click wells to add",
                xref=f"x{panel_idx + 1 if panel_idx > 0 else ''} domain",
                yref=f"y{panel_idx + 1 if panel_idx > 0 else ''} domain",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=12, color="gray"),
            )
            continue

        for curve in panel_curves:
            timepoints = curve.get("timepoints", [])
            values = curve.get("values", [])
            fit_values = curve.get("fit_values")
            name = curve.get("name", "")
            color_index = curve.get("color_index", 0)
            color = colors[color_index % len(colors)]

            # Data points (markers)
            fig.add_trace(
                go.Scatter(
                    x=timepoints,
                    y=values,
                    mode="markers",
                    name=name,
                    marker=dict(color=color, size=5, opacity=0.8),
                    showlegend=(panel_idx == 0),  # Only show legend for first panel
                ),
                row=row, col=col,
            )

            # Fit line
            if show_fit and fit_values:
                fig.add_trace(
                    go.Scatter(
                        x=timepoints,
                        y=fit_values,
                        mode="lines",
                        name=f"{name} fit",
                        line=dict(color=color, width=2),
                        showlegend=False,
                    ),
                    row=row, col=col,
                )

                # Add residuals if enabled
                if can_show_residuals and residual_row and len(values) == len(fit_values):
                    residuals = [v - f for v, f in zip(values, fit_values)]
                    fig.add_trace(
                        go.Scatter(
                            x=timepoints,
                            y=residuals,
                            mode="markers",
                            name=f"{name} residuals",
                            marker=dict(color=color, size=4, opacity=0.7),
                            showlegend=False,
                        ),
                        row=residual_row, col=col,
                    )

        # Add zero line for this panel's residuals
        if can_show_residuals and residual_row:
            fig.add_hline(y=0, line_dash="dash", line_color="gray", row=residual_row, col=col)

    # Update layout
    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
        ),
        margin=dict(l=50, r=20, t=80, b=40),
        hovermode="closest",
    )

    # Update axes
    if can_show_residuals:
        for panel_idx in range(n_panels):
            main_row = (panel_idx // cols) * 2 + 1
            residual_row = main_row + 1
            col = panel_idx % cols + 1
            fig.update_xaxes(title_text="Time (min)", row=residual_row, col=col)
            fig.update_yaxes(title_text="RFU", row=main_row, col=col)
            fig.update_yaxes(title_text="Resid.", row=residual_row, col=col)
    else:
        for i in range(n_panels):
            fig.update_xaxes(title_text="Time (min)", row=i//cols+1, col=i%cols+1)
            fig.update_yaxes(title_text="RFU", row=i//cols+1, col=i%cols+1)

    apply_plotly_theme(fig, dark_mode=dark_mode)
    return fig
