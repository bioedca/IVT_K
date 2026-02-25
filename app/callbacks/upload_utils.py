"""
Upload utility functions for data upload workflow.

Extracted from upload_callbacks.py during Phase 4 refactoring.

Provides:
- File parsing (BioTek content decoding, date/identifier extraction)
- Validation (file, layout matching, form, temperature QC)
- Upload processing (preview, submission, session handling)
- Data loading (layouts, sessions)
"""
from typing import Optional, Dict, List, Any, Tuple
import base64
from datetime import date

from app.parsers import parse_biotek_content, BioTekParseError
from app.services.upload_service import (
    UploadService,
    UploadValidationError,
    UploadProcessingError,
)
from app.theme import apply_plotly_theme
from app.logging_config import get_logger

logger = get_logger(__name__)


# Temperature QC threshold per PRD Section 3.6
TEMPERATURE_QC_THRESHOLD = 1.0  # ±1°C


# Date patterns for filename parsing used by the DATE PARSER
# These are reliable patterns that can be unambiguously parsed into dates
FILENAME_DATE_PATTERNS = [
    r"\d{4}[-_]?\d{2}[-_]?\d{2}",  # YYYYMMDD or YYYY-MM-DD or YYYY_MM_DD
    r"\d{2}[-_]?\d{2}[-_]?\d{4}",  # MMDDYYYY or MM-DD-YYYY or MM_DD_YYYY
]

# Extended date patterns for IDENTIFIER PARSER only
# These are more aggressive patterns to remove any date-like strings from filenames
# Includes formats that may be ambiguous but look like dates
IDENTIFIER_DATE_PATTERNS = [
    # 8-digit formats (with optional separators)
    r"\d{4}[-_]?\d{2}[-_]?\d{2}",  # YYYYMMDD, YYYY-MM-DD, YYYY_MM_DD
    r"\d{2}[-_]?\d{2}[-_]?\d{4}",  # MMDDYYYY, MM-DD-YYYY, DDMMYYYY, DD_MM_YYYY
    # 6-digit formats (2-digit year) - common in lab filenames
    r"\d{2}[-_]?\d{2}[-_]?\d{2}",  # YYMMDD, YY-MM-DD, MMDDYY, DDMMYY, etc.
]


def extract_identifier_from_filename(filename: str) -> Optional[str]:
    """
    Extract identifier from filename by removing date patterns and extension.

    Takes anything that's not a date pattern as the identifier.
    Uses aggressive date pattern matching to remove any date-like strings,
    including ambiguous formats like YYMMDD (e.g., 260131).

    Args:
        filename: Original filename

    Returns:
        Extracted identifier or None if only date/extension found
    """
    import re

    if not filename:
        return None

    # Remove file extension
    name = filename.rsplit(".", 1)[0] if "." in filename else filename

    # Remove all date-like patterns (uses extended patterns for aggressive removal)
    # Process longer patterns first to avoid partial matches
    for pattern in IDENTIFIER_DATE_PATTERNS:
        name = re.sub(pattern, "", name)

    # Clean up: remove common separators at start/end, multiple underscores/dashes
    name = re.sub(r"^[-_\s]+|[-_\s]+$", "", name)  # Trim separators
    name = re.sub(r"[-_\s]{2,}", "_", name)  # Collapse multiple separators

    # Return None if nothing left or just whitespace
    if not name or not name.strip():
        return None

    return name.strip()


def extract_date_from_content(content: str, filename: str) -> Optional[str]:
    """
    Extract date from file content or filename.

    Tries multiple patterns to extract date:
    1. BioTek-style date headers (Date:, Measurement Date:, etc.)
    2. ISO format dates in content (YYYY-MM-DD)
    3. US format dates (MM/DD/YYYY)
    4. Date in filename

    Args:
        content: File content string
        filename: Original filename

    Returns:
        ISO format date string (YYYY-MM-DD) or None if not found
    """
    import re
    from datetime import datetime

    # Patterns to search for dates
    date_patterns = [
        # BioTek-style headers
        (r"(?:Date|Measurement Date|Run Date|Created)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", "%m/%d/%Y"),
        (r"(?:Date|Measurement Date|Run Date|Created)[:\s]+(\d{4}[/-]\d{1,2}[/-]\d{1,2})", "%Y-%m-%d"),
        # ISO format anywhere in first 50 lines
        (r"(\d{4}-\d{2}-\d{2})", "%Y-%m-%d"),
        # US format MM/DD/YYYY
        (r"(\d{1,2}/\d{1,2}/\d{4})", "%m/%d/%Y"),
        # European format DD/MM/YYYY (less common for BioTek)
        (r"(\d{1,2}/\d{1,2}/\d{4})", "%d/%m/%Y"),
    ]

    # Search in first 50 lines of content
    first_lines = "\n".join(content.split("\n")[:50])

    for pattern, date_format in date_patterns:
        match = re.search(pattern, first_lines, re.IGNORECASE)
        if match:
            try:
                date_str = match.group(1)
                # Handle 2-digit years
                if len(date_str.split("/")[-1]) == 2 or len(date_str.split("-")[-1]) == 2:
                    date_format = date_format.replace("%Y", "%y")
                parsed_date = datetime.strptime(date_str, date_format)
                return parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                continue

    # Try to extract date from filename (uses shared patterns with identifier parser)
    for pattern in FILENAME_DATE_PATTERNS:
        # Wrap in capturing group for match.group(1)
        pattern = f"({pattern})"
        match = re.search(pattern, filename)
        if match:
            date_str = match.group(1).replace("-", "").replace("_", "")
            try:
                if len(date_str) == 8:
                    # Try YYYYMMDD first
                    try:
                        parsed_date = datetime.strptime(date_str, "%Y%m%d")
                        return parsed_date.strftime("%Y-%m-%d")
                    except ValueError:
                        # Try MMDDYYYY
                        parsed_date = datetime.strptime(date_str, "%m%d%Y")
                        return parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                continue

    return None


def parse_uploaded_file(
    contents: str,
    filename: str,
) -> Dict[str, Any]:
    """
    Parse uploaded file content.

    Args:
        contents: Base64 encoded file contents
        filename: Original filename

    Returns:
        Dict with parsed data or error information
    """
    if not contents or not filename:
        return {"error": "No file provided"}

    try:
        # Decode base64 content
        if "," not in contents:
            return {
                "is_valid": False,
                "error": "Invalid file format: expected base64-encoded data URL.",
                "filename": filename,
            }
        content_type, content_string = contents.split(",", 1)
        decoded = base64.b64decode(content_string)

        # Try to decode as text
        # Order matters: UTF-8 first, then check for UTF-16 BOM, then
        # fall back to latin-1.  bytes.decode('utf-16') succeeds on
        # almost any even-length byte sequence (no BOM required), so it
        # must NOT be tried before latin-1 — otherwise cp1252/latin-1
        # files (common BioTek output) get silently garbled.
        try:
            file_content = decoded.decode("utf-8")
        except UnicodeDecodeError:
            if decoded[:2] in (b'\xff\xfe', b'\xfe\xff'):
                try:
                    file_content = decoded.decode("utf-16")
                except UnicodeDecodeError:
                    file_content = decoded.decode("latin-1")
            else:
                file_content = decoded.decode("latin-1")

        # Determine format from filename
        file_format = "txt"
        if filename.endswith(".csv"):
            file_format = "csv"
        elif filename.endswith((".xlsx", ".xls")):
            file_format = "xlsx"

        # Parse with BioTek parser
        parsed = parse_biotek_content(file_content, file_format)

        # Try to extract date from file content or filename
        parsed_date = extract_date_from_content(file_content, filename)

        return {
            "is_valid": True,
            "parsed_data": parsed,
            "content": file_content,
            "filename": filename,
            "parsed_date": parsed_date,  # May be None if no date found
            "metadata": {
                "plate_format": parsed.plate_format,
                "temperature_setpoint": parsed.temperature_setpoint,
                "num_timepoints": parsed.num_timepoints,
                "num_wells_with_data": parsed.num_wells,
            },
        }

    except BioTekParseError as e:
        logger.warning("BioTek parse error", error=str(e), filename=filename)
        return {
            "is_valid": False,
            "error": str(e),
            "filename": filename,
        }
    except Exception as e:
        logger.exception("Failed to parse uploaded file", filename=filename)
        return {
            "is_valid": False,
            "error": "Failed to parse file. Please check the file format and try again.",
            "filename": filename,
        }


def parse_biotek_content_safe(content: str, format_hint: str = "txt") -> Dict[str, Any]:
    """
    Safely parse BioTek content with error handling.

    Args:
        content: File content string
        format_hint: Format hint for parser

    Returns:
        Dict with parsed data or error information
    """
    try:
        parsed = parse_biotek_content(content, format_hint)
        return {
            "is_valid": True,
            "well_data": dict(parsed.well_data),
            "timepoints": list(parsed.timepoints),
            "plate_format": parsed.plate_format,
            "temperature_setpoint": parsed.temperature_setpoint,
            "temperatures": list(parsed.temperatures) if parsed.temperatures else [],
            "parsed_data": parsed,
        }
    except BioTekParseError as e:
        logger.warning("BioTek parse error in safe parser", error=str(e))
        return {"is_valid": False, "error": str(e)}
    except Exception as e:
        logger.exception("Unexpected parse error in safe parser")
        return {"is_valid": False, "error": "An unexpected error occurred while parsing the file."}


def validate_upload_file(
    project_id: Optional[int],
    layout_id: Optional[int],
    file_content: Optional[str],
    filename: str,
) -> Dict[str, Any]:
    """
    Validate upload file against project and layout.

    Args:
        project_id: Target project ID
        layout_id: Target layout ID
        file_content: File content string
        filename: Original filename

    Returns:
        Validation result dict
    """
    errors = []
    warnings = []

    # Check required fields
    if not project_id:
        errors.append("Project is required")

    if not layout_id:
        errors.append("Layout selection is required")

    if not file_content:
        errors.append("File is required")

    if errors:
        return {
            "is_valid": False,
            "errors": errors,
            "warnings": [],
        }

    # Use UploadService for validation
    try:
        validation = UploadService.validate_upload(
            project_id=project_id,
            layout_id=layout_id,
            file_content=file_content,
            file_format=_get_format_from_filename(filename),
        )

        # Add temperature QC warnings
        if validation.parsed_data:
            temp_warnings = _check_temperature_qc_for_validation(
                validation.parsed_data.temperature_setpoint,
                list(validation.parsed_data.temperatures) if validation.parsed_data.temperatures else [],
            )
            for tw in temp_warnings:
                validation.warnings.append(tw)

        return {
            "is_valid": validation.is_valid,
            "errors": validation.errors,
            "warnings": [
                {
                    "code": w.code,
                    "message": w.message,
                    "suppressible": w.suppressible,
                    "details": w.details,
                }
                for w in validation.warnings
            ],
            "metadata": {
                "plate_format": validation.plate_format,
                "temperature_setpoint": validation.temperature_setpoint,
                "num_timepoints": validation.num_timepoints,
                "num_wells_with_data": validation.num_wells_with_data,
            },
            "matching": {
                "matched_wells": validation.matched_wells,
                "unmatched_wells": validation.unmatched_wells,
                "negative_control_count": validation.negative_control_count,
                "blank_count": validation.blank_count,
            },
        }

    except Exception as e:
        logger.exception("Upload validation error")
        return {
            "is_valid": False,
            "errors": ["An unexpected error occurred during validation. Please try again."],
            "warnings": [],
        }


def _get_format_from_filename(filename: str) -> str:
    """Get file format hint from filename."""
    if not filename:
        return "txt"
    filename = filename.lower()
    if filename.endswith(".csv"):
        return "csv"
    elif filename.endswith((".xlsx", ".xls")):
        return "xlsx"
    elif filename.endswith(".tsv"):
        return "tsv"
    return "txt"


def _check_temperature_qc_for_validation(
    setpoint: Optional[float],
    temperatures: List[float],
) -> List[Any]:
    """Check temperature QC and return warning objects if needed."""
    from app.services.upload_service import UploadWarning

    result = check_temperature_qc(setpoint, temperatures, TEMPERATURE_QC_THRESHOLD)

    if not result["passed"]:
        return [
            UploadWarning(
                code="TEMP_DEVIATION",
                message=f"Temperature deviation detected: max deviation {result['max_deviation']:.1f}°C (threshold: ±{TEMPERATURE_QC_THRESHOLD}°C)",
                details={
                    "setpoint": setpoint,
                    "min_temp": result.get("min_temp"),
                    "max_temp": result.get("max_temp"),
                    "max_deviation": result["max_deviation"],
                },
                suppressible=False,  # Temperature warnings are not suppressible
            )
        ]
    return []


def check_temperature_qc(
    setpoint: Optional[float],
    temperatures: List[float],
    threshold: float = TEMPERATURE_QC_THRESHOLD,
) -> Dict[str, Any]:
    """
    Check temperature QC against setpoint.

    Args:
        setpoint: Target temperature setpoint
        temperatures: List of temperature readings
        threshold: Maximum allowed deviation

    Returns:
        Dict with QC results
    """
    if setpoint is None:
        return {
            "passed": True,
            "max_deviation": 0.0,
            "warnings": [],
            "min_temp": None,
            "max_temp": None,
        }

    # Filter None values
    valid_temps = [t for t in temperatures if t is not None]

    if not valid_temps:
        return {
            "passed": True,
            "max_deviation": 0.0,
            "warnings": [],
            "min_temp": None,
            "max_temp": None,
        }

    min_temp = min(valid_temps)
    max_temp = max(valid_temps)

    max_deviation = max(abs(max_temp - setpoint), abs(min_temp - setpoint))

    warnings = []
    if max_deviation > threshold:
        warnings.append({
            "code": "TEMP_DEVIATION",
            "message": f"Temperature deviation of {max_deviation:.1f}°C exceeds ±{threshold}°C threshold",
        })

    return {
        "passed": max_deviation <= threshold,
        "max_deviation": max_deviation,
        "min_temp": min_temp,
        "max_temp": max_temp,
        "warnings": warnings,
    }


def detect_temperature_deviation(
    setpoint: Optional[float],
    temperatures: List[float],
    threshold: float = TEMPERATURE_QC_THRESHOLD,
) -> Dict[str, Any]:
    """
    Detect temperature deviations from setpoint.

    Args:
        setpoint: Target temperature
        temperatures: List of temperature readings
        threshold: Maximum allowed deviation

    Returns:
        Dict with deviation information
    """
    if setpoint is None or not temperatures:
        return {
            "has_deviation": False,
            "max_deviation": 0.0,
            "min_temp": None,
            "max_temp": None,
        }

    valid_temps = [t for t in temperatures if t is not None]

    if not valid_temps:
        return {
            "has_deviation": False,
            "max_deviation": 0.0,
            "min_temp": None,
            "max_temp": None,
        }

    min_temp = min(valid_temps)
    max_temp = max(valid_temps)
    max_deviation = max(abs(max_temp - setpoint), abs(min_temp - setpoint))

    return {
        "has_deviation": max_deviation > threshold,
        "max_deviation": max_deviation,
        "min_temp": min_temp,
        "max_temp": max_temp,
    }


def generate_temperature_warning_message(
    setpoint: float,
    actual_temp: float,
    threshold: float = TEMPERATURE_QC_THRESHOLD,
) -> str:
    """
    Generate a warning message for temperature deviation.

    Args:
        setpoint: Target temperature
        actual_temp: Actual temperature reading
        threshold: Deviation threshold

    Returns:
        Warning message string
    """
    deviation = actual_temp - setpoint
    direction = "above" if deviation > 0 else "below"

    return (
        f"Temperature of {actual_temp}°C is {abs(deviation):.1f}°C {direction} "
        f"the setpoint of {setpoint}°C (threshold: ±{threshold}°C)"
    )


def create_temperature_qc_summary(
    setpoint: Optional[float],
    temperatures: List[float],
    threshold: float = TEMPERATURE_QC_THRESHOLD,
) -> Dict[str, Any]:
    """
    Create a summary of temperature QC results.

    Args:
        setpoint: Target temperature
        temperatures: List of temperature readings
        threshold: Deviation threshold

    Returns:
        Summary dict
    """
    qc_result = check_temperature_qc(setpoint, temperatures, threshold)

    return {
        "setpoint": setpoint,
        "min_temp": qc_result.get("min_temp"),
        "max_temp": qc_result.get("max_temp"),
        "max_deviation": qc_result.get("max_deviation", 0.0),
        "threshold": threshold,
        "passed": qc_result["passed"],
        "status": "PASS" if qc_result["passed"] else "FAIL",
    }


def get_affected_temperature_timepoints(
    temperatures: List[float],
    setpoint: float,
    threshold: float = TEMPERATURE_QC_THRESHOLD,
) -> List[int]:
    """
    Get indices of timepoints with temperature deviation.

    Args:
        temperatures: List of temperature readings
        setpoint: Target temperature
        threshold: Deviation threshold

    Returns:
        List of affected timepoint indices
    """
    affected = []
    for i, temp in enumerate(temperatures):
        if temp is not None and abs(temp - setpoint) > threshold:
            affected.append(i)
    return affected


def add_temperature_qc_warnings(
    validation_result: Dict[str, Any],
    temperatures: List[float],
) -> Dict[str, Any]:
    """
    Add temperature QC warnings to validation result.

    Args:
        validation_result: Existing validation result
        temperatures: Temperature readings

    Returns:
        Updated validation result
    """
    result = dict(validation_result)
    if "warnings" not in result:
        result["warnings"] = []

    setpoint = result.get("metadata", {}).get("temperature_setpoint")
    if setpoint is not None:
        qc = check_temperature_qc(setpoint, temperatures, TEMPERATURE_QC_THRESHOLD)
        if not qc["passed"]:
            result["warnings"].append({
                "code": "TEMP_DEVIATION",
                "message": f"Temperature deviation: {qc['max_deviation']:.1f}°C (max allowed: ±{TEMPERATURE_QC_THRESHOLD}°C)",
                "suppressible": False,
            })

    return result


def prepare_upload_preview(
    parsed_data: Dict[str, Any],
    max_sample_wells: int = 5,
) -> Dict[str, Any]:
    """
    Prepare preview data for display.

    Args:
        parsed_data: Parsed file data
        max_sample_wells: Maximum wells to show in preview

    Returns:
        Preview data dict
    """
    well_data = parsed_data.get("well_data", {})
    timepoints = parsed_data.get("timepoints", [])

    sample_wells = list(well_data.keys())[:max_sample_wells]

    return {
        "num_wells": len(well_data),
        "num_timepoints": len(timepoints),
        "sample_wells": sample_wells,
        "sample_data": {
            well: well_data[well][:10] for well in sample_wells
        },
        "timepoints_preview": timepoints[:10] if timepoints else [],
    }


def create_preview_panel(
    wells_to_plot: List[str],
    well_data: Dict[str, List[float]],
    timepoints: List[float],
    assignments: List[Any],
    max_wells: int = 21,
    dark_mode: bool = False,
) -> Any:
    """
    Create the preview panel with raw curve plots.

    Args:
        wells_to_plot: List of well positions to include
        well_data: Dict mapping well position to fluorescence values
        timepoints: List of timepoints
        assignments: List of WellAssignment objects
        max_wells: Maximum number of wells to show (default 21)

    Returns:
        Dash component with preview plot
    """
    import dash_mantine_components as dmc
    from dash import dcc, html
    from dash_iconify import DashIconify
    import plotly.graph_objects as go

    # Create a mapping of position to assignment for well type info
    position_to_assignment = {a.well_position: a for a in assignments}

    # Sort wells by position (A1, A2, ... B1, B2, etc.)
    def well_sort_key(pos: str) -> Tuple[str, int]:
        try:
            row = pos[0]
            col = int(pos[1:])
            return (row, col)
        except (ValueError, IndexError):
            return (pos, 0)

    sorted_wells = sorted(wells_to_plot, key=well_sort_key)[:max_wells]

    # Color palette for different well types
    from app.models.plate_layout import WellType
    well_type_colors = {
        WellType.SAMPLE: "rgb(31, 119, 180)",       # Blue
        WellType.BLANK: "rgb(127, 127, 127)",       # Gray
        WellType.NEGATIVE_CONTROL_NO_TEMPLATE: "rgb(255, 127, 14)",  # Orange
        WellType.NEGATIVE_CONTROL_NO_DYE: "rgb(214, 39, 40)",        # Red
    }

    # Create the plot
    fig = go.Figure()

    for well_pos in sorted_wells:
        values = well_data.get(well_pos, [])
        if not values:
            continue

        assignment = position_to_assignment.get(well_pos)
        well_type = assignment.well_type if assignment else WellType.SAMPLE
        color = well_type_colors.get(well_type, "rgb(31, 119, 180)")

        # Get construct identifier if available
        construct_name = ""
        if assignment and assignment.construct:
            construct_name = f" ({assignment.construct.identifier})"

        fig.add_trace(go.Scatter(
            x=timepoints[:len(values)],
            y=values,
            mode="lines",
            name=f"{well_pos}{construct_name}",
            line=dict(width=1.5),
            hovertemplate=f"<b>{well_pos}</b><br>Time: %{{x:.1f}} min<br>RFU: %{{y:.0f}}<extra></extra>",
        ))

    fig.update_layout(
        title=dict(
            text=f"Raw Data Preview ({len(sorted_wells)} wells)",
            x=0.5,
            font=dict(size=14),
        ),
        xaxis_title="Time (min)",
        yaxis_title="Fluorescence (RFU)",
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
            font=dict(size=9),
        ),
        margin=dict(l=60, r=120, t=40, b=40),
        hovermode="x unified",
        height=350,
    )
    apply_plotly_theme(fig, dark_mode=dark_mode)

    # Build the preview panel
    truncated_message = None
    if len(wells_to_plot) > max_wells:
        truncated_message = dmc.Text(
            f"Showing {max_wells} of {len(wells_to_plot)} wells with data",
            size="xs",
            c="dimmed",
            style={"textAlign": "center", "marginTop": "0.5rem"},
        )

    return dmc.Paper(
        children=[
            dmc.Title("Preview", order=5, mb="sm"),
            dmc.Group(
                children=[
                    DashIconify(icon="mdi:chart-line", width=16, color="#228be6"),
                    dmc.Text(
                        f"{len(wells_to_plot)} wells matched from layout",
                        size="sm",
                        c="dimmed",
                    ),
                ],
                gap="xs",
                mb="sm",
            ),
            dcc.Graph(
                figure=fig,
                config={
                    "displayModeBar": True,
                    "displaylogo": False,
                    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                },
                style={"height": "350px"},
            ),
            truncated_message,
        ],
        p="md",
        withBorder=True,
        radius="md",
    )


def handle_file_upload(
    contents: Optional[str],
    filename: Optional[str],
    project_store: Optional[Dict],
) -> Optional[Dict[str, Any]]:
    """
    Handle file upload event.

    Args:
        contents: Base64 encoded file contents
        filename: Original filename
        project_store: Project store data

    Returns:
        Parsed file data or None
    """
    if not contents or not filename:
        return None

    return parse_uploaded_file(contents, filename)


def handle_layout_selection(
    layout_id: Optional[int],
    file_store: Optional[Dict],
    project_id: Optional[int],
) -> Optional[Dict[str, Any]]:
    """
    Handle layout selection change.

    Args:
        layout_id: Selected layout ID
        file_store: File store data
        project_id: Project ID

    Returns:
        Validation result or None
    """
    if not file_store or not layout_id or not project_id:
        return None

    file_content = file_store.get("content")
    filename = file_store.get("filename")

    if not file_content:
        return None

    return validate_upload_file(project_id, layout_id, file_content, filename)


def process_upload(
    project_id: int,
    layout_id: int,
    file_content: str,
    filename: str,
    session_option: str,
    session_date: Optional[str],
    username: str,
    session_id: Optional[int] = None,
    batch_id: Optional[str] = None,
    plate_number: int = 1,
    suppressed_warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Process the upload and create database records.

    Args:
        project_id: Target project ID
        layout_id: Target layout ID
        file_content: File content string
        filename: Original filename
        session_option: "new" or existing session ID
        session_date: Date for new session
        username: Username performing upload
        session_id: Existing session ID if not creating new
        batch_id: Batch identifier for new session
        plate_number: Plate number in session
        suppressed_warnings: List of warning codes to suppress

    Returns:
        Upload result dict
    """
    try:
        # Determine session handling
        use_session_id = None
        use_session_date = None

        if session_option != "new":
            # session_option can be an existing session ID as a string
            if session_id:
                use_session_id = session_id
            elif session_option.isdigit():
                use_session_id = int(session_option)
            else:
                # Fallback: treat as new session if session_option is not a valid ID
                use_session_date = date.fromisoformat(session_date) if session_date else date.today()
        else:
            use_session_date = date.fromisoformat(session_date) if session_date else date.today()

        result = UploadService.process_upload(
            project_id=project_id,
            layout_id=layout_id,
            session_id=use_session_id,
            file_content=file_content,
            file_format=_get_format_from_filename(filename),
            original_filename=filename,
            plate_number=plate_number,
            username=username,
            session_date=use_session_date,
            session_batch_id=batch_id,
            suppressed_warnings=suppressed_warnings or [],
        )

        return {
            "success": True,
            "plate_id": result.plate_id,
            "session_id": result.session_id,
            "wells_created": result.wells_created,
            "data_points_created": result.data_points_created,
            "warnings": [
                {"code": w.code, "message": w.message}
                for w in result.warnings
            ],
        }

    except UploadValidationError as e:
        logger.warning("Upload validation error", error=str(e))
        return {
            "success": False,
            "error": str(e),
        }
    except UploadProcessingError as e:
        logger.warning("Upload processing error", error=str(e))
        return {
            "success": False,
            "error": str(e),
        }
    except Exception as e:
        logger.exception("Unexpected upload failure")
        return {
            "success": False,
            "error": "Upload failed due to an unexpected error. Please try again.",
        }


def validate_layout_match(
    layout_wells: List[str],
    file_wells: List[str],
) -> Dict[str, Any]:
    """
    Validate well matching between layout and file.

    Args:
        layout_wells: Well positions from layout
        file_wells: Well positions from file

    Returns:
        Matching result dict
    """
    layout_set = set(layout_wells)
    file_set = set(file_wells)

    matched = layout_set.intersection(file_set)
    unmatched_layout = layout_set - file_set
    unmatched_file = file_set - layout_set

    return {
        "matched_count": len(matched),
        "unmatched_layout_wells": len(unmatched_layout),
        "unmatched_file_wells": len(unmatched_file),
        "matched_positions": list(matched),
        "missing_from_file": list(unmatched_layout),
        "extra_in_file": list(unmatched_file),
    }


def get_suppressible_warnings(warnings: List[Dict]) -> List[Dict]:
    """
    Get only suppressible warnings from a list.

    Args:
        warnings: List of warning dicts

    Returns:
        List of suppressible warnings
    """
    return [w for w in warnings if w.get("suppressible", False)]


def filter_suppressed_warnings(
    warnings: List[Dict],
    suppressed_codes: List[str],
) -> List[Dict]:
    """
    Filter out suppressed warnings.

    Args:
        warnings: List of warning dicts
        suppressed_codes: List of warning codes to suppress

    Returns:
        Filtered warnings list
    """
    return [w for w in warnings if w.get("code") not in suppressed_codes]


def validate_upload_form(
    has_file: bool,
    has_layout: bool,
    has_session_option: bool,
    validation_passed: bool,
) -> Dict[str, Any]:
    """
    Validate the upload form completion.

    Args:
        has_file: Whether file is uploaded
        has_layout: Whether layout is selected
        has_session_option: Whether session option is selected
        validation_passed: Whether file validation passed

    Returns:
        Form validation result
    """
    missing = []

    if not has_file:
        missing.append("file")
    if not has_layout:
        missing.append("layout")
    if not has_session_option:
        missing.append("session")

    can_submit = len(missing) == 0 and validation_passed

    return {
        "can_submit": can_submit,
        "missing_fields": missing,
        "validation_passed": validation_passed,
    }


def get_available_layouts(project_id: int) -> List[Dict]:
    """
    Get available layouts for a project.

    Args:
        project_id: Project ID

    Returns:
        List of layout dicts
    """
    try:
        from app.models import PlateLayout

        layouts = PlateLayout.query.filter_by(
            project_id=project_id,
            is_draft=False,
        ).all()

        return [
            {
                "id": l.id,
                "name": l.name,
                "plate_format": l.plate_format,
            }
            for l in layouts
        ]
    except Exception:
        logger.exception("Failed to fetch layouts for project %s", project_id)
        return []


def get_available_sessions(project_id: int) -> List[Dict]:
    """
    Get available sessions for a project.

    Args:
        project_id: Project ID

    Returns:
        List of session dicts
    """
    try:
        from app.models import ExperimentalSession

        sessions = ExperimentalSession.query.filter_by(
            project_id=project_id,
        ).order_by(
            ExperimentalSession.date.desc()
        ).all()

        return [
            {
                "id": s.id,
                "date": s.date.isoformat() if s.date else None,
                "batch_id": s.batch_identifier,
            }
            for s in sessions
        ]
    except Exception:
        logger.exception("Failed to fetch sessions for project %s", project_id)
        return []
