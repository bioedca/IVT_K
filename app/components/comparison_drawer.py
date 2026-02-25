"""
Comparison drawer component for curve comparison.

Phase 4: UX Enhancements - Comparison Drawer

Provides:
- Floating badge showing comparison count
- Side drawer with comparison list
- Add/remove curve functionality
- View Side-by-Side action
- Clear All action
"""
from typing import Optional, List, Dict, Any

import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify


# Constants
MAX_COMPARISON_ITEMS = 10
DRAWER_WIDTH = 400


def get_drawer_position_styles() -> Dict[str, Any]:
    """
    Get CSS styles for drawer position.

    Returns:
        Dictionary with CSS position properties for bottom-right placement.
    """
    return {
        "bottom": 20,
        "right": 20
    }


def create_comparison_badge(count: int = 0) -> dmc.ActionIcon:
    """
    Create the floating badge showing comparison count.

    Args:
        count: Number of items in comparison set.

    Returns:
        ActionIcon component with Badge showing count.
    """
    return dmc.ActionIcon(
        id="comparison-badge",
        children=dmc.Badge(
            id="comparison-count",
            children=str(count),
            color="blue" if count > 0 else "gray",
            size="lg",
            circle=True,
            variant="filled"
        ),
        variant="filled",
        color="blue",
        size="xl",
        radius="xl",
        style={"cursor": "pointer"}
    )


def create_comparison_list_item(
    curve_id: str,
    construct_name: str,
    plate_name: str,
    well_position: Optional[str] = None,
    session_name: Optional[str] = None,
) -> dmc.Paper:
    """
    Create a single item in the comparison list.

    Args:
        curve_id: Unique identifier for the curve.
        construct_name: Name of the construct.
        plate_name: Name of the plate.
        well_position: Optional well position (e.g., "A1").
        session_name: Optional session name.

    Returns:
        Paper component representing the comparison item.
    """
    # Build subtitle with optional info
    subtitle_parts = [plate_name]
    if well_position:
        subtitle_parts.append(well_position)
    if session_name:
        subtitle_parts.append(session_name)
    subtitle = " • ".join(subtitle_parts)

    return dmc.Paper(
        id={"type": "comparison-item", "index": curve_id},
        children=dmc.Group(
            [
                dmc.Stack(
                    [
                        dmc.Text(construct_name, fw=500, size="sm"),
                        dmc.Text(subtitle, c="dimmed", size="xs"),
                    ],
                    gap=2,
                    style={"flex": 1}
                ),
                dmc.ActionIcon(
                    id={"type": "comparison-remove", "index": curve_id},
                    children=DashIconify(icon="tabler:x", width=16),
                    variant="subtle",
                    color="gray",
                    size="sm"
                )
            ],
            justify="space-between",
            wrap="nowrap"
        ),
        p="xs",
        withBorder=True,
        radius="sm",
        mb="xs"
    )


def create_comparison_list(items: List[Dict[str, Any]]) -> dmc.Stack:
    """
    Create the comparison list from items.

    Args:
        items: List of dictionaries with curve_id, construct_name, plate_name, etc.

    Returns:
        Stack component containing comparison items or empty message.
    """
    if not items:
        return dmc.Stack(
            id="comparison-list",
            children=[
                dmc.Center(
                    dmc.Stack(
                        [
                            DashIconify(
                                icon="tabler:chart-line",
                                width=48,
                                color="gray"
                            ),
                            dmc.Text(
                                "No curves added",
                                c="dimmed",
                                size="sm",
                                ta="center"
                            ),
                            dmc.Text(
                                "Click 'Add to Comparison' on curves to compare them side-by-side",
                                c="dimmed",
                                size="xs",
                                ta="center"
                            )
                        ],
                        align="center",
                        gap="xs"
                    ),
                    h=200
                )
            ],
            gap="xs"
        )

    # Limit items to max
    display_items = items[:MAX_COMPARISON_ITEMS]

    item_components = [
        create_comparison_list_item(
            curve_id=item.get("curve_id", str(i)),
            construct_name=item.get("construct_name", "Unknown"),
            plate_name=item.get("plate_name", "Unknown Plate"),
            well_position=item.get("well_position"),
            session_name=item.get("session_name"),
        )
        for i, item in enumerate(display_items)
    ]

    return dmc.Stack(
        id="comparison-list",
        children=item_components,
        gap="xs"
    )


def create_comparison_actions(
    has_items: bool = False,
    item_count: int = 0
) -> dmc.Group:
    """
    Create action buttons for comparison drawer.

    Args:
        has_items: Whether there are items in the comparison set.
        item_count: Number of items in comparison set.

    Returns:
        Group component with action buttons.
    """
    # View button requires at least 2 items
    view_disabled = item_count < 2
    clear_disabled = not has_items

    return dmc.Group(
        [
            dmc.Button(
                id="view-comparison",
                children=[
                    DashIconify(icon="tabler:columns", width=16),
                    "View Side-by-Side"
                ],
                leftSection=None,
                variant="filled",
                color="blue",
                disabled=view_disabled,
                style={"flex": 1}
            ),
            dmc.Button(
                id="clear-comparison",
                children=[
                    DashIconify(icon="tabler:trash", width=16),
                    "Clear All"
                ],
                variant="outline",
                color="red",
                disabled=clear_disabled
            )
        ],
        justify="stretch",
        mt="md"
    )


def create_comparison_drawer(
    initial_items: Optional[List[Dict[str, Any]]] = None,
    is_open: bool = False
) -> dmc.Box:
    """
    Create the main comparison drawer component.

    This component includes:
    - A floating badge showing comparison count (bottom-right)
    - A side drawer with comparison list and actions
    - State management via dcc.Store

    Args:
        initial_items: Optional list of initial comparison items.
        is_open: Whether drawer is initially open.

    Returns:
        Box component containing Affix (badge) and Drawer.
    """
    items = initial_items or []
    position_styles = get_drawer_position_styles()

    return dmc.Box(
        children=[
            # State store for comparison items
            dcc.Store(
                id="comparison-store",
                data={"items": items, "last_clicked": None},
                storage_type="session"
            ),

            # Floating badge (Affix positioned at bottom-right)
            dmc.Affix(
                id="comparison-affix",
                children=create_comparison_badge(count=len(items)),
                position=position_styles,
                zIndex=100
            ),

            # Side drawer
            dmc.Drawer(
                id="comparison-drawer",
                title=dmc.Group(
                    [
                        DashIconify(icon="tabler:chart-dots-3", width=24),
                        dmc.Text("Comparison Set", fw=600)
                    ],
                    gap="xs"
                ),
                children=[
                    dmc.Stack(
                        [
                            # Item count info
                            dmc.Text(
                                f"{len(items)} of {MAX_COMPARISON_ITEMS} curves",
                                c="dimmed",
                                size="sm"
                            ),
                            dmc.Divider(),

                            # Scrollable list
                            dmc.ScrollArea(
                                children=create_comparison_list(items),
                                h=400,
                                type="auto"
                            ),

                            # Action buttons
                            create_comparison_actions(
                                has_items=len(items) > 0,
                                item_count=len(items)
                            )
                        ],
                        gap="md"
                    )
                ],
                opened=is_open,
                position="right",
                size=DRAWER_WIDTH,
                padding="md",
                zIndex=200
            )
        ]
    )


def create_comparison_drawer_skeleton() -> dmc.Box:
    """
    Create skeleton loading state for comparison drawer.

    Returns:
        Box component with skeleton elements.
    """
    return dmc.Box(
        children=[
            dmc.Affix(
                children=dmc.Skeleton(
                    circle=True,
                    height=48,
                    width=48
                ),
                position=get_drawer_position_styles()
            )
        ]
    )
