"""
Power Analysis layout.

Phase C: UI Layer Completion

Provides:
- Pre-experiment sample size planning
- Mid-experiment precision dashboard
- Power curve visualization
- Sample size calculator with VIF adjustments

PRD References:
- Section 3.12: Power Analysis & Experiment Planning (F12.1-F12.8)
- F12.1: Pre-experiment planning with user-provided variance
- F12.2: Mid-experiment precision dashboard
- F12.6: Analytical SE formula
- F12.7: Variance-aware sample size estimation
"""
from typing import Optional, List, Dict, Any

import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify
import plotly.graph_objects as go
import numpy as np

from app.theme import apply_plotly_theme


def create_power_analysis_layout(
    project_id: Optional[int] = None,
) -> html.Div:
    """
    Create the power analysis layout.

    Phase C: UI Layer Completion (F12.1-F12.8)

    Args:
        project_id: Optional project ID

    Returns:
        Power analysis layout
    """
    return html.Div([
        # Stores
        dcc.Store(id="power-project-store", data=project_id),
        dcc.Store(id="power-mode-store", data="pre_experiment"),
        dcc.Store(id="power-params-store", data=None),
        dcc.Store(id="power-results-store", data=None),

        # Header
        dmc.Group([
            dmc.Group([
                DashIconify(
                    icon="mdi:chart-bell-curve",
                    width=28,
                    color="var(--mantine-color-blue-6)",
                ),
                dmc.Title("Power Analysis & Planning", order=2),
            ], gap="sm"),
            dmc.SegmentedControl(
                id="power-mode-control",
                data=[
                    {"value": "pre_experiment", "label": "Pre-Experiment"},
                    {"value": "mid_experiment", "label": "Mid-Experiment"},
                    {"value": "post_hoc", "label": "Post-Hoc"},
                ],
                value="pre_experiment",
            ),
        ], justify="space-between", mb="md"),

        # Mode description
        dmc.Alert(
            id="power-mode-description",
            title="Pre-Experiment Planning",
            children="Estimate required sample sizes based on expected effect sizes and variance from literature or pilot data.",
            color="blue",
            icon=DashIconify(icon="mdi:information"),
            mb="md",
        ),

        # Main content
        html.Div(id="power-content-container"),
    ])


def create_planning_section(
    mode: str = "pre_experiment",
    project_data: Optional[Dict[str, Any]] = None,
) -> dmc.Grid:
    """
    Create planning section based on experiment phase.

    PRD Ref: F12.1 (pre), F12.2 (mid), F12.5 (post)

    Args:
        mode: Planning mode ('pre_experiment', 'mid_experiment', 'post_hoc')
        project_data: Optional project data for mid/post modes

    Returns:
        Grid component with planning controls
    """
    if mode == "pre_experiment":
        return _create_pre_experiment_section()
    elif mode == "mid_experiment":
        return _create_mid_experiment_section(project_data)
    else:
        return _create_post_hoc_section(project_data)


def _create_pre_experiment_section() -> dmc.Grid:
    """Create pre-experiment planning section."""
    return dmc.Grid([
        # Left: Input parameters
        dmc.GridCol([
            dmc.Paper([
                dmc.Text("Variance Parameters", fw=500, mb="md"),
                dmc.Text(
                    "Enter expected variance components from literature or pilot data",
                    size="sm",
                    c="dimmed",
                    mb="md",
                ),

                # Variance inputs
                dmc.Stack([
                    dmc.NumberInput(
                        id="power-tau-session",
                        label="Session variance (τ²_session)",
                        description="Between-session variance",
                        value=0.04,
                        min=0.001,
                        max=1.0,
                        step=0.01,
                        decimalScale=3,
                    ),
                    dmc.NumberInput(
                        id="power-tau-plate",
                        label="Plate variance (τ²_plate)",
                        description="Between-plate variance within session",
                        value=0.02,
                        min=0.001,
                        max=1.0,
                        step=0.01,
                        decimalScale=3,
                    ),
                    dmc.NumberInput(
                        id="power-tau-residual",
                        label="Residual variance (τ²_residual)",
                        description="Within-plate variance",
                        value=0.01,
                        min=0.001,
                        max=1.0,
                        step=0.001,
                        decimalScale=3,
                    ),
                ], gap="md"),

                dmc.Divider(my="md"),

                # Target inputs
                dmc.Stack([
                    dmc.NumberInput(
                        id="power-target-ci",
                        label="Target CI width (±)",
                        description="Desired 95% confidence interval half-width",
                        value=0.3,
                        min=0.05,
                        max=1.0,
                        step=0.05,
                        decimalScale=2,
                    ),
                    dmc.NumberInput(
                        id="power-target-power",
                        label="Target power",
                        description="Probability of detecting true effect",
                        value=0.8,
                        min=0.5,
                        max=0.99,
                        step=0.05,
                        decimalScale=2,
                    ),
                    dmc.NumberInput(
                        id="power-effect-size",
                        label="Minimum detectable effect (fold-change)",
                        description="Smallest biologically meaningful difference",
                        value=0.5,
                        min=0.1,
                        max=5.0,
                        step=0.1,
                        decimalScale=2,
                    ),
                ], gap="md"),

                dmc.Button(
                    "Calculate Sample Size",
                    id="power-calculate-btn",
                    leftSection=DashIconify(icon="mdi:calculator"),
                    fullWidth=True,
                    mt="lg",
                ),
            ], p="md", withBorder=True),
        ], span=5),

        # Right: Results
        dmc.GridCol([
            # Sample size results
            dmc.Paper([
                dmc.Text("Recommended Sample Size", fw=500, mb="md"),
                html.Div(id="power-sample-size-result"),
            ], p="md", mb="md", withBorder=True),

            # Power curve
            dmc.Paper([
                dmc.Text("Power Curve", fw=500, mb="md"),
                dcc.Graph(
                    id="power-curve-graph",
                    config={"displayModeBar": False},
                    style={"height": "300px"},
                ),
            ], p="md", withBorder=True),
        ], span=7),
    ])


def _create_mid_experiment_section(
    project_data: Optional[Dict[str, Any]] = None,
) -> dmc.Grid:
    """Create mid-experiment planning section."""
    return dmc.Grid([
        # Left: Current precision status
        dmc.GridCol([
            dmc.Paper([
                dmc.Group([
                    dmc.Text("Current Precision Status", fw=500),
                    dmc.Badge(
                        id="power-precision-status-badge",
                        children="Loading...",
                        color="gray",
                    ),
                ], justify="space-between", mb="md"),
                html.Div(id="power-precision-table"),
            ], p="md", withBorder=True),
        ], span=7),

        # Right: Recommendations
        dmc.GridCol([
            # Quick recommendation
            dmc.Paper([
                dmc.Text("Recommendation", fw=500, mb="sm"),
                html.Div(id="power-recommendation-text"),
            ], p="md", mb="md", withBorder=True),

            # Co-plating suggestions
            dmc.Paper([
                dmc.Text("Co-Plating Opportunities", fw=500, mb="sm"),
                html.Div(id="power-coplating-suggestions"),
            ], p="md", withBorder=True),
        ], span=5),
    ])


def _create_post_hoc_section(
    project_data: Optional[Dict[str, Any]] = None,
) -> dmc.Grid:
    """Create post-hoc analysis section."""
    return dmc.Grid([
        # Achieved precision summary
        dmc.GridCol([
            dmc.Paper([
                dmc.Text("Achieved Precision Summary", fw=500, mb="md"),
                html.Div(id="power-achieved-precision"),
            ], p="md", withBorder=True),
        ], span=12),

        # Publication-ready summary
        dmc.GridCol([
            dmc.Paper([
                dmc.Text("Publication Summary", fw=500, mb="md"),
                dmc.Alert(
                    children="This summary can be included in your methods section.",
                    color="blue",
                    icon=DashIconify(icon="mdi:information"),
                    mb="md",
                ),
                html.Div(id="power-publication-summary"),
                dmc.Button(
                    "Copy to Clipboard",
                    id="power-copy-summary-btn",
                    leftSection=DashIconify(icon="mdi:content-copy"),
                    variant="light",
                    mt="md",
                ),
            ], p="md", withBorder=True),
        ], span=8),

        # Variance estimates
        dmc.GridCol([
            dmc.Paper([
                dmc.Text("Estimated Variance Components", fw=500, mb="md"),
                html.Div(id="power-variance-estimates"),
            ], p="md", withBorder=True),
        ], span=4),
    ])


def create_sample_size_calculator(
    comparison_type: str = "direct",
    current_variance: Optional[Dict[str, float]] = None,
) -> dmc.Paper:
    """
    Create sample size calculator component.

    PRD Ref: F12.6, F12.7 - Analytical SE formula, VIF adjustments

    Args:
        comparison_type: Type of comparison ('direct', 'indirect_via_wt', etc.)
        current_variance: Current variance estimates

    Returns:
        Calculator component
    """
    # VIF values for different comparison types
    vif_values = {
        "direct": 1.0,
        "indirect_via_wt": 1.414,  # sqrt(2)
        "indirect_via_unreg": 2.0,
        "indirect_four_hop": 4.0,
    }

    vif = vif_values.get(comparison_type, 1.0)

    return dmc.Paper([
        dmc.Text("Sample Size Calculator", fw=500, mb="md"),

        dmc.Grid([
            dmc.GridCol([
                dmc.Select(
                    id="power-calc-comparison-type",
                    label="Comparison Type",
                    data=[
                        {"value": "direct", "label": "Direct (VIF = 1.0)"},
                        {"value": "indirect_via_wt", "label": "Via Wild-type (VIF = √2)"},
                        {"value": "indirect_via_unreg", "label": "Via Unregulated (VIF = 2.0)"},
                        {"value": "indirect_four_hop", "label": "Four-hop (VIF = 4.0)"},
                    ],
                    value=comparison_type,
                ),
            ], span=6),
            dmc.GridCol([
                dmc.NumberInput(
                    id="power-calc-target-ci",
                    label="Target CI Width (±)",
                    value=0.3,
                    min=0.05,
                    max=2.0,
                    step=0.05,
                    decimalScale=2,
                ),
            ], span=6),
        ], mb="md"),

        # VIF explanation
        dmc.Alert(
            title=f"Variance Inflation Factor: {vif:.2f}",
            children=f"For {comparison_type.replace('_', ' ')} comparisons, you need approximately {vif**2:.1f}x more samples to achieve the same precision as direct comparisons.",
            color="blue" if vif == 1.0 else ("yellow" if vif < 2 else "orange"),
            icon=DashIconify(icon="mdi:information"),
            mb="md",
        ),

        # Results
        html.Div(id="power-calc-results"),

        dmc.Button(
            "Calculate",
            id="power-calc-btn",
            leftSection=DashIconify(icon="mdi:calculator"),
            mt="md",
        ),
    ], p="md", withBorder=True)


def create_power_curve_display(
    n_range: Optional[List[int]] = None,
    power_values: Optional[List[float]] = None,
    target_power: float = 0.8,
    effect_size: float = 0.5,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create power curve visualization.

    Args:
        n_range: Sample size range
        power_values: Corresponding power values
        target_power: Target power level (horizontal line)
        effect_size: Effect size being detected

    Returns:
        Plotly figure
    """
    fig = go.Figure()

    if n_range is None or power_values is None:
        # Generate example curve
        n_range = list(range(3, 31))
        # Simulated power curve (sigmoid-like)
        power_values = [1 - np.exp(-0.2 * n) for n in n_range]

    # Power curve
    fig.add_trace(go.Scatter(
        x=n_range,
        y=power_values,
        mode="lines",
        name=f"Power (effect = {effect_size})",
        line=dict(color="#228be6", width=3),
        fill="tozeroy",
        fillcolor="rgba(34, 139, 230, 0.1)",
    ))

    # Target power line
    fig.add_hline(
        y=target_power,
        line_dash="dash",
        line_color="#fa5252",
        annotation_text=f"Target ({target_power:.0%})",
        annotation_position="right",
    )

    # Find intersection
    for i, p in enumerate(power_values):
        if p >= target_power:
            fig.add_vline(
                x=n_range[i],
                line_dash="dot",
                line_color="#40c057",
                annotation_text=f"n = {n_range[i]}",
                annotation_position="top",
            )
            break

    fig.update_layout(
        xaxis_title="Sample Size (n)",
        yaxis_title="Power",
        yaxis_range=[0, 1.05],
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
        ),
        margin=dict(l=50, r=20, t=40, b=50),
        hovermode="x unified",
    )

    apply_plotly_theme(fig, dark_mode)
    return fig


def create_sample_size_result(
    n_sessions: int,
    n_plates_per_session: int,
    n_replicates_per_plate: int,
    total_n: int,
    ci_width: float,
    power: float,
) -> dmc.Stack:
    """
    Create sample size result display.

    PRD Ref: F12.6 - Analytical SE formula

    Args:
        n_sessions: Number of sessions
        n_plates_per_session: Plates per session
        n_replicates_per_plate: Replicates per plate
        total_n: Total sample size
        ci_width: Achieved CI width
        power: Achieved power

    Returns:
        Result display component
    """
    return dmc.Stack([
        # Key metrics
        dmc.SimpleGrid(
            cols=3,
            children=[
                dmc.Paper([
                    dmc.Text("Sessions", size="xs", c="dimmed"),
                    dmc.Text(str(n_sessions), size="xl", fw=700),
                ], p="sm", withBorder=True, ta="center"),
                dmc.Paper([
                    dmc.Text("Plates/Session", size="xs", c="dimmed"),
                    dmc.Text(str(n_plates_per_session), size="xl", fw=700),
                ], p="sm", withBorder=True, ta="center"),
                dmc.Paper([
                    dmc.Text("Reps/Plate", size="xs", c="dimmed"),
                    dmc.Text(str(n_replicates_per_plate), size="xl", fw=700),
                ], p="sm", withBorder=True, ta="center"),
            ],
        ),

        # Summary
        dmc.Alert(
            title=f"Total: {total_n} replicates",
            children=f"This design achieves ±{ci_width:.2f} CI width with {power:.0%} power.",
            color="green",
            icon=DashIconify(icon="mdi:check-circle"),
        ),

        # Formula reference
        dmc.Accordion([
            dmc.AccordionItem([
                dmc.AccordionControl("SE Formula"),
                dmc.AccordionPanel([
                    dmc.Code(
                        "SE(μ) = √[τ²_session/n_s + τ²_plate/(n_s·n_p) + τ²_residual/(n_s·n_p·n_r)]",
                        block=True,
                    ),
                    dmc.Text(
                        "CI width ≈ 3.92 × SE(μ)",
                        size="sm",
                        c="dimmed",
                        mt="xs",
                    ),
                ]),
            ], value="formula"),
        ]),
    ], gap="md")


def create_power_analysis_skeleton() -> html.Div:
    """Create skeleton for loading state."""
    return html.Div([
        dmc.Group([
            dmc.Skeleton(height=32, width=250),
            dmc.Skeleton(height=36, width=300, radius="md"),
        ], justify="space-between", mb="md"),

        dmc.Skeleton(height=60, width="100%", radius="md", mb="md"),

        dmc.Grid([
            dmc.GridCol([
                dmc.Paper([
                    dmc.Skeleton(height=24, width=150, mb="md"),
                    dmc.Skeleton(height=36, width="100%", mb="md"),
                    dmc.Skeleton(height=36, width="100%", mb="md"),
                    dmc.Skeleton(height=36, width="100%", mb="md"),
                ], p="md", withBorder=True),
            ], span=5),
            dmc.GridCol([
                dmc.Paper([
                    dmc.Skeleton(height=24, width=200, mb="md"),
                    dmc.Skeleton(height=120, width="100%"),
                ], p="md", withBorder=True, mb="md"),
                dmc.Paper([
                    dmc.Skeleton(height=24, width=100, mb="md"),
                    dmc.Skeleton(height=250, width="100%"),
                ], p="md", withBorder=True),
            ], span=7),
        ]),
    ])
