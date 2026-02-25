"""
Plate grid interactive component for well selection and assignment.

Phase 2: Plate Layout Editor

Provides:
- Interactive click-to-assign plate grid editor
- Well selection with click, shift-click, ctrl-click
- Row/column/all selection helpers
- Visual well states and assignment display
- Checkerboard pattern validation for 384-well plates
"""
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum

from app.models.enums import LigandCondition

import dash_mantine_components as dmc
from dash import html
from dash_iconify import DashIconify


class WellState(str, Enum):
    """Well state values for visual display."""

    EMPTY = "empty"
    ASSIGNED = "assigned"
    SELECTED = "selected"
    BLOCKED = "blocked"
    CONTROL = "control"


# Plate format constants
ROWS_96 = list("ABCDEFGH")
COLS_96 = list(range(1, 13))
ROWS_384 = list("ABCDEFGHIJKLMNOP")
COLS_384 = list(range(1, 25))

# Color mapping for well states (light mode)
STATE_COLORS = {
    WellState.EMPTY: "#f8f9fa",
    WellState.ASSIGNED: "#228be6",
    WellState.SELECTED: "#40c057",
    WellState.BLOCKED: "#e9ecef",
    WellState.CONTROL: "#be4bdb",
    "empty": "#f8f9fa",
    "assigned": "#228be6",
    "selected": "#40c057",
    "blocked": "#e9ecef",
    "control": "#be4bdb",
    "sample": "#228be6",
    "blank": "#fab005",
    "negative_control_no_template": "#be4bdb",
    "negative_control_no_dye": "#f06595",
}

# Border colors for states (light mode)
STATE_BORDER_COLORS = {
    WellState.EMPTY: "#dee2e6",
    WellState.ASSIGNED: "#1971c2",
    WellState.SELECTED: "#2f9e44",
    WellState.BLOCKED: "#adb5bd",
    WellState.CONTROL: "#9c36b5",
}

# Color mapping for well states (dark mode)
STATE_COLORS_DARK = {
    WellState.EMPTY: "#2a3a3a",
    WellState.ASSIGNED: "#1a6fb5",
    WellState.SELECTED: "#2d8a3e",
    WellState.BLOCKED: "#1e2828",
    WellState.CONTROL: "#9c36b5",
    "empty": "#2a3a3a",
    "assigned": "#1a6fb5",
    "selected": "#2d8a3e",
    "blocked": "#1e2828",
    "control": "#9c36b5",
    "sample": "#1a6fb5",
    "blank": "#c99304",
    "negative_control_no_template": "#9c36b5",
    "negative_control_no_dye": "#c4507a",
}

# Border colors for states (dark mode)
STATE_BORDER_COLORS_DARK = {
    WellState.EMPTY: "rgba(255,255,255,0.12)",
    WellState.ASSIGNED: "#228be6",
    WellState.SELECTED: "#40c057",
    WellState.BLOCKED: "rgba(255,255,255,0.06)",
    WellState.CONTROL: "#be4bdb",
}

# Per-construct color palettes for distinct sample well coloring (light mode)
CONSTRUCT_PALETTE = [
    "#228be6", "#40c057", "#f76707", "#7950f2", "#e64980",
    "#15aabf", "#82c91e", "#fd7e14", "#4c6ef5", "#12b886",
    "#e8590c", "#845ef7",
]

# Per-construct color palettes for distinct sample well coloring (dark mode)
CONSTRUCT_PALETTE_DARK = [
    "#1a6fb5", "#2d8a3e", "#c75500", "#6741d9", "#c2255c",
    "#1098ad", "#66a80f", "#e8590c", "#4263eb", "#0ca678",
    "#d9480f", "#7048e8",
]


def _darken_hex(hex_color: str, factor: float = 0.7) -> str:
    """Darken a hex color by *factor* (0 = black, 1 = unchanged)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"#{int(r * factor):02x}{int(g * factor):02x}{int(b * factor):02x}"


def get_well_state_color(state: WellState | str, dark_mode: bool = False) -> str:
    """
    Get the background color for a given well state.

    Args:
        state: Well state value
        dark_mode: Whether to use dark mode colors

    Returns:
        Hex color string
    """
    if dark_mode:
        return STATE_COLORS_DARK.get(state, "#2a3a3a")
    return STATE_COLORS.get(state, "#f8f9fa")


def get_well_state_style(
    state: WellState | str,
    is_selected: bool = False,
    has_ligand: bool = False,
    dark_mode: bool = False,
) -> Dict[str, Any]:
    """
    Get the CSS style for a well based on its state.

    Args:
        state: Well state value
        is_selected: Whether well is currently selected
        has_ligand: Whether well has ligand assigned
        dark_mode: Whether to use dark mode colors

    Returns:
        Dict of CSS properties
    """
    border_colors = STATE_BORDER_COLORS_DARK if dark_mode else STATE_BORDER_COLORS
    default_border = "rgba(255,255,255,0.12)" if dark_mode else "#dee2e6"

    base_style = {
        "backgroundColor": get_well_state_color(state, dark_mode),
        "border": f"2px solid {border_colors.get(state, default_border)}",
        "borderRadius": "4px",
        "cursor": "pointer",
        "transition": "all 0.15s ease",
        "position": "relative",
    }

    if is_selected:
        if dark_mode:
            base_style.update({
                "boxShadow": "0 0 0 3px rgba(12, 124, 111, 0.3)",
                "border": "2px solid #0C7C6F",
            })
        else:
            base_style.update({
                "boxShadow": "0 0 0 3px rgba(12, 124, 111, 0.4)",
                "border": "2px solid #0C7C6F",
            })

    if state == WellState.BLOCKED or state == "blocked":
        if dark_mode:
            base_style.update({
                "cursor": "not-allowed",
                "opacity": 0.4,
                "backgroundColor": "#1e2828",
            })
        else:
            base_style.update({
                "cursor": "not-allowed",
                "opacity": 0.5,
                "backgroundColor": "#f1f3f5",
            })

    if has_ligand:
        base_style.update({
            "borderStyle": "dashed",
            "borderWidth": "3px",
        })

    return base_style


def well_position_to_index(position: str, plate_format: int = 96) -> Tuple[int, int]:
    """
    Convert well position string to row, col indices.

    Args:
        position: Well position (e.g., "A1", "H12")
        plate_format: 96 or 384

    Returns:
        (row_idx, col_idx) tuple
    """
    position = position.upper()
    row_letter = position[0]
    col_num = int(position[1:])

    rows = ROWS_384 if plate_format == 384 else ROWS_96
    row_idx = rows.index(row_letter)
    col_idx = col_num - 1

    return row_idx, col_idx


def index_to_well_position(row_idx: int, col_idx: int, plate_format: int = 96) -> str:
    """
    Convert row, col indices to well position string.

    Args:
        row_idx: Row index (0-based)
        col_idx: Column index (0-based)
        plate_format: 96 or 384

    Returns:
        Well position string (e.g., "A1")
    """
    rows = ROWS_384 if plate_format == 384 else ROWS_96
    row_letter = rows[row_idx]
    col_num = col_idx + 1

    return f"{row_letter}{col_num}"


def get_wells_in_range(
    start: str,
    end: str,
    plate_format: int = 96,
) -> List[str]:
    """
    Get all well positions in a rectangular range.

    Args:
        start: Start well position
        end: End well position
        plate_format: 96 or 384

    Returns:
        List of well positions in the range
    """
    start_row, start_col = well_position_to_index(start, plate_format)
    end_row, end_col = well_position_to_index(end, plate_format)

    # Normalize range (ensure start <= end)
    min_row, max_row = min(start_row, end_row), max(start_row, end_row)
    min_col, max_col = min(start_col, end_col), max(start_col, end_col)

    wells = []
    for row in range(min_row, max_row + 1):
        for col in range(min_col, max_col + 1):
            wells.append(index_to_well_position(row, col, plate_format))

    return wells


def get_wells_in_row(row_letter: str, plate_format: int = 96) -> List[str]:
    """
    Get all well positions in a specific row.

    Args:
        row_letter: Row letter (e.g., "A")
        plate_format: 96 or 384

    Returns:
        List of well positions in the row
    """
    row_letter = row_letter.upper()
    cols = COLS_384 if plate_format == 384 else COLS_96

    return [f"{row_letter}{col}" for col in cols]


def get_wells_in_column(col_num: int, plate_format: int = 96) -> List[str]:
    """
    Get all well positions in a specific column.

    Args:
        col_num: Column number (1-based)
        plate_format: 96 or 384

    Returns:
        List of well positions in the column
    """
    rows = ROWS_384 if plate_format == 384 else ROWS_96

    return [f"{row}{col_num}" for row in rows]


def is_checkerboard_valid_well(position: str, plate_format: int = 384, pattern: str = 'A') -> bool:
    """
    Check if a well position is valid in checkerboard pattern.

    Pattern A: Wells where (row_idx + col_idx) is even are valid (A1 is valid)
    Pattern B: Wells where (row_idx + col_idx) is odd are valid (B1 is valid)
    96-well plates don't enforce checkerboard.

    Args:
        position: Well position
        plate_format: 96 or 384
        pattern: 'A' or 'B'

    Returns:
        True if well is valid for checkerboard pattern
    """
    if plate_format != 384:
        return True

    row_idx, col_idx = well_position_to_index(position, plate_format)
    if pattern == 'B':
        return (row_idx + col_idx) % 2 == 1
    return (row_idx + col_idx) % 2 == 0


def validate_checkerboard_selection(
    wells: List[str],
    plate_format: int = 384,
    pattern: str = 'A',
) -> Tuple[bool, List[str]]:
    """
    Validate a selection against checkerboard pattern.

    Args:
        wells: List of well positions
        plate_format: 96 or 384
        pattern: 'A' or 'B'

    Returns:
        Tuple of (is_valid, list of invalid wells)
    """
    if plate_format != 384 or not wells:
        return True, []

    invalid_wells = [w for w in wells if not is_checkerboard_valid_well(w, plate_format, pattern)]

    return len(invalid_wells) == 0, invalid_wells


def get_checkerboard_blocked_wells(plate_format: int = 384, pattern: str = 'A') -> List[str]:
    """
    Get all blocked well positions in checkerboard pattern.

    Args:
        plate_format: 96 or 384
        pattern: 'A' or 'B'

    Returns:
        List of blocked well positions
    """
    if plate_format != 384:
        return []

    blocked = []
    target_mod = 1 if pattern == 'A' else 0  # Blocked wells have opposite parity
    for row_idx, row in enumerate(ROWS_384):
        for col_idx, col in enumerate(COLS_384):
            if (row_idx + col_idx) % 2 == target_mod:
                blocked.append(f"{row}{col}")

    return blocked


def is_edge_well(position: str, plate_format: int = 96) -> bool:
    """
    Check if a well position is on the edge of the plate.

    Edge wells are those in the first/last row or first/last column.

    Args:
        position: Well position (e.g., "A1", "H12")
        plate_format: 96 or 384

    Returns:
        True if well is on the edge
    """
    row_idx, col_idx = well_position_to_index(position, plate_format)

    if plate_format == 384:
        max_row = len(ROWS_384) - 1  # 15 (P)
        max_col = len(COLS_384) - 1  # 23 (column 24)
    else:
        max_row = len(ROWS_96) - 1   # 7 (H)
        max_col = len(COLS_96) - 1   # 11 (column 12)

    # Check if on first/last row or first/last column
    return row_idx == 0 or row_idx == max_row or col_idx == 0 or col_idx == max_col


def get_edge_wells(plate_format: int = 96) -> List[str]:
    """
    Get all edge well positions for a plate format.

    Args:
        plate_format: 96 or 384

    Returns:
        List of edge well positions
    """
    if plate_format == 384:
        rows = ROWS_384
        cols = COLS_384
    else:
        rows = ROWS_96
        cols = COLS_96

    edge_wells = []
    for row_idx, row in enumerate(rows):
        for col_idx, col in enumerate(cols):
            pos = f"{row}{col}"
            if is_edge_well(pos, plate_format):
                edge_wells.append(pos)

    return edge_wells


def find_nearest_valid_well(
    position: str,
    plate_format: int,
    pattern: str = 'A',
    occupied: Optional[set] = None,
) -> Optional[str]:
    """
    Find the nearest valid checkerboard position that is not occupied.

    Args:
        position: Original well position
        plate_format: 96 or 384
        pattern: 'A' or 'B'
        occupied: Set of already occupied well positions

    Returns:
        Nearest valid unoccupied position, or None if none found
    """
    if plate_format != 384:
        return position  # No redistribution needed for 96-well
    
    occupied = occupied or set()
    row_idx, col_idx = well_position_to_index(position, plate_format)
    
    rows = ROWS_384
    cols = COLS_384
    max_row = len(rows)
    max_col = len(cols)
    
    # Check positions in expanding rings around original
    for distance in range(1, max(max_row, max_col) + 1):
        candidates = []
        for dr in range(-distance, distance + 1):
            for dc in range(-distance, distance + 1):
                if abs(dr) != distance and abs(dc) != distance:
                    continue  # Only check ring, not interior
                new_row = row_idx + dr
                new_col = col_idx + dc
                if 0 <= new_row < max_row and 0 <= new_col < max_col:
                    pos = f"{rows[new_row]}{cols[new_col]}"
                    if is_checkerboard_valid_well(pos, plate_format, pattern) and pos not in occupied:
                        # Calculate actual distance for sorting
                        dist = abs(dr) + abs(dc)
                        candidates.append((dist, pos))
        
        if candidates:
            # Return closest candidate
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]
    
    return None


def get_checkerboard_valid_wells(plate_format: int = 384) -> List[str]:
    """
    Get all valid well positions in checkerboard pattern.

    Args:
        plate_format: 96 or 384

    Returns:
        List of valid well positions
    """
    if plate_format != 384:
        # All wells valid for 96-well
        wells = []
        for row in ROWS_96:
            for col in COLS_96:
                wells.append(f"{row}{col}")
        return wells

    valid = []
    for row_idx, row in enumerate(ROWS_384):
        for col_idx, col in enumerate(COLS_384):
            if (row_idx + col_idx) % 2 == 0:
                valid.append(f"{row}{col}")

    return valid


def create_well_cell(
    position: str,
    state: WellState | str = WellState.EMPTY,
    plate_format: int = 96,
    construct_name: Optional[str] = None,
    well_type: Optional[str] = None,
    has_ligand: bool = False,
    ligand_condition: Optional[str] = None,
    is_selected: bool = False,
    enforce_checkerboard: bool = False,
    pattern: str = 'A',
    cell_size: int = 32,
    cell_id: Optional[str] = None,
    skip_edges: bool = False,
    dark_mode: bool = False,
    construct_color: Optional[str] = None,
) -> html.Div:
    """
    Create a single well cell component.

    Args:
        position: Well position (e.g., "A1")
        state: Current well state
        plate_format: 96 or 384
        construct_name: Name of assigned construct
        well_type: Type of well (sample, blank, control)
        has_ligand: Whether well has ligand
        ligand_condition: Ligand condition string (+Lig/-Lig)
        is_selected: Whether well is selected
        enforce_checkerboard: Whether to enforce checkerboard for 384-well
        pattern: Checkerboard pattern ('A' or 'B')
        cell_size: Size of cell in pixels
        cell_id: Optional custom ID
        skip_edges: Whether to block edge wells
        dark_mode: Whether to use dark mode colors
        construct_color: Optional per-construct color override for sample wells

    Returns:
        Div component for the well cell
    """
    # Check if blocked by checkerboard or skip edges
    is_blocked = False
    if skip_edges and is_edge_well(position, plate_format):
        is_blocked = True
        state = WellState.BLOCKED
    elif enforce_checkerboard and plate_format == 384:
        if not is_checkerboard_valid_well(position, plate_format, pattern):
            is_blocked = True
            state = WellState.BLOCKED

    # Determine actual state based on well_type if provided
    actual_state = state
    if well_type:
        if well_type in ("negative_control_no_template", "negative_control_no_dye", "blank"):
            actual_state = WellState.CONTROL
        elif well_type == "sample" and construct_name:
            actual_state = WellState.ASSIGNED
        elif well_type == "empty":
            actual_state = WellState.EMPTY

    if is_selected and not is_blocked:
        actual_state = WellState.SELECTED

    # Get style
    style = get_well_state_style(actual_state, is_selected, has_ligand, dark_mode)
    style.update({
        "width": f"{cell_size}px",
        "height": f"{cell_size}px",
        "display": "flex",
        "alignItems": "center",
        "justifyContent": "center",
        "fontSize": f"{max(8, cell_size // 4)}px",
        "fontWeight": 500,
        "userSelect": "none",
    })

    # Apply per-construct color override for sample wells
    if construct_color and actual_state == WellState.ASSIGNED:
        style["backgroundColor"] = construct_color
        style["border"] = f"2px solid {_darken_hex(construct_color, 0.7)}"

    # Cell content
    content = []

    if is_blocked:
        content.append(html.Span("×", style={"color": "#555" if dark_mode else "#adb5bd", "fontSize": "16px"}))
    elif construct_name:
        # Show abbreviated construct name
        abbrev = construct_name[:3] if len(construct_name) > 3 else construct_name
        content.append(html.Span(abbrev, style={"color": "white"}))
    elif well_type and well_type not in ("empty", "sample"):
        # Show well type indicator
        type_indicators = {
            "blank": "B",
            "negative_control_no_template": "-T",
            "negative_control_no_dye": "-D",
        }
        indicator = type_indicators.get(well_type, "")
        content.append(html.Span(indicator, style={"color": "white"}))

    # Ligand condition indicator (prefer +Lig/-Lig over concentration dot)
    if not is_blocked:
        if ligand_condition == LigandCondition.PLUS_LIG:
            content.append(html.Div(
                "+",
                style={
                    "position": "absolute",
                    "top": "-2px",
                    "right": "-2px",
                    "fontSize": "10px",
                    "fontWeight": "900",
                    "color": "white",
                    "backgroundColor": "#20c997",
                    "borderRadius": "50%",
                    "width": "14px",
                    "height": "14px",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "lineHeight": "1",
                    "border": "1.5px solid {}".format("#1e2828" if dark_mode else "white"),
                    "zIndex": "2",
                }
            ))
        elif ligand_condition == LigandCondition.MINUS_LIG:
            content.append(html.Div(
                "\u2212",
                style={
                    "position": "absolute",
                    "top": "-2px",
                    "right": "-2px",
                    "fontSize": "10px",
                    "fontWeight": "900",
                    "color": "white",
                    "backgroundColor": "#fd7e14",
                    "borderRadius": "50%",
                    "width": "14px",
                    "height": "14px",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "lineHeight": "1",
                    "border": "1.5px solid {}".format("#1e2828" if dark_mode else "white"),
                    "zIndex": "2",
                }
            ))
        elif has_ligand:
            content.append(html.Div(
                style={
                    "position": "absolute",
                    "top": "-1px",
                    "right": "-1px",
                    "width": "8px",
                    "height": "8px",
                    "borderRadius": "50%",
                    "backgroundColor": "#fa5252",
                    "border": "1.5px solid {}".format("#1e2828" if dark_mode else "white"),
                    "zIndex": "2",
                }
            ))

    # Build title with condition info
    title_parts = [position]
    if construct_name:
        title_parts.append(construct_name)
    elif well_type:
        title_parts.append(well_type)
    else:
        title_parts.append("Empty")
    if ligand_condition:
        title_parts.append(ligand_condition)

    return html.Div(
        children=content,
        id=cell_id or f"well-{position}",
        style=style,
        className="well-cell",
        title=": ".join(title_parts),
        **{"data-well": position},
    )


def create_plate_grid(
    plate_format: int = 96,
    grid_id: str = "plate-grid",
    assignments: Optional[Dict[str, Dict]] = None,
    selected_wells: Optional[List[str]] = None,
    enforce_checkerboard: bool = False,
    pattern: str = 'A',
    readonly: bool = False,
    cell_size: Optional[int] = None,
    skip_edges: bool = False,
    dark_mode: bool = False,
    zoom: Optional[int] = None,
) -> dmc.Paper:
    """
    Create an interactive plate grid component.

    Args:
        plate_format: 96 or 384
        grid_id: Base ID for the grid component
        assignments: Dict mapping well positions to assignment data
        selected_wells: List of currently selected wells
        enforce_checkerboard: Whether to enforce checkerboard for 384-well
        pattern: Checkerboard pattern ('A' or 'B')
        readonly: Whether the grid is read-only
        cell_size: Override cell size in pixels
        skip_edges: Whether to block edge wells
        dark_mode: Whether to use dark mode colors
        zoom: Current zoom percentage (e.g. 100). Applied as CSS transform.

    Returns:
        Paper component containing the plate grid
    """
    assignments = assignments or {}
    selected_wells = selected_wells or []

    # Determine dimensions
    if plate_format == 384:
        rows = ROWS_384
        cols = COLS_384
        default_cell_size = 26  # Increased from 20 for better accessibility
    else:
        rows = ROWS_96
        cols = COLS_96
        default_cell_size = 40  # Increased from 32 for better accessibility

    cell_size = cell_size or default_cell_size
    label_color = "#a0a8a8" if dark_mode else "#868e96"

    # Create header row (column labels)
    header_cells = [html.Div(style={"width": "28px"})]  # Empty corner
    for col in cols:
        header_cells.append(html.Div(
            str(col),
            style={
                "width": f"{cell_size}px",
                "textAlign": "center",
                "fontSize": "11px",
                "color": label_color,
                "fontWeight": 500,
            }
        ))

    header_row = html.Div(
        header_cells,
        style={"display": "flex", "gap": "2px", "marginBottom": "2px"}
    )

    # Build per-construct color mapping for distinct sample colors
    construct_names = sorted({
        a.get("construct_name")
        for a in assignments.values()
        if a.get("well_type") == "sample" and a.get("construct_name")
    })
    palette = CONSTRUCT_PALETTE_DARK if dark_mode else CONSTRUCT_PALETTE
    construct_color_map = {
        name: palette[i % len(palette)]
        for i, name in enumerate(construct_names)
    }

    # Create well rows
    well_rows = []
    for row_letter in rows:
        row_cells = [
            html.Div(
                row_letter,
                style={
                    "width": "28px",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "fontSize": "11px",
                    "color": label_color,
                    "fontWeight": 500,
                }
            )
        ]

        for col in cols:
            position = f"{row_letter}{col}"
            assignment = assignments.get(position, {})
            is_selected = position in selected_wells

            cell = create_well_cell(
                position=position,
                plate_format=plate_format,
                construct_name=assignment.get("construct_name"),
                well_type=assignment.get("well_type"),
                has_ligand=assignment.get("ligand_condition") == LigandCondition.PLUS_LIG,
                ligand_condition=assignment.get("ligand_condition"),
                is_selected=is_selected,
                enforce_checkerboard=enforce_checkerboard,
                pattern=pattern,
                cell_size=cell_size,
                cell_id={"type": "plate-well", "index": position},
                skip_edges=skip_edges,
                dark_mode=dark_mode,
                construct_color=construct_color_map.get(assignment.get("construct_name")),
            )
            row_cells.append(cell)

        well_rows.append(html.Div(
            row_cells,
            style={"display": "flex", "gap": "2px"}
        ))

    # Wrap in container
    container_style = {
        "display": "inline-block",
        "cursor": "crosshair" if not readonly else "default",
    }
    if zoom is not None and zoom != 100:
        scale = zoom / 100
        container_style["transform"] = f"scale({scale})"
        container_style["transformOrigin"] = "top left"

    grid_container = html.Div(
        [header_row] + well_rows,
        id=f"{grid_id}-container",
        style=container_style,
    )

    return dmc.Paper(
        children=[grid_container],
        p="md",
        withBorder=True,
        radius="md",
        id=grid_id,
        style={"overflowX": "auto"},
    )


def create_zoom_control(grid_id: str = "plate-grid") -> dmc.Group:
    """
    Create a standalone zoom slider control for 384-well plate grids.

    Separated from create_plate_grid so the slider persists across
    grid re-renders (e.g., on well selection) without resetting zoom.

    Args:
        grid_id: Base ID matching the plate grid it controls.

    Returns:
        Group component containing the zoom slider.
    """
    return dmc.Group(
        children=[
            DashIconify(icon="mdi:magnify-minus-outline", width=16, color="gray"),
            dmc.Slider(
                id=f"{grid_id}-zoom-slider",
                min=50,
                max=150,
                value=100,
                step=10,
                marks=[
                    {"value": 50, "label": "50%"},
                    {"value": 100, "label": "100%"},
                    {"value": 150, "label": "150%"},
                ],
                style={"flex": 1, "maxWidth": 200},
                size="xs",
            ),
            DashIconify(icon="mdi:magnify-plus-outline", width=16, color="gray"),
        ],
        gap="xs",
        mb="sm",
        align="center",
    )


def create_plate_grid_skeleton(plate_format: int = 96) -> dmc.Paper:
    """
    Create a skeleton placeholder for plate grid loading state.

    Args:
        plate_format: 96 or 384

    Returns:
        Skeleton plate grid component
    """
    n_rows = 16 if plate_format == 384 else 8
    n_cols = 24 if plate_format == 384 else 12
    cell_size = 26 if plate_format == 384 else 40

    skeleton_rows = []
    for _ in range(n_rows):
        row_cells = []
        for _ in range(n_cols):
            row_cells.append(dmc.Skeleton(
                height=cell_size,
                width=cell_size,
                radius="sm",
            ))
        skeleton_rows.append(dmc.Group(row_cells, gap=2))

    return dmc.Paper(
        children=dmc.Stack(skeleton_rows, gap=2),
        p="md",
        withBorder=True,
        radius="md",
    )


def create_selection_helpers(
    plate_format: int = 96,
    helpers_id: str = "selection-helpers",
) -> dmc.Paper:
    """
    Create selection helper buttons.

    Args:
        plate_format: 96 or 384
        helpers_id: Base ID for helper components

    Returns:
        Paper component with selection helper buttons
    """
    rows = ROWS_384 if plate_format == 384 else ROWS_96
    cols = COLS_384 if plate_format == 384 else COLS_96

    # Row selection buttons
    row_buttons = []
    for row in rows:
        row_buttons.append(dmc.Button(
            row,
            id={"type": "selection-helper", "action": "row", "value": row},
            variant="subtle",
            size="compact-xs",
        ))

    # Column selection buttons
    col_buttons = []
    for col in cols:
        col_buttons.append(dmc.Button(
            str(col),
            id={"type": "selection-helper", "action": "column", "value": str(col)},
            variant="subtle",
            size="compact-xs",
        ))

    return dmc.Paper(
        children=[
            dmc.Stack([
                dmc.Group([
                    dmc.Text("Selection Helpers", size="sm", fw=500),
                    dmc.Group([
                        dmc.Button(
                            "Select All",
                            id={"type": "selection-helper", "action": "all", "value": "all"},
                            variant="light",
                            size="xs",
                            leftSection=DashIconify(icon="mdi:select-all", width=16),
                        ),
                        dmc.Button(
                            "Clear Selection",
                            id={"type": "selection-helper", "action": "clear", "value": "clear"},
                            variant="light",
                            color="red",
                            size="xs",
                            leftSection=DashIconify(icon="mdi:close-circle-outline", width=16),
                        ),
                    ], gap="xs"),
                ], justify="space-between"),

                dmc.Divider(),

                dmc.Group([
                    dmc.Text("Rows:", size="xs", c="dimmed"),
                    dmc.Group(row_buttons, gap=2),
                ], gap="xs"),

                dmc.Group([
                    dmc.Text("Columns:", size="xs", c="dimmed"),
                    dmc.Group(col_buttons, gap=2),
                ], gap="xs"),
            ], gap="xs"),
        ],
        p="sm",
        withBorder=True,
        radius="md",
        id=helpers_id,
    )


def create_assignment_panel(
    panel_id: str = "assignment-panel",
    constructs: Optional[List[Dict]] = None,
    selected_count: int = 0,
) -> dmc.Paper:
    """
    Create the assignment panel for assigning constructs to wells.

    Args:
        panel_id: Base ID for panel components
        constructs: List of construct dicts with id, identifier, family
        selected_count: Number of currently selected wells

    Returns:
        Paper component with assignment controls
    """
    constructs = constructs or []

    # Build construct options
    construct_options = [{"value": "", "label": "Select construct..."}]
    for c in constructs:
        label = c.get("identifier", f"Construct {c.get('id')}")
        if c.get("family"):
            label = f"{label} ({c.get('family')})"
        construct_options.append({
            "value": str(c.get("id")),
            "label": label,
        })

    # Well type options
    well_type_options = [
        {"value": "sample", "label": "Sample"},
        {"value": "blank", "label": "Blank"},
        {"value": "negative_control_no_template", "label": "-Template"},
        {"value": "negative_control_no_dye", "label": "-DFHBI"},
    ]

    return dmc.Paper(
        children=[
            dmc.Stack([
                dmc.Group([
                    dmc.Title("Assignment Panel", order=5),
                    dmc.Badge(
                        f"{selected_count} wells selected",
                        color="green" if selected_count > 0 else "gray",
                        id=f"{panel_id}-count-badge",
                    ),
                ], justify="space-between"),

                dmc.Divider(),

                dmc.Stack([
                    dmc.Select(
                        label="Construct",
                        placeholder="Select construct...",
                        data=construct_options,
                        id=f"{panel_id}-construct-select",
                        disabled=selected_count == 0,
                    ),

                    dmc.Select(
                        label="Well Type",
                        placeholder="Select well type...",
                        data=well_type_options,
                        value="sample",
                        id=f"{panel_id}-type-select",
                        disabled=selected_count == 0,
                    ),

                    dmc.TextInput(
                        label="Replicate Group",
                        placeholder="Optional group name",
                        id=f"{panel_id}-replicate-group",
                        disabled=selected_count == 0,
                    ),

                    dmc.Switch(
                        label="Ligand (+Lig)",
                        checked=False,
                        id=f"{panel_id}-ligand-condition",
                        disabled=selected_count == 0,
                    ),
                ], gap="sm"),

                dmc.Group([
                    dmc.Button(
                        "Clear",
                        id=f"{panel_id}-clear-btn",
                        variant="subtle",
                        color="red",
                        disabled=selected_count == 0,
                        leftSection=DashIconify(icon="mdi:eraser", width=20),
                    ),
                    dmc.Button(
                        "Assign",
                        id=f"{panel_id}-assign-btn",
                        disabled=selected_count == 0,
                        leftSection=DashIconify(icon="mdi:check", width=20),
                        style={"flex": 1},
                    ),
                ]),
            ], gap="md"),
        ],
        p="md",
        withBorder=True,
        radius="md",
        id=panel_id,
        style={"position": "sticky", "top": "76px", "zIndex": 5},
    )
