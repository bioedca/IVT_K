"""
Layout assignment callbacks for plate template editor assignment management.

Extracted from layout_callbacks.py during Phase 4 refactoring.

Provides:
- Assignment panel state management
- Save and publish callbacks
- Well assignment handling
- Layout summary updates
- Checkerboard redistribution
- Calculator plan import
- Clientside callback for grid zoom
"""
from dash import callback_context, Input, Output, State, no_update
from dash.exceptions import PreventUpdate
import dash_mantine_components as dmc

from app.models.enums import LigandCondition
from app.callbacks.layout_utils import (
    handle_layout_save,
    handle_layout_publish,
    get_layout_validation_status,
)
from app.logging_config import get_logger

logger = get_logger(__name__)


def register_layout_assignment_callbacks(app):
    """
    Register layout assignment management callbacks.

    Args:
        app: Dash application instance
    """
    # Import layout components here to avoid circular imports
    from app.layouts.plate_templates import (
        create_plate_templates_header,
        create_layout_summary_panel,
    )

    @app.callback(
        [
            Output("layout-assignment-count-badge", "children"),
            Output("layout-assignment-count-badge", "color"),
            Output("layout-assignment-construct-select", "disabled"),
            Output("layout-assignment-type-select", "disabled"),
            Output("layout-assignment-replicate-group", "disabled"),
            Output("layout-assignment-ligand-condition", "disabled"),
            Output("layout-assignment-assign-btn", "disabled"),
            Output("layout-assignment-clear-btn", "disabled"),
        ],
        [
            Input("plate-templates-selection-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def update_assignment_panel_state(selection):
        """Update assignment panel state based on selection."""
        if not selection:
            return (
                "0 wells selected",
                "gray",
                True, True, True, True, True, True
            )

        count = len(selection)
        return (
            f"{count} wells selected",
            "green",
            False, False, False, False, False, False
        )



    @app.callback(
        [
            Output("plate-templates-notification-container", "children", allow_duplicate=True),
            Output("plate-templates-layout-store", "data", allow_duplicate=True),
            Output("plate-templates-header-container", "children", allow_duplicate=True),
        ],
        [
            Input("plate-templates-save-btn", "n_clicks"),
        ],
        [
            State("plate-templates-project-store", "data"),
            State("plate-templates-layout-store", "data"),
            State("plate-templates-name-input", "value"),
            State("plate-templates-assignments-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def handle_save_callback(n_clicks, project_store, layout_store, layout_name, assignments):
        """Handle save button click."""
        from dash_iconify import DashIconify

        if not n_clicks:
            raise PreventUpdate

        project_id = project_store.get("project_id") if project_store else None
        layout_id = layout_store.get("layout_id") if layout_store else None

        if not project_id:
            alert = dmc.Alert(
                "Project not found",
                title="Error",
                color="red",
                icon=DashIconify(icon="mdi:alert-circle", width=20),
                withCloseButton=True,
                style={"marginBottom": "1rem"},
            )
            return alert, no_update, no_update

        if not layout_name or not layout_name.strip():
            alert = dmc.Alert(
                "Please enter a layout name",
                title="Error",
                color="red",
                icon=DashIconify(icon="mdi:alert-circle", width=20),
                withCloseButton=True,
                style={"marginBottom": "1rem"},
            )
            return alert, no_update, no_update

        success, message, new_layout_id = handle_layout_save(
            layout_id=layout_id,
            project_id=project_id,
            layout_name=layout_name,
            assignments=assignments or {},
            username="user",  # Would come from session in real app
        )

        if success:
            alert = dmc.Alert(
                "Layout saved as draft",
                title="Saved",
                color="blue",
                icon=DashIconify(icon="mdi:content-save", width=20),
                withCloseButton=True,
                style={"marginBottom": "1rem"},
            )

            # Refresh header to update layout selector
            from app.models import Project
            from app.services.plate_layout_service import PlateLayoutService

            project = Project.query.get(project_id)
            plate_format = int(project.plate_format.value) if project else 384

            existing_layouts_list = PlateLayoutService.list_layouts(project_id, include_draft=True)
            existing_layouts = [
                {"id": l.id, "name": l.name, "is_draft": l.is_draft}
                for l in existing_layouts_list
            ]

            new_header = create_plate_templates_header(
                project_id=project_id,
                project_name=project.name if project else "Project",
                layout_name=layout_name,
                is_draft=True,
                plate_format=plate_format,
                existing_layouts=existing_layouts,
                current_layout_id=new_layout_id,
            )

            return alert, {"layout_id": new_layout_id}, new_header
        else:
            alert = dmc.Alert(
                message,
                title="Save Failed",
                color="red",
                icon=DashIconify(icon="mdi:alert-circle", width=20),
                withCloseButton=True,
                style={"marginBottom": "1rem"},
            )
            return alert, no_update, no_update

    @app.callback(
        [
            Output("plate-templates-notification-container", "children"),
            Output("plate-templates-layout-store", "data", allow_duplicate=True),
            Output("plate-templates-header-container", "children", allow_duplicate=True),
        ],
        [
            Input("plate-templates-publish-btn", "n_clicks"),
        ],
        [
            State("plate-templates-layout-store", "data"),
            State("plate-templates-project-store", "data"),
            State("plate-templates-name-input", "value"),
            State("plate-templates-assignments-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def handle_publish_callback(n_clicks, layout_store, project_store, layout_name, assignments):
        """Handle publish button click - saves and publishes the layout."""
        if not n_clicks:
            raise PreventUpdate

        from dash_iconify import DashIconify

        project_id = project_store.get("project_id") if project_store else None
        layout_id = layout_store.get("layout_id") if layout_store else None

        if not project_id:
            alert = dmc.Alert(
                "Project not found",
                title="Error",
                color="red",
                icon=DashIconify(icon="mdi:alert-circle", width=20),
                withCloseButton=True,
                style={"marginBottom": "1rem"},
            )
            return alert, no_update, no_update

        # Validate layout name
        if not layout_name or not layout_name.strip():
            alert = dmc.Alert(
                "Please enter a layout name before publishing",
                title="Error",
                color="red",
                icon=DashIconify(icon="mdi:alert-circle", width=20),
                withCloseButton=True,
                style={"marginBottom": "1rem"},
            )
            return alert, no_update, no_update

        # First save the layout (creates new if needed)
        success, message, new_layout_id = handle_layout_save(
            layout_id=layout_id,
            project_id=project_id,
            layout_name=layout_name,
            assignments=assignments or {},
            username="user",
        )

        if not success:
            alert = dmc.Alert(
                message,
                title="Save Failed",
                color="red",
                icon=DashIconify(icon="mdi:alert-circle", width=20),
                withCloseButton=True,
                style={"marginBottom": "1rem"},
            )
            return alert, no_update, no_update

        # Now publish the layout
        success, message = handle_layout_publish(new_layout_id, "user")

        if success:
            alert = dmc.Alert(
                "Layout published successfully!",
                title="Published",
                color="green",
                icon=DashIconify(icon="mdi:check-circle", width=20),
                withCloseButton=True,
                style={"marginBottom": "1rem"},
            )

            # Refresh header to show "Published" status
            from app.models import Project
            from app.services.plate_layout_service import PlateLayoutService

            project = Project.query.get(project_id)
            plate_format = int(project.plate_format.value) if project else 384

            # Get updated layouts list
            existing_layouts_list = PlateLayoutService.list_layouts(project_id, include_draft=True)
            existing_layouts = [
                {"id": l.id, "name": l.name, "is_draft": l.is_draft}
                for l in existing_layouts_list
            ]

            new_header = create_plate_templates_header(
                project_id=project_id,
                project_name=project.name if project else "Project",
                layout_name=layout_name,
                is_draft=False,  # Now published
                plate_format=plate_format,
                existing_layouts=existing_layouts,
                current_layout_id=new_layout_id,
            )

            return alert, {"layout_id": new_layout_id}, new_header
        else:
            alert = dmc.Alert(
                message,
                title="Publish Failed",
                color="red",
                icon=DashIconify(icon="mdi:alert-circle", width=20),
                withCloseButton=True,
                style={"marginBottom": "1rem"},
            )
            return alert, {"layout_id": new_layout_id}, no_update

    @app.callback(
        Output("plate-templates-publish-btn", "disabled"),
        [
            Input("plate-templates-assignments-store", "data"),
            Input("layout-editor-checkerboard-toggle", "checked"),
            Input("layout-editor-pattern-selector", "value"),
        ],
        [
            State("plate-templates-project-store", "data"),
            State("plate-templates-constructs-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def update_publish_button_state(assignments, checkerboard_enabled, pattern, project_store, constructs_store):
        """Disable publish button when layout has validation issues or checkerboard violations."""
        if not assignments:
            return True  # Disable if no assignments

        project_id = project_store.get("project_id") if project_store else None
        plate_format = 96
        if project_id:
            from app.models import Project
            project = Project.query.get(project_id)
            if project:
                plate_format = int(project.plate_format.value)

        # Build summary for validation
        constructs_meta = constructs_store or {}
        pattern = pattern or 'A'

        summary_data = {
            "by_type": {},
            "by_role": {},
            "families_mutant": set(),
            "families_wt": set(),
            "checkerboard_violations": [],
        }

        for assignment in assignments.values():
            wt = assignment.get("well_type", "empty")
            summary_data["by_type"][wt] = summary_data["by_type"].get(wt, 0) + 1

            role = assignment.get("analytical_role")
            if role:
                summary_data["by_role"][role] = summary_data["by_role"].get(role, 0) + 1

            fid = assignment.get("family_id")
            if role == "mutant" and fid:
                summary_data["families_mutant"].add(fid)
            elif role == "wildtype" and fid:
                summary_data["families_wt"].add(fid)

        # Check checkerboard violations for 384-well plates
        if plate_format == 384:
            from app.components.plate_grid import validate_checkerboard_selection
            assigned_positions = list(assignments.keys())
            is_checkerboard_valid, invalid_wells = validate_checkerboard_selection(
                assigned_positions, plate_format, pattern
            )
            summary_data["checkerboard_violations"] = invalid_wells

        # Run validation
        is_valid, issues = get_layout_validation_status(summary_data)

        return not is_valid  # Disable button if not valid

    @app.callback(
        Output("plate-templates-assignments-store", "data"),
        [
            Input("layout-assignment-assign-btn", "n_clicks"),
            Input("layout-assignment-clear-btn", "n_clicks"),
        ],
        [
            State("layout-assignment-construct-select", "value"),
            State("layout-assignment-type-select", "value"),
            State("layout-assignment-replicate-group", "value"),
            State("layout-assignment-ligand-condition", "checked"),
            State("plate-templates-selection-store", "data"),
            State("plate-templates-assignments-store", "data"),
            State("plate-templates-constructs-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def handle_assignment_callback(
        assign_clicks,
        clear_clicks,
        construct_id,
        well_type,
        replicate_group,
        ligand_toggle,
        selection,
        current_assignments,
        constructs_metadata
    ):
        """Handle assignment panel actions (Assign/Clear)."""
        ctx = callback_context
        if not ctx.triggered or not selection:
            raise PreventUpdate

        triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
        current_assignments = current_assignments or {}

        # Determine action
        is_clear = triggered_id == "layout-assignment-clear-btn"

        updated_assignments = dict(current_assignments)

        # Helper to find unregulated well position
        def find_unregulated_well(assignments, constructs_meta):
            for pos, data in assignments.items():
                cid = data.get("construct_id")
                if cid and constructs_meta.get(str(cid), {}).get("is_unregulated"):
                    return pos
            return None

        # Helper to find a WT pair for a family
        def find_wt_for_family(family_id, assignments, constructs_meta):
            for pos, data in assignments.items():
                cid = data.get("construct_id")
                if cid:
                    c_meta = constructs_meta.get(str(cid), {})
                    if c_meta.get("is_wildtype") and c_meta.get("family_id") == family_id:
                        return pos
            return None

        for well in selection:
            if is_clear:
                # Remove assignment if exists
                if well in updated_assignments:
                    del updated_assignments[well]
            else:
                assignment_data = {
                    "position": well,
                    "well_type": well_type,
                }

                # Sample wells require a construct
                if well_type == "sample":
                    if not construct_id:
                        continue  # Construct required for sample wells

                    c_meta = constructs_metadata.get(str(construct_id))
                    if not c_meta:
                        continue

                    assignment_data["construct_id"] = int(construct_id)
                    assignment_data["family_id"] = c_meta.get("family_id")

                    # Populate analytical_role for display purposes (not stored in DB)
                    if c_meta.get("is_unregulated"):
                        assignment_data["analytical_role"] = "unregulated"
                        # Unregulated is never paired
                        assignment_data["paired_with"] = None
                    elif c_meta.get("is_wildtype"):
                        assignment_data["analytical_role"] = "wildtype"
                        # WT pairs with unregulated
                        unreg_pos = find_unregulated_well(updated_assignments, constructs_metadata)
                        if unreg_pos:
                            assignment_data["paired_with"] = unreg_pos
                    else:
                        assignment_data["analytical_role"] = "mutant"
                        # Mutant pairs with WT from same family
                        wt_pos = find_wt_for_family(c_meta.get("family_id"), updated_assignments, constructs_metadata)
                        if wt_pos:
                            assignment_data["paired_with"] = wt_pos

                    if replicate_group:
                        assignment_data["replicate_group"] = replicate_group
                    if ligand_toggle:
                        assignment_data["ligand_condition"] = LigandCondition.PLUS_LIG

                elif well_type in ["negative_control_no_template", "negative_control_no_dye", "blank"]:
                    # Control wells - no construct or pairing
                    assignment_data["construct_id"] = None
                    assignment_data["paired_with"] = None

                # Empty wells have minimal data
                elif well_type == "empty":
                    assignment_data["construct_id"] = None
                    assignment_data["paired_with"] = None

                updated_assignments[well] = assignment_data

        return updated_assignments

    @app.callback(
        Output("plate-templates-summary-container", "children", allow_duplicate=True),
        [
            Input("plate-templates-assignments-store", "data"),
            Input("layout-editor-checkerboard-toggle", "checked"),
            Input("layout-editor-pattern-selector", "value"),
        ],
        [
            State("plate-templates-project-store", "data"),
            State("plate-templates-constructs-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def update_layout_summary_callback(assignments, checkerboard_enabled, pattern, project_store, constructs_store):
        """Update layout summary when assignments change."""
        if assignments is None:
            return no_update

        project_id = project_store.get("project_id") if project_store else None
        constructs_meta = constructs_store or {}
        pattern = pattern or 'A'

        # Determine plate format
        plate_format = 96
        if project_id:
            from app.models import Project
            project = Project.query.get(project_id)
            if project:
                plate_format = int(project.plate_format.value)

        # Import layout components
        from app.components.plate_grid import validate_checkerboard_selection

        # Calculate summary stats
        summary_data = {
            "total_wells": 384 if plate_format == 384 else 96,
            "assigned_wells": len(assignments),
            "by_type": {},
            "by_role": {},  # Analytical roles from construct flags
            "constructs": [],
            "families_mutant": set(),
            "families_wt": set(),
            "checkerboard_violations": [],  # Wells that violate checkerboard pattern
        }

        # Track construct counts
        construct_counts = {}  # construct_id -> count

        for assignment in assignments.values():
            wt = assignment.get("well_type", "empty")
            summary_data["by_type"][wt] = summary_data["by_type"].get(wt, 0) + 1

            # Track analytical role for sample wells
            role = assignment.get("analytical_role")
            if role:
                summary_data["by_role"][role] = summary_data["by_role"].get(role, 0) + 1

            # Track family presence
            fid = assignment.get("family_id")
            if role == "mutant" and fid:
                summary_data["families_mutant"].add(fid)
            elif role == "wildtype" and fid:
                summary_data["families_wt"].add(fid)

            # Count constructs
            cid = assignment.get("construct_id")
            if cid:
                construct_counts[str(cid)] = construct_counts.get(str(cid), 0) + 1

        # Build constructs list with names
        for cid, count in construct_counts.items():
            c_meta = constructs_meta.get(str(cid), {})
            identifier = c_meta.get("identifier", f"Construct {cid}")
            summary_data["constructs"].append({
                "identifier": identifier,
                "count": count,
                "role": c_meta.get("is_unregulated") and "unregulated" or (c_meta.get("is_wildtype") and "wildtype" or "mutant")
            })

        # Sort constructs: unregulated first, then wildtype, then mutants
        role_order = {"unregulated": 0, "wildtype": 1, "mutant": 2}
        summary_data["constructs"].sort(key=lambda x: (role_order.get(x.get("role", "mutant"), 2), x.get("identifier", "")))

        # ALWAYS check checkerboard pattern compliance for 384-well plates
        # This is a physical constraint of the plate reader, not optional
        if plate_format == 384:
            assigned_positions = list(assignments.keys())
            is_checkerboard_valid, invalid_wells = validate_checkerboard_selection(
                assigned_positions, plate_format, pattern
            )
            summary_data["checkerboard_violations"] = invalid_wells

        # Run validation
        is_valid, issues = get_layout_validation_status(summary_data)

        # Add checkerboard violation warning
        checkerboard_warning = None
        if summary_data.get("checkerboard_violations"):
            violation_count = len(summary_data["checkerboard_violations"])
            checkerboard_warning = f"{violation_count} well(s) violate checkerboard pattern"

        return create_layout_summary_panel(
            summary_id="layout-summary",
            summary_data=summary_data,
            validation_passed=is_valid if assignments else None,
            validation_issues=issues,
            checkerboard_warning=checkerboard_warning,
        )

    @app.callback(
        Output("plate-templates-assignments-store", "data", allow_duplicate=True),
        [
            Input("layout-redistribute-checkerboard-btn", "n_clicks"),
        ],
        [
            State("plate-templates-assignments-store", "data"),
            State("plate-templates-project-store", "data"),
            State("layout-editor-pattern-selector", "value"),
        ],
        prevent_initial_call=True,
    )
    def redistribute_to_checkerboard(n_clicks, assignments, project_store, pattern):
        """Redistribute non-compliant wells to nearest valid checkerboard positions."""
        if not n_clicks or not assignments:
            raise PreventUpdate

        from app.components.plate_grid import (
            is_checkerboard_valid_well,
            find_nearest_valid_well,
        )

        project_id = project_store.get("project_id") if project_store else None
        plate_format = 96
        if project_id:
            from app.models import Project
            project = Project.query.get(project_id)
            if project:
                plate_format = int(project.plate_format.value)

        if plate_format != 384:
            raise PreventUpdate

        pattern = pattern or 'A'

        # Find all non-compliant wells
        non_compliant = []
        compliant = set()
        for pos, data in assignments.items():
            if is_checkerboard_valid_well(pos, plate_format, pattern):
                compliant.add(pos)
            else:
                non_compliant.append((pos, data))

        if not non_compliant:
            raise PreventUpdate

        # Redistribute each non-compliant well to nearest valid position
        import copy
        new_assignments = copy.deepcopy(assignments)
        occupied = set(new_assignments.keys())

        for old_pos, data in non_compliant:
            new_pos = find_nearest_valid_well(old_pos, plate_format, pattern, occupied)
            if new_pos:
                # Remove from old position
                del new_assignments[old_pos]
                occupied.discard(old_pos)

                # Add to new position
                data["position"] = new_pos
                new_assignments[new_pos] = data
                occupied.add(new_pos)

        return new_assignments

    @app.callback(
        [
            Output("plate-templates-assignments-store", "data", allow_duplicate=True),
            Output("plate-templates-import-store", "data"),
        ],
        Input("plate-templates-import-upload", "contents"),
        [
            State("plate-templates-import-upload", "filename"),
            State("plate-templates-project-store", "data"),
            State("plate-templates-constructs-store", "data"),
            State("layout-editor-checkerboard-toggle", "checked"),
            State("layout-editor-pattern-selector", "value"),
            State("layout-editor-skip-edges-toggle", "checked"),
        ],
        prevent_initial_call=True,
    )
    def import_calculator_plan(contents, filename, project_store, constructs_store, checkerboard_enabled, pattern, skip_edges):
        """Import a calculator plan JSON and generate recommended plate layout."""
        if not contents:
            raise PreventUpdate

        import base64
        import json

        # Decode the uploaded file
        try:
            if ',' not in contents:
                raise PreventUpdate
            content_type, content_string = contents.split(',', 1)
            decoded = base64.b64decode(content_string)
            plan_data = json.loads(decoded.decode('utf-8'))
        except (ValueError, json.JSONDecodeError):
            raise PreventUpdate

        # Get project info
        project_id = project_store.get("project_id") if project_store else None
        if not project_id:
            raise PreventUpdate

        from app.models import Project
        project = Project.query.get(project_id)
        if not project:
            raise PreventUpdate

        plate_format = int(project.plate_format.value)
        constructs_meta = constructs_store or {}
        pattern = pattern or 'A'

        # Extract parameters from the plan
        params = plan_data.get("parameters", {})
        replicates = params.get("replicates", 4)
        neg_template_count = params.get("negative_template_count", 2)
        neg_dfhbi_count = params.get("negative_dfhbi_count", 0)
        ligand_enabled = params.get("ligand_enabled", False)
        plan_constructs = plan_data.get("constructs", [])
        plan_dna_additions = plan_data.get("dna_additions", [])

        # Build a mapping from construct name to construct metadata in this project
        project_constructs = {c.identifier: c for c in project.constructs}

        # Generate well positions based on plate format and checkerboard pattern
        from app.components.plate_grid import (
            ROWS_96, COLS_96, ROWS_384, COLS_384,
            is_checkerboard_valid_well,
            is_edge_well,
        )

        if plate_format == 384:
            rows = ROWS_384
            cols = COLS_384
        else:
            rows = ROWS_96
            cols = COLS_96

        # Get all valid well positions
        valid_wells = []
        for row in rows:
            for col in cols:
                pos = f"{row}{col}"
                # Skip edge wells if enabled
                if skip_edges and is_edge_well(pos, plate_format):
                    continue
                if plate_format == 384 and checkerboard_enabled:
                    if is_checkerboard_valid_well(pos, plate_format, pattern):
                        valid_wells.append(pos)
                else:
                    valid_wells.append(pos)

        # Create assignments
        assignments = {}
        well_idx = 0

        # Helper to get next available well
        def get_next_well():
            nonlocal well_idx
            if well_idx < len(valid_wells):
                pos = valid_wells[well_idx]
                well_idx += 1
                return pos
            return None

        # 1. Add negative control wells (-Template)
        for _ in range(neg_template_count):
            pos = get_next_well()
            if pos:
                assignments[pos] = {
                    "position": pos,
                    "well_type": "negative_control_no_template",
                    "construct_id": None,
                    "analytical_role": None,
                    "family_id": None,
                }

        # 2. Add negative control wells (-DFHBI) if included
        for _ in range(neg_dfhbi_count):
            pos = get_next_well()
            if pos:
                assignments[pos] = {
                    "position": pos,
                    "well_type": "negative_control_no_dye",
                    "construct_id": None,
                    "analytical_role": None,
                    "family_id": None,
                }

        # 3. Add construct wells with replicates
        # If ligand is enabled and we have dna_additions with ligand conditions,
        # use those to generate +Lig/-Lig paired wells
        if ligand_enabled and plan_dna_additions:
            # Use DNA additions which already have +Lig/-Lig pairs
            # Group by construct name, then by ligand_condition
            # Sort: unregulated first, then wildtype, then mutants
            sorted_additions = sorted(
                [a for a in plan_dna_additions if not a.get("is_negative_control")],
                key=lambda a: (
                    0 if any(c.get("is_unregulated") and c.get("name") == a.get("construct_name") for c in plan_constructs)
                    else (1 if any(c.get("is_wildtype") and c.get("name") == a.get("construct_name") for c in plan_constructs) else 2),
                    a.get("construct_name", ""),
                    0 if a.get("ligand_condition") == LigandCondition.PLUS_LIG else 1,
                )
            )

            for addition in sorted_additions:
                construct_name = addition.get("construct_name")
                ligand_cond = addition.get("ligand_condition")
                project_construct = project_constructs.get(construct_name)

                if project_construct:
                    construct_id = project_construct.id
                    family_id = project_construct.family_id
                    is_unregulated = project_construct.is_unregulated
                    is_wildtype = project_construct.is_wildtype

                    if is_unregulated:
                        analytical_role = "unregulated"
                    elif is_wildtype:
                        analytical_role = "wildtype"
                    else:
                        analytical_role = "mutant"

                    # Add replicates for this construct+condition
                    for rep in range(replicates):
                        pos = get_next_well()
                        if pos:
                            cond_suffix = f"_{ligand_cond}" if ligand_cond else ""
                            assignments[pos] = {
                                "position": pos,
                                "well_type": "sample",
                                "construct_id": construct_id,
                                "construct_name": construct_name,
                                "analytical_role": analytical_role,
                                "family_id": family_id,
                                "replicate_group": f"rep_{rep + 1}{cond_suffix}",
                                "ligand_condition": ligand_cond,
                            }
        else:
            # No ligand - original behavior
            # Group constructs: unregulated first, then wildtype, then mutants
            sorted_constructs = sorted(
                plan_constructs,
                key=lambda c: (
                    0 if c.get("is_unregulated") else (1 if c.get("is_wildtype") else 2),
                    c.get("name", "")
                )
            )

            for construct in sorted_constructs:
                construct_name = construct.get("name")
                # Try to find matching construct in project
                project_construct = project_constructs.get(construct_name)

                if project_construct:
                    construct_id = project_construct.id
                    family_id = project_construct.family_id
                    is_unregulated = project_construct.is_unregulated
                    is_wildtype = project_construct.is_wildtype

                    if is_unregulated:
                        analytical_role = "unregulated"
                    elif is_wildtype:
                        analytical_role = "wildtype"
                    else:
                        analytical_role = "mutant"

                    # Add replicates for this construct
                    for rep in range(replicates):
                        pos = get_next_well()
                        if pos:
                            assignments[pos] = {
                                "position": pos,
                                "well_type": "sample",
                                "construct_id": construct_id,
                                "construct_name": construct_name,
                                "analytical_role": analytical_role,
                                "family_id": family_id,
                                "replicate_group": f"rep_{rep + 1}",
                            }

        return assignments, plan_data

    # Clientside callback: zoom slider controls grid container scale
    app.clientside_callback(
        """function(zoom) {
            var scale = (zoom || 100) / 100;
            return {
                'display': 'inline-block',
                'cursor': 'crosshair',
                'transform': 'scale(' + scale + ')',
                'transformOrigin': 'top left'
            };
        }""",
        Output("layout-editor-grid-container", "style"),
        Input("layout-editor-grid-zoom-slider", "value"),
        prevent_initial_call=True,
    )
