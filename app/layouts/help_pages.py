"""
Help page layouts for Getting Started Guide and Workflow Overview.
"""
import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify


def create_getting_started_layout() -> dmc.Container:
    """Create the Getting Started Guide page."""
    return dmc.Container(
        children=[
            # Back navigation
            dmc.Group(
                children=[
                    dcc.Link(
                        dmc.ActionIcon(
                            DashIconify(icon="mdi:arrow-left", width=24),
                            variant="subtle",
                            size="lg",
                        ),
                        href="/projects",
                    ),
                    dmc.Title("Getting Started Guide", order=2),
                ],
                gap="md",
                mb="xl",
            ),

            # Introduction
            dmc.Paper(
                children=[
                    dmc.Title("Welcome to IVT Kinetics Analyzer", order=3, mb="sm"),
                    dmc.Text(
                        "This application helps you design, execute, and analyze "
                        "in-vitro transcription (IVT) kinetics experiments using "
                        "fluorogenic aptamer reporters. Follow this guide to set up "
                        "your first project and run your analysis.",
                        size="md",
                        c="dimmed",
                    ),
                ],
                p="xl",
                withBorder=True,
                radius="md",
                mb="lg",
            ),

            # Step 1: Create a Project
            _guide_step(
                number=1,
                title="Create a Project",
                icon="mdi:folder-plus",
                content=[
                    dmc.Text(
                        "Start by creating a new project from the Projects page. "
                        "Give it a descriptive name (e.g., 'Stem II' or 'Loop Variants'). "
                        "Each project tracks a set of related experiments from "
                        "construct definition through final analysis.",
                    ),
                    dmc.List(
                        children=[
                            dmc.ListItem("Navigate to the Projects page (home screen)"),
                            dmc.ListItem('Click "New Project" and enter a name'),
                            dmc.ListItem("Click into the project to reach the Project Dashboard"),
                        ],
                        size="sm",
                        spacing="xs",
                        mt="sm",
                    ),
                ],
            ),

            # Step 2: Define Constructs
            _guide_step(
                number=2,
                title="Define Your Constructs",
                icon="mdi:dna",
                content=[
                    dmc.Text(
                        "Register the T-box or aptamer constructs you'll be testing. "
                        "Each construct needs an identifier, a family grouping, and "
                        "a stock concentration. Mark one construct per family as the "
                        "wild-type reference for fold-change calculations.",
                    ),
                    dmc.Alert(
                        title="Key concept: Families",
                        children=dmc.Text(
                            "Constructs in the same family are analyzed together in "
                            "the hierarchical model. The wild-type construct in each "
                            "family serves as the reference for fold-change comparisons.",
                            size="sm",
                        ),
                        color="blue",
                        icon=DashIconify(icon="mdi:lightbulb-outline", width=20),
                        mt="sm",
                    ),
                ],
            ),

            # Step 3: Plan IVT Reaction (optional)
            _guide_step(
                number=3,
                title="Plan Your IVT Reaction (Optional)",
                icon="mdi:calculator-variant",
                content=[
                    dmc.Text(
                        "Use the built-in reaction calculator to compute master mix "
                        "volumes, DNA additions, and generate a step-by-step bench "
                        "protocol. The calculator accounts for replicates, overage, "
                        "and negative controls automatically.",
                    ),
                    dmc.Text(
                        "This step is optional but recommended - the calculator "
                        "output can be imported directly into the plate layout step.",
                        size="sm",
                        c="dimmed",
                        mt="xs",
                    ),
                ],
            ),

            # Step 4: Create Plate Layout
            _guide_step(
                number=4,
                title="Create a Plate Layout",
                icon="mdi:grid",
                content=[
                    dmc.Text(
                        "Define where each construct and control goes on your plate. "
                        "Assign wells to constructs, mark negative controls "
                        "(-Template and -DFHBI), and set the plate format (96 or 384 well).",
                    ),
                    dmc.List(
                        children=[
                            dmc.ListItem(
                                "If you used the calculator, import the plan to "
                                "auto-populate well assignments"
                            ),
                            dmc.ListItem(
                                "Otherwise, manually assign constructs to wells "
                                "using the interactive plate grid"
                            ),
                            dmc.ListItem(
                                "Publish the layout when you're satisfied - "
                                "this locks it for data upload"
                            ),
                        ],
                        size="sm",
                        spacing="xs",
                        mt="sm",
                    ),
                ],
            ),

            # Step 5: Upload Data
            _guide_step(
                number=5,
                title="Upload Experimental Data",
                icon="mdi:upload",
                content=[
                    dmc.Text(
                        "Upload your BioTek plate reader export files (.txt format). "
                        "The parser automatically detects wells, timepoints, and "
                        "fluorescence readings. Each upload creates an experimental "
                        "session linked to the plate layout.",
                    ),
                ],
            ),

            # Step 6: Review QC
            _guide_step(
                number=6,
                title="Review Quality Control",
                icon="mdi:check-decagram",
                content=[
                    dmc.Text(
                        "Review automated QC flags for each experimental session. "
                        "The system checks for outlier wells, saturation, and drift. "
                        "Approve or exclude flagged wells, then approve the session "
                        "to unlock analysis.",
                    ),
                    dmc.Text(
                        "All sessions must be QC-approved before running the "
                        "hierarchical analysis.",
                        size="sm",
                        fw=500,
                        mt="xs",
                    ),
                ],
            ),

            # Step 7: Run Analysis
            _guide_step(
                number=7,
                title="Run Analysis",
                icon="mdi:chart-line",
                content=[
                    dmc.Text(
                        "Launch the dual statistical analysis. The system runs both "
                        "a Bayesian hierarchical model (PyMC MCMC) and a Frequentist "
                        "mixed-effects model (statsmodels) on your fold-change data. "
                        "Each construct family is modeled independently.",
                    ),
                    dmc.Alert(
                        title="Dual methods",
                        children=dmc.Text(
                            "Running both methods provides cross-validation. The Bayesian "
                            "model gives posterior distributions and credible intervals, "
                            "while the Frequentist model provides p-values and confidence "
                            "intervals. Agreement between methods increases confidence.",
                            size="sm",
                        ),
                        color="blue",
                        icon=DashIconify(icon="mdi:lightbulb-outline", width=20),
                        mt="sm",
                    ),
                ],
            ),

            # Step 8: Export Results
            _guide_step(
                number=8,
                title="Export Results",
                icon="mdi:export",
                content=[
                    dmc.Text(
                        "Generate publication-ready outputs including forest plots, "
                        "fitted curves, parameter tables, and daily experiment reports "
                        "in PDF format. The export page offers both a full publication "
                        "package and a daily report for lab notebook records.",
                    ),
                ],
            ),

            # Footer
            dmc.Paper(
                children=[
                    dmc.Group(
                        children=[
                            DashIconify(icon="mdi:help-circle", width=24, color="#228be6"),
                            html.Div(
                                children=[
                                    dmc.Text("Need more help?", fw=600),
                                    dmc.Text(
                                        "Check the Workflow Overview for a high-level map of "
                                        "how all the pieces fit together.",
                                        size="sm",
                                        c="dimmed",
                                    ),
                                ],
                            ),
                            dcc.Link(
                                dmc.Button("Workflow Overview", variant="light"),
                                href="/help/workflow",
                            ),
                        ],
                        gap="md",
                    ),
                ],
                p="lg",
                withBorder=True,
                radius="md",
                mt="lg",
                style={"backgroundColor": "var(--bg-surface)"},
            ),
        ],
        size="md",
        style={"paddingTop": "1rem", "paddingBottom": "2rem"},
    )


def create_workflow_overview_layout() -> dmc.Container:
    """Create the Workflow Overview page."""
    return dmc.Container(
        children=[
            # Back navigation
            dmc.Group(
                children=[
                    dcc.Link(
                        dmc.ActionIcon(
                            DashIconify(icon="mdi:arrow-left", width=24),
                            variant="subtle",
                            size="lg",
                        ),
                        href="/projects",
                    ),
                    dmc.Title("Workflow Overview", order=2),
                ],
                gap="md",
                mb="xl",
            ),

            # Overview intro
            dmc.Paper(
                children=[
                    dmc.Text(
                        "The IVT Kinetics Analyzer follows a structured pipeline from "
                        "experimental design through statistical analysis. Each stage "
                        "builds on the previous one, with safeguards to ensure data "
                        "integrity at every step.",
                        size="md",
                        c="dimmed",
                    ),
                ],
                p="xl",
                withBorder=True,
                radius="md",
                mb="lg",
            ),

            # Pipeline diagram
            dmc.Title("Analysis Pipeline", order=4, mb="md"),
            _workflow_pipeline(),

            # Key concepts
            dmc.Title("Key Concepts", order=4, mb="md", mt="xl"),

            dmc.SimpleGrid(
                children=[
                    _concept_card(
                        "Draft / Publish Workflow",
                        "mdi:file-check",
                        "Constructs, layouts, and other entities start as drafts. "
                        "You can edit freely in draft mode. Publishing locks the "
                        "entity and makes it available for downstream steps. "
                        "Children must be published before their parent.",
                    ),
                    _concept_card(
                        "Hierarchical Analysis",
                        "mdi:sitemap",
                        "The Bayesian model accounts for variance at multiple "
                        "levels: residual (well-to-well), plate (session-to-session), "
                        "and construct effects. This produces more reliable estimates "
                        "than simple averaging, especially with few replicates.",
                    ),
                    _concept_card(
                        "Fold Change",
                        "mdi:swap-vertical",
                        "Construct effects are measured as fold-changes relative to "
                        "the wild-type reference within each family. Fold-changes "
                        "are computed from fitted F_max values and analyzed on the "
                        "log scale for statistical modeling.",
                    ),
                    _concept_card(
                        "Dual Statistical Methods",
                        "mdi:scale-balance",
                        "Every analysis runs both Bayesian (PyMC MCMC) and "
                        "Frequentist (statsmodels) methods. Agreement between methods "
                        "increases confidence. Disagreement flags results that need "
                        "more data or careful interpretation.",
                    ),
                    _concept_card(
                        "Curve Fitting",
                        "mdi:chart-bell-curve-cumulative",
                        "Raw fluorescence time-courses are fit to kinetic models "
                        "(default: 3-parameter exponential with lag). The fitted "
                        "parameters (k_obs, F_max, t_lag) summarize each well's "
                        "transcription kinetics.",
                    ),
                    _concept_card(
                        "Quality Control",
                        "mdi:shield-check",
                        "Automated QC checks flag wells with anomalous behavior: "
                        "poor fits (low R\u00b2), saturation, drift, or outlier "
                        "kinetics. Flagged wells can be excluded before analysis "
                        "to protect statistical integrity.",
                    ),
                ],
                cols={"base": 1, "sm": 2, "lg": 3},
                spacing="md",
            ),

            # Data integrity
            dmc.Title("Data Integrity Safeguards", order=4, mb="md", mt="xl"),
            dmc.Paper(
                children=[
                    dmc.List(
                        children=[
                            dmc.ListItem([
                                dmc.Text("Cascade invalidation: ", span=True, fw=600),
                                dmc.Text(
                                    "When upstream data changes (e.g., a well is excluded), "
                                    "all downstream results are automatically invalidated.",
                                    span=True,
                                ),
                            ]),
                            dmc.ListItem([
                                dmc.Text("Soft deletes only: ", span=True, fw=600),
                                dmc.Text(
                                    "No data is ever permanently deleted. Exclusions and "
                                    "revisions are tracked in the audit trail.",
                                    span=True,
                                ),
                            ]),
                            dmc.ListItem([
                                dmc.Text("Publish locking: ", span=True, fw=600),
                                dmc.Text(
                                    "Published entities cannot be modified, preventing "
                                    "accidental changes to data that downstream analyses "
                                    "depend on.",
                                    span=True,
                                ),
                            ]),
                            dmc.ListItem([
                                dmc.Text("Full audit trail: ", span=True, fw=600),
                                dmc.Text(
                                    "Every create, update, publish, and approval action "
                                    "is logged with timestamp, user, and field-level diffs.",
                                    span=True,
                                ),
                            ]),
                        ],
                        spacing="sm",
                    ),
                ],
                p="lg",
                withBorder=True,
                radius="md",
            ),

            # Footer
            dmc.Paper(
                children=[
                    dmc.Group(
                        children=[
                            DashIconify(icon="mdi:book-open-variant", width=24, color="#228be6"),
                            html.Div(
                                children=[
                                    dmc.Text("Ready to start?", fw=600),
                                    dmc.Text(
                                        "Follow the step-by-step Getting Started Guide "
                                        "to set up your first project.",
                                        size="sm",
                                        c="dimmed",
                                    ),
                                ],
                            ),
                            dcc.Link(
                                dmc.Button("Getting Started Guide", variant="light"),
                                href="/help/getting-started",
                            ),
                        ],
                        gap="md",
                    ),
                ],
                p="lg",
                withBorder=True,
                radius="md",
                mt="lg",
                style={"backgroundColor": "var(--bg-surface)"},
            ),
        ],
        size="md",
        style={"paddingTop": "1rem", "paddingBottom": "2rem"},
    )


# ---------------------------------------------------------------------------
# Helper components
# ---------------------------------------------------------------------------


def _guide_step(number: int, title: str, icon: str, content: list) -> dmc.Paper:
    """Create a numbered guide step card."""
    return dmc.Paper(
        children=[
            dmc.Group(
                children=[
                    dmc.ThemeIcon(
                        DashIconify(icon=icon, width=22),
                        size=40,
                        radius="xl",
                        variant="light",
                        color="blue",
                    ),
                    html.Div(
                        children=[
                            dmc.Text(f"Step {number}", size="xs", c="dimmed", fw=600),
                            dmc.Title(title, order=4),
                        ],
                    ),
                ],
                gap="md",
                mb="md",
            ),
            html.Div(children=content),
        ],
        p="lg",
        withBorder=True,
        radius="md",
        mb="md",
    )


def _workflow_pipeline() -> dmc.Paper:
    """Create a visual workflow pipeline."""
    steps = [
        ("mdi:dna", "Constructs", "Define test & reference constructs"),
        ("mdi:calculator-variant", "Calculator", "Plan reactions (optional)"),
        ("mdi:grid", "Layout", "Assign wells on plate"),
        ("mdi:upload", "Upload", "Import BioTek data"),
        ("mdi:check-decagram", "QC Review", "Approve experimental sessions"),
        ("mdi:chart-line", "Analysis", "Bayesian + Frequentist modeling"),
        ("mdi:export", "Export", "Publication package & reports"),
    ]

    step_items = []
    for i, (icon, label, desc) in enumerate(steps):
        step_items.append(
            dmc.Stack(
                children=[
                    dmc.ThemeIcon(
                        DashIconify(icon=icon, width=24),
                        size=48,
                        radius="xl",
                        variant="light",
                        color="blue",
                    ),
                    dmc.Text(label, fw=600, size="sm", ta="center"),
                    dmc.Text(desc, size="xs", c="dimmed", ta="center"),
                ],
                align="center",
                gap="xs",
                style={"flex": "1", "minWidth": "100px"},
            )
        )
        if i < len(steps) - 1:
            step_items.append(
                DashIconify(
                    icon="mdi:chevron-right",
                    width=24,
                    color="var(--text-tertiary)",
                    style={"alignSelf": "center", "flexShrink": 0, "marginTop": "-20px"},
                )
            )

    return dmc.Paper(
        children=[
            dmc.Group(
                children=step_items,
                gap="sm",
                justify="center",
                wrap="wrap",
            ),
        ],
        p="xl",
        withBorder=True,
        radius="md",
    )


def _concept_card(title: str, icon: str, description: str) -> dmc.Paper:
    """Create a concept explanation card."""
    return dmc.Paper(
        children=[
            dmc.Group(
                children=[
                    dmc.ThemeIcon(
                        DashIconify(icon=icon, width=20),
                        size=36,
                        radius="md",
                        variant="light",
                        color="blue",
                    ),
                    dmc.Text(title, fw=600, size="sm"),
                ],
                gap="sm",
                mb="sm",
            ),
            dmc.Text(description, size="sm", c="dimmed"),
        ],
        p="md",
        withBorder=True,
        radius="md",
    )
