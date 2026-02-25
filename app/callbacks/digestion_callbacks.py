"""
Callbacks for the standalone restriction enzyme digestion calculator.
"""
from dash import Output, Input, State
from dash.exceptions import PreventUpdate


def register_digestion_callbacks(app):
    """Register digestion calculator callbacks."""

    # Print button — clientside to avoid server round-trip
    app.clientside_callback(
        """
        function(n) {
            if (n) {
                var prev = document.title;
                document.title = "Digestion Protocol";
                window.print();
                document.title = prev;
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("dig-print-dummy", "children"),
        Input("dig-print-btn", "n_clicks"),
        prevent_initial_call=True,
    )

    @app.callback(
        [
            Output("dig-results-container", "children"),
            Output("dig-protocol-container", "children"),
        ],
        Input("dig-calculate-btn", "n_clicks"),
        [
            State("dig-dna-conc", "value"),
            State("dig-dna-amount", "value"),
            State("dig-enzyme-name", "value"),
            State("dig-enzyme-conc", "value"),
            State("dig-units-per-ug", "value"),
            State("dig-buffer-name", "value"),
            State("dig-incubation-temp", "value"),
            State("dig-incubation-time", "value"),
        ],
        prevent_initial_call=True,
    )
    def calculate_digestion(
        n_clicks,
        dna_conc,
        dna_amount,
        enzyme_name,
        enzyme_conc,
        units_per_ug,
        buffer_name,
        incubation_temp,
        incubation_time,
    ):
        """Calculate digestion reaction volumes and generate protocol."""
        import dash_mantine_components as dmc
        from dash import html
        from dash_iconify import DashIconify

        if not n_clicks:
            raise PreventUpdate

        # ----- Validate inputs -----
        errors = []
        if not dna_conc or dna_conc <= 0:
            errors.append("DNA concentration must be greater than 0")
        if not dna_amount or dna_amount <= 0:
            errors.append("DNA amount must be greater than 0")
        if not enzyme_conc or enzyme_conc <= 0:
            errors.append("Enzyme concentration must be greater than 0")
        if not units_per_ug or units_per_ug <= 0:
            errors.append("Units per \u00b5g must be greater than 0")

        if errors:
            error_alert = dmc.Alert(
                title="Missing inputs",
                children=dmc.List(
                    [dmc.ListItem(e) for e in errors],
                    size="sm",
                ),
                color="red",
                icon=DashIconify(icon="mdi:alert-circle", width=20),
            )
            return error_alert, ""

        # ----- Calculate volumes -----
        # DNA volume: amount (µg) / concentration (µg/µL)
        dna_conc_ug_ul = dna_conc / 1000  # ng/µL → µg/µL
        dna_vol = dna_amount / dna_conc_ug_ul

        # Enzyme volume: (amount × units_per_ug) / concentration (U/µL)
        total_units = dna_amount * units_per_ug
        enzyme_conc_u_ul = enzyme_conc / 1000  # U/mL → U/µL
        enzyme_vol = total_units / enzyme_conc_u_ul

        # Total volume: enzyme at 5% v/v
        total_vol = enzyme_vol * 20

        # Buffer volume: 1X from 10X stock
        buffer_vol = total_vol / 10

        # Water volume: remainder
        water_vol = total_vol - dna_vol - enzyme_vol - buffer_vol

        # ----- Warnings -----
        warnings = []

        if water_vol < 0:
            warnings.append(
                "Negative water volume: DNA and/or enzyme volumes exceed "
                "the total reaction volume. Increase enzyme concentration "
                "or decrease DNA amount."
            )
            water_vol = 0
            # Recalculate total so the table sums correctly
            total_vol = dna_vol + enzyme_vol + buffer_vol

        if dna_vol > total_vol * 0.5:
            warnings.append(
                "DNA volume exceeds 50% of total reaction. Consider using "
                "a more concentrated DNA stock."
            )

        enzyme_display = enzyme_name.strip() if enzyme_name and enzyme_name.strip() else "Enzyme"
        buffer_display = buffer_name or "10X Buffer"

        # ----- Results panel -----
        results = _build_results_panel(
            dna_vol=dna_vol,
            enzyme_vol=enzyme_vol,
            buffer_vol=buffer_vol,
            water_vol=water_vol,
            total_vol=total_vol,
            total_units=total_units,
            enzyme_display=enzyme_display,
            buffer_display=buffer_display,
            dna_amount=dna_amount,
            dna_conc=dna_conc,
            enzyme_conc=enzyme_conc,
            warnings=warnings,
        )

        # ----- Protocol panel -----
        protocol = _build_protocol_panel(
            dna_vol=dna_vol,
            enzyme_vol=enzyme_vol,
            buffer_vol=buffer_vol,
            water_vol=water_vol,
            total_vol=total_vol,
            total_units=total_units,
            enzyme_display=enzyme_display,
            buffer_display=buffer_display,
            dna_amount=dna_amount,
            dna_conc=dna_conc,
            incubation_temp=incubation_temp or 37,
            incubation_time=incubation_time or 30,
        )

        return results, protocol


def _build_results_panel(
    *,
    dna_vol,
    enzyme_vol,
    buffer_vol,
    water_vol,
    total_vol,
    total_units,
    enzyme_display,
    buffer_display,
    dna_amount,
    dna_conc,
    enzyme_conc,
    warnings,
):
    """Build the volumes results panel."""
    import dash_mantine_components as dmc
    from dash import html
    from dash_iconify import DashIconify

    warning_alerts = []
    for w in warnings:
        warning_alerts.append(
            dmc.Alert(
                children=w,
                color="yellow",
                icon=DashIconify(icon="mdi:alert", width=18),
                mb="sm",
            )
        )

    # Summary stats
    stats = dmc.Group(
        children=[
            _stat_card(f"{dna_amount:.1f} \u00b5g", "DNA to digest"),
            _stat_card(f"{total_units:.0f} U", "Enzyme units"),
            _stat_card(f"{total_vol:.1f} \u00b5L", "Total volume"),
        ],
        gap="sm",
        mb="md",
    )

    # Volumes table
    rows = [
        ("DNA", f"{dna_vol:.1f}", f"{dna_conc:.0f} ng/\u00b5L stock"),
        (enzyme_display, f"{enzyme_vol:.1f}", f"{enzyme_conc:.0f} U/mL stock"),
        (f"{buffer_display} 10X", f"{buffer_vol:.1f}", "1X final concentration"),
        ("Nuclease-free water", f"{water_vol:.1f}", ""),
    ]

    table_rows = []
    for component, vol, note in rows:
        table_rows.append(
            html.Tr([
                html.Td(dmc.Text(component, fw=500, size="sm")),
                html.Td(dmc.Text(f"{vol} \u00b5L", size="sm", ta="right")),
                html.Td(dmc.Text(note, size="xs", c="dimmed")),
            ])
        )
    # Total row
    table_rows.append(
        html.Tr(
            [
                html.Td(dmc.Text("Total", fw=700, size="sm")),
                html.Td(dmc.Text(f"{total_vol:.1f} \u00b5L", fw=700, size="sm", ta="right")),
                html.Td(""),
            ],
            style={"borderTop": "2px solid #dee2e6"},
        )
    )

    table = dmc.Table(
        children=[
            html.Thead(
                html.Tr([
                    html.Th("Component"),
                    html.Th("Volume", style={"textAlign": "right"}),
                    html.Th("Note"),
                ])
            ),
            html.Tbody(table_rows),
        ],
        striped=True,
        highlightOnHover=True,
        mb="md",
    )

    return dmc.Paper(
        children=[
            dmc.Title("Calculated Volumes", order=4, mb="md"),
            *warning_alerts,
            stats,
            table,
        ],
        p="lg",
        withBorder=True,
        radius="md",
        mb="lg",
    )


def _build_protocol_panel(
    *,
    dna_vol,
    enzyme_vol,
    buffer_vol,
    water_vol,
    total_vol,
    total_units,
    enzyme_display,
    buffer_display,
    dna_amount,
    dna_conc,
    incubation_temp,
    incubation_time,
):
    """Build the step-by-step protocol panel."""
    import dash_mantine_components as dmc
    from dash import html
    from dash_iconify import DashIconify

    # Phenol-chloroform volumes
    pci_vol = total_vol  # 1:1 ratio

    # Ethanol precipitation
    etoh_vol = total_vol * 3  # 3× volume
    naac_vol = total_vol * 0.1  # 0.1× volume

    # Resuspension
    resuspend_vol = dna_amount  # ~1 µL per µg

    time_str = f"{round(incubation_time)} minutes"

    steps = [
        {
            "section": "PREPARE REACTION MIXTURE",
            "steps": [
                {
                    "text": "Label a microcentrifuge tube for the digestion reaction",
                    "note": f"Use a 1.5 mL tube for reactions \u2264 500 \u00b5L, "
                            f"or a 15 mL conical for larger volumes",
                },
                {
                    "text": f"Add {dna_vol:.1f} \u00b5L plasmid DNA "
                            f"({dna_conc:.0f} ng/\u00b5L) \u2192 tube",
                    "note": f"{dna_amount:.1f} \u00b5g total DNA",
                },
                {
                    "text": f"Add {buffer_vol:.1f} \u00b5L {buffer_display} "
                            f"(10X) \u2192 tube",
                    "note": "1X final concentration",
                },
                {
                    "text": f"Add {water_vol:.1f} \u00b5L nuclease-free water "
                            f"\u2192 tube",
                    "note": None,
                },
                {
                    "text": f"Add {enzyme_vol:.1f} \u00b5L {enzyme_display} "
                            f"({total_units:.0f} U) \u2192 tube",
                    "note": "Add enzyme LAST to minimize exposure to adverse conditions",
                },
            ],
        },
        {
            "section": "MIX & INCUBATE",
            "steps": [
                {
                    "text": "Mix gently by pipetting up and down or flicking the tube",
                    "note": "Avoid vortexing, which can damage DNA",
                },
                {
                    "text": f"Incubate at {incubation_temp}\u00b0C for {time_str}",
                    "note": "Timesaver enzymes may be ready in 15 minutes",
                },
            ],
        },
        {
            "section": "FIRST PHENOL-CHLOROFORM EXTRACTION",
            "steps": [
                {
                    "text": f"Add {pci_vol:.1f} \u00b5L phenol:chloroform:isoamyl "
                            f"alcohol (25:24:1) \u2192 tube",
                    "note": "1:1 ratio with reaction volume",
                },
                {
                    "text": "Mix by vigorous shaking",
                    "note": None,
                },
                {
                    "text": "Centrifuge at maximum speed for 5 minutes at room temperature",
                    "note": None,
                },
                {
                    "text": "Transfer the upper aqueous phase to a new tube",
                    "note": "Avoid the interphase",
                },
            ],
        },
        {
            "section": "SECOND PHENOL-CHLOROFORM EXTRACTION",
            "steps": [
                {
                    "text": f"Add {pci_vol:.1f} \u00b5L phenol:chloroform:isoamyl "
                            f"alcohol (25:24:1) \u2192 tube",
                    "note": None,
                },
                {
                    "text": "Vortex briefly, centrifuge at maximum speed for 5 minutes",
                    "note": None,
                },
                {
                    "text": "Transfer the aqueous phase to a fresh tube",
                    "note": None,
                },
            ],
        },
        {
            "section": "ETHANOL PRECIPITATION",
            "steps": [
                {
                    "text": f"Add {etoh_vol:.1f} \u00b5L cold (\u221220\u00b0C) "
                            f"100% ethanol \u2192 tube",
                    "note": "3\u00d7 volumes",
                },
                {
                    "text": f"Add {naac_vol:.1f} \u00b5L sodium acetate "
                            f"(3 M, pH 7.0) \u2192 tube",
                    "note": "0.1\u00d7 volumes",
                },
                {
                    "text": "Mix gently and incubate at \u221220\u00b0C for "
                            "\u22651 hour (or overnight)",
                    "note": None,
                },
                {
                    "text": "Centrifuge at maximum speed for 15 minutes at 4\u00b0C",
                    "note": "Discard supernatant carefully",
                },
                {
                    "text": "Wash the DNA pellet twice with 1 mL of 80% ethanol",
                    "note": "Centrifuge briefly between washes",
                },
                {
                    "text": "Dry the pellet using the SpeedVac",
                    "note": "Do not over-dry",
                },
            ],
        },
        {
            "section": "RESUSPEND DNA",
            "steps": [
                {
                    "text": f"Resuspend the pellet in ~{resuspend_vol:.0f} \u00b5L "
                            f"nuclease-free water",
                    "note": f"~1 \u00b5L per \u00b5g DNA ({dna_amount:.0f} \u00b5g)",
                },
            ],
        },
        {
            "section": "VERIFICATION (OPTIONAL)",
            "steps": [
                {
                    "text": "Run an aliquot on an agarose gel alongside "
                            "undigested reference DNA",
                    "note": "Digested (linear) DNA migrates slower than supercoiled DNA",
                },
            ],
        },
    ]

    # Build protocol HTML
    protocol_items = []
    step_num = 1

    for section in steps:
        # Section header
        protocol_items.append(
            html.Div(
                dmc.Text(section["section"], fw=700, size="sm", c="blue"),
                style={
                    "marginTop": "16px",
                    "marginBottom": "8px",
                    "paddingBottom": "4px",
                    "borderBottom": "1px solid #e3f2fd",
                },
            )
        )

        for step in section["steps"]:
            step_content = [
                html.Div(
                    children=[
                        html.Span(
                            f"{step_num}.",
                            style={
                                "fontWeight": "600",
                                "color": "#1a73e8",
                                "display": "inline-block",
                                "minWidth": "32px",
                            },
                        ),
                        html.Span(step["text"]),
                    ],
                    style={"marginBottom": "2px"},
                ),
            ]
            if step.get("note"):
                step_content.append(
                    html.Div(
                        f"({step['note']})",
                        style={
                            "marginLeft": "32px",
                            "color": "#666",
                            "fontStyle": "italic",
                            "fontSize": "0.9em",
                            "marginBottom": "4px",
                        },
                    )
                )
            protocol_items.append(
                html.Div(step_content, style={"marginBottom": "6px"})
            )
            step_num += 1

    # Notes section
    protocol_items.append(
        dmc.Alert(
            title="Notes",
            children=dmc.List(
                children=[
                    dmc.ListItem(
                        "For double digests, check NEB\u2019s Double Digest Finder "
                        "for compatible buffers."
                    ),
                    dmc.ListItem(
                        "rCutSmart buffer is compatible with >210 restriction enzymes."
                    ),
                    dmc.ListItem(
                        "Keep enzyme volume <10% of total reaction to "
                        "prevent star activity."
                    ),
                ],
                size="sm",
                spacing="xs",
            ),
            color="gray",
            mt="md",
        )
    )

    return dmc.Paper(
        children=[
            dmc.Group(
                children=[
                    html.Div(
                        children=[
                            dmc.Title("Protocol", order=4),
                            dmc.Text(
                                "Restriction Enzyme Digestion",
                                size="sm",
                                c="dimmed",
                            ),
                        ],
                    ),
                    dmc.Button(
                        "Print Protocol",
                        id="dig-print-btn",
                        variant="light",
                        size="sm",
                        leftSection=DashIconify(icon="mdi:printer", width=18),
                        className="dig-no-print",
                    ),
                ],
                justify="space-between",
                mb="md",
            ),
            html.Div(
                protocol_items,
                style={"fontSize": "0.95em", "lineHeight": "1.6"},
            ),
        ],
        p="lg",
        withBorder=True,
        radius="md",
    )


def _stat_card(value: str, label: str):
    """Create a small stat display card."""
    import dash_mantine_components as dmc

    return dmc.Paper(
        children=[
            dmc.Text(value, fw=700, size="lg", ta="center", c="blue"),
            dmc.Text(label, size="xs", c="dimmed", ta="center"),
        ],
        p="sm",
        withBorder=True,
        radius="md",
        style={"flex": "1", "minWidth": "100px", "backgroundColor": "var(--bg-surface)"},
    )
