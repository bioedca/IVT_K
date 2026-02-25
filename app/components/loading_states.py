"""
Reusable loading skeleton components.

UX Overhaul Phase 10: Consistent loading states across the application.
"""
import dash_mantine_components as dmc
from dash import html


def create_page_skeleton():
    """Create a full-page loading skeleton."""
    return dmc.Container(
        children=[
            dmc.Skeleton(height=36, width=300, mb="lg"),
            dmc.Skeleton(height=16, width=200, mb="xl"),
            dmc.Grid(
                children=[
                    dmc.GridCol(
                        dmc.Skeleton(height=200, radius="lg"),
                        span=8,
                    ),
                    dmc.GridCol(
                        dmc.Stack([
                            dmc.Skeleton(height=90, radius="lg"),
                            dmc.Skeleton(height=90, radius="lg"),
                        ], gap="md"),
                        span=4,
                    ),
                ],
                gutter="lg",
            ),
        ],
        size="lg",
        style={"paddingTop": "1rem"},
    )


def create_table_skeleton(rows: int = 5):
    """
    Create a table loading skeleton.

    Args:
        rows: Number of skeleton rows to show
    """
    header = dmc.Group(
        children=[
            dmc.Skeleton(height=14, width="20%"),
            dmc.Skeleton(height=14, width="15%"),
            dmc.Skeleton(height=14, width="25%"),
            dmc.Skeleton(height=14, width="15%"),
            dmc.Skeleton(height=14, width="10%"),
        ],
        gap="md",
        mb="sm",
    )
    row_skeletons = [
        dmc.Skeleton(height=40, radius="sm", mb=4)
        for _ in range(rows)
    ]
    return html.Div([header] + row_skeletons)


def create_card_skeleton():
    """Create a single card loading skeleton."""
    return dmc.Paper(
        children=[
            dmc.Group(
                children=[
                    dmc.Skeleton(height=20, width="60%"),
                    dmc.Skeleton(height=20, width=60, radius="xl"),
                ],
                justify="space-between",
                mb="sm",
            ),
            dmc.Skeleton(height=14, width="90%", mb="xs"),
            dmc.Skeleton(height=14, width="70%", mb="md"),
            dmc.Group(
                children=[
                    dmc.Skeleton(height=14, width=80),
                    dmc.Skeleton(height=14, width=80),
                    dmc.Skeleton(height=14, width=80),
                ],
                gap="lg",
            ),
        ],
        p="lg",
        withBorder=True,
        radius="lg",
    )


def create_chart_skeleton():
    """Create a chart area loading skeleton."""
    return dmc.Paper(
        children=[
            dmc.Skeleton(height=14, width=120, mb="md"),
            dmc.Skeleton(height=250, radius="md"),
        ],
        p="md",
        withBorder=True,
        radius="lg",
    )
