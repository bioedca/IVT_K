"""
Interactive Repair Wizard for file parsing issues.

Phase 3.7: Interactive Repair Wizard (F6.7)

Provides UI for:
- Column mapping for misaligned data
- Well position correction
- Skip row configuration
- Data preview before import
"""
from typing import Optional, List, Dict, Any
import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify


def create_repair_wizard_modal() -> dmc.Modal:
    """
    Create the file repair wizard modal.

    Returns:
        Modal component for repair wizard
    """
    return dmc.Modal(
        id="repair-wizard-modal",
        title="File Repair Wizard",
        size="xl",
        centered=True,
        opened=False,
        closeOnClickOutside=False,
        children=[
            # Store for wizard state
            dcc.Store(id="repair-wizard-state", data={
                "step": 1,
                "file_content": None,
                "file_lines": [],
                "header_row": None,
                "skip_rows": [],
                "column_mapping": {},
                "parsed_preview": None,
            }),

            # Wizard content container
            html.Div(id="repair-wizard-content", children=[
                _create_step_indicator(),
                html.Div(id="repair-wizard-step-content"),
            ]),

            # Footer with navigation buttons
            dmc.Group(
                justify="space-between",
                mt="lg",
                children=[
                    dmc.Button(
                        "Cancel",
                        id="repair-wizard-cancel-btn",
                        variant="outline",
                        color="gray",
                    ),
                    dmc.Group(
                        children=[
                            dmc.Button(
                                "Back",
                                id="repair-wizard-back-btn",
                                variant="light",
                                leftSection=DashIconify(icon="mdi:arrow-left"),
                                disabled=True,
                            ),
                            dmc.Button(
                                "Next",
                                id="repair-wizard-next-btn",
                                rightSection=DashIconify(icon="mdi:arrow-right"),
                            ),
                            dmc.Button(
                                "Import",
                                id="repair-wizard-import-btn",
                                color="green",
                                leftSection=DashIconify(icon="mdi:check"),
                                style={"display": "none"},
                            ),
                        ]
                    )
                ]
            )
        ]
    )


def _create_step_indicator() -> dmc.Stepper:
    """Create the step indicator component."""
    return dmc.Stepper(
        id="repair-wizard-stepper",
        active=0,
        size="sm",
        mb="lg",
        children=[
            dmc.StepperStep(
                label="Preview",
                description="View raw file",
                icon=DashIconify(icon="mdi:file-document-outline"),
            ),
            dmc.StepperStep(
                label="Header Row",
                description="Specify data start",
                icon=DashIconify(icon="mdi:format-header-1"),
            ),
            dmc.StepperStep(
                label="Skip Rows",
                description="Optional exclusions",
                icon=DashIconify(icon="mdi:format-list-bulleted"),
            ),
            dmc.StepperStep(
                label="Column Mapping",
                description="Map columns",
                icon=DashIconify(icon="mdi:table-column"),
            ),
            dmc.StepperStep(
                label="Preview Data",
                description="Verify parsing",
                icon=DashIconify(icon="mdi:check-circle-outline"),
            ),
        ]
    )


def create_step1_preview(
    file_lines: List[str],
    issue_message: str = "File parsing failed"
) -> html.Div:
    """
    Create Step 1: Raw file preview.

    Args:
        file_lines: Lines from the raw file
        issue_message: Description of the issue detected

    Returns:
        Div with file preview
    """
    # Format lines with line numbers
    formatted_lines = []
    for i, line in enumerate(file_lines[:100], 1):  # Show first 100 lines
        # Truncate long lines
        display_line = line[:150] + "..." if len(line) > 150 else line
        formatted_lines.append(
            html.Div(
                children=[
                    html.Span(
                        f"{i:4d}: ",
                        style={
                            "color": "gray",
                            "fontFamily": "monospace",
                            "marginRight": "8px"
                        }
                    ),
                    html.Span(
                        display_line,
                        style={"fontFamily": "monospace"}
                    )
                ],
                style={"marginBottom": "2px"}
            )
        )

    return html.Div([
        # Issue alert
        dmc.Alert(
            title="Issue Detected",
            children=issue_message,
            color="yellow",
            icon=DashIconify(icon="mdi:alert"),
            mb="md",
        ),

        # Instructions
        dmc.Text(
            "Review the file contents below. Look for where the data header row begins "
            "(typically contains 'Time', 'T', and well identifiers like 'A1', 'A2', etc.)",
            size="sm",
            c="dimmed",
            mb="md",
        ),

        # File preview
        dmc.Paper(
            children=[
                dmc.ScrollArea(
                    children=formatted_lines,
                    h=400,
                )
            ],
            p="md",
            withBorder=True,
            style={"backgroundColor": "var(--bg-surface)"}
        ),

        # Show line count
        dmc.Text(
            f"Showing first {min(len(file_lines), 100)} of {len(file_lines)} lines",
            size="xs",
            c="dimmed",
            mt="xs",
        ),
    ])


def create_step2_header_row(
    file_lines: List[str],
    suggested_row: Optional[int] = None
) -> html.Div:
    """
    Create Step 2: Header row specification.

    Args:
        file_lines: Lines from the raw file
        suggested_row: Auto-detected header row (1-indexed)

    Returns:
        Div with header row selector
    """
    # Try to find lines that look like headers
    candidate_lines = []
    for i, line in enumerate(file_lines[:100], 1):
        lower_line = line.lower()
        if 'time' in lower_line and ('a1' in lower_line or 'temperature' in lower_line):
            candidate_lines.append((i, line[:100]))

    return html.Div([
        dmc.Text(
            "Specify the line number where the data header row is located.",
            size="sm",
            mb="md",
        ),

        # Suggested rows
        html.Div([
            dmc.Text("Possible header rows detected:", fw=500, mb="xs"),
            html.Div([
                dmc.Paper(
                    children=[
                        dmc.Group([
                            dmc.Badge(f"Line {num}", color="blue"),
                            dmc.Text(preview, size="xs", style={"fontFamily": "monospace"}),
                            dmc.ActionIcon(
                                DashIconify(icon="mdi:check"),
                                id={"type": "select-header-row", "index": num},
                                color="green",
                                variant="light",
                            )
                        ], justify="space-between")
                    ],
                    p="xs",
                    mb="xs",
                    withBorder=True,
                )
                for num, preview in candidate_lines
            ]) if candidate_lines else dmc.Text("No candidate rows detected", c="dimmed", size="sm"),
        ], style={"marginBottom": "20px"}) if candidate_lines else None,

        # Manual input
        dmc.NumberInput(
            id="repair-header-row-input",
            label="Header row line number",
            description="Line number where column headers appear (1-indexed)",
            value=suggested_row or (candidate_lines[0][0] if candidate_lines else 1),
            min=1,
            max=len(file_lines),
            step=1,
            style={"maxWidth": "200px"},
        ),

        # Preview of selected line
        dmc.Paper(
            id="repair-header-preview",
            children=[
                dmc.Text("Selected header row:", size="sm", fw=500),
                dmc.Code(
                    file_lines[suggested_row - 1] if suggested_row and suggested_row <= len(file_lines) else "",
                    block=True,
                ),
            ],
            p="md",
            mt="md",
            withBorder=True,
            style={"backgroundColor": "var(--bg-surface)"}
        ),
    ])


def create_step3_skip_rows(
    file_lines: List[str],
    header_row: int,
    suggested_skips: Optional[List[int]] = None
) -> html.Div:
    """
    Create Step 3: Skip rows configuration.

    Args:
        file_lines: Lines from the raw file
        header_row: Selected header row number
        suggested_skips: Auto-detected rows to skip

    Returns:
        Div with skip row configuration
    """
    # Find rows that might need skipping (empty time values, etc.)
    potential_skips = []
    for i, line in enumerate(file_lines[header_row:], header_row + 1):
        if line.strip().startswith("0:00:00") or line.strip() == "":
            if len(potential_skips) < 10:  # Limit suggestions
                potential_skips.append((i, line[:80] if line else "(empty line)"))

    return html.Div([
        dmc.Text(
            "Optionally specify rows to skip during import (e.g., empty rows, "
            "placeholder rows with '0:00:00' timestamps).",
            size="sm",
            mb="md",
        ),

        # Skip options
        html.Div([
            dmc.Text("Rows that may need skipping:", fw=500, mb="xs"),
            html.Div([
                dmc.Checkbox(
                    id={"type": "skip-row-checkbox", "index": num},
                    label=dmc.Group([
                        dmc.Badge(f"Line {num}", size="sm"),
                        dmc.Text(
                            preview[:60] + "..." if len(preview) > 60 else preview,
                            size="xs",
                            style={"fontFamily": "monospace"}
                        ),
                    ]),
                    checked=num in (suggested_skips or []),
                    mb="xs",
                )
                for num, preview in potential_skips
            ]) if potential_skips else dmc.Text(
                "No problematic rows detected",
                c="dimmed",
                size="sm"
            ),
        ], style={"marginBottom": "20px"}),

        # Manual skip range input
        dmc.TextInput(
            id="repair-skip-rows-input",
            label="Additional rows to skip (optional)",
            description="Enter line numbers or ranges (e.g., '92-115, 200, 205-210')",
            placeholder="e.g., 92-115, 200",
        ),

        # Summary of skipped rows
        dmc.Paper(
            id="repair-skip-summary",
            children=[
                dmc.Text("Rows to be skipped:", size="sm", fw=500),
                dmc.Text("None selected", size="sm", c="dimmed"),
            ],
            p="md",
            mt="md",
            withBorder=True,
        ),
    ])


def create_step4_column_mapping(
    columns: List[str],
    suggested_mapping: Optional[Dict[str, str]] = None
) -> html.Div:
    """
    Create Step 4: Column mapping interface.

    Args:
        columns: List of column names from the header
        suggested_mapping: Auto-detected column mapping

    Returns:
        Div with column mapping interface
    """
    suggested = suggested_mapping or {}

    # Try to auto-detect columns
    time_col = suggested.get("time")
    temp_col = suggested.get("temperature")
    first_well = suggested.get("first_well")

    for col in columns:
        col_lower = col.lower().strip()
        if time_col is None and col_lower in ["time", "time [s]", "time (s)"]:
            time_col = col
        if temp_col is None and col_lower in ["t°", "t", "temperature", "temp"]:
            temp_col = col
        if first_well is None and col_lower in ["a1", "a01"]:
            first_well = col

    # Create select options
    column_options = [{"value": c, "label": c} for c in columns]

    return html.Div([
        dmc.Text(
            "Map the file columns to required data fields. This is typically "
            "auto-detected, but manual mapping may be needed for non-standard files.",
            size="sm",
            mb="md",
        ),

        dmc.Grid([
            dmc.GridCol([
                dmc.Select(
                    id="repair-time-column",
                    label="Time column",
                    description="Column containing timepoint values",
                    data=column_options,
                    value=time_col,
                    searchable=True,
                    required=True,
                )
            ], span=6),
            dmc.GridCol([
                dmc.Select(
                    id="repair-temp-column",
                    label="Temperature column (optional)",
                    description="Column containing temperature readings",
                    data=column_options,
                    value=temp_col,
                    searchable=True,
                    clearable=True,
                )
            ], span=6),
        ], mb="md"),

        dmc.Grid([
            dmc.GridCol([
                dmc.Select(
                    id="repair-first-well-column",
                    label="First well column",
                    description="First column containing well data (e.g., A1)",
                    data=column_options,
                    value=first_well,
                    searchable=True,
                    required=True,
                )
            ], span=6),
            dmc.GridCol([
                dmc.Checkbox(
                    id="repair-auto-detect-wells",
                    label="Auto-detect remaining well columns",
                    checked=True,
                    description="Automatically include columns after first well that match well patterns (A1-H12)",
                )
            ], span=6, style={"display": "flex", "alignItems": "center"}),
        ], mb="md"),

        # Preview of detected columns
        dmc.Paper(
            id="repair-column-preview",
            children=[
                dmc.Text("Detected columns:", size="sm", fw=500),
                dmc.Group([
                    dmc.Badge(col, color="blue", size="sm")
                    for col in columns[:20]
                ] + ([dmc.Badge(f"+{len(columns)-20} more", color="gray", size="sm")]
                     if len(columns) > 20 else []),
                gap="xs",
                ),
            ],
            p="md",
            mt="md",
            withBorder=True,
        ),
    ])


def create_step5_preview_data(
    preview_data: Dict[str, Any],
    num_wells: int,
    num_timepoints: int,
    sample_wells: List[str]
) -> html.Div:
    """
    Create Step 5: Data preview before import.

    Args:
        preview_data: Dict with preview information
        num_wells: Number of wells parsed
        num_timepoints: Number of timepoints
        sample_wells: List of sample well positions to show

    Returns:
        Div with data preview
    """
    return html.Div([
        # Success indicator
        dmc.Alert(
            title="File parsed successfully",
            children="Review the parsed data below before importing.",
            color="green",
            icon=DashIconify(icon="mdi:check-circle"),
            mb="md",
        ),

        # Summary stats
        dmc.Grid([
            dmc.GridCol([
                dmc.Paper(
                    children=[
                        dmc.Text(str(num_wells), size="xl", fw=700, ta="center"),
                        dmc.Text("Wells", size="sm", c="dimmed", ta="center"),
                    ],
                    p="md",
                    withBorder=True,
                )
            ], span=4),
            dmc.GridCol([
                dmc.Paper(
                    children=[
                        dmc.Text(str(num_timepoints), size="xl", fw=700, ta="center"),
                        dmc.Text("Timepoints", size="sm", c="dimmed", ta="center"),
                    ],
                    p="md",
                    withBorder=True,
                )
            ], span=4),
            dmc.GridCol([
                dmc.Paper(
                    children=[
                        dmc.Text(
                            f"{preview_data.get('temperature_setpoint', 'N/A')}",
                            size="xl",
                            fw=700,
                            ta="center"
                        ),
                        dmc.Text("Temperature", size="sm", c="dimmed", ta="center"),
                    ],
                    p="md",
                    withBorder=True,
                )
            ], span=4),
        ], mb="lg"),

        # Sample data preview
        dmc.Text("Sample data preview:", fw=500, mb="xs"),
        dmc.Paper(
            children=[
                dmc.ScrollArea(
                    children=html.Div(id="repair-data-preview-table"),
                    h=250,
                )
            ],
            p="md",
            withBorder=True,
            style={"backgroundColor": "var(--bg-surface)"}
        ),

        # Wells list
        dmc.Text("Wells detected:", fw=500, mt="md", mb="xs"),
        dmc.Group(
            [dmc.Badge(w, size="sm") for w in sample_wells[:24]] +
            ([dmc.Badge(f"+{len(sample_wells)-24} more", color="gray", size="sm")]
             if len(sample_wells) > 24 else []),
            gap="xs",
        ),
    ])


def create_repair_wizard_error(error_message: str) -> html.Div:
    """Create error display for repair wizard."""
    return html.Div([
        dmc.Alert(
            title="Repair Failed",
            children=error_message,
            color="red",
            icon=DashIconify(icon="mdi:alert-circle"),
        ),
        dmc.Text(
            "Please check your settings and try again. If the issue persists, "
            "the file format may not be supported.",
            size="sm",
            c="dimmed",
            mt="md",
        ),
    ])
