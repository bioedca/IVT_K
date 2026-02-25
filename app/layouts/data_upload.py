"""
Data upload layout - file upload and validation interface.

Phase 3: Data Upload Flow

Provides:
- File upload interface with drag-and-drop
- Layout selection and matching
- Validation results display
- Temperature QC warnings
- Session association
"""
from typing import Optional, Dict, List, Any

import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify


# Temperature QC threshold per PRD Section 3.6
TEMPERATURE_QC_THRESHOLD = 1.0  # ±1°C


def create_upload_layout(project_id: Optional[int] = None) -> dmc.Container:
    """
    Create the data upload layout.

    This layout provides the interface for uploading experimental
    data files and associating them with plate layouts and sessions.

    Args:
        project_id: Project ID for the upload

    Returns:
        Mantine Container with upload layout
    """
    return dmc.Container(
        children=[
            # Data stores
            dcc.Store(id="upload-project-store", data={"project_id": project_id}),
            dcc.Store(id="upload-file-store", data=None),  # Single file (legacy) or first file
            dcc.Store(id="upload-files-store", data=[]),   # Multiple files list
            dcc.Store(id="upload-validation-store", data=None),
            dcc.Store(id="upload-layout-store", data=None),
            dcc.Store(id="upload-session-store", data=None),
            dcc.Store(id="upload-suppressed-warnings-store", data=[]),
            dcc.Store(id="upload-success-store", data=None),  # Track successful uploads
            dcc.Store(id="upload-preview-file-index", data=0),  # Index of file to preview
            dcc.Store(id="upload-toast-countdown", data=None),  # Countdown seconds remaining
            dcc.Interval(
                id="upload-toast-interval",
                interval=1000,  # 1 second
                n_intervals=0,
                disabled=True,  # Disabled until toast is shown
            ),

            # Error notification container
            html.Div(id="upload-error-notification"),

            # Success toast notification (centered)
            dmc.Affix(
                children=html.Div(id="upload-success-toast"),
                position={"top": 80, "left": "50%"},
                style={"transform": "translateX(-50%)", "zIndex": 1000},
            ),

            # Header
            create_upload_header(project_id),

            # Main content
            dmc.Grid(
                children=[
                    # Left column - File upload and layout selection
                    dmc.GridCol(
                        children=[
                            create_file_upload_panel(),
                            html.Div(style={"height": "1rem"}),
                            create_layout_selection_panel(project_id),
                            html.Div(style={"height": "1rem"}),
                            create_session_panel(project_id),
                        ],
                        span=6,
                    ),

                    # Right column - Validation and preview (tabbed)
                    dmc.GridCol(
                        children=[
                            dmc.Tabs(
                                children=[
                                    dmc.TabsList([
                                        dmc.TabsTab("Preview", value="preview"),
                                        dmc.TabsTab("Validation", value="validation"),
                                    ], mb="sm"),
                                    dmc.TabsPanel(
                                        html.Div(
                                            id="upload-preview-container",
                                            children=[_create_preview_placeholder()],
                                        ),
                                        value="preview",
                                    ),
                                    dmc.TabsPanel(
                                        html.Div(
                                            id="upload-validation-container",
                                            children=[create_validation_panel()],
                                        ),
                                        value="validation",
                                    ),
                                ],
                                value="preview",
                            ),
                        ],
                        span=6,
                    ),
                ],
                gutter="lg",
            ),

            # Submit section
            html.Div(
                id="upload-submit-section",
                children=[_create_submit_section()],
                style={"marginTop": "1.5rem"},
            ),
        ],
        size="lg",
        style={"paddingTop": "1rem"},
    )


def create_upload_header(project_id: Optional[int] = None) -> html.Div:
    """
    Create the upload page header.

    Args:
        project_id: Project ID

    Returns:
        Div containing header elements
    """
    return html.Div(
        children=[
            dmc.Group(
                children=[
                    html.Div(
                        children=[
                            dmc.Title("Upload Data", order=3),
                            dmc.Text(
                                "Upload experimental data files from BioTek reader",
                                size="sm",
                                c="dimmed",
                            ),
                        ],
                    ),
                ],
                gap="md",
            ),
            dmc.Group(
                children=[
                    dmc.Button(
                        "Help",
                        id="upload-help-btn",
                        variant="subtle",
                        leftSection=DashIconify(icon="mdi:help-circle", width=18),
                    ),
                ],
                gap="sm",
            ),
        ],
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "marginBottom": "1.5rem",
        },
    )


def create_file_upload_panel() -> dmc.Paper:
    """
    Create the file upload panel with drag-and-drop.

    Returns:
        Paper component with file upload interface
    """
    return dmc.Paper(
        children=[
            dmc.Title("Select Files", order=5, mb="md"),
            dcc.Upload(
                id="upload-dropzone",
                children=html.Div(
                    children=[
                        DashIconify(
                            icon="mdi:cloud-upload",
                            width=48,
                            color="#228be6",
                        ),
                        dmc.Text(
                            "Drag and drop or click to select",
                            size="lg",
                            fw=500,
                            mt="md",
                        ),
                        dmc.Text(
                            "Supports multiple .txt, .csv, .xlsx files from BioTek reader",
                            size="sm",
                            c="dimmed",
                            mt="xs",
                        ),
                    ],
                    style={
                        "textAlign": "center",
                        "padding": "2rem",
                    },
                ),
                style={
                    "border": "2px dashed var(--border-medium)",
                    "borderRadius": "8px",
                    "cursor": "pointer",
                    "backgroundColor": "var(--bg-surface)",
                },
                style_active={
                    "borderColor": "#0C7C6F",
                    "backgroundColor": "rgba(12,124,111,0.05)",
                },
                multiple=True,  # Allow multiple file uploads
                accept=".txt,.csv,.xlsx,.xls,.tsv",
            ),
            html.Div(
                id="upload-file-info",
                style={"marginTop": "1rem"},
            ),
            # Session mode toggle for multiple files
            html.Div(
                id="upload-session-mode-container",
                children=[
                    dmc.Divider(my="md"),
                    dmc.Switch(
                        id="upload-session-mode-switch",
                        label="One session per file",
                        description="Each file creates its own session (recommended for different experiment days)",
                        checked=True,
                        mt="sm",
                    ),
                    dmc.Text(
                        id="upload-session-mode-hint",
                        children="Each plate file will be uploaded as a separate session with its own date.",
                        size="xs",
                        c="dimmed",
                        mt="xs",
                    ),
                ],
                style={"display": "none"},  # Hidden until multiple files uploaded
            ),
        ],
        p="md",
        withBorder=True,
        radius="md",
    )


def create_layout_selection_panel(
    project_id: Optional[int] = None,
    layouts: Optional[List[Dict]] = None,
) -> dmc.Paper:
    """
    Create the layout selection panel.

    Args:
        project_id: Project ID
        layouts: List of available layouts

    Returns:
        Paper component with layout selection
    """
    layout_options = []
    if layouts:
        layout_options = [
            {"value": str(l["id"]), "label": l["name"]}
            for l in layouts
        ]

    return dmc.Paper(
        children=[
            dmc.Title("Select Layout", order=5, mb="md"),
            dmc.Text(
                "Choose the plate layout that matches your experiment",
                size="sm",
                c="dimmed",
                mb="md",
            ),
            dmc.Select(
                id="upload-layout-select",
                label="Plate Layout",
                placeholder="Select a layout...",
                data=layout_options,
                searchable=True,
                clearable=True,
                leftSection=DashIconify(icon="mdi:grid", width=18),
            ),
        ],
        p="md",
        withBorder=True,
        radius="md",
    )


def create_session_panel(
    project_id: Optional[int] = None,
    sessions: Optional[List[Dict]] = None,
) -> dmc.Paper:
    """
    Create the session association panel.

    Args:
        project_id: Project ID
        sessions: List of existing sessions

    Returns:
        Paper component with session selection
    """
    session_options = [
        {"value": "new", "label": "Create new session"},
    ]
    if sessions:
        for s in sessions:
            label = f"{s.get('date', 'Unknown')} - {s.get('batch_id', s.get('id'))}"
            session_options.append({"value": str(s["id"]), "label": label})

    return dmc.Paper(
        children=[
            dmc.Title("Session", order=5, mb="md"),
            dmc.Text(
                "Associate this upload with an experimental session",
                size="sm",
                c="dimmed",
                mb="md",
            ),
            dmc.Select(
                id="upload-session-select",
                label="Experimental Session",
                placeholder="Select or create session...",
                data=session_options,
                value="new",
                leftSection=DashIconify(icon="mdi:calendar", width=18),
            ),
            html.Div(
                id="upload-new-session-fields",
                children=[
                    # Date parsing toggle
                    dmc.Switch(
                        id="upload-parse-date-switch",
                        label="Parse date from file",
                        description="Extract session date from uploaded file metadata",
                        checked=True,
                        mt="md",
                    ),
                    # Manual date selection (hidden when parse-date is on)
                    html.Div(
                        id="upload-manual-date-fields",
                        children=[
                            dmc.DateInput(
                                id="upload-session-date",
                                label="Session Date",
                                placeholder="Select date...",
                                mt="md",
                                leftSection=DashIconify(icon="mdi:calendar", width=18),
                            ),
                        ],
                        style={"display": "none"},
                    ),
                    # Parsed date display (shown when parse-date is on)
                    html.Div(
                        id="upload-parsed-date-display",
                        children=[
                            dmc.Alert(
                                id="upload-parsed-date-alert",
                                title="Date will be parsed from file",
                                children="Upload a file to extract the session date",
                                color="blue",
                                icon=DashIconify(icon="mdi:calendar-clock", width=20),
                                mt="md",
                            ),
                        ],
                    ),
                    dmc.Divider(my="sm"),
                    # Identifier parsing switch
                    dmc.Switch(
                        id="upload-parse-identifier-switch",
                        label="Parse identifier from filename",
                        description="Extract batch identifier from the uploaded filename",
                        checked=True,
                        mt="sm",
                    ),
                    # Parsed identifier display (shown when parse-identifier is on)
                    html.Div(
                        id="upload-parsed-identifier-display",
                        children=[
                            dmc.Alert(
                                id="upload-parsed-identifier-alert",
                                title="Identifier will be parsed from filename",
                                children="Upload a file to extract the identifier",
                                color="blue",
                                icon=DashIconify(icon="mdi:tag-text", width=20),
                                mt="xs",
                            ),
                        ],
                    ),
                    dmc.TextInput(
                        id="upload-session-batch",
                        label="Batch Identifier",
                        placeholder="Will use your username if empty",
                        description="Override the parsed identifier or enter your own",
                        mt="sm",
                    ),
                    dmc.NumberInput(
                        id="upload-plate-number",
                        label="Plate Number",
                        value=1,
                        min=1,
                        mt="sm",
                    ),
                ],
            ),
        ],
        p="md",
        withBorder=True,
        radius="md",
    )


def create_validation_panel(
    validation_result: Optional[Dict] = None,
) -> dmc.Paper:
    """
    Create the validation results display panel.

    Args:
        validation_result: Validation result dict

    Returns:
        Paper component with validation results
    """
    if validation_result is None:
        return dmc.Paper(
            children=[
                dmc.Title("Validation", order=5, mb="md"),
                dmc.Alert(
                    title="Waiting for file",
                    children="Upload a file to see validation results",
                    color="gray",
                    icon=DashIconify(icon="mdi:information", width=20),
                ),
            ],
            p="md",
            withBorder=True,
            radius="md",
        )

    # Build validation display
    children = [
        dmc.Title("Validation", order=5, mb="md"),
    ]

    # Status badge
    if validation_result.get("is_valid"):
        children.append(
            dmc.Alert(
                title="Validation Passed",
                children="File is ready to upload",
                color="green",
                icon=DashIconify(icon="mdi:check-circle", width=20),
                mb="md",
            )
        )
    else:
        children.append(
            dmc.Alert(
                title="Validation Failed",
                children="Please fix the errors below",
                color="red",
                icon=DashIconify(icon="mdi:alert-circle", width=20),
                mb="md",
            )
        )

    # Errors
    errors = validation_result.get("errors", [])
    if errors:
        error_items = [dmc.ListItem(str(e)) for e in errors]
        children.append(
            dmc.Paper(
                children=[
                    dmc.Group(
                        children=[
                            DashIconify(icon="mdi:close-circle", width=20, color="red"),
                            dmc.Text("Errors", fw=600, c="red"),
                        ],
                        gap="xs",
                        mb="sm",
                    ),
                    dmc.List(children=error_items, size="sm"),
                ],
                p="sm",
                withBorder=True,
                radius="sm",
                style={"backgroundColor": "var(--bg-surface)"},
                mb="md",
            )
        )

    # Warnings
    warnings = validation_result.get("warnings", [])
    if warnings:
        warning_items = []
        for w in warnings:
            msg = w.get("message", str(w)) if isinstance(w, dict) else str(w)
            suppressible = w.get("suppressible", False) if isinstance(w, dict) else False
            item = dmc.ListItem(
                children=[
                    msg,
                    dmc.Badge("Suppressible", size="xs", ml="xs") if suppressible else None,
                ],
            )
            warning_items.append(item)

        children.append(
            dmc.Paper(
                children=[
                    dmc.Group(
                        children=[
                            DashIconify(icon="mdi:alert", width=20, color="orange"),
                            dmc.Text("Warnings", fw=600, c="orange"),
                        ],
                        gap="xs",
                        mb="sm",
                    ),
                    dmc.List(children=warning_items, size="sm"),
                ],
                p="sm",
                withBorder=True,
                radius="sm",
                style={"backgroundColor": "var(--bg-surface)"},
                mb="md",
            )
        )

    # Metadata
    metadata = validation_result.get("metadata", {})
    if metadata:
        children.append(
            dmc.Paper(
                children=[
                    dmc.Group(
                        children=[
                            DashIconify(icon="mdi:information", width=20, color="blue"),
                            dmc.Text("File Information", fw=600),
                        ],
                        gap="xs",
                        mb="sm",
                    ),
                    dmc.SimpleGrid(
                        children=[
                            _create_info_item("Plate Format", f"{metadata.get('plate_format', 'N/A')}-well"),
                            _create_info_item("Temperature", f"{metadata.get('temperature_setpoint', 'N/A')}°C"),
                            _create_info_item("Timepoints", str(metadata.get('num_timepoints', 'N/A'))),
                            _create_info_item("Wells", str(metadata.get('num_wells_with_data', 'N/A'))),
                        ],
                        cols=2,
                    ),
                ],
                p="sm",
                withBorder=True,
                radius="sm",
            )
        )

    return dmc.Paper(
        children=children,
        p="md",
        withBorder=True,
        radius="md",
    )


def _create_info_item(label: str, value: str) -> html.Div:
    """Create a labeled info item."""
    return html.Div(
        children=[
            dmc.Text(label, size="xs", c="dimmed"),
            dmc.Text(value, size="sm", fw=500),
        ],
    )


def create_temperature_warning(
    setpoint: Optional[float] = None,
    actual_temps: Optional[List[float]] = None,
    threshold: float = TEMPERATURE_QC_THRESHOLD,
) -> Optional[dmc.Alert]:
    """
    Create temperature warning alert if deviation exceeds threshold.

    Args:
        setpoint: Target temperature
        actual_temps: List of actual temperature readings
        threshold: Maximum allowed deviation (default: 1.0°C)

    Returns:
        Alert component if warning needed, None otherwise
    """
    if setpoint is None or not actual_temps:
        return None

    # Filter None values
    valid_temps = [t for t in actual_temps if t is not None]
    if not valid_temps:
        return None

    min_temp = min(valid_temps)
    max_temp = max(valid_temps)

    max_deviation = max(abs(max_temp - setpoint), abs(min_temp - setpoint))

    if max_deviation <= threshold:
        return None

    # Create warning alert
    deviation_direction = "above" if max_temp - setpoint > threshold else "below"
    extreme_temp = max_temp if deviation_direction == "above" else min_temp

    return dmc.Alert(
        title="Temperature Deviation Detected",
        children=[
            dmc.Text(
                f"Temperature readings deviate from setpoint by more than ±{threshold}°C",
                size="sm",
            ),
            dmc.Group(
                children=[
                    dmc.Badge(f"Setpoint: {setpoint}°C", color="blue"),
                    dmc.Badge(f"Actual: {extreme_temp}°C", color="red"),
                    dmc.Badge(f"Deviation: {max_deviation:.1f}°C", color="orange"),
                ],
                gap="xs",
                mt="sm",
            ),
        ],
        color="yellow",
        icon=DashIconify(icon="mdi:thermometer-alert", width=20),
    )


def _create_preview_placeholder() -> dmc.Paper:
    """Create placeholder for data preview."""
    return dmc.Paper(
        children=[
            dmc.Group([
                dmc.Title("Preview", order=5),
                dmc.Group([
                    # File selector (hidden until multiple files)
                    html.Div(
                        id="upload-preview-file-selector-container",
                        children=[
                            dmc.Select(
                                id="upload-preview-file-select",
                                placeholder="Select file...",
                                data=[],
                                size="xs",
                                style={"width": "200px"},
                            ),
                        ],
                        style={"display": "none"},
                    ),
                    # Max wells selector
                    dmc.NumberInput(
                        id="upload-preview-max-wells",
                        label="Max wells",
                        value=21,
                        min=6,
                        max=96,
                        step=3,
                        size="xs",
                        style={"width": "100px"},
                    ),
                ], gap="sm"),
            ], justify="space-between", mb="md"),
            html.Div(
                id="upload-preview-plot-container",
                children=[
                    html.Div(
                        children=[
                            DashIconify(
                                icon="mdi:chart-scatter-plot",
                                width=48,
                                color="var(--text-tertiary)",
                            ),
                            dmc.Text(
                                "Data preview will appear here",
                                size="sm",
                                c="dimmed",
                                mt="md",
                            ),
                        ],
                        style={"textAlign": "center", "padding": "2rem"},
                    ),
                ],
            ),
        ],
        p="md",
        withBorder=True,
        radius="md",
    )


def _create_submit_section() -> dmc.Paper:
    """Create the submit section."""
    return dmc.Paper(
        children=[
            dmc.Group(
                children=[
                    html.Div(
                        children=[
                            dmc.Text("Ready to upload?", fw=600),
                            dmc.Text(
                                "Review validation results before proceeding",
                                size="sm",
                                c="dimmed",
                            ),
                        ],
                    ),
                    dmc.Group(
                        children=[
                            dmc.Button(
                                "Go to QC Review",
                                id="upload-goto-qc-btn",
                                variant="light",
                                color="green",
                                leftSection=DashIconify(icon="mdi:check-decagram", width=18),
                            ),
                            dmc.Button(
                                "Cancel",
                                id="upload-cancel-btn",
                                variant="subtle",
                                color="gray",
                            ),
                            dmc.Button(
                                "Upload Data",
                                id="upload-submit-btn",
                                variant="filled",
                                color="blue",
                                leftSection=DashIconify(icon="mdi:upload", width=18),
                                disabled=True,  # Disabled until validation passes
                            ),
                        ],
                        gap="sm",
                    ),
                ],
                justify="space-between",
                align="center",
            ),
        ],
        p="md",
        withBorder=True,
        radius="md",
    )


def create_upload_loading_state() -> dmc.Container:
    """
    Create loading state for upload layout.

    Returns:
        Container with skeleton placeholders
    """
    return dmc.Container(
        children=[
            # Header skeleton
            dmc.Group(
                children=[
                    dmc.Skeleton(height=40, width=40, radius="md"),
                    dmc.Stack(
                        children=[
                            dmc.Skeleton(height=28, width=200),
                            dmc.Skeleton(height=16, width=300),
                        ],
                        gap="xs",
                    ),
                ],
                gap="md",
                mb="xl",
            ),

            # Main content skeleton
            dmc.Grid(
                children=[
                    dmc.GridCol(
                        children=[
                            dmc.Skeleton(height=200, radius="md", mb="md"),
                            dmc.Skeleton(height=150, radius="md", mb="md"),
                            dmc.Skeleton(height=200, radius="md"),
                        ],
                        span=6,
                    ),
                    dmc.GridCol(
                        children=[
                            dmc.Skeleton(height=300, radius="md", mb="md"),
                            dmc.Skeleton(height=200, radius="md"),
                        ],
                        span=6,
                    ),
                ],
                gutter="lg",
            ),
        ],
        size="lg",
        style={"paddingTop": "1rem"},
    )
