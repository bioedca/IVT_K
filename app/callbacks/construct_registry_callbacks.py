"""
Construct Registry callbacks.

Phase C: UI Layer Completion (F3.1-F3.9)

Handles:
- Loading and displaying constructs
- Adding/Editing/Deleting constructs
- Filtering and searching
- Unregulated reference assignment
"""
from typing import List, Dict, Any, Optional

from dash import callback, Input, Output, State, no_update, ctx, ALL
from dash.exceptions import PreventUpdate
import dash_mantine_components as dmc
from dash_iconify import DashIconify

from sqlalchemy import func

from app.extensions import db
from app.services.construct_service import ConstructService, ConstructValidationError
from app.models.plate_layout import PlateLayout, WellAssignment, WellType
from app.logging_config import get_logger

logger = get_logger(__name__)

from app.layouts.construct_registry import (
    create_construct_table,
    create_construct_cards,
    create_family_summary,
    create_construct_form,
    create_unregulated_selector,
)


def register_construct_registry_callbacks(app):
    """Register construct registry callbacks."""

    @app.callback(
        [
            Output("construct-registry-data-store", "data"),
            Output("construct-count-badge", "children"),
            Output("construct-family-summary", "children"),
            Output("construct-unregulated-selector", "children"),
            Output("construct-family-filter", "data"),
        ],
        [
            Input("construct-registry-project-store", "data"),
            Input("construct-operation-result", "children"),  # Trigger reload on update
        ],
    )
    def load_construct_data(project_id, _):
        """Load construct data for the project."""
        if not project_id:
            raise PreventUpdate

        # Load constructs and families
        constructs = ConstructService.list_constructs(project_id, include_draft=True)
        families = ConstructService.get_families(project_id)
        
        # Get unregulated construct
        unregulated = ConstructService.get_unregulated_construct(project_id)
        current_unregulated_id = unregulated.id if unregulated else None

        # Batch-fetch replicate counts from plate layout assignments
        replicate_counts = dict(
            db.session.query(
                WellAssignment.construct_id,
                func.count(WellAssignment.id)
            )
            .join(PlateLayout, WellAssignment.layout_id == PlateLayout.id)
            .filter(
                PlateLayout.project_id == project_id,
                WellAssignment.construct_id.isnot(None),
                WellAssignment.well_type == WellType.SAMPLE,
            )
            .group_by(WellAssignment.construct_id)
            .all()
        )

        # Format construct data for store
        construct_data = [
            {
                "id": c.id,
                "identifier": c.identifier,
                "family": c.family,
                "description": c.description,
                "is_wildtype": c.is_wildtype,
                "is_reporter_only": c.is_unregulated,
                "is_unregulated": c.is_unregulated,
                "is_draft": c.is_draft,
                "notes": c.notes,
                "plasmid_size_bp": c.plasmid_size_bp,
                "replicate_count": replicate_counts.get(c.id, 0),
            }
            for c in constructs
            if not c.is_deleted
        ]

        # Format family options for filter
        family_options = [
            {"value": f["name"], "label": f["name"]} 
            for f in families 
            if f["name"] != "universal"
        ]

        # Create summary component
        summary_component = create_family_summary(families)

        # Create unregulated selector
        selector_component = create_unregulated_selector(
            construct_data, 
            current_unregulated_id
        )

        return (
            construct_data,
            f"{len(construct_data)} constructs",
            summary_component,
            selector_component,
            family_options
        )


    @app.callback(
        Output("construct-table-container", "children"),
        [
            Input("construct-registry-data-store", "data"),
            Input("construct-search-input", "value"),
            Input("construct-family-filter", "value"),
            Input("construct-view-mode", "value"),
        ]
    )
    def update_construct_list(data, search, family_filter, view_mode):
        """Filter and display construct list."""
        if data is None:
            return create_construct_table([])

        filtered = data
        
        # Apply filters
        if search:
            search = search.lower()
            filtered = [
                c for c in filtered 
                if search in c["identifier"].lower() or 
                   search in (c["family"] or "").lower()
            ]
            
        if family_filter:
            filtered = [c for c in filtered if c["family"] == family_filter]

        # Render
        if view_mode == "cards":
            return create_construct_cards(filtered)
        else:
            return create_construct_table(filtered)


    @app.callback(
        Output("construct-form-container", "children"),
        [
            Input("construct-add-btn", "n_clicks"),
            Input({"type": "construct-form-cancel", "index": ALL}, "n_clicks"),
        ],
        [
            State("construct-family-filter", "data"),
            State("construct-registry-editing-store", "data"),
        ],
        prevent_initial_call=True
    )
    def toggle_add_form(add_clicks, cancel_clicks, families, editing_data):
        """Toggle the add/edit form."""
        triggered = ctx.triggered_id
        
        # Check if cancel was clicked on the "add" form
        if isinstance(triggered, dict) and triggered.get("type") == "construct-form-cancel":
             if triggered.get("index") == "add":
                 return create_construct_form(
                     families=[f["value"] for f in families] if families else [],
                     form_index="add"
                 )
             return no_update # Ignore cancel from edit form
        
        if triggered == "construct-add-btn":
             # Show empty form
             return create_construct_form(
                 families=[f["value"] for f in families] if families else [],
                 form_index="add"
             )
             
        return no_update


    @app.callback(
        [
            Output("construct-edit-modal", "opened"),
            Output("construct-edit-form-container", "children"),
            Output("construct-registry-editing-store", "data"),
        ],
        [
            Input("construct-add-btn", "n_clicks"),  
            Input({"type": "construct-edit-btn", "index": ALL}, "n_clicks"),
            Input({"type": "construct-form-cancel", "index": ALL}, "n_clicks"),
            Input("construct-operation-result", "children"),
        ],
        [
            State("construct-registry-data-store", "data"),
            State("construct-family-filter", "data"),
        ],
        prevent_initial_call=True
    )
    def manage_modal(add_click, edit_clicks, cancel_clicks, result, constructs, families):
        """Manage edit modal state."""
        triggered = ctx.triggered_id
        
        # If result updated (success), close modal
        if triggered == "construct-operation-result":
             return False, no_update, None

        if isinstance(triggered, dict) and triggered.get("type") == "construct-edit-btn":
            if not any(edit_clicks):
                raise PreventUpdate
                
            construct_id = triggered["index"]
            construct = next((c for c in constructs if c["id"] == construct_id), None)
            
            if construct:
                form = create_construct_form(
                    families=[f["value"] for f in families] if families else [],
                    editing=construct,
                    form_index="edit"
                )
                return True, form, construct

        # Close on cancel if it came from edit form
        if isinstance(triggered, dict) and triggered.get("type") == "construct-form-cancel":
             if triggered.get("index") == "edit":
                 return False, no_update, None
            
        return no_update, no_update, no_update


    @app.callback(
        Output("construct-operation-result", "children"),
        Input({"type": "construct-form-submit", "index": ALL}, "n_clicks"),
        [
            State("construct-registry-project-store", "data"),
            State("construct-registry-editing-store", "data"),
            State({"type": "construct-form-field", "field": "identifier", "index": ALL}, "value"),
            State({"type": "construct-form-field", "field": "family", "index": ALL}, "value"),
            State({"type": "construct-form-field", "field": "is_wildtype", "index": ALL}, "checked"),
            State({"type": "construct-form-field", "field": "is_reporter_only", "index": ALL}, "checked"),
            State({"type": "construct-form-field", "field": "notes", "index": ALL}, "value"),
            State({"type": "construct-form-field", "field": "plasmid_size_bp", "index": ALL}, "value"),
            State("user-store", "data"),
        ],
        prevent_initial_call=True
    )
    def submit_construct(n_clicks, project_id, editing_data, identifiers, families, is_wts, is_reporters, notes_list, plasmid_sizes, user_data):
        """Handle construct form submission (create/update)."""
        if not any(n_clicks):
            raise PreventUpdate

        triggered = ctx.triggered_id
        if not triggered or not isinstance(triggered, dict):
             raise PreventUpdate

        form_index = triggered["index"]

        # Helper to extract value for specific index
        def get_state_val(state_list, idx):
             for item in state_list:
                 if item["id"]["index"] == idx:
                     return item["value"]
             return None

        # Extract values using ctx.states_list
        states = ctx.states_list
        # states[0] -> project_id (not list)
        # states[1] -> editing_data (not list)
        # states[2] -> identifiers (list)
        # states[3] -> families (list)
        # states[4] -> is_wts (list)
        # states[5] -> is_reporters (list)
        # states[6] -> notes_list (list)
        # states[7] -> plasmid_sizes (list)

        identifier = get_state_val(states[2], form_index)
        family = get_state_val(states[3], form_index)
        is_wt = get_state_val(states[4], form_index)
        is_reporter = get_state_val(states[5], form_index)
        notes = get_state_val(states[6], form_index)
        plasmid_size_bp = get_state_val(states[7], form_index)

        # Convert plasmid_size_bp to int if provided
        if plasmid_size_bp is not None:
            plasmid_size_bp = int(plasmid_size_bp)

        username = user_data.get("username", "anonymous") if user_data else "anonymous"

        try:
            if form_index == "edit" and editing_data:
                # Update
                ConstructService.update_construct(
                    construct_id=editing_data["id"],
                    username=username,
                    identifier=identifier,
                    family=family,
                    is_wildtype=is_wt,
                    is_unregulated=is_reporter,
                    notes=notes,
                    plasmid_size_bp=plasmid_size_bp,
                )
                action = "updated"
            else:
                # Create (Add)
                ConstructService.create_construct(
                    project_id=project_id,
                    username=username,
                    identifier=identifier,
                    family=family,
                    is_wildtype=is_wt,
                    is_unregulated=is_reporter,
                    notes=notes,
                    plasmid_size_bp=plasmid_size_bp,
                )
                action = "created"
                
            return dmc.Notification(
                title="Success",
                id="construct-notification",
                action="show",
                message=f"Construct successfully {action}",
                color="green",
                icon=DashIconify(icon="mdi:check-circle")
            )
            
        except ConstructValidationError as e:
            logger.warning("Construct validation error", error=str(e))
            return dmc.Notification(
                title="Validation Error",
                id="construct-notification",
                action="show",
                message=str(e),
                color="red",
                icon=DashIconify(icon="mdi:alert-circle")
            )
        except Exception as e:
            logger.exception("Error submitting construct")
            return dmc.Notification(
                title="Error",
                id="construct-notification",
                action="show",
                message="An unexpected error occurred. Please try again.",
                color="red",
                icon=DashIconify(icon="mdi:alert-circle")
            )

    @app.callback(
        [
             Output("construct-delete-modal", "opened"),
             Output("construct-delete-message", "children"),
             # No output needed for store, we use side-effect
        ],
        Input({"type": "construct-delete-btn", "index": ALL}, "n_clicks"),
        State("construct-registry-data-store", "data"),
        prevent_initial_call=True
    )
    def open_delete_modal(n_clicks, constructs):
        """Open delete confirmation modal."""
        if not any(n_clicks):
            raise PreventUpdate
            
        triggered = ctx.triggered_id
        construct_id = triggered["index"]
        construct = next((c for c in constructs if c["id"] == construct_id), None)
        
        name = construct["identifier"] if construct else "this construct"
        
        return (
            True, 
            f"Are you sure you want to delete '{name}'?",
        )

    @app.callback(
        Output("construct-registry-editing-store", "data", allow_duplicate=True),
        Input({"type": "construct-delete-btn", "index": ALL}, "n_clicks"),
        prevent_initial_call=True
    )
    def store_delete_id(n_clicks):
         if not any(n_clicks):
            raise PreventUpdate
         triggered = ctx.triggered_id
         return {"id": triggered["index"], "mode": "delete"}

    @app.callback(
        Output("construct-operation-result", "children", allow_duplicate=True),
        Input("construct-delete-confirm", "n_clicks"),
        [
            State("construct-registry-editing-store", "data"),
            State("user-store", "data"),
        ],
        prevent_initial_call=True
    )
    def confirm_delete(n_clicks, data, user_data):
        if not n_clicks or not data or data.get("mode") != "delete":
            raise PreventUpdate
            
        username = user_data.get("username", "anonymous") if user_data else "anonymous"
        
        try:
            ConstructService.delete_construct(data["id"], username)
            return dmc.Notification(
                title="Success",
                action="show",
                message="Construct deleted",
                color="green"
            )
        except Exception as e:
            logger.exception("Error deleting construct")
            return dmc.Notification(
                title="Error",
                action="show",
                message="An unexpected error occurred while deleting the construct.",
                color="red"
            )

    @app.callback(
        Output("construct-delete-modal", "opened", allow_duplicate=True),
        [
            Input("construct-delete-confirm", "n_clicks"),
            Input("construct-delete-cancel", "n_clicks")
        ],
        prevent_initial_call=True
    )
    def close_delete_modal(confirm, cancel):
        if confirm or cancel:
            return False
        return no_update

    @app.callback(
        Output("construct-operation-result", "children", allow_duplicate=True),
        Input("construct-unregulated-set-btn", "n_clicks"),
        [
             State("construct-unregulated-select", "value"),
             State("construct-registry-project-store", "data"),
             State("user-store", "data"),
        ],
        prevent_initial_call=True
    )
    def set_unregulated(n_clicks, construct_id, project_id, user_data):
        """Set unregulated reference."""
        if not n_clicks or not construct_id:
            raise PreventUpdate

        username = user_data.get("username", "anonymous") if user_data else "anonymous"
        
        try:
            # We need to update the construct to be unregulated
            ConstructService.update_construct(
                construct_id=int(construct_id),
                username=username,
                is_unregulated=True
            )
            return dmc.Notification(
                title="Success",
                action="show",
                message="Unregulated reference set",
                color="green"
            )
        except Exception as e:
            logger.exception("Error setting unregulated reference")
            return dmc.Notification(
                title="Error",
                action="show",
                message="An unexpected error occurred while setting the unregulated reference.",
                color="red"
            )

    @app.callback(
        Output("construct-operation-result", "children", allow_duplicate=True),
        Input({"type": "construct-publish-btn", "index": ALL}, "n_clicks"),
        State("user-store", "data"),
        prevent_initial_call=True
    )
    def publish_construct(n_clicks, user_data):
        """Publish a draft construct."""
        if not any(n_clicks):
            raise PreventUpdate

        triggered = ctx.triggered_id
        if not triggered or not isinstance(triggered, dict):
            raise PreventUpdate

        construct_id = triggered["index"]
        username = user_data.get("username", "anonymous") if user_data else "anonymous"

        try:
            ConstructService.publish_construct(construct_id, username)
            return dmc.Notification(
                title="Success",
                id="construct-notification",
                action="show",
                message="Construct published successfully",
                color="green",
                icon=DashIconify(icon="mdi:check-circle")
            )
        except ConstructValidationError as e:
            logger.warning("Construct publish validation error", error=str(e))
            return dmc.Notification(
                title="Cannot Publish",
                id="construct-notification",
                action="show",
                message=str(e),
                color="orange",
                icon=DashIconify(icon="mdi:alert")
            )
        except Exception as e:
            logger.exception("Error publishing construct")
            return dmc.Notification(
                title="Error",
                id="construct-notification",
                action="show",
                message="An unexpected error occurred while publishing the construct.",
                color="red",
                icon=DashIconify(icon="mdi:alert-circle")
            )

    @app.callback(
        Output("construct-operation-result", "children", allow_duplicate=True),
        Input({"type": "construct-unpublish-btn", "index": ALL}, "n_clicks"),
        State("user-store", "data"),
        prevent_initial_call=True
    )
    def unpublish_construct(n_clicks, user_data):
        """Unpublish a construct (revert to draft)."""
        if not any(n_clicks):
            raise PreventUpdate

        triggered = ctx.triggered_id
        if not triggered or not isinstance(triggered, dict):
            raise PreventUpdate

        construct_id = triggered["index"]
        username = user_data.get("username", "anonymous") if user_data else "anonymous"

        try:
            ConstructService.unpublish_construct(construct_id, username)
            return dmc.Notification(
                title="Success",
                id="construct-notification",
                action="show",
                message="Construct reverted to draft",
                color="blue",
                icon=DashIconify(icon="mdi:check-circle")
            )
        except Exception as e:
            logger.exception("Error unpublishing construct")
            return dmc.Notification(
                title="Error",
                id="construct-notification",
                action="show",
                message="An unexpected error occurred while unpublishing the construct.",
                color="red",
                icon=DashIconify(icon="mdi:alert-circle")
            )
