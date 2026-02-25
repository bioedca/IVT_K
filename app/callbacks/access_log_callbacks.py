"""Callbacks for the access log viewer page."""
from datetime import datetime, timedelta, timezone

from dash import callback, Input, Output, State, no_update
from dash.exceptions import PreventUpdate
import dash_mantine_components as dmc
from dash_iconify import DashIconify
from dash import html


def register_access_log_callbacks(app):
    """Register access log viewer callbacks."""

    @app.callback(
        Output("access-log-summary", "children"),
        Output("access-log-table", "children"),
        Input("access-log-refresh-btn", "n_clicks"),
        Input("access-log-filter-event", "value"),
        Input("access-log-filter-success", "value"),
        Input("access-log-filter-days", "value"),
        prevent_initial_call=False,
    )
    def update_access_log(_n_clicks, event_filter, success_filter, days_filter):
        """Load and filter access log entries."""
        from app.models.access_log import AccessLog

        try:
            days = int(days_filter) if days_filter else 30
        except (ValueError, TypeError):
            days = 30
        since = datetime.now(timezone.utc) - timedelta(days=days)

        query = AccessLog.query.filter(AccessLog.timestamp >= since)

        if event_filter:
            query = query.filter(AccessLog.event_type == event_filter)
        if success_filter == "true":
            query = query.filter(AccessLog.success.is_(True))
        elif success_filter == "false":
            query = query.filter(AccessLog.success.is_(False))

        limit = 500
        logs = query.order_by(AccessLog.timestamp.desc()).limit(limit).all()

        # Summary stats
        total = len(logs)
        truncated = total == limit
        total_display = f"{total}+" if truncated else str(total)
        logins = sum(1 for l in logs if l.event_type == "login" and l.success)
        failed = sum(1 for l in logs if not l.success)
        unique_ips = len({l.ip_address for l in logs if l.ip_address})

        summary = dmc.Group(
            children=[
                _stat_card("Total Events", total_display, "blue"),
                _stat_card("Successful Logins", str(logins), "green"),
                _stat_card("Failed Attempts", str(failed), "red"),
                _stat_card("Unique IPs", str(unique_ips), "violet"),
            ],
            gap="md",
            mb="md",
        )

        if not logs:
            table = dmc.Stack(
                children=[
                    DashIconify(icon="mdi:shield-check", width=48, color="#868e96"),
                    dmc.Text("No access events found", fw=500, c="dimmed"),
                ],
                align="center",
                gap="xs",
                py="xl",
            )
        else:
            rows = [_log_row(log) for log in logs]
            table = dmc.Stack(children=rows, gap="xs")

        return summary, table


def _stat_card(label, value, color):
    return dmc.Paper(
        children=[
            dmc.Stack(
                children=[
                    dmc.Text(label, size="xs", c="dimmed"),
                    dmc.Text(value, fw=700, size="xl", c=color),
                ],
                gap=2,
                align="center",
            ),
        ],
        p="md",
        withBorder=True,
        radius="md",
        w=160,
    )


def _log_row(log):
    """Render a single access log entry as a row."""
    color_map = {
        "login": "green",
        "logout": "blue",
        "pin_attempt": "red",
        "page_blocked": "orange",
    }
    icon_map = {
        "login": "mdi:login",
        "logout": "mdi:logout",
        "pin_attempt": "mdi:shield-alert",
        "page_blocked": "mdi:shield-off",
    }

    color = color_map.get(log.event_type, "gray")
    icon = icon_map.get(log.event_type, "mdi:information")
    time_str = log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else ""

    return dmc.Paper(
        children=[
            dmc.Group(
                children=[
                    dmc.ThemeIcon(
                        DashIconify(icon=icon, width=16),
                        color=color,
                        variant="light",
                        size="md",
                        radius="xl",
                    ),
                    dmc.Badge(
                        (log.event_type or "unknown").replace("_", " ").title(),
                        color=color,
                        size="sm",
                        variant="light",
                    ),
                    dmc.Badge(
                        "OK" if log.success else "FAIL",
                        color="green" if log.success else "red",
                        size="sm",
                    ),
                    dmc.Text(log.ip_address or "—", size="sm", c="dimmed", ff="monospace"),
                    dmc.Text(time_str, size="xs", c="dimmed"),
                    dmc.Text(log.details or "", size="xs", c="dimmed", style={"flex": 1}),
                ],
                gap="sm",
            ),
        ],
        p="xs",
        withBorder=True,
        radius="sm",
    )
