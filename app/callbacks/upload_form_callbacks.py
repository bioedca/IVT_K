"""
Upload form callbacks for file handling and form controls.

Extracted from upload_callbacks.py during Phase 4 refactoring.

Provides callbacks for:
- File upload handling (single and multi-file)
- Layout and session loading
- Session/date/identifier field toggling
- Parsed date and identifier display
"""
from dash import Output, Input, State, no_update
from dash.exceptions import PreventUpdate

from app.callbacks.upload_utils import (
    parse_uploaded_file,
    extract_identifier_from_filename,
    get_available_layouts,
    get_available_sessions,
)


def register_upload_form_callbacks(app):
    """
    Register upload form-related callbacks.

    Args:
        app: Dash application instance
    """
    @app.callback(
        [
            Output("upload-file-store", "data"),
            Output("upload-files-store", "data"),
            Output("upload-file-info", "children"),
            Output("upload-session-mode-container", "style"),
            Output("upload-preview-file-selector-container", "style"),
            Output("upload-preview-file-select", "data"),
        ],
        [
            Input("upload-dropzone", "contents"),
        ],
        [
            State("upload-dropzone", "filename"),
            State("upload-project-store", "data"),
            State("upload-files-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def handle_file_upload_callback(contents, filenames, _project_store, existing_files):
        """Handle file upload and parse (supports multiple files).

        Dash 4.0's dcc.Upload with multiple=True may deliver files one at
        a time instead of as a single list (platform-dependent).  To handle
        both cases we accumulate: when a single new file arrives we append
        it to the existing store; when a batch arrives we replace.
        """
        import dash_mantine_components as dmc
        from dash_iconify import DashIconify
        from dash import html

        if not contents or not filenames:
            return None, [], None, {"display": "none"}, {"display": "none"}, []

        # Normalize to lists
        if not isinstance(contents, list):
            contents = [contents]
        if not isinstance(filenames, list):
            filenames = [filenames]

        # Parse newly-dropped files
        new_parsed = []
        new_errors = []
        for content, filename in zip(contents, filenames):
            result = parse_uploaded_file(content, filename)
            if result.get("is_valid"):
                new_parsed.append(result)
            else:
                new_errors.append(f"{filename}: {result.get('error', 'Unknown error')}")

        # Accumulate: if a single file arrived and we already have files,
        # append (the Upload may be firing once per file).  If a batch of
        # >1 arrived, treat it as a fresh selection.
        if len(contents) == 1 and existing_files:
            # Deduplicate by filename
            existing_names = {f.get("filename") for f in existing_files}
            for f in new_parsed:
                if f.get("filename") not in existing_names:
                    existing_files.append(f)
            parsed_files = existing_files
        else:
            parsed_files = new_parsed

        # Build info display
        info_items = []
        errors = list(new_errors)
        for f in parsed_files:
            metadata = f.get("metadata", {})
            parsed_date = f.get("parsed_date")
            info_parts = [
                f"{metadata.get('plate_format', 'N/A')}-well",
                f"{metadata.get('num_wells_with_data', 'N/A')} wells",
            ]
            if parsed_date:
                info_parts.append(f"Date: {parsed_date}")
            info_items.append(
                dmc.Group([
                    DashIconify(icon="mdi:file-check", width=16, color="green"),
                    dmc.Text(f.get("filename", "?"), size="sm", fw=500),
                    dmc.Text(" • ".join(info_parts), size="xs", c="dimmed"),
                ], gap="xs")
            )

        if errors and not parsed_files:
            # All files failed to parse
            info = html.Div([
                dmc.Alert(
                    title=f"Parse Errors ({len(errors)} file(s))",
                    children=[dmc.Text(e, size="sm") for e in errors],
                    color="red",
                    icon=DashIconify(icon="mdi:file-alert", width=20),
                ),
            ])
        elif errors:
            # Some files failed, some succeeded
            info = html.Div([
                dmc.Alert(
                    title=f"Parse Errors ({len(errors)} file(s))",
                    children=[dmc.Text(e, size="sm") for e in errors],
                    color="red",
                    icon=DashIconify(icon="mdi:file-alert", width=20),
                ),
                dmc.Alert(
                    title=f"{len(parsed_files)} file(s) ready",
                    children=dmc.Stack(info_items, gap="xs"),
                    color="green",
                    icon=DashIconify(icon="mdi:file-check", width=20),
                    mt="sm",
                ),
            ])
        elif len(parsed_files) == 1:
            info = dmc.Alert(
                title=parsed_files[0].get("filename", "File"),
                children=dmc.Stack(info_items, gap="xs"),
                color="green",
                icon=DashIconify(icon="mdi:file-check", width=20),
            )
        else:
            info = dmc.Alert(
                title=f"{len(parsed_files)} files ready for upload",
                children=dmc.Stack(info_items, gap="xs"),
                color="green",
                icon=DashIconify(icon="mdi:file-multiple", width=20),
            )

        # Show/hide session mode toggle based on file count
        session_mode_style = {"display": "block"} if len(parsed_files) > 1 else {"display": "none"}

        # Show/hide file selector for preview
        file_selector_style = {"display": "block"} if len(parsed_files) > 1 else {"display": "none"}

        # Build file selector options
        file_options = [
            {"value": str(i), "label": f.get("filename", f"File {i+1}")}
            for i, f in enumerate(parsed_files)
        ]

        primary_file = parsed_files[0] if parsed_files else None
        return primary_file, parsed_files, info, session_mode_style, file_selector_style, file_options

    @app.callback(
        Output("upload-layout-select", "data"),
        Input("upload-project-store", "data"),
        prevent_initial_call=False,
    )
    def load_layouts_callback(project_store):
        """Load available layouts for project."""
        if not project_store or not project_store.get("project_id"):
            return []

        layouts = get_available_layouts(project_store["project_id"])
        return [
            {"value": str(layout["id"]), "label": layout["name"]}
            for layout in layouts
        ]

    @app.callback(
        Output("upload-session-select", "data"),
        Input("upload-project-store", "data"),
        prevent_initial_call=False,
    )
    def load_sessions_callback(project_store):
        """Load available sessions for project."""
        if not project_store or not project_store.get("project_id"):
            return [{"value": "new", "label": "Create new session"}]

        sessions = get_available_sessions(project_store["project_id"])
        options = [{"value": "new", "label": "Create new session"}]
        for s in sessions:
            label = f"{s.get('date', 'Unknown')} - {s.get('batch_id', s.get('id'))}"
            options.append({"value": str(s["id"]), "label": label})

        return options

    @app.callback(
        Output("upload-new-session-fields", "style"),
        Input("upload-session-select", "value"),
        prevent_initial_call=False,
    )
    def toggle_new_session_fields(session_value):
        """Show/hide new session fields."""
        if session_value == "new":
            return {"display": "block"}
        return {"display": "none"}

    @app.callback(
        [
            Output("upload-manual-date-fields", "style"),
            Output("upload-parsed-date-display", "style"),
        ],
        Input("upload-parse-date-switch", "checked"),
        prevent_initial_call=False,
    )
    def toggle_date_fields(parse_from_file):
        """Toggle visibility of manual date input vs parsed date display."""
        if parse_from_file:
            # Hide manual date input, show parsed date display
            return {"display": "none"}, {"display": "block"}
        else:
            # Show manual date input, hide parsed date display
            return {"display": "block"}, {"display": "none"}

    @app.callback(
        Output("upload-session-mode-hint", "children"),
        Input("upload-session-mode-switch", "checked"),
        prevent_initial_call=False,
    )
    def update_session_mode_hint(one_session_per_file):
        """Update hint text based on session mode selection."""
        if one_session_per_file:
            return "Each plate file will be uploaded as a separate session with its own date."
        else:
            return "All plate files will be uploaded into a single session (use for multiple plates from the same day)."

    @app.callback(
        Output("upload-parsed-date-alert", "children"),
        Output("upload-parsed-date-alert", "title"),
        Output("upload-parsed-date-alert", "color"),
        Input("upload-file-store", "data"),
        State("upload-parse-date-switch", "checked"),
        prevent_initial_call=True,
    )
    def update_parsed_date_display(file_store, parse_from_file):
        """Update the parsed date display when a file is uploaded."""
        if not parse_from_file:
            raise PreventUpdate

        if not file_store:
            return (
                "Upload a file to extract the session date",
                "Date will be parsed from file",
                "blue",
            )

        parsed_date = file_store.get("parsed_date")
        if parsed_date:
            return (
                f"Parsed date: {parsed_date}",
                "Date extracted from file",
                "green",
            )
        else:
            # No date found in file, will use today's date
            from datetime import date
            return (
                f"No date found in file. Will use today's date: {date.today().isoformat()}",
                "Using default date",
                "yellow",
            )

    @app.callback(
        Output("upload-parsed-identifier-display", "style"),
        Input("upload-parse-identifier-switch", "checked"),
        prevent_initial_call=False,
    )
    def toggle_identifier_display(parse_from_file):
        """Toggle visibility of parsed identifier display."""
        if parse_from_file:
            return {"display": "block"}
        else:
            return {"display": "none"}

    @app.callback(
        [
            Output("upload-parsed-identifier-alert", "children"),
            Output("upload-parsed-identifier-alert", "title"),
            Output("upload-parsed-identifier-alert", "color"),
            Output("upload-session-batch", "value", allow_duplicate=True),
        ],
        [
            Input("upload-file-store", "data"),
            Input("upload-parse-identifier-switch", "checked"),
        ],
        State("user-store", "data"),
        prevent_initial_call=True,
    )
    def update_parsed_identifier_display(file_store, parse_from_file, user_data):
        """Update the parsed identifier display when a file is uploaded."""
        # Get username for default
        username = user_data.get("username", "user") if user_data else "user"

        if not parse_from_file:
            # Not parsing from file - use username as default
            return (
                no_update,
                no_update,
                no_update,
                username,
            )

        if not file_store:
            return (
                f"Upload a file to extract the identifier (default: {username})",
                "Identifier will be parsed from filename",
                "blue",
                "",  # Clear the field until file is uploaded
            )

        filename = file_store.get("filename", "")
        parsed_id = extract_identifier_from_filename(filename)

        if parsed_id:
            return (
                f"Parsed identifier: {parsed_id}",
                "Identifier extracted from filename",
                "green",
                parsed_id,  # Pre-populate the field
            )
        else:
            # No identifier found in filename, will use username
            return (
                f"No identifier found in filename. Using: {username}",
                "Using default identifier",
                "yellow",
                username,
            )
