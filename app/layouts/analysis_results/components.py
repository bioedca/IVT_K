"""Shared helper components for analysis results layout."""
from typing import Optional, Union
import dash_mantine_components as dmc


def _format_with_se(value: Optional[float], se: Optional[float], decimals: int = 4) -> str:
    """Format a value with its SE, using scientific notation for very small SE."""
    if value is None:
        return "\u2014"
    if se is None or se == 0:
        return f"{value:.{decimals}f}"
    # Use scientific notation for SE < 0.001
    if se < 0.001:
        return f"{value:.{decimals}f} \u00b1 {se:.2e}"
    elif se < 0.01:
        return f"{value:.{decimals}f} \u00b1 {se:.4f}"
    else:
        return f"{value:.{decimals}f} \u00b1 {se:.3f}"


def get_ligand_condition_badge(ligand_condition: Optional[str]) -> Union[dmc.Badge, str]:
    """
    Create a ligand condition badge with standard color coding.

    Args:
        ligand_condition: "+Lig", "-Lig", "+Lig/-Lig", or None

    Returns:
        Badge component or em-dash text
    """
    if ligand_condition == "+Lig":
        return dmc.Badge("+Lig", color="teal", size="xs", variant="light")
    elif ligand_condition == "-Lig":
        return dmc.Badge("-Lig", color="orange", size="xs", variant="light")
    elif ligand_condition == "+Lig/-Lig":
        return dmc.Badge("Lig Effect", color="violet", size="xs", variant="light")
    else:
        return "\u2014"


def get_vif_badge(vif: float, path_type: str) -> dmc.Badge:
    """
    Create a VIF badge with appropriate color coding.

    Args:
        vif: Variance inflation factor
        path_type: Path type description

    Returns:
        Badge component
    """
    if vif <= 1.0:
        color = "green"
    elif vif <= 1.5:
        color = "yellow"
    elif vif <= 2.5:
        color = "orange"
    else:
        color = "red"

    return dmc.Badge(
        f"{path_type} (VIF={vif:.2f})",
        color=color,
        size="sm",
        variant="light",
    )
