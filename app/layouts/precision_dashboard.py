"""
Precision Dashboard layout.

Phase 7.1: Precision Dashboard (F12.1)

Displays:
- Per-construct precision table (CI width, target, status)
- Precision progress chart over time
- Color-coded status badges
- Construct filter and sort options
- Co-plating recommendations
"""
from typing import Optional, List, Dict, Any
import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify
import plotly.graph_objects as go


def create_precision_dashboard_layout(
    project_id: Optional[int] = None,
) -> html.Div:
    """
    Create the precision dashboard layout.

    Args:
        project_id: Optional project ID

    Returns:
        Precision dashboard layout
    """
    return html.Div([
        # Stores
        dcc.Store(id="precision-project-store", data=project_id),
        dcc.Store(id="precision-data-store", data=None),
        dcc.Store(id="precision-target-store", data=0.3),  # Default CI width target
        dcc.Store(id="precision-override-construct-store", data=None),  # For override workflow

        # Header
        dmc.Group([
            dmc.Title("Precision Dashboard", order=2),
            dmc.Group([
                dmc.Badge(
                    id="precision-summary-badge",
                    children="0/0 at target",
                    color="gray",
                    size="lg",
                ),
                dmc.SegmentedControl(
                    id="precision-view-mode",
                    data=[
                        {"value": "simple", "label": "Simple"},
                        {"value": "advanced", "label": "Advanced"},
                    ],
                    value="simple",
                    size="xs",
                ),
            ]),
        ], justify="space-between", mb="md"),

        # Target configuration
        dmc.Paper([
            dmc.Grid([
                dmc.GridCol([
                    dmc.NumberInput(
                        id="precision-target-input",
                        label="CI Width Target (±)",
                        description="95% confidence interval half-width",
                        value=0.3,
                        min=0.05,
                        max=1.0,
                        step=0.05,
                        decimalScale=2,
                    )
                ], span=3),
                dmc.GridCol([
                    dmc.Select(
                        id="precision-family-filter",
                        label="Family",
                        placeholder="All families",
                        data=[],
                        clearable=True,
                    )
                ], span=3),
                dmc.GridCol([
                    dmc.Select(
                        id="precision-sort-by",
                        label="Sort By",
                        data=[
                            {"value": "name", "label": "Name"},
                            {"value": "ci_width", "label": "CI Width"},
                            {"value": "status", "label": "Status"},
                            {"value": "effective_n", "label": "Effective N"},
                        ],
                        value="ci_width",
                    )
                ], span=2),
                dmc.GridCol([
                    dmc.Checkbox(
                        id="precision-show-met-only",
                        label="Show only unmet",
                        checked=False,
                        mt="xl",
                    )
                ], span=2),
                dmc.GridCol([
                    dmc.Button(
                        "Refresh",
                        id="precision-refresh-btn",
                        leftSection=DashIconify(icon="mdi:refresh"),
                        variant="light",
                        mt="xl",
                    )
                ], span=2, style={"display": "flex", "alignItems": "flex-end"}),
            ]),
        ], p="md", mb="md", withBorder=True),

        # Main content
        dmc.Grid([
            # Left: Precision table
            dmc.GridCol([
                dmc.Paper([
                    dmc.Group([
                        dmc.Text("Construct Precision", fw=500),
                        dmc.ActionIcon(
                            DashIconify(icon="mdi:download"),
                            id="precision-export-btn",
                            variant="subtle",
                        ),
                    ], justify="space-between", mb="sm"),
                    dmc.ScrollArea([
                        html.Div(id="precision-table-container"),
                    ], h=500),
                ], p="md", withBorder=True),
            ], span=7),

            # Right: Summary and recommendations
            dmc.GridCol([
                # Overall progress
                dmc.Paper([
                    dmc.Text("Overall Progress", fw=500, mb="sm"),
                    html.Div(id="precision-overall-progress"),
                ], p="md", mb="md", withBorder=True),

                # Recommendations
                dmc.Paper([
                    dmc.Text("Recommendations", fw=500, mb="sm"),
                    html.Div(id="precision-recommendations"),
                ], p="md", mb="md", withBorder=True),

                # History chart
                dmc.Paper([
                    dmc.Group([
                        dmc.Text("Precision History", fw=500),
                        dmc.MultiSelect(
                            id="precision-construct-filter",
                            placeholder="Filter constructs...",
                            data=[],  # Populated by callback
                            clearable=True,
                            searchable=True,
                            size="xs",
                            style={"width": "200px"},
                        ),
                    ], justify="space-between", mb="sm"),
                    dcc.Graph(
                        id="precision-history-chart",
                        config={"displayModeBar": False},
                        style={"height": "200px"},
                    ),
                ], p="md", withBorder=True),
            ], span=5),
        ]),

        # Override modal
        dmc.Modal(
            id="precision-override-modal",
            title="Override Precision Target",
            centered=True,
            children=[
                dmc.Stack([
                    dmc.Text(
                        id="precision-override-construct-name",
                        fw=500,
                    ),
                    dmc.NumberInput(
                        id="precision-override-target",
                        label="New target CI width (±)",
                        value=0.3,
                        min=0.05,
                        max=2.0,
                        step=0.05,
                        decimalScale=2,
                    ),
                    dmc.Textarea(
                        id="precision-override-justification",
                        label="Justification (required)",
                        placeholder="Explain why this construct needs a different precision target (min 20 characters)",
                        minRows=3,
                        required=True,
                    ),
                    dmc.Text(
                        "Precision target overrides are logged in the audit trail.",
                        size="xs",
                        c="dimmed",
                    ),
                    dmc.Group([
                        dmc.Button(
                            "Cancel",
                            id="precision-override-cancel",
                            variant="outline",
                        ),
                        dmc.Button(
                            "Save Override",
                            id="precision-override-save",
                            color="blue",
                        ),
                    ], justify="flex-end", mt="md"),
                ], gap="md"),
            ],
        ),

        # Override result notification
        html.Div(id="precision-override-result"),
    ])


def create_precision_table_simple(
    metrics: List[Dict[str, Any]],
    target: float = 0.3,
) -> dmc.Table:
    """
    Create simple precision table (read-only, no override capability).

    Simple mode shows status only - switch to Advanced mode for overrides.

    Args:
        metrics: List of precision metrics dicts
        target: CI width target (half-width)

    Returns:
        Table component
    """
    if not metrics:
        return dmc.Text("No precision data available", c="dimmed", ta="center")

    rows = []
    for m in metrics:
        ci_width = m.get("ci_width", 0)
        ci_half = ci_width / 2  # Convert to half-width for display
        meets_target = ci_half <= target
        has_override = m.get("has_override", False)
        status = m.get("status", "")

        # Status badge
        if has_override or status == "user_accepted":
            status_badge = dmc.Badge(
                "Accepted",
                color="blue",
                size="sm",
                leftSection=DashIconify(icon="mdi:account-check", width=12),
                variant="outline",
            )
        elif meets_target:
            status_badge = dmc.Badge("Met", color="green", size="sm", leftSection=DashIconify(icon="mdi:check", width=12))
        elif ci_half <= target * 1.5:
            status_badge = dmc.Badge("Close", color="yellow", size="sm", leftSection=DashIconify(icon="mdi:minus", width=12))
        else:
            status_badge = dmc.Badge("Not Met", color="red", size="sm", leftSection=DashIconify(icon="mdi:close", width=12))

        rows.append(
            html.Tr([
                html.Td(m.get("construct_name", "Unknown")),
                html.Td(f"±{ci_half:.2f}"),
                html.Td(status_badge),
            ])
        )

    return dmc.Table(
        striped=True,
        highlightOnHover=True,
        children=[
            html.Thead(
                html.Tr([
                    html.Th("Construct"),
                    html.Th("Current CI"),
                    html.Th("Status"),
                ])
            ),
            html.Tbody(rows),
        ],
    )


def create_precision_table_advanced(
    metrics: List[Dict[str, Any]],
    target: float = 0.3,
) -> dmc.Table:
    """
    Create advanced precision table with VIF, effective N, and override capability.

    PRD Ref: F12.6 - Precision target override with justification
    PRD Ref: F13.16 - Precision history visualization

    Args:
        metrics: List of precision metrics dicts
        target: CI width target (half-width, e.g., 0.3 for ±0.3)

    Returns:
        Table component
    """
    if not metrics:
        return dmc.Text("No precision data available", c="dimmed", ta="center")

    rows = []
    for m in metrics:
        ci_width = m.get("ci_width", 0)  # Full width from data
        ci_half = ci_width / 2  # Convert to half-width for display
        meets_target = ci_half <= target
        has_override = m.get("has_override", False)
        status = m.get("status", "")

        # Status color with override support
        if has_override or status == "user_accepted":
            status_color = "blue"
            status_variant = "outline"
        elif meets_target:
            status_color = "green"
            status_variant = "light"
        elif ci_half <= target * 1.5:
            status_color = "yellow"
            status_variant = "light"
        else:
            status_color = "red"
            status_variant = "light"

        # VIF badge
        vif = m.get("vif", 1.0)
        vif_color = "green" if vif == 1.0 else ("yellow" if vif < 2.0 else "red")

        # Path type
        path_type = m.get("path_type", "direct")
        path_icons = {
            "reference": "mdi:star",
            "direct": "mdi:arrow-right",
            "one_hop": "mdi:arrow-top-right",
            "two_hop": "mdi:arrow-u-right-top",
            "four_hop": "mdi:sitemap",
        }

        # Sparkline for history
        history = m.get("history", [])
        sparkline = create_sparkline(history) if history else "—"

        # CI width badge with override indicator (display as half-width ±)
        ci_badge_text = f"±{ci_half:.2f}"
        if has_override or status == "user_accepted":
            ci_badge_text = f"✓ {ci_badge_text}"

        # Action column - override button only in advanced mode
        construct_id = m.get("construct_id")
        if not meets_target and not has_override and status != "user_accepted":
            action = dmc.ActionIcon(
                DashIconify(icon="mdi:checkbox-marked-circle-outline", width=16),
                id={"type": "precision-override-btn", "index": construct_id},
                variant="subtle",
                color="blue",
                size="sm",
            )
        elif has_override or status == "user_accepted":
            action = dmc.Tooltip(
                dmc.Badge("Accepted", color="blue", size="xs", variant="light"),
                label=m.get("override_justification", "User accepted precision"),
                multiline=True,
                w=200,
            )
        else:
            action = ""

        rows.append(
            html.Tr([
                html.Td(m.get("construct_name", "Unknown")),
                html.Td(
                    dmc.Badge(
                        ci_badge_text,
                        color=status_color,
                        size="sm",
                        variant=status_variant,
                    )
                ),
                html.Td(
                    dmc.Group([
                        DashIconify(icon=path_icons.get(path_type, "mdi:help"), width=16),
                        dmc.Text((path_type or "unknown").replace("_", " ").title(), size="xs"),
                    ], gap="xs")
                ),
                html.Td(
                    dmc.Badge(f"{vif:.2f}", color=vif_color, size="sm")
                ),
                html.Td(str(m.get("effective_n", "—"))),
                html.Td(sparkline),
                html.Td(action),
            ])
        )

    return dmc.Table(
        striped=True,
        highlightOnHover=True,
        children=[
            html.Thead(
                html.Tr([
                    html.Th("Construct"),
                    html.Th("CI Width"),
                    html.Th("Path"),
                    html.Th("VIF"),
                    html.Th("Eff. N"),
                    html.Th("History"),
                    html.Th("Override"),
                ])
            ),
            html.Tbody(rows),
        ],
    )


def create_sparkline(history: List[float]) -> html.Div:
    """
    Create a simple sparkline visualization.

    Args:
        history: List of CI width values over time

    Returns:
        Sparkline component
    """
    if not history or len(history) < 2:
        return html.Div("—")

    # Normalize to 0-1 range
    min_val = min(history)
    max_val = max(history)
    range_val = max_val - min_val if max_val > min_val else 1

    normalized = [(v - min_val) / range_val for v in history]

    # Create bars
    bars = []
    for i, val in enumerate(normalized[-8:]):  # Last 8 values
        height = max(4, int(val * 20))
        bars.append(
            html.Div(
                style={
                    "width": "4px",
                    "height": f"{height}px",
                    "backgroundColor": "#228be6",
                    "display": "inline-block",
                    "marginRight": "1px",
                    "verticalAlign": "bottom",
                }
            )
        )

    return html.Div(
        bars,
        style={"display": "flex", "alignItems": "flex-end", "height": "24px"},
    )


def create_overall_progress(
    at_target: int,
    total: int,
    average_ci: float,
    target: float,
) -> html.Div:
    """
    Create overall progress display.

    Args:
        at_target: Number of constructs at target
        total: Total number of constructs
        average_ci: Average CI width
        target: Target CI width

    Returns:
        Progress display component
    """
    pct = (at_target / total * 100) if total > 0 else 0
    color = "green" if pct >= 80 else ("yellow" if pct >= 50 else "red")

    return html.Div([
        dmc.Progress(
            value=pct,
            color=color,
            size="xl",
            mb="sm",
        ),
        dmc.Text(f"{at_target}/{total} at target", size="sm", ta="center", mb="xs"),
        dmc.Grid([
            dmc.GridCol([
                dmc.Paper([
                    dmc.Text("At Target", size="xs", c="dimmed"),
                    dmc.Text(f"{at_target}/{total}", fw=700),
                ], p="xs", withBorder=True, ta="center"),
            ], span=4),
            dmc.GridCol([
                dmc.Paper([
                    dmc.Text("Avg CI", size="xs", c="dimmed"),
                    dmc.Text(f"±{average_ci:.2f}", fw=700),
                ], p="xs", withBorder=True, ta="center"),
            ], span=4),
            dmc.GridCol([
                dmc.Paper([
                    dmc.Text("Target", size="xs", c="dimmed"),
                    dmc.Text(f"±{target:.2f}", fw=700),
                ], p="xs", withBorder=True, ta="center"),
            ], span=4),
        ]),
    ])


def create_recommendations_panel(
    recommendations: List[Dict[str, Any]],
) -> html.Div:
    """
    Create smart recommendations panel based on variability estimates.

    Args:
        recommendations: List of recommendation dicts with:
            - construct_name: Construct identifier
            - current_ci: Current CI half-width
            - target_ci: Target CI half-width
            - current_n: Current number of replicates
            - additional_n: Recommended additional replicates
            - expected_ci: Expected CI after adding replicates
            - priority: "high", "medium", or "low"
            - vif: Variance inflation factor
            - vif_note: Optional note about VIF impact

    Returns:
        Recommendations panel component
    """
    if not recommendations:
        return dmc.Alert(
            title="All targets met",
            children="All constructs have reached the precision target.",
            color="green",
            icon=DashIconify(icon="mdi:check-circle"),
        )

    items = []
    for i, rec in enumerate(recommendations[:5]):  # Top 5
        construct_name = rec.get("construct_name", "Unknown")
        current_ci = rec.get("current_ci", 0)
        target_ci = rec.get("target_ci", 0.3)
        expected_ci = rec.get("expected_ci", 0)
        current_n = rec.get("current_n", 0)
        additional_n = rec.get("additional_n", 0)
        priority = rec.get("priority", "medium")
        vif = rec.get("vif", 1.0)
        vif_note = rec.get("vif_note", "")

        # Priority color
        priority_color = {"high": "red", "medium": "yellow", "low": "blue"}.get(priority, "gray")

        # Calculate improvement percentage
        if current_ci > 0 and expected_ci > 0:
            improvement_pct = ((current_ci - expected_ci) / current_ci) * 100
        else:
            improvement_pct = 0

        # Main recommendation text
        if additional_n > 0:
            wells_per_plate = 3  # Typical replicates per plate
            plates_needed = max(1, (additional_n + wells_per_plate - 1) // wells_per_plate)
            action_text = f"Add ~{additional_n} wells ({plates_needed} plate{'s' if plates_needed > 1 else ''})"
        else:
            action_text = "Near target"

        items.append(
            dmc.Paper([
                # Header row
                dmc.Group([
                    dmc.Badge(f"#{i+1}", color=priority_color, size="sm"),
                    dmc.Text(construct_name, size="sm", fw=600),
                ], justify="space-between", mb="xs"),

                # Action recommendation
                dmc.Text(action_text, size="sm", fw=500, c="blue"),

                # Current state
                dmc.Group([
                    dmc.Text(f"Current: ±{current_ci:.2f}", size="xs", c="dimmed"),
                    dmc.Text(f"n={current_n}", size="xs", c="dimmed"),
                ], justify="space-between", mt="xs"),

                # Expected outcome
                dmc.Group([
                    dmc.Text(
                        f"Expected: ±{expected_ci:.2f}",
                        size="xs",
                        c="green" if expected_ci <= target_ci else "orange",
                    ),
                    dmc.Badge(
                        f"-{improvement_pct:.0f}%" if improvement_pct > 0 else "—",
                        color="green" if improvement_pct > 0 else "gray",
                        size="xs",
                        variant="light",
                    ),
                ], justify="space-between"),

                # VIF warning if applicable
                dmc.Text(
                    vif_note,
                    size="xs",
                    c="orange",
                    mt="xs",
                ) if vif_note else None,
            ], p="xs", mb="xs", withBorder=True)
        )

    # Add summary note
    total_additional = sum(r.get("additional_n", 0) for r in recommendations)
    if total_additional > 0:
        items.append(
            dmc.Text(
                f"Total: ~{total_additional} additional wells recommended",
                size="xs",
                c="dimmed",
                ta="center",
                mt="sm",
            )
        )

    return html.Div(items)


def create_precision_history_chart(
    history: List[Dict[str, Any]],
    target: float,
) -> go.Figure:
    """
    Create precision history chart.

    Args:
        history: List of history records with date, construct, ci_width
        target: CI width target

    Returns:
        Plotly figure
    """
    fig = go.Figure()

    if not history:
        fig.add_annotation(
            text="No history data",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(color="gray"),
        )
    else:
        # Group by construct
        constructs = {}
        for h in history:
            cname = h.get("construct_name", "Unknown")
            if cname not in constructs:
                constructs[cname] = {"dates": [], "values": []}
            constructs[cname]["dates"].append(h.get("date"))
            constructs[cname]["values"].append(h.get("ci_width"))

        # Add traces
        colors = ["#228be6", "#40c057", "#fab005", "#fa5252", "#7950f2"]
        for i, (cname, data) in enumerate(list(constructs.items())[:5]):
            fig.add_trace(go.Scatter(
                x=data["dates"],
                y=data["values"],
                mode="lines+markers",
                name=cname,
                line=dict(color=colors[i % len(colors)]),
                marker=dict(size=4),
            ))

        # Add target line
        fig.add_hline(
            y=target,
            line_dash="dash",
            line_color="red",
            annotation_text="Target",
            annotation_position="right",
        )

    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0.5, xanchor="center"),
        margin=dict(l=40, r=20, t=30, b=30),
        xaxis_title="",
        yaxis_title="CI Width",
        hovermode="x unified",
    )

    return fig


def create_empty_precision_message() -> html.Div:
    """Create message for empty precision state."""
    return html.Div([
        dmc.Alert(
            title="No Precision Data",
            children="Run an analysis to view precision metrics for each construct.",
            color="blue",
            icon=DashIconify(icon="mdi:information"),
        ),
    ], style={"marginTop": "20px"})
