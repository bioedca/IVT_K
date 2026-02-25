"""
Step card component for workflow navigation.

Phase 1: Hub and Navigation Foundation

Provides:
- Visual workflow step cards with status indicators
- Lock/unlock state management
- Step dependency visualization
- Item count display
"""
from typing import Optional, List
from enum import Enum

import dash_mantine_components as dmc
from dash import html
from dash_iconify import DashIconify


class StepStatus(str, Enum):
    """Status values for workflow steps."""

    LOCKED = "locked"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


# Color mapping for each status
STATUS_COLORS = {
    StepStatus.LOCKED: "gray",
    StepStatus.PENDING: "yellow",
    StepStatus.IN_PROGRESS: "blue",
    StepStatus.COMPLETED: "green",
    "locked": "gray",
    "pending": "yellow",
    "in_progress": "blue",
    "completed": "green",
}

# Icon mapping for each status
STATUS_ICONS = {
    StepStatus.LOCKED: "mdi:lock-outline",
    StepStatus.PENDING: "mdi:circle-outline",
    StepStatus.IN_PROGRESS: "mdi:progress-clock",
    StepStatus.COMPLETED: "mdi:check-circle",
    "locked": "mdi:lock-outline",
    "pending": "mdi:circle-outline",
    "in_progress": "mdi:progress-clock",
    "completed": "mdi:check-circle",
}


def get_status_color(status: StepStatus | str) -> str:
    """
    Get the color for a given status.

    Args:
        status: Step status value

    Returns:
        Mantine color name
    """
    return STATUS_COLORS.get(status, "gray")


def get_status_icon(status: StepStatus | str) -> str:
    """
    Get the icon for a given status.

    Args:
        status: Step status value

    Returns:
        Iconify icon name
    """
    return STATUS_ICONS.get(status, "mdi:circle-outline")


def create_step_card(
    step_number: int,
    title: str,
    description: str,
    status: StepStatus | str = StepStatus.PENDING,
    item_count: Optional[int] = None,
    item_label: Optional[str] = None,
    href: Optional[str] = None,
    blockers: Optional[List[str]] = None,
    card_id: Optional[str] = None,
) -> dmc.Paper:
    """
    Create a step card for workflow navigation.

    Args:
        step_number: Step sequence number (1-7)
        title: Step title (e.g., "Define Constructs")
        description: Brief description of the step
        status: Current step status (locked, pending, in_progress, completed)
        item_count: Optional count of items (e.g., number of constructs)
        item_label: Label for item count (e.g., "constructs")
        href: Navigation link for the step
        blockers: List of blocker messages if step is locked
        card_id: Optional custom ID for the card

    Returns:
        Mantine Paper component representing the step card
    """
    # Normalize status to string
    if isinstance(status, StepStatus):
        status_value = status.value
    else:
        status_value = status

    color = get_status_color(status_value)
    icon = get_status_icon(status_value)
    is_locked = status_value == "locked"
    is_completed = status_value == "completed"

    # Build card children
    children = []

    # Header row: Step badge + Title
    header = dmc.Group(
        children=[
            dmc.Badge(
                f"Step {step_number}",
                color=color,
                variant="light" if not is_completed else "filled",
                size="lg",
            ),
            dmc.Title(
                title,
                order=5,
                **({"c": "dimmed"} if is_locked else {}),
            ),
        ],
        justify="space-between",
        mb="sm",
    )
    children.append(header)

    # Description
    children.append(
        dmc.Text(
            description,
            size="sm",
            c="dimmed",
            mb="md",
        )
    )

    # Status indicator row
    status_text_map = {
        "locked": "Locked",
        "pending": "Ready to Start",
        "in_progress": "In Progress",
        "completed": "Completed",
    }
    status_row = dmc.Group(
        children=[
            DashIconify(
                icon=icon,
                width=20,
                style={"color": f"var(--mantine-color-{color}-6)"},
            ),
            dmc.Text(
                status_text_map.get(status_value, "Unknown"),
                size="sm",
                fw=500,
                c=color,
            ),
        ],
        gap="xs",
        mb="sm",
    )
    children.append(status_row)

    # Item count (if provided)
    if item_count is not None and item_label:
        count_text = f"{item_count} {item_label}"
        if item_count == 1:
            # Remove trailing 's' for singular
            count_text = f"1 {item_label.rstrip('s')}"

        children.append(
            dmc.Group(
                children=[
                    DashIconify(
                        icon="mdi:database-outline",
                        width=16,
                        style={"color": "#868e96"},
                    ),
                    dmc.Text(
                        count_text,
                        size="sm",
                        c="dimmed",
                    ),
                ],
                gap="xs",
                mb="sm",
            )
        )

    # Blockers alert (if locked and blockers provided)
    if is_locked and blockers and len(blockers) > 0:
        blocker_items = [dmc.ListItem(blocker) for blocker in blockers]
        children.append(
            dmc.Alert(
                title="Requirements",
                color="gray",
                children=dmc.List(
                    blocker_items,
                    size="sm",
                    spacing="xs",
                ),
                icon=DashIconify(icon="mdi:information-outline", width=20),
                mb="sm",
            )
        )

    # Action link (if not locked)
    if not is_locked:
        action_text = "Continue" if status_value == "in_progress" else "View"
        if is_completed:
            action_text = "Review"

        if href:
            children.append(
                dmc.Anchor(
                    f"{action_text} →",
                    href=href,
                    size="sm",
                    fw=500,
                )
            )
        else:
            children.append(
                dmc.Text(
                    f"{action_text} →",
                    size="sm",
                    fw=500,
                    c="blue",
                    id=f"step-{step_number}-action" if not card_id else f"{card_id}-action",
                    style={"cursor": "pointer"},
                )
            )

    # Determine cursor and opacity based on status
    if is_locked:
        cursor = "not-allowed"
        opacity = 0.7
    else:
        cursor = "pointer"
        opacity = 1.0

    return dmc.Paper(
        children=children,
        p="md",
        withBorder=True,
        radius="md",
        id=card_id or f"step-card-{step_number}",
        className="hover-lift",
        style={
            "cursor": cursor,
            "opacity": opacity,
            "transition": "box-shadow 0.2s, transform 0.2s",
        },
        shadow="sm" if not is_locked else None,
    )


def create_step_card_skeleton() -> dmc.Paper:
    """
    Create a skeleton placeholder for step card loading state.

    Returns:
        Skeleton step card
    """
    return dmc.Paper(
        children=[
            dmc.Group(
                children=[
                    dmc.Skeleton(height=24, width=80, radius="xl"),
                    dmc.Skeleton(height=20, width=150),
                ],
                justify="space-between",
                mb="sm",
            ),
            dmc.Skeleton(height=16, width="100%", mb="md"),
            dmc.Group(
                children=[
                    dmc.Skeleton(height=20, width=20, radius="xl"),
                    dmc.Skeleton(height=16, width=100),
                ],
                gap="xs",
                mb="sm",
            ),
            dmc.Skeleton(height=16, width=80),
        ],
        p="md",
        withBorder=True,
        radius="md",
    )
