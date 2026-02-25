"""
Audit log layout for IVT Kinetics Analyzer.

Phase 10.4-10.6: Audit Trail UI (F18.3-F18.4)

Provides:
- Audit log query interface
- Filterable activity timeline
- Export to JSON/Markdown
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone

import dash_mantine_components as dmc
from dash import html, dcc, callback, Output, Input, State, no_update
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify


def create_audit_log_layout(project_id: Optional[int] = None) -> dmc.Stack:
    """
    Create the audit log layout.

    Args:
        project_id: Optional project ID to filter logs

    Returns:
        Mantine Stack component with audit log interface
    """
    return dmc.Stack([
        # Header
        dmc.Group([
            dmc.Title("Activity Log", order=2),
            dmc.Badge(
                "Audit Trail",
                color="blue",
                variant="light",
            ),
        ], justify="space-between"),

        # Filters
        dmc.Paper([
            dmc.Stack([
                dmc.Text("Filters", fw=500, size="sm"),
                dmc.Group([
                    dmc.Select(
                        id="audit-filter-action",
                        label="Action Type",
                        placeholder="All actions",
                        data=[
                            {"value": "", "label": "All Actions"},
                            {"value": "create", "label": "Create"},
                            {"value": "update", "label": "Update"},
                            {"value": "delete", "label": "Delete"},
                            {"value": "upload", "label": "Upload"},
                            {"value": "analyze", "label": "Analyze"},
                            {"value": "export", "label": "Export"},
                            {"value": "exclude", "label": "Exclude"},
                            {"value": "archive", "label": "Archive"},
                        ],
                        clearable=True,
                        w=150,
                    ),
                    dmc.Select(
                        id="audit-filter-entity",
                        label="Entity Type",
                        placeholder="All entities",
                        data=[
                            {"value": "", "label": "All Entities"},
                            {"value": "project", "label": "Project"},
                            {"value": "construct", "label": "Construct"},
                            {"value": "plate_layout", "label": "Plate Layout"},
                            {"value": "well", "label": "Well"},
                            {"value": "session", "label": "Session"},
                            {"value": "analysis", "label": "Analysis"},
                            {"value": "fit", "label": "Fit"},
                        ],
                        clearable=True,
                        w=150,
                    ),
                    dmc.TextInput(
                        id="audit-filter-user",
                        label="Username",
                        placeholder="Filter by user",
                        w=150,
                    ),
                    dmc.Select(
                        id="audit-filter-days",
                        label="Time Range",
                        value="7",
                        data=[
                            {"value": "1", "label": "Last 24 hours"},
                            {"value": "7", "label": "Last 7 days"},
                            {"value": "30", "label": "Last 30 days"},
                            {"value": "90", "label": "Last 90 days"},
                            {"value": "365", "label": "Last year"},
                        ],
                        w=150,
                    ),
                    dmc.Button(
                        "Apply Filters",
                        id="audit-apply-filters",
                        leftSection=DashIconify(icon="mdi:filter"),
                        variant="light",
                    ),
                ], gap="md"),
            ], gap="xs"),
        ], p="md", withBorder=True, radius="md"),

        # Summary cards
        dmc.Group([
            dmc.Paper([
                dmc.Stack([
                    dmc.Text("Total Actions", size="xs", c="dimmed"),
                    dmc.Text(id="audit-total-count", fw=700, size="xl"),
                ], gap=2, align="center"),
            ], p="md", withBorder=True, radius="md", w=150),
            dmc.Paper([
                dmc.Stack([
                    dmc.Text("Users Active", size="xs", c="dimmed"),
                    dmc.Text(id="audit-user-count", fw=700, size="xl"),
                ], gap=2, align="center"),
            ], p="md", withBorder=True, radius="md", w=150),
            dmc.Paper([
                dmc.Stack([
                    dmc.Text("Creates", size="xs", c="dimmed"),
                    dmc.Text(id="audit-create-count", fw=700, size="xl", c="green"),
                ], gap=2, align="center"),
            ], p="md", withBorder=True, radius="md", w=150),
            dmc.Paper([
                dmc.Stack([
                    dmc.Text("Updates", size="xs", c="dimmed"),
                    dmc.Text(id="audit-update-count", fw=700, size="xl", c="blue"),
                ], gap=2, align="center"),
            ], p="md", withBorder=True, radius="md", w=150),
            dmc.Paper([
                dmc.Stack([
                    dmc.Text("Deletes", size="xs", c="dimmed"),
                    dmc.Text(id="audit-delete-count", fw=700, size="xl", c="red"),
                ], gap=2, align="center"),
            ], p="md", withBorder=True, radius="md", w=150),
        ], gap="md"),

        # Export buttons
        dmc.Group([
            dmc.Button(
                "Export JSON",
                id="audit-export-json",
                leftSection=DashIconify(icon="mdi:code-json"),
                variant="outline",
                size="sm",
            ),
            dmc.Button(
                "Export Markdown",
                id="audit-export-md",
                leftSection=DashIconify(icon="mdi:language-markdown"),
                variant="outline",
                size="sm",
            ),
            dcc.Download(id="audit-download"),
        ], gap="sm"),

        # Activity timeline
        dmc.Paper([
            dmc.Stack([
                dmc.Text("Activity Timeline", fw=500),
                dmc.ScrollArea([
                    html.Div(id="audit-timeline-container"),
                ], h=500),
            ], gap="md"),
        ], p="md", withBorder=True, radius="md"),

        # Hidden store for project context
        dcc.Store(id="audit-project-id", data=project_id),

    ], gap="md")


def create_audit_entry_card(
    log_id: int,
    timestamp: datetime,
    username: str,
    action_type: str,
    entity_type: str,
    entity_id: int,
    changes: Optional[List[Dict]] = None,
    details: Optional[Dict] = None,
) -> dmc.Paper:
    """
    Create a card for a single audit log entry.

    Args:
        log_id: Audit log ID
        timestamp: When the action occurred
        username: Who performed the action
        action_type: Type of action
        entity_type: Type of entity affected
        entity_id: ID of affected entity
        changes: List of field changes
        details: Additional details

    Returns:
        Mantine Paper component
    """
    # Action type styling
    action_colors = {
        "create": "green",
        "update": "blue",
        "delete": "red",
        "upload": "violet",
        "analyze": "orange",
        "export": "cyan",
        "exclude": "yellow",
        "archive": "gray",
        "restore": "teal",
    }
    action_icons = {
        "create": "mdi:plus-circle",
        "update": "mdi:pencil",
        "delete": "mdi:delete",
        "upload": "mdi:upload",
        "analyze": "mdi:chart-line",
        "export": "mdi:download",
        "exclude": "mdi:close-circle",
        "archive": "mdi:archive",
        "restore": "mdi:restore",
    }

    color = action_colors.get(action_type, "gray")
    icon = action_icons.get(action_type, "mdi:information")

    # Format timestamp
    time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    relative_time = _get_relative_time(timestamp)

    # Build changes display
    changes_content = None
    if changes and len(changes) > 0:
        change_rows = []
        for change in changes[:5]:  # Limit to 5 changes
            field = change.get("field", "unknown")
            old_val = str(change.get("old", "-"))[:30]
            new_val = str(change.get("new", "-"))[:30]
            change_rows.append(
                dmc.Group([
                    dmc.Text(field, size="xs", fw=500, w=100),
                    dmc.Text(old_val, size="xs", c="red", w=100),
                    dmc.Text("→", size="xs", c="dimmed"),
                    dmc.Text(new_val, size="xs", c="green", w=100),
                ], gap="xs")
            )
        if len(changes) > 5:
            change_rows.append(
                dmc.Text(f"... and {len(changes) - 5} more changes", size="xs", c="dimmed")
            )
        changes_content = dmc.Stack(change_rows, gap=2)

    return dmc.Paper([
        dmc.Group([
            # Icon
            dmc.ThemeIcon(
                DashIconify(icon=icon, width=18),
                color=color,
                variant="light",
                radius="xl",
                size="lg",
            ),
            # Main content
            dmc.Stack([
                dmc.Group([
                    dmc.Badge(action_type.upper(), color=color, size="sm"),
                    dmc.Text(f"{entity_type}", size="sm", fw=500),
                    dmc.Text(f"#{entity_id}", size="sm", c="dimmed"),
                ], gap="xs"),
                dmc.Group([
                    dmc.Text(username, size="xs", c="dimmed"),
                    dmc.Text("•", size="xs", c="dimmed"),
                    dmc.Tooltip(
                        dmc.Text(relative_time, size="xs", c="dimmed"),
                        label=time_str,
                    ),
                ], gap="xs"),
            ], gap=2, style={"flex": 1}),
        ], align="flex-start", gap="md"),
        # Changes (if any)
        changes_content,
    ], p="sm", withBorder=True, radius="md", mb="xs")


def _get_relative_time(timestamp: datetime) -> str:
    """Get relative time string (e.g., '5 minutes ago')."""
    now = datetime.now(timezone.utc)
    # Ensure timezone compatibility (SQLite stores naive UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    diff = now - timestamp

    if diff.total_seconds() < 60:
        return "just now"
    elif diff.total_seconds() < 3600:
        minutes = int(diff.total_seconds() / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif diff.total_seconds() < 86400:
        hours = int(diff.total_seconds() / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.days < 7:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.days < 30:
        weeks = diff.days // 7
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    else:
        return timestamp.strftime("%Y-%m-%d")


def create_empty_state() -> dmc.Stack:
    """Create empty state display when no audit logs found."""
    return dmc.Stack([
        DashIconify(icon="mdi:history", width=48, color="gray"),
        dmc.Text("No activity found", fw=500, c="dimmed"),
        dmc.Text(
            "Activity will appear here as changes are made",
            size="sm",
            c="dimmed",
        ),
    ], align="center", gap="xs", py="xl")
