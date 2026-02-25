"""Master mix volume calculations for IVT reactions."""
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from .constants import (
    DEFAULT_OVERAGE_PERCENT,
    MIN_PIPETTABLE_VOLUME_UL,
    WARN_PIPETTABLE_VOLUME_UL,
    MAX_LIGAND_VOLUME_FRACTION,
)
# Renamed from volume_calculator.py per PRD
from .reaction_calculator import (
    LigandConfig,
    SingleReactionVolumes,
    ComponentVolume,
    DNAAddition,
    calculate_single_reaction_volumes,
    calculate_dna_additions,
    round_volume_up,
)


@dataclass
class MasterMixComponent:
    """A component in the master mix with scaled volume."""
    name: str
    order: int
    single_reaction_volume_ul: float
    master_mix_volume_ul: float
    stock_concentration: float
    stock_unit: str
    final_concentration: float
    final_unit: str


@dataclass
class MasterMixCalculation:
    """Complete master mix calculation result."""
    n_reactions: int
    overage_factor: float
    n_effective: float  # n_reactions × overage_factor
    single_reaction: SingleReactionVolumes
    components: List[MasterMixComponent] = field(default_factory=list)
    total_master_mix_volume_ul: float = 0.0
    master_mix_per_tube_ul: float = 0.0  # Volume to aliquot per tube
    dna_additions: List[DNAAddition] = field(default_factory=list)
    max_dna_volume_ul: float = 0.0
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    # Ligand workflow fields
    is_ligand_workflow: bool = False
    ligand_volume_per_rxn_ul: float = 0.0
    ligand_config: Optional[LigandConfig] = None
    # Precise (unrounded) values for validation tab
    precise_single_reaction: Optional[SingleReactionVolumes] = None
    precise_water_volume_ul: float = 0.0


def calculate_master_mix(
    n_reactions: int,
    dna_mass_ug: float = 20.0,
    overage_percent: float = DEFAULT_OVERAGE_PERCENT,
    constructs: Optional[List[Dict]] = None,
    negative_template_count: int = 3,
    negative_dye_count: int = 0,
    include_dye: bool = True,
    gtp_stock_mm: float = 467.3,
    gtp_final_mm: float = 6.0,
    atp_stock_mm: float = 364.8,
    atp_final_mm: float = 5.0,
    ctp_stock_mm: float = 343.3,
    ctp_final_mm: float = 5.0,
    utp_stock_mm: float = 407.8,
    utp_final_mm: float = 5.0,
    dfhbi_stock_um: float = 40000.0,
    dfhbi_final_um: float = 100.0,
    reaction_volume_ul: Optional[float] = None,
    target_dna_nM: Optional[float] = None,
    ligand_config: Optional[LigandConfig] = None,
) -> MasterMixCalculation:
    """
    Calculate master mix volumes for multiple reactions.

    The master mix contains all components EXCEPT DNA template, which is
    added per-tube. Water is also adjusted per-tube based on DNA volume.

    Master mix formula:
        N_effective = N × (1 + overage_percent/100)
        V_component_MM = V_component_single × N_effective

    Args:
        n_reactions: Number of reactions (tubes)
        dna_mass_ug: DNA mass per reaction in µg
        overage_percent: Extra volume percentage (default 20%)
        constructs: List of construct dicts for DNA calculations
        negative_template_count: Number of -Template controls
        negative_dye_count: Number of -DFHBI controls
        include_dye: Whether to include DFHBI in master mix
        *_stock_mm/*_final_mm: NTP stock/final concentrations
        dfhbi_stock_um/dfhbi_final_um: DFHBI concentrations
        reaction_volume_ul: Optional explicit reaction volume in µL

    Returns:
        MasterMixCalculation with all volumes
    """
    overage_factor = 1.0 + (overage_percent / 100.0)
    n_effective = n_reactions * overage_factor

    # Calculate single reaction volumes (Rounded for display)
    single = calculate_single_reaction_volumes(
        dna_mass_ug=dna_mass_ug,
        gtp_stock_mm=gtp_stock_mm,
        gtp_final_mm=gtp_final_mm,
        atp_stock_mm=atp_stock_mm,
        atp_final_mm=atp_final_mm,
        ctp_stock_mm=ctp_stock_mm,
        ctp_final_mm=ctp_final_mm,
        utp_stock_mm=utp_stock_mm,
        utp_final_mm=utp_final_mm,
        dfhbi_stock_um=dfhbi_stock_um,
        dfhbi_final_um=dfhbi_final_um,
        include_dye=include_dye,
        reaction_volume_ul=reaction_volume_ul,
        round_result=True, # Display rounded values
    )

    # Calculate precise single reaction volumes (Unrounded for accurate scaling)
    precise_single = calculate_single_reaction_volumes(
        dna_mass_ug=dna_mass_ug,
        gtp_stock_mm=gtp_stock_mm,
        gtp_final_mm=gtp_final_mm,
        atp_stock_mm=atp_stock_mm,
        atp_final_mm=atp_final_mm,
        ctp_stock_mm=ctp_stock_mm,
        ctp_final_mm=ctp_final_mm,
        utp_stock_mm=utp_stock_mm,
        utp_final_mm=utp_final_mm,
        dfhbi_stock_um=dfhbi_stock_um,
        dfhbi_final_um=dfhbi_final_um,
        include_dye=include_dye,
        reaction_volume_ul=reaction_volume_ul,
        round_result=False, # Use raw values for calculation
    )

    result = MasterMixCalculation(
        n_reactions=n_reactions,
        overage_factor=overage_factor,
        n_effective=n_effective,
        single_reaction=single,
        precise_single_reaction=precise_single,
    )

    # Calculate ligand volume if enabled
    ligand_vol_per_rxn = 0.0
    is_ligand = ligand_config is not None and ligand_config.enabled
    if is_ligand and reaction_volume_ul:
        v_rxn = reaction_volume_ul if reaction_volume_ul else single.reaction_volume_ul
        ligand_vol_per_rxn = round_volume_up(
            (ligand_config.final_concentration_uM * v_rxn)
            / ligand_config.stock_concentration_uM
        )
        # Validate ligand volume
        if ligand_vol_per_rxn > MAX_LIGAND_VOLUME_FRACTION * v_rxn:
            result.errors.append(
                f"Ligand volume {ligand_vol_per_rxn:.1f} µL exceeds "
                f"{MAX_LIGAND_VOLUME_FRACTION * 100:.0f}% of reaction volume "
                f"({v_rxn:.1f} µL). Increase stock concentration."
            )
            result.is_valid = False
        elif ligand_vol_per_rxn < MIN_PIPETTABLE_VOLUME_UL:
            result.errors.append(
                f"Ligand volume {ligand_vol_per_rxn:.3f} µL below pipetting threshold "
                f"({MIN_PIPETTABLE_VOLUME_UL} µL). Dilute stock to increase volume."
            )
            result.is_valid = False
        elif ligand_vol_per_rxn < WARN_PIPETTABLE_VOLUME_UL:
            diluted_stock = ligand_config.stock_concentration_uM / 2
            result.warnings.append(
                f"Ligand volume {ligand_vol_per_rxn:.1f} µL may reduce accuracy. "
                f"Consider diluting stock to {diluted_stock:.0f} µM."
            )
        result.is_ligand_workflow = True
        result.ligand_volume_per_rxn_ul = ligand_vol_per_rxn
        result.ligand_config = ligand_config

    # Calculate DNA additions if constructs provided
    max_dna_volume = 0.0
    if constructs:
        dna_additions, max_dna_volume = calculate_dna_additions(
            dna_mass_ug=dna_mass_ug,
            constructs=constructs,
            negative_template_count=negative_template_count,
            negative_dye_count=negative_dye_count,
            reaction_volume_ul=single.reaction_volume_ul,
            target_dna_nM=target_dna_nM,
            ligand_config=ligand_config,
        )
        result.dna_additions = dna_additions
        result.max_dna_volume_ul = max_dna_volume

    # Scale up component volumes for master mix
    mm_components = []
    total_mm_volume = 0.0

    # Map precise components by name for easy lookup
    precise_map = {c.name: c for c in precise_single.components}

    for comp in single.components:
        # Use precise volume for scaling, then round the result
        precise_comp = precise_map.get(comp.name)
        if precise_comp:
            precise_vol = precise_comp.volume_ul
        else:
            precise_vol = comp.volume_ul # Fallback
            
        mm_vol = round_volume_up(precise_vol * n_effective)
        
        mm_components.append(MasterMixComponent(
            name=comp.name,
            order=comp.order,
            single_reaction_volume_ul=precise_vol,     # Precise (unrounded) per-rxn
            master_mix_volume_ul=mm_vol,              # Precise total
            stock_concentration=comp.stock_concentration,
            stock_unit=comp.stock_unit,
            final_concentration=comp.final_concentration,
            final_unit=comp.final_unit,
        ))
        total_mm_volume += mm_vol

    # Calculate water volume
    # Water = V_rxn - (sum of all components) - V_DNA_ref
    # But water goes in master mix minus the DNA volume reference
    # Calculate water volume
    # Water = V_rxn - (sum of all components) - V_DNA_ref
    # Usage precise values for calculation
    precise_total_component_volume = sum(c.volume_ul for c in precise_single.components)
    
    # We also need the precise max_dna_volume?
    # calculate_dna_additions uses round_volume_up internally.
    # Ideally we would have a precise version of that too, but for now let's assume DNA volume is fixed by the rounded pipetting step since it's added per tube.
    # Wait, if DNA is added per tube, its volume IS the rounded volume (user pipettes it).
    # So max_dna_volume (which determines the water hole left for it) should stay rounded.
    
    # Subtract ligand volume from water budget for +Lig reactions
    # (ligand is added post-split, so water in base MM must account for it)
    ligand_water_deduction = ligand_vol_per_rxn if is_ligand else 0.0
    precise_water_volume_single = (
        precise_single.reaction_volume_ul
        - precise_total_component_volume
        - max_dna_volume
        - ligand_water_deduction
    )
    water_mm_volume = round_volume_up(precise_water_volume_single * n_effective)

    result.precise_water_volume_ul = precise_water_volume_single

    if precise_water_volume_single < 0:
        result.errors.append(
            f"Negative water volume ({precise_water_volume_single:.1f} µL): "
            "component volumes exceed reaction volume"
        )
        result.is_valid = False
    else:
        # Add water as first component
        mm_components.insert(0, MasterMixComponent(
            name="Nuclease-free water",
            order=1,
            single_reaction_volume_ul=precise_water_volume_single,  # Precise (unrounded) per-rxn
            master_mix_volume_ul=water_mm_volume,                  # Precise total
            stock_concentration=0.0,
            stock_unit="",
            final_concentration=0.0,
            final_unit="",
        ))
        total_mm_volume += water_mm_volume

    # Sort by order
    mm_components.sort(key=lambda c: c.order)

    # Validate master mix component volumes
    for comp in mm_components:
        if comp.master_mix_volume_ul > 0.000001:  # Only check non-zero volumes (with epsilon)
            if comp.master_mix_volume_ul < MIN_PIPETTABLE_VOLUME_UL:
                error_msg = f"{comp.name}: Master Mix volume {comp.master_mix_volume_ul:.3f} µL below pipetting threshold"
                result.errors.append(error_msg)
                result.is_valid = False
            elif comp.master_mix_volume_ul < WARN_PIPETTABLE_VOLUME_UL:
                warn_msg = f"{comp.name}: Master Mix volume {comp.master_mix_volume_ul:.3f} µL may reduce accuracy"
                result.warnings.append(warn_msg)

    result.components = mm_components
    result.total_master_mix_volume_ul = total_mm_volume
    result.master_mix_per_tube_ul = single.reaction_volume_ul - max_dna_volume

    # Propagate errors and warnings from single reaction
    result.errors.extend(single.errors)
    result.warnings.extend(single.warnings)
    result.is_valid = result.is_valid and single.is_valid

    # Add DNA-related warnings
    for addition in result.dna_additions:
        if addition.warning:
            if addition.is_valid:
                result.warnings.append(f"{addition.construct_name}: {addition.warning}")
            else:
                result.errors.append(f"{addition.construct_name}: {addition.warning}")
                result.is_valid = False

    return result


def calculate_total_wells(
    n_constructs: int,
    replicates_per_construct: int,
    negative_template_count: int = 3,
    negative_dye_count: int = 0,
    ligand_multiplier: int = 1,
) -> int:
    """
    Calculate total number of wells needed.

    Args:
        n_constructs: Number of DNA templates (including anchors)
        replicates_per_construct: Replicates per construct
        negative_template_count: -Template control wells
        negative_dye_count: -DFHBI control wells
        ligand_multiplier: 2 when ligand conditions enabled, 1 otherwise

    Returns:
        Total well count
    """
    construct_wells = n_constructs * replicates_per_construct
    control_wells = negative_template_count + negative_dye_count
    return (construct_wells + control_wells) * ligand_multiplier


def calculate_total_reactions(
    constructs: List[Dict],
    negative_template_count: int = 3,
    negative_dye_count: int = 0,
    ligand_multiplier: int = 1,
) -> int:
    """
    Calculate total number of reactions from construct list.

    Args:
        constructs: List of construct dicts with 'replicates' key
        negative_template_count: -Template control wells
        negative_dye_count: -DFHBI control wells
        ligand_multiplier: 2 when ligand conditions enabled, 1 otherwise

    Returns:
        Total reaction count
    """
    construct_reactions = sum(c.get('replicates', 4) for c in constructs)
    control_reactions = negative_template_count + negative_dye_count
    return (construct_reactions + control_reactions) * ligand_multiplier


def format_master_mix_table(mm: MasterMixCalculation) -> str:
    """
    Format master mix calculation as a text table.

    Args:
        mm: MasterMixCalculation result

    Returns:
        Formatted table string
    """
    lines = []
    lines.append("=" * 80)
    lines.append("MASTER MIX CALCULATION")
    lines.append("=" * 80)
    lines.append(f"Number of reactions: {mm.n_reactions}")
    lines.append(f"Overage: {(mm.overage_factor - 1) * 100:.0f}%")
    lines.append(f"Effective reactions: {mm.n_effective:.1f}")
    lines.append(f"Reaction volume: {mm.single_reaction.reaction_volume_ul:.1f} µL")
    lines.append("")

    lines.append("-" * 80)
    lines.append(f"{'Component':<25} {'Single (µL)':<15} {'Master Mix (µL)':<20}")
    lines.append("-" * 80)

    for comp in mm.components:
        lines.append(
            f"{comp.name:<25} {comp.single_reaction_volume_ul:>12.2f}   "
            f"{comp.master_mix_volume_ul:>15.1f}"
        )

    lines.append("-" * 80)
    lines.append(
        f"{'Total':<25} {mm.master_mix_per_tube_ul + mm.max_dna_volume_ul:>12.2f}   "
        f"{mm.total_master_mix_volume_ul:>15.1f}"
    )
    lines.append("")

    if mm.dna_additions:
        lines.append("DNA ADDITIONS (per tube)")
        lines.append("-" * 80)
        lines.append(
            f"{'Construct':<25} {'Stock (ng/µL)':<15} {'DNA (µL)':<12} "
            f"{'Water (µL)':<12} {'Total (µL)':<12}"
        )
        lines.append("-" * 80)

        for addition in mm.dna_additions:
            if addition.is_negative_control:
                stock_str = "-"
                dna_str = "-"
            else:
                stock_str = f"{addition.stock_concentration_ng_ul:.1f}"
                dna_str = f"{addition.dna_volume_ul:.1f}"

            lines.append(
                f"{addition.construct_name:<25} {stock_str:>12}   "
                f"{dna_str:>10}   {addition.water_adjustment_ul:>10.1f}   "
                f"{addition.total_addition_ul:>10.1f}"
            )

        lines.append("-" * 80)

    if mm.warnings:
        lines.append("")
        lines.append("WARNINGS:")
        for warning in mm.warnings:
            lines.append(f"  ⚠ {warning}")

    if mm.errors:
        lines.append("")
        lines.append("ERRORS:")
        for error in mm.errors:
            lines.append(f"  ✗ {error}")

    return "\n".join(lines)
