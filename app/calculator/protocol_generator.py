"""Pipetting protocol generator for IVT reactions."""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
import csv
import io

from app.models.enums import LigandCondition

from .master_mix import MasterMixCalculation, format_master_mix_table
from .constants import TUBE_CAPACITIES


def _recommend_tube_size(volume_ul: float) -> tuple[str, Optional[str]]:
    """
    Recommend appropriate tube size based on volume.
    
    Args:
        volume_ul: Volume in microliters
        
    Returns:
        Tuple of (tube_description, warning_message)
        warning_message is None if volume fits in largest tube
    """
    # Find smallest tube that fits the volume
    # TUBE_CAPACITIES is Dict[float, str] mapping max_vol -> name
    sorted_caps = sorted(TUBE_CAPACITIES.items())  # Sort by volume key
    
    for capacity, name in sorted_caps:
        if volume_ul <= capacity:
            return name, None
            
    # If we get here, volume exceeds largest tube
    largest_cap, largest_name = sorted_caps[-1]
    warning = (f"Volume {volume_ul:.1f} µL exceeds capacity of largest tube ({largest_name}). "
               f"Split into multiple tubes.")
    return largest_name, warning


@dataclass
class ProtocolStep:
    """A single step in the pipetting protocol."""
    step_number: int
    section: str  # e.g., "Master Mix Preparation", "DNA Addition"
    action: str
    volume_ul: Optional[float]
    component: str
    destination: str
    notes: Optional[str] = None


@dataclass
class PipettingProtocol:
    """Complete pipetting protocol for IVT setup."""
    title: str
    created_at: datetime
    created_by: Optional[str]
    project_name: Optional[str]
    session_name: Optional[str]
    calculation: MasterMixCalculation
    steps: List[ProtocolStep] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def generate_protocol(
    calculation: MasterMixCalculation,
    title: str = "IVT Reaction Setup Protocol",
    created_by: Optional[str] = None,
    project_name: Optional[str] = None,
    session_name: Optional[str] = None,
) -> PipettingProtocol:
    """
    Generate a complete pipetting protocol from master mix calculation.

    Args:
        calculation: MasterMixCalculation with all volumes
        title: Protocol title
        created_by: Username who created the protocol
        project_name: Associated project name
        session_name: Associated session name

    Returns:
        PipettingProtocol with all steps
    """
    protocol = PipettingProtocol(
        title=title,
        created_at=datetime.now(),
        created_by=created_by,
        project_name=project_name,
        session_name=session_name,
        calculation=calculation,
    )

    step_num = 0
    steps = []

    # Analyze workflow type and volumes first to recommend tubes

    # Check if we have -DFHBI controls necessitating a split master mix
    dfhbi_controls = [
        add for add in calculation.dna_additions
        if add.is_negative_control and add.negative_control_type == 'no_dye'
    ]
    has_dfhbi_controls = len(dfhbi_controls) > 0

    # Identify DFHBI component
    dfhbi_comp = next((c for c in calculation.components if "DFHBI" in c.name), None)

    # If we have controls but no dye in MM, we can't do the split (logic error or dye not included)
    is_split_workflow = has_dfhbi_controls and dfhbi_comp is not None

    # Detect ligand workflow
    is_ligand_workflow = getattr(calculation, 'is_ligand_workflow', False)
    ligand_vol_per_rxn = getattr(calculation, 'ligand_volume_per_rxn_ul', 0.0)
    ligand_config = getattr(calculation, 'ligand_config', None)

    # Calculate max volume for Main Master Mix tube
    if is_split_workflow:
        # Initial volume is everything minus dye
        # (Dye is added later to the main portion only)
        # Actually simplest: Max volume it will ever hold is Total MM Volume - Dye Volume (Base MM)
        # OR (Base MM - Split Portion) + Dye for Main.
        # usually Base MM (Total - Dye) is the largest volume it holds before split.
        base_mm_vol = calculation.total_master_mix_volume_ul - dfhbi_comp.master_mix_volume_ul
        mm_tube_vol = base_mm_vol
    else:
        mm_tube_vol = calculation.total_master_mix_volume_ul
        
    mm_tube_name, mm_warning = _recommend_tube_size(mm_tube_vol)
    if mm_warning:
        protocol.warnings.append(mm_warning)

    # Section 1: Master Mix Preparation
    steps.append(ProtocolStep(
        step_number=(step_num := step_num + 1),
        section="Master Mix Preparation",
        action="Label a new tube",
        volume_ul=None,
        component=mm_tube_name,
        destination="Work area",
        notes="Label as 'Master Mix' with date",
    ))

    # NTP component names for pre-mix step
    _NTP_NAMES = {"GTP", "ATP", "CTP", "UTP"}

    # Step 1: Base Master Mix (or Full MM if not splitting)
    # Add each master mix component in order
    for comp in calculation.components:
        if comp.master_mix_volume_ul > 0:
            # If splitting, skip Dye for now
            if is_split_workflow and comp == dfhbi_comp:
                continue

            # NTPs need mixing after thaw before adding
            if comp.name in _NTP_NAMES:
                steps.append(ProtocolStep(
                    step_number=(step_num := step_num + 1),
                    section="Master Mix Preparation",
                    action=f"Mix {comp.name} stock",
                    volume_ul=None,
                    component=f"{comp.name} stock tube",
                    destination="",
                    notes="Pipette up and down to mix after thawing",
                ))

            steps.append(ProtocolStep(
                step_number=(step_num := step_num + 1),
                section="Master Mix Preparation",
                action="Add to master mix tube",
                volume_ul=comp.master_mix_volume_ul,
                component=comp.name,
                destination="Master Mix tube",
                notes=f"{comp.stock_concentration} {comp.stock_unit} stock" if comp.stock_concentration > 0 else None,
            ))

    steps.append(ProtocolStep(
        step_number=(step_num := step_num + 1),
        section="Master Mix Preparation",
        action="Mix gently",
        volume_ul=None,
        component="Master Mix",
        destination="Master Mix tube",
        notes="Pipette up and down 10 times",
    ))

    # Split Workflow Steps
    if is_split_workflow:
        # Calculate split volumes
        # Replicates are already summed in n_reactions, but we need n for controls specifically
        # We need to account for replicates of the controls
        n_control_rxns = sum(getattr(c, 'replicates', 1) for c in dfhbi_controls)
        n_total_rxns = calculation.n_reactions
        split_ratio = n_control_rxns / n_total_rxns
        
        # Calculate volumes
        total_dye_vol = dfhbi_comp.master_mix_volume_ul
        dye_vol_for_main = total_dye_vol * (1 - split_ratio)
        # Note: water_vol_for_control is NOT added to MM tube anymore, but to DNA addition
        water_vol_for_control = total_dye_vol * split_ratio
        
        # Base MM volume (Total MM - Total Dye)
        base_mm_vol = calculation.total_master_mix_volume_ul - total_dye_vol
        base_mm_to_move = base_mm_vol * split_ratio
        
        # Determine tube size for Split tube
        split_tube_name, split_warning = _recommend_tube_size(base_mm_to_move)
        if split_warning:
            protocol.warnings.append(split_warning)
        
        # Add warnings for low split volumes
        if base_mm_to_move < 0.5:
             protocol.warnings.append(f"Master Mix Split: Transfer volume {base_mm_to_move:.1f} µL is very low. Use P2 pipette.")
        if dye_vol_for_main < 0.5:
             protocol.warnings.append(f"Master Mix Split: Dye volume {dye_vol_for_main:.1f} µL is very low. Use P2 pipette.")
        
        steps.append(ProtocolStep(
            step_number=(step_num := step_num + 1),
            section="Master Mix Split",
            action="Label new tube",
            volume_ul=None,
            component=split_tube_name,
            destination="Work area",
            notes="Label as '-DFHBI MM' (Empty Control)"
        ))
        
        steps.append(ProtocolStep(
            step_number=(step_num := step_num + 1),
            section="Master Mix Split",
            action="Transfer Base MM",
            volume_ul=base_mm_to_move,
            component="Base Master Mix",
            destination="-DFHBI MM tube",
            notes=f"For {n_control_rxns} control reactions"
        ))
        
        # REMOVED: Water placeholder step. Water will be added with DNA.
        
        steps.append(ProtocolStep(
            step_number=(step_num := step_num + 1),
            section="Master Mix Split",
            action="Add Dye to Main MM",
            volume_ul=dye_vol_for_main,
            component="DFHBI Dye",
            destination="Main Master Mix tube",
            notes="Adding dye only to the +DFHBI reactions"
        ))
        
        steps.append(ProtocolStep(
            step_number=(step_num := step_num + 1),
            section="Master Mix Split",
            action="Mix both tubes",
            volume_ul=None,
            component="Both MM tubes",
            destination="",
            notes="Ensures homogeneity"
        ))

    # Ligand Split Workflow
    if is_ligand_workflow and ligand_config:
        total_ligand_vol = ligand_vol_per_rxn * calculation.n_effective

        if is_split_workflow:
            # 4-way split: We already have Main MM (+DFHBI) and -DFHBI MM
            # Now split each into +Lig and -Lig portions
            # Count +Lig and -Lig reactions
            plus_lig_adds = [a for a in calculation.dna_additions if a.ligand_condition == LigandCondition.PLUS_LIG]
            minus_lig_adds = [a for a in calculation.dna_additions if a.ligand_condition == LigandCondition.MINUS_LIG]
            n_plus_lig = sum(a.replicates for a in plus_lig_adds)
            n_minus_lig = sum(a.replicates for a in minus_lig_adds)

            # Among +Lig, how many are -DFHBI controls?
            n_plus_lig_no_dye = sum(
                a.replicates for a in plus_lig_adds
                if a.is_negative_control and a.negative_control_type == 'no_dye'
            )
            n_plus_lig_dye = n_plus_lig - n_plus_lig_no_dye
            n_minus_lig_no_dye = sum(
                a.replicates for a in minus_lig_adds
                if a.is_negative_control and a.negative_control_type == 'no_dye'
            )
            n_minus_lig_dye = n_minus_lig - n_minus_lig_no_dye

            steps.append(ProtocolStep(
                step_number=(step_num := step_num + 1),
                section="Ligand Split",
                action="Label 2 additional tubes",
                volume_ul=None,
                component="Tubes",
                destination="Work area",
                notes="Label: '+Lig MM', '-Lig/-DFHBI MM' (you already have Main MM and -DFHBI MM)",
            ))

            # Split Main MM (+DFHBI) into +Lig/+DFHBI and -Lig/+DFHBI
            if n_minus_lig_dye > 0:
                frac_minus_lig_dye = n_minus_lig_dye / (n_plus_lig_dye + n_minus_lig_dye) if (n_plus_lig_dye + n_minus_lig_dye) > 0 else 0
                main_mm_vol = calculation.total_master_mix_volume_ul - dfhbi_comp.master_mix_volume_ul
                main_mm_after_dye = main_mm_vol * (1 - split_ratio) + dye_vol_for_main
                transfer_to_minus_lig_dye = main_mm_after_dye * frac_minus_lig_dye

                steps.append(ProtocolStep(
                    step_number=(step_num := step_num + 1),
                    section="Ligand Split",
                    action="Transfer from Main MM",
                    volume_ul=transfer_to_minus_lig_dye,
                    component="Main MM (+DFHBI)",
                    destination="-Lig/+DFHBI portion (relabel Main MM tube)",
                    notes=f"For {n_minus_lig_dye} -Lig/+DFHBI reactions. Remaining Main MM becomes +Lig/+DFHBI.",
                ))

            # Split -DFHBI MM into +Lig/-DFHBI and -Lig/-DFHBI
            if n_minus_lig_no_dye > 0 and n_plus_lig_no_dye > 0:
                frac_minus_lig_no_dye = n_minus_lig_no_dye / (n_plus_lig_no_dye + n_minus_lig_no_dye)
                no_dye_mm_vol = base_mm_to_move
                transfer_to_minus_lig_no_dye = no_dye_mm_vol * frac_minus_lig_no_dye

                steps.append(ProtocolStep(
                    step_number=(step_num := step_num + 1),
                    section="Ligand Split",
                    action="Transfer from -DFHBI MM",
                    volume_ul=transfer_to_minus_lig_no_dye,
                    component="-DFHBI MM",
                    destination="-Lig/-DFHBI MM tube",
                    notes=f"For {n_minus_lig_no_dye} -Lig/-DFHBI reactions. Remaining becomes +Lig/-DFHBI.",
                ))

            # Add ligand to +Lig tubes
            lig_for_plus_dye = ligand_vol_per_rxn * n_plus_lig_dye * calculation.overage_factor
            lig_for_plus_no_dye = ligand_vol_per_rxn * n_plus_lig_no_dye * calculation.overage_factor

            if lig_for_plus_dye > 0:
                steps.append(ProtocolStep(
                    step_number=(step_num := step_num + 1),
                    section="Ligand Split",
                    action="Add Ligand",
                    volume_ul=round(lig_for_plus_dye, 1),
                    component=f"Ligand ({ligand_config.stock_concentration_uM:.0f} µM stock)",
                    destination="+Lig/+DFHBI MM tube",
                    notes=f"{ligand_config.final_concentration_uM:.0f} µM final",
                ))
            if lig_for_plus_no_dye > 0:
                steps.append(ProtocolStep(
                    step_number=(step_num := step_num + 1),
                    section="Ligand Split",
                    action="Add Ligand",
                    volume_ul=round(lig_for_plus_no_dye, 1),
                    component=f"Ligand ({ligand_config.stock_concentration_uM:.0f} µM stock)",
                    destination="+Lig/-DFHBI MM tube",
                    notes=f"{ligand_config.final_concentration_uM:.0f} µM final",
                ))

            # Add replacement water to -Lig tubes
            water_for_minus_dye = ligand_vol_per_rxn * n_minus_lig_dye * calculation.overage_factor
            water_for_minus_no_dye = ligand_vol_per_rxn * n_minus_lig_no_dye * calculation.overage_factor

            if water_for_minus_dye > 0:
                steps.append(ProtocolStep(
                    step_number=(step_num := step_num + 1),
                    section="Ligand Split",
                    action="Add replacement water",
                    volume_ul=round(water_for_minus_dye, 1),
                    component="Nuclease-free water",
                    destination="-Lig/+DFHBI MM tube",
                    notes="Replaces ligand volume to maintain equal reaction volumes",
                ))
            if water_for_minus_no_dye > 0:
                steps.append(ProtocolStep(
                    step_number=(step_num := step_num + 1),
                    section="Ligand Split",
                    action="Add replacement water",
                    volume_ul=round(water_for_minus_no_dye, 1),
                    component="Nuclease-free water",
                    destination="-Lig/-DFHBI MM tube",
                    notes="Replaces ligand volume to maintain equal reaction volumes",
                ))

            steps.append(ProtocolStep(
                step_number=(step_num := step_num + 1),
                section="Ligand Split",
                action="Mix all 4 tubes",
                volume_ul=None,
                component="All MM tubes",
                destination="",
                notes="Ensures homogeneity in all conditions",
            ))

        else:
            # Ligand-only split (2 tubes): +Lig MM and -Lig MM
            # Split base MM in half (by reaction count)
            plus_lig_adds = [a for a in calculation.dna_additions if a.ligand_condition == LigandCondition.PLUS_LIG]
            minus_lig_adds = [a for a in calculation.dna_additions if a.ligand_condition == LigandCondition.MINUS_LIG]
            n_plus_lig = sum(a.replicates for a in plus_lig_adds)
            n_minus_lig = sum(a.replicates for a in minus_lig_adds)
            n_total = n_plus_lig + n_minus_lig

            frac_minus = n_minus_lig / n_total if n_total > 0 else 0.5
            base_mm_to_transfer = calculation.total_master_mix_volume_ul * frac_minus

            minus_lig_tube_name, minus_lig_warning = _recommend_tube_size(base_mm_to_transfer)
            if minus_lig_warning:
                protocol.warnings.append(minus_lig_warning)

            steps.append(ProtocolStep(
                step_number=(step_num := step_num + 1),
                section="Ligand Split",
                action="Label new tube",
                volume_ul=None,
                component=minus_lig_tube_name,
                destination="Work area",
                notes="Label as '-Lig MM'",
            ))

            steps.append(ProtocolStep(
                step_number=(step_num := step_num + 1),
                section="Ligand Split",
                action="Transfer Base MM",
                volume_ul=base_mm_to_transfer,
                component="Base Master Mix",
                destination="-Lig MM tube",
                notes=f"For {n_minus_lig} -Ligand reactions",
            ))

            # Add ligand to +Lig portion (remaining in original tube)
            lig_vol_for_plus = ligand_vol_per_rxn * n_plus_lig * calculation.overage_factor
            steps.append(ProtocolStep(
                step_number=(step_num := step_num + 1),
                section="Ligand Split",
                action="Add Ligand to Main MM",
                volume_ul=round(lig_vol_for_plus, 1),
                component=f"Ligand ({ligand_config.stock_concentration_uM:.0f} µM stock)",
                destination="+Lig MM tube (original MM tube)",
                notes=f"{ligand_config.final_concentration_uM:.0f} µM final concentration",
            ))

            # Add replacement water to -Lig portion
            water_for_minus = ligand_vol_per_rxn * n_minus_lig * calculation.overage_factor
            steps.append(ProtocolStep(
                step_number=(step_num := step_num + 1),
                section="Ligand Split",
                action="Add replacement water",
                volume_ul=round(water_for_minus, 1),
                component="Nuclease-free water",
                destination="-Lig MM tube",
                notes="Replaces ligand volume to maintain equal reaction volumes",
            ))

            steps.append(ProtocolStep(
                step_number=(step_num := step_num + 1),
                section="Ligand Split",
                action="Mix both tubes",
                volume_ul=None,
                component="Both MM tubes",
                destination="",
                notes="Ensures homogeneity",
            ))

    steps.append(ProtocolStep(
        step_number=(step_num := step_num + 1),
        section="Master Mix Preparation",
        action="Keep on ice",
        volume_ul=None,
        component="Master Mixes",
        destination="Ice",
        notes="Keep master mix on ice until ready to use",
    ))

    # Section 2: Aliquot Master Mix
    # Build per-condition tube breakdown for labelling notes
    _tube_labels = []
    for add in calculation.dna_additions:
        label = f"{add.replicates}x {add.construct_name}"
        if add.ligand_condition:
            label += f" ({add.ligand_condition})"
        _tube_labels.append(label)
    _label_notes = "Label tubes: " + ", ".join(_tube_labels)

    steps.append(ProtocolStep(
        step_number=(step_num := step_num + 1),
        section="Aliquot Master Mix",
        action="Label reaction tubes",
        volume_ul=None,
        component=f"{calculation.n_reactions} tubes",
        destination="Work area",
        notes=_label_notes,
    ))

    mm_per_tube_total = calculation.master_mix_per_tube_ul
    dye_vol_per_tube = 0.0
    
    if is_split_workflow and is_ligand_workflow:
        # 4-way aliquot: route each MM tube to correct reaction tubes
        dye_fraction = total_dye_vol / calculation.total_master_mix_volume_ul
        dye_vol_per_tube = mm_per_tube_total * dye_fraction
        base_mm_per_tube = mm_per_tube_total - dye_vol_per_tube

        # Count reactions per condition
        plus_lig_dye_adds = [a for a in calculation.dna_additions
                            if a.ligand_condition == LigandCondition.PLUS_LIG and not (a.is_negative_control and a.negative_control_type == 'no_dye')]
        minus_lig_dye_adds = [a for a in calculation.dna_additions
                              if a.ligand_condition == LigandCondition.MINUS_LIG and not (a.is_negative_control and a.negative_control_type == 'no_dye')]
        plus_lig_no_dye_adds = [a for a in calculation.dna_additions
                                if a.ligand_condition == LigandCondition.PLUS_LIG and a.is_negative_control and a.negative_control_type == 'no_dye']
        minus_lig_no_dye_adds = [a for a in calculation.dna_additions
                                 if a.ligand_condition == LigandCondition.MINUS_LIG and a.is_negative_control and a.negative_control_type == 'no_dye']

        n_pld = sum(a.replicates for a in plus_lig_dye_adds)
        n_mld = sum(a.replicates for a in minus_lig_dye_adds)
        n_plnd = sum(a.replicates for a in plus_lig_no_dye_adds)
        n_mlnd = sum(a.replicates for a in minus_lig_no_dye_adds)

        for label, vol, n, source in [
            ("+Lig/+DFHBI", mm_per_tube_total, n_pld, "+Lig/+DFHBI MM"),
            ("-Lig/+DFHBI", mm_per_tube_total, n_mld, "-Lig/+DFHBI MM"),
            ("+Lig/-DFHBI", base_mm_per_tube, n_plnd, "+Lig/-DFHBI MM"),
            ("-Lig/-DFHBI", base_mm_per_tube, n_mlnd, "-Lig/-DFHBI MM"),
        ]:
            if n > 0:
                steps.append(ProtocolStep(
                    step_number=(step_num := step_num + 1),
                    section="Aliquot Master Mix",
                    action=f"Aliquot {vol:.1f} µL",
                    volume_ul=vol,
                    component=source,
                    destination=f"The {n} {label} reaction tubes",
                    notes=f"{'No dye — add replacement water with DNA' if 'DFHBI' in label and '-DFHBI' in label else ''}",
                ))

    elif is_split_workflow:
        # 2-way DFHBI split aliquot (existing logic)
        dye_fraction = total_dye_vol / calculation.total_master_mix_volume_ul
        dye_vol_per_tube = mm_per_tube_total * dye_fraction
        base_mm_per_tube = mm_per_tube_total - dye_vol_per_tube

        # Aliquot -DFHBI MM (Base Only)
        steps.append(ProtocolStep(
            step_number=(step_num := step_num + 1),
            section="Aliquot Master Mix",
            action=f"Aliquot {base_mm_per_tube:.1f} µL",
            volume_ul=base_mm_per_tube,
            component="-DFHBI Master Mix (No Dye)",
            destination=f"The {len(dfhbi_controls)} -DFHBI control tubes",
            notes="Volume is lower because dye is missing (will add water later)",
        ))

        # Aliquot Main MM (Normal)
        n_main = calculation.n_reactions - sum(getattr(c, 'replicates', 1) for c in dfhbi_controls)
        steps.append(ProtocolStep(
            step_number=(step_num := step_num + 1),
            section="Aliquot Master Mix",
            action=f"Aliquot {mm_per_tube_total:.1f} µL",
            volume_ul=mm_per_tube_total,
            component="Main Master Mix (+DFHBI)",
            destination=f"The {n_main} standard reaction tubes",
            notes="Use the standard master mix for all other reactions",
        ))

    elif is_ligand_workflow:
        # 2-way ligand split aliquot
        plus_lig_adds = [a for a in calculation.dna_additions if a.ligand_condition == LigandCondition.PLUS_LIG]
        minus_lig_adds = [a for a in calculation.dna_additions if a.ligand_condition == LigandCondition.MINUS_LIG]
        n_plus = sum(a.replicates for a in plus_lig_adds)
        n_minus = sum(a.replicates for a in minus_lig_adds)

        steps.append(ProtocolStep(
            step_number=(step_num := step_num + 1),
            section="Aliquot Master Mix",
            action=f"Aliquot {mm_per_tube_total:.1f} µL",
            volume_ul=mm_per_tube_total,
            component="+Lig Master Mix",
            destination=f"The {n_plus} +Ligand reaction tubes",
            notes="From +Lig MM tube (with ligand)",
        ))

        steps.append(ProtocolStep(
            step_number=(step_num := step_num + 1),
            section="Aliquot Master Mix",
            action=f"Aliquot {mm_per_tube_total:.1f} µL",
            volume_ul=mm_per_tube_total,
            component="-Lig Master Mix",
            destination=f"The {n_minus} -Ligand reaction tubes",
            notes="From -Lig MM tube (with replacement water)",
        ))

    else:
        # Standard Aliquot
        steps.append(ProtocolStep(
            step_number=(step_num := step_num + 1),
            section="Aliquot Master Mix",
            action=f"Aliquot {mm_per_tube_total:.1f} µL to each tube",
            volume_ul=mm_per_tube_total,
            component="Master Mix",
            destination=f"All {calculation.n_reactions} reaction tubes",
            notes="Use same pipette tip for all aliquots to ensure equal distribution",
        ))

    # Section 3: DNA Addition
    # Explicit per-tube DNA additions
    for addition in calculation.dna_additions:
        reps = addition.replicates

        for rep in range(1, reps + 1):
            tube_label = f"{addition.construct_name}-{rep}"
            if addition.ligand_condition:
                tube_label += f" ({addition.ligand_condition})"

            if addition.is_negative_control and addition.negative_control_type == 'no_template':
                # -Template control: water only
                steps.append(ProtocolStep(
                    step_number=(step_num := step_num + 1),
                    section="DNA Addition",
                    action=f"Add water (no DNA)",
                    volume_ul=addition.total_addition_ul,
                    component="Nuclease-free water",
                    destination=f"Tube: {tube_label}",
                    notes="-Template negative control. Place tube on ice.",
                ))
            elif addition.is_negative_control and addition.negative_control_type == 'no_dye':
                # -DFHBI control: DNA + Water (adjustment + replaced dye volume)
                water_to_add = addition.water_adjustment_ul + dye_vol_per_tube
                total_vol = addition.dna_volume_ul + water_to_add

                steps.append(ProtocolStep(
                    step_number=(step_num := step_num + 1),
                    section="DNA Addition",
                    action="Add DNA + water",
                    volume_ul=total_vol,
                    component=f"DNA ({addition.dna_volume_ul:.1f} µL) + water ({water_to_add:.1f} µL)",
                    destination=f"Tube: {tube_label}",
                    notes=f"-DFHBI negative control. Includes {dye_vol_per_tube:.1f} µL water to replace dye. Place tube on ice.",
                ))
            else:
                # Normal construct
                if addition.water_adjustment_ul > 0.01:
                    steps.append(ProtocolStep(
                        step_number=(step_num := step_num + 1),
                        section="DNA Addition",
                        action="Add water adjustment",
                        volume_ul=addition.water_adjustment_ul,
                        component="Nuclease-free water",
                        destination=f"Tube: {tube_label}",
                        notes="Add water before DNA.",
                    ))

                if addition.stock_concentration_nM is not None:
                    comp_text = (
                        f"{addition.construct_name} "
                        f"({addition.stock_concentration_ng_ul:.0f} ng/µL = "
                        f"{addition.stock_concentration_nM:.1f} nM)"
                    )
                else:
                    comp_text = f"{addition.construct_name} ({addition.stock_concentration_ng_ul:.0f} ng/µL)"

                notes_text = "Place tube on ice."
                if getattr(addition, 'achieved_nM', None) is not None:
                    notes_text = f"Achieved: {addition.achieved_nM:.1f} nM. {notes_text}"

                steps.append(ProtocolStep(
                    step_number=(step_num := step_num + 1),
                    section="DNA Addition",
                    action=f"Add {addition.construct_name} DNA",
                    volume_ul=addition.dna_volume_ul,
                    component=comp_text,
                    destination=f"Tube: {tube_label}",
                    notes=notes_text,
                ))

    # Section 4: Final Steps
    steps.append(ProtocolStep(
        step_number=(step_num := step_num + 1),
        section="Final Steps",
        action="Mix all tubes gently",
        volume_ul=None,
        component="All reaction tubes",
        destination="",
        notes="Pipette up and down 3-5 times or flick tubes gently",
    ))

    steps.append(ProtocolStep(
        step_number=(step_num := step_num + 1),
        section="Final Steps",
        action="Spin down briefly",
        volume_ul=None,
        component="All reaction tubes",
        destination="Centrifuge",
        notes="Quick spin (2-3 seconds) to collect contents at bottom",
    ))

    steps.append(ProtocolStep(
        step_number=(step_num := step_num + 1),
        section="Final Steps",
        action="Transfer to plate wells",
        volume_ul=calculation.single_reaction.reaction_volume_ul,
        component="Complete reactions",
        destination="Plate wells as per layout",
        notes="Transfer according to plate layout design",
    ))

    protocol.steps = steps

    # Add notes and warnings
    protocol.notes = [
        "Keep all reagents on ice during preparation",
        "Use filter tips to prevent contamination",
        "Work in RNase-free environment",
    ]

    protocol.warnings = calculation.warnings + calculation.errors

    return protocol


def format_protocol_text(protocol: PipettingProtocol) -> str:
    """
    Format protocol as plain text document.

    Args:
        protocol: PipettingProtocol to format

    Returns:
        Formatted text string
    """
    lines = []

    # Header
    lines.append("=" * 80)
    lines.append(protocol.title.upper())
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Created: {protocol.created_at.strftime('%Y-%m-%d %H:%M')}")
    if protocol.created_by:
        lines.append(f"Created by: {protocol.created_by}")
    if protocol.project_name:
        lines.append(f"Project: {protocol.project_name}")
    if protocol.session_name:
        lines.append(f"Session: {protocol.session_name}")
    lines.append("")

    # Summary
    lines.append("-" * 80)
    lines.append("EXPERIMENT SUMMARY")
    lines.append("-" * 80)
    lines.append(f"Number of reactions: {protocol.calculation.n_reactions}")
    lines.append(f"Reaction volume: {protocol.calculation.single_reaction.reaction_volume_ul:.1f} µL")
    lines.append(f"Overage: {(protocol.calculation.overage_factor - 1) * 100:.0f}%")
    lines.append(f"Master mix per tube: {protocol.calculation.master_mix_per_tube_ul:.1f} µL")
    if getattr(protocol.calculation, 'is_ligand_workflow', False):
        lig_cfg = protocol.calculation.ligand_config
        if lig_cfg:
            lines.append(
                f"Ligand: {lig_cfg.final_concentration_uM:.0f} µM final "
                f"({lig_cfg.stock_concentration_uM:.0f} µM stock)"
            )
            lines.append(
                f"Ligand volume per reaction: {protocol.calculation.ligand_volume_per_rxn_ul:.1f} µL"
            )
    lines.append("")

    # Master mix table
    lines.append(format_master_mix_table(protocol.calculation))
    lines.append("")

    # DNA Source Requirements Table
    if protocol.calculation.dna_additions:
        # Check if any additions have nM data
        has_nM_data = any(
            add.stock_concentration_nM is not None
            for add in protocol.calculation.dna_additions
            if not add.is_negative_control or add.negative_control_type == 'no_dye'
        )

        lines.append("-" * 80)
        lines.append("DNA SOURCE REQUIREMENTS")
        lines.append("-" * 80)
        if has_nM_data:
            lines.append(
                f"{'Construct':<25} {'Conc (ng/µL)':<14} {'Stock (nM)':<12} {'Achieved nM':<12} {'Vol/Well':<10} "
                f"{'Rxns':<8} {'Total Required (µL)':<20}"
            )
        else:
            lines.append(
                f"{'Construct':<30} {'Conc (ng/µL)':<15} {'Vol/Well':<10} "
                f"{'Rxns':<8} {'Total Required (µL)':<20}"
            )
        lines.append("-" * 80)

        # Aggregate DNA usage by stock source
        dna_usage = {}

        for add in protocol.calculation.dna_additions:
            # Skip pure water controls if they don't consume DNA stock
            if add.stock_concentration_ng_ul == 0:
                continue

            # Key by stock concentration AND source name to correctly group controls
            # -DFHBI controls will have the same source name as the Reporter
            source = add.source_construct_name if add.source_construct_name else add.construct_name
            key = (add.stock_concentration_ng_ul, source)

            if key not in dna_usage:
                dna_usage[key] = {
                    "name": source,
                    "stock": add.stock_concentration_ng_ul,
                    "stock_nM": add.stock_concentration_nM,
                    "achieved_nM": getattr(add, 'achieved_nM', None),
                    "vol_per_well": add.dna_volume_ul,
                    "rxns": 0,
                    "total_vol": 0.0,
                    "is_control": add.is_negative_control
                }
                # If it's a normal construct (not previously initialized with control), flag as not control
                if not add.is_negative_control:
                    dna_usage[key]["is_control"] = False
            elif not add.is_negative_control:
                # Update to ensure we flag as not control if we see the main construct
                dna_usage[key]["is_control"] = False

            reps = getattr(add, 'replicates', 1)
            dna_usage[key]["rxns"] += reps
            dna_usage[key]["total_vol"] += add.dna_volume_ul * reps * protocol.calculation.overage_factor

        # Print aggregated table
        for key, usage in dna_usage.items():
            if has_nM_data:
                nM_str = f"{usage['stock_nM']:.1f}" if usage['stock_nM'] is not None else "N/A"
                achieved_str = f"{usage['achieved_nM']:.1f}" if usage.get('achieved_nM') is not None else "N/A"
                lines.append(
                    f"{usage['name']:<25} {usage['stock']:<14.1f} {nM_str:<12} {achieved_str:<12} "
                    f"{usage['vol_per_well']:<10.1f} {usage['rxns']:<8d} "
                    f"{usage['total_vol']:<20.1f}"
                )
            else:
                lines.append(
                    f"{usage['name']:<30} {usage['stock']:<15.1f} "
                    f"{usage['vol_per_well']:<10.1f} {usage['rxns']:<8d} "
                    f"{usage['total_vol']:<20.1f}"
                )
        lines.append("-" * 80)
        overage_pct = (protocol.calculation.overage_factor - 1) * 100
        lines.append(f"Note: Total Required includes {overage_pct:.0f}% safety margin for pipetting.")
        lines.append("")

    # Protocol steps
    lines.append("-" * 80)
    lines.append("STEP-BY-STEP PROTOCOL")
    lines.append("-" * 80)

    current_section = ""
    for step in protocol.steps:
        if step.section != current_section:
            current_section = step.section
            lines.append("")
            lines.append(f"### {current_section.upper()} ###")
            lines.append("")

        if step.volume_ul is not None and step.volume_ul > 0:
            vol_str = f"{step.volume_ul:.1f} µL"
        else:
            vol_str = ""

        line = f"  {step.step_number:2d}. {step.action}"
        if vol_str:
            line += f": {vol_str}"
        if step.component:
            line += f" {step.component}"
        if step.destination:
            line += f" → {step.destination}"

        lines.append(line)

        if step.notes:
            lines.append(f"      ({step.notes})")

    lines.append("")

    # Notes
    if protocol.notes:
        lines.append("-" * 80)
        lines.append("NOTES")
        lines.append("-" * 80)
        for note in protocol.notes:
            lines.append(f"  • {note}")
        lines.append("")

    # Warnings
    if protocol.warnings:
        lines.append("-" * 80)
        lines.append("WARNINGS")
        lines.append("-" * 80)
        for warning in protocol.warnings:
            lines.append(f"  ⚠ {warning}")
        lines.append("")

    lines.append("=" * 80)
    lines.append("END OF PROTOCOL")
    lines.append("=" * 80)

    return "\n".join(lines)


def format_protocol_csv(protocol: PipettingProtocol) -> str:
    """
    Format protocol as CSV for spreadsheet import.

    Args:
        protocol: PipettingProtocol to format

    Returns:
        CSV string
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Step", "Section", "Action", "Volume (µL)", "Component",
        "Destination", "Notes"
    ])

    # Steps
    for step in protocol.steps:
        writer.writerow([
            step.step_number,
            step.section,
            step.action,
            f"{step.volume_ul:.1f}" if step.volume_ul else "",
            step.component,
            step.destination,
            step.notes or "",
        ])

    return output.getvalue()


def generate_protocol_summary(calculation: MasterMixCalculation) -> str:
    """
    Generate a brief protocol summary card.

    Args:
        calculation: MasterMixCalculation

    Returns:
        Brief summary text
    """
    lines = []

    lines.append("QUICK PROTOCOL SUMMARY")
    lines.append("=" * 40)
    lines.append(f"Reactions: {calculation.n_reactions}")
    lines.append(f"Volume/rxn: {calculation.single_reaction.reaction_volume_ul:.0f} µL")
    lines.append(f"Master Mix: {calculation.total_master_mix_volume_ul:.0f} µL total")
    lines.append(f"Per tube: {calculation.master_mix_per_tube_ul:.1f} µL MM + DNA")
    lines.append("")

    # DNA summary
    if calculation.dna_additions:
        lines.append("DNA Additions:")
        for add in calculation.dna_additions[:5]:  # First 5
            if add.is_negative_control and add.negative_control_type == 'no_template':
                lines.append(f"  • {add.construct_name}: {add.total_addition_ul:.1f} µL water")
            elif add.is_negative_control and add.negative_control_type == 'no_dye':
                # -DFHBI control now has DNA
                lines.append(
                    f"  • {add.construct_name}: {add.dna_volume_ul:.1f} µL DNA + "
                    f"{add.water_adjustment_ul:.1f} µL water"
                )
            else:
                lines.append(
                    f"  • {add.construct_name}: {add.dna_volume_ul:.1f} µL DNA + "
                    f"{add.water_adjustment_ul:.1f} µL water"
                )
        if len(calculation.dna_additions) > 5:
            lines.append(f"  ... and {len(calculation.dna_additions) - 5} more")

    return "\n".join(lines)
