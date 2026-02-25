"""IVT Reaction Calculator constants and default parameters."""
from dataclasses import dataclass
from enum import Enum
from typing import Dict


class PlateFormat(Enum):
    """Supported plate formats."""
    WELL_96 = "96"
    WELL_384 = "384"


@dataclass(frozen=True)
class VolumeConstraints:
    """Volume constraints for different plate formats."""
    min_well_volume_ul: float
    max_well_volume_ul: float
    optimal_min_ul: float
    optimal_max_ul: float


# Plate format constraints
PLATE_CONSTRAINTS: Dict[PlateFormat, VolumeConstraints] = {
    PlateFormat.WELL_96: VolumeConstraints(
        min_well_volume_ul=100.0,
        max_well_volume_ul=250.0,
        optimal_min_ul=150.0,
        optimal_max_ul=200.0,
    ),
    PlateFormat.WELL_384: VolumeConstraints(
        min_well_volume_ul=20.0,
        max_well_volume_ul=50.0,
        optimal_min_ul=25.0,
        optimal_max_ul=40.0,
    ),
}

# Pipetting thresholds
MIN_PIPETTABLE_VOLUME_UL = 0.5  # Absolute minimum for accurate pipetting
WARN_PIPETTABLE_VOLUME_UL = 1.0  # Below this, show accuracy warning
TARGET_DNA_VOLUME_UL = 2.0  # Target DNA volume after intervention
MIN_DILUTION_STOCK_UL = 10.0  # Minimum stock for practical dilution
MIN_DILUTED_CONCENTRATION_NG_UL = 10.0  # Below this, dilution not recommended

# Default overage for master mix
DEFAULT_OVERAGE_PERCENT = 20.0

# Default reaction parameters
DEFAULT_DNA_MASS_UG = 20.0  # µg of DNA per reaction
DNA_MASS_TO_VOLUME_FACTOR = 10.0  # V_rxn = m_DNA × 10 (µL)

# nM-based DNA targeting constants
AVG_BP_MOLECULAR_WEIGHT = 617.96  # g/mol per base pair (average dsDNA)
TARGET_DNA_CONCENTRATION_NM = 50.0  # Default target final DNA concentration in nM

# Standard IVT reaction components with default concentrations
@dataclass(frozen=True)
class ReactionComponent:
    """A component of the IVT reaction."""
    name: str
    order: int  # Pipetting order
    stock_concentration: float
    stock_unit: str
    final_concentration: float
    final_unit: str
    volume_formula: str  # Description of formula


# Standard IVT components (from PRD section 3.4.9)
STANDARD_COMPONENTS = [
    ReactionComponent(
        name="Nuclease-free water",
        order=1,
        stock_concentration=0.0,
        stock_unit="",
        final_concentration=0.0,
        final_unit="",
        volume_formula="V_rxn - sum(others)",
    ),
    ReactionComponent(
        name="10X Reaction buffer",
        order=2,
        stock_concentration=10.0,
        stock_unit="X",
        final_concentration=1.0,
        final_unit="X",
        volume_formula="V_rxn / 10",
    ),
    ReactionComponent(
        name="MgCl₂",
        order=3,
        stock_concentration=1000.0,  # 1 M = 1000 mM
        stock_unit="mM",
        final_concentration=10.0,
        final_unit="mM",
        volume_formula="(V_rxn × final) / stock",
    ),
    ReactionComponent(
        name="GTP",
        order=5,
        stock_concentration=467.3,
        stock_unit="mM",
        final_concentration=6.0,
        final_unit="mM",
        volume_formula="(C_final × V_rxn) / C_stock",
    ),
    ReactionComponent(
        name="ATP",
        order=6,
        stock_concentration=364.8,
        stock_unit="mM",
        final_concentration=5.0,
        final_unit="mM",
        volume_formula="(C_final × V_rxn) / C_stock",
    ),
    ReactionComponent(
        name="CTP",
        order=7,
        stock_concentration=343.3,
        stock_unit="mM",
        final_concentration=5.0,
        final_unit="mM",
        volume_formula="(C_final × V_rxn) / C_stock",
    ),
    ReactionComponent(
        name="UTP",
        order=8,
        stock_concentration=407.8,
        stock_unit="mM",
        final_concentration=5.0,
        final_unit="mM",
        volume_formula="(C_final × V_rxn) / C_stock",
    ),
    ReactionComponent(
        name="DFHBI dye",
        order=9,
        stock_concentration=40000.0,  # 40 mM = 40000 µM
        stock_unit="µM",
        final_concentration=100.0,
        final_unit="µM",
        volume_formula="(C_final × V_rxn) / C_stock",
    ),
    ReactionComponent(
        name="Pyrophosphatase",
        order=10,
        stock_concentration=0.1,
        stock_unit="U/µL",
        final_concentration=0.0008,
        final_unit="U/µL",
        volume_formula="(V_rxn × 1.6) / 200",
    ),
    ReactionComponent(
        name="RNAsin",
        order=11,
        stock_concentration=40.0,
        stock_unit="U/µL",
        final_concentration=0.16,
        final_unit="U/µL",
        volume_formula="(V_rxn × 0.8) / 200",
    ),
    ReactionComponent(
        name="T7 RNA Polymerase",
        order=12,
        stock_concentration=1.0,
        stock_unit="U/µL",
        final_concentration=0.002,
        final_unit="U/µL",
        volume_formula="(V_rxn × 0.4) / 200",
    ),
]

# DNA template is handled separately (order 4)
DNA_COMPONENT_ORDER = 4

# 384-well plate checkerboard capacity
CHECKERBOARD_USABLE_WELLS_384 = 192

# Template limits for practical experiments
MIN_TEMPLATES = 1
MAX_TEMPLATES_RECOMMENDED = 4
MAX_TEMPLATES_ABSOLUTE = 6  # Hard limit with warning

# Replicate constraints
MIN_REPLICATES = 4  # Minimum for statistical validity
DEFAULT_NEGATIVE_TEMPLATE_REPLICATES = 3
DEFAULT_NEGATIVE_DYE_REPLICATES = 2

# Precision targets (fold change CI width)
DEFAULT_PRECISION_TARGET = 0.3  # ±0.3 fold change

# Effect probability target (P(|FC| > θ) threshold)
TARGET_EFFECT_PROBABILITY = 0.95  # 95% posterior probability of meaningful effect

# Ligand workflow constraints
MAX_LIGAND_VOLUME_FRACTION = 0.20  # Error if ligand > 20% of V_rxn

# Tube capacities (in µL)
# Maps max volume to tube description
TUBE_CAPACITIES = {
    600.0: "0.6 mL tube",
    1500.0: "1.5 mL tube",
    1800.0: "1.8 mL tube",
    5000.0: "5.0 mL tube",
}
