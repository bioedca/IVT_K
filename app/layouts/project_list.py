"""
Project list and dashboard layout.

Phase 2.8: Project dashboard UI with hub navigation (F2.5)
"""
from dash import html, dcc
import dash_mantine_components as dmc
from dash_iconify import DashIconify


def create_project_list_layout():
    """
    Create the project list/dashboard layout.

    Features:
    - List of user's projects with status summary
    - Create new project button
    - Project cards with quick stats
    """
    return dmc.Container(
        children=[
            # Header section
            dmc.Group(
                children=[
                    dmc.Title("Projects", order=2),
                    dmc.Button(
                        "New Project",
                        id="create-project-btn",
                        leftSection=dmc.Text("+", fw=700),
                        color="blue"
                    )
                ],
                justify="space-between",
                style={"marginBottom": "1.5rem"}
            ),

            # Filter/search bar
            dmc.Group(
                children=[
                    dmc.TextInput(
                        id="project-search-input",
                        value="",
                        placeholder="Search projects...",
                        leftSection=dmc.Text("🔍", size="sm"),
                        style={"flex": 1, "maxWidth": "300px"}
                    ),
                    dmc.SegmentedControl(
                        id="project-filter-status",
                        data=[
                            {"value": "all", "label": "All"},
                            {"value": "draft", "label": "Draft"},
                            {"value": "published", "label": "Published"},
                            {"value": "archived", "label": "Archived"}
                        ],
                        value="all"
                    )
                ],
                style={"marginBottom": "1rem"}
            ),

            # Project cards container
            html.Div(
                id="project-cards-container",
                children=[
                    # Loading placeholder
                    dmc.Center(
                        children=[
                            dmc.Loader(color="blue", size="lg")
                        ],
                        style={"padding": "3rem"}
                    )
                ]
            ),

            # Lab Tools section
            dmc.Divider(my="xl"),
            dmc.Paper(
                children=[
                    dmc.Group(
                        children=[
                            DashIconify(icon="mdi:toolbox", width=24, color="#868e96"),
                            dmc.Title("Lab Tools", order=4, c="dimmed"),
                        ],
                        gap="xs",
                        mb="md",
                    ),
                    dmc.SimpleGrid(
                        children=[
                            dcc.Link(
                                dmc.Paper(
                                    children=[
                                        dmc.Group(
                                            children=[
                                                dmc.ThemeIcon(
                                                    DashIconify(icon="mdi:content-cut", width=22),
                                                    size=40,
                                                    radius="md",
                                                    variant="light",
                                                    color="grape",
                                                ),
                                                html.Div(
                                                    children=[
                                                        dmc.Text("Digestion Calculator", fw=600, size="sm"),
                                                        dmc.Text(
                                                            "Calculate restriction enzyme digestion "
                                                            "volumes and generate bench protocol",
                                                            size="xs",
                                                            c="dimmed",
                                                        ),
                                                    ],
                                                ),
                                            ],
                                            gap="md",
                                        ),
                                    ],
                                    p="md",
                                    withBorder=True,
                                    radius="md",
                                    className="hover-lift",
                                    style={"cursor": "pointer"},
                                ),
                                href="/tools/digestion",
                                style={"textDecoration": "none", "color": "inherit"},
                            ),
                            dcc.Link(
                                dmc.Paper(
                                    children=[
                                        dmc.Group(
                                            children=[
                                                dmc.ThemeIcon(
                                                    DashIconify(icon="mdi:shield-lock", width=22),
                                                    size=40,
                                                    radius="md",
                                                    variant="light",
                                                    color="blue",
                                                ),
                                                html.Div(
                                                    children=[
                                                        dmc.Text("Access Log", fw=600, size="sm"),
                                                        dmc.Text(
                                                            "View PIN authentication events, "
                                                            "login attempts, and session activity",
                                                            size="xs",
                                                            c="dimmed",
                                                        ),
                                                    ],
                                                ),
                                            ],
                                            gap="md",
                                        ),
                                    ],
                                    p="md",
                                    withBorder=True,
                                    radius="md",
                                    className="hover-lift",
                                    style={"cursor": "pointer"},
                                ),
                                href="/admin/access-log",
                                style={"textDecoration": "none", "color": "inherit"},
                            ),
                        ],
                        cols={"base": 1, "sm": 2, "lg": 3},
                        spacing="md",
                    ),
                ],
                withBorder=True,
                radius="md",
                p="lg",
                mb="xl",
            ),

            # Create project modal
            dmc.Modal(
                id="create-project-modal",
                title="Create New Project",
                centered=True,
                children=[
                    dmc.TextInput(
                        id="new-project-name",
                        label="Project Name",
                        placeholder="e.g., Tbox Analysis 2024",
                        required=True,
                        style={"marginBottom": "1rem"}
                    ),
                    dmc.Textarea(
                        id="new-project-description",
                        label="Description",
                        placeholder="Brief description of the project...",
                        autosize=True,
                        minRows=2,
                        style={"marginBottom": "1rem"}
                    ),
                    dmc.Select(
                        id="new-project-plate-format",
                        label="Plate Format",
                        data=[
                            {"value": "384", "label": "384-well plate"},
                            {"value": "96", "label": "96-well plate"}
                        ],
                        value="384",
                        style={"marginBottom": "1rem"}
                    ),
                    dmc.TextInput(
                        id="new-project-reporter",
                        label="Reporter System",
                        placeholder="e.g., iSpinach",
                        style={"marginBottom": "1rem"}
                    ),
                    dmc.Group(
                        children=[
                            dmc.Button(
                                "Cancel",
                                id="cancel-create-project-btn",
                                variant="subtle"
                            ),
                            dmc.Button(
                                "Create Project",
                                id="submit-create-project-btn",
                                color="blue"
                            )
                        ],
                        justify="flex-end"
                    )
                ],
                opened=False
            ),

            # Delete project confirmation modal
            dmc.Modal(
                id="delete-project-modal",
                title="Delete Project",
                centered=True,
                children=[
                    dmc.Text(
                        id="delete-project-message",
                        children="Are you sure you want to delete this project?",
                        mb="md",
                    ),
                    dmc.Alert(
                        "This action can be undone by an administrator.",
                        color="yellow",
                        title="Soft Delete",
                        mb="md",
                    ),
                    dmc.Group(
                        children=[
                            dmc.Button(
                                "Cancel",
                                id="cancel-delete-project-btn",
                                variant="subtle",
                            ),
                            dmc.Button(
                                "Delete",
                                id="confirm-delete-project-btn",
                                color="red",
                            ),
                        ],
                        justify="flex-end",
                    ),
                ],
                opened=False,
            ),
            # Store to track which project is being deleted
            dcc.Store(id="delete-project-id-store", data=None),
        ],
        size="lg",
        style={"paddingTop": "1rem"}
    )


def create_project_card(project_data: dict):
    """
    Create a project card component with colored left border by status.

    Args:
        project_data: Dict with project info from API
    """
    status_color = "blue" if project_data.get("is_draft") else "green"
    status_text = "Draft" if project_data.get("is_draft") else "Published"

    if project_data.get("is_archived"):
        status_color = "gray"
        status_text = "Archived"

    # Status-based left border color
    border_colors = {
        "blue": "#D4860B",     # Draft → amber
        "green": "#0C7C6F",    # Published → teal
        "gray": "#868e96",     # Archived → gray
    }
    left_border_color = border_colors.get(status_color, "var(--border-medium)")

    return dmc.Card(
        children=[
            dmc.Group(
                children=[
                    dmc.Text(
                        project_data.get("name", "Unnamed Project"),
                        fw=600,
                        size="lg",
                    ),
                    dmc.Badge(
                        status_text,
                        color=status_color,
                        variant="light"
                    )
                ],
                justify="space-between",
                style={"marginBottom": "0.5rem"}
            ),
            dmc.Text(
                project_data.get("description") or "No description",
                size="sm",
                c="dimmed",
                lineClamp=2,
                style={"marginBottom": "1rem"}
            ),
            dmc.Group(
                children=[
                    dmc.Group(
                        children=[
                            DashIconify(icon="mdi:dna", width=16, color="var(--mantine-color-dimmed)"),
                            dmc.Text(
                                f"{project_data.get('construct_count', 0)} constructs",
                                size="sm",
                                c="dimmed"
                            )
                        ],
                        gap="xs"
                    ),
                    dmc.Group(
                        children=[
                            DashIconify(icon="mdi:grid", width=16, color="var(--mantine-color-dimmed)"),
                            dmc.Text(
                                f"{project_data.get('plate_format', '384')}-well",
                                size="sm",
                                c="dimmed"
                            )
                        ],
                        gap="xs"
                    ),
                    dmc.Group(
                        children=[
                            DashIconify(icon="mdi:chart-bar", width=16, color="var(--mantine-color-dimmed)"),
                            dmc.Text(
                                f"{project_data.get('session_count', 0)} sessions",
                                size="sm",
                                c="dimmed"
                            )
                        ],
                        gap="xs"
                    )
                ],
                gap="lg",
                style={"marginBottom": "1rem"}
            ),
            dmc.Group(
                children=[
                    dmc.Button(
                        "Open",
                        id={"type": "open-project-btn", "index": project_data.get("id")},
                        variant="light",
                        size="sm"
                    ),
                    dmc.Menu(
                        children=[
                            dmc.MenuTarget(
                                dmc.ActionIcon(
                                    DashIconify(icon="mdi:dots-vertical", width=18),
                                    variant="subtle",
                                    color="gray"
                                )
                            ),
                            dmc.MenuDropdown(
                                children=[
                                    dmc.MenuItem(
                                        "Settings",
                                        id={"type": "project-settings-btn", "index": project_data.get("id")}
                                    ),
                                    dmc.MenuItem(
                                        "Duplicate",
                                        id={"type": "duplicate-project-btn", "index": project_data.get("id")}
                                    ),
                                    dmc.MenuDivider(),
                                    dmc.MenuItem(
                                        "Archive" if not project_data.get("is_archived") else "Unarchive",
                                        id={"type": "archive-project-btn", "index": project_data.get("id")},
                                        color="yellow"
                                    ),
                                    dmc.MenuItem(
                                        "Delete",
                                        id={"type": "delete-project-btn", "index": project_data.get("id")},
                                        color="red"
                                    )
                                ]
                            )
                        ]
                    )
                ],
                justify="space-between"
            )
        ],
        withBorder=True,
        shadow="sm",
        radius="md",
        padding="lg",
        className="hover-lift",
        style={
            "marginBottom": "1rem",
            "borderLeft": f"4px solid {left_border_color}",
        },
    )


def create_empty_projects_message(is_filtered=False):
    """Create message shown when no projects match.

    Args:
        is_filtered: True when projects exist but don't match the current filter/search.
    """
    if is_filtered:
        return dmc.Center(
            children=[
                dmc.Stack(
                    children=[
                        DashIconify(
                            icon="mdi:filter-off-outline",
                            width=48,
                            color="var(--mantine-color-gray-4)",
                        ),
                        dmc.Title("No Matching Projects", order=3, ta="center"),
                        dmc.Text(
                            "No projects match the current filter. "
                            "Try a different filter or clear the search.",
                            c="dimmed",
                            ta="center",
                            maw=400,
                        ),
                    ],
                    align="center",
                    gap="sm",
                )
            ],
            style={"padding": "4rem 1rem"},
        )

    return dmc.Center(
        children=[
            dmc.Stack(
                children=[
                    DashIconify(
                        icon="mdi:flask-empty-outline",
                        width=56,
                        color="var(--mantine-color-gray-4)",
                    ),
                    dmc.Title("No Projects Yet", order=3, ta="center"),
                    dmc.Text(
                        "Create your first project to start analyzing IVT kinetics data. "
                        "You'll be able to define constructs, plan reactions, upload data, "
                        "and run statistical analysis.",
                        c="dimmed",
                        ta="center",
                        maw=450,
                    ),
                    dmc.Button(
                        "Create Your First Project",
                        id="create-first-project-btn",
                        size="lg",
                        leftSection=DashIconify(icon="mdi:plus", width=20),
                        variant="filled",
                        mt="md",
                    ),
                ],
                align="center",
                gap="sm",
            )
        ],
        style={"padding": "4rem 1rem"}
    )
