"""
Scientific Editorial theme for IVT Kinetics Analyzer.

Defines Mantine theme overrides, color scales, family color mapping,
and Plotly dark/light mode helpers.
"""
import hashlib
from typing import Dict, List, Union

# Teal 10-shade scale (primary)
TEAL_SCALE = [
    "#E6FAF8",  # 0 - lightest
    "#B3F0EA",  # 1
    "#80E6DC",  # 2
    "#4DDCCE",  # 3
    "#26CEBC",  # 4
    "#0C7C6F",  # 5 - primary
    "#0A6B60",  # 6
    "#085A51",  # 7
    "#064942",  # 8
    "#043833",  # 9 - darkest
]

# Amber 10-shade scale (accent)
AMBER_SCALE = [
    "#FFF8E6",  # 0 - lightest
    "#FEECC0",  # 1
    "#FDD98A",  # 2
    "#FCC654",  # 3
    "#F5B623",  # 4
    "#D4860B",  # 5 - primary
    "#B87209",  # 6
    "#9C5F07",  # 7
    "#804D06",  # 8
    "#643C04",  # 9 - darkest
]

# Fallback color cycle for unmapped families
_FALLBACK_CYCLE: List[str] = ["teal", "violet", "indigo", "cyan", "orange", "pink", "lime", "grape"]

# Family color mapping for consistent color-coding across the app
FAMILY_COLORS: Dict[str, str] = {
    "T-box": "teal",
    "Riboswitch": "violet",
    "Aptamer": "indigo",
    "Ribozyme": "cyan",
    "Control": "gray",
    "Other": "orange",
}


def get_family_color(family_name: str) -> str:
    """Get the Mantine color name for a construct family."""
    if family_name in FAMILY_COLORS:
        return FAMILY_COLORS[family_name]
    # Deterministic fallback using stable hash (consistent across sessions)
    stable_idx = int(hashlib.md5(family_name.encode()).hexdigest(), 16)
    return _FALLBACK_CYCLE[stable_idx % len(_FALLBACK_CYCLE)]


# Mantine theme configuration
SCIENTIFIC_THEME = {
    "primaryColor": "scientific-teal",
    "colors": {
        "scientific-teal": TEAL_SCALE,
        "scientific-amber": AMBER_SCALE,
    },
    "fontFamily": "'Source Sans 3', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    "fontFamilyMonospace": "'JetBrains Mono', 'Fira Code', monospace",
    "headings": {
        "fontFamily": "'Instrument Serif', Georgia, 'Times New Roman', serif",
    },
    "defaultRadius": "lg",
    "components": {
        "Paper": {
            "defaultProps": {
                "shadow": "sm",
                "radius": "lg",
            }
        },
        "Button": {
            "defaultProps": {
                "radius": "md",
            }
        },
        "Badge": {
            "defaultProps": {
                "radius": "md",
            }
        },
        "Card": {
            "defaultProps": {
                "radius": "lg",
                "shadow": "sm",
            }
        },
    },
}

# ---------------------------------------------------------------------------
# Plotly dark/light mode helpers
# ---------------------------------------------------------------------------

PLOTLY_LIGHT_TEMPLATE = "simple_white"
PLOTLY_DARK_TEMPLATE = "plotly_dark"


def get_plotly_template(dark_mode=False):
    """Return Plotly template string for current color scheme."""
    return PLOTLY_DARK_TEMPLATE if dark_mode else PLOTLY_LIGHT_TEMPLATE


def apply_plotly_theme(fig, dark_mode=False):
    """Apply scientific theme to a Plotly figure. Mutates fig in place."""
    template = get_plotly_template(dark_mode)
    fig.update_layout(
        template=template,
        font_family="Source Sans 3, sans-serif",
    )
    if dark_mode:
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#1e2a2a",
            font_color="#c0c0c0",
            xaxis=dict(
                gridcolor="rgba(255,255,255,0.06)",
                zerolinecolor="rgba(255,255,255,0.12)",
                tickfont=dict(color="#a0a8a8"),
            ),
            yaxis=dict(
                gridcolor="rgba(255,255,255,0.06)",
                zerolinecolor="rgba(255,255,255,0.12)",
                tickfont=dict(color="#a0a8a8"),
            ),
            modebar=dict(
                bgcolor="rgba(0,0,0,0)",
                color="#6b7575",
                activecolor="#26CEBC",
            ),
        )
    return fig


def get_annotation_bg(dark_mode=False):
    """Return a semi-transparent background color for Plotly annotations."""
    if dark_mode:
        return "rgba(30,42,42,0.9)"
    return "rgba(255,255,255,0.9)"
