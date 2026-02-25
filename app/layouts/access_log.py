"""
Access log viewer layout.

Admin page showing PIN authentication events with filtering and summary stats.
"""
import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify


def create_access_log_layout():
    """Create the access log viewer layout at /admin/access-log."""
    return dmc.Container(
        children=[
            # Header
            dmc.Group(
                children=[
                    dmc.Group(
                        children=[
                            DashIconify(icon="mdi:shield-lock", width=28, color="#228be6"),
                            dmc.Title("Access Log", order=2),
                        ],
                        gap="xs",
                    ),
                    dmc.Badge("Admin", color="red", variant="light"),
                ],
                justify="space-between",
                mb="lg",
            ),

            # Filters
            dmc.Paper(
                children=[
                    dmc.Group(
                        children=[
                            dmc.Select(
                                id="access-log-filter-event",
                                label="Event Type",
                                data=[
                                    {"value": "", "label": "All Events"},
                                    {"value": "login", "label": "Login"},
                                    {"value": "logout", "label": "Logout"},
                                    {"value": "pin_attempt", "label": "Failed Attempt"},
                                    {"value": "page_blocked", "label": "Page Blocked"},
                                ],
                                value="",
                                clearable=True,
                                w=160,
                            ),
                            dmc.Select(
                                id="access-log-filter-success",
                                label="Result",
                                data=[
                                    {"value": "", "label": "All"},
                                    {"value": "true", "label": "Success"},
                                    {"value": "false", "label": "Failed"},
                                ],
                                value="",
                                clearable=True,
                                w=120,
                            ),
                            dmc.Select(
                                id="access-log-filter-days",
                                label="Time Range",
                                data=[
                                    {"value": "1", "label": "Last 24 hours"},
                                    {"value": "7", "label": "Last 7 days"},
                                    {"value": "30", "label": "Last 30 days"},
                                    {"value": "90", "label": "Last 90 days"},
                                ],
                                value="30",
                                w=160,
                            ),
                            dmc.Button(
                                "Refresh",
                                id="access-log-refresh-btn",
                                leftSection=DashIconify(icon="mdi:refresh", width=16),
                                variant="light",
                                mt="xl",
                            ),
                        ],
                        gap="md",
                    ),
                ],
                p="md",
                withBorder=True,
                radius="md",
                mb="md",
            ),

            # Summary stats
            html.Div(id="access-log-summary"),

            # Events table
            dmc.Paper(
                children=[
                    dmc.Text("Events", fw=600, mb="sm"),
                    dmc.ScrollArea(
                        children=[html.Div(id="access-log-table")],
                        h=500,
                    ),
                ],
                p="md",
                withBorder=True,
                radius="md",
            ),
        ],
        size="lg",
        py="md",
    )
