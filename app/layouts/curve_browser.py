"""
Curve Browser layout.

Phase 4.12: Curve Browser visualization (F8.8, F8.9, F13.2)

Provides:
- Well selection grid with filters
- Curve visualization with fit overlay
- Residuals plot
- Side-by-side comparison (2-panel, 4-panel)
- Add to comparison workflow
"""
from typing import Optional, List, Dict, Any
import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify


def create_curve_browser_layout(
    project_id: Optional[int] = None,
) -> html.Div:
    """
    Create the curve browser layout.

    Args:
        project_id: Optional project ID for initial filter

    Returns:
        Curve browser layout
    """
    return html.Div([
        # Stores
        dcc.Store(id="curve-browser-project-store", data=project_id),
        dcc.Store(id="curve-browser-selected-wells", data=[]),  # All wells matching filters
        dcc.Store(id="curve-browser-multi-select", data=[]),  # User's multi-selected wells
        dcc.Store(id="curve-browser-comparison-set", data=[]),
        dcc.Store(id="curve-browser-current-well", data=None),
        dcc.Store(id="curve-browser-active-panel", data=0),  # Which panel to add wells to (0-3)
        dcc.Store(id="curve-browser-panel-wells", data=[[], [], [], []]),  # Wells in each panel

        # Header
        dmc.Group([
            dmc.Title("Curve Browser", order=2),
            dmc.Group([
                dmc.Badge(
                    id="curve-browser-multi-select-badge",
                    children="0 selected",
                    color="gray",
                    size="lg",
                ),
                dmc.Button(
                    "Clear Selection",
                    id="curve-browser-clear-multi-select",
                    variant="subtle",
                    size="xs",
                    color="gray",
                ),
                dmc.Tooltip(
                    label="Click wells to toggle selection. Selected wells shown as overlay.",
                    children=dmc.ActionIcon(
                        DashIconify(icon="mdi:information-outline"),
                        variant="light",
                    ),
                ),
            ], gap="xs"),
        ], justify="space-between", mb="md"),

        # Filters bar
        dmc.Paper([
            dmc.Grid([
                dmc.GridCol([
                    dmc.Select(
                        id="curve-browser-session-filter",
                        label="Session",
                        placeholder="All sessions",
                        data=[],
                        value=None,
                        clearable=True,
                        searchable=True,
                    )
                ], span=2),
                dmc.GridCol([
                    dmc.Select(
                        id="curve-browser-plate-filter",
                        label="Plate",
                        placeholder="All plates",
                        data=[],
                        value=None,
                        clearable=True,
                        searchable=True,
                    )
                ], span=2),
                dmc.GridCol([
                    dmc.Select(
                        id="curve-browser-construct-filter",
                        label="Construct",
                        placeholder="All constructs",
                        data=[],
                        clearable=True,
                        searchable=True,
                    )
                ], span=2),
                dmc.GridCol([
                    dmc.SegmentedControl(
                        id="curve-browser-qc-filter",
                        data=[
                            {"value": "all", "label": "All"},
                            {"value": "passed", "label": "Passed"},
                            {"value": "failed", "label": "Failed"},
                            {"value": "review", "label": "Review"},
                        ],
                        value="all",
                        size="xs",
                    )
                ], span=3),
                dmc.GridCol([
                    dmc.Checkbox(
                        id="curve-browser-show-excluded",
                        label="Show Excluded",
                        checked=False,
                    )
                ], span=2),
                dmc.GridCol([
                    dmc.Button(
                        "Reset",
                        id="curve-browser-reset-filters",
                        variant="subtle",
                        size="xs",
                        leftSection=DashIconify(icon="mdi:filter-off"),
                    )
                ], span=1, style={"display": "flex", "alignItems": "flex-end"}),
            ]),
        ], p="sm", mb="md", withBorder=True),

        # Main content
        dmc.Grid([
            # Left: Well selection grid
            dmc.GridCol([
                dmc.Paper([
                    dmc.Group([
                        dmc.Text("Wells", fw=500),
                        dmc.Text(id="curve-browser-well-count", size="sm", c="dimmed"),
                    ], justify="space-between", mb="sm"),
                    dmc.ScrollArea([
                        html.Div(id="curve-browser-well-grid"),
                    ], h=600),
                ], p="md", withBorder=True),
            ], span=3),

            # Center/Right: Actions, Plot, and Details
            dmc.GridCol([
                # Actions bar (above graph)
                dmc.Paper([
                    dmc.Group([
                        dmc.Group([
                            dmc.Button(
                                "Exclude Well",
                                id="curve-browser-exclude-btn",
                                variant="outline",
                                color="red",
                                size="xs",
                                leftSection=DashIconify(icon="mdi:close-circle"),
                            ),
                            dmc.Button(
                                "Include Well",
                                id="curve-browser-include-btn",
                                variant="outline",
                                color="green",
                                size="xs",
                                leftSection=DashIconify(icon="mdi:check-circle"),
                                style={"display": "none"},
                            ),
                            dmc.Button(
                                "Re-fit in Analysis",
                                id="curve-browser-refit-btn",
                                variant="outline",
                                size="xs",
                                leftSection=DashIconify(icon="mdi:arrow-right-circle"),
                            ),
                        ], gap="xs"),
                        dmc.Divider(orientation="vertical", h=24),
                        dmc.Group([
                            dmc.Button(
                                "Exclude from FC",
                                id="curve-browser-fc-exclude-btn",
                                variant="outline",
                                color="orange",
                                size="xs",
                                leftSection=DashIconify(icon="mdi:calculator-variant-remove"),
                            ),
                            dmc.Button(
                                "Include in FC",
                                id="curve-browser-fc-include-btn",
                                variant="outline",
                                color="teal",
                                size="xs",
                                leftSection=DashIconify(icon="mdi:calculator-variant"),
                                style={"display": "none"},
                            ),
                        ], gap="xs"),
                    ], justify="space-between"),
                ], p="sm", mb="sm", withBorder=True),
                # Hidden elements for callback compatibility
                html.Div([
                    dmc.ActionIcon(id="curve-browser-prev-btn", style={"display": "none"}),
                    dmc.ActionIcon(id="curve-browser-next-btn", style={"display": "none"}),
                    html.Span(id="curve-browser-well-position", style={"display": "none"}),
                ]),

                # Plot area
                dmc.Paper([
                    # Layout and panel selector
                    dmc.Group([
                        dmc.Group([
                            dmc.SegmentedControl(
                                id="curve-browser-layout",
                                data=[
                                    {"value": "single", "label": "Single"},
                                    {"value": "2-panel", "label": "2-Panel"},
                                    {"value": "4-panel", "label": "4-Panel"},
                                ],
                                value="single",
                                size="xs",
                            ),
                            dmc.Divider(orientation="vertical", h=24),
                            dmc.Text("Add to:", size="xs", c="dimmed"),
                            dmc.SegmentedControl(
                                id="curve-browser-active-panel-select",
                                data=[
                                    {"value": "0", "label": "P1"},
                                    {"value": "1", "label": "P2"},
                                    {"value": "2", "label": "P3"},
                                    {"value": "3", "label": "P4"},
                                ],
                                value="0",
                                size="xs",
                            ),
                            dmc.Button(
                                "Clear Panels",
                                id="curve-browser-clear-panels",
                                variant="subtle",
                                size="xs",
                                color="gray",
                            ),
                        ], gap="xs"),
                        dmc.Group([
                            dmc.Checkbox(
                                id="curve-browser-show-fit",
                                label="Show Fit",
                                checked=True,
                                size="xs",
                            ),
                            dmc.Checkbox(
                                id="curve-browser-show-residuals",
                                label="Residuals",
                                checked=False,
                                size="xs",
                            ),
                        ]),
                    ], justify="space-between", mb="sm"),

                    # Graph
                    dcc.Graph(
                        id="curve-browser-plot",
                        config={
                            "displayModeBar": True,
                            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                        },
                        style={"height": "550px"},
                    ),
                ], p="md", mb="sm", withBorder=True),

                # Details and Parameters below graph
                dmc.Grid([
                    dmc.GridCol([
                        dmc.Paper([
                            dmc.Text("Well Details", fw=500, mb="sm"),
                            html.Div(id="curve-browser-details-panel"),
                        ], p="md", withBorder=True, style={"height": "100%"}),
                    ], span=5),
                    dmc.GridCol([
                        dmc.Paper([
                            dmc.Text("Fit Parameters", fw=500, mb="sm"),
                            dmc.ScrollArea([
                                html.Div(id="curve-browser-params-panel"),
                            ], h=180),
                        ], p="md", withBorder=True, style={"height": "100%"}),
                    ], span=7),
                ]),
            ], span=9),
        ]),

        # Exclusion reason modal
        dmc.Modal(
            id="curve-browser-exclusion-modal",
            title="Exclude Well",
            centered=True,
            children=[
                dmc.Textarea(
                    id="curve-browser-exclusion-reason",
                    label="Reason for exclusion",
                    placeholder="Enter reason for excluding this well...",
                    minRows=3,
                    required=True,
                ),
                dmc.Group([
                    dmc.Button(
                        "Cancel",
                        id="curve-browser-exclusion-cancel",
                        variant="outline",
                    ),
                    dmc.Button(
                        "Exclude",
                        id="curve-browser-exclusion-confirm",
                        color="red",
                    ),
                ], justify="flex-end", mt="md"),
            ],
        ),
    ])


def create_well_grid_item(
    well_id: int,
    position: str,
    construct_name: Optional[str] = None,
    status: str = "pending",
    is_excluded: bool = False,
    is_selected: bool = False,
    is_in_comparison: bool = False,
    is_multi_selected: bool = False,
) -> html.Div:
    """
    Create a well grid item.

    Args:
        well_id: Well database ID
        position: Well position (e.g., "A1")
        construct_name: Construct identifier
        status: Fit status (pending, completed, failed, flagged)
        is_excluded: Whether well is excluded
        is_selected: Whether well is currently selected (primary)
        is_in_comparison: Whether well is in comparison set
        is_multi_selected: Whether well is in multi-selection

    Returns:
        Well grid item component
    """
    # Determine colors based on status
    status_colors = {
        "pending": "gray",
        "completed": "green",
        "failed": "red",
        "flagged": "yellow",
    }
    border_color = status_colors.get(status, "gray")

    # Build style
    style = {
        "cursor": "pointer",
        "opacity": 0.5 if is_excluded else 1.0,
        "textDecoration": "line-through" if is_excluded else "none",
    }

    if is_multi_selected:
        style["boxShadow"] = "0 0 0 2px var(--mantine-color-teal-filled)"
        style["backgroundColor"] = "var(--mantine-color-teal-light)"
    elif is_selected:
        style["boxShadow"] = "0 0 0 2px var(--mantine-color-blue-filled)"

    return html.Div(
        id={"type": "well-grid-item", "well_id": well_id},
        n_clicks=0,
        children=dmc.Paper(
            children=[
                dmc.Group([
                    dmc.Text(position, fw=500, size="sm"),
                    dmc.Badge("", color=border_color, size="xs", variant="dot"),
                ], justify="space-between"),
                dmc.Text(
                    construct_name or "-",
                    size="xs",
                    c="dimmed",
                    truncate=True,
                ),
                html.Div([
                    dmc.Badge(
                        DashIconify(icon="mdi:compare"),
                        color="blue",
                        size="xs",
                        variant="light",
                    ) if is_in_comparison else None,
                ]),
            ],
            p="xs",
            withBorder=True,
            style=style,
            className="well-grid-item",
        ),
    )


def create_well_details_panel(
    well_id: int,
    position: str,
    plate_name: str,
    construct_name: str,
    well_type: str,
    ligand: Optional[float] = None,
    ligand_condition: Optional[str] = None,
    status: str = "pending",
    exclusion_reason: Optional[str] = None,
    include_in_fc: bool = True,
) -> html.Div:
    """
    Create the well details panel content.

    Args:
        well_id: Well database ID
        position: Well position
        plate_name: Plate identifier
        construct_name: Construct name
        well_type: Well type
        ligand: Ligand concentration
        status: Fit status
        exclusion_reason: Reason if excluded
        include_in_fc: Whether well is included in fold change calculations
                       (syncs with Analysis tab's FC inclusion checkbox)

    Returns:
        Details panel content
    """
    status_colors = {
        "pending": "gray",
        "completed": "green",
        "failed": "red",
        "flagged": "yellow",
    }

    return html.Div([
        dmc.Stack([
            dmc.Group([
                dmc.Text("Position:", size="sm", c="dimmed"),
                dmc.Text(position, size="sm", fw=500),
            ], justify="space-between"),
            dmc.Group([
                dmc.Text("Plate:", size="sm", c="dimmed"),
                dmc.Text(plate_name, size="sm"),
            ], justify="space-between"),
            dmc.Group([
                dmc.Text("Construct:", size="sm", c="dimmed"),
                dmc.Text(construct_name, size="sm"),
            ], justify="space-between"),
            dmc.Group([
                dmc.Text("Type:", size="sm", c="dimmed"),
                dmc.Text(well_type, size="sm"),
            ], justify="space-between"),
            dmc.Group([
                dmc.Text("Ligand:", size="sm", c="dimmed"),
                dmc.Text(
                    f"{ligand} mM" if ligand is not None else "N/A",
                    size="sm"
                ),
            ], justify="space-between"),
            dmc.Group([
                dmc.Text("Condition:", size="sm", c="dimmed"),
                dmc.Badge(
                    ligand_condition,
                    color="teal" if ligand_condition == "+Lig" else "orange",
                    size="sm",
                    variant="light",
                ) if ligand_condition else dmc.Text("N/A", size="sm"),
            ], justify="space-between") if ligand_condition else None,
            dmc.Group([
                dmc.Text("Status:", size="sm", c="dimmed"),
                dmc.Badge(status, color=status_colors.get(status, "gray"), size="sm"),
            ], justify="space-between"),
            # FC inclusion status - syncs with Analysis tab checkbox
            # See: analysis_callbacks.py toggle_well_fc_inclusion()
            dmc.Divider(my="xs"),
            dmc.Group([
                dmc.Text("Include in FC:", size="sm", c="dimmed"),
                dmc.Badge(
                    "Yes" if include_in_fc else "No",
                    color="green" if include_in_fc else "gray",
                    size="sm",
                    variant="light" if include_in_fc else "outline",
                ),
            ], justify="space-between"),
        ], gap="xs"),

        html.Div([
            dmc.Divider(my="sm"),
            dmc.Alert(
                title="Excluded",
                children=exclusion_reason,
                color="red",
                icon=DashIconify(icon="mdi:alert"),
            ),
        ]) if exclusion_reason else None,
    ])


def create_fit_params_panel(
    params: Optional[Dict[str, float]] = None,
    uncertainties: Optional[Dict[str, float]] = None,
    multi_params: Optional[List[Dict[str, Any]]] = None,
) -> html.Div:
    """
    Create the fit parameters panel content.

    Args:
        params: Fit parameters dict (single well mode)
        uncertainties: Parameter uncertainties
        multi_params: List of dicts with well_id, position, construct, and params (multi-select mode)

    Returns:
        Parameters panel content
    """
    # Multi-select mode: show table of all selected wells
    if multi_params and len(multi_params) > 0:
        # Build table header
        header = dmc.TableThead(
            dmc.TableTr([
                dmc.TableTh("Well", style={"fontSize": "12px"}),
                dmc.TableTh("Construct", style={"fontSize": "12px"}),
                dmc.TableTh("k_obs (min\u207b\u00b9)", style={"fontSize": "12px"}),
                dmc.TableTh("F_max", style={"fontSize": "12px"}),
                dmc.TableTh("R\u00b2", style={"fontSize": "12px"}),
            ])
        )

        # Build table rows
        rows = []
        for wp in multi_params:
            p = wp.get("params", {})
            rows.append(
                dmc.TableTr([
                    dmc.TableTd(wp.get("position", ""), style={"fontSize": "12px", "fontWeight": 500}),
                    dmc.TableTd(wp.get("construct", ""), style={"fontSize": "12px"}),
                    dmc.TableTd(f"{p.get('k_obs', 0):.4f}" if p.get("k_obs") else "-", style={"fontSize": "12px"}),
                    dmc.TableTd(f"{p.get('F_max', 0):.0f}" if p.get("F_max") else "-", style={"fontSize": "12px"}),
                    dmc.TableTd(f"{p.get('R2', 0):.3f}" if p.get("R2") else "-", style={"fontSize": "12px"}),
                ])
            )

        return dmc.Table(
            [header, dmc.TableTbody(rows)],
            striped=True,
            highlightOnHover=True,
            withTableBorder=True,
            withColumnBorders=True,
        )

    # Single well mode
    if not params:
        return dmc.Text("No fit data available", c="dimmed", ta="center")

    uncertainties = uncertainties or {}

    rows = []
    param_labels = {
        "k_obs": ("k_obs", "min\u207b\u00b9"),
        "F_max": ("F_max", "RFU"),
        "t_lag": ("t_lag", "min"),
        "F_0": ("F_0", "RFU"),
        "R2": ("R\u00b2", ""),
        "rmse": ("RMSE", "RFU"),
    }

    for key, (label, unit) in param_labels.items():
        if key in params:
            value = params[key]
            unc = uncertainties.get(key)

            if unc:
                value_str = f"{value:.4g} \u00b1 {unc:.2g}"
            else:
                value_str = f"{value:.4g}"

            if unit:
                value_str += f" {unit}"

            rows.append(
                dmc.Group([
                    dmc.Text(label, size="sm", c="dimmed"),
                    dmc.Text(value_str, size="sm", fw=500),
                ], justify="space-between")
            )

    return dmc.Stack(rows, gap="xs")


def create_empty_plot_message() -> html.Div:
    """Create message for empty plot state."""
    return dmc.Paper([
        dmc.Center([
            dmc.Stack([
                DashIconify(icon="mdi:chart-line", width=48, color="gray"),
                dmc.Text("Select a well to view its curve", c="dimmed"),
            ], align="center", gap="sm"),
        ], style={"height": "400px"}),
    ], withBorder=True)
