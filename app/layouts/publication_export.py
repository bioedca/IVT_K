"""
Publication Export layout with package preview and daily report.

Phase 9.4-9.5: Publication package preview and export (F15.8-F15.10)
Phase 9.6: Daily report generation

Provides:
- Package preview with directory tree
- File list with sizes and types
- Exclude/include options
- Export configuration
- Daily report generation with section selection
"""
from typing import Optional, List, Dict, Any
import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify


def create_publication_export_layout(
    project_id: Optional[int] = None,
) -> html.Div:
    """
    Create the publication export layout with tabs for Publication Package
    and Daily Report.

    Args:
        project_id: Optional project ID

    Returns:
        Publication export layout
    """
    return html.Div([
        # Shared stores
        dcc.Store(id="export-project-store", data=project_id),
        dcc.Store(id="export-preview-store", data=None),
        dcc.Store(id="export-excluded-files", data=[]),
        dcc.Store(id="export-config-store", data=None),
        dcc.Store(id="report-html-store", data=None),

        # Header
        dmc.Group([
            dmc.Title("Export", order=2),
            dmc.Badge(
                id="export-status-badge",
                children="Ready",
                color="blue",
                size="lg",
            ),
        ], justify="space-between", mb="md"),

        # Tabbed interface
        dmc.Tabs([
            dmc.TabsList([
                dmc.TabsTab(
                    "Publication Package",
                    value="pub-package",
                    leftSection=DashIconify(icon="mdi:package-variant"),
                ),
                dmc.TabsTab(
                    "Daily Report",
                    value="daily-report",
                    leftSection=DashIconify(icon="mdi:file-document-outline"),
                ),
            ], mb="md"),

            # Tab 1: Publication Package (existing content)
            dmc.TabsPanel(
                _create_publication_package_panel(),
                value="pub-package",
            ),

            # Tab 2: Daily Report
            dmc.TabsPanel(
                _create_daily_report_panel(),
                value="daily-report",
            ),
        ], value="pub-package", id="export-tabs"),

        # Download components
        dcc.Download(id="export-download"),
        dcc.Download(id="report-download"),
    ])


def _create_publication_package_panel() -> html.Div:
    """Create the publication package tab content."""
    return html.Div([
        dmc.Grid([
            # Left: Configuration
            dmc.GridCol([
                dmc.Paper([
                    dmc.Text("Package Configuration", fw=500, mb="sm"),

                    # Metadata fields
                    dmc.TextInput(
                        id="export-title",
                        label="Package Title",
                        placeholder="IVT Kinetics Analysis Results",
                        mb="sm",
                    ),
                    dmc.Textarea(
                        id="export-description",
                        label="Description",
                        placeholder="Describe the dataset...",
                        minRows=2,
                        mb="sm",
                    ),
                    dmc.TextInput(
                        id="export-authors",
                        label="Authors (comma-separated)",
                        placeholder="Author One, Author Two",
                        mb="sm",
                    ),
                    dmc.TextInput(
                        id="export-keywords",
                        label="Keywords (comma-separated)",
                        placeholder="IVT, kinetics, fluorescence",
                        mb="sm",
                    ),
                    dmc.Select(
                        id="export-license",
                        label="License",
                        data=[
                            {"value": "CC-BY-4.0", "label": "CC-BY 4.0 (Attribution)"},
                            {"value": "CC-BY-SA-4.0", "label": "CC-BY-SA 4.0 (ShareAlike)"},
                            {"value": "CC0-1.0", "label": "CC0 (Public Domain)"},
                            {"value": "MIT", "label": "MIT License"},
                        ],
                        value="CC-BY-4.0",
                        mb="md",
                    ),

                    dmc.Divider(mb="md"),

                    # Include options
                    dmc.Text("Include in Package", fw=500, mb="sm"),
                    dmc.Stack([
                        dmc.Checkbox(
                            id="export-include-raw",
                            label="Raw data (original measurements)",
                            checked=True,
                        ),
                        dmc.Checkbox(
                            id="export-include-traces",
                            label="MCMC traces (NetCDF format)",
                            checked=True,
                        ),
                        dmc.Checkbox(
                            id="export-include-figures",
                            label="Publication-ready figures",
                            checked=True,
                        ),
                        dmc.Checkbox(
                            id="export-include-audit",
                            label="Audit log",
                            checked=True,
                        ),
                    ], gap="xs", mb="md"),

                    # Figure options
                    dmc.Group([
                        dmc.Select(
                            id="export-figure-format",
                            label="Figure Format",
                            data=[
                                {"value": "png", "label": "PNG (300 DPI)"},
                                {"value": "svg", "label": "SVG (Vector)"},
                                {"value": "pdf", "label": "PDF"},
                            ],
                            value="png",
                            style={"flex": 1},
                        ),
                        dmc.NumberInput(
                            id="export-figure-dpi",
                            label="DPI",
                            value=300,
                            min=72,
                            max=600,
                            step=50,
                            style={"width": "100px"},
                        ),
                    ], mb="md"),

                    dmc.Button(
                        "Generate Preview",
                        id="export-preview-btn",
                        leftSection=DashIconify(icon="mdi:eye"),
                        fullWidth=True,
                        mb="sm",
                    ),
                ], p="md", withBorder=True),
            ], span=4),

            # Right: Preview
            dmc.GridCol([
                dmc.Paper([
                    dmc.Group([
                        dmc.Text("Package Preview", fw=500),
                        dmc.Group([
                            dmc.Text(
                                id="export-total-size",
                                children="Estimated size: --",
                                size="sm",
                                c="dimmed",
                            ),
                            dmc.ActionIcon(
                                DashIconify(icon="mdi:refresh"),
                                id="export-refresh-preview",
                                variant="subtle",
                            ),
                        ]),
                    ], justify="space-between", mb="sm"),

                    # Preview content
                    dmc.ScrollArea([
                        html.Div(
                            id="export-preview-content",
                            children=[
                                dmc.Center([
                                    dmc.Stack([
                                        DashIconify(
                                            icon="mdi:package-variant-closed",
                                            width=48,
                                            color="gray",
                                        ),
                                        dmc.Text(
                                            "Click 'Generate Preview' to see package contents",
                                            c="dimmed",
                                            ta="center",
                                        ),
                                    ], align="center", gap="sm"),
                                ], h=300),
                            ],
                        ),
                    ], h=400),

                    dmc.Divider(my="md"),

                    # Export actions
                    dmc.Group([
                        dmc.Button(
                            "Download Package",
                            id="export-download-btn",
                            leftSection=DashIconify(icon="mdi:download"),
                            disabled=True,
                        ),
                        dmc.Button(
                            "Validate Package",
                            id="export-validate-btn",
                            leftSection=DashIconify(icon="mdi:check-circle"),
                            variant="outline",
                            disabled=True,
                        ),
                    ], justify="flex-end"),
                ], p="md", withBorder=True),
            ], span=8),
        ]),
    ])


def _create_daily_report_panel() -> html.Div:
    """Create the daily report tab content."""
    return html.Div([
        dmc.Grid([
            # Left: Report configuration
            dmc.GridCol([
                dmc.Paper([
                    # Data selectors
                    dmc.Text("Data Selection", fw=500, mb="sm"),
                    dmc.Text(
                        "Choose which plates and analysis version to include.",
                        size="sm", c="dimmed", mb="md",
                    ),

                    dmc.MultiSelect(
                        id="report-plate-select",
                        label="Plates",
                        placeholder="Loading plates...",
                        data=[],
                        mb="sm",
                    ),
                    dmc.Select(
                        id="report-version-select",
                        label="Analysis Version",
                        placeholder="Loading versions...",
                        data=[],
                        mb="sm",
                    ),
                    dmc.Select(
                        id="report-protocol-select",
                        label="Protocol (Reaction Setup)",
                        placeholder="Loading setups...",
                        data=[],
                        mb="md",
                    ),

                    dmc.Divider(mb="md"),

                    dmc.Text("Report Sections", fw=500, mb="sm"),
                    dmc.Text(
                        "Select which sections to include in your daily report.",
                        size="sm", c="dimmed", mb="md",
                    ),

                    dmc.Stack([
                        dmc.Checkbox(
                            id="report-include-curves",
                            label="Curve Fits",
                            checked=True,
                        ),
                        dmc.Checkbox(
                            id="report-include-fc",
                            label="Fold Changes",
                            checked=True,
                        ),
                        dmc.Checkbox(
                            id="report-include-hierarchical",
                            label="Hierarchical Results",
                            checked=True,
                        ),
                        dmc.Checkbox(
                            id="report-include-plate-layout",
                            label="Plate Layout",
                            checked=True,
                        ),
                        dmc.Checkbox(
                            id="report-include-qc",
                            label="QC Summary",
                            checked=True,
                        ),
                        dmc.Checkbox(
                            id="report-include-protocol",
                            label="Protocol",
                            checked=False,
                        ),
                        dmc.Checkbox(
                            id="report-include-audit",
                            label="Audit Trail",
                            checked=False,
                        ),
                    ], gap="xs", mb="md"),

                    dmc.Divider(mb="md"),

                    dmc.Button(
                        "Generate Report",
                        id="report-generate-btn",
                        leftSection=DashIconify(icon="mdi:file-document-outline"),
                        fullWidth=True,
                        mb="sm",
                    ),
                    dmc.Button(
                        "Download Report",
                        id="report-download-btn",
                        leftSection=DashIconify(icon="mdi:download"),
                        fullWidth=True,
                        variant="outline",
                        disabled=True,
                    ),
                ], p="md", withBorder=True),
            ], span=4),

            # Right: Report preview / status
            dmc.GridCol([
                dmc.Paper([
                    dmc.Text("Report Preview", fw=500, mb="sm"),

                    html.Div(
                        id="report-preview-content",
                        children=[
                            dmc.Center([
                                dmc.Stack([
                                    DashIconify(
                                        icon="mdi:file-document-outline",
                                        width=48,
                                        color="gray",
                                    ),
                                    dmc.Text(
                                        "Select sections and click 'Generate Report' to prepare "
                                        "a daily report.",
                                        c="dimmed",
                                        ta="center",
                                    ),
                                    dmc.Text(
                                        "The report downloads as a print-ready PDF with "
                                        "static charts and formatted tables.",
                                        c="dimmed",
                                        ta="center",
                                        size="sm",
                                    ),
                                ], align="center", gap="sm"),
                            ], h=400),
                        ],
                    ),
                ], p="md", withBorder=True),
            ], span=8),
        ]),
    ])


def create_directory_tree(preview: Dict[str, Any], excluded_files: List[str]) -> html.Div:
    """
    Create directory tree display from preview data.

    Args:
        preview: Preview data from get_package_preview()
        excluded_files: List of excluded file paths

    Returns:
        Directory tree component
    """
    items = []

    for dir_info in preview.get("directories", []):
        dir_name = dir_info["name"]
        dir_files = dir_info.get("files", [])
        dir_size = dir_info.get("estimated_size", 0)

        # Directory header
        items.append(
            dmc.Group([
                DashIconify(icon="mdi:folder", width=20, color="#fab005"),
                dmc.Text(dir_name, fw=500),
                dmc.Badge(
                    f"{len(dir_files)} files",
                    size="xs",
                    variant="light",
                ),
                dmc.Text(
                    _format_size(dir_size),
                    size="xs",
                    c="dimmed",
                ),
            ], gap="xs", mb="xs")
        )

        # Files in directory
        for file_info in dir_files:
            file_path = f"{dir_name}/{file_info['name']}"
            is_excluded = file_path in excluded_files

            items.append(
                dmc.Group([
                    dmc.Checkbox(
                        id={"type": "export-file-checkbox", "index": file_path},
                        checked=not is_excluded,
                        size="xs",
                    ),
                    DashIconify(
                        icon=_get_file_icon(file_info.get("type", "")),
                        width=16,
                        color="gray" if is_excluded else "blue",
                    ),
                    dmc.Text(
                        file_info["name"],
                        size="sm",
                        c="dimmed" if is_excluded else "dark",
                        td="line-through" if is_excluded else None,
                    ),
                    dmc.Text(
                        _format_size(file_info.get("estimated_size", 0)),
                        size="xs",
                        c="dimmed",
                    ),
                ], gap="xs", ml="lg", mb=4)
            )

    # Root files
    for file_info in preview.get("files", []):
        file_path = file_info["name"]
        is_excluded = file_path in excluded_files

        items.append(
            dmc.Group([
                dmc.Checkbox(
                    id={"type": "export-file-checkbox", "index": file_path},
                    checked=not is_excluded,
                    size="xs",
                ),
                DashIconify(
                    icon=_get_file_icon(file_info.get("type", "")),
                    width=16,
                    color="gray" if is_excluded else "blue",
                ),
                dmc.Text(
                    file_info["name"],
                    size="sm",
                    c="dimmed" if is_excluded else "dark",
                ),
                dmc.Text(
                    _format_size(file_info.get("estimated_size", 0)),
                    size="xs",
                    c="dimmed",
                ),
            ], gap="xs", mb=4)
        )

    # Warnings
    for warning in preview.get("warnings", []):
        items.append(
            dmc.Alert(
                warning,
                color="yellow",
                icon=DashIconify(icon="mdi:alert"),
                mb="xs",
            )
        )

    return html.Div(items)


def _format_size(size_bytes: int) -> str:
    """Format size in bytes to human readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def _get_file_icon(content_type: str) -> str:
    """Get icon based on content type."""
    if "json" in content_type:
        return "mdi:code-json"
    elif "csv" in content_type:
        return "mdi:file-delimited"
    elif "markdown" in content_type:
        return "mdi:language-markdown"
    elif "image" in content_type:
        return "mdi:image"
    elif "netcdf" in content_type:
        return "mdi:database"
    else:
        return "mdi:file"
