"""Diagnostics panels, assumption tests, effect sizes, Q-Q plots, and warnings."""
from typing import Optional, List, Dict, Any, Union
import dash_mantine_components as dmc
from dash import html
from dash_iconify import DashIconify
import plotly.graph_objects as go
import numpy as np

from app.theme import apply_plotly_theme


def create_diagnostics_panel(
    n_chains: int,
    n_draws: int,
    divergent_count: int,
    duration_seconds: float,
    warnings: List[str],
) -> html.Div:
    """
    Create MCMC diagnostics panel.

    Args:
        n_chains: Number of chains
        n_draws: Number of draws
        divergent_count: Number of divergent transitions
        duration_seconds: Analysis duration
        warnings: List of warning messages

    Returns:
        Diagnostics panel component
    """
    # Determine status
    if divergent_count == 0 and not warnings:
        status_color = "green"
        status_text = "Good"
        status_icon = "mdi:check-circle"
    elif divergent_count > 0 and (n_chains * n_draws) > 0 and divergent_count / (n_chains * n_draws) < 0.01:
        status_color = "yellow"
        status_text = "Minor Issues"
        status_icon = "mdi:alert-circle"
    else:
        status_color = "red"
        status_text = "Issues Detected"
        status_icon = "mdi:close-circle"

    return html.Div([
        dmc.Group([
            DashIconify(icon=status_icon, color=status_color, width=24),
            dmc.Badge(status_text, color=status_color, size="lg"),
        ], gap="xs", mb="sm"),

        dmc.Stack([
            dmc.Group([
                dmc.Text("Chains:", size="sm", c="dimmed"),
                dmc.Text(str(n_chains), size="sm"),
            ], justify="space-between"),
            dmc.Group([
                dmc.Text("Draws:", size="sm", c="dimmed"),
                dmc.Text(str(n_draws), size="sm"),
            ], justify="space-between"),
            dmc.Group([
                dmc.Text("Divergences:", size="sm", c="dimmed"),
                dmc.Badge(
                    str(divergent_count),
                    color="green" if divergent_count == 0 else "red",
                    size="sm",
                ),
            ], justify="space-between"),
            dmc.Group([
                dmc.Text("Duration:", size="sm", c="dimmed"),
                dmc.Text(f"{duration_seconds/60:.1f} min", size="sm"),
            ], justify="space-between"),
        ], gap="xs"),

        html.Div([
            dmc.Divider(my="sm"),
            dmc.Text("Warnings", fw=500, size="sm", mb="xs"),
            html.Div([
                dmc.Alert(
                    children=w,
                    color="yellow",
                    icon=DashIconify(icon="mdi:alert"),
                    mb="xs",
                ) for w in warnings
            ]) if warnings else dmc.Text("No warnings", c="dimmed", size="sm"),
        ]) if warnings else None,
    ])


def create_correlations_panel(
    correlations: Dict[str, float],
) -> Union[dmc.Text, dmc.Stack]:
    """
    Create parameter correlations panel.

    Args:
        correlations: Dict mapping param pairs to correlation values

    Returns:
        Correlations panel component
    """
    if not correlations:
        return dmc.Text("No correlation data available", c="dimmed", ta="center")

    rows = []
    for params, corr in correlations.items():
        if isinstance(params, tuple):
            param1, param2 = params
        elif "_vs_" in params:
            param1, param2 = params.split("_vs_")
        else:
            # Split on last underscore if no "_vs_" found
            parts = params.rsplit("_", 1)
            param1, param2 = parts if len(parts) == 2 else (params, "?")

        corr_color = "green" if abs(corr) < 0.3 else ("yellow" if abs(corr) < 0.7 else "red")

        rows.append(
            dmc.Group([
                dmc.Text(f"{param1} \u2194 {param2}", size="sm"),
                dmc.Badge(f"{corr:.3f}", color=corr_color, size="sm"),
            ], justify="space-between")
        )

    return dmc.Stack(rows, gap="xs")


def create_icc_display(
    icc_session: float,
    icc_plate: float,
) -> html.Div:
    """
    Create ICC (intraclass correlation) display.

    Args:
        icc_session: ICC at session level
        icc_plate: ICC at plate level

    Returns:
        ICC display component
    """
    return html.Div([
        dmc.Text("Intraclass Correlations", fw=500, size="sm", mb="xs"),
        dmc.Stack([
            dmc.Group([
                dmc.Text("ICC (Session):", size="sm", c="dimmed"),
                dmc.Progress(
                    value=icc_session * 100,
                    color="blue",
                    size="sm",
                    style={"width": "60px"},
                ),
                dmc.Text(f"{icc_session:.2f}", size="sm"),
            ], justify="space-between"),
            dmc.Group([
                dmc.Text("ICC (Plate):", size="sm", c="dimmed"),
                dmc.Progress(
                    value=icc_plate * 100,
                    color="green",
                    size="sm",
                    style={"width": "60px"},
                ),
                dmc.Text(f"{icc_plate:.2f}", size="sm"),
            ], justify="space-between"),
        ], gap="xs"),
    ])


def create_empty_results_message() -> html.Div:
    """Create message for empty results state."""
    return html.Div([
        dmc.Alert(
            title="No Analysis Available",
            children="Run a Bayesian analysis to view posterior summaries and variance decomposition.",
            color="blue",
            icon=DashIconify(icon="mdi:information"),
        ),
    ], style={"marginTop": "20px"})


# =============================================================================
# Sprint 7: Statistical Diagnostics Components
# =============================================================================

def create_assumption_tests_display(
    normality_stat: float,
    normality_p: float,
    normality_pass: bool,
    homoscedasticity_stat: Optional[float] = None,
    homoscedasticity_p: Optional[float] = None,
    homoscedasticity_pass: Optional[bool] = None,
    durbin_watson: Optional[float] = None,
) -> html.Div:
    """
    Create assumption tests display panel.

    PRD Reference: Lines 8540-8542, T8.15-T8.16

    Args:
        normality_stat: Shapiro-Wilk statistic
        normality_p: Shapiro-Wilk p-value
        normality_pass: Whether normality test passed
        homoscedasticity_stat: Levene test statistic
        homoscedasticity_p: Levene test p-value
        homoscedasticity_pass: Whether homoscedasticity test passed
        durbin_watson: Durbin-Watson statistic for autocorrelation

    Returns:
        Assumption tests display component
    """
    tests = []

    # Normality test (Shapiro-Wilk)
    norm_icon = "mdi:check-circle" if normality_pass else "mdi:alert-circle"
    norm_color = "green" if normality_pass else "red"
    norm_text = "Normal" if normality_pass else "Non-normal"

    tests.append(
        dmc.Paper([
            dmc.Group([
                DashIconify(icon=norm_icon, color=norm_color, width=20),
                dmc.Text("Shapiro-Wilk Test", fw=500, size="sm"),
            ], gap="xs"),
            dmc.Divider(my="xs"),
            dmc.Stack([
                dmc.Group([
                    dmc.Text("Statistic:", size="xs", c="dimmed"),
                    dmc.Text(f"{normality_stat:.4f}", size="xs"),
                ], justify="space-between"),
                dmc.Group([
                    dmc.Text("p-value:", size="xs", c="dimmed"),
                    dmc.Badge(
                        f"{normality_p:.4f}",
                        color=norm_color,
                        size="xs",
                    ),
                ], justify="space-between"),
                dmc.Group([
                    dmc.Text("Result:", size="xs", c="dimmed"),
                    dmc.Badge(norm_text, color=norm_color, size="xs", variant="light"),
                ], justify="space-between"),
            ], gap=4),
        ], p="xs", withBorder=True, mb="xs")
    )

    # Homoscedasticity test (Levene)
    if homoscedasticity_stat is not None:
        homo_icon = "mdi:check-circle" if homoscedasticity_pass else "mdi:alert-circle"
        homo_color = "green" if homoscedasticity_pass else "red"
        homo_text = "Homoscedastic" if homoscedasticity_pass else "Heteroscedastic"

        tests.append(
            dmc.Paper([
                dmc.Group([
                    DashIconify(icon=homo_icon, color=homo_color, width=20),
                    dmc.Text("Levene's Test", fw=500, size="sm"),
                ], gap="xs"),
                dmc.Divider(my="xs"),
                dmc.Stack([
                    dmc.Group([
                        dmc.Text("Statistic:", size="xs", c="dimmed"),
                        dmc.Text(f"{homoscedasticity_stat:.4f}", size="xs"),
                    ], justify="space-between"),
                    dmc.Group([
                        dmc.Text("p-value:", size="xs", c="dimmed"),
                        dmc.Badge(
                            f"{homoscedasticity_p:.4f}",
                            color=homo_color,
                            size="xs",
                        ),
                    ], justify="space-between"),
                    dmc.Group([
                        dmc.Text("Result:", size="xs", c="dimmed"),
                        dmc.Badge(homo_text, color=homo_color, size="xs", variant="light"),
                    ], justify="space-between"),
                ], gap=4),
            ], p="xs", withBorder=True, mb="xs")
        )

    # Durbin-Watson (autocorrelation)
    if durbin_watson is not None:
        # DW close to 2 means no autocorrelation
        dw_pass = 1.5 < durbin_watson < 2.5
        dw_icon = "mdi:check-circle" if dw_pass else "mdi:alert-circle"
        dw_color = "green" if dw_pass else "yellow"

        tests.append(
            dmc.Paper([
                dmc.Group([
                    DashIconify(icon=dw_icon, color=dw_color, width=20),
                    dmc.Text("Durbin-Watson", fw=500, size="sm"),
                ], gap="xs"),
                dmc.Divider(my="xs"),
                dmc.Stack([
                    dmc.Group([
                        dmc.Text("Statistic:", size="xs", c="dimmed"),
                        dmc.Text(f"{durbin_watson:.3f}", size="xs"),
                    ], justify="space-between"),
                    dmc.Group([
                        dmc.Text("Interpretation:", size="xs", c="dimmed"),
                        dmc.Text(
                            "No autocorr." if dw_pass else "Check autocorr.",
                            size="xs",
                            c=dw_color,
                        ),
                    ], justify="space-between"),
                ], gap=4),
            ], p="xs", withBorder=True, mb="xs")
        )

    if not tests:
        return dmc.Text("No assumption test data available", c="dimmed", size="sm")

    return html.Div(tests)


def create_effect_size_display(
    effect_sizes: List[Dict[str, Any]],
) -> html.Div:
    """
    Create effect size display panel.

    PRD Reference: Lines 8545-8546, T8.20

    Args:
        effect_sizes: List of dicts with:
            - comparison: Comparison name
            - cohens_d: Cohen's d value
            - category: Effect size category
            - mean_diff: Mean difference

    Returns:
        Effect size display component
    """
    if not effect_sizes:
        return dmc.Text("No effect size data available", c="dimmed", size="sm")

    rows = []
    for es in effect_sizes:
        d = es.get("cohens_d", 0)
        category = es.get("category", "negligible")

        # Color based on effect size magnitude
        if abs(d) < 0.2:
            color = "gray"
        elif abs(d) < 0.5:
            color = "blue"
        elif abs(d) < 0.8:
            color = "yellow"
        else:
            color = "green"

        rows.append(
            dmc.Paper([
                dmc.Group([
                    dmc.Text(es.get("comparison", "Unknown"), size="sm", fw=500),
                    dmc.Badge(
                        category.capitalize(),
                        color=color,
                        size="xs",
                        variant="light",
                    ),
                ], justify="space-between"),
                dmc.Group([
                    dmc.Text("Cohen's d:", size="xs", c="dimmed"),
                    dmc.Text(f"{d:.3f}", size="xs", fw=500),
                ], justify="space-between", mt=4),
            ], p="xs", withBorder=True, mb="xs")
        )

    return html.Div([
        dmc.Text(
            "Cohen's d measures the magnitude of each construct's fold-change "
            "effect relative to the residual variability in the experiment. "
            "A larger d means the construct's signal is easier to distinguish "
            "from noise, regardless of statistical significance.",
            size="xs", c="dimmed", mb="sm",
        ),
        html.Div(rows),
        dmc.Paper([
            dmc.Text("Interpretation guide", size="xs", fw=500, mb=4),
            dmc.Text([
                dmc.Text("|d| < 0.2  ", size="xs", c="gray", span=True, ff="monospace"),
                dmc.Text("Negligible \u2014 effect is within noise", size="xs", span=True),
            ]),
            dmc.Text([
                dmc.Text("0.2 \u2013 0.5  ", size="xs", c="blue", span=True, ff="monospace"),
                dmc.Text("Small \u2014 detectable but modest", size="xs", span=True),
            ]),
            dmc.Text([
                dmc.Text("0.5 \u2013 0.8  ", size="xs", c="yellow.8", span=True, ff="monospace"),
                dmc.Text("Medium \u2014 clearly distinguishable from control", size="xs", span=True),
            ]),
            dmc.Text([
                dmc.Text("|d| > 0.8  ", size="xs", c="green", span=True, ff="monospace"),
                dmc.Text("Large \u2014 strong, robust effect", size="xs", span=True),
            ]),
        ], p="xs", withBorder=True, mt="sm"),
    ])


def create_corrected_pvalues_table(
    comparisons: List[Dict[str, Any]],
    method: str = "fdr",
) -> html.Div:
    """
    Create multiple comparison corrected p-values table.

    PRD Reference: Lines 8543-8544, T8.18-T8.19

    Args:
        comparisons: List of dicts with:
            - name: Comparison name
            - p_value: Original p-value
            - adjusted_p: Adjusted p-value (after correction)
            - significant: Whether significant after correction
        method: Correction method used

    Returns:
        Corrected p-values table component
    """
    if not comparisons:
        return dmc.Text("No p-value data available", c="dimmed", size="sm")

    method_names = {
        "none": "Uncorrected",
        "bonferroni": "Bonferroni",
        "holm": "Holm-Bonferroni",
        "fdr": "Benjamini-Hochberg (FDR)",
    }

    rows = []
    for comp in comparisons:
        p_orig = comp.get("p_value", 1.0)
        p_adj = comp.get("adjusted_p", p_orig)
        sig = comp.get("significant", False)

        rows.append(
            html.Tr([
                html.Td(comp.get("name", "Unknown")),
                html.Td(f"{p_orig:.4f}"),
                html.Td(
                    dmc.Badge(
                        f"{p_adj:.4f}",
                        color="green" if sig else "gray",
                        size="sm",
                    )
                ),
                html.Td(
                    dmc.Badge(
                        "Significant" if sig else "Not Sig.",
                        color="green" if sig else "gray",
                        size="sm",
                        variant="light",
                    )
                ),
            ])
        )

    n_sig = sum(1 for c in comparisons if c.get("significant", False))
    n_total = len(comparisons)

    return html.Div([
        dmc.Group([
            dmc.Text(f"Method: {method_names.get(method, method)}", size="sm", c="dimmed"),
            dmc.Badge(
                f"{n_sig}/{n_total} significant",
                color="blue" if n_sig > 0 else "gray",
                size="sm",
            ),
        ], justify="space-between", mb="sm"),

        dmc.Table(
            striped=True,
            highlightOnHover=True,
            children=[
                html.Thead(
                    html.Tr([
                        html.Th("Comparison"),
                        html.Th("p (orig)"),
                        html.Th("p (adj)"),
                        html.Th("Result"),
                    ])
                ),
                html.Tbody(rows),
            ],
        ),
    ])


def create_qq_plot_for_residuals(
    residuals: List[float],
    title: str = "Q-Q Plot (Residuals)",
    y_label: str = "Observed Quantiles",
    trace_name: str = "Residuals",
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create Q-Q plot for model residuals or log fold changes.

    PRD Reference: Lines 8542-8543, T8.17

    Args:
        residuals: Array of values to test
        title: Plot title
        y_label: Y-axis label
        trace_name: Legend label for data points

    Returns:
        Plotly figure
    """
    if not residuals or len(residuals) < 3:
        fig = go.Figure()
        fig.add_annotation(
            text="Insufficient data for Q-Q plot",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
        )
        fig.update_layout(height=250)
        apply_plotly_theme(fig, dark_mode=dark_mode)
        return fig

    residuals = np.asarray(residuals)
    residuals = residuals[~np.isnan(residuals)]
    sorted_resid = np.sort(residuals)
    n = len(sorted_resid)

    # Calculate theoretical quantiles
    try:
        from scipy import stats
        positions = (np.arange(1, n + 1) - 0.375) / (n + 0.25)
        theoretical = stats.norm.ppf(positions)
    except ImportError:
        # Approximate
        positions = (np.arange(1, n + 1) - 0.5) / n
        theoretical = np.sqrt(2) * np.sign(positions - 0.5) * np.sqrt(-np.log(2 * np.minimum(positions, 1 - positions)))

    fig = go.Figure()

    # Add data points
    fig.add_trace(go.Scatter(
        x=theoretical,
        y=sorted_resid,
        mode='markers',
        marker=dict(size=6, color='#228be6', opacity=0.7),
        name=trace_name,
        hovertemplate='Theoretical: %{x:.2f}<br>Observed: %{y:.3f}<extra></extra>',
    ))

    # Add reference line (through Q1 and Q3)
    q1_idx = int(n * 0.25)
    q3_idx = int(n * 0.75)
    if q3_idx > q1_idx:
        slope = (sorted_resid[q3_idx] - sorted_resid[q1_idx]) / (theoretical[q3_idx] - theoretical[q1_idx])
        intercept = sorted_resid[q1_idx] - slope * theoretical[q1_idx]
    else:
        slope, intercept = 1, 0

    line_x = [theoretical.min(), theoretical.max()]
    line_y = [intercept + slope * x for x in line_x]

    fig.add_trace(go.Scatter(
        x=line_x,
        y=line_y,
        mode='lines',
        line=dict(color='#fa5252', width=2, dash='dash'),
        name='Normal Reference',
    ))

    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor='center', font=dict(size=12)),
        xaxis_title='Expected Normal Quantiles',
        yaxis_title=y_label,
        height=280,
        margin=dict(l=50, r=30, t=40, b=40),
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0.5, xanchor='center'),
    )
    apply_plotly_theme(fig, dark_mode=dark_mode)

    return fig


def create_empty_diagnostics() -> dmc.Alert:
    """Create empty diagnostics placeholder."""
    return dmc.Alert(
        title="Statistical Diagnostics",
        children="Run an analysis to view statistical assumption tests, effect sizes, and multiple comparison corrections.",
        color="blue",
        icon=DashIconify(icon="mdi:information"),
    )


def create_diagnostics_warnings_panel(
    warnings: List[Dict[str, Any]],
) -> Union[html.Div, dmc.Alert]:
    """
    Create a single consolidated warnings panel for diagnostics issues.

    All warnings are rendered as items inside one Paper container with
    a summary header showing severity counts.

    Args:
        warnings: List of dicts with keys:
            - severity: "critical" | "warning" | "info"
            - title: Short title string
            - message: Plain-language explanation
            - guidance: Actionable recommendation

    Returns:
        Div containing a single panel, or empty Div if no warnings.
    """
    if not warnings:
        return html.Div()

    severity_config = {
        "critical": {"color": "red", "icon": "mdi:alert-octagon"},
        "warning": {"color": "yellow", "icon": "mdi:alert"},
        "info": {"color": "blue", "icon": "mdi:information"},
    }

    # Sort: critical first, then warning, then info
    order = {"critical": 0, "warning": 1, "info": 2}
    sorted_warnings = sorted(warnings, key=lambda w: order.get(w.get("severity", "info"), 3))

    # Count by severity for the header badges
    counts = {}
    for w in sorted_warnings:
        sev = w.get("severity", "info")
        counts[sev] = counts.get(sev, 0) + 1

    # Determine overall panel color from the worst severity present
    if counts.get("critical", 0) > 0:
        panel_color = "red"
    elif counts.get("warning", 0) > 0:
        panel_color = "yellow"
    else:
        panel_color = "blue"

    # Build summary badges
    badges = []
    for sev, label in [("critical", "Critical"), ("warning", "Warning"), ("info", "Note")]:
        if counts.get(sev, 0) > 0:
            badges.append(
                dmc.Badge(
                    f"{counts[sev]} {label}" if counts[sev] > 1 else label,
                    color=severity_config[sev]["color"],
                    size="sm",
                    variant="light",
                )
            )

    # Build individual warning items
    items = []
    for i, w in enumerate(sorted_warnings):
        sev = w.get("severity", "info")
        cfg = severity_config.get(sev, severity_config["info"])

        item_children = [
            dmc.Text(w.get("message", ""), size="sm"),
        ]

        guidance = w.get("guidance")
        if guidance:
            item_children.append(
                dmc.Paper([
                    dmc.Group([
                        DashIconify(icon="mdi:lightbulb-on-outline", width=16, color=cfg["color"]),
                        dmc.Text("Recommendation", size="xs", fw=600),
                    ], gap=6),
                    dmc.Text(guidance, size="xs", c="dimmed", mt=4),
                ], p="xs", mt="xs", withBorder=True, radius="sm",
                    style={"borderLeft": f"3px solid var(--mantine-color-{cfg['color']}-4)"}),
            )

        items.append(
            html.Div([
                dmc.Group([
                    DashIconify(icon=cfg["icon"], color=cfg["color"], width=18),
                    dmc.Text(w.get("title", "Issue"), size="sm", fw=600),
                    dmc.Badge(sev.capitalize(), color=cfg["color"], size="xs", variant="light"),
                ], gap="xs"),
                dmc.Stack(item_children, gap="xs", mt=4, ml=26),
                dmc.Divider(my="sm") if i < len(sorted_warnings) - 1 else None,
            ])
        )

    return dmc.Alert(
        title=dmc.Group([
            dmc.Text(f"{len(warnings)} Diagnostic Issue{'s' if len(warnings) != 1 else ''}", fw=600),
            dmc.Group(badges, gap=6),
        ], justify="space-between", style={"width": "100%"}),
        color=panel_color,
        icon=DashIconify(icon="mdi:stethoscope"),
        children=dmc.Stack(items, gap=0),
        mb="md",
    )
