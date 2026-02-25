"""
Forest plot visualization components.

Phase 8.2-8.4: Forest & Violin Plots (F13.1-F13.9)

Provides:
- Interactive forest plot with VIF badges
- Hierarchical grouping by family
- Sort/group options
- Progress tracking visualization
"""
from typing import Dict, List, Any, Optional, Tuple
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

from app.theme import apply_plotly_theme


# VIF badge colors
VIF_COLORS = {
    1.0: "#40c057",    # Green - direct comparison
    1.414: "#fab005",  # Yellow - one hop (sqrt(2))
    2.0: "#fd7e14",    # Orange - two hops
    4.0: "#fa5252",    # Red - four hops
}


def get_vif_color(vif: float) -> str:
    """Get color for VIF value."""
    if vif <= 1.0:
        return VIF_COLORS[1.0]
    elif vif <= 1.5:
        return VIF_COLORS[1.414]
    elif vif <= 2.5:
        return VIF_COLORS[2.0]
    else:
        return VIF_COLORS[4.0]


def get_vif_label(vif: float) -> str:
    """Get label for VIF value."""
    if vif <= 1.0:
        return "Direct"
    elif vif <= 1.5:
        return "1-hop"
    elif vif <= 2.5:
        return "2-hop"
    else:
        return "4-hop"


def create_forest_plot(
    constructs: List[Dict[str, Any]],
    sort_by: str = "effect_size",
    group_by: Optional[str] = None,
    show_reference_line: bool = True,
    show_95_ci: bool = True,
    show_50_ci: bool = False,
    show_vif_badges: bool = True,
    title: Optional[str] = None,
    height: Optional[int] = None,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create an interactive forest plot with modern styling.

    Args:
        constructs: List of dicts with:
            - name: Construct name
            - family: Family name (optional)
            - mean: Point estimate (log fold change)
            - ci_lower: 95% CI lower bound
            - ci_upper: 95% CI upper bound
            - ci_50_lower: 50% CI lower bound (optional)
            - ci_50_upper: 50% CI upper bound (optional)
            - vif: Variance inflation factor
            - is_wt: Whether this is a wild-type
            - status: pending/complete/excluded (optional)
        sort_by: "effect_size", "alphabetical", "family", "precision"
        group_by: None or "family"
        show_reference_line: Show vertical line at FC=1 (log=0)
        show_95_ci: Show 95% confidence intervals
        show_50_ci: Show 50% confidence intervals (inner)
        show_vif_badges: Show VIF badges
        title: Optional chart title
        height: Figure height (auto-calculated if None)

    Returns:
        Plotly figure
    """
    if not constructs:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=14, color="#868e96"),
        )
        fig.update_layout(height=300)
        apply_plotly_theme(fig, dark_mode)
        return fig

    # Filter out excluded constructs
    active_constructs = [c for c in constructs if c.get("status") != "excluded"]

    # Sort constructs
    if sort_by == "effect_size":
        active_constructs = sorted(active_constructs, key=lambda x: abs(x.get("mean", 0)), reverse=True)
    elif sort_by == "alphabetical":
        active_constructs = sorted(active_constructs, key=lambda x: x.get("name", ""))
    elif sort_by == "family":
        active_constructs = sorted(active_constructs, key=lambda x: (x.get("family", ""), x.get("name", "")))
    elif sort_by == "precision":
        active_constructs = sorted(
            active_constructs,
            key=lambda x: (x.get("ci_upper", 0) - x.get("ci_lower", 0))
        )

    # Group by family if requested
    if group_by == "family":
        families = {}
        for c in active_constructs:
            family = c.get("family", "Unknown")
            if family not in families:
                families[family] = []
            families[family].append(c)

        # Reorder with family headers
        ordered_constructs = []
        for family in sorted(families.keys()):
            family_constructs = families[family]
            wts = [c for c in family_constructs if c.get("is_wt")]
            non_wts = [c for c in family_constructs if not c.get("is_wt")]
            ordered_constructs.extend(wts)
            ordered_constructs.extend(non_wts)
        active_constructs = ordered_constructs

    # Calculate figure height
    n_constructs = len(active_constructs)
    if height is None:
        height = max(350, n_constructs * 35 + 120)

    # Create figure
    fig = go.Figure()

    # Y positions (reversed so first item is at top)
    y_positions = list(range(n_constructs - 1, -1, -1))
    y_labels = [c.get("name", f"Construct {i}") for i, c in enumerate(active_constructs)]

    # Extract data
    ci_lower = [c.get("ci_lower", c.get("mean", 0)) for c in active_constructs]
    ci_upper = [c.get("ci_upper", c.get("mean", 0)) for c in active_constructs]
    means = [c.get("mean", 0) for c in active_constructs]

    # Add alternating row backgrounds for readability
    stripe_color = "rgba(255, 255, 255, 0.04)" if dark_mode else "rgba(0, 0, 0, 0.02)"
    shapes = []
    for i in range(n_constructs):
        if i % 2 == 0:
            shapes.append(dict(
                type="rect",
                x0=0, x1=1,
                xref="paper",
                y0=y_positions[i] - 0.4,
                y1=y_positions[i] + 0.4,
                fillcolor=stripe_color,
                line=dict(width=0),
                layer="below",
            ))

    # Add reference line at FC=1 (log=0)
    ref_line_color = "#495057" if dark_mode else "#dee2e6"
    if show_reference_line:
        fig.add_vline(
            x=0,
            line=dict(color=ref_line_color, width=2),
            layer="below",
        )
        # Add subtle shading for negative effects
        x_min = min(ci_lower) - 0.5 if ci_lower else -2
        shapes.append(dict(
            type="rect",
            x0=x_min, x1=0,
            y0=-0.5, y1=n_constructs - 0.5,
            fillcolor="rgba(250, 82, 82, 0.03)",
            line=dict(width=0),
            layer="below",
        ))
        # Add subtle shading for positive effects
        x_max = max(ci_upper) + 0.5 if ci_upper else 2
        shapes.append(dict(
            type="rect",
            x0=0, x1=x_max,
            y0=-0.5, y1=n_constructs - 0.5,
            fillcolor="rgba(64, 192, 87, 0.03)",
            line=dict(width=0),
            layer="below",
        ))

    # Color scheme based on effect direction and significance
    def get_effect_color(mean_val, ci_low, ci_high):
        """Get color based on effect direction and whether CI excludes 0."""
        ci_excludes_zero = (ci_low > 0) or (ci_high < 0)
        if not ci_excludes_zero:
            return "#adb5bd"  # Gray - not significant (CI includes 0)
        elif mean_val > 0:
            return "#2f9e44"  # Strong green - significant positive
        else:
            return "#e03131"  # Strong red - significant negative

    colors = [get_effect_color(means[i], ci_lower[i], ci_upper[i]) for i in range(n_constructs)]

    # Marker symbol based on ligand condition
    LIGAND_SYMBOLS = {
        None: "diamond",
        "+Lig": "circle",
        "-Lig": "square",
        "+Lig/-Lig": "star",
    }
    symbols = [
        LIGAND_SYMBOLS.get(c.get("ligand_condition"), "diamond")
        for c in active_constructs
    ]
    # Track which ligand conditions are present (for legend entries)
    ligand_conditions_present = {
        c.get("ligand_condition") for c in active_constructs
        if c.get("ligand_condition") is not None
    }

    # Add 95% CI as horizontal lines (whiskers)
    if show_95_ci:
        for i in range(n_constructs):
            # CI line
            fig.add_trace(go.Scatter(
                x=[ci_lower[i], ci_upper[i]],
                y=[y_positions[i], y_positions[i]],
                mode="lines",
                line=dict(color=colors[i], width=3),
                showlegend=False,
                hoverinfo="skip",
            ))
            # CI caps (whiskers)
            cap_height = 0.15
            fig.add_trace(go.Scatter(
                x=[ci_lower[i], ci_lower[i]],
                y=[y_positions[i] - cap_height, y_positions[i] + cap_height],
                mode="lines",
                line=dict(color=colors[i], width=2),
                showlegend=False,
                hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=[ci_upper[i], ci_upper[i]],
                y=[y_positions[i] - cap_height, y_positions[i] + cap_height],
                mode="lines",
                line=dict(color=colors[i], width=2),
                showlegend=False,
                hoverinfo="skip",
            ))

    # Add point estimates as diamonds
    # Calculate actual FC for hover
    actual_fc = [np.exp(m) for m in means]
    actual_ci_lower = [np.exp(cl) for cl in ci_lower]
    actual_ci_upper = [np.exp(cu) for cu in ci_upper]

    fig.add_trace(go.Scatter(
        x=means,
        y=y_positions,
        mode="markers",
        marker=dict(
            size=14,
            color=colors,
            symbol=symbols,
            line=dict(color="#1a1b1e" if dark_mode else "white", width=2),
        ),
        hovertemplate=(
            "<b>%{text}</b><br><br>"
            "<b>Fold Change:</b> %{customdata[3]:.2f}x<br>"
            "<b>95% CI:</b> [%{customdata[4]:.2f}x, %{customdata[5]:.2f}x]<br><br>"
            "<b>Log scale:</b> %{x:.3f}<br>"
            "<b>95% CI (log):</b> [%{customdata[0]:.3f}, %{customdata[1]:.3f}]"
            "<extra></extra>"
        ),
        text=y_labels,
        customdata=[
            [ci_lower[i], ci_upper[i], active_constructs[i].get("vif", 1.0),
             actual_fc[i], actual_ci_lower[i], actual_ci_upper[i]]
            for i in range(n_constructs)
        ],
        showlegend=False,
    ))

    # Add effect size annotations on the right
    annotations = []
    for i in range(n_constructs):
        fc_text = f"{actual_fc[i]:.2f}x"
        ci_text = f"[{actual_ci_lower[i]:.2f}, {actual_ci_upper[i]:.2f}]"
        annotations.append(dict(
            x=1.02,
            xref="paper",
            y=y_positions[i],
            text=f"<b>{fc_text}</b>",
            showarrow=False,
            font=dict(size=14, color=colors[i], family="monospace"),
            xanchor="left",
        ))

    # Add VIF badges if requested (further right)
    if show_vif_badges:
        for i, c in enumerate(active_constructs):
            vif = c.get("vif", 1.0)
            if vif > 1.0:  # Only show if VIF > 1
                vif_label = get_vif_label(vif)
                vif_color = get_vif_color(vif)
                annotations.append(dict(
                    x=1.14,
                    xref="paper",
                    y=y_positions[i],
                    text=f"<b>{vif_label}</b>",
                    showarrow=False,
                    font=dict(size=12, color=vif_color),
                    xanchor="left",
                ))

    # Add family separators if grouping
    if group_by == "family":
        current_family = None
        for i, c in enumerate(active_constructs):
            family = c.get("family", "Unknown")
            if family != current_family and current_family is not None:
                shapes.append(dict(
                    type="line",
                    x0=0, x1=1,
                    xref="paper",
                    y0=y_positions[i] + 0.5,
                    y1=y_positions[i] + 0.5,
                    line=dict(color="#adb5bd", width=1.5, dash="dot"),
                ))
            current_family = family

    fig.update_layout(shapes=shapes, annotations=annotations)

    # Color tokens
    text_primary = "#c1c2c5" if dark_mode else "#212529"
    text_secondary = "#909296" if dark_mode else "#495057"
    grid_color = "rgba(255,255,255,0.06)" if dark_mode else "rgba(0,0,0,0.05)"
    hover_bg = "#25262b" if dark_mode else "white"
    hover_border = "#495057" if dark_mode else "#dee2e6"

    # Update layout with modern styling
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=20, color=text_primary, family="Arial, sans-serif"),
            x=0.5,
            xanchor="center",
        ) if title else None,
        xaxis=dict(
            title=dict(
                text="log(Fold Change)",
                font=dict(size=16, color=text_secondary),
                standoff=10,
            ),
            zeroline=False,
            showgrid=True,
            gridcolor=grid_color,
            gridwidth=1,
            tickfont=dict(size=14, color=text_secondary),
        ),
        yaxis=dict(
            tickmode="array",
            tickvals=y_positions,
            ticktext=y_labels,
            autorange=True,
            tickfont=dict(size=14, color=text_primary),
            showgrid=False,
        ),
        height=height,
        margin=dict(l=220, r=140, t=80 if title else 50, b=70),
        hoverlabel=dict(
            bgcolor=hover_bg,
            bordercolor=hover_border,
            font=dict(size=14, color=text_primary),
        ),
    )

    # Add legend for color interpretation
    fig.add_trace(go.Scatter(
        x=[None], y=[None],
        mode="markers",
        marker=dict(size=12, color="#2f9e44", symbol="diamond"),
        name="Significant increase",
        showlegend=True,
    ))
    fig.add_trace(go.Scatter(
        x=[None], y=[None],
        mode="markers",
        marker=dict(size=12, color="#e03131", symbol="diamond"),
        name="Significant decrease",
        showlegend=True,
    ))
    fig.add_trace(go.Scatter(
        x=[None], y=[None],
        mode="markers",
        marker=dict(size=12, color="#adb5bd", symbol="diamond"),
        name="Not significant",
        showlegend=True,
    ))

    # Add ligand condition legend entries when conditions are present
    LIGAND_LEGEND = {
        "+Lig": ("circle", "#868e96", "+Lig"),
        "-Lig": ("square", "#868e96", "\u2212Lig"),
        "+Lig/-Lig": ("star", "#868e96", "Lig Effect"),
    }
    for cond in sorted(ligand_conditions_present):
        symbol, color, label = LIGAND_LEGEND.get(cond, ("diamond", "#adb5bd", cond))
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode="markers",
            marker=dict(size=12, color=color, symbol=symbol),
            name=label,
            showlegend=True,
        ))

    legend_bg = "rgba(26,27,30,0.9)" if dark_mode else "rgba(255,255,255,0.9)"
    fig.update_layout(
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=14),
            bgcolor=legend_bg,
        ),
    )

    apply_plotly_theme(fig, dark_mode)
    return fig


def create_snr_forest_plot(
    constructs: List[Dict[str, Any]],
    snr_thresholds: Dict[str, float] = None,
    title: str = "Signal-to-Noise Ratio by Construct",
    height: Optional[int] = None,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a forest plot showing SNR values with quality-based coloring.

    Args:
        constructs: List of dicts with:
            - name: Construct name
            - snr: Signal-to-noise ratio
            - snr_ci_lower: Optional CI lower
            - snr_ci_upper: Optional CI upper
        snr_thresholds: Quality thresholds (default: excellent=20, good=10, marginal=5)
        title: Chart title
        height: Figure height

    Returns:
        Plotly figure
    """
    if snr_thresholds is None:
        snr_thresholds = {"excellent": 20, "good": 10, "marginal": 5}

    if not constructs:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
        )
        return fig

    # Sort by SNR
    sorted_constructs = sorted(constructs, key=lambda x: x.get("snr", 0), reverse=True)

    n_constructs = len(sorted_constructs)
    if height is None:
        height = max(400, n_constructs * 25 + 100)

    y_positions = list(range(n_constructs - 1, -1, -1))
    y_labels = [c.get("name", f"Construct {i}") for i, c in enumerate(sorted_constructs)]
    snr_values = [c.get("snr", 0) for c in sorted_constructs]

    # Determine colors based on quality
    colors = []
    for snr in snr_values:
        if snr >= snr_thresholds["excellent"]:
            colors.append("#40c057")  # Green - excellent
        elif snr >= snr_thresholds["good"]:
            colors.append("#82c91e")  # Light green - good
        elif snr >= snr_thresholds["marginal"]:
            colors.append("#fab005")  # Yellow - marginal
        else:
            colors.append("#fa5252")  # Red - poor

    fig = go.Figure()

    # Add threshold lines
    for level, threshold in snr_thresholds.items():
        fig.add_vline(
            x=threshold,
            line=dict(color="gray", width=1, dash="dot"),
            annotation_text=level,
            annotation_position="top",
        )

    # Add bars
    fig.add_trace(go.Bar(
        y=y_positions,
        x=snr_values,
        orientation="h",
        marker=dict(color=colors),
        hovertemplate="<b>%{text}</b><br>SNR: %{x:.1f}<extra></extra>",
        text=y_labels,
    ))

    fig.update_layout(
        title=title,
        xaxis=dict(title="Signal-to-Noise Ratio"),
        yaxis=dict(
            tickmode="array",
            tickvals=y_positions,
            ticktext=y_labels,
        ),
        height=height,
        margin=dict(l=150, r=50, t=60, b=50),
    )

    apply_plotly_theme(fig, dark_mode)
    return fig


def create_dual_forest_plot(
    constructs: List[Dict[str, Any]],
    title: str = "Fold Change and SNR Comparison",
    height: Optional[int] = None,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a dual forest plot with FC on left and SNR on right.

    Args:
        constructs: List of dicts with mean, ci_lower, ci_upper, snr
        title: Chart title
        height: Figure height

    Returns:
        Plotly figure with two subplots
    """
    if not constructs:
        return go.Figure()

    n_constructs = len(constructs)
    if height is None:
        height = max(400, n_constructs * 30 + 100)

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Fold Change (log₂)", "Signal-to-Noise Ratio"),
        horizontal_spacing=0.15,
    )

    y_positions = list(range(n_constructs - 1, -1, -1))
    y_labels = [c.get("name", f"Construct {i}") for i, c in enumerate(constructs)]

    # Left subplot: Fold change
    means = [c.get("mean", 0) for c in constructs]
    ci_lower = [c.get("ci_lower", c.get("mean", 0)) for c in constructs]
    ci_upper = [c.get("ci_upper", c.get("mean", 0)) for c in constructs]
    vif_colors = [get_vif_color(c.get("vif", 1.0)) for c in constructs]

    fig.add_trace(
        go.Scatter(
            x=means,
            y=y_positions,
            mode="markers",
            marker=dict(size=10, color=vif_colors),
            error_x=dict(
                type="data",
                symmetric=False,
                array=[ci_upper[i] - means[i] for i in range(n_constructs)],
                arrayminus=[means[i] - ci_lower[i] for i in range(n_constructs)],
            ),
            showlegend=False,
        ),
        row=1, col=1
    )

    # Right subplot: SNR
    snr_values = [c.get("snr", 0) for c in constructs]
    snr_colors = []
    for snr in snr_values:
        if snr >= 20:
            snr_colors.append("#40c057")
        elif snr >= 10:
            snr_colors.append("#82c91e")
        elif snr >= 5:
            snr_colors.append("#fab005")
        else:
            snr_colors.append("#fa5252")

    fig.add_trace(
        go.Bar(
            y=y_positions,
            x=snr_values,
            orientation="h",
            marker=dict(color=snr_colors),
            showlegend=False,
        ),
        row=1, col=2
    )

    # Add reference line at FC=0
    fig.add_vline(x=0, line=dict(color="gray", dash="dash"), row=1, col=1)

    fig.update_layout(
        title=title,
        height=height,
        margin=dict(l=150, r=50, t=80, b=50),
    )

    # Update y-axes
    fig.update_yaxes(
        tickmode="array",
        tickvals=y_positions,
        ticktext=y_labels,
        row=1, col=1
    )
    fig.update_yaxes(
        tickmode="array",
        tickvals=y_positions,
        ticktext=[""] * n_constructs,  # Hide labels on right
        row=1, col=2
    )

    apply_plotly_theme(fig, dark_mode)
    return fig


def create_progress_forest_plot(
    history: List[Dict[str, Any]],
    construct_name: str,
    title: Optional[str] = None,
    height: int = 300,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a forest plot showing precision progress over time for a single construct.

    Args:
        history: List of dicts with date, mean, ci_lower, ci_upper
        construct_name: Name of the construct
        title: Optional title
        height: Figure height

    Returns:
        Plotly figure showing CI evolution
    """
    if not history:
        fig = go.Figure()
        fig.add_annotation(
            text="No history data",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
        )
        return fig

    # Sort by date
    sorted_history = sorted(history, key=lambda x: x.get("date", ""))

    dates = [h.get("date", f"Point {i}") for i, h in enumerate(sorted_history)]
    means = [h.get("mean", 0) for h in sorted_history]
    ci_lower = [h.get("ci_lower", h.get("mean", 0)) for h in sorted_history]
    ci_upper = [h.get("ci_upper", h.get("mean", 0)) for h in sorted_history]

    fig = go.Figure()

    # Add CI bands
    fig.add_trace(go.Scatter(
        x=dates + dates[::-1],
        y=ci_upper + ci_lower[::-1],
        fill="toself",
        fillcolor="rgba(64, 192, 87, 0.2)",
        line=dict(color="rgba(0,0,0,0)"),
        showlegend=False,
        hoverinfo="skip",
    ))

    # Add mean line
    fig.add_trace(go.Scatter(
        x=dates,
        y=means,
        mode="lines+markers",
        line=dict(color="#228be6", width=2),
        marker=dict(size=8),
        name="Mean",
        hovertemplate="Date: %{x}<br>Mean: %{y:.3f}<extra></extra>",
    ))

    # Add CI lines
    fig.add_trace(go.Scatter(
        x=dates,
        y=ci_upper,
        mode="lines",
        line=dict(color="#40c057", width=1, dash="dash"),
        name="95% CI",
    ))
    fig.add_trace(go.Scatter(
        x=dates,
        y=ci_lower,
        mode="lines",
        line=dict(color="#40c057", width=1, dash="dash"),
        showlegend=False,
    ))

    fig.update_layout(
        title=title or f"Precision Progress: {construct_name}",
        xaxis=dict(title="Date"),
        yaxis=dict(title="log₂(Fold Change)"),
        height=height,
        margin=dict(l=60, r=40, t=60, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )

    apply_plotly_theme(fig, dark_mode)
    return fig


def create_cross_project_forest_plot(
    projects: List[Dict[str, Any]],
    construct_identifier: str,
    parameter_type: str = "log_fc_fmax",
    show_summary: bool = True,
    title: Optional[str] = None,
    height: Optional[int] = None,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a forest plot comparing the same construct across multiple projects.

    Args:
        projects: List of dicts with:
            - project_name: Project name
            - mean: Point estimate
            - ci_lower: 95% CI lower bound
            - ci_upper: 95% CI upper bound
            - plate_count: Number of plates
            - replicate_count: Number of replicates
        construct_identifier: The construct being compared
        parameter_type: Parameter type for axis label
        show_summary: Show summary diamond at bottom (not pooled, descriptive only)
        title: Optional chart title
        height: Figure height (auto-calculated if None)

    Returns:
        Plotly figure

    PRD Reference: F20.2 - Side-by-side forest plot for same construct from different projects
    """
    if not projects:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available for comparison",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=14, color="gray"),
        )
        return fig

    # Sort by mean estimate (highest at top)
    sorted_projects = sorted(projects, key=lambda x: x.get("mean", 0), reverse=True)

    n_projects = len(sorted_projects)
    if height is None:
        height = max(300, n_projects * 50 + 150)

    fig = go.Figure()

    # Y positions (reversed so first item is at top)
    y_positions = list(range(n_projects - 1, -1, -1))

    # Project labels with sample info
    y_labels = [
        f"{p['project_name']} (n={p.get('replicate_count', 0)}, {p.get('plate_count', 0)} plates)"
        for p in sorted_projects
    ]

    # Add reference line at FC=1 (log2=0)
    fig.add_vline(
        x=0,
        line=dict(color="gray", width=1, dash="dash"),
        annotation_text="FC=1",
        annotation_position="top"
    )

    # Extract values
    means = [p.get("mean", 0) for p in sorted_projects]
    ci_lowers = [p.get("ci_lower", 0) for p in sorted_projects]
    ci_uppers = [p.get("ci_upper", 0) for p in sorted_projects]

    # Project colors - use a gradient based on position
    colors = ["#228be6", "#40c057", "#fab005", "#fa5252", "#be4bdb",
              "#15aabf", "#82c91e", "#fd7e14", "#e64980", "#7950f2"]

    # Main forest plot points with error bars
    fig.add_trace(go.Scatter(
        x=means,
        y=y_positions,
        mode="markers",
        marker=dict(
            size=12,
            color=[colors[i % len(colors)] for i in range(n_projects)],
            symbol="diamond"
        ),
        error_x=dict(
            type="data",
            symmetric=False,
            array=[u - m for u, m in zip(ci_uppers, means)],
            arrayminus=[m - l for m, l in zip(means, ci_lowers)],
            thickness=2,
            width=6,
            color="rgba(0,0,0,0.5)"
        ),
        name="95% CI",
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Mean: %{x:.3f}<br>"
            "95% CI: [%{customdata[1]:.3f}, %{customdata[2]:.3f}]<br>"
            "Plates: %{customdata[3]}<br>"
            "Replicates: %{customdata[4]}"
            "<extra></extra>"
        ),
        customdata=[
            [p["project_name"], p.get("ci_lower", 0), p.get("ci_upper", 0),
             p.get("plate_count", 0), p.get("replicate_count", 0)]
            for p in sorted_projects
        ]
    ))

    # Add text annotations for estimates
    annotations = []
    for i, p in enumerate(sorted_projects):
        annotations.append(dict(
            x=p.get("ci_upper", 0) + 0.05,
            y=y_positions[i],
            text=f"{p.get('mean', 0):.2f} [{p.get('ci_lower', 0):.2f}, {p.get('ci_upper', 0):.2f}]",
            showarrow=False,
            font=dict(size=10),
            xanchor="left"
        ))

    # Add summary diamond if requested and enough data
    if show_summary and len(sorted_projects) >= 2:
        all_means = [p.get("mean", 0) for p in sorted_projects]
        summary_mean = np.mean(all_means)
        summary_min = np.min(all_means)
        summary_max = np.max(all_means)
        total_replicates = sum(p.get("replicate_count", 0) for p in sorted_projects)

        # Summary row position
        summary_y = -1

        # Add summary diamond
        fig.add_trace(go.Scatter(
            x=[summary_mean],
            y=[summary_y],
            mode="markers",
            marker=dict(
                size=18,
                color="#fab005",
                symbol="diamond",
                line=dict(color="black", width=1)
            ),
            name="Cross-project mean",
            hovertemplate=(
                "<b>Cross-Project Summary</b><br>"
                f"Mean: {summary_mean:.3f}<br>"
                f"Range: [{summary_min:.3f}, {summary_max:.3f}]<br>"
                f"Projects: {len(sorted_projects)}<br>"
                f"Total replicates: {total_replicates}"
                "<extra></extra>"
            )
        ))

        # Add range line for summary
        fig.add_shape(
            type="line",
            x0=summary_min,
            x1=summary_max,
            y0=summary_y,
            y1=summary_y,
            line=dict(color="#fab005", width=3)
        )

        y_labels.append("Summary (descriptive)")
        y_positions.append(summary_y)

        annotations.append(dict(
            x=summary_max + 0.05,
            y=summary_y,
            text=f"{summary_mean:.2f} (range: {summary_max - summary_min:.2f})",
            showarrow=False,
            font=dict(size=10, color="#fab005"),
            xanchor="left"
        ))

    # Update layout with annotations
    fig.update_layout(annotations=annotations)

    # Parameter labels
    parameter_labels = {
        "log_fc_fmax": "log₂ FC(F_max)",
        "log_fc_kobs": "log₂ FC(k_obs)",
        "delta_tlag": "Δt_lag (min)"
    }
    x_label = parameter_labels.get(parameter_type, parameter_type)

    fig.update_layout(
        title=title or f"Cross-Project Comparison: {construct_identifier}",
        xaxis=dict(
            title=x_label,
            zeroline=True,
            zerolinecolor="gray",
            zerolinewidth=1,
        ),
        yaxis=dict(
            tickmode="array",
            tickvals=y_positions,
            ticktext=y_labels,
            autorange="reversed"
        ),
        height=height,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=250, r=180, t=80, b=50),
    )

    apply_plotly_theme(fig, dark_mode)
    return fig
