"""
Calculator callbacks for the IVT Reaction Calculator UI.

Phase 2.5.34: Calculator UI callbacks (F4.1-F4.34)

Handles:
- Loading recommendations from backend
- Construct selection/deselection
- Impact preview updates
- Volume calculations
- Protocol generation
- First Experiment Wizard flow
"""
from dash import Input, Output, State, callback, no_update, ctx, ALL, MATCH
from dash.exceptions import PreventUpdate
import json
import re

from app.services import SmartPlannerService, SmartPlannerError
from app.logging_config import get_logger

logger = get_logger(__name__)
from app.calculator import (
    calculate_master_mix,
    generate_protocol,
    format_protocol_text,
    format_protocol_csv,
    format_master_mix_table,
    validate_construct_list,
    format_validation_result,
    PlannerMode,
    MasterMixCalculation,
    LigandConfig,
    round_volume_up,
)
from app.calculator.constants import (
    PLATE_CONSTRAINTS,
    PlateFormat,
    DNA_MASS_TO_VOLUME_FACTOR,
    TARGET_DNA_CONCENTRATION_NM,
    MAX_LIGAND_VOLUME_FRACTION,
    MIN_PIPETTABLE_VOLUME_UL,
    WARN_PIPETTABLE_VOLUME_UL,
    DEFAULT_OVERAGE_PERCENT,
    STANDARD_COMPONENTS,
)


def _generate_printable_protocol_html(protocol, mm):
    """Generate printable HTML with checkboxes for the protocol.
    
    Args:
        protocol: PipettingProtocol object
        mm: MasterMixCalculation object
    
    Returns:
        List of Dash HTML components for the printable protocol
    """
    from dash import html
    from datetime import datetime
    
    elements = []
    
    # Header
    elements.append(html.H1("IVT Pipetting Protocol"))
    
    # Summary section
    summary_items = [
        html.P(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}"),
        html.P(f"Total Reactions: {mm.n_reactions}"),
        html.P(f"Reaction Volume: {mm.single_reaction.reaction_volume_ul:.1f} µL"),
        html.P(f"Master Mix per Tube: {mm.master_mix_per_tube_ul:.1f} µL"),
    ]
    if getattr(mm, 'is_ligand_workflow', False) and mm.ligand_config:
        summary_items.append(html.P(
            f"Ligand: {mm.ligand_config.final_concentration_uM:.0f} µM final "
            f"({mm.ligand_config.stock_concentration_uM:.0f} µM stock), "
            f"{mm.ligand_volume_per_rxn_ul:.1f} µL/rxn"
        ))
    if hasattr(protocol, 'project_name') and protocol.project_name:
        summary_items.insert(1, html.P(f"Project: {protocol.project_name}"))
    
    elements.append(html.Div(summary_items, className="summary"))
    
    # Master Mix Components Table
    elements.append(html.H2("Master Mix Components"))
    mm_table_rows = [
        html.Tr([
            html.Th("Component"),
            html.Th("Stock"),
            html.Th("Per Rxn (µL)"),
            html.Th("Total (µL)"),
        ])
    ]
    for comp in mm.components:
        mm_table_rows.append(html.Tr([
            html.Td(comp.name),
            html.Td(f"{comp.stock_concentration} {comp.stock_unit}"),
            html.Td(f"{comp.single_reaction_volume_ul:.2f}"),
            html.Td(f"{comp.master_mix_volume_ul:.1f}"),
        ]))
    elements.append(html.Table(mm_table_rows))
    
    # DNA Additions Table
    if mm.dna_additions:
        elements.append(html.H2("DNA Additions (per tube)"))
        has_lig_cond = any(
            getattr(add, 'ligand_condition', None)
            for add in mm.dna_additions
        )
        header_cells = [html.Th("Construct")]
        if has_lig_cond:
            header_cells.append(html.Th("Condition"))
        header_cells.extend([
            html.Th("Stock (ng/µL)"),
            html.Th("DNA (µL)"),
            html.Th("Water (µL)"),
            html.Th("Total (µL)"),
        ])
        dna_table_rows = [html.Tr(header_cells)]
        for add in mm.dna_additions:
            stock = f"{add.stock_concentration_ng_ul:.0f}" if add.stock_concentration_ng_ul > 0 else "-"
            dna = f"{add.dna_volume_ul:.1f}" if add.dna_volume_ul > 0 else "-"
            cells = [html.Td(add.construct_name)]
            if has_lig_cond:
                cells.append(html.Td(getattr(add, 'ligand_condition', '-') or '-'))
            cells.extend([
                html.Td(stock),
                html.Td(dna),
                html.Td(f"{add.water_adjustment_ul:.1f}"),
                html.Td(f"{add.total_addition_ul:.1f}"),
            ])
            dna_table_rows.append(html.Tr(cells))
        elements.append(html.Table(dna_table_rows))
    
    # Protocol Steps with Checkboxes
    elements.append(html.H2("Procedure"))
    
    step_table_rows = [
        html.Tr([
            html.Th("✓", className="checkbox-cell"),
            html.Th("#"),
            html.Th("Action"),
            html.Th("Volume"),
            html.Th("Component"),
            html.Th("Destination"),
            html.Th("Notes"),
        ])
    ]

    current_section = ""
    for step in protocol.steps:
        # Add section header if section changed
        if step.section != current_section:
            current_section = step.section
            step_table_rows.append(html.Tr([
                html.Td(colSpan=7, children=current_section, className="section-header")
            ]))

        vol_str = f"{step.volume_ul:.1f} µL" if step.volume_ul else "-"
        step_table_rows.append(html.Tr([
            html.Td("☐", className="checkbox-cell"),  # Unicode empty checkbox
            html.Td(step.step_number),
            html.Td(step.action),
            html.Td(vol_str),
            html.Td(step.component or "-"),
            html.Td(step.destination or "-"),
            html.Td(step.notes or "", className="notes"),
        ], className="step-row"))
    
    elements.append(html.Table(step_table_rows))
    
    # Notes
    if protocol.notes:
        elements.append(html.H3("Important Notes"))
        elements.append(html.Ul([html.Li(note) for note in protocol.notes]))
    
    return elements


_PRINT_CSS = """\
body {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.4;
    max-width: 8in;
    margin: 0.5in auto;
    padding: 0;
}
h1 { font-size: 16pt; margin-bottom: 8pt; border-bottom: 2px solid #333; padding-bottom: 4pt; }
h2 { font-size: 13pt; margin-top: 16pt; margin-bottom: 8pt; color: #333; border-bottom: 1px solid #ccc; }
h3 { font-size: 11pt; margin-top: 12pt; margin-bottom: 6pt; color: #555; }
.summary { background: #f5f5f5; padding: 10px; border-radius: 4px; margin-bottom: 16pt; }
.summary p { margin: 4pt 0; }
table { width: 100%; border-collapse: collapse; margin: 8pt 0; font-size: 10pt; }
th, td { border: 1px solid #ccc; padding: 6px 8px; text-align: left; }
th { background: #f0f0f0; font-weight: 600; }
.step-row td { vertical-align: top; }
.checkbox-cell { width: 24px; text-align: center; }
input[type="checkbox"] { width: 14px; height: 14px; margin: 0; }
.section-header { background: #e8e8e8; font-weight: 600; }
.notes { font-size: 9pt; color: #666; font-style: italic; }
.footer { margin-top: 20pt; padding-top: 8pt; border-top: 1px solid #ccc; font-size: 9pt; color: #666; }
pre { white-space: pre-wrap; font-family: 'Courier New', monospace; font-size: 10pt; }
@media print {
    body { margin: 0; }
    .no-print { display: none; }
}"""


def _build_protocol_select_options(setups):
    """Build dropdown select options from a list of ReactionSetup objects.

    Returns:
        Tuple of (select_options, visible_style).
        select_options is a list of dicts with 'value' and 'label' keys.
        visible_style is a CSS style dict (hidden if no setups).
    """
    if not setups:
        return [], {"display": "none"}
    select_options = []
    for s in setups:
        date_str = s.created_at.strftime("%Y-%m-%d") if s.created_at else "unknown"
        select_options.append({
            "value": str(s.id),
            "label": f"{s.name} — {date_str}",
        })
    return select_options, {"display": "block"}


def _build_printable_from_setup(setup):
    """Build printable HTML elements from a stored ReactionSetup.

    Renders the same structured tables as _generate_printable_protocol_html()
    using the stored JSON data from the database.

    Args:
        setup: ReactionSetup ORM instance

    Returns:
        List of Dash HTML components for the printable protocol
    """
    from dash import html

    elements = []

    # Header — matches fresh protocol style
    elements.append(html.H1("IVT Pipetting Protocol"))

    # Summary section
    summary_items = []
    if setup.created_at:
        summary_items.append(html.P(f"Date: {setup.created_at.strftime('%Y-%m-%d %H:%M')}"))
    # Compute total reactions from stored fields
    n_reactions = setup.n_reactions
    if n_reactions is None:
        # Fallback for setups saved before n_reactions was stored
        n_neg_tpl = setup.n_negative_template or 0
        n_neg_dye = setup.n_negative_dye or 0
        n_reactions = ((setup.n_constructs or 0) * (setup.n_replicates or 0)) + n_neg_tpl + n_neg_dye
    summary_items.append(html.P(f"Total Reactions: {n_reactions}"))
    summary_items.append(html.P(f"Reaction Volume: {setup.total_reaction_volume_ul:.1f} µL"))
    if setup.master_mix_per_tube_ul:
        summary_items.append(html.P(f"Master Mix per Tube: {setup.master_mix_per_tube_ul:.1f} µL"))
    elif setup.total_master_mix_volume_ul and n_reactions:
        # Fallback estimate for old setups
        summary_items.append(html.P(f"Total Master Mix: {setup.total_master_mix_volume_ul:.1f} µL"))
    if setup.ligand_final_concentration_um and setup.ligand_stock_concentration_um:
        lig_vol = setup.ligand_volume_per_rxn_ul or 0.0
        summary_items.append(html.P(
            f"Ligand: {setup.ligand_final_concentration_um:.0f} µM final "
            f"({setup.ligand_stock_concentration_um:.0f} µM stock), "
            f"{lig_vol:.1f} µL/rxn"
        ))
    elements.append(html.Div(summary_items, className="summary"))

    # Master mix volumes table (from stored JSON dict)
    if setup.master_mix_volumes:
        elements.append(html.H2("Master Mix Components"))
        mm_rows = [html.Tr([
            html.Th("Component"),
            html.Th("Stock"),
            html.Th("Per Rxn (µL)"),
            html.Th("Total (µL)"),
        ])]
        for comp_name, vol in setup.master_mix_volumes.items():
            if isinstance(vol, dict):
                stock_conc = vol.get('stock_concentration') or 0
                stock_unit = (vol.get('stock_unit') or '').strip()
                stock_str = f"{stock_conc} {stock_unit}".strip() if stock_conc else "-"
                single_ul = vol.get('single_ul')
                total_ul = vol.get('total_ul')
                single_str = f"{single_ul:.2f}" if single_ul is not None else "-"
                total_str = f"{total_ul:.1f}" if total_ul is not None else "-"
            else:
                # Legacy format: vol is just a number
                stock_str = "-"
                single_str = "-"
                total_str = f"{vol:.1f}" if isinstance(vol, (int, float)) else str(vol)
            mm_rows.append(html.Tr([
                html.Td(comp_name),
                html.Td(stock_str),
                html.Td(single_str),
                html.Td(total_str),
            ]))
        elements.append(html.Table(mm_rows))

    # DNA additions table
    if setup.dna_additions:
        elements.append(html.H2("DNA Additions (per tube)"))
        has_lig_cond = any(
            getattr(a, 'ligand_condition', None) for a in setup.dna_additions
        )
        header_cells = [html.Th("Construct")]
        if has_lig_cond:
            header_cells.append(html.Th("Condition"))
        header_cells.extend([
            html.Th("Stock (ng/µL)"),
            html.Th("DNA (µL)"),
            html.Th("Water (µL)"),
            html.Th("Total (µL)"),
        ])
        dna_rows = [html.Tr(header_cells)]
        for a in setup.dna_additions:
            # Build stock string with nM info if available
            if a.dna_stock_concentration_ng_ul:
                stock = f"{a.dna_stock_concentration_ng_ul:.0f}"
            else:
                stock = "-"
            dna = f"{a.dna_volume_ul:.1f}" if a.dna_volume_ul and a.dna_volume_ul > 0 else "-"
            cells = [html.Td(a.construct_name)]
            if has_lig_cond:
                cells.append(html.Td(getattr(a, 'ligand_condition', '-') or '-'))
            cells.extend([
                html.Td(stock),
                html.Td(dna),
                html.Td(f"{a.water_adjustment_ul:.1f}"),
                html.Td(f"{a.total_addition_ul:.1f}"),
            ])
            dna_rows.append(html.Tr(cells))
        elements.append(html.Table(dna_rows))

    # Protocol steps — parse stored text into structured table
    if setup.protocol_text:
        elements.append(html.H2("Procedure"))
        step_rows = _parse_protocol_text_to_table(setup.protocol_text)
        if step_rows:
            elements.append(html.Table(step_rows))
        else:
            # Fallback to pre-formatted text if parsing fails
            elements.append(html.Pre(setup.protocol_text))

    return elements


def _parse_protocol_text_to_table(protocol_text):
    """Parse stored protocol text into structured table rows.

    The protocol text format has sections delimited by ### headers and
    numbered steps like '  1. Action: volume component → destination'.

    Returns:
        List of html.Tr elements, or empty list if parsing fails.
    """
    from dash import html

    lines = protocol_text.split('\n')
    rows = [html.Tr([
        html.Th("✓", className="checkbox-cell"),
        html.Th("#"),
        html.Th("Action"),
        html.Th("Volume"),
        html.Th("Component"),
        html.Th("Destination"),
        html.Th("Notes"),
    ])]

    step_pattern = re.compile(r'^\s*(\d+)\.\s+(.+)$')
    section_pattern = re.compile(r'^###\s*(.+?)\s*###\s*$')
    parsed_any = False
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check for section headers (### SECTION NAME ###)
        sec_match = section_pattern.match(line)
        if sec_match:
            rows.append(html.Tr([
                html.Td(colSpan=7, children=sec_match.group(1).strip(), className="section-header")
            ]))
            i += 1
            continue

        # Check for numbered steps
        step_match = step_pattern.match(line)
        if step_match:
            parsed_any = True
            step_num = step_match.group(1)
            step_text = step_match.group(2).strip()

            # Collect continuation lines (indented, non-numbered, non-empty)
            notes_parts = []
            while i + 1 < len(lines):
                next_line = lines[i + 1]
                # Continuation: indented line starting with ( or just indented text
                if next_line and (next_line.startswith('     ') or next_line.startswith('\t')) and not step_pattern.match(next_line):
                    notes_parts.append(next_line.strip().strip('()'))
                    i += 1
                else:
                    break

            # Parse the step text to extract volume, component, destination
            action, volume, component, destination = _parse_step_text(step_text)
            notes = '; '.join(notes_parts) if notes_parts else ""

            rows.append(html.Tr([
                html.Td("☐", className="checkbox-cell"),
                html.Td(step_num),
                html.Td(action),
                html.Td(volume),
                html.Td(component),
                html.Td(destination),
                html.Td(notes, className="notes"),
            ], className="step-row"))

        i += 1

    return rows if parsed_any else []


def _parse_step_text(text):
    """Extract action, volume, component, and destination from a step string.

    Common formats:
      'Add to master mix tube: 176.7 µL 10X Reaction buffer → Master Mix tube'
      'Mix GTP stock GTP stock tube'
      'Label a new tube 1.5 mL tube → Work area'
      'Add -4nt DNA: 3.3 µL -4nt (988 ng/µL) → Tube: -4nt-1'
      'Add water adjustment: 2.4 µL Nuclease-free water → Tube: -4nt-1'
      'Keep on ice → Ice'

    Returns:
        Tuple of (action, volume, component, destination).
    """
    # Split on → for destination
    if '→' in text:
        before_arrow, destination = text.rsplit('→', 1)
        destination = destination.strip()
    elif ' → ' in text:
        before_arrow, destination = text.rsplit(' → ', 1)
        destination = destination.strip()
    else:
        before_arrow = text
        destination = "-"

    before_arrow = before_arrow.strip()

    # Try to extract volume (number followed by µL)
    vol_match = re.search(r'(\d+\.?\d*)\s*µL', before_arrow)
    if vol_match:
        volume = f"{float(vol_match.group(1)):.1f} µL"
        # Action is everything before the volume pattern
        vol_start = vol_match.start()
        # Find the colon-separated action prefix
        colon_idx = before_arrow.find(':')
        if colon_idx != -1 and colon_idx < vol_start:
            action = before_arrow[:colon_idx].strip()
            component = before_arrow[vol_match.end():].strip()
        else:
            action = before_arrow[:vol_start].strip().rstrip(':')
            component = before_arrow[vol_match.end():].strip()
    else:
        volume = "-"
        colon_idx = before_arrow.find(':')
        if colon_idx != -1:
            action = before_arrow[:colon_idx].strip()
            component = before_arrow[colon_idx + 1:].strip()
        else:
            action = before_arrow
            component = "-"

    if not component:
        component = "-"

    return action, volume, component, destination


def register_calculator_callbacks(app):
    """Register all calculator-related callbacks."""

    @app.callback(
        [
            Output("reaction-volume-input", "min"),
            Output("reaction-volume-input", "max"),
            Output("reaction-volume-input", "value"),
            Output("volume-constraint-help", "children"),
        ],
        Input("calc-project-store", "data"),
        State("reaction-volume-input", "value"),
        prevent_initial_call=True,
    )
    def update_volume_constraints_for_plate_format(project_data, current_value):
        """Update reaction volume input constraints based on project plate format."""
        if not project_data or not project_data.get("project_id"):
            raise PreventUpdate

        project_id = project_data["project_id"]

        try:
            project_summary = SmartPlannerService.get_project_summary(project_id)
            raw_fmt = project_summary.get("plate_format", "384")

            # Normalize to string "384" or "96"
            if hasattr(raw_fmt, "value"):
                plate_fmt_str = str(raw_fmt.value)
            else:
                plate_fmt_str = str(raw_fmt)

            plate_format = PlateFormat.WELL_384 if plate_fmt_str == "384" else PlateFormat.WELL_96
            constraints = PLATE_CONSTRAINTS[plate_format]

            # Update help text to show active constraint
            if plate_fmt_str == "384":
                help_text = f"384-well plate: {constraints.min_well_volume_ul:.0f}-{constraints.max_well_volume_ul:.0f} µL"
            else:
                help_text = f"96-well plate: {constraints.min_well_volume_ul:.0f}-{constraints.max_well_volume_ul:.0f} µL"

            # Clamp current value to new constraints if needed
            new_value = current_value
            if current_value is not None:
                if current_value < constraints.min_well_volume_ul:
                    new_value = constraints.min_well_volume_ul
                elif current_value > constraints.max_well_volume_ul:
                    new_value = constraints.max_well_volume_ul

            return (
                constraints.min_well_volume_ul,
                constraints.max_well_volume_ul,
                new_value,
                help_text,
            )

        except Exception:
            # Default to 384-well constraints on error
            constraints = PLATE_CONSTRAINTS[PlateFormat.WELL_384]
            return (
                constraints.min_well_volume_ul,
                constraints.max_well_volume_ul,
                no_update,
                "384-well plate: 20-50 µL",
            )

    @app.callback(
        [
            Output("calc-mode-store", "data"),
            Output("calc-first-experiment-wizard", "style"),
            Output("calc-main-content", "style"),
        ],
        Input("calc-project-store", "data"),
        prevent_initial_call=True,
    )
    def detect_planner_mode(project_data):
        """Detect whether to show wizard or normal planner."""
        if not project_data or not project_data.get("project_id"):
            raise PreventUpdate

        project_id = project_data["project_id"]

        try:
            mode = SmartPlannerService.detect_planner_mode(project_id)

            if mode == PlannerMode.FIRST_EXPERIMENT:
                return (
                    mode.value,
                    {"display": "block"},
                    {"display": "none"},
                )
            else:
                return (
                    mode.value,
                    {"display": "none"},
                    {"display": "block"},
                )
        except Exception:
            # Default to normal mode on error
            return (
                PlannerMode.NORMAL.value,
                {"display": "none"},
                {"display": "block"},
            )

    @app.callback(
        [
            Output("wizard-templates-list", "children"),
            Output("wizard-controls-list", "children"),
            Output("wizard-total-wells", "children"),
        ],
        Input("calc-mode-store", "data"),
        State("calc-project-store", "data"),
        prevent_initial_call=True,
    )
    def load_first_experiment_suggestion(mode, project_data):
        """Load first experiment suggestion for wizard."""
        import dash_mantine_components as dmc
        from dash import html

        if mode != PlannerMode.FIRST_EXPERIMENT.value:
            raise PreventUpdate

        if not project_data or not project_data.get("project_id"):
            raise PreventUpdate

        project_id = project_data["project_id"]

        try:
            suggestion = SmartPlannerService.get_first_experiment_suggestion(
                project_id, replicates=4
            )

            # Build templates list
            templates = []
            if suggestion.reporter_only:
                templates.append(
                    dmc.Group([
                        dmc.Checkbox(checked=True, disabled=True),
                        dmc.Text(suggestion.reporter_only.name),
                        dmc.Badge("required", size="xs", color="red"),
                        dmc.Text("4 replicates", size="sm", c="dimmed"),
                    ], gap="sm", mb="xs")
                )
            if suggestion.wildtype:
                templates.append(
                    dmc.Group([
                        dmc.Checkbox(checked=True, disabled=True),
                        dmc.Text(suggestion.wildtype.name),
                        dmc.Badge(suggestion.wildtype.family, size="xs"),
                        dmc.Text("4 replicates", size="sm", c="dimmed"),
                    ], gap="sm", mb="xs")
                )

            # Build controls list
            controls = [
                dmc.Group([
                    dmc.Checkbox(checked=True, disabled=True),
                    dmc.Text("-Template (required)"),
                    dmc.Text(f"{suggestion.negative_template_count} replicates", size="sm", c="dimmed"),
                ], gap="sm", mb="xs"),
                dmc.Group([
                    dmc.Checkbox(checked=True, disabled=True),
                    dmc.Text("-DFHBI (recommended)"),
                    dmc.Text(f"{suggestion.negative_dye_count} replicates", size="sm", c="dimmed"),
                ], gap="sm", mb="xs"),
            ]

            # Total wells
            total_wells = html.Div([
                dmc.Text("Total wells: ", span=True),
                dmc.Text(str(suggestion.total_wells), span=True, fw=600),
            ])

            return templates, controls, total_wells

        except Exception as e:
            logger.exception("Error loading first experiment suggestion")
            error_msg = dmc.Alert("An unexpected error occurred while loading the suggestion.", color="red")
            return [error_msg], [], html.Div()

    @app.callback(
        [
            Output("calc-first-experiment-wizard", "style", allow_duplicate=True),
            Output("calc-main-content", "style", allow_duplicate=True),
        ],
        [
            Input("wizard-skip-btn", "n_clicks"),
            Input("wizard-continue-btn", "n_clicks"),
        ],
        prevent_initial_call=True,
    )
    def handle_wizard_actions(skip_clicks, continue_clicks):
        """Handle wizard button clicks."""
        triggered = ctx.triggered_id
        if triggered in ["wizard-skip-btn", "wizard-continue-btn"]:
            return {"display": "none"}, {"display": "block"}
        raise PreventUpdate

    @app.callback(
        Output("rec-list-container", "children"),
        [
            Input("calc-mode-store", "data"),
            Input("calc-selected-constructs", "data"),
        ],
        State("calc-project-store", "data"),
        prevent_initial_call=True,
    )
    def load_recommendations(mode, selected_ids, project_data):
        """Load construct recommendations."""
        import dash_mantine_components as dmc
        from app.layouts.calculator import create_recommendation_card

        if mode == PlannerMode.FIRST_EXPERIMENT.value:
            raise PreventUpdate

        if not project_data or not project_data.get("project_id"):
            return dmc.Text("No project selected", c="dimmed", ta="center")

        project_id = project_data["project_id"]
        selected_ids = selected_ids or []

        try:
            recommendations = SmartPlannerService.get_recommendations(
                project_id, max_recommendations=10
            )

            if not recommendations:
                return dmc.Text(
                    "No recommendations available. Add constructs to the project first.",
                    c="dimmed",
                    ta="center",
                    py="xl"
                )

            cards = []
            for rec in recommendations:
                cards.append(
                    create_recommendation_card(
                        construct_id=rec.construct_id,
                        name=rec.name,
                        score=rec.total_score,
                        brief_reason=rec.brief_reason,
                        detailed_reason=rec.detailed_reason,
                        current_ci=rec.current_ci_width,
                        target_ci=rec.target_ci_width,
                        replicates_needed=rec.replicates_needed,
                        is_selected=rec.construct_id in selected_ids,
                        prob_meaningful=rec.prob_meaningful,
                        is_wildtype=rec.is_wildtype,
                    )
                )

            return cards

        except Exception as e:
            logger.exception("Error loading recommendations")
            return dmc.Alert("An unexpected error occurred while loading recommendations.", color="red")

    @app.callback(
        Output("calc-selected-constructs", "data"),
        Input({"type": "rec-checkbox", "id": ALL}, "checked"),
        State({"type": "rec-checkbox", "id": ALL}, "id"),
        State("calc-selected-constructs", "data"),
        prevent_initial_call=True,
    )
    def update_selected_constructs(checked_values, ids, current_selected):
        """Update selected constructs when checkboxes change."""
        if not ids:
            raise PreventUpdate

        selected = []
        for check, id_obj in zip(checked_values, ids):
            if check:
                selected.append(id_obj["id"])

        return selected

    @app.callback(
        [
            Output("selected-constructs-list", "children"),
            Output("auto-added-anchors-list", "children"),
            Output("template-progress", "value"),
            Output("template-count-text", "children"),
            Output("calc-generate-btn", "disabled"),
        ],
        Input("calc-selected-constructs", "data"),
        State("calc-project-store", "data"),
        State("replicate-count-input", "value"),
        prevent_initial_call=True,
    )
    def update_selection_display(selected_ids, project_data, replicates):
        """Update the selection panel display."""
        import dash_mantine_components as dmc
        from app.layouts.calculator import create_selected_construct_item

        if not project_data or not project_data.get("project_id"):
            raise PreventUpdate

        project_id = project_data["project_id"]
        selected_ids = selected_ids or []

        if not selected_ids:
            return (
                dmc.Text("No constructs selected", c="dimmed", ta="center", py="lg"),
                dmc.Text("Anchors will appear here", c="dimmed", size="sm", ta="center", py="sm"),
                0,
                "0/4 templates",
                True,
            )

        try:
            # Create plan to get auto-added anchors
            plan = SmartPlannerService.create_experiment_plan(
                project_id,
                selected_ids,
                replicates or 4,
            )

            # Build selected constructs list
            selected_items = []
            for c in plan.constructs:
                selected_items.append(
                    create_selected_construct_item(
                        construct_id=c.construct_id,
                        name=c.name,
                        family=c.family,
                        is_anchor=c.is_anchor,
                    )
                )

            # Build auto-added anchors list
            anchor_items = []
            for c in plan.auto_added_anchors:
                anchor_items.append(
                    create_selected_construct_item(
                        construct_id=c.construct_id,
                        name=c.name,
                        family=c.family,
                        is_anchor=True,
                    )
                )

            if not anchor_items:
                anchor_items = [
                    dmc.Text("No additional anchors needed", c="dimmed", size="sm", ta="center")
                ]

            # Template count
            total_templates = plan.total_templates
            max_templates = 4
            progress = min(100, (total_templates / max_templates) * 100)
            progress_color = "green" if total_templates <= 4 else "red"

            return (
                selected_items,
                anchor_items,
                progress,
                f"{total_templates}/{max_templates} templates",
                False,  # Enable generate button
            )

        except Exception as e:
            logger.exception("Error updating selection display")
            error = dmc.Alert("An unexpected error occurred. Please try again.", color="red")
            return (
                error,
                [],
                0,
                "0/4 templates",
                True,
            )

    @app.callback(
        [
            Output("impact-constructs", "children"),
            Output("impact-plates", "children"),
            Output("impact-precision", "children"),
            Output("impact-wells", "children"),
            Output("per-construct-impact-list", "children"),
        ],
        Input("calc-selected-constructs", "data"),
        Input("replicate-count-input", "value"),
        Input("neg-template-count", "value"),
        Input("neg-dfhbi-checkbox", "checked"),
        Input("ligand-enabled-switch", "checked"),
        State("calc-project-store", "data"),
        prevent_initial_call=True,
    )
    def update_impact_preview(selected_ids, replicates, neg_temp_count, include_dfhbi, ligand_enabled, project_data):
        """Update the impact preview panel."""
        import dash_mantine_components as dmc

        default = ("--/--", "--", "--%", "--", [])

        if not project_data or not project_data.get("project_id"):
            return default

        if not selected_ids:
            return default

        project_id = project_data["project_id"]

        try:
            impact = SmartPlannerService.calculate_impact_preview(
                project_id,
                selected_ids,
                replicates or 4,
                negative_template_count=neg_temp_count or 3,
                include_dfhbi=include_dfhbi,
            )

            # Per-construct impact list
            per_construct = []
            for item in impact.per_construct_impact:
                if item.get("improvement_pct") is not None:
                    per_construct.append(
                        dmc.Group([
                            dmc.Text(item["name"], size="sm"),
                            dmc.Text(
                                f"+-{item['current_ci']:.2f} -> +-{item['projected_ci']:.2f}",
                                size="sm",
                                c="dimmed"
                            ),
                            dmc.Badge(
                                f"+{item['improvement_pct']:.0f}%",
                                color="green",
                                size="xs"
                            ),
                        ], justify="space-between", mb="xs")
                    )
                else:
                    per_construct.append(
                        dmc.Group([
                            dmc.Text(item["name"], size="sm"),
                            dmc.Badge("New data", color="blue", size="xs"),
                        ], justify="space-between", mb="xs")
                    )

            wells = impact.total_wells_needed
            if ligand_enabled:
                wells = wells * 2
            wells_str = str(wells)
            if ligand_enabled:
                wells_str += " (2x ligand)"

            return (
                f"{impact.constructs_before}/{impact.constructs_after} (+{impact.constructs_gained})",
                f"{impact.plates_to_target_before} -> {impact.plates_to_target_after}",
                f"+{impact.precision_improvement_pct:.0f}%",
                wells_str,
                per_construct if per_construct else [dmc.Text("No impact data", c="dimmed", size="sm")],
            )

        except Exception:
            return default

    @app.callback(
        Output("neg-dfhbi-count", "disabled"),
        Input("neg-dfhbi-checkbox", "checked"),
    )
    def toggle_dfhbi_count(checked):
        """Enable/disable DFHBI count input based on checkbox."""
        return not checked

    @app.callback(
        [
            Output("ligand-stock-input", "disabled"),
            Output("ligand-final-input", "disabled"),
            Output("ligand-config-div", "style"),
            Output("ligand-well-badge", "style"),
        ],
        Input("ligand-enabled-switch", "checked"),
    )
    def toggle_ligand_controls(checked):
        """Enable/disable ligand configuration inputs."""
        if checked:
            return (
                False,
                False,
                {"display": "block"},
                {"display": "inline-block"},
            )
        return (
            True,
            True,
            {"display": "none"},
            {"display": "none"},
        )

    @app.callback(
        Output("ligand-volume-preview", "children"),
        [
            Input("ligand-stock-input", "value"),
            Input("ligand-final-input", "value"),
            Input("reaction-volume-input", "value"),
        ],
        State("ligand-enabled-switch", "checked"),
        prevent_initial_call=True,
    )
    def update_ligand_volume_preview(stock_conc, final_conc, rxn_vol, enabled):
        """Show real-time ligand volume preview with warnings."""
        import dash_mantine_components as dmc

        if not enabled or not stock_conc or not final_conc or not rxn_vol:
            return None

        stock_conc = float(stock_conc)
        final_conc = float(final_conc)
        rxn_vol = float(rxn_vol)

        if stock_conc <= 0:
            return dmc.Alert("Stock concentration must be > 0", color="red")

        lig_vol = round_volume_up((final_conc * rxn_vol) / stock_conc)

        elements = [
            dmc.Text(
                f"Ligand volume per reaction: {lig_vol:.1f} µL",
                size="sm",
                fw=500,
                mb="xs",
            )
        ]

        if lig_vol > MAX_LIGAND_VOLUME_FRACTION * rxn_vol:
            elements.append(
                dmc.Alert(
                    f"Ligand volume exceeds {MAX_LIGAND_VOLUME_FRACTION * 100:.0f}% of reaction volume. "
                    "Increase stock concentration.",
                    color="red",
                )
            )
        elif lig_vol < MIN_PIPETTABLE_VOLUME_UL:
            elements.append(
                dmc.Alert(
                    f"Volume {lig_vol:.2f} µL is below pipetting threshold ({MIN_PIPETTABLE_VOLUME_UL} µL). "
                    f"Dilute stock to increase volume.",
                    color="red",
                )
            )
        elif lig_vol < WARN_PIPETTABLE_VOLUME_UL:
            diluted = stock_conc / 2
            elements.append(
                dmc.Alert(
                    f"Volume {lig_vol:.1f} µL may reduce accuracy. "
                    f"Consider diluting stock to {diluted:.0f} µM.",
                    color="yellow",
                )
            )

        return elements

    @app.callback(
        [
            Output("calc-results-section", "style"),
            Output("calc-export-btn", "disabled"),
            Output("calc-publish-btn", "disabled"),
            Output("calc-plan-store", "data"),
            Output("master-mix-table", "children"),
            Output("dna-additions-table", "children"),
            Output("validation-messages", "children"),
            Output("protocol-text", "children"),
            Output("printable-protocol", "children"),
            Output("calc-protocol-history-select", "value"),
            Output("calc-protocol-view-modal", "opened", allow_duplicate=True),
        ],
        [
            Input("calc-generate-btn", "n_clicks"),
            Input("calc-reset-btn", "n_clicks"),
        ],
        [
            State("calc-project-store", "data"),
            State("calc-selected-constructs", "data"),
            State("replicate-count-input", "value"),
            State("reaction-volume-input", "value"),
            State("neg-template-count", "value"),
            State("neg-dfhbi-checkbox", "checked"),
            State("neg-dfhbi-count", "value"),
            State("ligand-enabled-switch", "checked"),
            State("ligand-stock-input", "value"),
            State("ligand-final-input", "value"),
            State({"type": "construct-conc-input", "id": ALL}, "value"),
            State({"type": "construct-conc-input", "id": ALL}, "id"),
        ],
        prevent_initial_call=True,
    )
    def generate_volumes_and_protocol(
        n_clicks,
        reset_clicks,
        project_data,
        selected_ids,
        replicates,
        reaction_volume,
        neg_template_count,
        include_dfhbi,
        dfhbi_count,
        ligand_enabled,
        ligand_stock,
        ligand_final,
        conc_values,
        conc_ids,
    ):
        """Generate volume calculations and protocol."""
        import dash_mantine_components as dmc
        from dash import html
        import datetime

        triggered = ctx.triggered_id

        if triggered == "calc-reset-btn":
            return (
                {"display": "none"},
                True,
                True,
                None,
                [],
                [],
                [],
                "",
                [],
                None,   # Clear protocol history select
                False,  # Close protocol view modal
            )

        if not n_clicks or not project_data or not selected_ids:
            raise PreventUpdate

        project_id = project_data["project_id"]
        
        # Get project info to validate constraints
        project_summary = SmartPlannerService.get_project_summary(project_id)
        raw_fmt = project_summary.get("plate_format", "384")
        
        # Normalize to string "384" or "96"
        # Handle different Enum classes (model vs constant) via duck typing
        if hasattr(raw_fmt, "value"):
            plate_fmt_str = str(raw_fmt.value)
        else:
            plate_fmt_str = str(raw_fmt)
            
        plate_format = PlateFormat.WELL_384 if plate_fmt_str == "384" else PlateFormat.WELL_96
        
        # Parse volume
        volume_ul = float(reaction_volume) if reaction_volume else 50.0

        # Convert volume to DNA mass for calculator (fallback for mass-based path)
        # V = Mass * 10 => Mass = V / 10
        dna_mass = volume_ul / DNA_MASS_TO_VOLUME_FACTOR
        
        # Validate volume constraints
        volume_warnings = []
        constraints = PLATE_CONSTRAINTS[plate_format]
        if volume_ul < constraints.min_well_volume_ul or volume_ul > constraints.max_well_volume_ul:
            volume_warnings.append(
                f"Reaction volume {volume_ul:.1f} µL is outside recommended range for {plate_fmt_str}-well plate "
                f"({constraints.min_well_volume_ul:.0f}-{constraints.max_well_volume_ul:.0f} µL)"
            )

        # Create map of construct ID -> concentration
        conc_map = {}
        if conc_ids and conc_values:
            for id_obj, val in zip(conc_ids, conc_values):
                if val is not None:
                    conc_map[id_obj["id"]] = float(val)

        try:
            # Create experiment plan to get ALL required constructs (selected + anchors)
            # This ensures we include auto-added controls like WT and Reporter-only
            plan = SmartPlannerService.create_experiment_plan(
                project_id=project_id,
                selected_construct_ids=selected_ids,
                replicates=replicates or 4,
                include_dfhbi=include_dfhbi
            )

            # Combine explicit selection and auto-added anchors
            all_constructs = plan.constructs + plan.auto_added_anchors

            # Build constructs list for calculator
            # Fetch plasmid_size_bp from DB for each construct
            from app.services.construct_service import ConstructService
            constructs = []
            for c in all_constructs:
                # Use user input concentration or default to 1000 ng/uL
                # Note: c has attribute construct_id, not key access
                cid = c.construct_id
                stock_conc = conc_map.get(cid, 1000.0)

                # Fetch plasmid_size_bp from database
                db_construct = ConstructService.get_construct(cid)
                plasmid_bp = db_construct.plasmid_size_bp if db_construct else None

                constructs.append({
                    "construct_id": c.construct_id,
                    "name": c.name,
                    "stock_concentration_ng_ul": stock_conc,
                    "is_wildtype": c.is_wildtype,
                    "is_unregulated": c.is_unregulated,
                    "family": c.family,
                    "replicates": replicates or 4,
                    "plasmid_size_bp": plasmid_bp,
                })

            # Build ligand config
            ligand_cfg = None
            ligand_multiplier = 1
            if ligand_enabled:
                ligand_cfg = LigandConfig(
                    enabled=True,
                    stock_concentration_uM=float(ligand_stock) if ligand_stock else 1000.0,
                    final_concentration_uM=float(ligand_final) if ligand_final else 100.0,
                )
                ligand_multiplier = 2

            # Calculate total reactions
            n_reactions = len(constructs) * (replicates or 4)
            n_reactions += neg_template_count or 3
            if include_dfhbi:
                n_reactions += dfhbi_count or 2
            n_reactions *= ligand_multiplier

            # Calculate master mix with nM-based DNA targeting
            mm = calculate_master_mix(
                n_reactions=n_reactions,
                constructs=constructs,
                dna_mass_ug=dna_mass,
                negative_template_count=neg_template_count or 3,
                negative_dye_count=dfhbi_count or 2 if include_dfhbi else 0,
                reaction_volume_ul=volume_ul,
                target_dna_nM=TARGET_DNA_CONCENTRATION_NM,
                ligand_config=ligand_cfg,
            )
            
            # Check for low pipetting volumes requiring dilution
            dilution_alerts = []
            for addition in mm.dna_additions:
                if addition.requires_dilution:
                    # Extract the suggestion from the warning
                    suggestion = addition.warning.split("; ")[-1] if addition.warning else "Consult lab manual"
                    dilution_alerts.append(
                        dmc.Alert(
                            children=[
                                dmc.Text(f"Construct: {addition.construct_name}", fw=700),
                                dmc.Text(suggestion),
                            ],
                            title="Dilution Required",
                            color="red",
                            mb="sm"
                        )
                    )
            
            if dilution_alerts:
                dilution_banner = dmc.Stack([
                    dmc.Alert(
                        "Pipetting volumes < 0.5 µL detected. Accurately pipetting these small volumes is unreliable.",
                        title="Unsafe Pipetting Volumes",
                        color="red",
                        variant="filled",
                        mb="md"
                    ),
                    dmc.Text(
                        "Please dilute the following DNA samples to eliminate the need for tiny water additions:",
                        mb="sm"
                    ),
                    *dilution_alerts,
                    dmc.Text(
                        "After diluting, update the stock concentration in the inputs above and regenerate.",
                        c="dimmed",
                        fs="italic",
                        mt="md"
                    )
                ])
                
                return (
                    {"display": "block"},
                    True,  # Disable export button
                    True,  # Disable publish button
                    None,  # No plan data
                    dilution_banner,  # Display banner in MM Table slot
                    [],  # Empty DNA table
                    [],  # Empty validation
                    "Protocol generation paused due to safe pipetting violation.",  # Text placeholder
                    [],  # Empty printable
                    no_update,  # Keep protocol history select
                    no_update,  # Keep protocol view modal
                )

            # Inject validation warnings
            mm.warnings.extend(volume_warnings)

            # Generate protocol
            protocol = generate_protocol(mm, title="IVT Reaction Setup")
            protocol_text = format_protocol_text(protocol)

            # Format master mix table
            mm_table = dmc.Table(
                data={
                    "head": ["Component", "Stock Conc.", "Per Rxn (µL)", "Total (µL)"],
                    "body": [
                        [
                            c.name,
                            f"{c.stock_concentration} {c.stock_unit}",
                            f"{c.single_reaction_volume_ul:.2f}",
                            f"{c.master_mix_volume_ul:.1f}"
                        ]
                        for c in mm.components
                    ]
                },
                striped=True,
                highlightOnHover=True,
            )

            # Format DNA additions table
            has_ligand_conditions = any(
                add.ligand_condition for add in mm.dna_additions
            )
            dna_rows = []
            for addition in mm.dna_additions:
                # Format cells
                # Construct Name
                name_cell = addition.construct_name

                # Stock Conc
                stock_cell = f"{addition.stock_concentration_ng_ul:.0f}" if addition.stock_concentration_ng_ul > 0 else "-"

                # DNA Volume
                dna_cell = f"{addition.dna_volume_ul:.1f}" if addition.dna_volume_ul > 0 else "-"

                # Water Volume
                water_cell = f"{addition.water_adjustment_ul:.1f}"

                # Total Volume
                total_cell = f"{addition.total_addition_ul:.1f}"

                row = [name_cell]
                if has_ligand_conditions:
                    row.append(addition.ligand_condition or "-")
                row.extend([stock_cell, dna_cell, water_cell, total_cell])

                dna_rows.append(row)

            dna_head = ["Construct"]
            if has_ligand_conditions:
                dna_head.append("Condition")
            dna_head.extend(["Stock (ng/µL)", "DNA (µL)", "Water (µL)", "Total (µL)"])

            dna_table = dmc.Table(
                data={
                    "head": dna_head,
                    "body": dna_rows,
                },
                striped=True,
                highlightOnHover=True,
            ) if dna_rows else dmc.Text("No DNA additions", c="dimmed")

            # === Comprehensive Validation Tab ===
            validation_sections = []

            # --- Section 0: Calculator Warnings (volume constraints, etc.) ---
            all_warnings = mm.warnings + (mm.errors if mm.errors else [])
            if all_warnings:
                warn_children = [dmc.Text(w) for w in all_warnings]
                validation_sections.append(
                    dmc.Stack([
                        dmc.Text("Calculator Warnings", fw=700, size="lg"),
                        dmc.Alert(
                            children=warn_children,
                            color="yellow" if not mm.errors else "red",
                            title="Warnings" if not mm.errors else "Errors & Warnings",
                        ),
                    ], gap="xs")
                )

            # --- Section 1: Master Mix Component Verification ---
            # Build formula lookup from STANDARD_COMPONENTS
            formula_map = {sc.name: sc.volume_formula for sc in STANDARD_COMPONENTS}

            v_rxn = mm.single_reaction.reaction_volume_ul
            comp_rows = []
            for comp in mm.components:
                # Per-rxn is now precise (unrounded); MM total is what's actually pipetted
                precise_vol = comp.single_reaction_volume_ul
                # Effective per-rxn = actual pipetted MM total / n_effective
                effective_per_rxn = comp.master_mix_volume_ul / mm.n_effective if mm.n_effective > 0 else precise_vol

                # Back-calculate final concentration from effective per-rxn volume
                if comp.stock_concentration > 0 and v_rxn > 0:
                    back_calc_final = (effective_per_rxn / v_rxn) * comp.stock_concentration
                    deviation_pct = ((back_calc_final - comp.final_concentration) / comp.final_concentration * 100
                                     if comp.final_concentration > 0 else 0.0)
                    back_calc_str = f"{back_calc_final:.4f} {comp.final_unit}"
                    dev_str = f"{deviation_pct:+.2f}%"
                else:
                    # Water — no concentration to back-calculate
                    back_calc_str = "-"
                    dev_str = "-"

                formula = formula_map.get(comp.name, "-")
                stock_str = f"{comp.stock_concentration} {comp.stock_unit}" if comp.stock_concentration > 0 else "-"
                target_str = f"{comp.final_concentration} {comp.final_unit}" if comp.final_concentration > 0 else "-"

                comp_rows.append([
                    comp.name,
                    stock_str,
                    target_str,
                    formula,
                    f"{precise_vol:.4f}",
                    f"{comp.master_mix_volume_ul:.1f}",
                    back_calc_str,
                    dev_str,
                ])

            comp_table = dmc.Table(
                data={
                    "head": [
                        "Component", "Stock", "Target Final", "Formula",
                        "Per Rxn (µL)", "MM Total (µL)",
                        "Back-Calc Final", "Deviation",
                    ],
                    "body": comp_rows,
                },
                striped=True,
                highlightOnHover=True,
                withTableBorder=True,
                style={"fontSize": "0.85rem"},
            )
            validation_sections.append(
                dmc.Stack([
                    dmc.Text("Master Mix Component Verification", fw=700, size="lg"),
                    dmc.Text(
                        f"Reaction volume: {v_rxn:.1f} µL | "
                        f"Overage: {(mm.overage_factor - 1) * 100:.0f}% | "
                        f"N effective: {mm.n_effective:.1f}",
                        size="sm", c="dimmed",
                    ),
                    comp_table,
                ], gap="xs")
            )

            # --- Section 2: DNA Additions Verification ---
            if mm.dna_additions:
                has_ligand = any(a.ligand_condition for a in mm.dna_additions)
                has_nM = any(a.achieved_nM is not None for a in mm.dna_additions if not a.is_negative_control)

                dna_v_head = ["Construct"]
                if has_ligand:
                    dna_v_head.append("Condition")
                dna_v_head.extend(["Stock (ng/µL)", "DNA Vol (µL)", "Water Adj (µL)", "Total (µL)"])
                if has_nM:
                    dna_v_head.extend(["Target nM", "Achieved nM"])

                dna_v_rows = []
                for a in mm.dna_additions:
                    row = [a.construct_name]
                    if has_ligand:
                        row.append(a.ligand_condition or "-")

                    if a.is_negative_control and a.stock_concentration_ng_ul == 0:
                        row.extend(["-", "-", f"{a.water_adjustment_ul:.1f}", f"{a.total_addition_ul:.1f}"])
                    else:
                        row.extend([
                            f"{a.stock_concentration_ng_ul:.0f}",
                            f"{a.dna_volume_ul:.1f}",
                            f"{a.water_adjustment_ul:.1f}",
                            f"{a.total_addition_ul:.1f}",
                        ])

                    if has_nM:
                        target_nM_str = f"{TARGET_DNA_CONCENTRATION_NM:.0f}" if not a.is_negative_control or a.negative_control_type == 'no_dye' else "-"
                        achieved_nM_str = f"{a.achieved_nM:.1f}" if a.achieved_nM is not None else "-"
                        row.extend([target_nM_str, achieved_nM_str])

                    dna_v_rows.append(row)

                dna_v_table = dmc.Table(
                    data={"head": dna_v_head, "body": dna_v_rows},
                    striped=True,
                    highlightOnHover=True,
                    withTableBorder=True,
                    style={"fontSize": "0.85rem"},
                )
                validation_sections.append(
                    dmc.Stack([
                        dmc.Text("DNA Additions Verification", fw=700, size="lg", mt="md"),
                        dna_v_table,
                    ], gap="xs")
                )

            # --- Section 3: Ligand Verification (conditional) ---
            if mm.is_ligand_workflow and mm.ligand_config:
                lig = mm.ligand_config
                lig_vol = mm.ligand_volume_per_rxn_ul
                # Back-calculate actual final concentration from rounded volume
                lig_back_calc = (lig_vol / v_rxn) * lig.stock_concentration_uM if v_rxn > 0 else 0.0
                lig_deviation = ((lig_back_calc - lig.final_concentration_uM) / lig.final_concentration_uM * 100
                                 if lig.final_concentration_uM > 0 else 0.0)

                lig_rows = [
                    ["Stock concentration", f"{lig.stock_concentration_uM:.1f} µM"],
                    ["Target final", f"{lig.final_concentration_uM:.1f} µM"],
                    ["Volume per rxn", f"{lig_vol:.1f} µL"],
                    ["Back-calc final", f"{lig_back_calc:.2f} µM"],
                    ["Deviation", f"{lig_deviation:+.2f}%"],
                ]
                lig_table = dmc.Table(
                    data={"head": ["Parameter", "Value"], "body": lig_rows},
                    striped=True,
                    highlightOnHover=True,
                    withTableBorder=True,
                    style={"fontSize": "0.85rem", "maxWidth": "400px"},
                )
                validation_sections.append(
                    dmc.Stack([
                        dmc.Text("Ligand Verification", fw=700, size="lg", mt="md"),
                        lig_table,
                    ], gap="xs")
                )

            # --- Section 4: Construct Validation (existing pass/fail) ---
            validation = validate_construct_list(constructs)
            if validation.is_valid:
                construct_validation = dmc.Alert(
                    "All construct parameters validated successfully",
                    color="green",
                    title="Construct Validation Passed",
                )
            else:
                alert_children = []
                if validation.errors:
                    alert_children.append(
                        dmc.Alert(
                            children=[dmc.Text(msg.message) for msg in validation.errors],
                            color="red",
                            title="Validation Errors",
                        )
                    )
                if validation.warnings:
                    alert_children.append(
                        dmc.Alert(
                            children=[dmc.Text(msg.message) for msg in validation.warnings],
                            color="yellow",
                            title="Warnings",
                        )
                    )
                construct_validation = dmc.Stack(alert_children)

            validation_sections.append(
                dmc.Stack([
                    dmc.Text("Construct Validation", fw=700, size="lg", mt="md"),
                    construct_validation,
                ], gap="xs")
            )

            validation_display = dmc.Stack(validation_sections, gap="md")

            # Store enriched plan data for export
            # We need component-level details for plate layout generation
            plan_data = {
                "project_id": project_id,
                "created_at": datetime.datetime.now().isoformat(),
                "parameters": {
                    "replicates": replicates,
                    "reaction_volume_ul": volume_ul,
                    "negative_template_count": neg_template_count,
                    "negative_dfhbi_count": dfhbi_count if include_dfhbi else 0,
                    "include_dfhbi": include_dfhbi,
                    "total_reactions": n_reactions,
                    "ligand_enabled": bool(ligand_enabled),
                    "ligand_stock_uM": float(ligand_stock) if ligand_enabled and ligand_stock else None,
                    "ligand_final_uM": float(ligand_final) if ligand_enabled and ligand_final else None,
                },
                "constructs": [
                    {
                        "id": c.get("construct_id"),
                        "name": c["name"],
                        "family": c.get("family"),
                        "is_wildtype": c.get("is_wildtype"),
                        "is_unregulated": c.get("is_unregulated"),
                        "stock_conc": c.get("stock_concentration_ng_ul"),
                        "plasmid_size_bp": c.get("plasmid_size_bp"),
                    }
                    for c in constructs
                ],
                # Add full component list from Master Mix for verification
                "master_mix_components": [
                    {
                        "name": comp.name,
                        "volume_per_rxn": comp.single_reaction_volume_ul,
                        "total_volume": comp.master_mix_volume_ul
                    }
                    for comp in mm.components
                ],
                # DNA additions with ligand conditions and nM targeting data
                "dna_additions": [
                    {
                        "construct_name": a.construct_name,
                        "construct_id": a.construct_id,
                        "stock_concentration_ng_ul": a.stock_concentration_ng_ul,
                        "dna_volume_ul": a.dna_volume_ul,
                        "water_adjustment_ul": a.water_adjustment_ul,
                        "total_addition_ul": a.total_addition_ul,
                        "replicates": a.replicates,
                        "is_negative_control": a.is_negative_control,
                        "negative_control_type": a.negative_control_type,
                        "source_construct_name": a.source_construct_name,
                        "ligand_condition": a.ligand_condition,
                        "stock_concentration_nM": a.stock_concentration_nM,
                        "plasmid_size_bp": a.plasmid_size_bp,
                        "achieved_nM": a.achieved_nM,
                    }
                    for a in mm.dna_additions
                ],
            }

            # Generate printable HTML with checkboxes
            printable_html = _generate_printable_protocol_html(protocol, mm)

            return (
                {"display": "block"},
                False,  # Enable export button
                False,  # Enable publish button
                plan_data,
                mm_table,
                dna_table,
                validation_display,
                protocol_text,
                printable_html,
                no_update,  # Keep protocol history select
                no_update,  # Keep protocol view modal
            )

        except Exception as e:
            logger.exception("Error generating protocol")
            error = dmc.Alert("An unexpected error occurred while generating the protocol. Please try again.", color="red")
            return (
                {"display": "block"},
                True,  # Disable export button on error
                True,  # Disable publish button on error
                None,
                error,
                [],
                [],
                "",
                [],  # Empty printable protocol
                no_update,  # Keep protocol history select
                no_update,  # Keep protocol view modal
            )

    # Shared print-to-PDF JS function (used by both live and history print buttons)
    _print_js_template = """
        function(print_clicks) {{
            if (!print_clicks) {{
                return window.dash_clientside.no_update;
            }}
            var printContent = document.getElementById('{element_id}');
            if (!printContent || !printContent.innerHTML.trim()) {{
                alert('{empty_msg}');
                return window.dash_clientside.no_update;
            }}
            var css = {css_json};
            var printWindow = window.open('', '_blank', 'width=800,height=600');
            printWindow.document.write(
                '<!DOCTYPE html><html><head><title>IVT Pipetting Protocol</title>' +
                '<style>' + css + '</style></head><body>' +
                printContent.innerHTML +
                '<div class="footer">Generated by IVT Kinetics Analyzer</div>' +
                '</body></html>'
            );
            printWindow.document.close();
            printWindow.onload = function() {{ printWindow.print(); }};
            return window.dash_clientside.no_update;
        }}
    """
    _css_json = json.dumps(_PRINT_CSS)

    # Clientside callback to trigger browser print (live protocol)
    app.clientside_callback(
        _print_js_template.format(
            element_id="printable-protocol",
            empty_msg="Please generate a protocol first by selecting constructs and clicking Calculate.",
            css_json=_css_json,
        ),
        Output("printable-protocol", "className"),  # Dummy output
        Input("print-protocol-btn", "n_clicks"),
        prevent_initial_call=True,
    )


    @app.callback(
        Output({"type": "rec-details", "id": MATCH}, "opened"),
        Input({"type": "rec-expand", "id": MATCH}, "n_clicks"),
        State({"type": "rec-details", "id": MATCH}, "opened"),
        prevent_initial_call=True,
    )
    def toggle_recommendation_details(n_clicks, is_opened):
        """Toggle the expanded details view for a recommendation card (F4.1)."""
        if n_clicks is None:
            raise PreventUpdate
        return not is_opened

    @app.callback(
        [
            Output("wizard-continue-btn", "children"),
            Output("calc-selected-constructs", "data", allow_duplicate=True),
        ],
        Input("wizard-test-mutants-checkbox", "checked"),
        State("calc-project-store", "data"),
        prevent_initial_call=True,
    )
    def handle_test_mutants_checkbox(checked, project_data):
        """Handle the 'test mutants' checkbox in First Experiment Wizard (F4.7).

        When checked, changes button text and pre-selects all untested mutants.
        """
        if not project_data or not project_data.get("project_id"):
            raise PreventUpdate

        if checked:
            # Get all untested mutants and select them
            try:
                project_id = project_data["project_id"]
                stats = SmartPlannerService.get_construct_stats(
                    project_id, uploaded_only=False
                )
                # Select all non-anchor constructs that don't have data
                mutant_ids = [
                    s.construct_id for s in stats
                    if not s.is_wildtype and not s.is_unregulated and not s.has_data
                ]
                return "Continue with All Constructs", mutant_ids
            except Exception:
                return "Continue with WT Setup", []
        else:
            return "Continue with WT Setup", []

    @app.callback(
        [
            Output("dfhbi-recommendation-badge", "children"),
            Output("dfhbi-recommendation-reason", "children"),
        ],
        Input("calc-project-store", "data"),
    )
    def update_dfhbi_recommendation(project_data):
        """Update -DFHBI control recommendation display (F4.5)."""
        import dash_mantine_components as dmc

        default_badge = dmc.Badge("Optional", color="gray", size="sm")
        default_reason = dmc.Text(
            "No recent -DFHBI control data available to assess.",
            size="sm", c="dimmed"
        )

        if not project_data or not project_data.get("project_id"):
            return default_badge, default_reason

        try:
            project_id = project_data["project_id"]

            # Get DFHBI recommendation from service
            recent_controls = SmartPlannerService._get_recent_dfhbi_controls(project_id)
            typical_fmax = SmartPlannerService._get_typical_fmax(project_id)

            from app.calculator import recommend_dfhbi_controls, RecommendationConfidence
            rec = recommend_dfhbi_controls(recent_controls, typical_fmax)

            # Build badge based on confidence
            if rec.confidence == RecommendationConfidence.REQUIRED:
                badge = dmc.Badge("Recommended", color="blue", size="sm")
            elif rec.confidence == RecommendationConfidence.RECOMMENDED:
                badge = dmc.Badge("Recommended", color="yellow", size="sm")
            else:
                badge = dmc.Badge("Optional", color="gray", size="sm")

            # Build reason text
            reason = dmc.Text(rec.reason, size="sm")

            return badge, reason

        except Exception:
            return default_badge, default_reason

    @app.callback(
        Output("replicate-alert", "children"),
        [
            Input("replicate-count-input", "value"),
            Input("calc-selected-constructs", "data"),
        ],
        State("calc-project-store", "data"),
        prevent_initial_call=True,
    )
    def update_replicate_recommendation(replicates, selected_ids, project_data):
        """Update replicate recommendation based on selected constructs (F4.8)."""
        import dash_mantine_components as dmc

        if not project_data or not project_data.get("project_id"):
            return dmc.Text("4 replicates is the standard starting point", size="sm")

        if not selected_ids:
            return dmc.Text("4 replicates is the standard starting point", size="sm")

        replicates = replicates or 4

        try:
            project_id = project_data["project_id"]
            stats = SmartPlannerService.get_construct_stats(project_id, uploaded_only=False)
            selected_stats = [s for s in stats if s.construct_id in selected_ids]

            # Check if any construct has existing data with poor precision
            from app.calculator import calculate_sample_size_for_precision, DEFAULT_PRECISION_TARGET

            needs_more = []
            for s in selected_stats:
                if s.ci_width and s.ci_width > DEFAULT_PRECISION_TARGET:
                    result = calculate_sample_size_for_precision(
                        s.ci_width, s.replicate_count, DEFAULT_PRECISION_TARGET
                    )
                    if result.additional_needed > replicates:
                        needs_more.append((s.name, result.additional_needed))

            if needs_more:
                msg = f"Some constructs may benefit from more replicates for target precision"
                return dmc.Text(msg, size="sm", c="orange")
            elif replicates < 4:
                return dmc.Text("Minimum 4 replicates required for reliable statistics", size="sm", c="red")
            else:
                return dmc.Text(f"{replicates} replicates provides good statistical power", size="sm")

        except Exception:
            return dmc.Text("4 replicates is the standard starting point", size="sm")

    @app.callback(
        Output("export-plan-download", "data"),
        Input("calc-export-btn", "n_clicks"),
        State("calc-plan-store", "data"),
        prevent_initial_call=True,
    )
    def export_experiment_plan(n_clicks, plan_data):
        """Export the experiment plan as JSON."""
        if not n_clicks or not plan_data:
            raise PreventUpdate

        import json
        from dash import dcc
        import datetime

        # Generate filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"IVT_Experiment_Plan_{timestamp}.json"

        return dcc.send_string(
            json.dumps(plan_data, indent=2),
            filename=filename
        )

    # ==================== Protocol History Callbacks ====================

    @app.callback(
        [
            Output("calc-protocol-history-select", "data"),
            Output("calc-protocol-history-select", "style"),
        ],
        Input("calc-project-store", "data"),
    )
    def load_protocol_history(project_data):
        """Load published protocols list for the dropdown."""
        hidden = {"display": "none"}
        if not project_data or not project_data.get("project_id"):
            return [], hidden

        project_id = project_data["project_id"]

        try:
            from app.services.reaction_calculator_service import CalculatorService
            setups = CalculatorService.list_reaction_setups(project_id)
            select_options, style = _build_protocol_select_options(setups)
            return select_options, style

        except Exception:
            logger.exception("Error loading protocol history")
            return [], hidden

    @app.callback(
        [
            Output("calc-protocol-view-modal", "opened"),
            Output("calc-protocol-view-modal", "title"),
            Output("calc-protocol-view-content", "children"),
            Output("calc-history-printable-protocol", "children"),
            Output("calc-viewed-protocol-id", "data"),
        ],
        Input("calc-protocol-history-select", "value"),
        State("calc-project-store", "data"),
        prevent_initial_call=True,
    )
    def view_published_protocol(setup_id, project_data):
        """Open modal with the selected protocol's details and printable HTML."""
        import dash_mantine_components as dmc
        from dash import html

        if not setup_id:
            return False, no_update, no_update, no_update, None

        project_id = project_data.get("project_id") if project_data else None

        try:
            from app.services.reaction_calculator_service import CalculatorService
            setup = CalculatorService.get_reaction_setup(int(setup_id))

            if not setup or (project_id and setup.project_id != project_id):
                return False, no_update, no_update, no_update, None

            date_str = setup.created_at.strftime("%Y-%m-%d %H:%M") if setup.created_at else "N/A"
            created_by = setup.created_by or "N/A"

            content = dmc.Stack([
                dmc.SimpleGrid(
                    cols=2,
                    spacing="sm",
                    children=[
                        html.Div([
                            dmc.Text("Created", size="xs", c="dimmed"),
                            dmc.Text(date_str, size="sm", fw=500),
                        ]),
                        html.Div([
                            dmc.Text("Created by", size="xs", c="dimmed"),
                            dmc.Text(created_by, size="sm", fw=500),
                        ]),
                        html.Div([
                            dmc.Text("Constructs", size="xs", c="dimmed"),
                            dmc.Text(str(setup.n_constructs), size="sm", fw=500),
                        ]),
                        html.Div([
                            dmc.Text("Replicates", size="xs", c="dimmed"),
                            dmc.Text(str(setup.n_replicates), size="sm", fw=500),
                        ]),
                    ],
                    mb="md",
                ),
                dmc.Divider(),
                dmc.Text("Protocol", size="sm", fw=500, mt="sm"),
                dmc.Code(
                    children=setup.protocol_text or "No protocol text stored.",
                    block=True,
                    style={
                        "whiteSpace": "pre-wrap",
                        "maxHeight": "400px",
                        "overflow": "auto",
                    },
                ),
            ], gap="xs")

            # Build printable HTML from stored data
            printable_elements = _build_printable_from_setup(setup)

            return True, setup.name, content, printable_elements, int(setup_id)

        except Exception:
            logger.exception("Error loading protocol details")
            return False, no_update, no_update, no_update, None

    @app.callback(
        Output("calc-history-export-download", "data"),
        Input("calc-history-export-btn", "n_clicks"),
        [
            State("calc-viewed-protocol-id", "data"),
            State("calc-project-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def export_history_protocol_json(n_clicks, setup_id, project_data):
        """Export a published protocol as JSON."""
        if not n_clicks or not setup_id:
            raise PreventUpdate

        import datetime as _dt
        from app.services.reaction_calculator_service import CalculatorService
        from dash import dcc

        try:
            sid = int(setup_id)
        except (ValueError, TypeError):
            raise PreventUpdate

        project_id = project_data.get("project_id") if project_data else None

        setup = CalculatorService.get_reaction_setup(sid)
        if not setup or (project_id and setup.project_id != project_id):
            raise PreventUpdate

        # Compute total reactions
        n_reactions = (
            setup.n_reactions
            if setup.n_reactions is not None
            else (
                (setup.n_constructs or 0) * (setup.n_replicates or 0)
                + (setup.n_negative_template or 0)
                + (setup.n_negative_dye or 0)
            )
        )

        dna_additions = setup.dna_additions or []

        # Detect ligand workflow from stored fields or dna_additions
        has_ligand = bool(setup.ligand_final_concentration_um) or any(
            a.ligand_condition for a in dna_additions
        )

        # Build constructs array from DNA additions (non-negative, deduplicated)
        seen_constructs = {}
        for a in dna_additions:
            if a.is_negative_control or a.construct_name in seen_constructs:
                continue
            construct = a.construct if a.construct_id else None
            seen_constructs[a.construct_name] = {
                "id": a.construct_id,
                "name": a.construct_name,
                "family": getattr(construct, 'family', None) if construct else None,
                "is_wildtype": getattr(construct, 'is_wildtype', False) if construct else False,
                "is_unregulated": getattr(construct, 'is_unregulated', False) if construct else False,
                "stock_conc": a.dna_stock_concentration_ng_ul,
                "plasmid_size_bp": a.plasmid_size_bp,
            }

        # Build master_mix_components in flat array format
        mm_components = []
        if setup.master_mix_volumes:
            for name, vol in setup.master_mix_volumes.items():
                if isinstance(vol, dict):
                    mm_components.append({
                        "name": name,
                        "volume_per_rxn": vol.get('single_ul', 0),
                        "total_volume": vol.get('total_ul', 0),
                    })
                else:
                    # Legacy entries stored as bare numbers — no per-rxn breakdown
                    mm_components.append({
                        "name": name,
                        "volume_per_rxn": None,
                        "total_volume": vol if isinstance(vol, (int, float)) else 0,
                    })

        plan_data = {
            "project_id": setup.project_id,
            "created_at": setup.created_at.isoformat() if setup.created_at else None,
            "parameters": {
                "replicates": setup.n_replicates,
                "reaction_volume_ul": setup.total_reaction_volume_ul,
                "negative_template_count": setup.n_negative_template or 0,
                "negative_dfhbi_count": setup.n_negative_dye or 0,
                "include_dfhbi": bool(setup.include_negative_dye),
                "total_reactions": n_reactions,
                "ligand_enabled": has_ligand,
                "ligand_stock_uM": setup.ligand_stock_concentration_um,
                "ligand_final_uM": setup.ligand_final_concentration_um,
            },
            "constructs": list(seen_constructs.values()),
            "master_mix_components": mm_components,
            "dna_additions": [
                {
                    "construct_name": a.construct_name,
                    "construct_id": a.construct_id,
                    "stock_concentration_ng_ul": a.dna_stock_concentration_ng_ul,
                    "stock_concentration_nM": a.stock_concentration_nM,
                    "plasmid_size_bp": a.plasmid_size_bp,
                    "achieved_nM": a.achieved_nM,
                    "dna_volume_ul": a.dna_volume_ul,
                    "water_adjustment_ul": a.water_adjustment_ul,
                    "total_addition_ul": a.total_addition_ul,
                    "replicates": setup.n_replicates,
                    "is_negative_control": a.is_negative_control,
                    "negative_control_type": a.negative_control_type,
                    "ligand_condition": a.ligand_condition,
                }
                for a in dna_additions
            ],
        }

        safe_name = re.sub(r'[^\w\-]', '_', setup.name.strip())
        timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Protocol_{safe_name}_{timestamp}.json"

        return dcc.send_string(
            json.dumps(plan_data, indent=2),
            filename=filename,
        )

    # Clientside callback to trigger print from protocol history view
    app.clientside_callback(
        _print_js_template.format(
            element_id="calc-history-printable-protocol",
            empty_msg="No protocol content available to print.",
            css_json=_css_json,
        ),
        Output("calc-history-printable-protocol", "className"),  # Dummy output
        Input("calc-history-print-btn", "n_clicks"),
        prevent_initial_call=True,
    )

    # ==================== Publish Protocol Callbacks ====================

    @app.callback(
        Output("calc-publish-modal", "opened"),
        [
            Input("calc-publish-btn", "n_clicks"),
            Input("calc-publish-cancel-btn", "n_clicks"),
        ],
        State("calc-publish-modal", "opened"),
        prevent_initial_call=True,
    )
    def toggle_publish_modal(publish_clicks, cancel_clicks, currently_open):
        """Open/close the publish modal."""
        triggered = ctx.triggered_id
        if triggered == "calc-publish-btn":
            return True
        elif triggered == "calc-publish-cancel-btn":
            return False
        return currently_open

    @app.callback(
        [
            Output("calc-publish-modal", "opened", allow_duplicate=True),
            Output("calc-notification-container", "children"),
            Output("calc-publish-feedback", "children"),
            Output("calc-protocol-history-select", "data", allow_duplicate=True),
            Output("calc-protocol-history-select", "style", allow_duplicate=True),
        ],
        Input("calc-publish-confirm-btn", "n_clicks"),
        [
            State("calc-project-store", "data"),
            State("calc-plan-store", "data"),
            State("calc-publish-name", "value"),
            State("calc-publish-notes", "value"),
            State("replicate-count-input", "value"),
        ],
        prevent_initial_call=True,
    )
    def publish_protocol_to_database(n_clicks, project_data, plan_data, name, notes, replicates):
        """Save the protocol to the database."""
        import dash_mantine_components as dmc
        from dash_iconify import DashIconify
        from app.services.reaction_calculator_service import CalculatorService
        from app.models import AuditLog

        if not n_clicks:
            raise PreventUpdate

        # Validate inputs
        if not project_data or not project_data.get("project_id"):
            feedback = dmc.Alert(
                "Project not found",
                color="red",
                icon=DashIconify(icon="mdi:alert-circle", width=20),
            )
            return no_update, None, feedback, no_update, no_update

        if not plan_data:
            feedback = dmc.Alert(
                "No protocol generated. Please generate a protocol first.",
                color="red",
                icon=DashIconify(icon="mdi:alert-circle", width=20),
            )
            return no_update, None, feedback, no_update, no_update

        if not name or not name.strip():
            feedback = dmc.Alert(
                "Please enter a protocol name",
                color="red",
                icon=DashIconify(icon="mdi:alert-circle", width=20),
            )
            return no_update, None, feedback, no_update, no_update

        project_id = project_data["project_id"]

        try:
            # Get construct data from plan
            constructs = plan_data.get("constructs", [])
            params = plan_data.get("parameters", {})

            # Build construct list for calculator (include plasmid_size_bp for nM targeting)
            construct_list = []
            for c in constructs:
                construct_list.append({
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "family": c.get("family"),
                    "is_wildtype": c.get("is_wildtype", False),
                    "is_unregulated": c.get("is_unregulated", False),
                    "stock_concentration_ng_ul": c.get("stock_conc", 100.0),
                    "replicates": params.get("replicates", 4),
                    "plasmid_size_bp": c.get("plasmid_size_bp"),
                })

            # Calculate volumes
            n_reactions = params.get("total_reactions", len(constructs) * params.get("replicates", 4))
            reaction_volume = params.get("reaction_volume_ul", 50.0)
            dna_mass = reaction_volume / DNA_MASS_TO_VOLUME_FACTOR

            # Build ligand config if enabled
            ligand_cfg = None
            if params.get("ligand_enabled"):
                ligand_cfg = LigandConfig(
                    enabled=True,
                    stock_concentration_uM=params.get("ligand_stock_uM") or 1000.0,
                    final_concentration_uM=params.get("ligand_final_uM") or 100.0,
                )

            mm = calculate_master_mix(
                n_reactions=n_reactions,
                dna_mass_ug=dna_mass,
                overage_percent=DEFAULT_OVERAGE_PERCENT,
                constructs=construct_list,
                negative_template_count=params.get("negative_template_count", 2),
                negative_dye_count=params.get("negative_dfhbi_count", 0),
                include_dye=params.get("include_dfhbi", True),
                reaction_volume_ul=reaction_volume,
                target_dna_nM=TARGET_DNA_CONCENTRATION_NM,
                ligand_config=ligand_cfg,
            )

            # Generate protocol text
            protocol = generate_protocol(mm, title=name.strip(), created_by="user")
            protocol_text = format_protocol_text(protocol)

            # Save to database using the service
            setup = CalculatorService.save_reaction_setup(
                project_id=project_id,
                calculation=mm,
                name=name.strip(),
                n_replicates=params.get("replicates", 4),
                created_by="user",
            )

            # Log to audit trail
            AuditLog.log_action(
                username="user",
                action_type="create",
                entity_type="reaction_setup",
                entity_id=setup.id,
                project_id=project_id,
                changes=[
                    {"field": "name", "old": None, "new": name.strip()},
                    {"field": "n_constructs", "old": None, "new": len(constructs)},
                    {"field": "n_reactions", "old": None, "new": n_reactions},
                    {"field": "protocol_published", "old": None, "new": True},
                ]
            )

            # Success notification
            notification = dmc.Alert(
                f"Protocol '{name.strip()}' published successfully!",
                title="Published",
                color="green",
                icon=DashIconify(icon="mdi:check-circle", width=20),
                withCloseButton=True,
                style={"marginBottom": "1rem"},
            )

            # Refresh the protocol history dropdown
            all_setups = CalculatorService.list_reaction_setups(project_id)
            new_select_options, style = _build_protocol_select_options(all_setups)

            return (
                False, notification, None,
                new_select_options, style,
            )

        except ValueError as e:
            logger.warning("Protocol publish validation error", error=str(e))
            feedback = dmc.Alert(
                str(e),
                color="red",
                icon=DashIconify(icon="mdi:alert-circle", width=20),
            )
            return no_update, None, feedback, no_update, no_update

        except Exception as e:
            logger.exception("Error publishing protocol")
            feedback = dmc.Alert(
                "An unexpected error occurred while publishing the protocol. Please try again.",
                color="red",
                icon=DashIconify(icon="mdi:alert-circle", width=20),
            )
            return no_update, None, feedback, no_update, no_update
