"""
Upload processing callbacks for validation, preview, and submission.

Extracted from upload_callbacks.py during Phase 4 refactoring.

Provides callbacks for:
- File validation against layout
- Data preview with curve plots
- Submit button state management
- Upload submission (single and multi-file)
- Toast countdown and form reset
- Cancel and navigation
"""
from dash import Output, Input, State, no_update
from dash.exceptions import PreventUpdate

from app.callbacks.upload_utils import (
    validate_upload_file,
    validate_upload_form,
    create_preview_panel,
    process_upload,
)


def register_upload_processing_callbacks(app):
    """
    Register upload processing-related callbacks.

    Args:
        app: Dash application instance
    """
    @app.callback(
        [
            Output("upload-validation-store", "data"),
            Output("upload-validation-container", "children"),
        ],
        [
            Input("upload-file-store", "data"),
            Input("upload-layout-select", "value"),
        ],
        [
            State("upload-project-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def validate_upload_callback(file_store, layout_id, project_store):
        """Validate upload when file or layout changes."""
        from app.layouts.data_upload import create_validation_panel

        if not file_store or not layout_id or not project_store:
            return None, create_validation_panel(None)

        project_id = project_store.get("project_id")
        file_content = file_store.get("content")
        filename = file_store.get("filename")

        if not file_content:
            return None, create_validation_panel(None)

        result = validate_upload_file(project_id, int(layout_id), file_content, filename)
        return result, create_validation_panel(result)

    @app.callback(
        Output("upload-preview-plot-container", "children"),
        [
            Input("upload-files-store", "data"),
            Input("upload-layout-select", "value"),
            Input("upload-preview-file-select", "value"),
            Input("upload-preview-max-wells", "value"),
        ],
        Input("color-scheme-store", "data"),
        prevent_initial_call=True,
    )
    def update_preview_callback(files_store, layout_id, selected_file_index, max_wells, scheme):
        """Update preview when file, layout, selection, or max wells changes."""
        from dash import html
        from dash_iconify import DashIconify
        import dash_mantine_components as dmc

        # Default max wells to 21
        if max_wells is None:
            max_wells = 21

        # Handle empty file list
        if not files_store or not layout_id:
            return html.Div(
                children=[
                    DashIconify(icon="mdi:chart-scatter-plot", width=48, color="#adb5bd"),
                    dmc.Text("Data preview will appear here", size="sm", c="dimmed", mt="md"),
                ],
                style={"textAlign": "center", "padding": "2rem"},
            )

        # Get the file to preview (default to first file)
        file_index = int(selected_file_index) if selected_file_index else 0
        if file_index >= len(files_store):
            file_index = 0

        file_store = files_store[file_index]

        # Get parsed data from file store
        parsed_data = file_store.get("parsed_data")
        if not parsed_data:
            return html.Div(
                children=[
                    DashIconify(icon="mdi:chart-scatter-plot", width=48, color="#adb5bd"),
                    dmc.Text("No data to preview", size="sm", c="dimmed", mt="md"),
                ],
                style={"textAlign": "center", "padding": "2rem"},
            )

        # Get well data and timepoints
        well_data = parsed_data.get("well_data", {})
        timepoints = parsed_data.get("timepoints", [])

        if not well_data or not timepoints:
            return html.Div(
                children=[
                    DashIconify(icon="mdi:chart-scatter-plot", width=48, color="#adb5bd"),
                    dmc.Text("No well data found", size="sm", c="dimmed", mt="md"),
                ],
                style={"textAlign": "center", "padding": "2rem"},
            )

        # Get layout well assignments (non-empty wells)
        try:
            from app.models import PlateLayout, WellAssignment
            from app.models.plate_layout import WellType

            layout = PlateLayout.query.get(int(layout_id))
            if not layout:
                return html.Div(
                    children=[
                        DashIconify(icon="mdi:alert", width=48, color="#adb5bd"),
                        dmc.Text("Layout not found", size="sm", c="dimmed", mt="md"),
                    ],
                    style={"textAlign": "center", "padding": "2rem"},
                )

            # Get non-empty well assignments
            filled_assignments = WellAssignment.query.filter(
                WellAssignment.layout_id == layout.id,
                WellAssignment.well_type != WellType.EMPTY
            ).all()

            # Get positions of filled wells that also have data in the uploaded file
            filled_positions = {a.well_position for a in filled_assignments}
            wells_to_plot = [pos for pos in well_data.keys() if pos in filled_positions]

            if not wells_to_plot:
                return html.Div(
                    children=[
                        DashIconify(icon="mdi:alert", width=48, color="#adb5bd"),
                        dmc.Text("No matching wells found", size="sm", c="dimmed", mt="md"),
                    ],
                    style={"textAlign": "center", "padding": "2rem"},
                )

            # Create preview plot with specified max wells
            dark_mode = (scheme == "dark")
            return create_preview_panel(wells_to_plot, well_data, timepoints, filled_assignments, max_wells=max_wells, dark_mode=dark_mode)

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error creating preview: {e}")
            return _create_preview_placeholder()

    @app.callback(
        Output("upload-submit-btn", "disabled"),
        [
            Input("upload-validation-store", "data"),
            Input("upload-file-store", "data"),
            Input("upload-layout-select", "value"),
            Input("upload-session-select", "value"),
        ],
        prevent_initial_call=False,
    )
    def update_submit_button(validation, file_store, layout_id, session_value):
        """Enable/disable submit button based on form state."""
        form_result = validate_upload_form(
            has_file=bool(file_store and file_store.get("content")),
            has_layout=bool(layout_id),
            has_session_option=bool(session_value),
            validation_passed=bool(validation and validation.get("is_valid")),
        )
        return not form_result["can_submit"]

    @app.callback(
        [
            Output("upload-success-toast", "children"),
            Output("upload-success-store", "data"),
            Output("upload-error-notification", "children"),
            Output("upload-toast-countdown", "data"),
            Output("upload-toast-interval", "disabled"),
        ],
        Input("upload-submit-btn", "n_clicks"),
        [
            State("upload-project-store", "data"),
            State("upload-file-store", "data"),
            State("upload-files-store", "data"),
            State("upload-layout-select", "value"),
            State("upload-session-select", "value"),
            State("upload-session-date", "value"),
            State("upload-session-batch", "value"),
            State("upload-plate-number", "value"),
            State("upload-suppressed-warnings-store", "data"),
            State("upload-parse-date-switch", "checked"),
            State("upload-session-mode-switch", "checked"),
            State("user-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def submit_upload_callback(
        n_clicks,
        project_store,
        file_store,
        files_store,
        layout_id,
        session_value,
        session_date,
        batch_id,
        plate_number,
        suppressed_warnings,
        parse_date_from_file,
        one_session_per_file,
        user_data,
    ):
        """Process upload submission (supports multiple files)."""
        import dash_mantine_components as dmc
        from dash_iconify import DashIconify

        if not n_clicks:
            raise PreventUpdate

        if not project_store or not layout_id:
            raise PreventUpdate

        # Get files to process
        files_to_process = files_store if files_store else ([file_store] if file_store else [])
        if not files_to_process:
            raise PreventUpdate

        project_id = project_store["project_id"]

        # Get username for default batch ID and audit logging
        username = user_data.get("username", "user") if user_data else "user"

        # Use username as default batch_id if not provided
        effective_batch_id = batch_id if batch_id and batch_id.strip() else username

        # Track results for all files
        total_wells_created = 0
        total_plates_created = 0
        errors = []
        session_ids = set()

        # Determine session handling
        shared_session_id = None
        if not one_session_per_file and len(files_to_process) > 1:
            # All files go into a single session - use first file's date or manual date
            if parse_date_from_file and files_to_process[0].get("parsed_date"):
                use_date = files_to_process[0].get("parsed_date")
            elif not parse_date_from_file:
                use_date = session_date
            else:
                use_date = None

            # Create the shared session with first upload
            first_file = files_to_process[0]
            result = process_upload(
                project_id=project_id,
                layout_id=int(layout_id),
                file_content=first_file.get("content", ""),
                filename=first_file.get("filename", "upload.txt"),
                session_option=session_value,
                session_date=use_date,
                username=username,
                batch_id=effective_batch_id,
                plate_number=plate_number or 1,
                suppressed_warnings=suppressed_warnings or [],
            )

            if result["success"]:
                shared_session_id = result.get("session_id")
                total_wells_created += result.get("wells_created", 0)
                total_plates_created += 1
                session_ids.add(shared_session_id)
            else:
                errors.append(f"{first_file.get('filename')}: {result.get('error')}")

            # Process remaining files into the same session
            for i, file_data in enumerate(files_to_process[1:], start=2):
                result = process_upload(
                    project_id=project_id,
                    layout_id=int(layout_id),
                    file_content=file_data.get("content", ""),
                    filename=file_data.get("filename", f"upload_{i}.txt"),
                    session_option=str(shared_session_id),  # Use the shared session
                    session_date=None,  # Not needed for existing session
                    username=username,
                    batch_id=None,
                    plate_number=(plate_number or 1) + i - 1,
                    suppressed_warnings=suppressed_warnings or [],
                )

                if result["success"]:
                    total_wells_created += result.get("wells_created", 0)
                    total_plates_created += 1
                else:
                    errors.append(f"{file_data.get('filename')}: {result.get('error')}")
        else:
            # One session per file (default) or single file
            for i, file_data in enumerate(files_to_process, start=1):
                # Determine date for this file
                if parse_date_from_file and file_data.get("parsed_date"):
                    use_date = file_data.get("parsed_date")
                elif not parse_date_from_file:
                    use_date = session_date
                else:
                    use_date = None

                # Generate unique batch ID for each file if creating new sessions
                file_batch_id = effective_batch_id
                if session_value == "new" and len(files_to_process) > 1:
                    base_batch = effective_batch_id
                    file_batch_id = f"{base_batch}_{i}"

                result = process_upload(
                    project_id=project_id,
                    layout_id=int(layout_id),
                    file_content=file_data.get("content", ""),
                    filename=file_data.get("filename", f"upload_{i}.txt"),
                    session_option=session_value,
                    session_date=use_date,
                    username=username,
                    batch_id=file_batch_id,
                    plate_number=plate_number or 1,
                    suppressed_warnings=suppressed_warnings or [],
                )

                if result["success"]:
                    total_wells_created += result.get("wells_created", 0)
                    total_plates_created += 1
                    if result.get("session_id"):
                        session_ids.add(result.get("session_id"))
                else:
                    errors.append(f"{file_data.get('filename')}: {result.get('error')}")

        # Helper to create toast with countdown
        def create_success_toast(title, message, color, icon_name, countdown=5):
            return dmc.Alert(
                id="upload-success-notification",
                title=title,
                children=[
                    dmc.Text(message, size="sm"),
                    dmc.Text(
                        f"This message will close in {countdown} seconds...",
                        size="xs",
                        c="dimmed",
                        mt="xs",
                        id="upload-toast-countdown-text",
                    ),
                ],
                color=color,
                icon=DashIconify(icon=icon_name, width=20),
                withCloseButton=True,
                style={"width": "400px"},
            )

        # Build response
        if errors and total_plates_created == 0:
            # Complete failure - no countdown needed
            error_alert = dmc.Alert(
                title="Upload Failed",
                children=[dmc.Text(e, size="sm") for e in errors],
                color="red",
                icon=DashIconify(icon="mdi:alert-circle", width=20),
                withCloseButton=True,
                style={"marginBottom": "1rem"},
            )
            return no_update, no_update, error_alert, no_update, True  # Keep interval disabled
        elif errors:
            # Partial success
            message = f"{total_plates_created} plate(s) uploaded ({total_wells_created} wells). {len(errors)} file(s) failed."
            success_toast = create_success_toast(
                "Upload Partially Successful",
                message,
                "yellow",
                "mdi:alert",
            )
            error_alert = dmc.Alert(
                title=f"{len(errors)} file(s) failed",
                children=[dmc.Text(e, size="sm") for e in errors],
                color="red",
                icon=DashIconify(icon="mdi:alert-circle", width=20),
                withCloseButton=True,
                style={"marginBottom": "1rem"},
            )
            success_data = {
                "success": True,
                "plates_created": total_plates_created,
                "wells_created": total_wells_created,
                "session_ids": list(session_ids),
            }
            return success_toast, success_data, error_alert, 5, False  # Start countdown at 5, enable interval
        else:
            # Complete success
            if total_plates_created == 1:
                message = f"File uploaded successfully. {total_wells_created} wells created."
            else:
                message = f"{total_plates_created} plates uploaded successfully. {total_wells_created} total wells created."

            success_toast = create_success_toast(
                "Upload Successful!",
                message,
                "green",
                "mdi:check-circle",
            )
            success_data = {
                "success": True,
                "plates_created": total_plates_created,
                "wells_created": total_wells_created,
                "session_ids": list(session_ids),
            }
            return success_toast, success_data, no_update, 5, False  # Start countdown at 5, enable interval

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("upload-cancel-btn", "n_clicks"),
        State("upload-project-store", "data"),
        prevent_initial_call=True,
    )
    def cancel_upload_callback(n_clicks, project_store):
        """Handle cancel button."""
        if not n_clicks:
            raise PreventUpdate

        if project_store and project_store.get("project_id"):
            return f"/project/{project_store['project_id']}"
        return "/projects"

    @app.callback(
        [
            Output("upload-toast-countdown", "data", allow_duplicate=True),
            Output("upload-success-toast", "children", allow_duplicate=True),
            Output("upload-toast-interval", "disabled", allow_duplicate=True),
            Output("upload-success-store", "data", allow_duplicate=True),
        ],
        Input("upload-toast-interval", "n_intervals"),
        [
            State("upload-toast-countdown", "data"),
            State("upload-success-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def update_toast_countdown(n_intervals, countdown, success_data):
        """Update the countdown timer on the success toast."""
        import dash_mantine_components as dmc
        from dash_iconify import DashIconify

        if countdown is None or countdown <= 0:
            raise PreventUpdate

        new_countdown = countdown - 1

        if new_countdown <= 0:
            # Time's up - clear toast and trigger form reset
            return None, None, True, success_data  # This will trigger reset_form_after_success

        # Update toast with new countdown
        if success_data:
            plates = success_data.get("plates_created", 1)
            wells = success_data.get("wells_created", 0)
            if plates == 1:
                message = f"File uploaded successfully. {wells} wells created."
                title = "Upload Successful!"
                color = "green"
                icon_name = "mdi:check-circle"
            else:
                message = f"{plates} plates uploaded successfully. {wells} total wells created."
                title = "Upload Successful!"
                color = "green"
                icon_name = "mdi:check-circle"
        else:
            message = "Upload completed."
            title = "Upload Successful!"
            color = "green"
            icon_name = "mdi:check-circle"

        updated_toast = dmc.Alert(
            id="upload-success-notification",
            title=title,
            children=[
                dmc.Text(message, size="sm"),
                dmc.Text(
                    f"This message will close in {new_countdown} second{'s' if new_countdown != 1 else ''}...",
                    size="xs",
                    c="dimmed",
                    mt="xs",
                ),
            ],
            color=color,
            icon=DashIconify(icon=icon_name, width=20),
            withCloseButton=True,
            style={"width": "400px"},
        )

        return new_countdown, updated_toast, False, no_update

    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("upload-goto-qc-btn", "n_clicks"),
        State("upload-project-store", "data"),
        prevent_initial_call=True,
    )
    def goto_qc_callback(n_clicks, project_store):
        """Handle Go to QC Review button."""
        if not n_clicks:
            raise PreventUpdate

        if project_store and project_store.get("project_id"):
            return f"/project/{project_store['project_id']}/qc"
        raise PreventUpdate

    @app.callback(
        [
            Output("upload-file-store", "data", allow_duplicate=True),
            Output("upload-file-info", "children", allow_duplicate=True),
            Output("upload-validation-store", "data", allow_duplicate=True),
            Output("upload-validation-container", "children", allow_duplicate=True),
            Output("upload-preview-container", "children", allow_duplicate=True),
            Output("upload-layout-select", "value", allow_duplicate=True),
            Output("upload-session-select", "value", allow_duplicate=True),
            Output("upload-session-date", "value", allow_duplicate=True),
            Output("upload-session-batch", "value", allow_duplicate=True),
            Output("upload-plate-number", "value", allow_duplicate=True),
            Output("upload-success-toast", "children", allow_duplicate=True),
            Output("upload-success-store", "data", allow_duplicate=True),
        ],
        Input("upload-success-store", "data"),
        [
            State("upload-project-store", "data"),
            State("user-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def reset_form_after_success(success_data, project_store, user_data):
        """Reset the form after successful upload to allow another upload."""
        import dash_mantine_components as dmc
        from dash_iconify import DashIconify
        from app.layouts.data_upload import create_validation_panel, _create_preview_placeholder

        if not success_data or not success_data.get("success"):
            raise PreventUpdate

        # Reset all form fields for a new upload
        file_info = dmc.Alert(
            title="Ready for new upload",
            children="Previous file uploaded successfully. You can now upload another file.",
            color="blue",
            icon=DashIconify(icon="mdi:information", width=20),
        )

        return (
            None,  # Clear file store
            file_info,  # File info message
            None,  # Clear validation store
            create_validation_panel(),  # Reset validation panel
            _create_preview_placeholder(),  # Reset preview
            None,  # Clear layout selection
            "new",  # Reset session to "new"
            None,  # Clear date
            "",  # Clear batch ID
            1,  # Reset plate number
            None,  # Clear toast
            None,  # Clear success store
        )


def _create_preview_placeholder():
    """Create a placeholder for the preview area (fallback for errors)."""
    from app.layouts.data_upload import _create_preview_placeholder as _layout_placeholder
    return _layout_placeholder()
