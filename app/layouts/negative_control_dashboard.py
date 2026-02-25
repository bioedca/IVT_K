"""
Negative Control Dashboard layout.

Phase 3.5.8: Negative Control Dashboard (F19.13)

Displays:
- Background summary table per plate
- Detection limits (LOD, LOQ)
- Samples below detection limits
- Time series plot
- Plate heatmap view
"""
from typing import Optional, List, Dict, Any
import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify
import plotly.graph_objects as go

from app.theme import apply_plotly_theme


def create_negative_control_dashboard(
    project_id: Optional[int] = None,
    session_id: Optional[int] = None,
) -> html.Div:
    """
    Create the negative control dashboard layout.

    Args:
        project_id: Optional project ID for filtering
        session_id: Optional session ID for filtering

    Returns:
        Dashboard layout
    """
    return html.Div([
        # Stores
        dcc.Store(id="neg-ctrl-project-store", data=project_id),
        dcc.Store(id="neg-ctrl-session-store", data=session_id),
        dcc.Store(id="neg-ctrl-data-store", data=None),
        dcc.Store(id="neg-ctrl-qc-status-store", data=None),

        # Header with QC Status
        dmc.Group([
            dmc.Group([
                dmc.Title("Negative Control Dashboard", order=2),
                dmc.Badge("QC Review", color="blue", size="lg"),
            ], gap="sm"),
            html.Div(id="neg-ctrl-qc-status-badge"),
        ], justify="space-between", mb="md"),

        # Filters
        dmc.Paper([
            dmc.Grid([
                dmc.GridCol([
                    dmc.Select(
                        id="neg-ctrl-session-select",
                        label="Session",
                        placeholder="Select session",
                        data=[],
                        searchable=True,
                    )
                ], span=4),
                dmc.GridCol([
                    dmc.MultiSelect(
                        id="neg-ctrl-plate-select",
                        label="Plates",
                        placeholder="Select plates (all if empty)",
                        data=[],
                        searchable=True,
                    )
                ], span=4),
                dmc.GridCol([
                    dmc.Button(
                        "Refresh",
                        id="neg-ctrl-refresh-btn",
                        leftSection=DashIconify(icon="mdi:refresh"),
                        variant="light",
                        mt="xl",
                    )
                ], span=4, style={"display": "flex", "alignItems": "flex-end"}),
            ])
        ], p="md", mb="md", withBorder=True),

        # Main content
        dmc.Grid([
            # Left column: Summary table and detection limits
            dmc.GridCol([
                # Background Summary Table
                dmc.Paper([
                    dmc.Text("Background Summary", fw=500, mb="sm"),
                    html.Div(id="neg-ctrl-summary-table"),
                ], p="md", mb="md", withBorder=True),

                # Detection Limits Card
                dmc.Paper([
                    dmc.Text("Detection Limits", fw=500, mb="sm"),
                    html.Div(id="neg-ctrl-detection-limits"),
                ], p="md", mb="md", withBorder=True),

                # Samples below detection
                dmc.Paper([
                    dmc.Text("Detection Status", fw=500, mb="sm"),
                    html.Div(id="neg-ctrl-detection-status"),
                ], p="md", withBorder=True),
            ], span=5),

            # Right column: Visualizations (collapsible)
            dmc.GridCol([
                dmc.Accordion(
                    children=[
                        dmc.AccordionItem(
                            children=[
                                dmc.AccordionControl("Background Time Series"),
                                dmc.AccordionPanel([
                                    dmc.Group([
                                        dmc.SegmentedControl(
                                            id="neg-ctrl-timeseries-type",
                                            data=[
                                                {"value": "mean", "label": "Mean"},
                                                {"value": "all", "label": "All Wells"},
                                            ],
                                            value="mean",
                                            size="xs",
                                        ),
                                    ], justify="flex-end", mb="sm"),
                                    dcc.Graph(
                                        id="neg-ctrl-timeseries-plot",
                                        config={"displayModeBar": False},
                                        style={"height": "300px"},
                                    ),
                                ]),
                            ],
                            value="timeseries",
                        ),
                        dmc.AccordionItem(
                            children=[
                                dmc.AccordionControl("Spatial Distribution"),
                                dmc.AccordionPanel([
                                    dmc.Group([
                                        dmc.Select(
                                            id="neg-ctrl-heatmap-plate",
                                            placeholder="Select plate",
                                            data=[],
                                            size="xs",
                                            style={"width": "150px"},
                                        ),
                                    ], justify="flex-end", mb="sm"),
                                    dcc.Graph(
                                        id="neg-ctrl-heatmap",
                                        config={"displayModeBar": False},
                                        style={"height": "300px"},
                                    ),
                                ]),
                            ],
                            value="heatmap",
                        ),
                    ],
                    value=["timeseries", "heatmap"],
                    multiple=True,
                    variant="separated",
                ),
            ], span=7),
        ]),

        # QC Review Panel
        dmc.Paper([
            dmc.Text("QC Review", fw=500, mb="sm"),
            dmc.Stack([
                dmc.Textarea(
                    id="neg-ctrl-qc-notes",
                    label="Review Notes",
                    placeholder="Add notes about QC review (optional)...",
                    minRows=2,
                    maxRows=4,
                ),
                # Notification container - placed near buttons for visibility
                html.Div(id="neg-ctrl-notification-container"),
                dmc.Group([
                    dmc.Button(
                        "Approve QC",
                        id="neg-ctrl-approve-btn",
                        leftSection=DashIconify(icon="mdi:check-circle"),
                        color="green",
                        disabled=True,
                    ),
                    dmc.Button(
                        "Reject QC",
                        id="neg-ctrl-reject-btn",
                        leftSection=DashIconify(icon="mdi:close-circle"),
                        color="red",
                        variant="outline",
                        disabled=True,
                    ),
                    dmc.Button(
                        "Next Issue",
                        id="neg-ctrl-next-issue-btn",
                        leftSection=DashIconify(icon="mdi:arrow-right-circle"),
                        variant="light",
                        color="blue",
                        disabled=True,  # Enabled only after resolving current session
                    ),
                    dmc.Button(
                        "Export Report",
                        id="neg-ctrl-export-btn",
                        leftSection=DashIconify(icon="mdi:download"),
                        variant="outline",
                    ),
                ], justify="flex-end"),
            ], gap="sm"),
        ], p="md", mt="md", withBorder=True,
            style={
                "position": "sticky",
                "bottom": 0,
                "zIndex": 10,
                "background": "var(--mantine-color-body)",
                "paddingTop": "0.5rem",
                "borderTop": "1px solid var(--mantine-color-default-border)",
            },
        ),
    ])


def create_background_summary_table(
    plate_data: List[Dict[str, Any]],
) -> dmc.Table:
    """
    Create the background summary table.

    Args:
        plate_data: List of plate summary dicts

    Returns:
        Table component
    """
    if not plate_data:
        return dmc.Text("No data available", c="dimmed", ta="center")

    rows = []
    for plate in plate_data:
        # Determine correction method badge color
        corr_method = plate.get("correction_method", "simple")
        corr_colors = {"simple": "green", "time_dependent": "yellow", "spatial": "orange"}
        corr_color = corr_colors.get(corr_method, "gray")

        # CV status badge
        cv = plate.get("cv", 0) * 100
        cv_color = "green" if cv < 15 else ("yellow" if cv < 20 else "red")

        rows.append(
            html.Tr([
                html.Td(plate.get("plate_name", f"P{plate.get('plate_id', '?')}")),
                html.Td(str(plate.get("n_controls", 0))),
                html.Td(f"{plate.get('mean_bg', 0):.0f}"),
                html.Td(f"{plate.get('sd_bg', 0):.1f}"),
                html.Td(f"{plate.get('bsi', 0):.2f}"),
                html.Td(dmc.Badge(f"{cv:.1f}%", color=cv_color, size="sm")),
                html.Td(dmc.Badge(corr_method[:4].title(), color=corr_color, size="sm")),
            ])
        )

    return dmc.Table(
        striped=True,
        highlightOnHover=True,
        children=[
            html.Thead(
                html.Tr([
                    html.Th("Plate"),
                    html.Th("Neg Ctrls"),
                    html.Th("Mean BG"),
                    html.Th("SD BG"),
                    html.Th("BSI"),
                    html.Th("CV"),
                    html.Th("Corr"),
                ])
            ),
            html.Tbody(rows),
        ],
    )


def create_detection_limits_display(
    lod: float,
    loq: float,
    min_detectable_fc: float,
) -> html.Div:
    """
    Create detection limits display with color coding.

    Args:
        lod: Limit of Detection
        loq: Limit of Quantification
        min_detectable_fc: Minimum detectable fold change

    Returns:
        Display component
    """
    # Color code Min FC based on sensitivity
    # < 1.5 = excellent (green), 1.5-2.0 = good (blue), 2.0-3.0 = moderate (yellow), > 3.0 = poor (red)
    if min_detectable_fc < 1.5:
        fc_color = "green"
        fc_bg = "var(--bg-surface)"
    elif min_detectable_fc < 2.0:
        fc_color = "blue"
        fc_bg = "var(--bg-surface)"
    elif min_detectable_fc < 3.0:
        fc_color = "yellow"
        fc_bg = "var(--bg-surface)"
    else:
        fc_color = "red"
        fc_bg = "var(--bg-surface)"

    return html.Div([
        dmc.Grid([
            dmc.GridCol([
                dmc.Paper([
                    dmc.Text("LOD", size="xs", c="red", fw=500),
                    dmc.Text(f"{lod:.0f} RFU", size="lg", fw=700, c="red"),
                    dmc.Text("mean + 3\u03c3", size="xs", c="dimmed"),
                    dmc.Text("Lowest detectable signal", size="xs", c="dimmed", fs="italic", mt=4),
                ], p="sm", withBorder=True, ta="center", style={"backgroundColor": "var(--bg-surface)", "borderColor": "var(--border-medium)"})
            ], span=4),
            dmc.GridCol([
                dmc.Paper([
                    dmc.Text("LOQ", size="xs", c="orange", fw=500),
                    dmc.Text(f"{loq:.0f} RFU", size="lg", fw=700, c="orange"),
                    dmc.Text("mean + 10\u03c3", size="xs", c="dimmed"),
                    dmc.Text("Reliable quantification threshold", size="xs", c="dimmed", fs="italic", mt=4),
                ], p="sm", withBorder=True, ta="center", style={"backgroundColor": "var(--bg-surface)", "borderColor": "var(--border-medium)"})
            ], span=4),
            dmc.GridCol([
                dmc.Paper([
                    dmc.Text("Min FC", size="xs", c=fc_color, fw=500),
                    dmc.Text(f"{min_detectable_fc:.2f}", size="lg", fw=700, c=fc_color),
                    dmc.Text("LOD / mean background", size="xs", c="dimmed"),
                    dmc.Text("Smallest measurable fold change", size="xs", c="dimmed", fs="italic", mt=4),
                ], p="sm", withBorder=True, ta="center", style={"backgroundColor": fc_bg})
            ], span=4),
        ]),
    ])


def create_detection_status_display(
    total_samples: int,
    below_lod: int,
    below_loq: int,
) -> html.Div:
    """
    Create detection status display.

    Args:
        total_samples: Total number of samples
        below_lod: Samples below LOD
        below_loq: Samples below LOQ (but above LOD)

    Returns:
        Display component
    """
    above_loq = total_samples - below_lod - below_loq

    # Calculate percentages
    pct_above_loq = (above_loq / total_samples * 100) if total_samples > 0 else 0
    pct_below_loq = (below_loq / total_samples * 100) if total_samples > 0 else 0
    pct_below_lod = (below_lod / total_samples * 100) if total_samples > 0 else 0

    # Create stacked progress visualization using a horizontal bar
    return html.Div([
        # Stacked bar using divs
        html.Div([
            html.Div(
                style={
                    "width": f"{pct_above_loq}%",
                    "backgroundColor": "#40c057",  # green
                    "height": "24px",
                    "display": "inline-block",
                }
            ),
            html.Div(
                style={
                    "width": f"{pct_below_loq}%",
                    "backgroundColor": "#fab005",  # yellow
                    "height": "24px",
                    "display": "inline-block",
                }
            ),
            html.Div(
                style={
                    "width": f"{pct_below_lod}%",
                    "backgroundColor": "#fa5252",  # red
                    "height": "24px",
                    "display": "inline-block",
                }
            ),
        ], style={
            "width": "100%",
            "backgroundColor": "var(--bg-hover)",
            "borderRadius": "4px",
            "overflow": "hidden",
            "marginBottom": "8px",
        }),
        dmc.Group([
            dmc.Badge(f"Above LOQ: {above_loq}", color="green", size="sm"),
            dmc.Badge(f"Below LOQ: {below_loq}", color="yellow", size="sm"),
            dmc.Badge(f"Below LOD: {below_lod}", color="red", size="sm"),
        ], gap="xs"),
        dmc.Text(
            f"Total: {total_samples} samples",
            size="sm",
            c="dimmed",
            mt="xs",
        ),
    ])


def create_background_timeseries_plot(
    timepoints: List[float],
    mean_values: List[float],
    sd_values: Optional[List[float]] = None,
    individual_wells: Optional[Dict[str, List[float]]] = None,
    show_all: bool = False,
) -> go.Figure:
    """
    Create background time series plot.

    Args:
        timepoints: Time values
        mean_values: Mean background at each timepoint
        sd_values: Optional SD values for error band
        individual_wells: Optional dict of individual well traces
        show_all: Whether to show individual wells

    Returns:
        Plotly figure
    """
    fig = go.Figure()

    if show_all and individual_wells:
        # Show individual wells
        for well_pos, values in individual_wells.items():
            fig.add_trace(go.Scatter(
                x=timepoints[:len(values)],
                y=values,
                mode="lines",
                name=well_pos,
                opacity=0.5,
                line=dict(width=1),
            ))
    else:
        # Show mean with error band
        if sd_values:
            upper = [m + s for m, s in zip(mean_values, sd_values)]
            lower = [m - s for m, s in zip(mean_values, sd_values)]

            fig.add_trace(go.Scatter(
                x=timepoints + timepoints[::-1],
                y=upper + lower[::-1],
                fill="toself",
                fillcolor="rgba(100, 100, 100, 0.2)",
                line=dict(color="rgba(0,0,0,0)"),
                name="\u00b1 1 SD",
                showlegend=True,
            ))

        fig.add_trace(go.Scatter(
            x=timepoints,
            y=mean_values,
            mode="lines+markers",
            name="Mean Background",
            line=dict(color="blue", width=2),
            marker=dict(size=4),
        ))

    fig.update_layout(
        xaxis_title="Time (min)",
        yaxis_title="Fluorescence (RFU)",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=50, r=20, t=30, b=40),
        hovermode="x unified",
    )

    return fig


def create_plate_heatmap(
    well_values: Dict[str, float],
    plate_format: int = 96,
    title: str = "Mean Background",
    *,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create plate heatmap for background visualization.

    Args:
        well_values: Dict mapping well position to value
        plate_format: Plate format (96 or 384)
        title: Colorbar title
        dark_mode: Whether to apply dark mode theme

    Returns:
        Plotly figure
    """
    if plate_format == 96:
        n_rows, n_cols = 8, 12
    else:
        n_rows, n_cols = 16, 24

    # Create grid
    z_values = [[None] * n_cols for _ in range(n_rows)]

    for pos, val in well_values.items():
        if len(pos) < 2:
            continue
        row = ord(pos[0].upper()) - ord('A')
        try:
            col = int(pos[1:]) - 1
        except ValueError:
            continue

        if 0 <= row < n_rows and 0 <= col < n_cols:
            z_values[row][col] = val

    # Row and column labels
    row_labels = [chr(ord('A') + i) for i in range(n_rows)]
    col_labels = [str(i + 1) for i in range(n_cols)]

    fig = go.Figure(data=go.Heatmap(
        z=z_values,
        x=col_labels,
        y=row_labels,
        colorscale="Viridis",
        colorbar=dict(title=title, thickness=15, len=0.9),
        hoverongaps=False,
        hovertemplate="Well: %{y}%{x}<br>Value: %{z:.0f} RFU<extra></extra>",
    ))

    # Add grid lines as shapes at well boundaries
    shapes = []
    line_color = "#999999" if dark_mode else "#555555"
    line_width = 1

    # Vertical lines (at column edges)
    for i in range(n_cols + 1):
        shapes.append(dict(
            type="line",
            x0=i - 0.5, x1=i - 0.5,
            y0=-0.5, y1=n_rows - 0.5,
            line=dict(color=line_color, width=line_width),
            layer="above",
        ))

    # Horizontal lines (at row edges)
    for i in range(n_rows + 1):
        shapes.append(dict(
            type="line",
            x0=-0.5, x1=n_cols - 0.5,
            y0=i - 0.5, y1=i - 0.5,
            line=dict(color=line_color, width=line_width),
            layer="above",
        ))

    fig.update_layout(
        xaxis=dict(
            side="top",
            tickangle=0,
            tickfont=dict(size=9),
            dtick=1,
            constrain="domain",
            showgrid=False,
            zeroline=False,
            ticks="",
        ),
        yaxis=dict(
            autorange="reversed",
            tickfont=dict(size=9),
            dtick=1,
            constrain="domain",
            showgrid=False,
            zeroline=False,
            ticks="",
        ),
        margin=dict(l=20, r=60, t=20, b=10),
        shapes=shapes,
    )

    apply_plotly_theme(fig, dark_mode)

    return fig


def create_empty_dashboard_message() -> html.Div:
    """Create message for empty dashboard state."""
    return html.Div([
        dmc.Alert(
            title="No Data Available",
            children="Select a session to view negative control analysis.",
            color="blue",
            icon=DashIconify(icon="mdi:information"),
        ),
    ], style={"marginTop": "20px"})


def create_qc_status_badge(
    qc_status: str,
    reviewed_by: Optional[str] = None,
    reviewed_at: Optional[str] = None,
) -> dmc.Group:
    """
    Create a QC status badge with reviewer info.

    Args:
        qc_status: One of 'pending', 'in_review', 'approved', 'rejected'
        reviewed_by: Username of reviewer
        reviewed_at: Timestamp of review

    Returns:
        Group with status badge and optional reviewer info
    """
    status_config = {
        "pending": {"color": "gray", "icon": "mdi:clock-outline", "label": "Pending Review"},
        "in_review": {"color": "blue", "icon": "mdi:eye", "label": "In Review"},
        "approved": {"color": "green", "icon": "mdi:check-circle", "label": "QC Approved"},
        "rejected": {"color": "red", "icon": "mdi:close-circle", "label": "QC Rejected"},
    }

    config = status_config.get(qc_status.lower(), status_config["pending"])

    badge = dmc.Badge(
        config["label"],
        color=config["color"],
        size="lg",
        leftSection=DashIconify(icon=config["icon"], width=16),
    )

    elements = [badge]

    if reviewed_by and qc_status.lower() in ["approved", "rejected"]:
        reviewer_text = f"by {reviewed_by}"
        if reviewed_at:
            reviewer_text += f" on {reviewed_at}"
        elements.append(
            dmc.Text(reviewer_text, size="xs", c="dimmed")
        )

    return dmc.Group(elements, gap="xs")
