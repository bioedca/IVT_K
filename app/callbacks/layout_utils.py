"""
Layout callback utility functions.

Extracted from layout_callbacks.py during Phase 4 refactoring.
Contains all module-level helper functions used by layout callbacks.
"""
from typing import Optional, List, Dict, Tuple

from app.components.plate_grid import (
    get_wells_in_range,
    get_wells_in_row,
    get_wells_in_column,
    validate_checkerboard_selection,
    ROWS_96,
    COLS_96,
    ROWS_384,
    COLS_384,
)
from app.logging_config import get_logger

logger = get_logger(__name__)


def handle_well_click(
    clicked_well: str,
    current_selection: List[str],
    shift_key: bool = False,
    ctrl_key: bool = False,
    last_clicked: Optional[str] = None,
    plate_format: int = 96,
) -> List[str]:
    """
    Handle a well click event and return updated selection.

    Args:
        clicked_well: The well position that was clicked
        current_selection: Current list of selected wells
        shift_key: Whether shift key was held
        ctrl_key: Whether ctrl/cmd key was held
        last_clicked: The last clicked well (for shift-click range)
        plate_format: 96 or 384

    Returns:
        Updated list of selected wells
    """
    if not clicked_well:
        return current_selection

    if shift_key and last_clicked:
        # Range selection
        range_wells = get_wells_in_range(last_clicked, clicked_well, plate_format)
        if ctrl_key:
            # Add range to existing selection
            return merge_selections(current_selection, range_wells)
        else:
            # Replace selection with range
            return range_wells

    elif ctrl_key:
        # Toggle well in selection
        if clicked_well in current_selection:
            return [w for w in current_selection if w != clicked_well]
        else:
            return current_selection + [clicked_well]

    else:
        # Single click replaces selection
        return [clicked_well]


def compute_selection_range(
    start: str,
    end: str,
    plate_format: int = 96,
) -> List[str]:
    """
    Compute all wells in a rectangular range.

    Args:
        start: Start well position
        end: End well position
        plate_format: 96 or 384

    Returns:
        List of well positions in the range
    """
    return get_wells_in_range(start, end, plate_format)


def merge_selections(
    selection1: List[str],
    selection2: List[str],
) -> List[str]:
    """
    Merge two selections, removing duplicates.

    Args:
        selection1: First selection list
        selection2: Second selection list

    Returns:
        Merged list without duplicates
    """
    seen = set()
    result = []
    for well in selection1 + selection2:
        if well not in seen:
            seen.add(well)
            result.append(well)
    return result


def handle_selection_helper(
    helper_type: str,
    helper_value: Optional[str],
    plate_format: int = 96,
) -> List[str]:
    """
    Handle selection helper button click.

    Args:
        helper_type: Type of helper ("row", "column", "all")
        helper_value: Value for the helper (row letter or column number)
        plate_format: 96 or 384

    Returns:
        List of selected wells
    """
    rows = ROWS_384 if plate_format == 384 else ROWS_96
    cols = COLS_384 if plate_format == 384 else COLS_96

    if helper_type == "row" and helper_value:
        return get_wells_in_row(helper_value, plate_format)

    elif helper_type == "column" and helper_value:
        try:
            col_num = int(helper_value)
            return get_wells_in_column(col_num, plate_format)
        except ValueError:
            return []

    elif helper_type == "all":
        wells = []
        for row in rows:
            for col in cols:
                wells.append(f"{row}{col}")
        return wells

    return []


def handle_assignment(
    selected_wells: List[str],
    construct_id: Optional[int],
    well_type: str,
    ligand_concentration: Optional[float] = None,
    replicate_group: Optional[str] = None,
) -> List[Dict]:
    """
    Create assignment data for selected wells.

    Args:
        selected_wells: List of wells to assign
        construct_id: Construct ID (None for controls/blanks)
        well_type: Well type string
        ligand_concentration: Optional ligand concentration
        replicate_group: Optional replicate group name

    Returns:
        List of assignment dicts
    """
    assignments = []
    for well in selected_wells:
        assignment = {
            "well_position": well,
            "construct_id": construct_id,
            "well_type": well_type,
            "ligand_concentration": ligand_concentration,
            "replicate_group": replicate_group,
        }
        assignments.append(assignment)
    return assignments


def handle_clear_selection() -> List[str]:
    """
    Clear the current selection.

    Returns:
        Empty list
    """
    return []


def validate_assignment(
    construct_id: Optional[int],
    well_type: str,
    wells: List[str],
    plate_format: int = 96,
    enforce_checkerboard: bool = False,
) -> Tuple[bool, List[str]]:
    """
    Validate an assignment before applying.

    Args:
        construct_id: Construct ID
        well_type: Well type string
        wells: List of wells to assign
        plate_format: 96 or 384
        enforce_checkerboard: Whether to enforce checkerboard pattern

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    # Sample wells require construct
    if well_type == "sample" and construct_id is None:
        errors.append("Sample wells require a construct assignment")

    # Check checkerboard pattern for 384-well
    if enforce_checkerboard and plate_format == 384:
        is_valid, invalid_wells = validate_checkerboard_selection(wells, plate_format)
        if not is_valid:
            errors.append(
                f"Checkerboard pattern violation: {', '.join(invalid_wells)} are not valid positions"
            )

    return len(errors) == 0, errors


def get_layout_validation_status(
    summary: Dict,
) -> Tuple[bool, List[str]]:
    """
    Check if a layout meets minimum requirements.

    Args:
        summary: Layout summary dict

    Returns:
        Tuple of (is_valid, list of issues)
    """
    issues = []
    by_type = summary.get("by_type", {})
    by_role = summary.get("by_role", {})  # Analytical roles from construct flags

    # Check for minimum negative controls (2) - MUST be done first
    ntc_count = by_type.get("negative_control_no_template", 0)
    if ntc_count < 2:
        issues.append(f"Step 1: Add -Template wells (need >=2, found {ntc_count})")

    # Check for Unregulated anchor - second priority
    unreg_count = by_role.get("unregulated", 0)
    if unreg_count < 1:
        if ntc_count >= 2:
            issues.append("Step 2: Add Aptamer anchor (iSpinach, Corn, Mango, etc.) wells")
        else:
            issues.append("Step 2: Add Aptamer anchor (iSpinach, Corn, Mango, etc.) wells")

    # Check for WT/Mutant requirements
    wt_count = by_role.get("wildtype", 0)
    mutant_count = by_role.get("mutant", 0)

    # Guide for adding WT
    if wt_count == 0 and ntc_count >= 2 and unreg_count >= 1:
        # Don't report as error, just guidance - WT is optional if no mutants
        pass

    # Check Family Integrity (Mutants pair with WT)
    families_mutant = set(summary.get("families_mutant", []))
    families_wt = set(summary.get("families_wt", []))

    missing_wt = families_mutant - families_wt
    if missing_wt:
        issues.append(f"Missing Wild-type for {len(missing_wt)} families with mutants")

    # Check for checkerboard violations (blocks publishing for 384-well plates)
    checkerboard_violations = summary.get("checkerboard_violations", [])
    if checkerboard_violations:
        issues.append(f"Checkerboard pattern violation: {len(checkerboard_violations)} well(s) in blocked positions")

    return len(issues) == 0, issues



def handle_layout_save(
    layout_id: Optional[int],
    project_id: int,
    layout_name: str,
    assignments: Dict[str, Dict],
    username: str,
) -> Tuple[bool, str, Optional[int]]:
    """
    Save layout to database.

    Args:
        layout_id: Existing layout ID (None for new)
        project_id: Project ID
        layout_name: Layout name
        assignments: Well assignments dict
        username: User performing the action

    Returns:
        Tuple of (success, message, layout_id)
    """
    # Import here to avoid circular imports
    from app.services.plate_layout_service import PlateLayoutService, PlateLayoutValidationError
    from app.models.plate_layout import WellType

    try:
        if layout_id is None:
            # Create new layout
            from app.models import Project
            project = Project.query.get(project_id)
            if not project:
                return False, "Project not found", None

            layout = PlateLayoutService.create_layout(
                project_id=project_id,
                name=layout_name,
                username=username,
                plate_format=project.plate_format.value,
            )
            layout_id = layout.id
        else:
            # Update existing layout name if changed
            layout = PlateLayoutService.get_layout(layout_id)
            if layout and layout.name != layout_name:
                layout.name = layout_name

        # Apply assignments
        for well_position, assignment in assignments.items():
            well_type_str = assignment.get("well_type", "sample")
            try:
                well_type = WellType(well_type_str)
            except ValueError:
                return False, f"Invalid well type: {well_type_str}", layout_id

            PlateLayoutService.assign_well(
                layout_id=layout_id,
                well_position=well_position,
                username=username,
                construct_id=assignment.get("construct_id"),
                well_type=well_type,
                paired_with=assignment.get("paired_with"),
                replicate_group=assignment.get("replicate_group"),
                ligand_concentration=assignment.get("ligand_concentration"),
                ligand_condition=assignment.get("ligand_condition"),
            )

        return True, "Layout saved successfully", layout_id

    except PlateLayoutValidationError as e:
        logger.warning("Layout save validation error", error=str(e))
        return False, str(e), layout_id
    except Exception as e:
        logger.exception("Error saving layout")
        return False, "An unexpected error occurred while saving the layout.", layout_id


def handle_layout_publish(
    layout_id: int,
    username: str,
) -> Tuple[bool, str]:
    """
    Publish a layout (mark as non-draft).

    Args:
        layout_id: Layout ID to publish
        username: User performing the action

    Returns:
        Tuple of (success, message)
    """
    # Import here to avoid circular imports
    from app.services.plate_layout_service import PlateLayoutService, PlateLayoutValidationError

    try:
        PlateLayoutService.publish_layout(layout_id, username)
        return True, "Layout published successfully"

    except PlateLayoutValidationError as e:
        logger.warning("Layout publish validation error", error=str(e))
        return False, str(e)
    except Exception as e:
        logger.exception("Error publishing layout")
        return False, "An unexpected error occurred while publishing the layout."
