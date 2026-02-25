"""
Plate templates layout for creating and editing plate layouts.

Phase 2: Plate Layout Editor

Provides:
- Layout creation and editing interface
- Plate grid integration
- Assignment panel
- Validation and summary display
"""
from typing import Optional, List, Dict, Any

import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify

from app.components.plate_grid import (
    create_plate_grid,
    create_plate_grid_skeleton,
    create_selection_helpers,
    create_assignment_panel,
    create_zoom_control,
)


# Well type options for assignment panel
# Note: Analytical roles (Unregulated, Wild-type, Mutant) all use well_type="sample"
# The role is determined by the Construct's is_unregulated and is_wildtype flags
WELL_TYPE_OPTIONS = [
    # Sample wells - role derived from construct flags
    {"value": "sample", "label": "Sample", "description": "Sample well with construct (role determined by construct flags)"},
    # Control wells
    {"value": "blank", "label": "Blank", "description": "Buffer-only well for instrument baseline"},
    {"value": "negative_control_no_template", "label": "-Template", "description": "No DNA template, primary baseline"},
    {"value": "negative_control_no_dye", "label": "-DFHBI", "description": "No dye, autofluorescence check"},
]


def create_plate_templates_layout(
    project_id: int,
    layout_id: Optional[int] = None,
    plate_format: int = 384,
) -> dmc.Container:
    """
    Create the main plate templates layout.

    Args:
        project_id: Current project ID
        layout_id: Optional layout ID if editing existing
        plate_format: 96 or 384 (needed for initial control state)

    Returns:
        Container with the complete layout editor interface
    """
    # Create initial controls with checkerboard toggle - MUST exist before callbacks fire
    # Auto-enable checkerboard for 384-well plates
    initial_checkerboard = (plate_format == 384)
    initial_controls = create_layout_controls(
        plate_format=plate_format,
        enforce_checkerboard=initial_checkerboard,
        pattern='A',
        section_id="layout-editor",
    )

    return dmc.Container(
        children=[
            # Data stores
            dcc.Store(id="plate-templates-project-store", data={"project_id": project_id}),
            dcc.Store(id="plate-templates-layout-store", data={"layout_id": layout_id} if layout_id else None),
            dcc.Store(id="plate-templates-selection-store", data=[]),
            dcc.Store(id="plate-templates-last-clicked-store", data=None),
            dcc.Store(id="plate-templates-assignments-store", data={}),
            dcc.Store(id="plate-templates-constructs-store", data={}), # New store for construct metadata
            dcc.Store(id="plate-templates-well-click-store", data=None),  # Store for latest well click with modifiers
            dcc.Store(id="plate-templates-import-store", data=None),  # Store for imported calculator plan

            # Notification container for save/publish feedback
            html.Div(id="plate-templates-notification-container"),

            # Header
            html.Div(id="plate-templates-header-container"),

            # Main content grid
            dmc.Grid(
                children=[
                    # Left column: Plate grid and selection helpers
                    dmc.GridCol(
                        children=[
                            dmc.Stack([
                                # Controls (Checkerboard toggle, etc) - rendered directly to avoid callback timing issues
                                html.Div(
                                    id="plate-templates-controls-container",
                                    children=initial_controls,
                                    style={"marginBottom": "1rem"}
                                ),

                                # Zoom control (outside grid container so it persists across re-renders)
                                html.Div(
                                    id="plate-templates-zoom-container",
                                    children=create_zoom_control(grid_id="layout-editor-grid") if plate_format == 384 else None,
                                ),

                                # Grid editor
                                html.Div(id="plate-templates-grid-container"),
                                html.Div(id="plate-templates-helpers-container"),
                            ], gap="md"),
                        ],
                        span={"base": 12, "lg": 8},
                    ),

                    # Right column: Assignment panel and summary
                    dmc.GridCol(
                        children=[
                            dmc.Stack([
                                html.Div(id="plate-templates-assignment-container"),
                                html.Div(id="plate-templates-summary-container"),
                            ], gap="md"),
                        ],
                        span={"base": 12, "lg": 4},
                    ),
                ],
                gutter="lg",
            ),
        ],
        fluid=True,
        py="md",
    )


def create_plate_templates_header(
    project_id: int,
    project_name: str = "Project",
    layout_name: Optional[str] = None,
    is_draft: bool = True,
    plate_format: int = 384,
    existing_layouts: Optional[List[Dict]] = None,
    current_layout_id: Optional[int] = None,
) -> dmc.Paper:
    """
    Create the header section for plate templates page.

    Args:
        project_id: Project ID
        project_name: Project name for display
        layout_name: Layout name if editing existing
        is_draft: Whether layout is in draft state
        plate_format: 96 or 384
        existing_layouts: List of existing layouts for dropdown
        current_layout_id: Currently selected layout ID

    Returns:
        Paper component with header content
    """
    existing_layouts = existing_layouts or []

    # Title based on new/edit mode
    if layout_name:
        title = f"Edit Layout: {layout_name}"
    else:
        title = "Create New Plate Layout"

    # Status badge
    status_badge = dmc.Badge(
        "Draft" if is_draft else "Published",
        color="yellow" if is_draft else "green",
        variant="light",
    )

    # Format badge
    format_badge = dmc.Badge(
        f"{plate_format}-well",
        color="blue",
        variant="outline",
    )

    # Layout selector dropdown
    layout_options = [{"value": "", "label": "+ New Layout"}]
    for layout in existing_layouts:
        status = " (Draft)" if layout.get("is_draft") else ""
        layout_options.append({
            "value": str(layout.get("id")),
            "label": f"{layout.get('name')}{status}",
        })

    layout_selector = dmc.Select(
        id="plate-templates-layout-selector",
        label="Load Layout",
        placeholder="Select a layout...",
        data=layout_options,
        value=str(current_layout_id) if current_layout_id else "",
        w=200,
        size="sm",
    )

    return dmc.Paper(
        children=[
            dmc.Group([
                dmc.Stack([
                    dmc.Title(title, order=3),
                    dmc.Text(
                        f"Project: {project_name}",
                        size="sm",
                        c="dimmed",
                    ),
                ], gap=0),

                dmc.Group([
                    layout_selector,
                    dcc.Upload(
                        id="plate-templates-import-upload",
                        children=dmc.Button(
                            "Import from Calculator",
                            id="plate-templates-import-btn",
                            variant="outline",
                            color="violet",
                            leftSection=DashIconify(icon="mdi:file-import", width=20),
                        ),
                        accept=".json",
                        style={"display": "inline-block"},
                    ),
                    status_badge,
                    format_badge,
                    dmc.Button(
                        "Save Draft",
                        id="plate-templates-save-btn",
                        variant="light",
                        leftSection=DashIconify(icon="mdi:content-save", width=20),
                    ),
                    dmc.Button(
                        "Publish",
                        id="plate-templates-publish-btn",
                        color="green",
                        leftSection=DashIconify(icon="mdi:check-circle", width=20),
                    ),
                ], gap="sm"),
            ], justify="space-between"),
        ],
        p="md",
        withBorder=True,
        radius="md",
        mb="md",
    )


def create_layout_info_panel(
    project_id: int,
    plate_format: int = 384,
    layout_name: Optional[str] = None,
    assigned_wells: int = 0,
    total_wells: Optional[int] = None,
) -> dmc.Paper:
    """
    Create the layout info panel.

    Args:
        project_id: Project ID
        plate_format: 96 or 384
        layout_name: Current layout name
        assigned_wells: Number of assigned wells
        total_wells: Total wells (computed from format if not provided)

    Returns:
        Paper component with layout info
    """
    if total_wells is None:
        total_wells = 384 if plate_format == 384 else 96

    completion_pct = (assigned_wells / total_wells * 100) if total_wells > 0 else 0

    return dmc.Paper(
        children=[
            dmc.Stack([
                dmc.TextInput(
                    label="Layout Name",
                    placeholder="Enter layout name...",
                    value=layout_name or "",
                    id="plate-templates-name-input",
                    required=True,
                ),

                dmc.Group([
                    dmc.Stack([
                        dmc.Text("Format", size="xs", c="dimmed"),
                        dmc.Text(f"{plate_format}-well", fw=500),
                    ], gap=0),
                    dmc.Stack([
                        dmc.Text("Assigned", size="xs", c="dimmed"),
                        dmc.Text(f"{assigned_wells} / {total_wells}", fw=500),
                    ], gap=0),
                ], grow=True),

                dmc.Progress(
                    value=completion_pct,
                    color="blue",
                    size="sm",
                ),
            ], gap="sm"),
        ],
        p="md",
        withBorder=True,
        radius="md",
    )


def create_layout_controls(
    plate_format: int = 384,
    enforce_checkerboard: bool = None,  # None means auto-detect
    pattern: str = 'A',
    skip_edges: bool = False,
    section_id: str = "layout-editor",
) -> dmc.Paper:
    """Create the layout controls section (toggle and pattern selector)."""

    # Auto-enable checkerboard for 384-well plates
    if enforce_checkerboard is None:
        enforce_checkerboard = (plate_format == 384)

    # Checkerboard toggle (always create for callback stability, hide if not 384)
    toggle_style = {}
    if plate_format != 384:
        toggle_style = {"display": "none"}

    checkerboard_control = dmc.Switch(
        label="Enforce Checkerboard Pattern",
        description="Only allow assignments to alternating wells",
        id=f"{section_id}-checkerboard-toggle",
        checked=enforce_checkerboard,
        style=toggle_style,
    )

    # Skip edges toggle
    skip_edges_control = dmc.Switch(
        label="Skip Edge Wells",
        description="Exclude wells on plate perimeter",
        id=f"{section_id}-skip-edges-toggle",
        checked=skip_edges,
    )

    # Pattern selector (only visible when checkerboard enabled on 384)
    pattern_selector = dmc.SegmentedControl(
        id=f"{section_id}-pattern-selector",
        data=[
            {"value": "A", "label": "Pattern A (A1)"},
            {"value": "B", "label": "Pattern B (B1)"},
        ],
        value=pattern,
        size="xs",
    )

    # Wrap pattern selector to control visibility
    pattern_wrapper = html.Div(
        id=f"{section_id}-pattern-wrapper",
        children=[pattern_selector],
        style={"display": "block" if enforce_checkerboard and plate_format == 384 else "none"},
    )

    return dmc.Paper(
        children=[
            dmc.Stack([
                dmc.Group([
                    dmc.Title("Plate Grid", order=5),
                    dmc.Group([
                        pattern_wrapper,
                        checkerboard_control,
                        skip_edges_control,
                    ], gap="md"),
                ], justify="space-between"),
                dmc.Text(
                    "Click to select wells. Shift-click to select a range.",
                    size="xs",
                    c="dimmed",
                ),
            ], gap="xs"),
        ],
        p="sm",
        withBorder=True,
        radius="md",
    )



def create_layout_editor_section(
    plate_format: int = 384,
    section_id: str = "layout-editor",
    assignments: Optional[Dict] = None,
    selected_wells: Optional[List[str]] = None,
    # enforce_checkerboard arg deprecated/unused for grid generation here, handled in controls
    enforce_checkerboard: bool = False, 
) -> dmc.Stack:
    """
    Create the main layout editor section (Grid + Helpers).
    Controls are now separate.
    """
    grid = create_plate_grid(
        plate_format=plate_format,
        grid_id=f"{section_id}-grid",
        assignments=assignments,
        selected_wells=selected_wells,
        enforce_checkerboard=enforce_checkerboard,
    )

    helpers = create_selection_helpers(
        plate_format=plate_format,
        helpers_id=f"{section_id}-helpers",
    )

    return dmc.Stack([
        grid,
        helpers,
    ], gap="md")


def create_layout_summary_panel(
    summary_id: str = "layout-summary",
    summary_data: Optional[Dict] = None,
    validation_passed: Optional[bool] = None,
    validation_issues: Optional[List[str]] = None,
    checkerboard_warning: Optional[str] = None,
) -> dmc.Paper:
    """
    Create the layout summary panel.

    Args:
        summary_id: Base ID for summary components
        summary_data: Layout summary data
        validation_passed: Whether validation passed
        validation_issues: List of validation issues
        checkerboard_warning: Warning message for checkerboard violations

    Returns:
        Paper component with summary display
    """
    summary_data = summary_data or {}
    validation_issues = validation_issues or []

    # Build summary content
    content = [
        dmc.Title("Layout Summary", order=5),
        dmc.Divider(),
    ]

    # Well counts by type
    by_type = summary_data.get("by_type", {})
    if by_type:
        type_items = []
        for well_type, count in by_type.items():
            type_label = well_type.replace("_", " ").title()
            type_items.append(
                dmc.Group([
                    dmc.Text(type_label, size="sm"),
                    dmc.Badge(str(count), color="blue", variant="light"),
                ], justify="space-between")
            )
        content.append(dmc.Stack(type_items, gap="xs"))
    else:
        content.append(
            dmc.Text("No wells assigned yet", c="dimmed", size="sm")
        )

    # Construct breakdown
    constructs = summary_data.get("constructs", [])
    if constructs:
        content.append(dmc.Divider())
        content.append(dmc.Text("Constructs", size="sm", fw=500))
        construct_items = []
        for c in constructs:
            construct_items.append(
                dmc.Group([
                    dmc.Text(c.get("identifier", "Unknown"), size="sm"),
                    dmc.Badge(str(c.get("count", 0)), color="gray", variant="light"),
                ], justify="space-between")
            )
        content.append(dmc.Stack(construct_items, gap="xs"))

    # Validation status
    if validation_passed is not None:
        content.append(dmc.Divider())
        if validation_passed:
            content.append(
                dmc.Alert(
                    "Layout is valid and ready to publish",
                    color="green",
                    icon=DashIconify(icon="mdi:check-circle", width=20),
                )
            )
        else:
            issues_list = dmc.List([
                dmc.ListItem(issue) for issue in validation_issues
            ], size="sm")
            content.append(
                dmc.Alert(
                    title="Validation Issues",
                    children=issues_list,
                    color="red",
                    icon=DashIconify(icon="mdi:alert-circle", width=20),
                )
            )

    # Checkerboard warning with redistribute button
    if checkerboard_warning:
        content.append(dmc.Divider())
        content.append(
            dmc.Alert(
                title="Plate Reader Constraint",
                children=dmc.Stack([
                    dmc.Text(checkerboard_warning, size="sm"),
                    dmc.Text(
                        "384-well plates require checkerboard pattern for accurate reading. "
                        "Click below to move wells to nearest valid positions.",
                        size="xs",
                        c="dimmed",
                    ),
                    dmc.Button(
                        "Redistribute to Checkerboard",
                        id="layout-redistribute-checkerboard-btn",
                        size="xs",
                        color="orange",
                        leftSection=DashIconify(icon="mdi:shuffle-variant", width=16),
                    ),
                ], gap="xs"),
                color="orange",
                icon=DashIconify(icon="mdi:alert", width=20),
            )
        )

    return dmc.Paper(
        children=dmc.Stack(content, gap="sm"),
        p="md",
        withBorder=True,
        radius="md",
        id=summary_id,
    )


def create_plate_templates_loading_state(
    plate_format: int = 384,
) -> dmc.Container:
    """
    Create loading state for plate templates page.

    Args:
        plate_format: 96 or 384

    Returns:
        Container with skeleton loading state
    """
    return dmc.Container(
        children=[
            # Header skeleton
            dmc.Paper(
                children=[
                    dmc.Group([
                        dmc.Group([
                            dmc.Skeleton(height=40, width=40, radius="md"),
                            dmc.Stack([
                                dmc.Skeleton(height=24, width=200),
                                dmc.Skeleton(height=16, width=120),
                            ], gap="xs"),
                        ], gap="md"),
                        dmc.Group([
                            dmc.Skeleton(height=24, width=60),
                            dmc.Skeleton(height=24, width=80),
                            dmc.Skeleton(height=36, width=100),
                            dmc.Skeleton(height=36, width=80),
                        ], gap="sm"),
                    ], justify="space-between"),
                ],
                p="md",
                withBorder=True,
                radius="md",
                mb="md",
            ),

            # Content skeleton
            dmc.Grid(
                children=[
                    dmc.GridCol(
                        children=[
                            create_plate_grid_skeleton(plate_format),
                            dmc.Paper(
                                children=[
                                    dmc.Skeleton(height=100, width="100%"),
                                ],
                                p="md",
                                withBorder=True,
                                radius="md",
                                mt="md",
                            ),
                        ],
                        span={"base": 12, "lg": 8},
                    ),
                    dmc.GridCol(
                        children=[
                            dmc.Paper(
                                children=[
                                    dmc.Stack([
                                        dmc.Skeleton(height=24, width="60%"),
                                        dmc.Skeleton(height=40, width="100%"),
                                        dmc.Skeleton(height=40, width="100%"),
                                        dmc.Skeleton(height=40, width="100%"),
                                        dmc.Skeleton(height=36, width="100%"),
                                    ], gap="sm"),
                                ],
                                p="md",
                                withBorder=True,
                                radius="md",
                            ),
                            dmc.Paper(
                                children=[
                                    dmc.Stack([
                                        dmc.Skeleton(height=24, width="50%"),
                                        dmc.Skeleton(height=60, width="100%"),
                                        dmc.Skeleton(height=60, width="100%"),
                                    ], gap="sm"),
                                ],
                                p="md",
                                withBorder=True,
                                radius="md",
                                mt="md",
                            ),
                        ],
                        span={"base": 12, "lg": 4},
                    ),
                ],
                gutter="lg",
            ),
        ],
        fluid=True,
        py="md",
    )
