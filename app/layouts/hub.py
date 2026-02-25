"""
Hub layout - central project navigation dashboard.

Phase 1: Hub and Navigation Foundation

Provides:
- Central project dashboard with step cards
- Workflow progress visualization
- Quick navigation to project sections
- Step unlock status display
"""
from typing import Optional, Dict, List, Any

import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify

from app.components.step_card import create_step_card, create_step_card_skeleton, StepStatus


# Workflow step definitions per PRD Section 1.5
WORKFLOW_STEPS = [
    {
        "number": 1,
        "title": "Define Constructs",
        "description": "Add T-box constructs and families for your experiment",
        "route": "/project/{project_id}/constructs",
        "icon": "mdi:dna",
        "item_label": "constructs",
    },
    {
        "number": 2,
        "title": "Plan IVT Reaction",
        "description": "Calculate reaction volumes and plan your IVT setup (optional)",
        "route": "/project/{project_id}/calculator",
        "icon": "mdi:calculator-variant",
        "item_label": "plans",
        "optional": True,
    },
    {
        "number": 3,
        "title": "Create Layout",
        "description": "Define plate layout templates and well assignments",
        "route": "/project/{project_id}/layouts",
        "icon": "mdi:grid",
        "item_label": "layouts",
    },
    {
        "number": 4,
        "title": "Upload Data",
        "description": "Upload experimental data files from BioTek reader",
        "route": "/project/{project_id}/upload",
        "icon": "mdi:upload",
        "item_label": "files",
    },
    {
        "number": 5,
        "title": "Review QC",
        "description": "Review quality control results and approve sessions",
        "route": "/project/{project_id}/qc",
        "icon": "mdi:check-decagram",
        "item_label": "pending",
    },
    {
        "number": 6,
        "title": "Run Analysis",
        "description": "Run hierarchical Bayesian analysis on your data",
        "route": "/project/{project_id}/analysis",
        "icon": "mdi:chart-line",
        "item_label": "analyses",
    },
    {
        "number": 7,
        "title": "Export",
        "description": "Export results and create publication-ready outputs",
        "route": "/project/{project_id}/export",
        "icon": "mdi:export",
        "item_label": "exports",
    },
]


def create_hub_layout(project_id: Optional[int] = None) -> dmc.Container:
    """
    Create the hub layout for project navigation.

    This is the main project dashboard showing workflow steps,
    progress, and quick navigation options.

    Args:
        project_id: Optional project ID

    Returns:
        Mantine Container with hub layout
    """
    return dmc.Container(
        children=[
            # Data stores
            dcc.Store(id="hub-project-store", data={"project_id": project_id}),
            dcc.Store(id="hub-step-statuses-store", data={}),

            # Header section
            _create_hub_header(project_id),

            # Progress summary
            html.Div(
                id="hub-progress-container",
                children=[create_progress_summary()],
                style={"marginBottom": "1.5rem"},
            ),

            # Main content grid
            dmc.Grid(
                children=[
                    # Left column - Workflow steps
                    dmc.GridCol(
                        children=[
                            dmc.Title("Workflow Steps", order=4, mb="md"),
                            html.Div(
                                id="hub-steps-container",
                                children=[create_workflow_steps_grid(project_id)],
                            ),
                        ],
                        span=8,
                    ),

                    # Right column - Quick actions and status
                    dmc.GridCol(
                        children=[
                            create_quick_actions_panel(project_id),
                            html.Div(style={"height": "1rem"}),
                            _create_help_section(),
                        ],
                        span=4,
                    ),
                ],
                gutter="lg",
            ),
        ],
        size="lg",
        style={"paddingTop": "1rem"},
    )


def _create_hub_header(project_id: Optional[int] = None) -> html.Div:
    """Create the hub header section."""
    return html.Div(
        children=[
            dmc.Group(
                children=[
                    dmc.ActionIcon(
                        DashIconify(icon="mdi:arrow-left", width=24),
                        id="hub-back-btn",
                        variant="subtle",
                        size="lg",
                    ),
                    html.Div(
                        children=[
                            dmc.Skeleton(
                                height=28,
                                width=250,
                                id="hub-project-name-skeleton",
                            ),
                            dmc.Text(
                                "Project Dashboard",
                                size="sm",
                                c="dimmed",
                            ),
                        ],
                        id="hub-title-container",
                    ),
                ],
                gap="md",
            ),
            dmc.Button(
                "Settings",
                id="hub-settings-btn",
                variant="subtle",
                leftSection=DashIconify(icon="mdi:cog", width=18),
            ),
        ],
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "marginBottom": "1.5rem",
        },
    )


def create_workflow_steps_grid(
    project_id: Optional[int] = None,
    step_statuses: Optional[Dict[int, str]] = None,
    item_counts: Optional[Dict[int, int]] = None,
) -> dmc.SimpleGrid:
    """
    Create the grid of workflow step cards.

    Args:
        project_id: Project ID for generating links
        step_statuses: Dict mapping step number to status string
        item_counts: Dict mapping step number to item count

    Returns:
        SimpleGrid containing step cards
    """
    step_statuses = step_statuses or {}
    item_counts = item_counts or {}

    cards = []
    for step in WORKFLOW_STEPS:
        step_num = step["number"]

        # Get status (default to locked for steps > 1, pending for step 1)
        if step_statuses:
            status = step_statuses.get(step_num, "locked")
        else:
            # Default: step 1 and 2 are pending, rest locked
            status = "pending" if step_num <= 2 else "locked"

        # Get item count
        count = item_counts.get(step_num)

        # Generate href
        href = None
        if project_id and status != "locked":
            href = step["route"].format(project_id=project_id)

        # Get blockers for locked steps
        blockers = None
        if status == "locked":
            blockers = _get_step_blockers_display(step_num)

        card = create_step_card(
            step_number=step_num,
            title=step["title"],
            description=step["description"],
            status=status,
            item_count=count,
            item_label=step.get("item_label"),
            href=href,
            blockers=blockers,
        )
        cards.append(card)

    return dmc.SimpleGrid(
        children=cards,
        cols={"base": 1, "sm": 2, "lg": 2},
        spacing="md",
    )


def _get_step_blockers_display(step_number: int) -> List[str]:
    """Get display-friendly blocker messages for a step."""
    blockers_map = {
        3: ["At least one construct must be defined"],
        4: ["A plate layout must be created"],
        5: ["Experimental data must be uploaded"],
        6: ["All sessions must be QC approved"],
        7: ["Analysis must be completed"],
    }
    return blockers_map.get(step_number, [])


def create_workflow_stepper(
    step_statuses: Optional[Dict[int, str]] = None,
) -> dmc.Paper:
    """
    Create a horizontal workflow stepper.

    Args:
        step_statuses: Dict mapping step number (1-7) to status string

    Returns:
        Paper component with horizontal Stepper
    """
    step_statuses = step_statuses or {}

    # Determine active step (first non-completed step)
    active_index = 0
    for i, step in enumerate(WORKFLOW_STEPS):
        status = step_statuses.get(step["number"], "locked")
        if status == "completed":
            active_index = i + 1
        else:
            break

    # Cap at total steps
    active_index = min(active_index, len(WORKFLOW_STEPS))

    stepper_steps = []
    for step in WORKFLOW_STEPS:
        status = step_statuses.get(step["number"], "locked")
        description = "Completed" if status == "completed" else (
            "In progress" if status == "in_progress" else (
                "Ready" if status == "pending" else "Locked"
            )
        )
        # Color differentiation: completed=teal, current=yellow
        step_color = None
        if status == "completed":
            step_color = "teal"
        elif status in ("in_progress", "pending"):
            step_color = "yellow"

        step_kwargs = dict(
            label=step["title"],
            description=description,
            icon=DashIconify(icon=step["icon"], width=18),
            completedIcon=DashIconify(icon="mdi:check", width=18),
        )
        if step_color:
            step_kwargs["color"] = step_color

        stepper_steps.append(
            dmc.StepperStep(**step_kwargs)
        )

    return dmc.Paper(
        children=[
            dmc.Stepper(
                id="hub-workflow-stepper",
                active=active_index,
                children=stepper_steps,
                size="sm",
                allowNextStepsSelect=False,
            ),
        ],
        p="md",
        withBorder=True,
        radius="md",
    )


def create_progress_summary(
    completed_steps: int = 0,
    total_steps: int = 7,
) -> dmc.Paper:
    """
    Create a progress summary panel (legacy fallback).

    Args:
        completed_steps: Number of completed steps
        total_steps: Total number of steps

    Returns:
        Paper component with progress summary
    """
    progress_pct = (completed_steps / total_steps * 100) if total_steps > 0 else 0

    # Determine progress color
    if progress_pct >= 100:
        color = "green"
        message = "All steps completed!"
    elif progress_pct >= 70:
        color = "blue"
        message = "Almost there!"
    elif progress_pct >= 30:
        color = "yellow"
        message = "Making progress"
    else:
        color = "gray"
        message = "Just getting started"

    return dmc.Paper(
        children=[
            dmc.Group(
                children=[
                    html.Div(
                        children=[
                            dmc.Text(
                                "Workflow Progress",
                                fw=600,
                                size="sm",
                            ),
                            dmc.Text(
                                message,
                                size="xs",
                                c="dimmed",
                            ),
                        ],
                    ),
                    dmc.RingProgress(
                        sections=[{"value": progress_pct, "color": color}],
                        label=dmc.Text(
                            f"{completed_steps}/{total_steps}",
                            ta="center",
                            fw=700,
                            size="sm",
                        ),
                        size=80,
                        thickness=8,
                    ),
                ],
                justify="space-between",
                align="center",
            ),
            dmc.Progress(
                value=progress_pct,
                color=color,
                size="sm",
                mt="md",
            ),
        ],
        p="md",
        withBorder=True,
        radius="md",
    )


def create_quick_actions_panel(
    project_id: Optional[int] = None,
    step_statuses: Optional[Dict[int, str]] = None,
) -> dmc.Paper:
    """
    Create the quick actions panel with contextual primary CTA.

    The primary action adapts based on workflow progress:
    - No constructs → "Define Constructs"
    - No layouts → "Create Layout"
    - Data ready → "Run Analysis"
    - Analysis done → "Export Results"

    Args:
        project_id: Project ID
        step_statuses: Dict mapping step number to status

    Returns:
        Paper component with quick actions
    """
    step_statuses = step_statuses or {}

    # Determine primary CTA based on workflow state
    s1 = step_statuses.get(1, "pending")
    s3 = step_statuses.get(3, "locked")
    s6 = step_statuses.get(6, "locked")
    s7 = step_statuses.get(7, "locked")

    return dmc.Paper(
        children=[
            dmc.Title("Quick Actions", order=5, mb="md"),
            dmc.Stack(
                children=[
                    # Primary CTA - adapts to workflow state
                    dmc.Button(
                        "Define Constructs" if s1 == "pending" else (
                            "Create Layout" if s3 == "pending" else (
                                "Export Results" if s7 != "locked" else "Run Analysis"
                            )
                        ),
                        id="quick-run-analysis-btn",
                        variant="filled",
                        fullWidth=True,
                        leftSection=DashIconify(icon="mdi:play-circle", width=20),
                    ),
                    dmc.Button(
                        "View Curves",
                        id="quick-view-curves-btn",
                        variant="light",
                        fullWidth=True,
                        leftSection=DashIconify(icon="mdi:chart-scatter-plot", width=20),
                    ),
                    dmc.Button(
                        "Export Results",
                        id="quick-export-btn",
                        variant="light",
                        fullWidth=True,
                        leftSection=DashIconify(icon="mdi:file-export", width=20),
                        disabled=s7 == "locked",
                    ),
                    dmc.Divider(my="xs"),
                    dmc.Button(
                        "Precision Dashboard",
                        id="quick-precision-btn",
                        variant="subtle",
                        fullWidth=True,
                        leftSection=DashIconify(icon="mdi:target", width=20),
                    ),
                ],
                gap="xs",
            ),
        ],
        p="md",
        withBorder=True,
        radius="md",
    )


def _create_help_section() -> dmc.Paper:
    """Create the help section panel."""
    return dmc.Paper(
        children=[
            dmc.Title("Need Help?", order=5, mb="md"),
            dmc.Stack(
                children=[
                    dmc.Group(
                        children=[
                            DashIconify(icon="mdi:book-open-variant", width=20, color="#228be6"),
                            dmc.Anchor(
                                "Getting Started Guide",
                                href="/help/getting-started",
                                size="sm",
                            ),
                        ],
                        gap="xs",
                    ),
                    dmc.Group(
                        children=[
                            DashIconify(icon="mdi:help-circle", width=20, color="#228be6"),
                            dmc.Anchor(
                                "Workflow Overview",
                                href="/help/workflow",
                                size="sm",
                            ),
                        ],
                        gap="xs",
                    ),
                ],
                gap="sm",
            ),
        ],
        p="md",
        withBorder=True,
        radius="md",
        style={"backgroundColor": "var(--bg-surface)"},
    )


def create_hub_loading_state() -> dmc.Container:
    """
    Create a loading state for the hub layout.

    Returns:
        Container with skeleton placeholders
    """
    skeleton_cards = [create_step_card_skeleton() for _ in range(7)]

    return dmc.Container(
        children=[
            # Header skeleton
            dmc.Group(
                children=[
                    dmc.Skeleton(height=40, width=40, radius="md"),
                    dmc.Stack(
                        children=[
                            dmc.Skeleton(height=28, width=250),
                            dmc.Skeleton(height=16, width=120),
                        ],
                        gap="xs",
                    ),
                ],
                gap="md",
                mb="xl",
            ),

            # Progress skeleton
            dmc.Skeleton(height=100, radius="md", mb="lg"),

            # Grid skeleton
            dmc.SimpleGrid(
                children=skeleton_cards,
                cols={"base": 1, "sm": 2, "lg": 2},
                spacing="md",
            ),
        ],
        size="lg",
        style={"paddingTop": "1rem"},
    )
