"""DNA dilution calculator for normalizing stock concentrations."""
from dataclasses import dataclass
from typing import Optional, List

from .constants import (
    MIN_PIPETTABLE_VOLUME_UL,
    TARGET_DNA_VOLUME_UL,
    MIN_DILUTION_STOCK_UL,
    MIN_DILUTED_CONCENTRATION_NG_UL,
)


@dataclass
class DilutionStep:
    """A single step in the dilution protocol."""
    step_number: int
    action: str
    volume_ul: float
    component: str
    notes: Optional[str] = None


@dataclass
class DilutionProtocol:
    """Complete DNA dilution protocol."""
    original_concentration_ng_ul: float
    target_concentration_ng_ul: float
    dilution_factor: float
    stock_volume_ul: float
    diluent_volume_ul: float
    final_volume_ul: float
    steps: List[DilutionStep]
    is_recommended: bool = True
    warning: Optional[str] = None


@dataclass
class SerialDilutionProtocol:
    """Multi-step serial dilution protocol."""
    original_concentration_ng_ul: float
    final_concentration_ng_ul: float
    total_dilution_factor: float
    dilutions: List[DilutionProtocol]
    total_stock_consumed_ul: float


def calculate_simple_dilution(
    original_concentration_ng_ul: float,
    target_concentration_ng_ul: float,
    stock_volume_ul: float = MIN_DILUTION_STOCK_UL,
) -> DilutionProtocol:
    """
    Calculate a simple (single-step) dilution protocol.

    Uses C1V1 = C2V2 formula.

    Args:
        original_concentration_ng_ul: Starting DNA concentration
        target_concentration_ng_ul: Desired final concentration
        stock_volume_ul: Amount of stock DNA to use

    Returns:
        DilutionProtocol with steps
    """
    if target_concentration_ng_ul >= original_concentration_ng_ul:
        raise ValueError(
            f"Target concentration ({target_concentration_ng_ul}) must be "
            f"less than original ({original_concentration_ng_ul})"
        )

    if target_concentration_ng_ul <= 0:
        raise ValueError("Target concentration must be positive")

    dilution_factor = original_concentration_ng_ul / target_concentration_ng_ul
    final_volume = stock_volume_ul * dilution_factor
    diluent_volume = final_volume - stock_volume_ul

    steps = [
        DilutionStep(
            step_number=1,
            action="Pipette into new tube",
            volume_ul=stock_volume_ul,
            component="DNA stock",
            notes=f"From {original_concentration_ng_ul:.1f} ng/µL stock",
        ),
        DilutionStep(
            step_number=2,
            action="Add",
            volume_ul=diluent_volume,
            component="Nuclease-free water",
        ),
        DilutionStep(
            step_number=3,
            action="Mix gently",
            volume_ul=0.0,
            component="",
            notes="Pipette up and down 5-10 times",
        ),
    ]

    protocol = DilutionProtocol(
        original_concentration_ng_ul=original_concentration_ng_ul,
        target_concentration_ng_ul=target_concentration_ng_ul,
        dilution_factor=dilution_factor,
        stock_volume_ul=stock_volume_ul,
        diluent_volume_ul=diluent_volume,
        final_volume_ul=final_volume,
        steps=steps,
    )

    # Check if dilution is practical
    if target_concentration_ng_ul < MIN_DILUTED_CONCENTRATION_NG_UL:
        protocol.is_recommended = False
        protocol.warning = (
            f"Target concentration {target_concentration_ng_ul:.1f} ng/µL is very low. "
            "DNA may be unstable at this concentration."
        )

    if diluent_volume < MIN_PIPETTABLE_VOLUME_UL:
        protocol.is_recommended = False
        protocol.warning = (
            f"Diluent volume {diluent_volume:.2f} µL is below pipetting threshold. "
            "Use larger stock volume or serial dilution."
        )

    return protocol


def calculate_dilution_for_target_dna_volume(
    current_stock_ng_ul: float,
    current_dna_volume_ul: float,
    target_dna_volume_ul: float = TARGET_DNA_VOLUME_UL,
    stock_volume_ul: float = MIN_DILUTION_STOCK_UL,
) -> DilutionProtocol:
    """
    Calculate dilution needed to achieve target DNA volume.

    When DNA volume is below pipetting threshold, calculate the dilution
    needed to bring it up to a comfortable pipetting volume.

    Args:
        current_stock_ng_ul: Current DNA stock concentration
        current_dna_volume_ul: Current calculated DNA volume
        target_dna_volume_ul: Desired DNA volume for pipetting
        stock_volume_ul: Amount of stock to use for dilution

    Returns:
        DilutionProtocol
    """
    if current_dna_volume_ul >= target_dna_volume_ul:
        raise ValueError(
            f"Current DNA volume ({current_dna_volume_ul:.2f} µL) already meets "
            f"target ({target_dna_volume_ul:.2f} µL)"
        )

    # Calculate required dilution factor
    # If current volume is 0.3 µL and target is 2.0 µL, need to dilute by 2.0/0.3 = 6.67x
    dilution_factor = target_dna_volume_ul / current_dna_volume_ul
    target_concentration = current_stock_ng_ul / dilution_factor

    return calculate_simple_dilution(
        original_concentration_ng_ul=current_stock_ng_ul,
        target_concentration_ng_ul=target_concentration,
        stock_volume_ul=stock_volume_ul,
    )


def calculate_serial_dilution(
    original_concentration_ng_ul: float,
    target_concentration_ng_ul: float,
    max_single_dilution: float = 100.0,
    stock_volume_per_step_ul: float = MIN_DILUTION_STOCK_UL,
) -> SerialDilutionProtocol:
    """
    Calculate a serial dilution when single dilution would be impractical.

    Used when dilution factor is very large (e.g., 1:1000 or more).

    Args:
        original_concentration_ng_ul: Starting concentration
        target_concentration_ng_ul: Final desired concentration
        max_single_dilution: Maximum fold dilution per step
        stock_volume_per_step_ul: Stock volume for each dilution step

    Returns:
        SerialDilutionProtocol with multiple steps
    """
    total_factor = original_concentration_ng_ul / target_concentration_ng_ul

    if total_factor <= max_single_dilution:
        # Single dilution is sufficient
        single = calculate_simple_dilution(
            original_concentration_ng_ul=original_concentration_ng_ul,
            target_concentration_ng_ul=target_concentration_ng_ul,
            stock_volume_ul=stock_volume_per_step_ul,
        )
        return SerialDilutionProtocol(
            original_concentration_ng_ul=original_concentration_ng_ul,
            final_concentration_ng_ul=target_concentration_ng_ul,
            total_dilution_factor=total_factor,
            dilutions=[single],
            total_stock_consumed_ul=stock_volume_per_step_ul,
        )

    # Calculate number of steps needed
    import math
    n_steps = math.ceil(math.log(total_factor) / math.log(max_single_dilution))

    # Calculate dilution factor per step
    factor_per_step = total_factor ** (1.0 / n_steps)

    dilutions = []
    current_conc = original_concentration_ng_ul
    total_stock = stock_volume_per_step_ul  # Only first step uses original stock

    for i in range(n_steps):
        next_conc = current_conc / factor_per_step

        # Last step should hit target exactly
        if i == n_steps - 1:
            next_conc = target_concentration_ng_ul

        dilution = calculate_simple_dilution(
            original_concentration_ng_ul=current_conc,
            target_concentration_ng_ul=next_conc,
            stock_volume_ul=stock_volume_per_step_ul,
        )
        dilutions.append(dilution)
        current_conc = next_conc

    return SerialDilutionProtocol(
        original_concentration_ng_ul=original_concentration_ng_ul,
        final_concentration_ng_ul=target_concentration_ng_ul,
        total_dilution_factor=total_factor,
        dilutions=dilutions,
        total_stock_consumed_ul=total_stock,
    )


def normalize_dna_stocks(
    constructs: List[dict],
    target_concentration_ng_ul: float,
) -> List[Optional[DilutionProtocol]]:
    """
    Calculate dilutions needed to normalize multiple DNA stocks.

    Args:
        constructs: List of dicts with 'name' and 'stock_concentration_ng_ul'
        target_concentration_ng_ul: Common target concentration

    Returns:
        List of DilutionProtocol (or None if no dilution needed)
    """
    protocols = []

    for construct in constructs:
        stock_conc = construct.get('stock_concentration_ng_ul', 0)

        if stock_conc <= target_concentration_ng_ul:
            # No dilution needed (or stock is already lower)
            protocols.append(None)
        else:
            protocol = calculate_simple_dilution(
                original_concentration_ng_ul=stock_conc,
                target_concentration_ng_ul=target_concentration_ng_ul,
            )
            protocols.append(protocol)

    return protocols


def format_dilution_protocol(protocol: DilutionProtocol) -> str:
    """
    Format a dilution protocol as text.

    Args:
        protocol: DilutionProtocol to format

    Returns:
        Formatted text string
    """
    lines = []
    lines.append("=" * 60)
    lines.append("DNA DILUTION PROTOCOL")
    lines.append("=" * 60)
    lines.append(f"Original concentration: {protocol.original_concentration_ng_ul:.1f} ng/µL")
    lines.append(f"Target concentration: {protocol.target_concentration_ng_ul:.1f} ng/µL")
    lines.append(f"Dilution factor: {protocol.dilution_factor:.1f}x")
    lines.append("")
    lines.append("STEPS:")
    lines.append("-" * 60)

    for step in protocol.steps:
        if step.volume_ul > 0:
            line = f"{step.step_number}. {step.action}: {step.volume_ul:.2f} µL {step.component}"
        else:
            line = f"{step.step_number}. {step.action}"

        if step.notes:
            line += f"\n   ({step.notes})"
        lines.append(line)

    lines.append("-" * 60)
    lines.append(f"Final volume: {protocol.final_volume_ul:.2f} µL at {protocol.target_concentration_ng_ul:.1f} ng/µL")

    if protocol.warning:
        lines.append("")
        lines.append(f"⚠ WARNING: {protocol.warning}")

    return "\n".join(lines)
