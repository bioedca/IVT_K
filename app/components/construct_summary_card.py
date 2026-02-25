"""
Construct summary card component for forest plot interaction.

Phase 4: UX Enhancements - Construct Summary Card

Provides:
- Modal displaying construct details on forest plot click
- Construct metadata display (family, type, replicates)
- Fold change and confidence interval display
- Precision status indicator
- Plate breakdown table
- Navigation to curve browser
"""
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime

import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify


class PrecisionStatus(str, Enum):
    """Precision target status values."""
    MET = "met"
    NOT_MET = "not_met"
    PENDING = "pending"


# Color mappings for precision status
PRECISION_COLORS = {
    PrecisionStatus.MET: "green",
    PrecisionStatus.NOT_MET: "orange",
    PrecisionStatus.PENDING: "gray",
    "met": "green",
    "not_met": "orange",
    "pending": "gray",
}

# Icons for precision status
PRECISION_ICONS = {
    PrecisionStatus.MET: "tabler:check",
    PrecisionStatus.NOT_MET: "tabler:alert-triangle",
    PrecisionStatus.PENDING: "tabler:clock",
    "met": "tabler:check",
    "not_met": "tabler:alert-triangle",
    "pending": "tabler:clock",
}


def format_confidence_interval(
    lower: Optional[float],
    upper: Optional[float],
    precision: int = 2
) -> str:
    """
    Format confidence interval for display.

    Args:
        lower: Lower bound of CI.
        upper: Upper bound of CI.
        precision: Number of decimal places.

    Returns:
        Formatted string like "[1.50, 2.50]"
    """
    if lower is None or upper is None:
        return "[-, -]"
    return f"[{lower:.{precision}f}, {upper:.{precision}f}]"


def format_fold_change(
    value: Optional[float],
    precision: int = 2
) -> str:
    """
    Format fold change value for display.

    Args:
        value: Fold change value.
        precision: Number of decimal places.

    Returns:
        Formatted string like "2.34"
    """
    if value is None:
        return "-"
    return f"{value:.{precision}f}"


def get_precision_status_badge(
    status: PrecisionStatus | str
) -> dmc.Badge:
    """
    Create a badge for precision status.

    Args:
        status: PrecisionStatus enum or string value.

    Returns:
        Badge component with appropriate color and icon.
    """
    color = PRECISION_COLORS.get(status, "gray")
    icon = PRECISION_ICONS.get(status, "tabler:question-mark")

    if isinstance(status, PrecisionStatus):
        label = status.value.replace("_", " ").title()
    else:
        label = str(status).replace("_", " ").title()

    return dmc.Badge(
        children=[
            DashIconify(icon=icon, width=14),
            f" {label}"
        ],
        color=color,
        variant="light",
        size="md"
    )


def create_construct_header(
    construct_name: str
) -> dmc.Group:
    """
    Create the header section with construct name.

    Args:
        construct_name: Name of the construct.

    Returns:
        Group component with title and close button placeholder.
    """
    return dmc.Group(
        [
            dmc.Text(f"Construct: {construct_name}", fw=600, size="lg"),
        ],
        justify="space-between"
    )


def create_construct_metadata(
    family: str,
    construct_type: str,
    total_replicates: int,
    description: Optional[str] = None
) -> dmc.SimpleGrid:
    """
    Create metadata panel showing construct information.

    Args:
        family: Construct family name.
        construct_type: Type (e.g., "Mutant", "Wild-type").
        total_replicates: Total number of replicates.
        description: Optional description text.

    Returns:
        SimpleGrid component with metadata fields.
    """
    items = [
        dmc.Stack(
            [
                dmc.Text("Family", c="dimmed", size="xs"),
                dmc.Text(family, fw=500, size="sm")
            ],
            gap=2
        ),
        dmc.Stack(
            [
                dmc.Text("Type", c="dimmed", size="xs"),
                dmc.Text(construct_type, fw=500, size="sm")
            ],
            gap=2
        ),
        dmc.Stack(
            [
                dmc.Text("Total Replicates", c="dimmed", size="xs"),
                dmc.Text(str(total_replicates), fw=500, size="sm")
            ],
            gap=2
        ),
    ]

    return dmc.SimpleGrid(
        children=items,
        cols=3,
        spacing="md"
    )


def create_statistics_panel(
    fold_change: Optional[float],
    ci_lower: Optional[float],
    ci_upper: Optional[float],
    precision_status: PrecisionStatus | str,
    parameter_name: str = "F_max"
) -> dmc.SimpleGrid:
    """
    Create statistics panel showing fold change and CI.

    Args:
        fold_change: Fold change value.
        ci_lower: Lower confidence interval bound.
        ci_upper: Upper confidence interval bound.
        precision_status: Precision target status.
        parameter_name: Name of the parameter (e.g., "F_max").

    Returns:
        SimpleGrid component with statistics.
    """
    return dmc.SimpleGrid(
        [
            dmc.Stack(
                [
                    dmc.Text(f"Fold Change ({parameter_name})", c="dimmed", size="xs"),
                    dmc.Text(format_fold_change(fold_change), fw=600, size="lg")
                ],
                gap=2
            ),
            dmc.Stack(
                [
                    dmc.Text("95% CI", c="dimmed", size="xs"),
                    dmc.Text(
                        format_confidence_interval(ci_lower, ci_upper),
                        fw=500,
                        size="sm"
                    )
                ],
                gap=2
            ),
            dmc.Stack(
                [
                    dmc.Text("Precision Status", c="dimmed", size="xs"),
                    get_precision_status_badge(precision_status)
                ],
                gap=2
            ),
        ],
        cols=3,
        spacing="md"
    )


def create_plate_breakdown_table(
    plates: List[Dict[str, Any]]
) -> dmc.Table:
    """
    Create table showing plate breakdown information.

    Args:
        plates: List of plate dictionaries with name, session, replicates, excluded.

    Returns:
        Table component with plate breakdown.
    """
    if not plates:
        return dmc.Center(
            dmc.Text("No plate data available", c="dimmed", size="sm"),
            h=60
        )

    # Create table header
    header = dmc.TableThead(
        dmc.TableTr([
            dmc.TableTh("Plate"),
            dmc.TableTh("Session"),
            dmc.TableTh("Reps"),
            dmc.TableTh("Excluded"),
        ])
    )

    # Create table rows
    rows = []
    for plate in plates:
        # Handle session as datetime or string
        session = plate.get("session", "-")
        if isinstance(session, datetime):
            session = session.strftime("%Y-%m")

        rows.append(
            dmc.TableTr([
                dmc.TableTd(plate.get("name", "-")),
                dmc.TableTd(str(session)),
                dmc.TableTd(str(plate.get("replicates", 0))),
                dmc.TableTd(str(plate.get("excluded", 0))),
            ])
        )

    body = dmc.TableTbody(rows)

    return dmc.Table(
        [header, body],
        striped=True,
        highlightOnHover=True,
        withTableBorder=True,
        withColumnBorders=True
    )


def create_card_actions(
    construct_id: int
) -> dmc.Group:
    """
    Create action buttons for the card.

    Args:
        construct_id: ID of the construct for navigation.

    Returns:
        Group component with action buttons.
    """
    return dmc.Group(
        [
            dmc.Button(
                id={"type": "construct-view-wells", "index": construct_id},
                children=[
                    DashIconify(icon="tabler:list-details", width=16),
                    "View All Wells"
                ],
                variant="outline",
                color="blue"
            ),
            dmc.Button(
                id="construct-summary-close",
                children="Close",
                variant="subtle",
                color="gray"
            )
        ],
        justify="flex-end",
        mt="md"
    )


def create_construct_summary_card(
    construct_id: int,
    construct_name: str,
    family: str,
    construct_type: str,
    total_replicates: int,
    fold_change: Optional[float],
    ci_lower: Optional[float],
    ci_upper: Optional[float],
    precision_status: PrecisionStatus | str,
    plates: List[Dict[str, Any]],
    parameter_name: str = "F_max",
    description: Optional[str] = None
) -> dmc.Modal:
    """
    Create the main construct summary card modal.

    This modal appears when clicking a point on a forest plot,
    showing detailed information about the construct.

    Args:
        construct_id: Unique ID of the construct.
        construct_name: Name of the construct.
        family: Construct family name.
        construct_type: Type (Mutant, Wild-type, etc.).
        total_replicates: Total number of replicates.
        fold_change: Fold change value.
        ci_lower: Lower CI bound.
        ci_upper: Upper CI bound.
        precision_status: Precision target status.
        plates: List of plate breakdown dictionaries.
        parameter_name: Parameter name for display.
        description: Optional construct description.

    Returns:
        Modal component with construct summary.
    """
    return dmc.Modal(
        id="construct-summary-modal",
        title=create_construct_header(construct_name),
        children=[
            # Store for construct data
            dcc.Store(
                id="construct-summary-store",
                data={"construct_id": construct_id}
            ),

            dmc.Stack(
                [
                    # Metadata section
                    create_construct_metadata(
                        family=family,
                        construct_type=construct_type,
                        total_replicates=total_replicates,
                        description=description
                    ),

                    dmc.Divider(),

                    # Statistics section
                    create_statistics_panel(
                        fold_change=fold_change,
                        ci_lower=ci_lower,
                        ci_upper=ci_upper,
                        precision_status=precision_status,
                        parameter_name=parameter_name
                    ),

                    dmc.Divider(),

                    # Plate breakdown section
                    dmc.Stack(
                        [
                            dmc.Text("PLATE BREAKDOWN", c="dimmed", size="xs", fw=600),
                            create_plate_breakdown_table(plates)
                        ],
                        gap="xs"
                    ),

                    # Action buttons
                    create_card_actions(construct_id)
                ],
                gap="md"
            )
        ],
        opened=True,
        size="lg",
        centered=True
    )


def create_construct_summary_skeleton() -> dmc.Modal:
    """
    Create skeleton loading state for construct summary card.

    Returns:
        Modal component with skeleton elements.
    """
    return dmc.Modal(
        id="construct-summary-modal-skeleton",
        title=dmc.Skeleton(height=24, width="60%"),
        children=[
            dmc.Stack(
                [
                    # Metadata skeleton
                    dmc.SimpleGrid(
                        [
                            dmc.Skeleton(height=40) for _ in range(3)
                        ],
                        cols=3
                    ),

                    dmc.Divider(),

                    # Statistics skeleton
                    dmc.SimpleGrid(
                        [
                            dmc.Skeleton(height=50) for _ in range(3)
                        ],
                        cols=3
                    ),

                    dmc.Divider(),

                    # Table skeleton
                    dmc.Skeleton(height=120),

                    # Actions skeleton
                    dmc.Group(
                        [
                            dmc.Skeleton(height=36, width=120),
                            dmc.Skeleton(height=36, width=80)
                        ],
                        justify="flex-end"
                    )
                ],
                gap="md"
            )
        ],
        opened=True,
        size="lg"
    )
