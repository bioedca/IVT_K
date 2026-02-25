"""Cross-family comparison tables and custom comparison result display."""
from typing import Optional, List, Dict, Any, Union
import dash_mantine_components as dmc
from dash import html
from dash_iconify import DashIconify

from app.layouts.analysis_results.components import get_vif_badge


# =============================================================================
# Sprint 3: Cross-Family Comparison Components (F13.14)
# =============================================================================

def create_cross_family_precomputed_table(
    comparisons: List[Dict[str, Any]],
) -> Union[dmc.Text, dmc.Table]:
    """
    Create table for pre-computed mutant vs unregulated comparisons.

    PRD Reference: F13.14 - Cross-family comparison tab

    Args:
        comparisons: List of dicts with:
            - test_name: Test construct name
            - control_name: Control construct name (unregulated)
            - fc: Fold change value
            - ci_lower: 95% CI lower bound
            - ci_upper: 95% CI upper bound
            - vif: Variance inflation factor
            - path_type: Path type string

    Returns:
        Table component
    """
    if not comparisons:
        return dmc.Text(
            "No pre-computed comparisons available. Run analysis to generate.",
            c="dimmed", ta="center"
        )

    rows = []
    for comp in comparisons:
        fc = comp.get("fc", 1.0)
        ci_lower = comp.get("ci_lower", 0)
        ci_upper = comp.get("ci_upper", 0)
        vif = comp.get("vif", 2.0)
        path_type = comp.get("path_type", "Two-hop")

        # CI width badge color
        ci_width = ci_upper - ci_lower
        ci_color = "green" if ci_width < 0.3 else ("yellow" if ci_width < 0.5 else "red")

        rows.append(
            html.Tr([
                html.Td(
                    dmc.Text(f"{comp.get('test_name', 'Unknown')} vs {comp.get('control_name', 'Unreg')}", size="sm")
                ),
                html.Td(
                    dmc.Group([
                        dmc.Text(f"{fc:.2f}", fw=500, size="sm"),
                        dmc.Badge(
                            f"[{ci_lower:.2f}, {ci_upper:.2f}]",
                            color=ci_color,
                            size="sm",
                            variant="light",
                        ),
                    ], gap="xs")
                ),
                html.Td(get_vif_badge(vif, path_type)),
            ])
        )

    return dmc.Table(
        striped=True,
        highlightOnHover=True,
        children=[
            html.Thead(
                html.Tr([
                    html.Th("Comparison"),
                    html.Th("Fold Change [95% CI]"),
                    html.Th("Path Type"),
                ])
            ),
            html.Tbody(rows),
        ],
    )


def create_cross_family_mutant_table(
    comparisons: List[Dict[str, Any]],
) -> Union[dmc.Text, dmc.Table]:
    """
    Create table for cross-family mutant-to-mutant comparisons.

    PRD Reference: F13.14 - Cross-family comparison tab

    Args:
        comparisons: List of dicts with:
            - mutant1_name: First mutant name
            - mutant1_family: First mutant family
            - mutant2_name: Second mutant name
            - mutant2_family: Second mutant family
            - fc: Fold change value
            - ci_lower: 95% CI lower bound
            - ci_upper: 95% CI upper bound
            - vif: Variance inflation factor (typically 4.0)

    Returns:
        Table component
    """
    if not comparisons:
        return dmc.Text(
            "No cross-family mutant comparisons available.",
            c="dimmed", ta="center"
        )

    rows = []
    for comp in comparisons:
        fc = comp.get("fc", 1.0)
        ci_lower = comp.get("ci_lower", 0)
        ci_upper = comp.get("ci_upper", 0)
        vif = comp.get("vif", 4.0)

        # CI width badge color
        ci_width = ci_upper - ci_lower
        ci_color = "green" if ci_width < 0.5 else ("yellow" if ci_width < 1.0 else "red")

        comparison_text = (
            f"{comp.get('mutant1_name', '?')} ({comp.get('mutant1_family', '?')}) vs "
            f"{comp.get('mutant2_name', '?')} ({comp.get('mutant2_family', '?')})"
        )

        rows.append(
            html.Tr([
                html.Td(dmc.Text(comparison_text, size="sm")),
                html.Td(
                    dmc.Group([
                        dmc.Text(f"{fc:.2f}", fw=500, size="sm"),
                        dmc.Badge(
                            f"[{ci_lower:.2f}, {ci_upper:.2f}]",
                            color=ci_color,
                            size="sm",
                            variant="light",
                        ),
                    ], gap="xs")
                ),
                html.Td(get_vif_badge(vif, "Four-hop")),
            ])
        )

    return dmc.Table(
        striped=True,
        highlightOnHover=True,
        children=[
            html.Thead(
                html.Tr([
                    html.Th("Comparison"),
                    html.Th("Fold Change [95% CI]"),
                    html.Th("Path Type"),
                ])
            ),
            html.Tbody(rows),
        ],
    )


def create_custom_comparison_result(
    result: Optional[Dict[str, Any]],
) -> Union[html.Div, dmc.Alert, dmc.Paper]:
    """
    Create display for custom comparison result.

    Args:
        result: Dict with:
            - test_name: Test construct name
            - control_name: Control construct name
            - fc: Fold change value
            - ci_lower: 95% CI lower bound
            - ci_upper: 95% CI upper bound
            - vif: Variance inflation factor
            - path_type: Path type string
            - path_description: Detailed path description
            - is_valid: Whether comparison is valid

    Returns:
        Result display component
    """
    if result is None:
        return html.Div()

    if not result.get("is_valid", True):
        return dmc.Alert(
            title="Comparison Not Available",
            children=result.get("error_message", "Unable to compute comparison between these constructs."),
            color="red",
            icon=DashIconify(icon="mdi:alert-circle"),
        )

    fc = result.get("fc", 1.0)
    ci_lower = result.get("ci_lower", 0)
    ci_upper = result.get("ci_upper", 0)
    vif = result.get("vif", 1.0)
    path_type = result.get("path_type", "Unknown")
    path_desc = result.get("path_description", "")

    # Determine precision color
    ci_width = ci_upper - ci_lower
    ci_color = "green" if ci_width < 0.3 else ("yellow" if ci_width < 0.5 else "red")

    return dmc.Paper([
        dmc.Group([
            dmc.Text(
                f"{result.get('test_name', '?')} vs {result.get('control_name', '?')}",
                fw=700, size="lg"
            ),
            get_vif_badge(vif, path_type),
        ], justify="space-between", mb="sm"),

        dmc.Divider(mb="sm"),

        dmc.Group([
            dmc.Stack([
                dmc.Text("Fold Change", size="xs", c="dimmed"),
                dmc.Text(f"{fc:.3f}", fw=700, size="xl"),
            ], gap=0, align="center"),

            dmc.Stack([
                dmc.Text("95% CI", size="xs", c="dimmed"),
                dmc.Badge(
                    f"[{ci_lower:.3f}, {ci_upper:.3f}]",
                    color=ci_color,
                    size="lg",
                ),
            ], gap=0, align="center"),

            dmc.Stack([
                dmc.Text("CI Width", size="xs", c="dimmed"),
                dmc.Text(f"\u00b1{ci_width/2:.3f}", size="lg", c=ci_color),
            ], gap=0, align="center"),
        ], justify="space-around", mb="md"),

        dmc.Divider(mb="sm"),

        dmc.Text("Comparison Path", size="sm", c="dimmed", mb="xs"),
        dmc.Text(path_desc, size="sm"),

        # Warning for high VIF
        dmc.Alert(
            children=f"VIF={vif:.2f}: Standard errors are inflated by {vif:.1f}x due to indirect comparison path.",
            color="orange" if vif > 2 else "yellow",
            icon=DashIconify(icon="mdi:alert"),
            variant="light",
            mt="md",
        ) if vif > 1.0 else None,
    ], p="md", withBorder=True, bg="gray.0")


def create_empty_cross_family() -> dmc.Alert:
    """Create empty cross-family comparison placeholder."""
    return dmc.Alert(
        title="Cross-Family Comparisons",
        children="Run an analysis to view cross-family comparisons through the unregulated reference.",
        color="blue",
        icon=DashIconify(icon="mdi:information"),
    )
