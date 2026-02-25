"""Volume intervention logic for handling low DNA volumes and well capacity issues."""
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum

from .constants import (
    MIN_PIPETTABLE_VOLUME_UL,
    WARN_PIPETTABLE_VOLUME_UL,
    TARGET_DNA_VOLUME_UL,
    MIN_DILUTION_STOCK_UL,
    MIN_DILUTED_CONCENTRATION_NG_UL,
    PlateFormat,
    PLATE_CONSTRAINTS,
)
# Renamed from dna_dilution.py per PRD
from .dilution_calculator import calculate_dilution_for_target_dna_volume


class InterventionType(Enum):
    """Type of volume intervention."""
    NONE = "none"
    WARNING = "warning"
    DILUTION = "dilution"
    SCALE_UP = "scale_up"
    SPLIT_WELLS = "split_wells"


@dataclass
class DilutionOption:
    """Dilution intervention option."""
    target_concentration_ng_ul: float
    stock_volume_ul: float
    diluent_volume_ul: float
    total_diluted_volume_ul: float
    dna_stock_consumed_ul: float
    new_dna_volume_ul: float
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)


@dataclass
class ScaleUpOption:
    """Reaction scale-up intervention option."""
    original_reaction_volume_ul: float
    new_reaction_volume_ul: float
    scale_factor: float
    dna_stock_consumed_ul: float
    new_dna_volume_ul: float
    wells_needed: int
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)


@dataclass
class SplitWellOption:
    """Well splitting intervention option."""
    original_volume_ul: float
    wells_needed: int
    volume_per_well_ul: float
    note: str


@dataclass
class VolumeIntervention:
    """Complete volume intervention recommendation."""
    required: bool
    intervention_type: InterventionType
    warning: Optional[str] = None
    dilution_option: Optional[DilutionOption] = None
    scaleup_option: Optional[ScaleUpOption] = None
    split_option: Optional[SplitWellOption] = None
    recommended: Optional[str] = None  # 'dilution', 'scaleup', or 'split'
    explanation: Optional[str] = None


def recommend_dna_volume_intervention(
    dna_volume_ul: float,
    reaction_volume_ul: float,
    dna_stock_ng_ul: float,
    dna_stock_available_ul: float = 100.0,
    dna_mass_ug: float = 20.0,
    plate_format: PlateFormat = PlateFormat.WELL_384,
) -> VolumeIntervention:
    """
    Recommend intervention when DNA volume is below pipetting threshold.

    Args:
        dna_volume_ul: Calculated DNA volume in µL
        reaction_volume_ul: Total reaction volume in µL
        dna_stock_ng_ul: DNA stock concentration in ng/µL
        dna_stock_available_ul: Available DNA stock in µL
        dna_mass_ug: DNA mass per reaction in µg
        plate_format: Plate format for constraints

    Returns:
        VolumeIntervention with recommended options
    """
    # No intervention needed
    if dna_volume_ul >= WARN_PIPETTABLE_VOLUME_UL:
        return VolumeIntervention(
            required=False,
            intervention_type=InterventionType.NONE,
        )

    # Warning only (0.5-1.0 µL)
    if dna_volume_ul >= MIN_PIPETTABLE_VOLUME_UL:
        return VolumeIntervention(
            required=False,
            intervention_type=InterventionType.WARNING,
            warning=f"DNA volume {dna_volume_ul:.2f} µL may reduce pipetting accuracy",
        )

    # Intervention required (< 0.5 µL)
    constraints = PLATE_CONSTRAINTS[plate_format]

    # Option 1: DNA Dilution
    # Target: comfortable pipetting margin
    dilution_factor = TARGET_DNA_VOLUME_UL / dna_volume_ul
    diluted_concentration = dna_stock_ng_ul / dilution_factor
    dilution_stock_needed = MIN_DILUTION_STOCK_UL
    dilution_water_needed = dilution_stock_needed * (dilution_factor - 1)
    total_diluted_volume = dilution_stock_needed * dilution_factor

    dilution_option = DilutionOption(
        target_concentration_ng_ul=diluted_concentration,
        stock_volume_ul=dilution_stock_needed,
        diluent_volume_ul=dilution_water_needed,
        total_diluted_volume_ul=total_diluted_volume,
        dna_stock_consumed_ul=dilution_stock_needed,
        new_dna_volume_ul=TARGET_DNA_VOLUME_UL,
        pros=["Maintains standard reaction volume", "Established protocol"],
        cons=[f"Uses {dilution_stock_needed:.0f} µL stock (vs {dna_volume_ul:.2f} µL undiluted)"],
    )

    # Option 2: Reaction Scale-Up
    # Scale to minimum well volume or target DNA volume, whichever is larger
    scale_for_min_well = constraints.min_well_volume_ul / reaction_volume_ul
    scale_for_target_dna = TARGET_DNA_VOLUME_UL / dna_volume_ul
    scale_factor = max(scale_for_min_well, scale_for_target_dna)

    new_reaction_volume = reaction_volume_ul * scale_factor
    new_dna_volume = dna_volume_ul * scale_factor
    dna_consumed_scaleup = new_dna_volume

    # Calculate wells needed for scaled reaction
    from math import ceil
    wells_needed = 1
    if new_reaction_volume > constraints.max_well_volume_ul:
        wells_needed = ceil(new_reaction_volume / constraints.max_well_volume_ul)

    scaleup_option = ScaleUpOption(
        original_reaction_volume_ul=reaction_volume_ul,
        new_reaction_volume_ul=new_reaction_volume,
        scale_factor=scale_factor,
        dna_stock_consumed_ul=dna_consumed_scaleup,
        new_dna_volume_ul=new_dna_volume,
        wells_needed=wells_needed,
        pros=["More efficient DNA usage", "Larger volume may improve signal"],
        cons=[
            f"Changes reaction volume to {new_reaction_volume:.0f} µL",
            "All other components scale proportionally",
        ],
    )

    if wells_needed > 1:
        scaleup_option.cons.append(f"Requires {wells_needed} wells per reaction (split)")

    # Determine recommended option
    if diluted_concentration < MIN_DILUTED_CONCENTRATION_NG_UL:
        # Too dilute, stability concerns
        recommended = 'scaleup'
        explanation = (
            f"Dilution would result in very low concentration "
            f"({diluted_concentration:.1f} ng/µL < {MIN_DILUTED_CONCENTRATION_NG_UL} ng/µL). "
            "Scale-up recommended for DNA stability."
        )
    elif dna_stock_available_ul < dilution_stock_needed * 2:
        # Limited stock
        recommended = 'scaleup'
        explanation = (
            f"Limited DNA stock available ({dna_stock_available_ul:.0f} µL). "
            "Scale-up uses DNA more efficiently."
        )
    elif wells_needed > 4:
        # Too many wells for scale-up
        recommended = 'dilution'
        explanation = (
            f"Scale-up would require {wells_needed} wells per reaction. "
            "Dilution maintains simpler plate layout."
        )
    else:
        # Default to dilution
        recommended = 'dilution'
        explanation = (
            "Dilution is recommended as it maintains standard reaction volume "
            "and doesn't require well splitting."
        )

    return VolumeIntervention(
        required=True,
        intervention_type=InterventionType.DILUTION if recommended == 'dilution' else InterventionType.SCALE_UP,
        dilution_option=dilution_option,
        scaleup_option=scaleup_option,
        recommended=recommended,
        explanation=explanation,
    )


def recommend_well_volume_intervention(
    reaction_volume_ul: float,
    plate_format: PlateFormat = PlateFormat.WELL_384,
) -> VolumeIntervention:
    """
    Recommend intervention when reaction volume exceeds well capacity.

    Args:
        reaction_volume_ul: Total reaction volume in µL
        plate_format: Plate format for constraints

    Returns:
        VolumeIntervention with split recommendation if needed
    """
    constraints = PLATE_CONSTRAINTS[plate_format]

    if reaction_volume_ul <= constraints.max_well_volume_ul:
        if reaction_volume_ul < constraints.min_well_volume_ul:
            return VolumeIntervention(
                required=True,
                intervention_type=InterventionType.WARNING,
                warning=(
                    f"Reaction volume {reaction_volume_ul:.1f} µL is below "
                    f"minimum {constraints.min_well_volume_ul} µL for {plate_format.value}-well plates"
                ),
            )
        return VolumeIntervention(
            required=False,
            intervention_type=InterventionType.NONE,
        )

    # Split required
    from math import ceil
    wells_needed = ceil(reaction_volume_ul / constraints.max_well_volume_ul)
    volume_per_well = reaction_volume_ul / wells_needed

    split_option = SplitWellOption(
        original_volume_ul=reaction_volume_ul,
        wells_needed=wells_needed,
        volume_per_well_ul=volume_per_well,
        note=f"Split {reaction_volume_ul:.0f} µL across {wells_needed} wells",
    )

    return VolumeIntervention(
        required=True,
        intervention_type=InterventionType.SPLIT_WELLS,
        split_option=split_option,
        recommended='split',
        explanation=(
            f"Reaction volume {reaction_volume_ul:.1f} µL exceeds "
            f"maximum well volume {constraints.max_well_volume_ul} µL. "
            f"Split across {wells_needed} wells at {volume_per_well:.1f} µL each."
        ),
    )


def validate_all_volumes(
    constructs: List[dict],
    reaction_volume_ul: float,
    dna_mass_ug: float,
    plate_format: PlateFormat = PlateFormat.WELL_384,
) -> List[VolumeIntervention]:
    """
    Validate volumes for all constructs and return interventions needed.

    Args:
        constructs: List of construct dicts with 'name', 'stock_concentration_ng_ul', 'stock_available_ul'
        reaction_volume_ul: Total reaction volume
        dna_mass_ug: DNA mass per reaction
        plate_format: Plate format

    Returns:
        List of VolumeIntervention for each construct
    """
    # Renamed from volume_calculator.py per PRD
    from .reaction_calculator import calculate_dna_volume

    interventions = []

    for construct in constructs:
        stock_conc = construct.get('stock_concentration_ng_ul', 100.0)
        stock_available = construct.get('stock_available_ul', 100.0)

        dna_vol = calculate_dna_volume(dna_mass_ug, stock_conc)

        intervention = recommend_dna_volume_intervention(
            dna_volume_ul=dna_vol,
            reaction_volume_ul=reaction_volume_ul,
            dna_stock_ng_ul=stock_conc,
            dna_stock_available_ul=stock_available,
            dna_mass_ug=dna_mass_ug,
            plate_format=plate_format,
        )

        interventions.append(intervention)

    return interventions


def format_intervention(intervention: VolumeIntervention, construct_name: str = "") -> str:
    """
    Format a volume intervention as text.

    Args:
        intervention: VolumeIntervention to format
        construct_name: Name of construct for context

    Returns:
        Formatted text string
    """
    lines = []

    if construct_name:
        lines.append(f"VOLUME INTERVENTION: {construct_name}")
    else:
        lines.append("VOLUME INTERVENTION")
    lines.append("=" * 60)

    if not intervention.required:
        if intervention.warning:
            lines.append(f"⚠ {intervention.warning}")
        else:
            lines.append("✓ No intervention required")
        return "\n".join(lines)

    if intervention.dilution_option:
        opt = intervention.dilution_option
        marker = "★ " if intervention.recommended == 'dilution' else "  "
        lines.append(f"{marker}OPTION 1: DILUTE DNA STOCK")
        lines.append("-" * 60)
        lines.append(f"  Target concentration: {opt.target_concentration_ng_ul:.1f} ng/µL")
        lines.append(f"  Take {opt.stock_volume_ul:.1f} µL stock DNA")
        lines.append(f"  Add {opt.diluent_volume_ul:.1f} µL nuclease-free water")
        lines.append(f"  Final volume: {opt.total_diluted_volume_ul:.1f} µL")
        lines.append(f"  New DNA volume per reaction: {opt.new_dna_volume_ul:.1f} µL")
        lines.append("")
        for pro in opt.pros:
            lines.append(f"  ✓ {pro}")
        for con in opt.cons:
            lines.append(f"  ✗ {con}")
        lines.append("")

    if intervention.scaleup_option:
        opt = intervention.scaleup_option
        marker = "★ " if intervention.recommended == 'scaleup' else "  "
        lines.append(f"{marker}OPTION 2: SCALE UP REACTION")
        lines.append("-" * 60)
        lines.append(f"  Scale factor: {opt.scale_factor:.2f}x")
        lines.append(f"  New reaction volume: {opt.new_reaction_volume_ul:.1f} µL")
        lines.append(f"  New DNA volume: {opt.new_dna_volume_ul:.1f} µL")
        if opt.wells_needed > 1:
            lines.append(f"  Wells needed: {opt.wells_needed}")
        lines.append("")
        for pro in opt.pros:
            lines.append(f"  ✓ {pro}")
        for con in opt.cons:
            lines.append(f"  ✗ {con}")
        lines.append("")

    if intervention.split_option:
        opt = intervention.split_option
        lines.append("REQUIRED: SPLIT WELLS")
        lines.append("-" * 60)
        lines.append(f"  {opt.note}")
        lines.append(f"  Volume per well: {opt.volume_per_well_ul:.1f} µL")
        lines.append("")

    if intervention.explanation:
        lines.append("RECOMMENDATION:")
        lines.append(f"  {intervention.explanation}")

    return "\n".join(lines)
