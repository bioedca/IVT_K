"""
Callbacks for the Interactive Repair Wizard.

Phase 3.7: Interactive Repair Wizard (F6.7)

Handles:
- Wizard step navigation
- Header row detection
- Skip row configuration
- Column mapping
- Data preview and import
"""
from typing import Optional, Dict, Any, List, Tuple
import re

from dash import callback, Input, Output, State, ctx, no_update, ALL, MATCH
from dash.exceptions import PreventUpdate
import dash_mantine_components as dmc

from app.layouts.repair_wizard import (
    create_step1_preview,
    create_step2_header_row,
    create_step3_skip_rows,
    create_step4_column_mapping,
    create_step5_preview_data,
    create_repair_wizard_error,
)


def register_repair_callbacks(app):
    """Register all repair wizard callbacks."""

    @app.callback(
        Output("repair-wizard-step-content", "children"),
        Output("repair-wizard-stepper", "active"),
        Output("repair-wizard-back-btn", "disabled"),
        Output("repair-wizard-next-btn", "style"),
        Output("repair-wizard-import-btn", "style"),
        Input("repair-wizard-state", "data"),
        prevent_initial_call=True,
    )
    def render_wizard_step(state: Dict[str, Any]):
        """Render the current wizard step content."""
        if not state:
            raise PreventUpdate

        step = state.get("step", 1)
        file_lines = state.get("file_lines", [])

        # Determine button visibility
        back_disabled = step <= 1
        show_next = {"display": "block"} if step < 5 else {"display": "none"}
        show_import = {"display": "block"} if step == 5 else {"display": "none"}

        if step == 1:
            content = create_step1_preview(
                file_lines=file_lines,
                issue_message=state.get("issue_message", "File parsing failed")
            )
        elif step == 2:
            content = create_step2_header_row(
                file_lines=file_lines,
                suggested_row=state.get("header_row")
            )
        elif step == 3:
            content = create_step3_skip_rows(
                file_lines=file_lines,
                header_row=state.get("header_row", 1),
                suggested_skips=state.get("skip_rows")
            )
        elif step == 4:
            columns = state.get("columns", [])
            content = create_step4_column_mapping(
                columns=columns,
                suggested_mapping=state.get("column_mapping")
            )
        elif step == 5:
            preview = state.get("parsed_preview", {})
            content = create_step5_preview_data(
                preview_data=preview,
                num_wells=preview.get("num_wells", 0),
                num_timepoints=preview.get("num_timepoints", 0),
                sample_wells=preview.get("sample_wells", [])
            )
        else:
            content = create_repair_wizard_error("Invalid wizard step")

        return content, step - 1, back_disabled, show_next, show_import

    @app.callback(
        Output("repair-wizard-state", "data", allow_duplicate=True),
        Input("repair-wizard-next-btn", "n_clicks"),
        State("repair-wizard-state", "data"),
        State("repair-header-row-input", "value"),
        State("repair-skip-rows-input", "value"),
        State({"type": "skip-row-checkbox", "index": ALL}, "checked"),
        State({"type": "skip-row-checkbox", "index": ALL}, "id"),
        State("repair-time-column", "value"),
        State("repair-temp-column", "value"),
        State("repair-first-well-column", "value"),
        State("repair-auto-detect-wells", "checked"),
        prevent_initial_call=True,
    )
    def handle_next_click(
        n_clicks,
        state,
        header_row,
        skip_rows_input,
        skip_checkboxes,
        skip_checkbox_ids,
        time_column,
        temp_column,
        first_well_column,
        auto_detect_wells,
    ):
        """Handle next button click - save current step and advance."""
        if not n_clicks or not state:
            raise PreventUpdate

        step = state.get("step", 1)
        new_state = dict(state)

        # Save data from current step
        if step == 2:
            # Save header row
            new_state["header_row"] = header_row
            # Extract columns from header row
            file_lines = state.get("file_lines", [])
            if header_row and header_row <= len(file_lines):
                header_line = file_lines[header_row - 1]
                columns = _parse_columns_from_header(header_line)
                new_state["columns"] = columns

        elif step == 3:
            # Save skip rows
            skip_rows = []

            # From checkboxes
            if skip_checkboxes and skip_checkbox_ids:
                for checked, id_dict in zip(skip_checkboxes, skip_checkbox_ids):
                    if checked:
                        skip_rows.append(id_dict["index"])

            # From manual input
            if skip_rows_input:
                manual_skips = _parse_skip_rows_input(skip_rows_input)
                skip_rows.extend(manual_skips)

            new_state["skip_rows"] = sorted(set(skip_rows))

        elif step == 4:
            # Save column mapping
            new_state["column_mapping"] = {
                "time": time_column,
                "temperature": temp_column,
                "first_well": first_well_column,
                "auto_detect_wells": auto_detect_wells,
            }

            # Generate preview data
            preview = _generate_preview(new_state)
            new_state["parsed_preview"] = preview

        # Advance to next step
        new_state["step"] = min(step + 1, 5)

        return new_state

    @app.callback(
        Output("repair-wizard-state", "data", allow_duplicate=True),
        Input("repair-wizard-back-btn", "n_clicks"),
        State("repair-wizard-state", "data"),
        prevent_initial_call=True,
    )
    def handle_back_click(n_clicks, state):
        """Handle back button click."""
        if not n_clicks or not state:
            raise PreventUpdate

        new_state = dict(state)
        new_state["step"] = max(state.get("step", 1) - 1, 1)

        return new_state

    @app.callback(
        Output("repair-wizard-modal", "opened", allow_duplicate=True),
        Output("repair-wizard-state", "data", allow_duplicate=True),
        Input("repair-wizard-cancel-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def handle_cancel_click(n_clicks):
        """Handle cancel button click."""
        if not n_clicks:
            raise PreventUpdate

        # Close modal and reset state
        return False, {
            "step": 1,
            "file_content": None,
            "file_lines": [],
            "header_row": None,
            "skip_rows": [],
            "column_mapping": {},
            "parsed_preview": None,
        }

    @app.callback(
        Output("repair-header-preview", "children"),
        Input("repair-header-row-input", "value"),
        State("repair-wizard-state", "data"),
        prevent_initial_call=True,
    )
    def update_header_preview(row_num, state):
        """Update the header row preview when selection changes."""
        if not row_num or not state:
            raise PreventUpdate

        file_lines = state.get("file_lines", [])

        if row_num <= 0 or row_num > len(file_lines):
            return [
                dmc.Text("Selected header row:", size="sm", weight=500),
                dmc.Text("Invalid line number", color="red"),
            ]

        line = file_lines[row_num - 1]
        columns = _parse_columns_from_header(line)

        return [
            dmc.Text("Selected header row:", size="sm", weight=500),
            dmc.Code(line[:200] + ("..." if len(line) > 200 else ""), block=True),
            dmc.Text(f"Detected {len(columns)} columns", size="xs", color="dimmed", mt="xs"),
        ]

    @app.callback(
        Output("repair-skip-summary", "children"),
        Input({"type": "skip-row-checkbox", "index": ALL}, "checked"),
        Input("repair-skip-rows-input", "value"),
        State({"type": "skip-row-checkbox", "index": ALL}, "id"),
        prevent_initial_call=True,
    )
    def update_skip_summary(checkboxes, manual_input, checkbox_ids):
        """Update the skip rows summary."""
        skip_rows = []

        # From checkboxes
        if checkboxes and checkbox_ids:
            for checked, id_dict in zip(checkboxes, checkbox_ids):
                if checked:
                    skip_rows.append(id_dict["index"])

        # From manual input
        if manual_input:
            manual_skips = _parse_skip_rows_input(manual_input)
            skip_rows.extend(manual_skips)

        skip_rows = sorted(set(skip_rows))

        if not skip_rows:
            return [
                dmc.Text("Rows to be skipped:", size="sm", weight=500),
                dmc.Text("None selected", size="sm", color="dimmed"),
            ]

        # Format as ranges for display
        ranges = _format_row_ranges(skip_rows)

        return [
            dmc.Text("Rows to be skipped:", size="sm", weight=500),
            dmc.Text(f"{len(skip_rows)} rows: {ranges}", size="sm"),
        ]


def _parse_columns_from_header(header_line: str) -> List[str]:
    """
    Parse column names from a header line.

    Args:
        header_line: Header line from file

    Returns:
        List of column names
    """
    # Try tab-separated first
    if '\t' in header_line:
        columns = header_line.split('\t')
    else:
        # Try comma-separated
        columns = header_line.split(',')

    # Clean up column names
    return [c.strip() for c in columns if c.strip()]


def _parse_skip_rows_input(input_str: str) -> List[int]:
    """
    Parse skip rows input string.

    Supports formats like:
    - "92-115" (range)
    - "92, 93, 94" (list)
    - "92-115, 200, 205-210" (mixed)

    Args:
        input_str: User input string

    Returns:
        List of row numbers to skip
    """
    rows = []
    if not input_str:
        return rows

    # Split by comma
    parts = input_str.split(',')

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Check for range
        if '-' in part:
            match = re.match(r'(\d+)\s*-\s*(\d+)', part)
            if match:
                start, end = int(match.group(1)), int(match.group(2))
                rows.extend(range(start, end + 1))
        else:
            # Single number
            try:
                rows.append(int(part))
            except ValueError:
                pass

    return rows


def _format_row_ranges(rows: List[int]) -> str:
    """
    Format a list of row numbers into ranges for display.

    Args:
        rows: Sorted list of row numbers

    Returns:
        Formatted string like "92-115, 200, 205-210"
    """
    if not rows:
        return "None"

    ranges = []
    start = rows[0]
    end = rows[0]

    for row in rows[1:]:
        if row == end + 1:
            end = row
        else:
            if start == end:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}-{end}")
            start = row
            end = row

    # Add final range
    if start == end:
        ranges.append(str(start))
    else:
        ranges.append(f"{start}-{end}")

    return ", ".join(ranges)


def _generate_preview(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate preview data using current repair settings.

    Args:
        state: Current wizard state

    Returns:
        Preview data dict
    """
    file_lines = state.get("file_lines", [])
    header_row = state.get("header_row", 1)
    skip_rows = set(state.get("skip_rows", []))
    column_mapping = state.get("column_mapping", {})

    if not file_lines or not header_row:
        return {"error": "Invalid configuration"}

    # Get columns from header
    columns = _parse_columns_from_header(file_lines[header_row - 1])

    # Find well columns
    time_col = column_mapping.get("time")
    first_well = column_mapping.get("first_well")
    auto_detect = column_mapping.get("auto_detect_wells", True)

    well_columns = []
    if first_well and first_well in columns:
        start_idx = columns.index(first_well)
        if auto_detect:
            # Include all columns after first well that look like well positions
            well_pattern = re.compile(r'^[A-H](0?[1-9]|1[0-2])$', re.IGNORECASE)
            for col in columns[start_idx:]:
                if well_pattern.match(col.strip()):
                    well_columns.append(col)
        else:
            well_columns = [first_well]

    # Count data rows
    data_rows = 0
    for i, line in enumerate(file_lines[header_row:], header_row + 1):
        if i not in skip_rows and line.strip():
            data_rows += 1

    return {
        "num_wells": len(well_columns),
        "num_timepoints": data_rows,
        "sample_wells": well_columns[:50],
        "columns": columns,
        "temperature_setpoint": "Detected",
        "time_column": time_col,
        "first_well_column": first_well,
    }


def open_repair_wizard(
    file_content: str,
    issue_message: str = "File parsing failed"
) -> Dict[str, Any]:
    """
    Initialize repair wizard state for a file with issues.

    Args:
        file_content: Raw file content
        issue_message: Description of the parsing issue

    Returns:
        Initial wizard state
    """
    file_lines = file_content.split('\n')

    # Try to detect header row
    suggested_header = None
    for i, line in enumerate(file_lines[:100], 1):
        lower = line.lower()
        if 'time' in lower and ('a1' in lower or 'temperature' in lower):
            suggested_header = i
            break

    return {
        "step": 1,
        "file_content": file_content,
        "file_lines": file_lines,
        "header_row": suggested_header,
        "skip_rows": [],
        "column_mapping": {},
        "parsed_preview": None,
        "issue_message": issue_message,
    }


def apply_repair_settings(
    file_content: str,
    state: Dict[str, Any]
) -> Tuple[str, Dict[str, str]]:
    """
    Apply repair settings to generate repaired file content.

    Args:
        file_content: Original file content
        state: Wizard state with repair settings

    Returns:
        Tuple of (repaired_content, metadata)
    """
    file_lines = file_content.split('\n')
    header_row = state.get("header_row", 1)
    skip_rows = set(state.get("skip_rows", []))
    column_mapping = state.get("column_mapping", {})

    # Build repaired content
    output_lines = []

    # Include lines from header row onwards, excluding skip rows
    for i, line in enumerate(file_lines[header_row - 1:], header_row):
        if i not in skip_rows:
            output_lines.append(line)

    repaired_content = '\n'.join(output_lines)

    metadata = {
        "original_header_row": str(header_row),
        "skipped_rows": ",".join(map(str, sorted(skip_rows))),
        "time_column": column_mapping.get("time", ""),
        "temp_column": column_mapping.get("temperature", ""),
        "first_well": column_mapping.get("first_well", ""),
    }

    return repaired_content, metadata
