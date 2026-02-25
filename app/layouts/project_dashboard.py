"""
Project dashboard layout - hub navigation for a specific project.

Phase 2.8: Project dashboard UI with hub navigation (F2.5)
"""
from dash import html, dcc
import dash_mantine_components as dmc


def create_project_dashboard_layout(project_id: int = None):
    """
    Create the project dashboard/hub layout.

    This is the main navigation hub for a project, showing:
    - Project overview and status
    - Data completeness indicators
    - Quick navigation to all project sections
    - Recent activity

    Args:
        project_id: Project ID to display
    """
    return dmc.Container(
        children=[
            # Store for project data
            dcc.Store(id="dashboard-project-store", data={"project_id": project_id}),

            # Header with project info
            html.Div(
                id="dashboard-header",
                children=[
                    dmc.Group(
                        children=[
                            dmc.ActionIcon(
                                dmc.Text("←", size="lg"),
                                id="dashboard-back-btn",
                                variant="subtle",
                                size="lg"
                            ),
                            html.Div(
                                children=[
                                    dmc.Skeleton(height=28, width=200),  # Project name placeholder
                                    dmc.Skeleton(height=16, width=100, mt=4)  # Status placeholder
                                ],
                                id="dashboard-title-container"
                            )
                        ],
                        gap="md"
                    ),
                    dmc.Group(
                        children=[
                            dmc.Button(
                                "Settings",
                                id="dashboard-settings-btn",
                                variant="subtle",
                                leftSection=dmc.Text("⚙", size="sm")
                            ),
                            dmc.Menu(
                                children=[
                                    dmc.MenuTarget(
                                        dmc.Button(
                                            "Actions",
                                            variant="light",
                                            rightSection=dmc.Text("▼", size="xs")
                                        )
                                    ),
                                    dmc.MenuDropdown(
                                        children=[
                                            dmc.MenuItem(
                                                "Run Analysis",
                                                id="dashboard-run-analysis-btn"
                                            ),
                                            dmc.MenuItem(
                                                "Export Results",
                                                id="dashboard-export-btn"
                                            ),
                                            dmc.MenuDivider(),
                                            dmc.MenuItem(
                                                "Publish Project",
                                                id="dashboard-publish-btn",
                                                color="green"
                                            )
                                        ]
                                    )
                                ]
                            )
                        ],
                        gap="sm"
                    )
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "marginBottom": "1.5rem"
                }
            ),

            # Data completeness cards
            dmc.SimpleGrid(
                cols=4,
                spacing="lg",
                children=[
                    _create_stat_card(
                        title="Constructs",
                        icon="🧬",
                        stat_id="dashboard-construct-count",
                        link_id="dashboard-constructs-link"
                    ),
                    _create_stat_card(
                        title="Plate Layouts",
                        icon="📋",
                        stat_id="dashboard-layout-count",
                        link_id="dashboard-layouts-link"
                    ),
                    _create_stat_card(
                        title="Sessions",
                        icon="🧪",
                        stat_id="dashboard-session-count",
                        link_id="dashboard-sessions-link"
                    ),
                    _create_stat_card(
                        title="Analyses",
                        icon="📊",
                        stat_id="dashboard-analysis-count",
                        link_id="dashboard-analyses-link"
                    )
                ],
                id="dashboard-stats-grid",
                style={"marginBottom": "2rem"}
            ),

            # Main content sections
            dmc.Grid(
                children=[
                    # Left column - Navigation sections
                    dmc.GridCol(
                        children=[
                            dmc.Paper(
                                children=[
                                    dmc.Title("Project Sections", order=4, mb="md"),
                                    dmc.NavLink(
                                        label="Constructs",
                                        description="Manage T-box constructs and families",
                                        leftSection=dmc.Text("🧬"),
                                        id="nav-constructs",
                                        active=False
                                    ),
                                    dmc.NavLink(
                                        label="Plate Layouts",
                                        description="Define well assignments and templates",
                                        leftSection=dmc.Text("📋"),
                                        id="nav-layouts",
                                        active=False
                                    ),
                                    dmc.NavLink(
                                        label="Experimental Sessions",
                                        description="Upload and manage plate data",
                                        leftSection=dmc.Text("🧪"),
                                        id="nav-sessions",
                                        active=False
                                    ),
                                    dmc.NavLink(
                                        label="Analysis",
                                        description="Run kinetic analysis and view results",
                                        leftSection=dmc.Text("📊"),
                                        id="nav-analysis",
                                        active=False
                                    ),
                                    dmc.NavLink(
                                        label="Results & Export",
                                        description="View plots and export data",
                                        leftSection=dmc.Text("📈"),
                                        id="nav-results",
                                        active=False
                                    )
                                ],
                                p="md",
                                withBorder=True,
                                radius="md"
                            )
                        ],
                        span=4
                    ),

                    # Right column - Status and activity
                    dmc.GridCol(
                        children=[
                            # Data completeness checklist
                            dmc.Paper(
                                children=[
                                    dmc.Title("Data Completeness", order=4, mb="md"),
                                    html.Div(
                                        id="completeness-checklist",
                                        children=[
                                            _create_checklist_item(
                                                "Reporter-only construct defined",
                                                "check-unregulated",
                                                False
                                            ),
                                            _create_checklist_item(
                                                "At least one construct family",
                                                "check-families",
                                                False
                                            ),
                                            _create_checklist_item(
                                                "Plate layout with anchors",
                                                "check-layout",
                                                False
                                            ),
                                            _create_checklist_item(
                                                "Experimental data uploaded",
                                                "check-data",
                                                False
                                            ),
                                            _create_checklist_item(
                                                "Analysis completed",
                                                "check-analysis",
                                                False
                                            )
                                        ]
                                    )
                                ],
                                p="md",
                                withBorder=True,
                                radius="md",
                                style={"marginBottom": "1rem"}
                            ),

                            # Recent activity
                            dmc.Paper(
                                children=[
                                    dmc.Title("Recent Activity", order=4, mb="md"),
                                    html.Div(
                                        id="recent-activity-list",
                                        children=[
                                            dmc.Text(
                                                "No recent activity",
                                                c="dimmed",
                                                size="sm",
                                                ta="center",
                                                py="lg"
                                            )
                                        ]
                                    )
                                ],
                                p="md",
                                withBorder=True,
                                radius="md"
                            )
                        ],
                        span=8
                    )
                ],
                gutter="lg"
            )
        ],
        size="lg",
        style={"paddingTop": "1rem"}
    )


def _create_stat_card(title: str, icon: str, stat_id: str, link_id: str):
    """Create a statistics card for the dashboard."""
    return dmc.Paper(
        children=[
            dmc.Group(
                children=[
                    dmc.Text(icon, size="xl"),
                    html.Div(
                        children=[
                            dmc.Text(title, size="sm", c="dimmed"),
                            dmc.Skeleton(
                                height=24,
                                width=40,
                                id=stat_id
                            )
                        ]
                    )
                ],
                gap="md"
            ),
            dmc.Anchor(
                "View →",
                id=link_id,
                size="sm",
                style={"marginTop": "0.5rem", "display": "block"}
            )
        ],
        p="md",
        withBorder=True,
        radius="md",
        style={"cursor": "pointer"}
    )


def _create_checklist_item(label: str, item_id: str, checked: bool):
    """Create a checklist item for data completeness."""
    return dmc.Group(
        children=[
            dmc.Checkbox(
                id=item_id,
                checked=checked,
                disabled=True,  # Read-only, status determined by data
                size="sm"
            ),
            dmc.Text(
                label,
                size="sm",
                c="dimmed" if not checked else "dark"
            )
        ],
        gap="sm",
        style={"marginBottom": "0.5rem"}
    )


def create_activity_item(action: str, timestamp: str, user: str):
    """Create an activity item for the recent activity list."""
    return dmc.Group(
        children=[
            dmc.Avatar(user[0].upper() if user else "?", size="sm", radius="xl"),
            html.Div(
                children=[
                    dmc.Text(action, size="sm"),
                    dmc.Text(f"{user} • {timestamp}", size="xs", c="dimmed")
                ]
            )
        ],
        gap="sm",
        style={"marginBottom": "0.75rem"}
    )
