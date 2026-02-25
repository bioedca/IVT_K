"""
IVT Reaction Calculator layout - Smart Experiment Planner UI.

Phase 2.5.34: Calculator UI (F4.1-F4.34)

Provides:
- Construct recommendations panel with scoring
- Construct selection with impact preview
- Replicate assignment with power-based suggestions
- Volume calculations display
- Protocol preview and export
- First Experiment Wizard for new projects
"""
from dash import html, dcc
import dash_mantine_components as dmc
from dash_iconify import DashIconify


def create_calculator_layout(project_id: int = None):
    """
    Create the IVT Reaction Calculator layout.

    Args:
        project_id: Project ID for context
    """
    return dmc.Container(
        children=[
            # Stores for state management
            dcc.Store(id="calc-project-store", data={"project_id": project_id}),
            dcc.Store(id="calc-selected-constructs", data=[]),
            dcc.Store(id="calc-plan-store", data=None),
            dcc.Store(id="calc-mode-store", data=None),
            dcc.Store(id="calc-viewed-protocol-id", data=None),
            dcc.Download(id="export-plan-download"),

            # Header
            html.Div(
                children=[
                    dmc.Group(
                        children=[

                            html.Div(
                                children=[
                                    dmc.Title(
                                        "IVT Reaction Calculator",
                                        order=2
                                    ),
                                    dmc.Text(
                                        "Smart Experiment Planner",
                                        size="sm",
                                        c="dimmed"
                                    )
                                ]
                            ),
                            dmc.Select(
                                id="calc-protocol-history-select",
                                placeholder="View published protocols...",
                                data=[],
                                searchable=True,
                                clearable=True,
                                w=280,
                                size="sm",
                                leftSection=DashIconify(icon="mdi:history", width=16),
                                style={"display": "none"},
                            ),
                        ],
                        gap="md"
                    ),
                    dmc.Group(
                        children=[
                            dmc.Button(
                                "Reset",
                                id="calc-reset-btn",
                                variant="subtle",
                                color="gray"
                            ),
                            dmc.Button(
                                "Export JSON",
                                id="calc-export-btn",
                                variant="outline",
                                disabled=True,
                                leftSection=dmc.Text("⬇️", size="sm"),
                            ),
                            dmc.Button(
                                "Publish Protocol",
                                id="calc-publish-btn",
                                variant="light",
                                color="green",
                                disabled=True,
                                leftSection=dmc.Text("📋", size="sm"),
                            ),
                            dmc.Button(
                                "Generate Protocol",
                                id="calc-generate-btn",
                                variant="filled",
                                disabled=True
                            )
                        ],
                        gap="sm"
                    )
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "marginBottom": "1.5rem"
                }
            ),

            # Publish Protocol Modal
            dmc.Modal(
                id="calc-publish-modal",
                title="Publish Protocol to Database",
                centered=True,
                children=[
                    dmc.Text(
                        "Save this protocol to the project database. The protocol text "
                        "will be stored for audit trail purposes.",
                        size="sm",
                        c="dimmed",
                        style={"marginBottom": "1rem"}
                    ),
                    dmc.TextInput(
                        id="calc-publish-name",
                        label="Protocol Name",
                        placeholder="e.g., Experiment 2024-01-30",
                        required=True,
                        style={"marginBottom": "1rem"}
                    ),
                    dmc.Textarea(
                        id="calc-publish-notes",
                        label="Notes (optional)",
                        placeholder="Any additional notes about this experiment...",
                        autosize=True,
                        minRows=2,
                        style={"marginBottom": "1rem"}
                    ),
                    html.Div(id="calc-publish-feedback"),
                    dmc.Group(
                        children=[
                            dmc.Button(
                                "Cancel",
                                id="calc-publish-cancel-btn",
                                variant="subtle"
                            ),
                            dmc.Button(
                                "Publish",
                                id="calc-publish-confirm-btn",
                                color="green"
                            )
                        ],
                        justify="flex-end",
                        style={"marginTop": "1rem"}
                    )
                ],
                opened=False
            ),

            # Protocol View Modal
            dmc.Modal(
                id="calc-protocol-view-modal",
                title="Published Protocol",
                centered=True,
                size="lg",
                children=[
                    html.Div(id="calc-protocol-view-content"),
                    dmc.Divider(my="md"),
                    dmc.Group(
                        children=[
                            dmc.Button(
                                "Export JSON",
                                id="calc-history-export-btn",
                                variant="outline",
                                size="sm",
                                leftSection=DashIconify(icon="mdi:code-json", width=16),
                            ),
                            dmc.Button(
                                "Print / Save PDF",
                                id="calc-history-print-btn",
                                variant="light",
                                size="sm",
                                leftSection=DashIconify(icon="mdi:printer", width=16),
                            ),
                        ],
                        justify="flex-end",
                    ),
                    # Hidden printable protocol container for history view
                    html.Div(
                        id="calc-history-printable-protocol",
                        className="printable-protocol",
                        style={"display": "none"},
                    ),
                ],
                opened=False,
            ),
            dcc.Download(id="calc-history-export-download"),

            # Notification container
            html.Div(id="calc-notification-container"),

            # First Experiment Wizard (shown when no data)
            html.Div(
                id="calc-first-experiment-wizard",
                children=[_create_first_experiment_wizard()],
                style={"display": "none"}
            ),

            # Main calculator content (hidden when wizard active)
            html.Div(
                id="calc-main-content",
                children=[
                    dmc.Accordion(
                        children=[
                            # Section 1: Construct Selection
                            dmc.AccordionItem(
                                children=[
                                    dmc.AccordionControl(
                                        "Construct Selection",
                                        icon=dmc.ThemeIcon(
                                            DashIconify(icon="mdi:dna", width=18),
                                            variant="light",
                                            size="sm",
                                            radius="xl",
                                        ),
                                    ),
                                    dmc.AccordionPanel([
                                        _create_recommendations_panel(),
                                        _create_selection_panel(),
                                    ]),
                                ],
                                value="construct-selection",
                            ),
                            # Section 2: Reaction Setup
                            dmc.AccordionItem(
                                children=[
                                    dmc.AccordionControl(
                                        "Reaction Setup",
                                        icon=dmc.ThemeIcon(
                                            DashIconify(icon="mdi:test-tube", width=18),
                                            variant="light",
                                            size="sm",
                                            radius="xl",
                                        ),
                                    ),
                                    dmc.AccordionPanel([
                                        _create_impact_preview_panel(),
                                        _create_negative_controls_panel(),
                                        _create_ligand_controls_panel(),
                                        _create_replicate_settings_panel(),
                                    ]),
                                ],
                                value="reaction-setup",
                            ),
                        ],
                        value=["construct-selection", "reaction-setup"],
                        multiple=True,
                        variant="separated",
                        mb="lg",
                    ),

                    # Volume calculation results (shown after generate)
                    html.Div(
                        id="calc-results-section",
                        children=[
                            _create_volume_results_panel(),
                            _create_protocol_preview_panel(),
                        ],
                        style={"display": "none"}
                    )
                ]
            ),

            # Export modal
            _create_export_modal(),
        ],
        size="xl",
        style={"paddingTop": "1rem", "paddingBottom": "2rem"}
    )


def _create_first_experiment_wizard():
    """Create the First Experiment Wizard for new projects."""
    return dmc.Paper(
        children=[
            dmc.Alert(
                title="First Experiment Wizard",
                color="blue",
                children=[
                    dmc.Text([
                        "Welcome! Before testing mutants, we recommend establishing ",
                        "baseline data with your wild-type and reporter-only constructs."
                    ]),
                ],
                mb="lg"
            ),

            dmc.Title("Recommended First Experiment", order=4, mb="md"),

            # Constructs section
            dmc.Paper(
                children=[
                    dmc.Text("DNA Templates", fw=500, mb="sm"),
                    html.Div(id="wizard-templates-list"),
                    dmc.Space(h="md"),
                    dmc.Text("Controls", fw=500, mb="sm"),
                    html.Div(id="wizard-controls-list"),
                    dmc.Divider(my="md"),
                    html.Div(
                        id="wizard-total-wells",
                        children=[
                            dmc.Text("Total wells: ", span=True),
                            dmc.Text("--", span=True, fw=600)
                        ]
                    )
                ],
                p="md",
                withBorder=True,
                radius="md",
                mb="lg"
            ),

            # Why start with WT
            dmc.Accordion(
                children=[
                    dmc.AccordionItem(
                        value="why",
                        children=[
                            dmc.AccordionControl("Why start with WT?"),
                            dmc.AccordionPanel(
                                children=[
                                    dmc.List(
                                        children=[
                                            dmc.ListItem("Establishes baseline fold change (WT vs reporter-only)"),
                                            dmc.ListItem("Validates your experimental setup and signal quality"),
                                            dmc.ListItem("Provides reference for interpreting mutant effects"),
                                            dmc.ListItem("Generates variance estimates for power analysis"),
                                        ]
                                    )
                                ]
                            )
                        ]
                    )
                ],
                mb="lg"
            ),

            # Actions
            dmc.Group(
                children=[
                    dmc.Checkbox(
                        id="wizard-test-mutants-checkbox",
                        label="I want to test mutants in my first experiment (advanced)",
                        size="sm"
                    ),
                ],
                mb="md"
            ),

            dmc.Group(
                children=[
                    dmc.Button(
                        "Continue with WT Setup",
                        id="wizard-continue-btn",
                        variant="filled"
                    ),
                    dmc.Button(
                        "Skip Wizard",
                        id="wizard-skip-btn",
                        variant="subtle",
                        color="gray"
                    )
                ],
                justify="flex-end"
            )
        ],
        p="xl",
        withBorder=True,
        radius="md"
    )


def _create_recommendations_panel():
    """Create the construct recommendations panel."""
    return dmc.Paper(
        children=[
            dmc.Group(
                children=[
                    dmc.Title("Recommended Next Constructs", order=4),
                    dmc.ActionIcon(
                        dmc.Text("?", size="sm"),
                        id="rec-help-btn",
                        variant="subtle",
                        size="sm",
                        radius="xl"
                    )
                ],
                justify="space-between",
                mb="md"
            ),

            # Recommendations list
            html.Div(
                id="rec-list-container",
                children=[
                    dmc.Text(
                        "Loading recommendations...",
                        c="dimmed",
                        ta="center",
                        py="xl"
                    )
                ]
            )
        ],
        p="md",
        withBorder=True,
        radius="md",
        mb="lg"
    )


def _create_selection_panel():
    """Create the construct selection panel."""
    return dmc.Paper(
        children=[
            dmc.Title("Selected Constructs", order=4, mb="md"),

            # Template count indicator
            html.Div(
                id="template-count-indicator",
                children=[
                    dmc.Progress(
                        value=0,
                        id="template-progress",
                        size="lg",
                        radius="md",
                        mb="xs"
                    ),
                    dmc.Text(
                        "0/4 templates",
                        id="template-count-text",
                        size="sm",
                        c="dimmed"
                    )
                ],
                style={"marginBottom": "1rem"}
            ),

            # Selected constructs list
            html.Div(
                id="selected-constructs-list",
                children=[
                    dmc.Text(
                        "No constructs selected",
                        c="dimmed",
                        ta="center",
                        py="lg"
                    )
                ]
            ),

            # Auto-added anchors
            dmc.Divider(my="md", label="Auto-added Anchors", labelPosition="center"),
            html.Div(
                id="auto-added-anchors-list",
                children=[
                    dmc.Text(
                        "Anchors will appear here",
                        c="dimmed",
                        size="sm",
                        ta="center",
                        py="sm"
                    )
                ]
            )
        ],
        p="md",
        withBorder=True,
        radius="md"
    )


def _create_impact_preview_panel():
    """Create the impact preview panel."""
    return dmc.Paper(
        children=[
            dmc.Title("Impact Preview", order=4, mb="md"),

            html.Div(
                id="impact-preview-content",
                children=[
                    # Stats grid
                    dmc.SimpleGrid(
                        cols=2,
                        spacing="md",
                        children=[
                            _create_impact_stat(
                                "Constructs covered",
                                "impact-constructs",
                                "--/--"
                            ),
                            _create_impact_stat(
                                "Est. plates to target",
                                "impact-plates",
                                "--"
                            ),
                            _create_impact_stat(
                                "Precision improvement",
                                "impact-precision",
                                "--%"
                            ),
                            _create_impact_stat(
                                "Wells needed",
                                "impact-wells",
                                "--"
                            ),
                        ],
                        mb="md"
                    ),

                    # Per-construct impact (collapsed by default)
                    dmc.Accordion(
                        children=[
                            dmc.AccordionItem(
                                value="details",
                                children=[
                                    dmc.AccordionControl("Per-construct impact"),
                                    dmc.AccordionPanel(
                                        children=[
                                            html.Div(id="per-construct-impact-list")
                                        ]
                                    )
                                ]
                            )
                        ]
                    )
                ]
            )
        ],
        p="md",
        withBorder=True,
        radius="md",
        mb="lg"
    )


def _create_impact_stat(label: str, stat_id: str, default: str):
    """Create a single impact statistic display."""
    return html.Div(
        children=[
            dmc.Text(label, size="xs", c="dimmed"),
            dmc.Text(default, id=stat_id, size="lg", fw=600)
        ]
    )


def _create_negative_controls_panel():
    """Create the negative controls configuration panel."""
    return dmc.Paper(
        children=[
            dmc.Title("Negative Controls", order=4, mb="md"),

            # -Template (always required)
            dmc.Group(
                children=[
                    dmc.Checkbox(
                        id="neg-template-checkbox",
                        checked=True,
                        disabled=True,
                        label="-Template controls"
                    ),
                    dmc.Badge("REQUIRED", color="blue", size="sm"),
                    dmc.NumberInput(
                        id="neg-template-count",
                        value=3,
                        min=2,
                        max=6,
                        step=1,
                        w=80,
                        size="xs"
                    )
                ],
                justify="space-between",
                mb="sm"
            ),
            dmc.Text(
                "Provides plate-specific baseline",
                size="xs",
                c="dimmed",
                mb="md"
            ),

            # -DFHBI (smart recommendation)
            dmc.Group(
                children=[
                    dmc.Checkbox(
                        id="neg-dfhbi-checkbox",
                        checked=False,
                        label="-DFHBI controls"
                    ),
                    html.Div(
                        id="dfhbi-recommendation-badge",
                        children=[
                            dmc.Badge("Optional", color="gray", size="sm")
                        ]
                    ),
                    dmc.NumberInput(
                        id="neg-dfhbi-count",
                        value=2,
                        min=2,
                        max=4,
                        step=1,
                        w=80,
                        size="xs",
                        disabled=True
                    )
                ],
                justify="space-between",
                mb="xs"
            ),

            # DFHBI recommendation reason
            dmc.Accordion(
                children=[
                    dmc.AccordionItem(
                        value="dfhbi-why",
                        children=[
                            dmc.AccordionControl(
                                "Why optional?",
                                id="dfhbi-why-control"
                            ),
                            dmc.AccordionPanel(
                                children=[
                                    dmc.Text(
                                        "The -DFHBI control measures autofluorescence from reaction "
                                        "components in the absence of the dye, answering the question "
                                        "\"is there unexpected signal not coming from aptamer-dye binding?\" "
                                        "This is a diagnostic for assay validation and troubleshooting, "
                                        "not a correction factor used in routine analysis.",
                                        size="sm",
                                        mb="sm"
                                    ),
                                    dmc.Text(
                                        "Once you have confirmed across several sessions that your reaction "
                                        "components have negligible autofluorescence, repeating this measurement "
                                        "provides diminishing returns.",
                                        size="sm",
                                        mb="sm"
                                    ),
                                    dmc.Text(
                                        "The -Template control, by contrast, is required on every plate because "
                                        "it measures the complete reaction background that varies with each "
                                        "master mix preparation and is directly subtracted from sample signals.",
                                        size="sm",
                                        mb="sm"
                                    ),
                                    dmc.Text(
                                        "The software recommends -DFHBI controls when session history lacks "
                                        "recent measurements or when previous controls showed anomalies, but "
                                        "does not require them because they do not participate in the core "
                                        "baseline correction pipeline.",
                                        size="sm",
                                        c="dimmed"
                                    ),
                                    dmc.Divider(my="sm"),
                                    dmc.Text("Current recommendation:", size="xs", fw=500),
                                    html.Div(
                                        id="dfhbi-recommendation-reason",
                                        children=[
                                            dmc.Text(
                                                "Select a project to see personalized recommendation.",
                                                size="sm",
                                                c="dimmed",
                                                fs="italic"
                                            )
                                        ]
                                    )
                                ]
                            )
                        ]
                    )
                ],
                variant="contained"
            )
        ],
        p="md",
        withBorder=True,
        radius="md",
        mb="lg"
    )


def _create_ligand_controls_panel():
    """Create the ligand conditions configuration panel."""
    return dmc.Paper(
        children=[
            dmc.Group(
                children=[
                    dmc.Title("+/- Ligand Conditions", order=4),
                    dmc.Badge(
                        "2x wells",
                        id="ligand-well-badge",
                        color="orange",
                        size="sm",
                        style={"display": "none"},
                    ),
                ],
                justify="space-between",
                mb="md",
            ),

            dmc.Switch(
                id="ligand-enabled-switch",
                label="Enable +/- Ligand conditions",
                checked=False,
                mb="md",
            ),

            html.Div(
                id="ligand-config-div",
                children=[
                    dmc.Group(
                        children=[
                            dmc.Text("Stock concentration:", size="sm"),
                            dmc.NumberInput(
                                id="ligand-stock-input",
                                value=1000.0,
                                min=0.1,
                                step=100,
                                w=120,
                                size="xs",
                                rightSection=dmc.Text("µM", size="xs", c="dimmed"),
                                disabled=True,
                            ),
                        ],
                        justify="space-between",
                        mb="sm",
                    ),
                    dmc.Group(
                        children=[
                            dmc.Text("Final concentration:", size="sm"),
                            dmc.NumberInput(
                                id="ligand-final-input",
                                value=100.0,
                                min=0.1,
                                step=10,
                                w=120,
                                size="xs",
                                rightSection=dmc.Text("µM", size="xs", c="dimmed"),
                                disabled=True,
                            ),
                        ],
                        justify="space-between",
                        mb="sm",
                    ),
                    html.Div(id="ligand-volume-preview"),
                ],
                style={"display": "none"},
            ),

            dmc.Text(
                "Each construct gets +Ligand and -Ligand wells. "
                "Ligand is added to the master mix post-split.",
                size="xs",
                c="dimmed",
            ),
        ],
        p="md",
        withBorder=True,
        radius="md",
        mb="lg",
    )


def _create_replicate_settings_panel():
    """Create the replicate settings panel."""
    return dmc.Paper(
        children=[
            dmc.Title("Replicate Settings", order=4, mb="md"),

            # Reaction Volume Input
            dmc.Group(
                children=[
                    dmc.Text("Reaction Volume:"),
                    dmc.NumberInput(
                        id="reaction-volume-input",
                        value=40.0,
                        min=20.0,
                        max=50.0,
                        step=1.0,
                        w=100,
                        rightSection="µL"
                    )
                ],
                justify="space-between",
                mb="sm"
            ),
            dmc.Text(
                "Constrained by plate format (96-well: 100-250 µL, 384-well: 20-50 µL)",
                size="xs",
                c="dimmed",
                id="volume-constraint-help",
                mb="md"
            ),
            
            dmc.Divider(my="sm"),

            dmc.Group(
                children=[
                    dmc.Text("Replicates per construct:"),
                    dmc.NumberInput(
                        id="replicate-count-input",
                        value=4,
                        min=4,
                        max=12,
                        step=1,
                        w=100
                    )
                ],
                justify="space-between",
                mb="sm"
            ),

            dmc.Text(
                "Minimum 4 replicates required for reliable statistics",
                size="xs",
                c="dimmed",
                mb="md"
            ),

            # Power-based recommendation
            html.Div(
                id="replicate-recommendation",
                children=[
                    dmc.Alert(
                        id="replicate-alert",
                        title="Recommendation",
                        color="blue",
                        children=[
                            dmc.Text(
                                "4 replicates is the standard starting point",
                                size="sm"
                            )
                        ]
                    )
                ]
            )
        ],
        p="md",
        withBorder=True,
        radius="md"
    )


def _create_volume_results_panel():
    """Create the volume calculation results panel."""
    return dmc.Paper(
        children=[
            dmc.Title("Volume Calculations", order=3, mb="md"),

            dmc.Tabs(
                value="master-mix",
                children=[
                    dmc.TabsList(
                        children=[
                            dmc.TabsTab("Master Mix", value="master-mix"),
                            dmc.TabsTab("DNA Additions", value="dna"),
                            dmc.TabsTab("Validation", value="validation"),
                        ]
                    ),

                    dmc.TabsPanel(
                        value="master-mix",
                        children=[
                            html.Div(id="master-mix-table", style={"padding": "1rem"})
                        ]
                    ),

                    dmc.TabsPanel(
                        value="dna",
                        children=[
                            html.Div(id="dna-additions-table", style={"padding": "1rem"})
                        ]
                    ),

                    dmc.TabsPanel(
                        value="validation",
                        children=[
                            html.Div(id="validation-messages", style={"padding": "1rem"})
                        ]
                    )
                ]
            )
        ],
        p="md",
        withBorder=True,
        radius="md",
        mb="lg"
    )


def _create_protocol_preview_panel():
    """Create the protocol preview panel."""
    return dmc.Paper(
        children=[
            dmc.Group(
                children=[
                    dmc.Title("Pipetting Protocol", order=3),
                    dmc.Button(
                        "Print / Save PDF",
                        id="print-protocol-btn",
                        variant="light",
                        size="sm",
                        leftSection=html.I(className="fas fa-print")
                    )
                ],
                justify="space-between",
                mb="md"
            ),

            # Protocol content (screen view)
            html.Div(
                id="protocol-preview-content",
                children=[
                    dmc.Code(
                        id="protocol-text",
                        block=True,
                        style={"whiteSpace": "pre-wrap", "maxHeight": "400px", "overflow": "auto"}
                    )
                ]
            ),
            
            # Printable protocol (hidden on screen, shown in print)
            html.Div(
                id="printable-protocol",
                className="printable-protocol",
                style={"display": "none"}
            )
        ],
        p="md",
        withBorder=True,
        radius="md"
    )


def _create_export_modal():
    """Create the export modal dialog."""
    return dmc.Modal(
        id="export-modal",
        title="Export Protocol",
        opened=False,
        children=[
            dmc.Stack(
                children=[
                    dmc.Text("Choose export format:"),
                    dmc.RadioGroup(
                        id="export-format-radio",
                        value="csv",
                        children=[
                            dmc.Radio("CSV (spreadsheet)", value="csv"),
                            dmc.Radio("PDF (printable)", value="pdf"),
                            dmc.Radio("Text (plain)", value="text"),
                        ]
                    ),
                    dmc.Divider(),
                    dmc.Checkbox(
                        id="export-include-summary",
                        label="Include experiment summary",
                        checked=True
                    ),
                    dmc.Group(
                        children=[
                            dmc.Button(
                                "Cancel",
                                id="export-cancel-btn",
                                variant="subtle"
                            ),
                            dmc.Button(
                                "Download",
                                id="export-download-btn",
                                variant="filled"
                            )
                        ],
                        justify="flex-end",
                        mt="md"
                    )
                ],
                gap="md"
            )
        ]
    )


def create_recommendation_card(
    construct_id: int,
    name: str,
    score: float,
    brief_reason: str,
    detailed_reason: str,
    current_ci: float = None,
    target_ci: float = None,
    replicates_needed: int = None,
    is_selected: bool = False,
    prob_meaningful: float = None,
    is_wildtype: bool = False,
):
    """
    Create a recommendation card component.

    Args:
        construct_id: Construct database ID
        name: Construct name
        score: Recommendation score (0-100, percentage share of remaining need)
        brief_reason: Brief explanation
        detailed_reason: Detailed explanation
        current_ci: Current CI width
        target_ci: Target CI width
        replicates_needed: Additional replicates needed
        is_selected: Whether currently selected
        prob_meaningful: P(|FC| > theta) from Bayesian analysis
        is_wildtype: Whether this is a WT construct (shown as "Required")
    """
    # WT constructs show "Required" blue badge instead of a score
    if is_wildtype:
        badge_text = "Required"
        score_color = "blue"
    elif score <= 0:
        badge_text = "Complete"
        score_color = "gray"
    else:
        badge_text = f"{score:.0f}%"
        if score >= 25:
            score_color = "red"
        elif score >= 10:
            score_color = "yellow"
        else:
            score_color = "green"

    # P(effect) display for expandable details
    if prob_meaningful is not None:
        prob_text = f"{prob_meaningful * 100:.0f}%"
    else:
        prob_text = "N/A"

    return dmc.Paper(
        children=[
            dmc.Group(
                children=[
                    dmc.Checkbox(
                        id={"type": "rec-checkbox", "id": construct_id},
                        checked=is_selected,
                        size="md"
                    ),
                    html.Div(
                        children=[
                            dmc.Group(
                                children=[
                                    dmc.Text(name, fw=500),
                                    dmc.Badge(
                                        badge_text,
                                        color=score_color,
                                        size="sm"
                                    )
                                ],
                                gap="sm"
                            ),
                            dmc.Text(brief_reason, size="sm", c="dimmed")
                        ],
                        style={"flex": 1}
                    ),
                    dmc.ActionIcon(
                        dmc.Text("v", size="xs"),
                        id={"type": "rec-expand", "id": construct_id},
                        variant="subtle",
                        size="sm"
                    )
                ],
                gap="md",
                wrap="nowrap"
            ),

            # Expandable details
            dmc.Collapse(
                id={"type": "rec-details", "id": construct_id},
                opened=False,
                children=[
                    dmc.Divider(my="sm"),
                    dmc.Text(detailed_reason, size="sm"),
                    dmc.SimpleGrid(
                        cols=4,
                        spacing="xs",
                        mt="sm",
                        children=[
                            html.Div([
                                dmc.Text("Current CI", size="xs", c="dimmed"),
                                dmc.Text(
                                    f"+-{current_ci:.2f}" if current_ci else "N/A",
                                    size="sm"
                                )
                            ]),
                            html.Div([
                                dmc.Text("Target CI", size="xs", c="dimmed"),
                                dmc.Text(
                                    f"+-{target_ci:.2f}" if target_ci else "N/A",
                                    size="sm"
                                )
                            ]),
                            html.Div([
                                dmc.Text("P(effect)", size="xs", c="dimmed"),
                                dmc.Text(prob_text, size="sm")
                            ]),
                            html.Div([
                                dmc.Text("Reps needed", size="xs", c="dimmed"),
                                dmc.Text(
                                    str(replicates_needed) if replicates_needed else "N/A",
                                    size="sm"
                                )
                            ])
                        ]
                    )
                ]
            )
        ],
        p="sm",
        withBorder=True,
        radius="md",
        style={
            "marginBottom": "0.5rem",
            "backgroundColor": "var(--mantine-color-blue-0)" if is_selected else None
        }
    )


def create_selected_construct_item(
    construct_id: int,
    name: str,
    family: str = None,
    is_anchor: bool = False,
):
    """Create a selected construct list item."""
    return dmc.Group(
        children=[
            html.Div(
                children=[
                    dmc.Text(name, size="sm", fw=500),
                    dmc.Group(
                        children=[
                            dmc.Badge(
                                family or "universal",
                                size="xs",
                                color="gray"
                            ) if family else None,
                            dmc.Badge(
                                "Anchor",
                                size="xs",
                                color="blue",
                                variant="light"
                            ) if is_anchor else None,
                        ],
                        gap="xs"
                    )
                ]
            ),
            dmc.Group(
                children=[
                    dmc.NumberInput(
                        id={"type": "construct-conc-input", "id": construct_id},
                        value=1000,
                        min=1,
                        step=10,
                        w=75,
                        size="xs",
                        styles={"input": {"textAlign": "right"}}
                    ),
                    dmc.Text("ng/µL", size="10px", c="dimmed", style={"lineHeight": "1", "width": "25px"}),
                ],
                gap="3px"
            )
        ],
        justify="space-between",
        align="center",
        style={"padding": "0.5rem 0", "borderBottom": "1px solid #eee"}
    )
