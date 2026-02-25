"""Posterior, frequentist, and comparison result tables; info/control panels."""
from typing import Optional, List, Dict, Any, Union
import dash_mantine_components as dmc
from dash import html
from dash_iconify import DashIconify
import plotly.graph_objects as go
import numpy as np

from app.theme import apply_plotly_theme
from app.layouts.analysis_results.components import get_ligand_condition_badge


def create_posterior_table(
    posteriors: List[Dict[str, Any]],
    selected_param: str = "log_fc_fmax",
) -> Union[dmc.Table, dmc.Text]:
    """
    Create the posterior summary table.

    Args:
        posteriors: List of posterior summaries with keys:
            - construct_name, mean, std, ci_lower, ci_upper, r_hat, ess_bulk, prob_meaningful
        selected_param: Parameter to display

    Returns:
        Table component
    """
    import numpy as np
    if not posteriors:
        return dmc.Text("No analysis results available", c="dimmed", ta="center")

    # Check if this is a log-scale parameter (needs FC conversion)
    is_log_param = selected_param in ("log_fc_fmax", "log_fc_kobs")

    # Check if any posteriors have ligand conditions
    has_ligand = any(p.get("ligand_condition") for p in posteriors)

    rows = []
    for p in posteriors:
        # Determine status colors
        r_hat = p.get("r_hat", None)
        r_hat_color = "green" if r_hat and r_hat < 1.01 else ("yellow" if r_hat and r_hat < 1.05 else "red")

        ess = p.get("ess_bulk", None)
        ess_color = "green" if ess and ess > 400 else ("yellow" if ess and ess > 100 else "red")

        ci_width = p.get("ci_upper", 0) - p.get("ci_lower", 0)
        ci_color = "green" if ci_width < 0.3 else ("yellow" if ci_width < 0.5 else "red")

        prob = p.get("prob_meaningful", None)

        # Get log-scale values
        log_mean = p.get('mean', 0)
        log_ci_lower = p.get('ci_lower', 0)
        log_ci_upper = p.get('ci_upper', 0)

        # Convert to actual FC if log parameter
        if is_log_param:
            actual_fc = np.exp(log_mean)
            actual_ci_lower = np.exp(log_ci_lower)
            actual_ci_upper = np.exp(log_ci_upper)
            fc_cell = html.Td(
                dmc.Tooltip(
                    dmc.Text(f"{actual_fc:.2f}x", fw=500),
                    label=f"CI: [{actual_ci_lower:.2f}x, {actual_ci_upper:.2f}x]",
                    withArrow=True,
                )
            )
        else:
            # For delta_tlag, show as-is (already in real units)
            fc_cell = html.Td(
                dmc.Text(f"{log_mean:.2f} min", fw=500)
            )

        # Ligand condition cell
        ligand_cells = []
        if has_ligand:
            ligand_cells.append(html.Td(get_ligand_condition_badge(p.get("ligand_condition"))))

        rows.append(
            html.Tr([
                html.Td(p.get("construct_name", "Unknown")),
                *ligand_cells,
                fc_cell,
                html.Td(f"{log_mean:.3f}"),
                html.Td(f"{p.get('std', 0):.3f}"),
                html.Td(
                    dmc.Badge(
                        f"[{log_ci_lower:.2f}, {log_ci_upper:.2f}]",
                        color=ci_color,
                        size="sm",
                        variant="light",
                    )
                ),
                html.Td(
                    dmc.Badge(
                        f"{r_hat:.3f}" if r_hat else "N/A",
                        color=r_hat_color,
                        size="sm",
                    ) if r_hat else "-"
                ),
                html.Td(
                    dmc.Badge(
                        f"{ess:.0f}" if ess else "N/A",
                        color=ess_color,
                        size="sm",
                    ) if ess else "-"
                ),
                html.Td(
                    dmc.Badge(
                        f"{prob*100:.1f}%" if prob is not None else "N/A",
                        color="blue" if prob and prob > 0.95 else "gray",
                        size="sm",
                        variant="light",
                    ) if prob is not None else "-"
                ),
            ])
        )

    # Adjust headers based on parameter type
    if is_log_param:
        value_header = "Fold Change"
        log_header = "log(FC)"
    else:
        value_header = "\u0394t_lag"
        log_header = "Value"

    # Build headers
    header_cells = [html.Th("Construct")]
    if has_ligand:
        header_cells.append(html.Th("Condition"))
    header_cells.extend([
        html.Th(value_header),
        html.Th(log_header),
        html.Th("SD"),
        html.Th("95% CI (log)"),
        html.Th("R-hat"),
        html.Th("ESS"),
        html.Th("P(|FC|>\u03b8)"),
    ])

    return dmc.Table(
        striped=True,
        highlightOnHover=True,
        children=[
            html.Thead(html.Tr(header_cells)),
            html.Tbody(rows),
        ],
    )


def create_frequentist_table(
    estimates: List[Dict[str, Any]],
    selected_param: str = "log_fc_fmax",
    warnings: Optional[List[str]] = None,
) -> Union[html.Div, dmc.Text]:
    """
    Create the frequentist estimate summary table.

    Args:
        estimates: List of frequentist estimates with keys:
            - construct_name, mean, std, ci_lower, ci_upper
        selected_param: Parameter to display
        warnings: Optional list of convergence warnings to display below table

    Returns:
        Table component (wrapped in Div with potential warning)
    """
    if not estimates:
        return dmc.Text("No frequentist results available", c="dimmed", ta="center")

    # Check if this is a log-scale parameter (needs FC conversion)
    is_log_param = selected_param in ("log_fc_fmax", "log_fc_kobs")

    # Check if any estimates have ligand conditions
    has_ligand = any(p.get("ligand_condition") for p in estimates)

    # Threshold for detecting unrealistic results
    # For log FC: CI width > 10 means exp(10) = 22000x range - unrealistic
    # For delta_tlag: CI width > 100 minutes is unrealistic
    max_reasonable_width = 10.0 if is_log_param else 100.0

    rows = []
    has_unrealistic = False

    for p in estimates:
        ci_width = abs(p.get("ci_upper", 0) - p.get("ci_lower", 0))
        std = p.get('std', 0)

        # Detect unrealistic results
        is_unrealistic = ci_width > max_reasonable_width or std > 1000

        if is_unrealistic:
            has_unrealistic = True
            ci_color = "red"
        else:
            ci_color = "green" if ci_width < 0.3 else ("yellow" if ci_width < 0.5 else "red")

        # Get values
        log_mean = p.get('mean', 0)
        log_ci_lower = p.get('ci_lower', 0)
        log_ci_upper = p.get('ci_upper', 0)

        # Convert to actual FC if log parameter
        if is_log_param:
            if is_unrealistic:
                fc_cell = html.Td(
                    dmc.Tooltip(
                        dmc.Text("FAILED", c="red", fw=500),
                        label="Model produced unrealistic estimates",
                        withArrow=True,
                    )
                )
            else:
                actual_fc = np.exp(log_mean)
                actual_ci_lower = np.exp(log_ci_lower)
                actual_ci_upper = np.exp(log_ci_upper)
                fc_cell = html.Td(
                    dmc.Tooltip(
                        dmc.Text(f"{actual_fc:.2f}x", fw=500),
                        label=f"CI: [{actual_ci_lower:.2f}x, {actual_ci_upper:.2f}x]",
                        withArrow=True,
                    )
                )
        else:
            if is_unrealistic:
                fc_cell = html.Td(dmc.Text("FAILED", c="red", fw=500))
            else:
                fc_cell = html.Td(dmc.Text(f"{log_mean:.2f} min", fw=500))

        # Determine significance based on whether CI includes zero
        if is_unrealistic:
            sig_badge = dmc.Badge("Failed", color="red", size="sm", variant="light")
        else:
            is_significant = (log_ci_lower > 0) or (log_ci_upper < 0)
            sig_badge = dmc.Badge(
                "Sig" if is_significant else "NS",
                color="blue" if is_significant else "gray",
                size="sm",
                variant="light",
            )

        # Format CI display
        if is_unrealistic:
            ci_display = dmc.Badge("Unrealistic", color="red", size="sm", variant="light")
        else:
            ci_display = dmc.Badge(
                f"[{log_ci_lower:.2f}, {log_ci_upper:.2f}]",
                color=ci_color,
                size="sm",
                variant="light",
            )

        row_style = {"backgroundColor": "rgba(255, 100, 100, 0.1)"} if is_unrealistic else {}

        # Ligand condition cell
        ligand_cells = []
        if has_ligand:
            ligand_cells.append(html.Td(get_ligand_condition_badge(p.get("ligand_condition"))))

        rows.append(
            html.Tr([
                html.Td(p.get("construct_name", "Unknown")),
                *ligand_cells,
                fc_cell,
                html.Td(f"{log_mean:.3f}" if not is_unrealistic else "\u2014"),
                html.Td(f"{std:.3f}" if std < 1000 else "\u2014"),
                html.Td(ci_display),
                html.Td(sig_badge),
            ], style=row_style)
        )

    # Adjust headers based on parameter type
    if is_log_param:
        value_header = "Fold Change"
        log_header = "log(FC)"
    else:
        value_header = "\u0394t_lag"
        log_header = "Value"

    # Build header cells
    header_cells = [html.Th("Construct")]
    if has_ligand:
        header_cells.append(html.Th("Condition"))
    header_cells.extend([
        html.Th(value_header),
        html.Th(log_header),
        html.Th("SE"),
        html.Th("95% CI"),
        html.Th("Status"),
    ])

    result = []

    # Add warning if any results are unrealistic
    if has_unrealistic:
        result.append(
            dmc.Alert(
                title="Frequentist Model Failed",
                color="red",
                children=dmc.Stack([
                    dmc.Text(
                        "One or more estimates have unrealistic confidence intervals, "
                        "indicating the REML model failed to converge properly.",
                        size="sm",
                    ),
                    dmc.Text(
                        "This typically occurs when variance components are near zero "
                        "(singular covariance). The Bayesian estimates should be preferred.",
                        size="sm",
                        c="dimmed",
                    ),
                ], gap="xs"),
                mb="md",
            )
        )

    result.append(
        dmc.Table(
            striped=True,
            highlightOnHover=True,
            children=[
                html.Thead(html.Tr(header_cells)),
                html.Tbody(rows),
            ],
        )
    )

    # Add convergence warnings below the table if provided
    if warnings:
        result.append(
            dmc.Alert(
                title="Convergence Warnings",
                color="yellow",
                children=dmc.Stack([
                    dmc.Text("The frequentist model encountered the following issues:", size="sm"),
                    dmc.List([
                        dmc.ListItem(dmc.Text(w, size="xs")) for w in warnings[:5]
                    ], size="sm", withPadding=True),
                ], gap="xs"),
                mt="md",
            )
        )

    return html.Div(result)


def create_comparison_table(
    bayesian: List[Dict[str, Any]],
    frequentist: List[Dict[str, Any]],
    selected_param: str = "log_fc_fmax",
) -> Union[html.Div, dmc.Text]:
    """
    Create side-by-side comparison table of Bayesian and Frequentist results.

    Args:
        bayesian: List of Bayesian posteriors
        frequentist: List of frequentist estimates
        selected_param: Parameter to display

    Returns:
        Comparison table component with disagreement highlighting
    """
    if not bayesian and not frequentist:
        return dmc.Text("No analysis results available", c="dimmed", ta="center")

    # Create lookup for frequentist results by (construct_id, ligand_condition)
    freq_lookup = {
        (str(p.get("construct_id")), p.get("ligand_condition")): p
        for p in frequentist
    }

    is_log_param = selected_param in ("log_fc_fmax", "log_fc_kobs")

    # Check if any results have ligand conditions
    has_ligand = any(p.get("ligand_condition") for p in bayesian)

    rows = []
    disagreements = []
    missing_freq_constructs = []

    for bp in bayesian:
        construct_id = str(bp.get("construct_id"))
        ligand_condition = bp.get("ligand_condition")
        construct_name = bp.get("construct_name", "Unknown")
        fp = freq_lookup.get((construct_id, ligand_condition), {})

        # Track constructs missing frequentist results
        if not fp and construct_name not in missing_freq_constructs:
            missing_freq_constructs.append(construct_name)

        # Bayesian values
        b_mean = bp.get('mean', 0)
        b_ci_lower = bp.get('ci_lower', 0)
        b_ci_upper = bp.get('ci_upper', 0)
        b_prob_meaningful = bp.get('prob_meaningful')

        # Frequentist values
        f_mean = fp.get('mean', None)
        f_ci_lower = fp.get('ci_lower', None)
        f_ci_upper = fp.get('ci_upper', None)
        f_std = fp.get('std', 0)

        # Detect unrealistic frequentist results
        max_reasonable_width = 10.0 if is_log_param else 100.0
        f_ci_width = abs(f_ci_upper - f_ci_lower) if f_ci_lower is not None and f_ci_upper is not None else 0
        freq_is_unrealistic = f_ci_width > max_reasonable_width or f_std > 1000

        # Check for disagreement
        has_disagreement = False
        disagreement_reason = None

        if freq_is_unrealistic:
            has_disagreement = True
            disagreement_reason = "Frequentist model failed (unrealistic CI)"
        elif f_mean is not None:
            # Point estimate difference > 20%
            if b_mean != 0 and abs(f_mean - b_mean) / abs(b_mean) > 0.20:
                has_disagreement = True
                disagreement_reason = "Point estimates differ by >20%"

            # Sign disagreement
            if (b_mean > 0 and f_mean < 0) or (b_mean < 0 and f_mean > 0):
                has_disagreement = True
                disagreement_reason = "Direction of effect disagrees"

            # CI overlap check
            if f_ci_lower is not None and f_ci_upper is not None:
                # Check if CIs don't overlap
                if b_ci_upper < f_ci_lower or f_ci_upper < b_ci_lower:
                    has_disagreement = True
                    disagreement_reason = "Confidence/credible intervals do not overlap"

        if has_disagreement:
            disagreements.append((construct_name, disagreement_reason))

        # Use red background for failed frequentist, yellow for other disagreements
        if freq_is_unrealistic:
            row_style = {"backgroundColor": "rgba(255, 100, 100, 0.15)"}
        elif has_disagreement:
            row_style = {"backgroundColor": "rgba(255, 200, 100, 0.15)"}
        else:
            row_style = {}

        # Format fold changes
        if is_log_param:
            b_fc = np.exp(b_mean)
            b_fc_text = f"{b_fc:.2f}x"
            if freq_is_unrealistic:
                f_fc_text = "FAILED"
            elif f_mean is not None:
                f_fc = np.exp(f_mean)
                f_fc_text = f"{f_fc:.2f}x"
            else:
                f_fc_text = "\u2014"
        else:
            b_fc_text = f"{b_mean:.2f} min"
            if freq_is_unrealistic:
                f_fc_text = "FAILED"
            elif f_mean is not None:
                f_fc_text = f"{f_mean:.2f} min"
            else:
                f_fc_text = "\u2014"

        # Bayesian significance (based on prob_meaningful)
        b_sig = "\u2014"
        if b_prob_meaningful is not None:
            if b_prob_meaningful > 0.95:
                b_sig = dmc.Badge("Strong", color="green", size="xs")
            elif b_prob_meaningful > 0.80:
                b_sig = dmc.Badge("Moderate", color="yellow", size="xs")
            else:
                b_sig = dmc.Badge("Weak", color="gray", size="xs")

        # Frequentist significance
        if freq_is_unrealistic:
            f_sig = dmc.Badge("Failed", color="red", size="xs")
        elif f_ci_lower is not None and f_ci_upper is not None:
            is_sig = (f_ci_lower > 0) or (f_ci_upper < 0)
            f_sig = dmc.Badge("Sig" if is_sig else "NS", color="blue" if is_sig else "gray", size="xs")
        else:
            f_sig = "\u2014"

        # Format frequentist CI
        if freq_is_unrealistic:
            f_ci_text = "Unrealistic"
        elif f_ci_lower is not None and f_ci_upper is not None:
            f_ci_text = f"{f_ci_lower:.2f}, {f_ci_upper:.2f}"
        else:
            f_ci_text = "\u2014"

        # Ligand condition cell
        ligand_cells = []
        if has_ligand:
            ligand_cells.append(html.Td(get_ligand_condition_badge(ligand_condition)))

        rows.append(
            html.Tr([
                html.Td(construct_name),
                *ligand_cells,
                html.Td(b_fc_text),
                html.Td(f"{b_ci_lower:.2f}, {b_ci_upper:.2f}"),
                html.Td(b_sig),
                html.Td(f_fc_text, style={"color": "red"} if freq_is_unrealistic else {}),
                html.Td(f_ci_text, style={"color": "red"} if freq_is_unrealistic else {}),
                html.Td(f_sig),
                html.Td(
                    DashIconify(icon="mdi:alert", color="orange", width=16) if has_disagreement else ""
                ),
            ], style=row_style)
        )

    # Build result
    result = []

    # Warning panel if there are disagreements
    if disagreements:
        result.append(
            dmc.Alert(
                title="Method Disagreement Detected",
                color="yellow",
                children=dmc.Stack([
                    dmc.Text(
                        f"{len(disagreements)} construct(s) show disagreement between Bayesian and Frequentist methods:",
                        size="sm",
                    ),
                    dmc.List([
                        dmc.ListItem(
                            dmc.Text(f"{name}: {reason}", size="xs"),
                            icon=DashIconify(icon="mdi:alert-circle", color="orange", width=14),
                        )
                        for name, reason in disagreements[:5]  # Show max 5
                    ], size="sm", withPadding=True),
                    dmc.Text(
                        "Consider checking model assumptions or data quality for these constructs.",
                        size="xs",
                        c="dimmed",
                    ),
                ], gap="xs"),
                mb="md",
            )
        )

    # Banner for constructs missing frequentist results
    if missing_freq_constructs:
        result.append(
            dmc.Alert(
                title="Partial Frequentist Results",
                color="blue",
                children=dmc.Stack([
                    dmc.Text(
                        f"{len(missing_freq_constructs)} construct(s) have no matching frequentist "
                        f"estimates (model may not have converged or was not run for these entries). "
                        f"Bayesian results are shown alone for these constructs.",
                        size="sm",
                    ),
                    dmc.List([
                        dmc.ListItem(dmc.Text(name, size="xs"))
                        for name in missing_freq_constructs[:5]
                    ], size="sm", withPadding=True),
                ], gap="xs"),
                mb="md",
            )
        )

    # Table
    result.append(
        dmc.Table(
            striped=True,
            highlightOnHover=True,
            children=[
                html.Thead([
                    html.Tr([
                        html.Th("", rowSpan=2),
                        *([html.Th("Condition", rowSpan=2)] if has_ligand else []),
                        html.Th("Bayesian", colSpan=3, style={"textAlign": "center", "backgroundColor": "rgba(59, 130, 246, 0.1)"}),
                        html.Th("Frequentist", colSpan=3, style={"textAlign": "center", "backgroundColor": "rgba(34, 197, 94, 0.1)"}),
                        html.Th("", rowSpan=2),
                    ]),
                    html.Tr([
                        html.Th("Estimate"),
                        html.Th("95% CI"),
                        html.Th("Evidence"),
                        html.Th("Estimate"),
                        html.Th("95% CI"),
                        html.Th("Sig"),
                    ]),
                ]),
                html.Tbody(rows),
            ],
        )
    )

    return html.Div(result)


def create_method_info_panel(
    method: str,
    has_frequentist: bool = True,
    frequentist_warnings: Optional[List[str]] = None,
) -> html.Div:
    """
    Create the method information panel with guidelines and warnings.

    Args:
        method: Selected method ("bayesian", "frequentist", or "comparison")
        has_frequentist: Whether frequentist results are available
        frequentist_warnings: List of frequentist convergence warnings

    Returns:
        Info panel component
    """
    if method == "bayesian":
        return dmc.Alert(
            title="Bayesian Analysis",
            color="blue",
            children=dmc.Stack([
                dmc.Text(
                    "Results show posterior distributions from Markov Chain Monte Carlo (MCMC) sampling.",
                    size="sm",
                ),
                dmc.List([
                    dmc.ListItem("R-hat < 1.01: Good chain convergence", icon=DashIconify(icon="mdi:check", color="green", width=14)),
                    dmc.ListItem("ESS > 400: Sufficient effective samples", icon=DashIconify(icon="mdi:check", color="green", width=14)),
                    dmc.ListItem("P(|FC|>\u03b8): Probability of meaningful effect", icon=DashIconify(icon="mdi:information", color="blue", width=14)),
                ], size="sm", withPadding=True),
            ], gap="xs"),
            mb="md",
        )

    elif method == "frequentist":
        if not has_frequentist:
            return dmc.Alert(
                title="Frequentist Results Not Available",
                color="red",
                children=dmc.Text(
                    "Frequentist analysis was not run or failed. Check analysis logs for details.",
                    size="sm",
                ),
                mb="md",
            )

        # Note: Convergence warnings are now shown in the frequentist table section
        # to reduce clutter in the info panel

        return html.Div([
            dmc.Alert(
                title="Frequentist Analysis (REML)",
                color="blue",
                children=dmc.Stack([
                    dmc.Text(
                        "Results from Restricted Maximum Likelihood (REML) mixed-effects model.",
                        size="sm",
                    ),
                    dmc.List([
                        dmc.ListItem("SE: Standard error of the estimate", icon=DashIconify(icon="mdi:information", color="blue", width=14)),
                        dmc.ListItem("95% CI: Confidence interval (Wald-type)", icon=DashIconify(icon="mdi:information", color="blue", width=14)),
                        dmc.ListItem("Sig: Whether CI excludes zero", icon=DashIconify(icon="mdi:information", color="blue", width=14)),
                    ], size="sm", withPadding=True),
                    dmc.Divider(my="xs"),
                    dmc.Text("Interpretation notes:", size="sm", fw=500),
                    dmc.List([
                        dmc.ListItem(
                            "Frequentist CIs are based on asymptotic normality assumptions",
                            icon=DashIconify(icon="mdi:alert-circle-outline", color="gray", width=14),
                        ),
                        dmc.ListItem(
                            "With small samples, Bayesian credible intervals may be more reliable",
                            icon=DashIconify(icon="mdi:alert-circle-outline", color="gray", width=14),
                        ),
                        dmc.ListItem(
                            "Singular covariance warnings indicate near-zero variance components",
                            icon=DashIconify(icon="mdi:alert-circle-outline", color="gray", width=14),
                        ),
                    ], size="xs", withPadding=True),
                ], gap="xs"),
                mb="md",
            ),
        ])

    elif method == "comparison":
        return dmc.Alert(
            title="Method Comparison",
            color="violet",
            children=dmc.Stack([
                dmc.Text(
                    "Side-by-side comparison of Bayesian and Frequentist estimates.",
                    size="sm",
                ),
                dmc.Text("When methods agree:", size="sm", fw=500),
                dmc.List([
                    dmc.ListItem("Both methods find similar effect sizes and directions", icon=DashIconify(icon="mdi:check-circle", color="green", width=14)),
                    dmc.ListItem("Confidence in the results is strengthened", icon=DashIconify(icon="mdi:check-circle", color="green", width=14)),
                ], size="sm", withPadding=True),
                dmc.Text("When methods disagree:", size="sm", fw=500),
                dmc.List([
                    dmc.ListItem("Yellow highlighting indicates potential issues", icon=DashIconify(icon="mdi:alert", color="orange", width=14)),
                    dmc.ListItem("Check for small sample sizes or outliers", icon=DashIconify(icon="mdi:alert", color="orange", width=14)),
                    dmc.ListItem("Bayesian results are generally more robust with limited data", icon=DashIconify(icon="mdi:information", color="blue", width=14)),
                ], size="sm", withPadding=True),
            ], gap="xs"),
            mb="md",
        )

    return html.Div()


def create_probability_display(
    construct_name: str,
    prob_direction: float,
    prob_meaningful: float,
    threshold: float,
) -> html.Div:
    """
    Create probability display for selected construct.

    Args:
        construct_name: Name of selected construct
        prob_direction: P(FC > 0 | data)
        prob_meaningful: P(|FC| > threshold | data)
        threshold: Fold change threshold

    Returns:
        Probability display component
    """
    return html.Div([
        dmc.Text(f"Selected: {construct_name}", fw=500, size="sm", mb="xs"),
        dmc.Stack([
            dmc.Group([
                dmc.Text("P(FC > 0):", size="sm", c="dimmed"),
                dmc.Text(f"{prob_direction*100:.1f}%", size="sm", fw=500),
            ], justify="space-between"),
            dmc.Group([
                dmc.Text(f"P(|FC| > {threshold:.1f}):", size="sm", c="dimmed"),
                dmc.Text(f"{prob_meaningful*100:.1f}%", size="sm", fw=500),
            ], justify="space-between"),
        ], gap="xs"),
        dmc.Progress(
            value=prob_meaningful * 100,
            color="blue" if prob_meaningful > 0.95 else ("yellow" if prob_meaningful > 0.80 else "gray"),
            size="lg",
            mt="sm",
        ),
    ])


def create_variance_pie_chart(
    var_session: Optional[float],
    var_plate: Optional[float],
    var_residual: Optional[float],
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create variance decomposition pie chart.

    Only shows components that were actually estimated (non-None).
    Adapts to the model tier used (e.g., Tier 1 only has residual).

    Args:
        var_session: Session-level variance (None if not in model)
        var_plate: Plate-level variance (None if not in model)
        var_residual: Residual variance

    Returns:
        Plotly figure
    """
    # Build lists of only estimated components
    labels = []
    values = []
    colors_list = []

    color_map = {
        "Session": "#228be6",
        "Plate": "#40c057",
        "Residual": "#fab005",
    }

    if var_session is not None and var_session > 0:
        labels.append("Session")
        values.append(var_session)
        colors_list.append(color_map["Session"])

    if var_plate is not None and var_plate > 0:
        labels.append("Plate")
        values.append(var_plate)
        colors_list.append(color_map["Plate"])

    if var_residual is not None and var_residual > 0:
        labels.append("Residual")
        values.append(var_residual)
        colors_list.append(color_map["Residual"])

    # Handle case where no variance components are available
    if not values:
        fig = go.Figure()
        fig.add_annotation(
            text="No variance components estimated",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=12, color="gray"),
        )
        fig.update_layout(margin=dict(l=20, r=20, t=20, b=20))
        return fig

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        marker=dict(colors=colors_list),
        textinfo="percent",
        textposition="outside",
        hovertemplate="%{label}: %{value:.4f}<br>%{percent}<extra></extra>",
    )])

    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, x=0.5, xanchor="center"),
        margin=dict(l=20, r=20, t=20, b=40),
    )
    apply_plotly_theme(fig, dark_mode=dark_mode)

    return fig
