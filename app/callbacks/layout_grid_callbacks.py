"""
Layout grid callbacks for plate template editor well selection and grid interactions.

Extracted from layout_callbacks.py during Phase 4 refactoring.

Provides:
- Clientside callback for well click tracking with shift key state
- Well click handling and selection management
- Selection helpers (row, column, all)
- Grid visual updates
- Assignment exclusivity enforcement
- Layout toggle and pattern selector
- Layout editor initialization
"""
from dash import callback_context, Input, Output, State, no_update
from dash.exceptions import PreventUpdate
import dash_mantine_components as dmc

from app.components.plate_grid import (
    is_checkerboard_valid_well,
    is_edge_well,
)
from app.callbacks.layout_utils import (
    handle_well_click,
    handle_selection_helper,
    get_layout_validation_status,
)
from app.logging_config import get_logger

logger = get_logger(__name__)


def register_layout_grid_callbacks(app):
    """
    Register layout grid interaction callbacks.

    Args:
        app: Dash application instance
    """
    # Import layout components here to avoid circular imports
    from app.layouts.plate_templates import (
        create_plate_templates_header,
        create_layout_info_panel,
        create_layout_editor_section,
        create_layout_summary_panel,
        create_layout_controls,
    )
    from app.components.plate_grid import create_assignment_panel, create_plate_grid

    from dash import ALL

    # Clientside callback to capture well clicks with shift key state
    app.clientside_callback(
        """
        function(n_clicks_list) {
            // Setup keyboard listener if not already attached
            if (!window._shiftKeyListenerAttached) {
                window._shiftKeyState = false;
                document.addEventListener('keydown', function(e) {
                    if (e.key === 'Shift') window._shiftKeyState = true;
                });
                document.addEventListener('keyup', function(e) {
                    if (e.key === 'Shift') window._shiftKeyState = false;
                });
                window._shiftKeyListenerAttached = true;
            }

            const triggered = dash_clientside.callback_context.triggered;
            if (!triggered || triggered.length === 0) return window.dash_clientside.no_update;

            // Get the triggered element
            const triggeredItem = triggered[0];

            // IMPORTANT: Only process actual clicks (n_clicks must be a positive number)
            // This prevents false triggers when the grid re-renders and components are recreated
            if (!triggeredItem.value || triggeredItem.value <= 0) {
                return window.dash_clientside.no_update;
            }

            const triggered_id_str = triggeredItem.prop_id.split('.')[0];
            try {
                const triggered_id = JSON.parse(triggered_id_str);
                // We only care about well clicks
                if (triggered_id.type !== 'plate-well') return window.dash_clientside.no_update;

                // Return click info with current shift key state
                return {
                    well: triggered_id.index,
                    shiftKey: window._shiftKeyState || false,
                    timestamp: Date.now()
                };
            } catch (e) {
                return window.dash_clientside.no_update;
            }
        }
        """,
        Output("plate-templates-well-click-store", "data"),
        [Input({"type": "plate-well", "index": ALL}, "n_clicks")],
        prevent_initial_call=True,
    )

    @app.callback(
        Output("plate-templates-selection-store", "data", allow_duplicate=True),
        [
            Input("layout-editor-checkerboard-toggle", "checked"),
            Input("layout-editor-pattern-selector", "value"),
            Input("layout-editor-skip-edges-toggle", "checked"),
        ],
        prevent_initial_call=True,
    )
    def handle_layout_toggle_change(checked, pattern, skip_edges):
        """Clear selection when checkerboard pattern, pattern type, or skip edges is changed."""
        return []

    @app.callback(
        Output("layout-editor-pattern-wrapper", "style"),
        [
            Input("layout-editor-checkerboard-toggle", "checked"),
        ],
        [
            State("plate-templates-project-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def toggle_pattern_selector_visibility(checked, project_store):
        """Show/hide pattern selector based on checkerboard toggle."""
        project_id = project_store.get("project_id") if project_store else None
        plate_format = 96
        if project_id:
            from app.models import Project
            project = Project.query.get(project_id)
            if project:
                plate_format = int(project.plate_format.value)

        if checked and plate_format == 384:
            return {"display": "block"}
        return {"display": "none"}

    @app.callback(
        Output("plate-templates-layout-store", "data"),
        [
            Input("plate-templates-layout-selector", "value"),
        ],
        [
            State("plate-templates-layout-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def handle_layout_selection(selected_value, current_layout_store):
        """Handle layout selection from dropdown."""
        if selected_value == "" or selected_value is None:
            # New layout selected - clear the layout ID
            return {"layout_id": None}
        else:
            # Existing layout selected
            try:
                layout_id = int(selected_value)
                return {"layout_id": layout_id}
            except (ValueError, TypeError):
                raise PreventUpdate

    @app.callback(
        [
            Output("plate-templates-header-container", "children"),
            Output("plate-templates-controls-container", "children"),
            Output("plate-templates-grid-container", "children"),
            Output("plate-templates-helpers-container", "children"),
            Output("plate-templates-assignment-container", "children"),
            Output("plate-templates-summary-container", "children"),
            Output("plate-templates-selection-store", "data", allow_duplicate=True),
            Output("plate-templates-assignments-store", "data", allow_duplicate=True),
            Output("plate-templates-constructs-store", "data"),
            Output("plate-templates-last-clicked-store", "data", allow_duplicate=True),
            Output("plate-templates-well-click-store", "data", allow_duplicate=True),
        ],
        [
            Input("plate-templates-project-store", "data"),
            Input("plate-templates-layout-store", "data"),
        ],
        prevent_initial_call="initial_duplicate",
    )
    def initialize_layout_editor(project_store, layout_store):
        """Initialize the layout editor components."""
        import traceback

        if not project_store:
            raise PreventUpdate

        try:
            project_id = project_store.get("project_id")
            layout_id = layout_store.get("layout_id") if layout_store else None

            # Get project info
            from app.models import Project
            project = Project.query.get(project_id)
            if not project:
                raise PreventUpdate

            plate_format = int(project.plate_format.value)

            # Get constructs for assignment panel
            constructs = [
                {"id": c.id, "identifier": c.identifier, "family": c.family}
                for c in project.constructs
            ]

            # Build constructs metadata for client-side validation
            constructs_metadata = {
                str(c.id): {
                    "id": c.id,
                    "identifier": c.identifier,
                    "family_id": c.family_id,
                    "family": c.family,
                    "is_wildtype": c.is_wildtype,
                    "is_unregulated": c.is_unregulated
                }
                for c in project.constructs
            }

            # Get existing layouts for this project
            from app.services.plate_layout_service import PlateLayoutService
            existing_layouts_list = PlateLayoutService.list_layouts(project_id, include_draft=True)
            existing_layouts = [
                {"id": l.id, "name": l.name, "is_draft": l.is_draft}
                for l in existing_layouts_list
            ]

            # Get layout info if editing existing
            layout_name = None
            is_draft = True
            assignments = {}

            if layout_id:
                layout = PlateLayoutService.get_layout(layout_id)
                if layout:
                    layout_name = layout.name
                    is_draft = layout.is_draft
                    # Get assignments
                    summary = PlateLayoutService.get_layout_summary(layout_id)
                    grid_data = PlateLayoutService.get_layout_grid(layout_id)
                    for row in grid_data:
                        for cell in row:
                            if cell["well_type"] != "empty":
                                assignments[cell["position"]] = cell

            # Create header with layout selector
            header = create_plate_templates_header(
                project_id=project_id,
                project_name=project.name,
                layout_name=layout_name,
                is_draft=is_draft,
                plate_format=plate_format,
                existing_layouts=existing_layouts,
                current_layout_id=layout_id,
            )

            # Controls section is now rendered directly in the layout to avoid callback timing issues
            # Don't overwrite it here - use no_update to preserve the initial controls
            controls_section = no_update

            # Create grid section
            grid_section = create_layout_editor_section(
                plate_format=plate_format,
                section_id="layout-editor",
                assignments=assignments,
            )

            # Create info panel
            info_panel = create_layout_info_panel(
                project_id=project_id,
                plate_format=plate_format,
                layout_name=layout_name,
                assigned_wells=len(assignments),
            )

            # Create assignment panel
            assignment_panel = create_assignment_panel(
                panel_id="layout-assignment",
                constructs=constructs,
            )

            # Create summary panel
            summary_data = {
                "total_wells": 384 if plate_format == 384 else 96,
                "assigned_wells": len(assignments),
                "by_type": {},
                "by_role": {},
                "constructs": [],
                "families_mutant": [],
                "families_wt": [],
                "checkerboard_violations": [],
            }
            for assignment in assignments.values():
                wt = assignment.get("well_type", "empty")
                summary_data["by_type"][wt] = summary_data["by_type"].get(wt, 0) + 1

                # Track analytical roles
                role = assignment.get("analytical_role")
                if role:
                    summary_data["by_role"][role] = summary_data["by_role"].get(role, 0) + 1

                # Track family presence for validation
                fid = assignment.get("family_id")
                if role == "mutant" and fid:
                    if fid not in summary_data["families_mutant"]:
                        summary_data["families_mutant"].append(fid)
                elif role == "wildtype" and fid:
                    if fid not in summary_data["families_wt"]:
                        summary_data["families_wt"].append(fid)

            # Check checkerboard violations for 384-well plates
            if plate_format == 384 and assignments:
                from app.components.plate_grid import validate_checkerboard_selection
                assigned_positions = list(assignments.keys())
                # Use default pattern 'A' for initial load
                is_checkerboard_valid, invalid_wells = validate_checkerboard_selection(
                    assigned_positions, plate_format, 'A'
                )
                summary_data["checkerboard_violations"] = invalid_wells

            is_valid, issues = get_layout_validation_status(summary_data)
            summary_panel = create_layout_summary_panel(
                summary_id="layout-summary",
                summary_data=summary_data,
                validation_passed=is_valid if assignments else None,
                validation_issues=issues,
            )

            return (
                header,
                controls_section,
                grid_section,
                info_panel,
                assignment_panel,
                summary_panel,
                [],  # Reset selection store
                assignments,  # Initialize assignments store
                constructs_metadata,  # Populate constructs store
                None,  # Reset last-clicked store
                None,  # Reset well-click store
            )
        except Exception as e:
            print(f"ERROR in initialize_layout_editor: {e}")
            traceback.print_exc()
            raise

    @app.callback(
        [
            Output("plate-templates-selection-store", "data"),
            Output("plate-templates-last-clicked-store", "data"),
        ],
        [
            Input("plate-templates-well-click-store", "data"),
        ],
        [
            State("plate-templates-selection-store", "data"),
            State("plate-templates-last-clicked-store", "data"),
            State("plate-templates-project-store", "data"),
            State("layout-editor-checkerboard-toggle", "checked"),
            State("layout-editor-pattern-selector", "value"),
            State("layout-editor-skip-edges-toggle", "checked"),
        ],
        prevent_initial_call=True,
    )
    def handle_well_click_callback(well_click_data, current_selection, last_clicked, project_store, checkerboard_enabled, pattern, skip_edges):
        """Handle well click events collected from the client."""
        if not well_click_data:
            raise PreventUpdate

        clicked_well = well_click_data.get("well")
        shift_key = well_click_data.get("shiftKey", False)

        if not clicked_well:
            raise PreventUpdate

        # Get project info for validation
        project_id = project_store.get("project_id") if project_store else None
        # Default to 96 if failing
        plate_format = 96
        if project_id:
             from app.models import Project
             project = Project.query.get(project_id)
             if project:
                 plate_format = int(project.plate_format.value)

        # Check skip edges constraint
        if skip_edges and is_edge_well(clicked_well, plate_format):
            # Edge well, ignore click when skip edges is enabled
            raise PreventUpdate

        # Check checkerboard constraint
        pattern = pattern or 'A'  # Default to Pattern A
        if checkerboard_enabled and plate_format == 384:
            if not is_checkerboard_valid_well(clicked_well, plate_format, pattern):
                # Invalid well for checkerboard, ignore click
                raise PreventUpdate

        # Update selection using shift key for range select
        new_selection = handle_well_click(
            clicked_well=clicked_well,
            current_selection=current_selection or [],
            shift_key=bool(shift_key),  # Range selection if shift held
            ctrl_key=not shift_key,  # Toggle behavior if not shift-clicking (always multi-select)
            last_clicked=last_clicked,
            plate_format=plate_format
        )

        # Filter out edge wells from selection if skip_edges is enabled
        if skip_edges:
            new_selection = [w for w in new_selection if not is_edge_well(w, plate_format)]

        return new_selection, clicked_well

    @app.callback(
        Output("plate-templates-selection-store", "data", allow_duplicate=True),
        [
            Input({"type": "selection-helper", "action": ALL, "value": ALL}, "n_clicks"),
        ],
        [
            State("plate-templates-project-store", "data"),
            State("layout-editor-checkerboard-toggle", "checked"),
            State("layout-editor-pattern-selector", "value"),
            State("layout-editor-skip-edges-toggle", "checked"),
        ],
        prevent_initial_call=True,
    )
    def handle_selection_helper_callback(n_clicks_list, project_store, checkerboard_enabled, pattern, skip_edges):
        """Handle selection helper button clicks."""
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate

        triggered_prop_id = ctx.triggered[0]["prop_id"]
        triggered_value = ctx.triggered[0]["value"]

        # Ignored reset triggers (None or 0)
        if not triggered_value:
             raise PreventUpdate

        # Get plate format from project
        project_id = project_store.get("project_id") if project_store else None
        if not project_id:
            raise PreventUpdate

        from app.models import Project
        project = Project.query.get(project_id)
        plate_format = int(project.plate_format.value) if project else 96

        # Determine which helper was clicked
        triggered_prop_id = ctx.triggered[0]["prop_id"]

        # Example: '{"type":"selection-helper","action":"row","value":"A"}.n_clicks'
        if "{" not in triggered_prop_id:
            # Fallback for string IDs if any used (e.g. static helpers)
            # But the component uses pattern matching, so this shouldn't happen usually
            raise PreventUpdate

        import json
        try:
             id_part = triggered_prop_id.split(".")[0]
             triggered_id = json.loads(id_part)
             helper_type = triggered_id.get("action")
             helper_value = triggered_id.get("value")
        except Exception:
             raise PreventUpdate

        if not helper_type:
             raise PreventUpdate

        if helper_type == "clear":
             return []

        # Use existing logic
        new_selection = handle_selection_helper(
            helper_type=helper_type,
            helper_value=helper_value,
            plate_format=plate_format
        )

        # Filter out edge wells if skip_edges is enabled
        if skip_edges:
            new_selection = [w for w in new_selection if not is_edge_well(w, plate_format)]

        # Filter out invalid checkerboard wells if checkerboard is enabled
        pattern = pattern or 'A'
        if checkerboard_enabled and plate_format == 384:
            new_selection = [w for w in new_selection if is_checkerboard_valid_well(w, plate_format, pattern)]

        return new_selection

    @app.callback(
        Output("plate-templates-grid-container", "children", allow_duplicate=True),
        [
            Input("plate-templates-selection-store", "data"),
            Input("plate-templates-assignments-store", "data"),
            Input("layout-editor-checkerboard-toggle", "checked"),
            Input("layout-editor-pattern-selector", "value"),
            Input("layout-editor-skip-edges-toggle", "checked"),
        ],
        [
            State("plate-templates-project-store", "data"),
            State("color-scheme-store", "data"),
            State("layout-editor-grid-zoom-slider", "value"),
        ],
        prevent_initial_call=True,
    )
    def update_grid_visuals(selection, assignments, checkerboard_enabled, pattern, skip_edges, project_store, color_scheme, zoom_value):
        """Update the grid visuals when state changes."""

        project_id = project_store.get("project_id") if project_store else None
        # Default to 96 if failing
        plate_format = 96
        construct_map = {}

        if project_id:
             from app.models import Project
             project = Project.query.get(project_id)
             if project:
                 plate_format = int(project.plate_format.value)
                 # Create id -> identifier map
                 construct_map = {c.id: c.identifier for c in project.constructs}

        # Enrich assignments with construct names for visualization
        enriched_assignments = {}
        if assignments:
            # Create a deep copy to avoid modifying the store directly if it's mutable
            import copy
            enriched_assignments = copy.deepcopy(assignments)

            for pos, data in enriched_assignments.items():
                c_id = data.get("construct_id")
                if c_id:
                     # Ensure int
                     try:
                         c_id = int(c_id)
                         data["construct_name"] = construct_map.get(c_id, f"ID:{c_id}")
                     except (ValueError, TypeError):
                         pass

        # Import layout components
        from app.components.plate_grid import create_plate_grid, create_selection_helpers

        # Default pattern
        pattern = pattern or 'A'
        dark_mode = (color_scheme == "dark") if color_scheme else False

        # Create just the grid and helpers to update the grid container
        # The controls container (toggle) is NOT updated, preserving its state/callbacks
        grid = create_plate_grid(
            plate_format=plate_format,
            grid_id="layout-editor-grid",
            assignments=enriched_assignments,
            selected_wells=selection,
            enforce_checkerboard=checkerboard_enabled if plate_format == 384 else False,
            pattern=pattern,
            skip_edges=skip_edges,
            dark_mode=dark_mode,
            zoom=zoom_value,
        )

        helpers = create_selection_helpers(
            plate_format=plate_format,
            helpers_id="layout-editor-helpers",
        )

        return dmc.Stack([grid, helpers], gap="md")

    # Callback to enforce mutual exclusivity between Well Type and Construct
    @app.callback(
        [
            Output("layout-assignment-construct-select", "disabled", allow_duplicate=True),
            Output("layout-assignment-construct-select", "value", allow_duplicate=True),
            Output("layout-assignment-type-select", "value", allow_duplicate=True),
        ],
        [
            Input("layout-assignment-type-select", "value"),
            Input("layout-assignment-construct-select", "value"),
        ],
        [
            State("plate-templates-selection-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def enforce_assignment_exclusivity(well_type, construct_value, selection):
        """
        Enforce mutual exclusivity between Well Type and Construct selection.

        Rules:
        - If Well Type is NOT 'sample', Construct must be disabled and cleared
        - If Construct is selected, Well Type must be 'sample'
        """
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate

        triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
        no_selection = not selection or len(selection) == 0

        # If type dropdown was changed
        if triggered_id == "layout-assignment-type-select":
            if well_type != "sample":
                # Disable construct and clear it
                return True, None, no_update
            else:
                # Enable construct (if wells selected)
                return no_selection, no_update, no_update

        # If construct dropdown was changed
        elif triggered_id == "layout-assignment-construct-select":
            if construct_value and construct_value != "":
                # Auto-set type to 'sample'
                return no_selection, no_update, "sample"
            else:
                return no_selection, no_update, no_update

        return no_update, no_update, no_update
