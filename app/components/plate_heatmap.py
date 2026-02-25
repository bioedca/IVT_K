"""
Plate heatmap visualization components.

Phase 8.1: Plate Heatmaps (F13.1, F13.3)

Provides:
- 96-well plate heatmap
- 384-well checkerboard heatmap
- Color scale selection
- Well tooltip on hover
"""
from typing import Dict, List, Any, Optional, Tuple
import plotly.graph_objects as go
import numpy as np

from app.theme import apply_plotly_theme


# Well position mappings
ROWS_96 = list("ABCDEFGH")
COLS_96 = list(range(1, 13))
ROWS_384 = list("ABCDEFGHIJKLMNOP")
COLS_384 = list(range(1, 25))


def well_to_coords(well: str, plate_format: int = 96) -> Tuple[int, int]:
    """
    Convert well position to row, col indices.

    Args:
        well: Well position (e.g., "A1", "H12")
        plate_format: 96 or 384

    Returns:
        (row_idx, col_idx) tuple
    """
    row_letter = well[0].upper()
    col_num = int(well[1:])

    rows = ROWS_384 if plate_format == 384 else ROWS_96
    row_idx = rows.index(row_letter) if row_letter in rows else 0
    col_idx = col_num - 1

    return row_idx, col_idx


def _make_grid_shapes(n_rows: int, n_cols: int, dark_mode: bool = False) -> List[dict]:
    """Build grid-line shapes at every cell boundary (plate-style grid)."""
    shapes = []
    line_color = "#555555" if dark_mode else "#999999"
    line_width = 1

    # Vertical lines
    for i in range(n_cols + 1):
        shapes.append(dict(
            type="line",
            x0=i - 0.5, x1=i - 0.5,
            y0=-0.5, y1=n_rows - 0.5,
            line=dict(color=line_color, width=line_width),
            layer="above",
        ))

    # Horizontal lines
    for i in range(n_rows + 1):
        shapes.append(dict(
            type="line",
            x0=-0.5, x1=n_cols - 0.5,
            y0=i - 0.5, y1=i - 0.5,
            line=dict(color=line_color, width=line_width),
            layer="above",
        ))

    return shapes


def _plate_axis_layout(
    n_rows: int, n_cols: int, rows: list, cols: list,
    dark_mode: bool = False,
) -> dict:
    """Return common plate-style axis and background layout dict."""
    bg_color = "#1a1b1e" if dark_mode else "white"
    return dict(
        xaxis=dict(
            tickmode="array",
            tickvals=list(range(n_cols)),
            ticktext=[str(c) for c in cols],
            side="top",
            tickfont=dict(size=9),
            showgrid=False,
            zeroline=False,
            ticks="",
            scaleanchor="y",
            constrain="domain",
        ),
        yaxis=dict(
            tickmode="array",
            tickvals=list(range(n_rows)),
            ticktext=rows,
            autorange="reversed",
            tickfont=dict(size=9),
            showgrid=False,
            zeroline=False,
            ticks="",
            constrain="domain",
        ),
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
    )


def create_plate_heatmap(
    data: Dict[str, float],
    plate_format: int = 96,
    parameter: str = "value",
    colorscale: str = "Viridis",
    title: Optional[str] = None,
    show_values: bool = True,
    value_format: str = ".2f",
    null_color: str = "lightgray",
    height: int = 400,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a plate heatmap visualization.

    Args:
        data: Dict mapping well positions to values (e.g., {"A1": 1.5, "B2": 2.3})
        plate_format: 96 or 384
        parameter: Parameter name for color bar label
        colorscale: Plotly colorscale name
        title: Optional chart title
        show_values: Whether to show values in cells
        value_format: Format string for values
        null_color: Color for empty wells
        height: Figure height in pixels

    Returns:
        Plotly figure
    """
    if plate_format == 384:
        rows = ROWS_384
        cols = COLS_384
        n_rows, n_cols = 16, 24
    else:
        rows = ROWS_96
        cols = COLS_96
        n_rows, n_cols = 8, 12

    # Create data matrix
    z = np.full((n_rows, n_cols), np.nan)
    hover_text = [[None for _ in range(n_cols)] for _ in range(n_rows)]
    annotations = []

    for well, value in data.items():
        try:
            row_idx, col_idx = well_to_coords(well, plate_format)
            if 0 <= row_idx < n_rows and 0 <= col_idx < n_cols:
                z[row_idx, col_idx] = value
                hover_text[row_idx][col_idx] = f"{well}<br>{parameter}: {value:{value_format}}"

                if show_values and value is not None:
                    annotations.append(dict(
                        x=col_idx,
                        y=row_idx,
                        text=f"{value:{value_format}}",
                        showarrow=False,
                        font=dict(size=8 if plate_format == 384 else 10, color="white"),
                    ))
        except (ValueError, IndexError):
            continue

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=list(range(n_cols)),
        y=list(range(n_rows)),
        colorscale=colorscale,
        zsmooth=False,
        hoverongaps=False,
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_text,
        colorbar=dict(
            title=parameter,
            thickness=15,
            len=0.7,
        ),
        showscale=True,
    ))

    # Add annotations for values
    if show_values and annotations:
        for ann in annotations:
            fig.add_annotation(**ann)

    fig.update_layout(
        title=title,
        shapes=_make_grid_shapes(n_rows, n_cols, dark_mode=dark_mode),
        height=height,
        margin=dict(l=30, r=60, t=60 if title else 30, b=10),
        **_plate_axis_layout(n_rows, n_cols, rows, cols, dark_mode=dark_mode),
    )

    apply_plotly_theme(fig, dark_mode)
    return fig


def create_plate_heatmap_categorical(
    data: Dict[str, str],
    plate_format: int = 96,
    category_colors: Optional[Dict[str, str]] = None,
    title: Optional[str] = None,
    height: int = 400,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a plate heatmap with categorical data (e.g., construct names, status).

    Args:
        data: Dict mapping well positions to category values
        plate_format: 96 or 384
        category_colors: Optional mapping of categories to colors
        title: Optional chart title
        height: Figure height in pixels

    Returns:
        Plotly figure
    """
    if plate_format == 384:
        rows = ROWS_384
        cols = COLS_384
        n_rows, n_cols = 16, 24
    else:
        rows = ROWS_96
        cols = COLS_96
        n_rows, n_cols = 8, 12

    # Get unique categories and assign colors
    categories = sorted(set(data.values()))
    if category_colors is None:
        # Default color palette
        default_colors = [
            "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
            "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
        ]
        category_colors = {cat: default_colors[i % len(default_colors)]
                          for i, cat in enumerate(categories)}

    # Create numeric mapping for heatmap
    cat_to_num = {cat: i for i, cat in enumerate(categories)}

    z = np.full((n_rows, n_cols), np.nan)
    hover_text = [[None for _ in range(n_cols)] for _ in range(n_rows)]

    for well, category in data.items():
        try:
            row_idx, col_idx = well_to_coords(well, plate_format)
            if 0 <= row_idx < n_rows and 0 <= col_idx < n_cols:
                z[row_idx, col_idx] = cat_to_num.get(category, np.nan)
                hover_text[row_idx][col_idx] = f"{well}<br>{category}"
        except (ValueError, IndexError):
            continue

    # Create discrete colorscale
    n_cats = len(categories)
    colorscale = []
    for i, cat in enumerate(categories):
        color = category_colors.get(cat, "#808080")
        colorscale.append([i / n_cats, color])
        colorscale.append([(i + 1) / n_cats, color])

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=list(range(n_cols)),
        y=list(range(n_rows)),
        colorscale=colorscale,
        zsmooth=False,
        hoverongaps=False,
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_text,
        showscale=True,
        colorbar=dict(
            title="Category",
            tickmode="array",
            tickvals=[(i + 0.5) for i in range(n_cats)],
            ticktext=categories,
            thickness=15,
            len=0.7,
        ),
        zmin=0,
        zmax=n_cats,
    ))

    fig.update_layout(
        title=title,
        shapes=_make_grid_shapes(n_rows, n_cols, dark_mode=dark_mode),
        height=height,
        margin=dict(l=30, r=80, t=60 if title else 30, b=10),
        **_plate_axis_layout(n_rows, n_cols, rows, cols, dark_mode=dark_mode),
    )

    apply_plotly_theme(fig, dark_mode)
    return fig


def create_completion_heatmap(
    data: Dict[str, str],
    plate_format: int = 96,
    title: Optional[str] = None,
    height: int = 400,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a completion status heatmap with standard colors.

    Status colors:
    - "complete" / "met": Green
    - "near" / "close": Yellow
    - "far" / "not_met": Red
    - "pending": Gray
    - "excluded": Light gray

    Args:
        data: Dict mapping well positions to status
        plate_format: 96 or 384
        title: Optional chart title
        height: Figure height in pixels

    Returns:
        Plotly figure
    """
    status_colors = {
        "complete": "#40c057",
        "met": "#40c057",
        "near": "#fab005",
        "close": "#fab005",
        "far": "#fa5252",
        "not_met": "#fa5252",
        "pending": "#868e96",
        "excluded": "#dee2e6",
        "empty": "#f8f9fa",
    }

    return create_plate_heatmap_categorical(
        data=data,
        plate_format=plate_format,
        category_colors=status_colors,
        title=title,
        height=height,
        dark_mode=dark_mode,
    )


def create_checkerboard_heatmap(
    data: Dict[str, float],
    plate_format: int = 384,
    parameter: str = "value",
    colorscale: str = "RdYlGn",
    title: Optional[str] = None,
    highlight_pattern: bool = True,
    height: int = 500,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a 384-well checkerboard heatmap.

    In 384-well format, constructs are typically plated in checkerboard pattern
    with alternating wells used for different purposes.

    Args:
        data: Dict mapping well positions to values
        plate_format: 96 or 384
        parameter: Parameter name for color bar label
        colorscale: Plotly colorscale name
        title: Optional chart title
        highlight_pattern: Whether to highlight checkerboard pattern
        height: Figure height in pixels

    Returns:
        Plotly figure
    """
    fig = create_plate_heatmap(
        data=data,
        plate_format=plate_format,
        parameter=parameter,
        colorscale=colorscale,
        title=title,
        show_values=False,  # Too small for 384
        height=height,
        dark_mode=dark_mode,
    )

    if highlight_pattern and plate_format == 384:
        # Add subtle checkerboard overlay on top of grid lines
        existing_shapes = list(fig.layout.shapes or [])
        for row in range(16):
            for col in range(24):
                if (row + col) % 2 == 1:
                    existing_shapes.append(dict(
                        type="rect",
                        x0=col - 0.5,
                        x1=col + 0.5,
                        y0=row - 0.5,
                        y1=row + 0.5,
                        line=dict(color="rgba(0,0,0,0.1)", width=1),
                        fillcolor="rgba(0,0,0,0.02)",
                    ))
        fig.update_layout(shapes=existing_shapes)

    return fig


def create_multi_parameter_heatmap(
    well_data: List[Dict[str, Any]],
    plate_format: int = 96,
    primary_param: str = "k_obs",
    secondary_param: Optional[str] = "r_squared",
    title: Optional[str] = None,
    height: int = 400,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a heatmap with primary color and secondary indicator.

    Args:
        well_data: List of dicts with 'well' and parameter values
        plate_format: 96 or 384
        primary_param: Parameter for color scale
        secondary_param: Optional parameter for border/marker
        title: Optional chart title
        height: Figure height

    Returns:
        Plotly figure
    """
    # Extract primary parameter data
    primary_data = {}
    secondary_data = {}

    for item in well_data:
        well = item.get("well")
        if well:
            if primary_param in item and item[primary_param] is not None:
                primary_data[well] = item[primary_param]
            if secondary_param and secondary_param in item and item[secondary_param] is not None:
                secondary_data[well] = item[secondary_param]

    # Create base heatmap
    fig = create_plate_heatmap(
        data=primary_data,
        plate_format=plate_format,
        parameter=primary_param,
        title=title,
        height=height,
        dark_mode=dark_mode,
    )

    # Add secondary parameter as markers if available
    if secondary_data and secondary_param:
        rows = ROWS_384 if plate_format == 384 else ROWS_96

        x_coords = []
        y_coords = []
        marker_sizes = []
        hover_texts = []

        for well, value in secondary_data.items():
            row_idx, col_idx = well_to_coords(well, plate_format)
            x_coords.append(col_idx)
            y_coords.append(row_idx)
            # Scale marker size by secondary value (assuming 0-1 range like R²)
            marker_sizes.append(max(5, min(20, value * 20)))
            hover_texts.append(f"{well}<br>{secondary_param}: {value:.3f}")

        fig.add_trace(go.Scatter(
            x=x_coords,
            y=y_coords,
            mode="markers",
            marker=dict(
                size=marker_sizes,
                color="white",
                opacity=0.6,
                line=dict(color="black", width=1),
            ),
            hovertemplate="%{text}<extra></extra>",
            text=hover_texts,
            showlegend=False,
        ))

    return fig


# Convenience functions for common parameters
def create_kobs_heatmap(
    data: Dict[str, float],
    plate_format: int = 96,
    title: str = "k_obs by Well Position",
    dark_mode: bool = False,
) -> go.Figure:
    """Create heatmap for k_obs values."""
    return create_plate_heatmap(
        data=data,
        plate_format=plate_format,
        parameter="k_obs (min⁻¹)",
        colorscale="Viridis",
        title=title,
        dark_mode=dark_mode,
    )


def create_fmax_heatmap(
    data: Dict[str, float],
    plate_format: int = 96,
    title: str = "F_max by Well Position",
    dark_mode: bool = False,
) -> go.Figure:
    """Create heatmap for F_max values."""
    return create_plate_heatmap(
        data=data,
        plate_format=plate_format,
        parameter="F_max (RFU)",
        colorscale="Plasma",
        title=title,
        dark_mode=dark_mode,
    )


def create_rsquared_heatmap(
    data: Dict[str, float],
    plate_format: int = 96,
    title: str = "R² by Well Position",
    dark_mode: bool = False,
) -> go.Figure:
    """Create heatmap for R² values with good=green, poor=red."""
    return create_plate_heatmap(
        data=data,
        plate_format=plate_format,
        parameter="R²",
        colorscale="RdYlGn",
        title=title,
        dark_mode=dark_mode,
    )


def create_layout_heatmap_with_draft_indicators(
    well_assignments: List[Dict[str, Any]],
    plate_format: int = 96,
    title: Optional[str] = None,
    height: int = 400,
    dark_mode: bool = False,
) -> go.Figure:
    """
    Create a plate layout heatmap with draft construct visual distinction.

    PRD Reference: Section 0.22, F3.6
    Draft constructs are displayed with:
    - Dashed border around wells
    - Gray background color
    - "DRAFT" text indicator in cell

    Args:
        well_assignments: List of dicts with 'well', 'construct_name', 'is_draft', 'color'
        plate_format: 96 or 384
        title: Optional chart title
        height: Figure height in pixels

    Returns:
        Plotly figure with draft visual distinction
    """
    if plate_format == 384:
        rows = ROWS_384
        cols = COLS_384
        n_rows, n_cols = 16, 24
        font_size = 6
    else:
        rows = ROWS_96
        cols = COLS_96
        n_rows, n_cols = 8, 12
        font_size = 9

    # Prepare data structures
    z = np.full((n_rows, n_cols), np.nan)
    hover_text = [[None for _ in range(n_cols)] for _ in range(n_rows)]
    annotations = []
    draft_shapes = []

    # Get unique constructs and assign numeric values
    construct_names = set()
    for item in well_assignments:
        if item.get("construct_name"):
            construct_names.add(item["construct_name"])
    construct_names = sorted(construct_names)
    construct_to_num = {name: i for i, name in enumerate(construct_names)}

    # Default colors for constructs
    default_colors = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
        "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5",
    ]

    # Build color mapping
    construct_colors = {}
    for i, name in enumerate(construct_names):
        construct_colors[name] = default_colors[i % len(default_colors)]

    # Process each well assignment
    for item in well_assignments:
        well = item.get("well")
        construct_name = item.get("construct_name")
        is_draft = item.get("is_draft", False)
        custom_color = item.get("color")

        if not well:
            continue

        try:
            row_idx, col_idx = well_to_coords(well, plate_format)
            if not (0 <= row_idx < n_rows and 0 <= col_idx < n_cols):
                continue

            if construct_name:
                z[row_idx, col_idx] = construct_to_num.get(construct_name, 0)

                # Use custom color or default
                color = custom_color or construct_colors.get(construct_name, "#808080")

                # Draft constructs get gray background
                if is_draft:
                    color = "#e0e0e0"  # Light gray for draft

                # Build hover text
                status_text = " (DRAFT)" if is_draft else ""
                hover_text[row_idx][col_idx] = f"{well}<br>{construct_name}{status_text}"

                # Add construct label annotation
                label_text = construct_name[:8]  # Truncate long names
                if is_draft:
                    label_text = f"{label_text[:6]}*"  # Add asterisk for draft

                annotations.append(dict(
                    x=col_idx,
                    y=row_idx,
                    text=label_text,
                    showarrow=False,
                    font=dict(
                        size=font_size,
                        color="black" if is_draft else "white"
                    ),
                ))

                # Add dashed border for draft constructs
                if is_draft:
                    draft_shapes.append(dict(
                        type="rect",
                        x0=col_idx - 0.45,
                        x1=col_idx + 0.45,
                        y0=row_idx - 0.45,
                        y1=row_idx + 0.45,
                        line=dict(
                            color="#666666",
                            width=2,
                            dash="dash"  # Dashed border for draft
                        ),
                        fillcolor="rgba(0,0,0,0)",
                    ))
            else:
                # Empty well
                hover_text[row_idx][col_idx] = f"{well}<br>Empty"

        except (ValueError, IndexError):
            continue

    # Build discrete colorscale from construct colors
    n_constructs = len(construct_names)
    if n_constructs > 0:
        colorscale = []
        for i, name in enumerate(construct_names):
            color = construct_colors.get(name, "#808080")
            colorscale.append([i / n_constructs, color])
            colorscale.append([(i + 1) / n_constructs, color])
    else:
        colorscale = [[0, "#f8f9fa"], [1, "#f8f9fa"]]

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=list(range(n_cols)),
        y=list(range(n_rows)),
        colorscale=colorscale,
        zsmooth=False,
        hoverongaps=False,
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_text,
        showscale=True if n_constructs > 0 else False,
        colorbar=dict(
            title="Construct",
            tickmode="array",
            tickvals=[(i + 0.5) for i in range(n_constructs)] if n_constructs > 0 else [],
            ticktext=construct_names if n_constructs > 0 else [],
            thickness=15,
            len=0.7,
        ) if n_constructs > 0 else None,
        zmin=0,
        zmax=max(n_constructs, 1),
    ))

    # Add annotations
    for ann in annotations:
        fig.add_annotation(**ann)

    # Grid lines + draft shapes
    all_shapes = _make_grid_shapes(n_rows, n_cols, dark_mode=dark_mode) + draft_shapes

    fig.update_layout(
        title=title,
        shapes=all_shapes,
        height=height,
        margin=dict(l=30, r=80, t=60 if title else 30, b=10),
        **_plate_axis_layout(n_rows, n_cols, rows, cols, dark_mode=dark_mode),
    )

    apply_plotly_theme(fig, dark_mode)
    return fig


def get_draft_well_style() -> Dict[str, Any]:
    """
    Return CSS style dict for draft construct wells in Dash components.

    PRD Reference: Section 0.22, F3.6
    Draft constructs should have dashed border + gray background.

    Returns:
        Dict of CSS properties for draft well styling
    """
    return {
        "border": "2px dashed #666666",
        "backgroundColor": "#f0f0f0",
        "position": "relative",
    }


def create_draft_badge():
    """
    Create a "DRAFT" badge component for overlay on draft constructs.

    PRD Reference: Section 0.22, F3.6

    Returns:
        Dash component for draft badge (requires dash_mantine_components)
    """
    # Import here to avoid circular dependency
    import dash_mantine_components as dmc

    return dmc.Badge(
        "DRAFT",
        color="gray",
        size="xs",
        variant="filled",
        style={
            "position": "absolute",
            "top": "2px",
            "right": "2px",
            "fontSize": "8px",
            "padding": "2px 4px",
        }
    )
