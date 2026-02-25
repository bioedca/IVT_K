"""
Cross-project comparison layout.

Sprint 8: Cross-Project Features (PRD Section 3.20)

Provides:
- F20.1: View constructs by identifier across projects
- F20.2: Side-by-side forest plot for same construct from different projects
- F20.3: Overlay posteriors from different projects
- F20.4: Tabular comparison of estimates with CIs

Note: Read-only comparison view. No meta-analysis.
"""
from dash import html, dcc
import dash_mantine_components as dmc


def create_cross_project_comparison_layout():
    """
    Create the cross-project comparison layout.

    Features:
    - Construct identifier selector (shared across projects)
    - Project selection checklist
    - Parameter type selector
    - Forest plot comparing projects
    - Posterior overlay plot
    - Summary statistics table
    - Export button
    """
    return dmc.Container(
        children=[
            # Header
            dmc.Group(
                children=[
                    dmc.Title("Cross-Project Comparison", order=2),
                    dmc.Badge(
                        "Read-Only View",
                        color="gray",
                        variant="outline",
                        size="lg"
                    ),
                ],
                justify="space-between",
                style={"marginBottom": "1rem"}
            ),

            # Description
            dmc.Alert(
                children=[
                    "Compare the same construct across different projects. ",
                    "This is a read-only comparison view - projects remain ",
                    "statistically independent (no data pooling or meta-analysis)."
                ],
                title="About Cross-Project Comparison",
                color="blue",
                variant="light",
                style={"marginBottom": "1.5rem"}
            ),

            # Main content grid
            dmc.Grid(
                children=[
                    # Left panel: Selection controls
                    dmc.GridCol(
                        children=[
                            dmc.Paper(
                                children=[
                                    # Construct selector
                                    dmc.Stack(
                                        children=[
                                            dmc.Text(
                                                "Select Construct",
                                                fw=600,
                                                size="sm"
                                            ),
                                            dmc.Select(
                                                id="cross-project-construct-select",
                                                placeholder="Choose a construct...",
                                                searchable=True,
                                                nothingFoundMessage="No matching constructs",
                                                data=[],  # Populated by callback
                                                style={"marginBottom": "1rem"}
                                            ),

                                            # Parameter selector
                                            dmc.Text(
                                                "Parameter",
                                                fw=600,
                                                size="sm"
                                            ),
                                            dmc.SegmentedControl(
                                                id="cross-project-parameter-select",
                                                data=[
                                                    {"value": "log_fc_fmax", "label": "FC(F_max)"},
                                                    {"value": "log_fc_kobs", "label": "FC(k_obs)"},
                                                    {"value": "delta_tlag", "label": "Δt_lag"},
                                                ],
                                                value="log_fc_fmax",
                                                fullWidth=True,
                                                style={"marginBottom": "1rem"}
                                            ),

                                            # Analysis type selector
                                            dmc.Text(
                                                "Analysis Type",
                                                fw=600,
                                                size="sm"
                                            ),
                                            dmc.SegmentedControl(
                                                id="cross-project-analysis-type",
                                                data=[
                                                    {"value": "bayesian", "label": "Bayesian"},
                                                    {"value": "frequentist", "label": "Frequentist"},
                                                ],
                                                value="bayesian",
                                                fullWidth=True,
                                                style={"marginBottom": "1rem"}
                                            ),

                                            dmc.Divider(style={"marginY": "1rem"}),

                                            # Project selection
                                            dmc.Text(
                                                "Projects Containing This Construct",
                                                fw=600,
                                                size="sm",
                                                style={"marginBottom": "0.5rem"}
                                            ),
                                            html.Div(
                                                id="cross-project-project-list",
                                                children=[
                                                    dmc.Text(
                                                        "Select a construct to see available projects",
                                                        c="dimmed",
                                                        size="sm",
                                                        fs="italic"
                                                    )
                                                ]
                                            ),
                                        ],
                                        gap="xs"
                                    )
                                ],
                                p="md",
                                radius="md",
                                withBorder=True
                            )
                        ],
                        span=3
                    ),

                    # Right panel: Visualizations and results
                    dmc.GridCol(
                        children=[
                            # Forest plot
                            dmc.Paper(
                                children=[
                                    dmc.Group(
                                        children=[
                                            dmc.Text("Forest Plot Comparison", fw=600),
                                            dmc.ActionIcon(
                                                id="cross-project-forest-download",
                                                children=dmc.Text("⬇", size="sm"),
                                                variant="subtle",
                                                color="gray",
                                                size="sm"
                                            )
                                        ],
                                        justify="space-between",
                                        style={"marginBottom": "0.5rem"}
                                    ),
                                    dcc.Graph(
                                        id="cross-project-forest-plot",
                                        config={
                                            "displayModeBar": True,
                                            "toImageButtonOptions": {
                                                "format": "svg",
                                                "filename": "cross_project_forest"
                                            }
                                        },
                                        style={"height": "400px"}
                                    )
                                ],
                                p="md",
                                radius="md",
                                withBorder=True,
                                style={"marginBottom": "1rem"}
                            ),

                            # Posterior overlay plot
                            dmc.Paper(
                                children=[
                                    dmc.Group(
                                        children=[
                                            dmc.Text("Posterior Comparison", fw=600),
                                            dmc.ActionIcon(
                                                id="cross-project-posterior-download",
                                                children=dmc.Text("⬇", size="sm"),
                                                variant="subtle",
                                                color="gray",
                                                size="sm"
                                            )
                                        ],
                                        justify="space-between",
                                        style={"marginBottom": "0.5rem"}
                                    ),
                                    dcc.Graph(
                                        id="cross-project-posterior-plot",
                                        config={
                                            "displayModeBar": True,
                                            "toImageButtonOptions": {
                                                "format": "svg",
                                                "filename": "cross_project_posterior"
                                            }
                                        },
                                        style={"height": "300px"}
                                    )
                                ],
                                p="md",
                                radius="md",
                                withBorder=True,
                                style={"marginBottom": "1rem"}
                            ),

                            # Summary table
                            dmc.Paper(
                                children=[
                                    dmc.Group(
                                        children=[
                                            dmc.Text("Summary Table", fw=600),
                                            dmc.Button(
                                                "Export CSV",
                                                id="cross-project-export-btn",
                                                variant="light",
                                                color="blue",
                                                size="xs",
                                                leftSection=dmc.Text("📊", size="xs")
                                            )
                                        ],
                                        justify="space-between",
                                        style={"marginBottom": "0.5rem"}
                                    ),
                                    html.Div(
                                        id="cross-project-summary-table",
                                        children=[
                                            dmc.Text(
                                                "Select a construct and projects to see comparison data",
                                                c="dimmed",
                                                ta="center",
                                                py="xl"
                                            )
                                        ]
                                    )
                                ],
                                p="md",
                                radius="md",
                                withBorder=True
                            ),

                            # Download component (hidden)
                            dcc.Download(id="cross-project-download-csv")
                        ],
                        span=9
                    )
                ],
                gutter="md"
            ),

            # Store for selected projects
            dcc.Store(id="cross-project-selected-projects", data=[]),

            # Store for comparison data
            dcc.Store(id="cross-project-comparison-data", data=None)
        ],
        size="xl",
        py="md"
    )


def create_project_checkbox_item(
    project_id: int,
    project_name: str,
    plate_count: int,
    replicate_count: int,
    has_analysis: bool,
    analysis_date: str = None,
    checked: bool = True
) -> dmc.Checkbox:
    """
    Create a checkbox item for project selection.

    Args:
        project_id: Project ID
        project_name: Project name
        plate_count: Number of plates
        replicate_count: Number of replicates
        has_analysis: Whether project has completed analysis
        analysis_date: Date of latest analysis
        checked: Initial checked state
    """
    label_parts = [project_name]

    if plate_count > 0:
        label_parts.append(f"({plate_count} plates, {replicate_count} replicates)")

    if not has_analysis:
        label_parts.append("[No analysis]")

    return dmc.Checkbox(
        id={"type": "cross-project-checkbox", "index": project_id},
        label=" ".join(label_parts),
        checked=checked and has_analysis,
        disabled=not has_analysis,
        style={"marginBottom": "0.5rem"}
    )


def create_summary_table_row(
    project_name: str,
    plate_count: int,
    replicate_count: int,
    mean: float,
    ci_lower: float,
    ci_upper: float,
    ci_width: float,
    prob_positive: float = None,
    prob_meaningful: float = None
) -> html.Tr:
    """
    Create a table row for the summary table.
    """
    cells = [
        html.Td(project_name),
        html.Td(str(plate_count)),
        html.Td(str(replicate_count)),
        html.Td(f"{mean:.3f}"),
        html.Td(f"[{ci_lower:.3f}, {ci_upper:.3f}]"),
        html.Td(f"{ci_width:.3f}"),
    ]

    if prob_positive is not None:
        cells.append(html.Td(f"{prob_positive:.1%}"))
    if prob_meaningful is not None:
        cells.append(html.Td(f"{prob_meaningful:.1%}"))

    return html.Tr(cells)


def create_summary_table(
    projects: list,
    show_bayesian: bool = True
) -> dmc.Table:
    """
    Create the full summary table.

    Args:
        projects: List of project data dicts
        show_bayesian: Whether to show Bayesian probability columns
    """
    if not projects:
        return dmc.Text(
            "No data available",
            c="dimmed",
            ta="center",
            py="xl"
        )

    # Header
    header_cells = [
        html.Th("Project"),
        html.Th("Plates"),
        html.Th("Replicates"),
        html.Th("Mean"),
        html.Th("95% CI"),
        html.Th("CI Width"),
    ]

    if show_bayesian:
        header_cells.extend([
            html.Th("P(FC>1)"),
            html.Th("P(Meaningful)")
        ])

    header = html.Thead(html.Tr(header_cells))

    # Body
    rows = []
    for p in projects:
        cells = [
            html.Td(p.get("project_name", "")),
            html.Td(str(p.get("plate_count", 0))),
            html.Td(str(p.get("replicate_count", 0))),
            html.Td(f"{p.get('mean', 0):.3f}"),
            html.Td(f"[{p.get('ci_lower', 0):.3f}, {p.get('ci_upper', 0):.3f}]"),
            html.Td(f"{p.get('ci_width', 0):.3f}"),
        ]

        if show_bayesian:
            prob_pos = p.get("prob_positive")
            prob_mean = p.get("prob_meaningful")
            cells.append(html.Td(f"{prob_pos:.1%}" if prob_pos is not None else "—"))
            cells.append(html.Td(f"{prob_mean:.1%}" if prob_mean is not None else "—"))

        rows.append(html.Tr(cells))

    # Add summary row if multiple projects
    if len(projects) >= 2:
        means = [p.get("mean", 0) for p in projects]
        total_plates = sum(p.get("plate_count", 0) for p in projects)
        total_reps = sum(p.get("replicate_count", 0) for p in projects)
        mean_of_means = sum(means) / len(means)
        range_val = max(means) - min(means)

        summary_cells = [
            html.Td(html.Strong("Summary")),
            html.Td(html.Strong(str(total_plates))),
            html.Td(html.Strong(str(total_reps))),
            html.Td(html.Strong(f"{mean_of_means:.3f}")),
            html.Td(html.Strong(f"range: {range_val:.3f}")),
            html.Td("—"),
        ]

        if show_bayesian:
            summary_cells.extend([html.Td("—"), html.Td("—")])

        rows.append(html.Tr(summary_cells, style={"backgroundColor": "var(--bg-surface)"}))

    body = html.Tbody(rows)

    return dmc.Table(
        children=[header, body],
        striped=True,
        highlightOnHover=True,
        withTableBorder=True,
        withColumnBorders=True
    )
