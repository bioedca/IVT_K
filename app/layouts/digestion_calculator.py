"""
Standalone restriction enzyme digestion calculator.

Calculates reaction volumes for linearizing plasmid DNA and generates
a step-by-step bench protocol based on the NEB digestion workflow.
"""
import dash_mantine_components as dmc
from dash import html, dcc
from dash_iconify import DashIconify


def create_digestion_calculator_layout() -> dmc.Container:
    """Create the digestion calculator page."""
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
                    html.Div(
                        children=[
                            dmc.Title("Restriction Enzyme Digestion Calculator", order=2),
                            dmc.Text(
                                "Linearize plasmid DNA for in vitro transcription",
                                size="sm",
                                c="dimmed",
                            ),
                        ],
                    ),
                ],
                gap="md",
                mb="xl",
                className="dig-page-header",
            ),

            dmc.Grid(
                children=[
                    # Left column - Inputs
                    dmc.GridCol(
                        children=[_create_input_panel()],
                        span={"base": 12, "md": 5},
                        className="dig-input-col",
                    ),
                    # Right column - Results + Protocol
                    dmc.GridCol(
                        children=[
                            html.Div(id="dig-results-container"),
                            html.Div(id="dig-protocol-container"),
                            # Hidden target for print clientside callback
                            html.Div(id="dig-print-dummy", style={"display": "none"}),
                        ],
                        span={"base": 12, "md": 7},
                        className="dig-output-col",
                    ),
                ],
                gutter="lg",
            ),

        ],
        size="lg",
        style={"paddingTop": "1rem", "paddingBottom": "2rem"},
    )


def _create_input_panel() -> dmc.Paper:
    """Create the input form panel."""
    return dmc.Paper(
        children=[
            dmc.Title("Reaction Parameters", order=4, mb="md"),

            # DNA section
            dmc.Text("DNA", fw=600, size="sm", mb="xs", c="blue"),
            dmc.NumberInput(
                id="dig-dna-conc",
                label="DNA concentration (ng/\u00b5L)",
                placeholder="e.g., 1639",
                min=0.1,
                step=10,
                decimalScale=1,
                mb="sm",
            ),
            dmc.NumberInput(
                id="dig-dna-amount",
                label="Amount of DNA to digest (\u00b5g)",
                placeholder="e.g., 100",
                min=0.1,
                step=10,
                decimalScale=1,
                value=100,
                mb="md",
            ),

            dmc.Divider(mb="md"),

            # Enzyme section
            dmc.Text("Enzyme", fw=600, size="sm", mb="xs", c="blue"),
            dmc.TextInput(
                id="dig-enzyme-name",
                label="Restriction enzyme name",
                placeholder="e.g., NsiI, EcoRI, BamHI",
                mb="sm",
            ),
            dmc.NumberInput(
                id="dig-enzyme-conc",
                label="Enzyme concentration (U/mL)",
                placeholder="e.g., 20000",
                min=1,
                step=1000,
                decimalScale=0,
                mb="sm",
            ),
            dmc.NumberInput(
                id="dig-units-per-ug",
                label="Units per \u00b5g DNA",
                placeholder="5\u201310 recommended",
                min=1,
                max=50,
                step=1,
                decimalScale=0,
                value=5,
                mb="md",
            ),

            dmc.Divider(mb="md"),

            # Buffer section
            dmc.Text("Buffer", fw=600, size="sm", mb="xs", c="blue"),
            dmc.Select(
                id="dig-buffer-name",
                label="Reaction buffer (10X stock)",
                data=[
                    "rCutSmart",
                    "CutSmart",
                    "NEBuffer 1.1",
                    "NEBuffer 2.1",
                    "NEBuffer 3.1",
                ],
                value="rCutSmart",
                mb="md",
            ),

            dmc.Divider(mb="md"),

            # Incubation
            dmc.Text("Incubation", fw=600, size="sm", mb="xs", c="blue"),
            dmc.NumberInput(
                id="dig-incubation-temp",
                label="Incubation temperature (\u00b0C)",
                value=37,
                min=20,
                max=65,
                step=1,
                mb="sm",
            ),
            dmc.NumberInput(
                id="dig-incubation-time",
                label="Incubation time (minutes)",
                value=30,
                min=5,
                max=960,
                step=5,
                decimalScale=0,
                mb="md",
            ),

            # Calculate button
            dmc.Button(
                "Calculate",
                id="dig-calculate-btn",
                fullWidth=True,
                color="blue",
                size="md",
                leftSection=DashIconify(icon="mdi:calculator", width=20),
            ),
        ],
        p="lg",
        withBorder=True,
        radius="md",
    )
