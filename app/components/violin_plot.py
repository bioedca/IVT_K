"""
Violin plot visualization components.

Phase 8.2-8.4: Forest & Violin Plots (F13.4-F13.6)

Provides:
- Violin plots for posterior distributions
- Completion matrix visualization
- Distribution comparison plots
"""
from typing import Dict, List, Any, Optional
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

from app.theme import apply_plotly_theme


def create_violin_plot(
    distributions: List[Dict[str, Any]],
    parameter: str = "log2_fc",
    show_box: bool = True,
    show_points: bool = False,
    title: Optional[str] = None,
    height: int = 400,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create violin plots for posterior distributions.

    Args:
        distributions: List of dicts with:
            - name: Construct/group name
            - samples: Array of MCMC samples
            - mean: Optional point estimate
            - ci_lower: Optional CI lower
            - ci_upper: Optional CI upper
        parameter: Parameter name for axis label
        show_box: Show box plot inside violin
        show_points: Show individual sample points
        title: Optional chart title
        height: Figure height

    Returns:
        Plotly figure
    """
    if not distributions:
        fig = go.Figure()
        fig.add_annotation(
            text="No distribution data",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
        )
        return fig

    fig = go.Figure()

    for i, dist in enumerate(distributions):
        name = dist.get("name", f"Group {i}")
        samples = dist.get("samples", [])

        if len(samples) == 0:
            continue

        # Determine points display
        if show_points:
            points = "all"
            jitter = 0.3
        else:
            points = False
            jitter = 0

        fig.add_trace(go.Violin(
            y=samples,
            name=name,
            box_visible=show_box,
            meanline_visible=True,
            points=points,
            jitter=jitter,
            pointpos=0,
            fillcolor=f"rgba(66, 133, 244, 0.5)",
            line_color="#228be6",
            hoverinfo="y+name",
        ))

    fig.update_layout(
        title=title,
        yaxis=dict(title=parameter),
        xaxis=dict(title="Construct"),
        height=height,
        margin=dict(l=60, r=40, t=60 if title else 40, b=80),
        showlegend=False,
        violinmode="group",
    )

    apply_plotly_theme(fig, dark_mode=dark_mode)
    return fig


def create_paired_violin_plot(
    groups: List[Dict[str, Any]],
    parameter: str = "log2_fc",
    title: Optional[str] = None,
    height: int = 400,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create paired violin plots comparing two conditions per group.

    Args:
        groups: List of dicts with:
            - name: Group name
            - condition_a: Dict with name, samples
            - condition_b: Dict with name, samples
        parameter: Parameter name for axis label
        title: Optional chart title
        height: Figure height

    Returns:
        Plotly figure
    """
    if not groups:
        fig = go.Figure()
        fig.add_annotation(
            text="No data",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
        )
        return fig

    fig = go.Figure()

    # Get condition names from first group
    cond_a_name = groups[0].get("condition_a", {}).get("name", "Condition A")
    cond_b_name = groups[0].get("condition_b", {}).get("name", "Condition B")

    for group in groups:
        name = group.get("name", "Unknown")
        cond_a = group.get("condition_a", {})
        cond_b = group.get("condition_b", {})

        samples_a = cond_a.get("samples", [])
        samples_b = cond_b.get("samples", [])

        if len(samples_a) > 0:
            fig.add_trace(go.Violin(
                y=samples_a,
                x=[name] * len(samples_a),
                name=cond_a_name,
                side="negative",
                line_color="#228be6",
                fillcolor="rgba(34, 139, 230, 0.5)",
                legendgroup=cond_a_name,
                showlegend=(name == groups[0].get("name")),
            ))

        if len(samples_b) > 0:
            fig.add_trace(go.Violin(
                y=samples_b,
                x=[name] * len(samples_b),
                name=cond_b_name,
                side="positive",
                line_color="#fa5252",
                fillcolor="rgba(250, 82, 82, 0.5)",
                legendgroup=cond_b_name,
                showlegend=(name == groups[0].get("name")),
            ))

    fig.update_layout(
        title=title,
        yaxis=dict(title=parameter),
        xaxis=dict(title="Group"),
        height=height,
        margin=dict(l=60, r=40, t=60 if title else 40, b=80),
        violingap=0,
        violinmode="overlay",
    )

    apply_plotly_theme(fig, dark_mode=dark_mode)
    return fig


def create_completion_matrix(
    constructs: List[Dict[str, Any]],
    sessions: List[str],
    title: str = "Precision Completion Matrix",
    height: Optional[int] = None,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a completion matrix showing precision status across sessions.

    Args:
        constructs: List of dicts with:
            - name: Construct name
            - sessions: Dict mapping session to status (complete/near/far/pending)
        sessions: List of session names (columns)
        title: Chart title
        height: Figure height

    Returns:
        Plotly figure
    """
    if not constructs or not sessions:
        fig = go.Figure()
        fig.add_annotation(
            text="No data",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
        )
        return fig

    # Status to numeric mapping
    status_map = {
        "complete": 3,
        "met": 3,
        "near": 2,
        "close": 2,
        "far": 1,
        "not_met": 1,
        "pending": 0,
        "excluded": -1,
    }

    # Create matrix
    n_constructs = len(constructs)
    n_sessions = len(sessions)

    z = np.zeros((n_constructs, n_sessions))
    hover_text = [[None for _ in range(n_sessions)] for _ in range(n_constructs)]

    for i, construct in enumerate(constructs):
        name = construct.get("name", f"Construct {i}")
        session_data = construct.get("sessions", {})

        for j, session in enumerate(sessions):
            status = session_data.get(session, "pending")
            z[i, j] = status_map.get(status, 0)
            hover_text[i][j] = f"{name}<br>Session: {session}<br>Status: {status}"

    # Custom colorscale
    colorscale = [
        [0.0, "#dee2e6"],    # Excluded
        [0.25, "#868e96"],   # Pending
        [0.5, "#fa5252"],    # Far
        [0.75, "#fab005"],   # Near
        [1.0, "#40c057"],    # Complete
    ]

    if height is None:
        height = max(400, n_constructs * 25 + 100)

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=sessions,
        y=[c.get("name", f"Construct {i}") for i, c in enumerate(constructs)],
        colorscale=colorscale,
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_text,
        showscale=True,
        colorbar=dict(
            title="Status",
            tickmode="array",
            tickvals=[-1, 0, 1, 2, 3],
            ticktext=["Excluded", "Pending", "Far", "Near", "Complete"],
            thickness=15,
        ),
        zmin=-1,
        zmax=3,
    ))

    fig.update_layout(
        title=title,
        xaxis=dict(title="Session", side="top"),
        yaxis=dict(title="Construct", autorange="reversed"),
        height=height,
        margin=dict(l=150, r=80, t=80, b=50),
    )

    apply_plotly_theme(fig, dark_mode=dark_mode)
    return fig


def create_distribution_comparison(
    construct_a: Dict[str, Any],
    construct_b: Dict[str, Any],
    parameter: str = "log2_fc",
    title: Optional[str] = None,
    height: int = 350,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a distribution comparison between two constructs.

    Args:
        construct_a: Dict with name, samples, mean, ci_lower, ci_upper
        construct_b: Dict with name, samples, mean, ci_lower, ci_upper
        parameter: Parameter name
        title: Optional title
        height: Figure height

    Returns:
        Plotly figure
    """
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=(construct_a.get("name", "A"), construct_b.get("name", "B")),
        horizontal_spacing=0.1,
    )

    for col, construct in enumerate([construct_a, construct_b], 1):
        samples = construct.get("samples", [])

        if len(samples) > 0:
            # Add histogram
            fig.add_trace(
                go.Histogram(
                    x=samples,
                    nbinsx=50,
                    name=construct.get("name", ""),
                    showlegend=False,
                    marker_color="#228be6" if col == 1 else "#fa5252",
                    opacity=0.7,
                ),
                row=1, col=col
            )

            # Add mean line
            mean = construct.get("mean", np.mean(samples))
            fig.add_vline(
                x=mean,
                line=dict(color="black", width=2),
                row=1, col=col
            )

            # Add CI lines
            ci_lower = construct.get("ci_lower", np.percentile(samples, 2.5))
            ci_upper = construct.get("ci_upper", np.percentile(samples, 97.5))
            fig.add_vline(
                x=ci_lower,
                line=dict(color="gray", width=1, dash="dash"),
                row=1, col=col
            )
            fig.add_vline(
                x=ci_upper,
                line=dict(color="gray", width=1, dash="dash"),
                row=1, col=col
            )

    fig.update_layout(
        title=title,
        height=height,
        margin=dict(l=50, r=50, t=80, b=50),
    )

    fig.update_xaxes(title_text=parameter, row=1, col=1)
    fig.update_xaxes(title_text=parameter, row=1, col=2)
    fig.update_yaxes(title_text="Count", row=1, col=1)

    apply_plotly_theme(fig, dark_mode=dark_mode)
    return fig


def create_qq_plot(
    samples: List[float],
    title: str = "Q-Q Plot (Normal)",
    height: int = 350,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a Q-Q plot comparing samples to normal distribution.

    Args:
        samples: Array of samples
        title: Chart title
        height: Figure height

    Returns:
        Plotly figure
    """
    if not samples or len(samples) < 3:
        fig = go.Figure()
        fig.add_annotation(
            text="Insufficient samples",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
        )
        return fig

    from scipy import stats

    # Compute theoretical quantiles
    sorted_samples = np.sort(samples)
    n = len(sorted_samples)
    theoretical_quantiles = stats.norm.ppf((np.arange(1, n + 1) - 0.5) / n)

    fig = go.Figure()

    # Add scatter points
    fig.add_trace(go.Scatter(
        x=theoretical_quantiles,
        y=sorted_samples,
        mode="markers",
        marker=dict(size=5, color="#228be6"),
        name="Samples",
    ))

    # Add reference line
    min_val = min(theoretical_quantiles.min(), sorted_samples.min())
    max_val = max(theoretical_quantiles.max(), sorted_samples.max())
    fig.add_trace(go.Scatter(
        x=[min_val, max_val],
        y=[min_val, max_val],
        mode="lines",
        line=dict(color="red", dash="dash"),
        name="Normal reference",
    ))

    fig.update_layout(
        title=title,
        xaxis=dict(title="Theoretical Quantiles"),
        yaxis=dict(title="Sample Quantiles"),
        height=height,
        margin=dict(l=60, r=40, t=60, b=50),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )

    apply_plotly_theme(fig, dark_mode=dark_mode)
    return fig


def create_residual_distribution(
    residuals: List[float],
    title: str = "Residual Distribution",
    height: int = 300,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a histogram of residuals with normal overlay.

    Args:
        residuals: Array of residuals
        title: Chart title
        height: Figure height

    Returns:
        Plotly figure
    """
    if not residuals:
        fig = go.Figure()
        fig.add_annotation(
            text="No residuals",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
        )
        return fig

    fig = go.Figure()

    # Add histogram
    fig.add_trace(go.Histogram(
        x=residuals,
        nbinsx=30,
        name="Residuals",
        marker_color="#228be6",
        opacity=0.7,
        histnorm="probability density",
    ))

    # Add normal curve overlay
    from scipy import stats
    x_range = np.linspace(min(residuals), max(residuals), 100)
    mu, std = np.mean(residuals), np.std(residuals)
    normal_pdf = stats.norm.pdf(x_range, mu, std)

    fig.add_trace(go.Scatter(
        x=x_range,
        y=normal_pdf,
        mode="lines",
        line=dict(color="red", width=2),
        name="Normal fit",
    ))

    fig.update_layout(
        title=title,
        xaxis=dict(title="Residual"),
        yaxis=dict(title="Density"),
        height=height,
        margin=dict(l=60, r=40, t=60, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )

    apply_plotly_theme(fig, dark_mode=dark_mode)
    return fig
