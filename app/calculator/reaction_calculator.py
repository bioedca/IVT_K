"""Core volume calculation functions for IVT reactions."""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from math import ceil

from app.models.enums import LigandCondition

from .constants import (
    STANDARD_COMPONENTS,
    DNA_COMPONENT_ORDER,
    DNA_MASS_TO_VOLUME_FACTOR,
    DEFAULT_DNA_MASS_UG,
    MIN_PIPETTABLE_VOLUME_UL,
    WARN_PIPETTABLE_VOLUME_UL,
    AVG_BP_MOLECULAR_WEIGHT,
    TARGET_DNA_CONCENTRATION_NM,
    MAX_LIGAND_VOLUME_FRACTION,
    PlateFormat,
    PLATE_CONSTRAINTS,
)
from .dna_converter import DNAConcentrationConverter


@dataclass
class LigandConfig:
    """Configuration for ligand conditions in riboswitch experiments."""
    enabled: bool = False
    stock_concentration_uM: float = 1000.0
    final_concentration_uM: float = 100.0


@dataclass
class ComponentVolume:
    """Calculated volume for a single reaction component."""
    name: str
    order: int
    stock_concentration: float
    stock_unit: str
    final_concentration: float
    final_unit: str
    volume_ul: float
    is_valid: bool = True
    warning: Optional[str] = None


@dataclass
class DNAAddition:
    """Calculated DNA addition for a single construct."""
    construct_name: str
    construct_id: Optional[int]
    stock_concentration_ng_ul: float
    dna_volume_ul: float
    water_adjustment_ul: float
    total_addition_ul: float
    replicates: int = 1  # Number of wells for this construct
    is_negative_control: bool = False
    negative_control_type: Optional[str] = None
    source_construct_name: Optional[str] = None
    is_valid: bool = True
    requires_dilution: bool = False
    warning: Optional[str] = None
    stock_concentration_nM: Optional[float] = None
    plasmid_size_bp: Optional[int] = None
    achieved_nM: Optional[float] = None
    ligand_condition: Optional[LigandCondition] = None


@dataclass
class SingleReactionVolumes:
    """All calculated volumes for a single reaction."""
    reaction_volume_ul: float
    dna_mass_ug: float
    components: List[ComponentVolume] = field(default_factory=list)
    water_volume_ul: float = 0.0
    total_volume_ul: float = 0.0
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class SplitCalculation:
    """Result of split well calculation."""
    wells_needed: int
    volume_per_well: List[float]
    note: Optional[str] = None


def round_volume_up(volume_ul: float, precision: float = 0.1) -> float:
    """
    Round a volume UP to the specified precision for pipetting.
    
    This ensures we never underpipette, maintaining concentration integrity.
    Negative volumes are returned as 0.0.
    
    Args:
        volume_ul: Volume in µL
        precision: Decimal precision (default 0.1 µL)
    
    Returns:
        Volume rounded up to precision
    
    Examples:
        round_volume_up(1.23) -> 1.3
        round_volume_up(1.20) -> 1.2
        round_volume_up(1.01) -> 1.1
    """
    if volume_ul <= 0:
        return 0.0
    # Multiply by 1/precision, ceil, then divide back
    factor = 1.0 / precision
    return ceil(volume_ul * factor) / factor


def calculate_reaction_volume(dna_mass_ug: float = DEFAULT_DNA_MASS_UG) -> float:
    """
    Calculate total reaction volume from DNA mass.

    V_rxn = m_DNA × 10 (µL)

    Args:
        dna_mass_ug: DNA mass in micrograms

    Returns:
        Total reaction volume in µL
    """
    return dna_mass_ug * DNA_MASS_TO_VOLUME_FACTOR


def calculate_buffer_volume(reaction_volume_ul: float, stock_x: float = 10.0, final_x: float = 1.0) -> float:
    """
    Calculate volume of reaction buffer.

    V_buffer = V_rxn × (final_x / stock_x)

    Args:
        reaction_volume_ul: Total reaction volume in µL
        stock_x: Stock buffer concentration (default 10X)
        final_x: Final buffer concentration (default 1X)

    Returns:
        Buffer volume in µL
    """
    return reaction_volume_ul * (final_x / stock_x)


def calculate_component_volume(
    reaction_volume_ul: float,
    final_concentration: float,
    stock_concentration: float,
) -> float:
    """
    Calculate volume for a standard concentration-based component.

    V = (C_final × V_rxn) / C_stock

    Args:
        reaction_volume_ul: Total reaction volume in µL
        final_concentration: Desired final concentration
        stock_concentration: Stock concentration

    Returns:
        Component volume in µL
    """
    if stock_concentration == 0:
        return 0.0
    return (final_concentration * reaction_volume_ul) / stock_concentration


def calculate_dna_volume(
    dna_mass_ug: float,
    stock_concentration_ng_ul: float,
) -> float:
    """
    Calculate DNA template volume.

    V_DNA = m_DNA / (C_DNA / 1000)

    where m_DNA is in µg and C_DNA is in ng/µL

    Args:
        dna_mass_ug: DNA mass in micrograms
        stock_concentration_ng_ul: DNA stock concentration in ng/µL

    Returns:
        DNA volume in µL
    """
    if stock_concentration_ng_ul == 0:
        return 0.0
    # Convert µg to ng: 1 µg = 1000 ng
    dna_mass_ng = dna_mass_ug * 1000
    return dna_mass_ng / stock_concentration_ng_ul


def ng_ul_to_nM(stock_ng_ul: float, plasmid_size_bp: int) -> float:
    """Convert ng/µL to nM. Delegates to :class:`DNAConcentrationConverter`."""
    return DNAConcentrationConverter.ng_ul_to_nM(stock_ng_ul, plasmid_size_bp)


def calculate_dna_volume_nM(
    target_nM: float,
    stock_nM: float,
    reaction_volume_ul: float,
) -> float:
    """Calculate DNA volume for target nM. Delegates to :class:`DNAConcentrationConverter`."""
    return DNAConcentrationConverter.nM_to_volume(target_nM, stock_nM, reaction_volume_ul)


def calculate_enzyme_volume(
    reaction_volume_ul: float,
    factor: float,
) -> float:
    """
    Calculate enzyme volume using the standard formula.

    V = (V_rxn × factor) / 200

    Args:
        reaction_volume_ul: Total reaction volume in µL
        factor: Multiplication factor for the enzyme

    Returns:
        Enzyme volume in µL
    """
    return (reaction_volume_ul * factor) / 200


def calculate_single_reaction_volumes(
    dna_mass_ug: float = DEFAULT_DNA_MASS_UG,
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
    include_dye: bool = True,
    reaction_volume_ul: Optional[float] = None,
    round_result: bool = True,
) -> SingleReactionVolumes:
    """
    Calculate all component volumes for a single IVT reaction.

    This excludes DNA template which is calculated separately per construct.

    Args:
        dna_mass_ug: DNA mass in micrograms
        gtp_stock_mm: GTP stock concentration in mM
        gtp_final_mm: GTP final concentration in mM
        atp_stock_mm: ATP stock concentration in mM
        atp_final_mm: ATP final concentration in mM
        ctp_stock_mm: CTP stock concentration in mM
        ctp_final_mm: CTP final concentration in mM
        utp_stock_mm: UTP stock concentration in mM
        utp_final_mm: UTP final concentration in mM
        dfhbi_stock_um: DFHBI stock concentration in µM
        dfhbi_final_um: DFHBI final concentration in µM
        include_dye: Whether to include DFHBI dye
        reaction_volume_ul: Optional explicit reaction volume in µL
        round_result: Whether to round volumes for pipetting (True) or keep raw for calculation (False)

    Returns:
        SingleReactionVolumes with all calculated component volumes
    """
    # Use explicit volume if provided, otherwise calculate from DNA mass
    if reaction_volume_ul is not None:
        v_rxn = reaction_volume_ul
    else:
        v_rxn = calculate_reaction_volume(dna_mass_ug)

    result = SingleReactionVolumes(
        reaction_volume_ul=v_rxn,
        dna_mass_ug=dna_mass_ug,
    )
    errors = []
    warnings = []
    components = []

    def _maybe_round(vol: float) -> float:
        return round_volume_up(vol) if round_result else vol

    # 1. Reaction buffer (10X -> 1X)
    buffer_vol = _maybe_round(calculate_buffer_volume(v_rxn))
    components.append(ComponentVolume(
        name="10X Reaction buffer",
        order=2,
        stock_concentration=10.0,
        stock_unit="X",
        final_concentration=1.0,
        final_unit="X",
        volume_ul=buffer_vol,
    ))

    # 2. MgCl₂ (1M -> 10mM)
    mgcl2_vol = _maybe_round(calculate_component_volume(v_rxn, 10.0, 1000.0))
    components.append(ComponentVolume(
        name="MgCl₂",
        order=3,
        stock_concentration=1000.0,
        stock_unit="mM",
        final_concentration=10.0,
        final_unit="mM",
        volume_ul=mgcl2_vol,
    ))

    # 3. NTPs
    ntp_configs = [
        ("GTP", gtp_stock_mm, gtp_final_mm, 5),
        ("ATP", atp_stock_mm, atp_final_mm, 6),
        ("CTP", ctp_stock_mm, ctp_final_mm, 7),
        ("UTP", utp_stock_mm, utp_final_mm, 8),
    ]

    for name, stock, final, order in ntp_configs:
        vol = _maybe_round(calculate_component_volume(v_rxn, final, stock))
        comp = ComponentVolume(
            name=name,
            order=order,
            stock_concentration=stock,
            stock_unit="mM",
            final_concentration=final,
            final_unit="mM",
            volume_ul=vol,
        )
        components.append(comp)

    # 4. DFHBI dye (optional)
    if include_dye:
        dfhbi_vol = _maybe_round(calculate_component_volume(v_rxn, dfhbi_final_um, dfhbi_stock_um))
        comp = ComponentVolume(
            name="DFHBI dye",
            order=9,
            stock_concentration=dfhbi_stock_um,
            stock_unit="µM",
            final_concentration=dfhbi_final_um,
            final_unit="µM",
            volume_ul=dfhbi_vol,
        )
        components.append(comp)

    # 5. Enzymes
    # Pyrophosphatase: (V_rxn × 1.6) / 200
    ppi_vol = _maybe_round(calculate_enzyme_volume(v_rxn, 1.6))
    components.append(ComponentVolume(
        name="Pyrophosphatase",
        order=10,
        stock_concentration=0.1,
        stock_unit="U/µL",
        final_concentration=0.0008,
        final_unit="U/µL",
        volume_ul=ppi_vol,
    ))

    # RNAsin: (V_rxn × 0.8) / 200
    rnasin_vol = _maybe_round(calculate_enzyme_volume(v_rxn, 0.8))
    components.append(ComponentVolume(
        name="RNAsin",
        order=11,
        stock_concentration=40.0,
        stock_unit="U/µL",
        final_concentration=0.16,
        final_unit="U/µL",
        volume_ul=rnasin_vol,
    ))

    # T7 RNA Polymerase: (V_rxn × 0.4) / 200
    t7_vol = _maybe_round(calculate_enzyme_volume(v_rxn, 0.4))
    components.append(ComponentVolume(
        name="T7 RNA Polymerase",
        order=12,
        stock_concentration=1.0,
        stock_unit="U/µL",
        final_concentration=0.002,
        final_unit="U/µL",
        volume_ul=t7_vol,
    ))

    # Sort by order and calculate total (excluding DNA and water)
    components.sort(key=lambda c: c.order)
    non_water_total = sum(c.volume_ul for c in components)

    # Water will be calculated after DNA is known
    result.components = components
    result.errors = errors
    result.warnings = warnings
    result.is_valid = len(errors) == 0

    return result


def calculate_dna_additions(
    dna_mass_ug: float,
    constructs: List[Dict],
    negative_template_count: int = 3,
    negative_dye_count: int = 0,
    reaction_volume_ul: Optional[float] = None,
    target_dna_nM: Optional[float] = None,
    ligand_config: Optional[LigandConfig] = None,
) -> Tuple[List[DNAAddition], float]:
    """
    Calculate DNA additions for all constructs and determine reference DNA volume.

    When target_dna_nM is provided and constructs have plasmid_size_bp, uses nM-based
    targeting instead of mass-based targeting for biologically precise DNA concentrations.

    Args:
        dna_mass_ug: DNA mass in micrograms per reaction (fallback for mass-based)
        constructs: List of construct dicts with 'name', 'id', 'stock_concentration_ng_ul',
                    and optionally 'plasmid_size_bp'
        negative_template_count: Number of -Template negative control wells
        negative_dye_count: Number of -DFHBI negative control wells
        reaction_volume_ul: Total reaction volume in µL (required for nM path)
        target_dna_nM: Target final DNA concentration in nM (enables nM path)

    Returns:
        Tuple of (List of DNAAddition, max DNA volume for water adjustment reference)
    """
    additions = []
    max_dna_volume = 0.0

    # Determine if nM-based targeting is available
    use_nM = (
        target_dna_nM is not None
        and reaction_volume_ul is not None
    )

    # Calculate DNA volumes for each construct
    for construct in constructs:
        stock_conc = construct.get('stock_concentration_ng_ul', 100.0)
        plasmid_bp = construct.get('plasmid_size_bp')
        stock_nM = None
        achieved_nM = None

        if use_nM and plasmid_bp and plasmid_bp > 0:
            # nM-based path
            stock_nM = ng_ul_to_nM(stock_conc, plasmid_bp)
            raw_vol = calculate_dna_volume_nM(target_dna_nM, stock_nM, reaction_volume_ul)
            dna_vol = round_volume_up(raw_vol)
            # Compute achieved nM after rounding
            if stock_nM > 0 and reaction_volume_ul > 0:
                achieved_nM = (dna_vol * stock_nM) / reaction_volume_ul
        else:
            # Mass-based fallback
            dna_vol = round_volume_up(calculate_dna_volume(dna_mass_ug, stock_conc))

        if dna_vol > max_dna_volume:
            max_dna_volume = dna_vol

        addition = DNAAddition(
            construct_name=construct.get('name', 'Unknown'),
            construct_id=construct.get('id'),
            stock_concentration_ng_ul=stock_conc,
            dna_volume_ul=dna_vol,
            water_adjustment_ul=0.0,  # Will be calculated after
            total_addition_ul=0.0,  # Will be calculated after
            replicates=construct.get('replicates', 1),
            source_construct_name=construct.get('name', 'Unknown'),
            stock_concentration_nM=stock_nM,
            plasmid_size_bp=plasmid_bp,
            achieved_nM=achieved_nM,
        )

        # Validate DNA volume
        if dna_vol < MIN_PIPETTABLE_VOLUME_UL:
            addition.is_valid = False
            addition.warning = f"DNA volume {dna_vol:.3f} µL below pipetting threshold"
        elif dna_vol < WARN_PIPETTABLE_VOLUME_UL:
            addition.warning = f"DNA volume {dna_vol:.3f} µL may reduce accuracy"

        additions.append(addition)

    # Add negative template controls (no DNA)
    for i in range(negative_template_count):
        additions.append(DNAAddition(
            construct_name=f"-Template #{i+1}",
            construct_id=None,
            stock_concentration_ng_ul=0.0,
            dna_volume_ul=0.0,
            water_adjustment_ul=0.0,
            total_addition_ul=0.0,
            is_negative_control=True,
            negative_control_type="no_template",
            source_construct_name=None,
        ))

    # Find reporter construct (is_unregulated=True) for -DFHBI controls
    reporter_construct = next((c for c in constructs if c.get('is_unregulated')), None)

    # Add negative dye controls (Reporter DNA, but no DFHBI in MM)
    for i in range(negative_dye_count):
        stock_conc = 0.0
        dna_vol = 0.0
        stock_nM_ctrl = None
        plasmid_bp_ctrl = None
        achieved_nM_ctrl = None

        if reporter_construct:
            stock_conc = reporter_construct.get('stock_concentration_ng_ul', 100.0)
            plasmid_bp_ctrl = reporter_construct.get('plasmid_size_bp')

            if use_nM and plasmid_bp_ctrl and plasmid_bp_ctrl > 0:
                stock_nM_ctrl = ng_ul_to_nM(stock_conc, plasmid_bp_ctrl)
                raw_vol = calculate_dna_volume_nM(target_dna_nM, stock_nM_ctrl, reaction_volume_ul)
                dna_vol = round_volume_up(raw_vol)
                if stock_nM_ctrl > 0 and reaction_volume_ul > 0:
                    achieved_nM_ctrl = (dna_vol * stock_nM_ctrl) / reaction_volume_ul
            else:
                dna_vol = round_volume_up(calculate_dna_volume(dna_mass_ug, stock_conc))

        additions.append(DNAAddition(
            construct_name=f"-DFHBI #{i+1}",
            construct_id=None,
            stock_concentration_ng_ul=stock_conc,
            dna_volume_ul=dna_vol,
            water_adjustment_ul=0.0,
            total_addition_ul=0.0,
            is_negative_control=True,
            negative_control_type="no_dye",
            source_construct_name=reporter_construct.get('name') if reporter_construct else None,
            stock_concentration_nM=stock_nM_ctrl,
            plasmid_size_bp=plasmid_bp_ctrl,
            achieved_nM=achieved_nM_ctrl,
        ))

    # Calculate water adjustments to normalize total addition volume
    # V_water_adjust_i = V_DNA_ref - V_DNA_i
    # All volumes are rounded up to 0.1 µL for pipetting accuracy
    for addition in additions:
        if not addition.is_negative_control or addition.negative_control_type == 'no_dye':
            water_adj = max(0.0, max_dna_volume - addition.dna_volume_ul)
            addition.water_adjustment_ul = round(water_adj, 1)
        else:
            # -Template controls get full water volume
            addition.water_adjustment_ul = round_volume_up(max_dna_volume)

        # Validate water volume
        if 0 < addition.water_adjustment_ul < MIN_PIPETTABLE_VOLUME_UL:
            addition.requires_dilution = True
            warn_msg = f"Water volume {addition.water_adjustment_ul} µL below pipetting threshold"
            
            # Suggest standard dilutions (1:2, 1:4, 1:5, 1:10)
            # We want the DNA volume to INCREASE to at least Max Volume (Water=0)
            # NewVol = Mass / (Stock * Factor) = Vol / Factor
            # We need Vol / Factor >= MaxVol  =>  Factor <= Vol / MaxVol
            
            if max_dna_volume > 0 and addition.stock_concentration_ng_ul > 0:
                current_vol = (dna_mass_ug * 1000) / addition.stock_concentration_ng_ul
                limit_factor = current_vol / max_dna_volume
                
                # Standard factors: 1:2 (0.5), 1:4 (0.25), 1:5 (0.2), 1:10 (0.1)
                standard_factors = [0.5, 0.25, 0.2, 0.1]
                suggested_factor = None
                
                for factor in standard_factors:
                    if factor <= limit_factor:
                        suggested_factor = factor
                        break
                
                # If no standard factor works (limit is very small), fallback to calculated
                if suggested_factor:
                    new_conc = addition.stock_concentration_ng_ul * suggested_factor
                    ratio_map = {0.5: "1:2", 0.25: "1:4", 0.2: "1:5", 0.1: "1:10"}
                    ratio_str = ratio_map.get(suggested_factor, f"{suggested_factor*100:.0f}%")
                    warn_msg += f". Suggest diluting {ratio_str} (to {new_conc:.1f} ng/µL)"
                else:
                    target_conc = (dna_mass_ug * 1000) / max_dna_volume
                    dilution_pct = (target_conc / addition.stock_concentration_ng_ul) * 100
                    warn_msg += f". Suggest diluting to {target_conc:.1f} ng/µL ({dilution_pct:.1f}%)"
            
            if addition.warning:
                addition.warning += f"; {warn_msg}"
            else:
                addition.warning = warn_msg

        addition.total_addition_ul = round_volume_up(
            addition.dna_volume_ul + addition.water_adjustment_ul
        )

    # Ligand duplication: when enabled, duplicate every addition into +Lig/-Lig pairs
    if ligand_config and ligand_config.enabled and reaction_volume_ul:
        ligand_vol = round_volume_up(
            (ligand_config.final_concentration_uM * reaction_volume_ul)
            / ligand_config.stock_concentration_uM
        )
        duplicated = []
        for add in additions:
            import copy
            # +Lig version: water reduced by ligand volume (ligand replaces water)
            plus_lig = copy.copy(add)
            plus_lig.ligand_condition = LigandCondition.PLUS_LIG

            # -Lig version: gets extra water equal to ligand volume
            minus_lig = copy.copy(add)
            minus_lig.ligand_condition = LigandCondition.MINUS_LIG
            minus_lig.water_adjustment_ul = round(
                add.water_adjustment_ul + ligand_vol, 1
            )
            minus_lig.total_addition_ul = round_volume_up(
                minus_lig.dna_volume_ul + minus_lig.water_adjustment_ul
            )

            duplicated.append(plus_lig)
            duplicated.append(minus_lig)
        additions = duplicated

    return additions, max_dna_volume


def calculate_split_wells(
    reaction_volume_ul: float,
    max_well_volume_ul: float = 80.0,
) -> SplitCalculation:
    """
    Calculate how to split a reaction across multiple wells.

    Args:
        reaction_volume_ul: Total reaction volume in µL
        max_well_volume_ul: Maximum volume per well in µL

    Returns:
        SplitCalculation with wells needed and volumes
    """
    if reaction_volume_ul <= max_well_volume_ul:
        return SplitCalculation(
            wells_needed=1,
            volume_per_well=[reaction_volume_ul],
        )

    wells_needed = ceil(reaction_volume_ul / max_well_volume_ul)
    base_volume = reaction_volume_ul / wells_needed

    # Distribute volume evenly
    volumes = [base_volume] * wells_needed

    # Handle any floating point remainder
    total_distributed = sum(volumes)
    remainder = reaction_volume_ul - total_distributed
    if abs(remainder) > 0.001:
        volumes[-1] += remainder

    return SplitCalculation(
        wells_needed=wells_needed,
        volume_per_well=volumes,
        note=f"Split {reaction_volume_ul:.1f} µL across {wells_needed} wells",
    )


def validate_well_volume(
    volume_ul: float,
    plate_format: PlateFormat = PlateFormat.WELL_384,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate that a volume is appropriate for the plate format.

    Args:
        volume_ul: Volume to validate in µL
        plate_format: Plate format for constraints

    Returns:
        Tuple of (is_valid, error_message, warning_message)
    """
    constraints = PLATE_CONSTRAINTS[plate_format]

    if volume_ul < constraints.min_well_volume_ul:
        return (
            False,
            f"Volume {volume_ul:.1f} µL below minimum {constraints.min_well_volume_ul} µL",
            None,
        )

    if volume_ul > constraints.max_well_volume_ul:
        return (
            False,
            f"Volume {volume_ul:.1f} µL exceeds maximum {constraints.max_well_volume_ul} µL",
            None,
        )

    if volume_ul < constraints.optimal_min_ul or volume_ul > constraints.optimal_max_ul:
        return (
            True,
            None,
            f"Volume {volume_ul:.1f} µL outside optimal range "
            f"({constraints.optimal_min_ul}-{constraints.optimal_max_ul} µL)",
        )

    return (True, None, None)
