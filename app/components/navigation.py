"""
Navigation components for the Dash application.

Phase C: UI Layer Completion
UX Overhaul: Sidebar navigation, breadcrumbs, active page highlighting

Provides:
- Breadcrumb navigation for page hierarchy
- Sidebar navigation for project context
- Navbar for application-level navigation
"""
from typing import List, Optional, Dict, Any, Union

import dash_mantine_components as dmc
from dash import html
from dash_iconify import DashIconify


# Navigation items for project context — all workflow steps
PROJECT_NAV_ITEMS = [
    {
        "id": "hub",
        "label": "Dashboard",
        "icon": "mdi:view-dashboard-outline",
        "href": "/project/{project_id}",
    },
    {
        "id": "constructs",
        "label": "Constructs",
        "icon": "mdi:dna",
        "href": "/project/{project_id}/constructs",
    },
    {
        "id": "calculator",
        "label": "Calculator",
        "icon": "mdi:calculator-variant",
        "href": "/project/{project_id}/calculator",
    },
    {
        "id": "layouts",
        "label": "Plate Layouts",
        "icon": "mdi:grid",
        "href": "/project/{project_id}/layouts",
    },
    {
        "id": "upload",
        "label": "Data Upload",
        "icon": "mdi:upload",
        "href": "/project/{project_id}/upload",
    },
    {
        "id": "qc",
        "label": "QC Review",
        "icon": "mdi:check-decagram",
        "href": "/project/{project_id}/qc",
    },
    {
        "id": "curves",
        "label": "Curve Browser",
        "icon": "mdi:chart-scatter-plot",
        "href": "/project/{project_id}/curves",
    },
    {
        "id": "analysis",
        "label": "Analysis",
        "icon": "mdi:chart-line",
        "href": "/project/{project_id}/analysis",
    },
    {
        "id": "precision",
        "label": "Precision",
        "icon": "mdi:target",
        "href": "/project/{project_id}/precision",
    },
    {
        "id": "export",
        "label": "Export",
        "icon": "mdi:export",
        "href": "/project/{project_id}/export",
    },
    {
        "id": "settings",
        "label": "Settings",
        "icon": "mdi:cog-outline",
        "href": "/project/{project_id}/settings",
    },
]

# Top-level navigation items
TOP_NAV_ITEMS = [
    {
        "id": "projects",
        "label": "Projects",
        "icon": "mdi:folder-outline",
        "href": "/projects",
    },
    {
        "id": "calculator",
        "label": "Calculator",
        "icon": "mdi:calculator",
        "href": "/calculator",
    },
    {
        "id": "help",
        "label": "Help",
        "icon": "mdi:help-circle-outline",
        "href": "/help",
    },
]

# Page labels for breadcrumbs
PAGE_LABELS = {
    "hub": "Dashboard",
    "constructs": "Constructs",
    "calculator": "Calculator",
    "layouts": "Plate Layouts",
    "upload": "Data Upload",
    "qc": "QC Review",
    "curves": "Curve Browser",
    "analysis": "Analysis",
    "precision": "Precision",
    "export": "Export",
    "settings": "Settings",
    "audit": "Audit Log",
}


def create_breadcrumbs(
    path: List[Union[str, Dict[str, str]]],
    separator: str = "/",
) -> dmc.Breadcrumbs:
    """
    Create breadcrumb navigation.

    Args:
        path: List of breadcrumb items. Each item can be:
            - A string (label only, no link)
            - A dict with 'label' and optional 'href'
        separator: Separator character between items

    Returns:
        Mantine Breadcrumbs component
    """
    if not path:
        return dmc.Breadcrumbs(children=[], separator=separator)

    items = []
    for i, item in enumerate(path):
        is_last = i == len(path) - 1

        if isinstance(item, str):
            items.append(
                dmc.Text(
                    item,
                    size="sm",
                    c="dimmed" if is_last else None,
                    fw=500 if is_last else None,
                )
            )
        elif isinstance(item, dict):
            label = item.get("label", "")
            href = item.get("href")

            if href and not is_last:
                items.append(
                    dmc.Anchor(
                        label,
                        href=href,
                        size="sm",
                        underline="hover",
                    )
                )
            else:
                items.append(
                    dmc.Text(
                        label,
                        size="sm",
                        c="dimmed" if is_last else None,
                        fw=500 if is_last else None,
                    )
                )

    return dmc.Breadcrumbs(
        children=items,
        separator=separator,
    )


def create_sidebar(
    current_page: str,
    project_id: Optional[int] = None,
    project_name: Optional[str] = None,
    collapsed: bool = False,
) -> html.Div:
    """
    Create sidebar navigation content.

    Args:
        current_page: ID of the currently active page (e.g., "hub", "constructs")
        project_id: Optional project ID for project-specific navigation
        project_name: Optional project name to display in header
        collapsed: Whether sidebar is in collapsed state

    Returns:
        Div containing the sidebar navigation items
    """
    nav_items = []

    # Project header (if project context)
    if project_id is not None:
        nav_items.append(
            dmc.Group(
                children=[
                    DashIconify(
                        icon="mdi:flask-outline",
                        width=20,
                        color="var(--mantine-color-teal-6)",
                    ),
                    dmc.Text(
                        project_name or f"Project {project_id}",
                        size="sm",
                        fw=600,
                        lineClamp=1,
                    ) if not collapsed else None,
                ],
                gap="sm",
                mb="xs",
                px="xs",
                wrap="nowrap",
            )
        )
        nav_items.append(dmc.Divider(mb="xs"))

        # Section label: WORKFLOW
        if not collapsed:
            nav_items.append(
                dmc.Text(
                    "WORKFLOW",
                    size="xs",
                    fw=700,
                    c="dimmed",
                    tt="uppercase",
                    pl="md",
                    mb=4,
                )
            )

        # IDs that belong to the ANALYSIS section
        analysis_ids = {"analysis", "precision", "export"}

        # Project navigation
        analysis_label_added = False
        for item in PROJECT_NAV_ITEMS:
            is_active = item["id"] == current_page
            href = item["href"].format(project_id=project_id)

            # Section label: ANALYSIS before first analysis item
            if item["id"] in analysis_ids and not analysis_label_added:
                if not collapsed:
                    nav_items.append(
                        dmc.Text(
                            "ANALYSIS",
                            size="xs",
                            fw=700,
                            c="dimmed",
                            tt="uppercase",
                            pl="md",
                            mt="sm",
                            mb=4,
                        )
                    )
                analysis_label_added = True

            # Divider before Settings
            if item["id"] == "settings":
                nav_items.append(dmc.Divider(my="sm"))

            nav_items.append(
                _create_nav_link(
                    label=item["label"],
                    icon=item["icon"],
                    href=href,
                    is_active=is_active,
                    collapsed=collapsed,
                )
            )
    else:
        # Top-level navigation
        for item in TOP_NAV_ITEMS:
            is_active = item["id"] == current_page

            nav_items.append(
                _create_nav_link(
                    label=item["label"],
                    icon=item["icon"],
                    href=item["href"],
                    is_active=is_active,
                    collapsed=collapsed,
                )
            )

    return html.Div(
        children=[
            dmc.Stack(
                children=nav_items,
                gap=2,
            ),
        ],
        style={"padding": "0.5rem"},
    )


def _create_nav_link(
    label: str,
    icon: str,
    href: str,
    is_active: bool = False,
    collapsed: bool = False,
) -> dmc.NavLink:
    """
    Create a single navigation link.

    Args:
        label: Link text
        icon: Iconify icon name
        href: Navigation target
        is_active: Whether this link is currently active
        collapsed: Whether sidebar is collapsed (icon only)

    Returns:
        Mantine NavLink component
    """
    return dmc.NavLink(
        label=label if not collapsed else None,
        leftSection=DashIconify(
            icon=icon,
            width=18,
            color="var(--mantine-color-teal-6)" if is_active else None,
        ),
        href=href,
        active=is_active,
        variant="light" if is_active else "subtle",
        style={
            "borderRadius": "var(--mantine-radius-md)",
        },
    )


def create_navbar(
    project_name: Optional[str] = None,
    show_back_button: bool = False,
    back_href: Optional[str] = None,
) -> dmc.Paper:
    """
    Create top navbar for application.

    Args:
        project_name: Optional project name to display
        show_back_button: Whether to show a back navigation button
        back_href: URL for back button

    Returns:
        Mantine Paper component for navbar
    """
    children = []

    # Left section: Logo and optional back button
    left_items = []

    if show_back_button:
        left_items.append(
            dmc.ActionIcon(
                DashIconify(icon="mdi:arrow-left", width=20),
                variant="subtle",
                size="lg",
                component="a",
                href=back_href or "/projects",
            )
        )

    left_items.append(
        dmc.Group(
            children=[
                DashIconify(
                    icon="mdi:chart-bell-curve-cumulative",
                    width=28,
                    color="var(--mantine-color-teal-6)",
                ),
                dmc.Text(
                    "IVT Kinetics Analyzer",
                    size="lg",
                    fw=700,
                ),
            ],
            gap="xs",
        )
    )

    children.append(
        dmc.Group(
            children=left_items,
            gap="md",
        )
    )

    # Center section: Project name (if provided)
    if project_name:
        children.append(
            dmc.Group(
                children=[
                    DashIconify(
                        icon="mdi:flask-outline",
                        width=20,
                        color="var(--mantine-color-gray-6)",
                    ),
                    dmc.Text(
                        project_name,
                        size="md",
                        fw=500,
                    ),
                ],
                gap="xs",
            )
        )

    # Right section: Quick actions
    children.append(
        dmc.Group(
            children=[
                dmc.Tooltip(
                    dmc.ActionIcon(
                        DashIconify(icon="mdi:help-circle-outline", width=20),
                        variant="subtle",
                        size="lg",
                        id="navbar-help-btn",
                    ),
                    label="Help",
                    position="bottom",
                ),
                dmc.Tooltip(
                    dmc.ActionIcon(
                        DashIconify(icon="mdi:cog-outline", width=20),
                        variant="subtle",
                        size="lg",
                        id="navbar-settings-btn",
                    ),
                    label="Settings",
                    position="bottom",
                ),
            ],
            gap="xs",
        )
    )

    return dmc.Paper(
        children=[
            dmc.Group(
                children=children,
                justify="space-between",
                h="100%",
                px="md",
            ),
        ],
        p="xs",
        withBorder=True,
        radius=0,
        shadow="sm",
        style={
            "position": "sticky",
            "top": 0,
            "zIndex": 100,
            "backgroundColor": "var(--mantine-color-body)",
        },
    )


def create_nav_skeleton() -> dmc.Paper:
    """
    Create a skeleton placeholder for navigation loading state.

    Returns:
        Skeleton navigation component
    """
    return dmc.Paper(
        children=[
            dmc.Stack(
                children=[
                    dmc.Skeleton(height=32, width="100%", radius="md"),
                    dmc.Divider(my="sm"),
                    dmc.Skeleton(height=28, width="100%", radius="md"),
                    dmc.Skeleton(height=28, width="100%", radius="md"),
                    dmc.Skeleton(height=28, width="100%", radius="md"),
                    dmc.Skeleton(height=28, width="100%", radius="md"),
                    dmc.Skeleton(height=28, width="100%", radius="md"),
                ],
                gap="xs",
            ),
        ],
        p="sm",
        withBorder=True,
        radius="md",
        style={"width": "240px"},
    )
