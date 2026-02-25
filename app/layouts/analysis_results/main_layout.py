"""Main analysis results layout (create_analysis_results_layout)."""
from typing import Optional
import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify

from app.layouts.analysis_results.workflow import create_curve_fitting_workflow


def create_analysis_results_layout(
    project_id: Optional[int] = None,
    analysis_id: Optional[int] = None,
) -> html.Div:
    """
    Create the analysis results layout.

    Args:
        project_id: Optional project ID
        analysis_id: Optional analysis version ID

    Returns:
        Analysis results layout
    """
    return html.Div([
        # Stores
        dcc.Store(id="analysis-project-store", data=project_id),
        dcc.Store(id="analysis-version-store", data=analysis_id),
        dcc.Store(id="analysis-results-store", data=None),
        dcc.Store(id="analysis-threshold-store", data=1.5),  # Default FC threshold
        dcc.Store(id="fitting-selected-plates-store", data=[]),  # Selected plate IDs
        dcc.Store(id="fitting-results-store", data=None),  # Fitting task results

        # Stores and intervals (invisible components, no wrapper needed)
        dcc.Store(id="fitting-start-btn-clicks", data=0),
        dcc.Store(id="fitting-continue-fc-clicks", data=0),
        dcc.Store(id="fc-back-clicks", data=0),
        dcc.Store(id="fc-compute-clicks", data=0),
        dcc.Store(id="fitting-open-browser-clicks", data=0),
        dcc.Store(id="fc-run-analysis-clicks", data=0),
        dcc.Store(id="fc-publish-clicks", data=0),
        dcc.Store(id="fc-unpublish-clicks", data=0),
        dcc.Store(id="fitting-selected-wells-store", data=[]),  # Selected well IDs for curve viewer
        dcc.Store(id="fitting-task-id-store", data=None),
        dcc.Interval(id="fitting-progress-interval", interval=2000, disabled=True),
        # Analysis (MCMC) task tracking
        dcc.Store(id="analysis-task-id-store", data=None),
        dcc.Interval(id="analysis-progress-interval", interval=3000, disabled=True),
        # Step 1 value stores (to persist across step changes)
        dcc.Store(id="fitting-model-select-store", data="delayed_exponential"),
        dcc.Store(id="fitting-force-refit-store", data=False),
        dcc.Store(id="fitting-preselect-plates-store", data=[]),  # Pre-select plates from curve browser
        # Explore previous fits button stores
        dcc.Store(id="explore-view-fits-clicks", data=0),
        dcc.Store(id="explore-view-fc-clicks", data=0),
        dcc.Store(id="explore-curve-browser-clicks", data=0),
        dcc.Store(id="explore-selected-plates-store", data=[]),
        # R\u00b2 threshold filtering stores
        dcc.Store(id="r2-threshold-store", data=0.80),
        dcc.Store(id="r2-apply-threshold-clicks", data=0),
        dcc.Store(id="r2-include-all-clicks", data=0),

        # Header
        dmc.Group([
            dmc.Title("Analysis Results", order=2),
            dmc.Group([
                dmc.Badge(
                    id="analysis-status-badge",
                    children="No Analysis",
                    color="gray",
                    size="lg",
                ),
                dmc.Badge(
                    id="analysis-scope-badge",
                    children="Full",
                    color="green",
                    size="lg",
                    variant="outline",
                ),
            ]),
        ], justify="space-between", mb="md"),

        # =================================================================
        # Tabbed layout for Analysis page
        # =================================================================
        dmc.Tabs(
            id="analysis-page-tabs",
            value="curve-fitting",
            children=[
                dmc.TabsList([
                    dmc.TabsTab("Curve Fitting", value="curve-fitting",
                        leftSection=DashIconify(icon="mdi:chart-bell-curve", width=16)),
                    dmc.TabsTab("Results", value="results",
                        leftSection=DashIconify(icon="mdi:table-large", width=16)),
                    dmc.TabsTab("Diagnostics", value="diagnostics",
                        leftSection=DashIconify(icon="mdi:stethoscope", width=16)),
                ], mb="md"),

                # =============================================================
                # Tab 1: Curve Fitting
                # =============================================================
                dmc.TabsPanel([
                    # Phase 4: Curve Fitting Workflow (Collapsible)
                    dmc.Accordion([
                        dmc.AccordionItem([
                            dmc.AccordionControl(
                                dmc.Group([
                                    DashIconify(icon="mdi:chart-bell-curve-cumulative", width=20),
                                    "Curve Fitting Workflow",
                                    dmc.Badge(
                                        id="fitting-accordion-badge",
                                        children="Step 1: Select Plates",
                                        color="blue",
                                        size="sm",
                                        variant="light",
                                        ml="auto",
                                    ),
                                ], gap="sm"),
                            ),
                            dmc.AccordionPanel([
                                create_curve_fitting_workflow(project_id),
                            ]),
                        ], value="curve-fitting"),
                    ], value="curve-fitting", mb="md"),

                    # Explore Previous Fits (view existing results without workflow)
                    dmc.Accordion([
                        dmc.AccordionItem([
                            dmc.AccordionControl(
                                dmc.Group([
                                    DashIconify(icon="mdi:history", width=20),
                                    "Explore Previous Fits",
                                    dmc.Badge(
                                        id="previous-fits-badge",
                                        children="Loading...",
                                        color="gray",
                                        size="sm",
                                        variant="light",
                                        ml="auto",
                                    ),
                                ], gap="sm"),
                            ),
                            dmc.AccordionPanel([
                                html.Div(id="previous-fits-content", children=[
                                    dmc.Text("Loading previous fits...", c="dimmed", ta="center"),
                                ]),
                            ]),
                        ], value="previous-fits"),
                    ], mb="md"),
                ], value="curve-fitting"),

                # =============================================================
                # Tab 2: Results
                # =============================================================
                dmc.TabsPanel([
                    # Hierarchical Analysis Results
                    dmc.Divider(
                        label=dmc.Group([
                            DashIconify(icon="mdi:chart-areaspline", width=20),
                            "Hierarchical Analysis Results",
                        ], gap="xs"),
                        labelPosition="center",
                        my="lg",
                    ),

                    # Analysis selector and controls
        dmc.Paper([
            dmc.Grid([
                dmc.GridCol([
                    dmc.Select(
                        id="analysis-version-select",
                        label="Analysis Version",
                        placeholder="Select analysis",
                        data=[],
                        searchable=True,
                    )
                ], span=3),
                dmc.GridCol([
                    dmc.Select(
                        id="analysis-construct-filter",
                        label="Construct",
                        placeholder="All constructs",
                        data=[],
                        clearable=True,
                        searchable=True,
                    )
                ], span=2),
                dmc.GridCol([
                    dmc.Select(
                        id="analysis-parameter-select",
                        label="Parameter",
                        data=[
                            {"value": "log_fc_fmax", "label": "F_max Fold Change"},
                            {"value": "log_fc_kobs", "label": "k_obs Fold Change"},
                            {"value": "delta_tlag", "label": "t_lag Difference"},
                        ],
                        value="log_fc_fmax",
                    )
                ], span=2),
                dmc.GridCol([
                    dmc.Text("Analysis Method", size="sm", fw=500, mb=4),
                    dmc.SegmentedControl(
                        id="analysis-method-select",
                        data=[
                            {"value": "bayesian", "label": "Bayesian"},
                            {"value": "frequentist", "label": "Frequentist"},
                            {"value": "comparison", "label": "Compare"},
                        ],
                        value="bayesian",
                        fullWidth=True,
                        style={"minWidth": "360px"},
                    ),
                ], span=3),
                dmc.GridCol([
                    dmc.Button(
                        "Run New Analysis",
                        id="analysis-run-btn",
                        leftSection=DashIconify(icon="mdi:play"),
                        variant="light",
                        mt="xl",
                    )
                ], span=2, style={"display": "flex", "alignItems": "flex-end"}),
            ]),
        ], p="md", mb="md", withBorder=True),

        # Method comparison warning/info panel (hidden by default)
        html.Div(id="analysis-method-info-panel", children=[]),

        # Main content
        dmc.Grid([
            # Left: Results Table
            dmc.GridCol([
                dmc.Paper([
                    dmc.Group([
                        dmc.Text(id="analysis-table-title", children="Posterior Summaries", fw=500),
                        dmc.ActionIcon(
                            DashIconify(icon="mdi:download"),
                            id="analysis-export-btn",
                            variant="subtle",
                        ),
                    ], justify="space-between", mb="sm"),
                    html.Div(id="analysis-posterior-table"),
                ], p="md", withBorder=True, style={"minHeight": "400px"}),
            ], span=7),

            # Right: Summary panels
            dmc.GridCol([
                # Probability Calculator (Bayesian only)
                html.Div(id="analysis-probability-panel", children=[
                    dmc.Paper([
                        dmc.Text("Effect Probability", fw=500, mb="sm"),
                        dmc.Stack([
                            dmc.NumberInput(
                                id="analysis-threshold-input",
                                label="Fold change threshold",
                                value=1.5,
                                min=1.0,
                                max=10.0,
                                step=0.1,
                                decimalScale=2,
                            ),
                            html.Div(id="analysis-probability-display"),
                        ], gap="sm"),
                    ], p="md", mb="md", withBorder=True),
                ]),

                # Variance Decomposition
                dmc.Paper([
                    dmc.Text("Variance Decomposition", fw=500, mb="sm"),
                    dcc.Graph(
                        id="analysis-variance-pie",
                        config={"displayModeBar": False},
                        style={"height": "200px"},
                    ),
                ], p="md", mb="md", withBorder=True),

                # Diagnostics Panel (content changes based on method)
                dmc.Paper([
                    dmc.Text(id="analysis-diagnostics-title", children="MCMC Diagnostics", fw=500, mb="sm"),
                    html.Div(id="analysis-diagnostics-panel"),
                ], p="md", withBorder=True),
            ], span=5),
        ]),

        # Correlations panel (collapsible)
        dmc.Accordion([
            dmc.AccordionItem([
                dmc.AccordionControl("Parameter Correlations"),
                dmc.AccordionPanel([
                    html.Div(id="analysis-correlations-panel"),
                ]),
            ], value="correlations"),
        ], mb="md"),

        # Forest Plot (interactive visualization of all construct effects)
        dmc.Paper([
            dmc.Group([
                dmc.Text("Forest Plot", fw=500),
                dmc.Group([
                    dmc.Select(
                        id="forest-sort-select",
                        data=[
                            {"value": "effect_size", "label": "Sort by Effect Size"},
                            {"value": "alphabetical", "label": "Sort Alphabetically"},
                            {"value": "precision", "label": "Sort by Precision"},
                        ],
                        value="effect_size",
                        size="xs",
                        w=180,
                    ),
                    dmc.Switch(
                        id="forest-group-by-family",
                        label="Group by Family",
                        size="sm",
                    ),
                ], gap="md"),
            ], justify="space-between", mb="sm"),
            dcc.Graph(
                id="analysis-forest-plot",
                config={"displayModeBar": True, "displaylogo": False},
                style={"minHeight": "400px"},
            ),
        ], p="md", mb="md", withBorder=True),
                ], value="results"),

                # =============================================================
                # Tab 3: Diagnostics
                # =============================================================
                dmc.TabsPanel([
        # Statistical Diagnostics panel (Sprint 7)
        dmc.Accordion([
            dmc.AccordionItem([
                dmc.AccordionControl("Statistical Diagnostics"),
                dmc.AccordionPanel([
                    # Family selector for per-family diagnostics
                    dmc.Group([
                        dmc.Text("Family", size="sm", fw=500),
                        dmc.Select(
                            id="analysis-diagnostics-family-select",
                            placeholder="All families (pooled)",
                            data=[],
                            clearable=True,
                            searchable=True,
                            style={"width": "250px"},
                        ),
                    ], justify="flex-start", gap="md", mb="md"),

                    # Dynamic warnings panel
                    html.Div(id="analysis-diagnostics-warnings", className="mb-md"),

                    dmc.Grid([
                        # Assumption Tests
                        dmc.GridCol([
                            dmc.Paper([
                                dmc.Text("Assumption Tests", fw=500, mb="sm"),
                                html.Div(id="analysis-assumption-tests"),
                            ], p="md", withBorder=True),
                        ], span=4),

                        # Q-Q Plot
                        dmc.GridCol([
                            dmc.Paper([
                                dmc.Text(
                                    id="analysis-qq-title",
                                    children="Q-Q Plot",
                                    fw=500,
                                ),
                                html.Div(
                                    id="analysis-qq-description",
                                    children=dmc.Text(
                                        "Checks whether the hierarchical model's normality "
                                        "assumption holds. Points following the diagonal line "
                                        "indicate the data is consistent with a normal distribution.",
                                        size="xs", c="dimmed",
                                    ),
                                ),
                                dcc.Graph(
                                    id="analysis-qq-plot",
                                    config={"displayModeBar": False},
                                    style={"height": "300px"},
                                ),
                            ], p="md", withBorder=True),
                        ], span=4),

                        # Effect Sizes
                        dmc.GridCol([
                            dmc.Paper([
                                dmc.Text("Effect Sizes", fw=500, mb="sm"),
                                html.Div(id="analysis-effect-sizes"),
                            ], p="md", withBorder=True),
                        ], span=4),
                    ], mb="md"),

                    # Multiple Comparison Corrections
                    dmc.Paper([
                        dmc.Group([
                            dmc.Text("Multiple Comparison Corrections", fw=500),
                            dmc.Select(
                                id="analysis-correction-method",
                                data=[
                                    {"value": "none", "label": "None (uncorrected)"},
                                    {"value": "bonferroni", "label": "Bonferroni (FWER control)"},
                                    {"value": "holm", "label": "Holm-Bonferroni (FWER control)"},
                                    {"value": "fdr", "label": "Benjamini-Hochberg (FDR control)"},
                                ],
                                value="fdr",
                                style={"width": "250px"},
                            ),
                        ], justify="space-between", mb="md"),
                        html.Div(id="analysis-corrected-pvalues"),
                    ], p="md", withBorder=True),
                ]),
            ], value="diagnostics"),
        ], mb="md"),

        # Cross-Family Comparisons panel (Sprint 3 - F13.14)
        dmc.Accordion([
            dmc.AccordionItem([
                dmc.AccordionControl(
                    dmc.Group([
                        "Cross-Family Comparisons",
                        dmc.Badge("Exploratory", color="orange", size="sm", variant="light"),
                    ], gap="sm"),
                ),
                dmc.AccordionPanel([
                    # Exploratory warning banner
                    dmc.Alert(
                        title="Exploratory Comparisons",
                        children=[
                            "Cross-family comparisons go through the unregulated reference and have ",
                            dmc.Text("limited biological interpretability", fw=700, span=True),
                            ". Use VIF (Variance Inflation Factor) to assess precision degradation: ",
                            dmc.Text("VIF=2", fw=500, span=True, c="orange"),
                            " for mutant vs unregulated (two-hop), ",
                            dmc.Text("VIF=4", fw=500, span=True, c="red"),
                            " for cross-family mutant comparisons (four-hop).",
                        ],
                        color="orange",
                        icon=DashIconify(icon="mdi:alert"),
                        mb="md",
                    ),

                    # Pre-computed comparisons
                    dmc.Paper([
                        dmc.Text("Pre-computed Comparisons (Mutants vs Unregulated)", fw=500, mb="sm"),
                        dmc.Text(
                            "Two-hop comparisons through wildtype \u2192 unregulated path",
                            size="sm", c="dimmed", mb="md"
                        ),
                        html.Div(id="cross-family-precomputed-table"),
                    ], p="md", mb="md", withBorder=True),

                    # Cross-family mutant comparisons
                    dmc.Paper([
                        dmc.Text("Cross-Family Mutant Comparisons", fw=500, mb="sm"),
                        dmc.Text(
                            "Four-hop comparisons: Mutant\u2081 \u2192 WT\u2081 \u2192 Unregulated \u2192 WT\u2082 \u2192 Mutant\u2082",
                            size="sm", c="dimmed", mb="md"
                        ),
                        html.Div(id="cross-family-mutant-table"),
                    ], p="md", mb="md", withBorder=True),

                    # On-demand custom comparison
                    dmc.Paper([
                        dmc.Text("Request Custom Comparison", fw=500, mb="sm"),
                        dmc.Text(
                            "Compute a custom comparison between any two constructs",
                            size="sm", c="dimmed", mb="md"
                        ),
                        dmc.Grid([
                            dmc.GridCol([
                                dmc.Select(
                                    id="cross-family-construct1-select",
                                    label="First Construct",
                                    placeholder="Select construct",
                                    data=[],
                                    searchable=True,
                                )
                            ], span=4),
                            dmc.GridCol([
                                dmc.Center([
                                    dmc.Text("vs", fw=500, c="dimmed", mt="xl"),
                                ]),
                            ], span=1),
                            dmc.GridCol([
                                dmc.Select(
                                    id="cross-family-construct2-select",
                                    label="Second Construct",
                                    placeholder="Select construct",
                                    data=[],
                                    searchable=True,
                                )
                            ], span=4),
                            dmc.GridCol([
                                dmc.Button(
                                    "Compute",
                                    id="cross-family-compute-btn",
                                    leftSection=DashIconify(icon="mdi:calculator"),
                                    variant="light",
                                    mt="xl",
                                ),
                            ], span=3, style={"display": "flex", "alignItems": "flex-end"}),
                        ], mb="md"),
                        dmc.Alert(
                            children="Custom comparisons are computed fresh from current data and not cached.",
                            color="blue",
                            icon=DashIconify(icon="mdi:information"),
                            variant="light",
                            mb="md",
                        ),
                        html.Div(id="cross-family-custom-result"),
                    ], p="md", withBorder=True),
                ]),
            ], value="cross-family"),
        ], mb="md"),
                ], value="diagnostics"),
            ],
        ),

        # Run analysis modal
        dmc.Modal(
            id="analysis-run-modal",
            title="Run Bayesian Analysis",
            centered=True,
            size="lg",
            children=[
                dmc.Stack([
                    dmc.Alert(
                        title="Long-Running Task",
                        children="Bayesian analysis typically takes 15-60 minutes depending on data size. "
                                 "You can close this browser and the analysis will continue in the background.",
                        color="blue",
                        icon=DashIconify(icon="mdi:information"),
                    ),
                    dmc.TextInput(
                        id="analysis-checkpoint-name",
                        label="Checkpoint Name",
                        placeholder="e.g., Initial analysis",
                        required=True,
                    ),
                    dmc.Textarea(
                        id="analysis-checkpoint-description",
                        label="Description (optional)",
                        placeholder="Notes about this analysis run...",
                        minRows=2,
                    ),
                    dmc.Checkbox(
                        id="analysis-include-frequentist",
                        label="Include frequentist comparison",
                        checked=True,
                    ),
                    dmc.Group([
                        dmc.Button(
                            "Cancel",
                            id="analysis-run-cancel",
                            variant="outline",
                        ),
                        dmc.Button(
                            "Start Analysis",
                            id="analysis-run-confirm",
                            color="blue",
                            leftSection=DashIconify(icon="mdi:play"),
                        ),
                    ], justify="flex-end", mt="md"),
                ], gap="md"),
            ],
        ),

        # Progress modal
        dmc.Modal(
            id="analysis-progress-modal",
            title="Analysis in Progress",
            centered=True,
            closeOnClickOutside=False,
            closeOnEscape=False,
            children=[
                dmc.Stack([
                    dmc.Progress(
                        id="analysis-progress-bar",
                        value=0,
                        size="xl",
                        animated=True,
                    ),
                    dmc.Text(
                        id="analysis-progress-text",
                        ta="center",
                        c="dimmed",
                    ),
                    dmc.Text(
                        "You can close this dialog. Analysis will continue in background.",
                        size="sm",
                        ta="center",
                        c="dimmed",
                    ),
                    dmc.Button(
                        "Close",
                        id="analysis-progress-close",
                        variant="subtle",
                        fullWidth=True,
                    ),
                ], gap="md"),
            ],
        ),
    ])
