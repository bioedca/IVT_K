"""
Progress tracking and completion matrix components.

Phase C: UI Layer Completion

Provides:
- Completion matrix visualization (F13.5)
- Progress bar with construct precision status
- Status indicator badges

PRD References:
- F13.5: Completion matrix colored by precision status
- F12.2: Mid-experiment precision dashboard
"""
from typing import List, Optional, Dict, Any, Union
from enum import Enum

import dash_mantine_components as dmc
from dash import html
from dash_iconify import DashIconify
import plotly.graph_objects as go
import plotly.express as px

from app.theme import apply_plotly_theme


# Status color mapping for precision targets
COMPLETION_COLORS = {
    "met": "#40c057",       # Green - meets target
    "close": "#fab005",     # Yellow - close to target (within 1.5x)
    "not_met": "#fa5252",   # Red - below target
    "pending": "#868e96",   # Gray - no data yet
    "user_accepted": "#228be6",  # Blue - user accepted current precision
}

# Icon mapping for status indicators
STATUS_ICONS = {
    "met": "mdi:check-circle",
    "close": "mdi:minus-circle",
    "not_met": "mdi:close-circle",
    "pending": "mdi:circle-outline",
    "user_accepted": "mdi:account-check",
}


class PrecisionStatus(str, Enum):
    """Precision target status values."""
    MET = "met"
    CLOSE = "close"
    NOT_MET = "not_met"
    PENDING = "pending"
    USER_ACCEPTED = "user_accepted"


def get_precision_status(
    ci_width: Optional[float],
    target: float = 0.3,
    has_override: bool = False,
) -> str:
    """
    Determine precision status from CI width.

    Args:
        ci_width: Current CI width (None if no data)
        target: Target CI width
        has_override: Whether user has accepted this precision

    Returns:
        Status string: 'met', 'close', 'not_met', 'pending', or 'user_accepted'
    """
    if has_override:
        return "user_accepted"
    if ci_width is None:
        return "pending"
    if ci_width <= target:
        return "met"
    if ci_width <= target * 1.5:
        return "close"
    return "not_met"


def create_completion_matrix(
    constructs: List[Dict[str, Any]],
    target: float = 0.3,
    group_by_family: bool = True,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create completion matrix colored by precision status.

    PRD Ref: F13.5 - Completion matrix visualization

    Args:
        constructs: List of construct dicts with:
            - name: Construct identifier
            - family: Family grouping (optional)
            - ci_width: Current CI width (optional)
            - status: Status override (optional)
        target: CI width target
        group_by_family: Whether to group constructs by family

    Returns:
        Plotly figure showing completion matrix
    """
    fig = go.Figure()

    if not constructs:
        fig.add_annotation(
            text="No constructs defined",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=14, color="gray"),
        )
        fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            height=200,
            margin=dict(l=20, r=20, t=20, b=20),
        )
        return fig

    # Sort by family if grouping
    if group_by_family:
        constructs = sorted(
            constructs,
            key=lambda c: (c.get("family", ""), c.get("name", "")),
        )

    # Extract data for heatmap
    names = [c.get("name", f"Construct {i}") for i, c in enumerate(constructs)]
    ci_widths = []
    colors = []
    statuses = []

    for c in constructs:
        ci = c.get("ci_width")
        status = c.get("status") or get_precision_status(
            ci, target, c.get("has_override", False)
        )
        statuses.append(status)
        colors.append(COMPLETION_COLORS.get(status, COMPLETION_COLORS["pending"]))
        ci_widths.append(ci if ci is not None else 0)

    # Create color scale from status colors
    colorscale = [
        [0.0, COMPLETION_COLORS["met"]],
        [0.25, COMPLETION_COLORS["close"]],
        [0.5, COMPLETION_COLORS["not_met"]],
        [0.75, COMPLETION_COLORS["pending"]],
        [1.0, COMPLETION_COLORS["user_accepted"]],
    ]

    # Map statuses to numeric values for colorscale
    status_values = {
        "met": 0.0,
        "close": 0.25,
        "not_met": 0.5,
        "pending": 0.75,
        "user_accepted": 1.0,
    }
    z_values = [[status_values.get(s, 0.75) for s in statuses]]

    # Calculate grid dimensions (aim for roughly square)
    n = len(constructs)
    cols = min(n, max(4, int(n ** 0.5) + 1))
    rows = (n + cols - 1) // cols

    # Reshape data for grid
    z_grid = []
    text_grid = []
    hover_grid = []

    idx = 0
    for r in range(rows):
        row_z = []
        row_text = []
        row_hover = []
        for c in range(cols):
            if idx < n:
                construct = constructs[idx]
                status = statuses[idx]
                ci = ci_widths[idx]
                name = names[idx]

                row_z.append(status_values.get(status, 0.75))
                row_text.append(name[:8] + "..." if len(name) > 8 else name)
                hover_text = f"<b>{name}</b><br>"
                hover_text += f"CI: ±{ci:.2f}<br>" if ci > 0 else "CI: N/A<br>"
                hover_text += f"Status: {status.replace('_', ' ').title()}"
                row_hover.append(hover_text)
                idx += 1
            else:
                row_z.append(None)
                row_text.append("")
                row_hover.append("")
        z_grid.append(row_z)
        text_grid.append(row_text)
        hover_grid.append(row_hover)

    # Create heatmap
    fig.add_trace(go.Heatmap(
        z=z_grid,
        text=text_grid,
        texttemplate="%{text}",
        textfont=dict(size=10, color="white"),
        hovertext=hover_grid,
        hoverinfo="text",
        colorscale=[
            [0.0, COMPLETION_COLORS["met"]],
            [0.3, COMPLETION_COLORS["close"]],
            [0.6, COMPLETION_COLORS["not_met"]],
            [0.8, COMPLETION_COLORS["pending"]],
            [1.0, COMPLETION_COLORS["user_accepted"]],
        ],
        showscale=False,
        xgap=2,
        ygap=2,
    ))

    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, autorange="reversed"),
        height=max(200, rows * 50),
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    apply_plotly_theme(fig, dark_mode=dark_mode)
    # Override plot_bgcolor back to transparent for this heatmap
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def create_progress_bar(
    current: int,
    total: int,
    label: Optional[str] = None,
    color: Optional[str] = None,
    size: str = "md",
) -> dmc.Stack:
    """
    Create a progress bar with label.

    Args:
        current: Number of items completed
        total: Total number of items
        label: Optional label text
        color: Color override (auto-calculated if None)
        size: Size of progress bar ('xs', 'sm', 'md', 'lg', 'xl')

    Returns:
        Mantine Stack with progress bar and labels
    """
    if total == 0:
        percentage = 0
    else:
        percentage = (current / total) * 100

    # Auto-determine color based on progress
    if color is None:
        if percentage >= 80:
            color = "green"
        elif percentage >= 50:
            color = "yellow"
        else:
            color = "red"

    children = []

    if label:
        children.append(
            dmc.Group(
                children=[
                    dmc.Text(label, size="sm", fw=500),
                    dmc.Text(
                        f"{current}/{total}",
                        size="sm",
                        c="dimmed",
                    ),
                ],
                justify="space-between",
            )
        )

    children.append(
        dmc.Progress(
            value=percentage,
            color=color,
            size=size,
            radius="md",
        )
    )

    return dmc.Stack(
        children=children,
        gap="xs",
    )


def create_status_indicator(
    status: Union[str, PrecisionStatus],
    label: Optional[str] = None,
    size: str = "sm",
) -> dmc.Badge:
    """
    Create a status indicator badge.

    Args:
        status: Status value ('met', 'close', 'not_met', 'pending', 'user_accepted')
        label: Optional custom label (default uses status name)
        size: Badge size

    Returns:
        Mantine Badge component
    """
    if isinstance(status, PrecisionStatus):
        status = status.value

    color = COMPLETION_COLORS.get(status, COMPLETION_COLORS["pending"])
    icon = STATUS_ICONS.get(status, "mdi:circle-outline")

    # Convert hex to mantine color name if possible
    color_map = {
        COMPLETION_COLORS["met"]: "green",
        COMPLETION_COLORS["close"]: "yellow",
        COMPLETION_COLORS["not_met"]: "red",
        COMPLETION_COLORS["pending"]: "gray",
        COMPLETION_COLORS["user_accepted"]: "blue",
    }
    mantine_color = color_map.get(color, "gray")

    # Default label based on status
    display_label = label or status.replace("_", " ").title()

    return dmc.Badge(
        children=display_label,
        color=mantine_color,
        size=size,
        leftSection=DashIconify(icon=icon, width=12),
        variant="light",
    )


def create_progress_summary(
    constructs_at_target: int,
    constructs_total: int,
    average_ci: Optional[float] = None,
    target: float = 0.3,
) -> dmc.Paper:
    """
    Create a summary panel showing overall progress.

    Args:
        constructs_at_target: Number of constructs meeting target
        constructs_total: Total number of constructs
        average_ci: Average CI width (optional)
        target: CI width target

    Returns:
        Mantine Paper component with summary
    """
    if constructs_total == 0:
        percentage = 0
    else:
        percentage = (constructs_at_target / constructs_total) * 100

    # Determine overall status
    if percentage >= 80:
        status = "met"
        message = "Excellent progress!"
    elif percentage >= 50:
        status = "close"
        message = "Good progress, keep going"
    else:
        status = "not_met"
        message = "More data needed"

    children = [
        dmc.Group(
            children=[
                dmc.Text("Precision Progress", fw=600),
                create_status_indicator(status),
            ],
            justify="space-between",
            mb="sm",
        ),
        create_progress_bar(
            current=constructs_at_target,
            total=constructs_total,
            size="lg",
        ),
        dmc.Text(message, size="sm", c="dimmed", mt="xs"),
    ]

    # Add average CI if provided
    if average_ci is not None:
        children.append(
            dmc.Group(
                children=[
                    dmc.Text("Average CI width:", size="sm"),
                    dmc.Badge(
                        f"±{average_ci:.2f}",
                        color="blue" if average_ci <= target else "orange",
                        size="sm",
                    ),
                ],
                gap="xs",
                mt="sm",
            )
        )

    return dmc.Paper(
        children=children,
        p="md",
        withBorder=True,
        radius="md",
    )


def create_family_progress_table(
    family_stats: List[Dict[str, Any]],
    target: float = 0.3,
) -> dmc.Table:
    """
    Create a table showing progress by family.

    Args:
        family_stats: List of dicts with:
            - family: Family name
            - at_target: Constructs at target
            - total: Total constructs
            - avg_ci: Average CI width
        target: CI width target

    Returns:
        Mantine Table component
    """
    if not family_stats:
        return dmc.Text("No family data available", c="dimmed", ta="center")

    rows = []
    for stat in family_stats:
        at_target = stat.get("at_target", 0)
        total = stat.get("total", 0)
        avg_ci = stat.get("avg_ci")

        if total == 0:
            pct = 0
        else:
            pct = (at_target / total) * 100

        status = "met" if pct >= 80 else ("close" if pct >= 50 else "not_met")

        rows.append(
            html.Tr([
                html.Td(stat.get("family", "Unknown")),
                html.Td(f"{at_target}/{total}"),
                html.Td(
                    dmc.Progress(
                        value=pct,
                        color=COMPLETION_COLORS.get(status, "gray").replace("#", ""),
                        size="sm",
                        style={"width": "80px"},
                    )
                ),
                html.Td(
                    f"±{avg_ci:.2f}" if avg_ci is not None else "—"
                ),
                html.Td(create_status_indicator(status, size="xs")),
            ])
        )

    return dmc.Table(
        striped=True,
        highlightOnHover=True,
        children=[
            html.Thead(
                html.Tr([
                    html.Th("Family"),
                    html.Th("At Target"),
                    html.Th("Progress"),
                    html.Th("Avg CI"),
                    html.Th("Status"),
                ])
            ),
            html.Tbody(rows),
        ],
    )


def create_progress_tracker_skeleton() -> dmc.Stack:
    """
    Create a skeleton placeholder for progress tracker loading state.

    Returns:
        Skeleton progress tracker component
    """
    return dmc.Stack(
        children=[
            dmc.Group(
                children=[
                    dmc.Skeleton(height=24, width=150),
                    dmc.Skeleton(height=24, width=80, radius="xl"),
                ],
                justify="space-between",
            ),
            dmc.Skeleton(height=12, width="100%", radius="md"),
            dmc.Skeleton(height=16, width=200),
            dmc.Skeleton(height=200, width="100%", radius="md"),
        ],
        gap="md",
    )
