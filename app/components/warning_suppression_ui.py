"""
Warning suppression UI components.

Phase 4: UX Enhancements - Warning Suppression UI

Provides:
- Warning suppression modal
- Suppressible warning card
- Suppression reason input
- Suppression history list
"""
from typing import Optional, List, Dict, Any
from datetime import datetime

import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify

from app.models.warning_suppression import WarningType


# Display names for warning types
WARNING_TYPE_DISPLAY_NAMES = {
    WarningType.INCOMPLETE_PLATE: "Incomplete Plate",
    WarningType.TEMPERATURE_DEVIATION: "Temperature Deviation",
    WarningType.MISSING_NEGATIVE_CONTROL: "Missing Negative Control",
    WarningType.LOW_REPLICATE_COUNT: "Low Replicate Count",
    WarningType.HIGH_CV: "High Coefficient of Variation",
    WarningType.OUTLIER_DETECTED: "Outlier Detected",
    WarningType.EDGE_EFFECT: "Edge Effect",
    WarningType.MISSING_WELLS: "Missing Wells",
}

# Descriptions for warning types
WARNING_TYPE_DESCRIPTIONS = {
    WarningType.INCOMPLETE_PLATE: (
        "Some wells on this plate are missing data or have not been assigned. "
        "This may affect statistical power for constructs on this plate."
    ),
    WarningType.TEMPERATURE_DEVIATION: (
        "Temperature during the experiment deviated more than ±1°C from the setpoint. "
        "This may affect reaction kinetics and comparability."
    ),
    WarningType.MISSING_NEGATIVE_CONTROL: (
        "This plate is missing required negative control wells. "
        "Negative controls are essential for baseline correction."
    ),
    WarningType.LOW_REPLICATE_COUNT: (
        "The number of replicates is below the recommended minimum for "
        "reliable statistical inference."
    ),
    WarningType.HIGH_CV: (
        "Coefficient of variation exceeds acceptable threshold, indicating "
        "high variability between replicates."
    ),
    WarningType.OUTLIER_DETECTED: (
        "Statistical outliers were detected that may affect analysis results. "
        "Review individual curves for anomalies."
    ),
    WarningType.EDGE_EFFECT: (
        "Edge wells show systematic differences from interior wells, "
        "possibly due to evaporation or temperature gradients."
    ),
    WarningType.MISSING_WELLS: (
        "Expected wells are missing data. This may indicate parsing errors "
        "or experimental issues."
    ),
}


def get_warning_type_display_name(warning_type: WarningType) -> str:
    """
    Get display name for a warning type.

    Args:
        warning_type: The warning type enum value.

    Returns:
        Human-readable display name.
    """
    return WARNING_TYPE_DISPLAY_NAMES.get(warning_type, str(warning_type.value))


def get_warning_type_description(warning_type: WarningType) -> str:
    """
    Get description for a warning type.

    Args:
        warning_type: The warning type enum value.

    Returns:
        Detailed description of the warning.
    """
    return WARNING_TYPE_DESCRIPTIONS.get(
        warning_type,
        "This warning indicates a potential issue that may affect data quality."
    )


def create_suppression_reason_input() -> dmc.Textarea:
    """
    Create the reason input field for warning suppression.

    Returns:
        Textarea component for entering suppression reason.
    """
    return dmc.Textarea(
        id="suppression-reason-input",
        label="Reason for Suppression",
        description="Provide a meaningful justification (minimum 10 characters)",
        placeholder="Explain why this warning should be suppressed...",
        required=True,
        minRows=3,
        maxRows=5
    )


def create_warning_suppression_modal(
    warning_type: WarningType,
    plate_id: int,
    well_id: Optional[int] = None
) -> dmc.Modal:
    """
    Create modal for suppressing a warning.

    Args:
        warning_type: Type of warning being suppressed.
        plate_id: ID of the plate.
        well_id: Optional well ID for well-specific warnings.

    Returns:
        Modal component with suppression form.
    """
    display_name = get_warning_type_display_name(warning_type)
    description = get_warning_type_description(warning_type)

    return dmc.Modal(
        id="warning-suppression-modal",
        title=dmc.Group(
            [
                DashIconify(icon="tabler:alert-triangle", width=24, color="orange"),
                dmc.Text(f"Suppress Warning: {display_name}", fw=600)
            ],
            gap="xs"
        ),
        children=[
            # Store for warning data
            dcc.Store(
                id="suppression-modal-store",
                data={
                    "warning_type": warning_type.value,
                    "plate_id": plate_id,
                    "well_id": well_id
                }
            ),

            dmc.Stack(
                [
                    # Warning description
                    dmc.Alert(
                        children=description,
                        color="yellow",
                        icon=DashIconify(icon="tabler:info-circle", width=20)
                    ),

                    # Reason input
                    create_suppression_reason_input(),

                    # Notice about audit trail
                    dmc.Text(
                        "This action will be logged with your username and timestamp.",
                        c="dimmed",
                        size="xs",
                        fs="italic"
                    ),

                    # Action buttons
                    dmc.Group(
                        [
                            dmc.Button(
                                id="suppression-cancel-btn",
                                children="Cancel",
                                variant="subtle",
                                color="gray"
                            ),
                            dmc.Button(
                                id="suppression-confirm-btn",
                                children=[
                                    DashIconify(icon="tabler:check", width=16),
                                    "Suppress Warning"
                                ],
                                variant="filled",
                                color="orange"
                            )
                        ],
                        justify="flex-end"
                    )
                ],
                gap="md"
            )
        ],
        opened=True,
        size="md",
        centered=True
    )


def create_suppressible_warning_card(
    warning_type: WarningType,
    message: str,
    plate_id: int,
    well_id: Optional[int] = None,
    is_suppressed: bool = False,
    suppression_reason: Optional[str] = None
) -> dmc.Alert:
    """
    Create a warning card that can be suppressed.

    Args:
        warning_type: Type of warning.
        message: Warning message to display.
        plate_id: ID of the plate.
        well_id: Optional well ID.
        is_suppressed: Whether warning is currently suppressed.
        suppression_reason: Reason if suppressed.

    Returns:
        Alert component with warning and suppress button.
    """
    display_name = get_warning_type_display_name(warning_type)

    if is_suppressed:
        # Show suppressed state
        return dmc.Alert(
            id={"type": "warning-card", "warning": warning_type.value, "plate": plate_id},
            title=f"{display_name} (Suppressed)",
            children=dmc.Stack(
                [
                    dmc.Text(message, size="sm"),
                    dmc.Text(
                        f"Reason: {suppression_reason}",
                        c="dimmed",
                        size="xs",
                        fs="italic"
                    )
                ],
                gap="xs"
            ),
            color="gray",
            variant="light",
            icon=DashIconify(icon="tabler:eye-off", width=20)
        )

    # Show active warning with suppress button
    return dmc.Alert(
        id={"type": "warning-card", "warning": warning_type.value, "plate": plate_id},
        title=display_name,
        children=dmc.Stack(
            [
                dmc.Text(message, size="sm"),
                dmc.Button(
                    id={
                        "type": "suppress-warning-btn",
                        "warning": warning_type.value,
                        "plate": plate_id,
                        "well": well_id or ""
                    },
                    children=[
                        DashIconify(icon="tabler:eye-off", width=16),
                        "Suppress"
                    ],
                    variant="subtle",
                    color="yellow",
                    size="xs",
                    mt="xs"
                )
            ],
            gap="xs"
        ),
        color="yellow",
        variant="light",
        icon=DashIconify(icon="tabler:alert-triangle", width=20)
    )


def create_suppression_history_list(
    suppressions: List[Dict[str, Any]]
) -> dmc.Stack:
    """
    Create a list showing suppression history.

    Args:
        suppressions: List of suppression dictionaries.

    Returns:
        Stack component with suppression history items.
    """
    if not suppressions:
        return dmc.Stack(
            [
                dmc.Center(
                    dmc.Text(
                        "No suppressions recorded",
                        c="dimmed",
                        size="sm"
                    ),
                    h=60
                )
            ]
        )

    # Sort by date (newest first)
    sorted_suppressions = sorted(
        suppressions,
        key=lambda x: x.get("suppressed_at", ""),
        reverse=True
    )

    items = []
    for suppression in sorted_suppressions:
        warning_type = suppression.get("warning_type", "unknown")

        # Handle warning_type as enum or string
        if isinstance(warning_type, WarningType):
            display_name = get_warning_type_display_name(warning_type)
        else:
            # Try to convert string to enum
            try:
                display_name = get_warning_type_display_name(WarningType(warning_type))
            except (ValueError, KeyError):
                display_name = str(warning_type).replace("_", " ").title()

        # Format timestamp
        suppressed_at = suppression.get("suppressed_at")
        if isinstance(suppressed_at, datetime):
            timestamp = suppressed_at.strftime("%Y-%m-%d %H:%M")
        elif isinstance(suppressed_at, str):
            timestamp = suppressed_at[:16] if len(suppressed_at) > 16 else suppressed_at
        else:
            timestamp = "Unknown"

        items.append(
            dmc.Paper(
                children=dmc.Stack(
                    [
                        dmc.Group(
                            [
                                dmc.Badge(display_name, color="gray", size="sm"),
                                dmc.Text(
                                    f"by {suppression.get('suppressed_by', 'Unknown')}",
                                    c="dimmed",
                                    size="xs"
                                )
                            ],
                            justify="space-between"
                        ),
                        dmc.Text(
                            suppression.get("reason", "No reason provided"),
                            size="sm"
                        ),
                        dmc.Text(
                            timestamp,
                            c="dimmed",
                            size="xs"
                        )
                    ],
                    gap="xs"
                ),
                p="sm",
                withBorder=True,
                radius="sm"
            )
        )

    return dmc.Stack(
        children=items,
        gap="sm"
    )
