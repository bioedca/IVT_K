"""
Reusable empty state and no-data components.

UX Overhaul Phase 10: Consistent empty states across the application.
"""
import dash_mantine_components as dmc
from dash import html
from dash_iconify import DashIconify


def create_empty_state(
    icon: str = "mdi:inbox-outline",
    title: str = "No Data",
    description: str = "There's nothing here yet.",
    action_button=None,
    icon_size: int = 48,
    icon_color: str = "gray",
):
    """
    Create a reusable empty state component.

    Args:
        icon: DashIconify icon name
        title: Main heading
        description: Subtext explanation
        action_button: Optional Dash component (e.g. dmc.Button) for CTA
        icon_size: Icon size in pixels
        icon_color: Mantine color name for icon

    Returns:
        Centered empty state component
    """
    children = [
        DashIconify(
            icon=icon,
            width=icon_size,
            color=f"var(--mantine-color-{icon_color}-4)",
        ),
        dmc.Title(title, order=4, c="dimmed", mt="md"),
        dmc.Text(description, c="dimmed", size="sm", ta="center", maw=400),
    ]
    if action_button:
        children.append(html.Div(action_button, style={"marginTop": "1rem"}))

    return dmc.Center(
        dmc.Stack(
            children=children,
            align="center",
            gap="xs",
        ),
        style={"padding": "3rem 1rem"},
    )


def create_no_data_chart(message: str = "No data to display"):
    """
    Create a styled empty state for chart areas.

    Args:
        message: Message to show in the empty chart area

    Returns:
        Styled empty chart placeholder
    """
    return dmc.Center(
        dmc.Stack(
            children=[
                DashIconify(
                    icon="mdi:chart-line-variant",
                    width=36,
                    color="var(--mantine-color-gray-4)",
                ),
                dmc.Text(message, c="dimmed", size="sm"),
            ],
            align="center",
            gap="xs",
        ),
        style={
            "padding": "2rem",
            "minHeight": "200px",
            "border": "1px dashed var(--mantine-color-gray-3)",
            "borderRadius": "var(--mantine-radius-md)",
        },
    )
