"""IVT Reaction Calculator - comprehensive experiment planning tool.

This module provides:
- Volume calculations for IVT reactions
- Master mix volume calculations with overage
- DNA dilution protocols
- Volume intervention recommendations
- Pipetting protocol generation
- Input/output validation

Example usage:
    from app.calculator import calculate_master_mix, generate_protocol

    # Define constructs
    constructs = [
        {'name': 'Reporter-only', 'stock_concentration_ng_ul': 100, 'is_unregulated': True},
        {'name': 'Tbox1_WT', 'stock_concentration_ng_ul': 150, 'is_wildtype': True, 'family': 'Tbox1'},
        {'name': 'Tbox1_M1', 'stock_concentration_ng_ul': 200, 'family': 'Tbox1'},
    ]

    # Calculate master mix
    mm = calculate_master_mix(
        n_reactions=12,
        constructs=constructs,
        dna_mass_ug=20.0,
    )

    # Generate protocol
    protocol = generate_protocol(mm, title="My IVT Setup")
    print(format_protocol_text(protocol))
"""

# Constants and types
from .constants import (
    PlateFormat,
    VolumeConstraints,
    PLATE_CONSTRAINTS,
    MIN_PIPETTABLE_VOLUME_UL,
    WARN_PIPETTABLE_VOLUME_UL,
    TARGET_DNA_VOLUME_UL,
    DEFAULT_OVERAGE_PERCENT,
    DEFAULT_DNA_MASS_UG,
    DNA_MASS_TO_VOLUME_FACTOR,
    AVG_BP_MOLECULAR_WEIGHT,
    TARGET_DNA_CONCENTRATION_NM,
    STANDARD_COMPONENTS,
    MIN_REPLICATES,
    MAX_TEMPLATES_RECOMMENDED,
    MAX_TEMPLATES_ABSOLUTE,
    CHECKERBOARD_USABLE_WELLS_384,
    DEFAULT_PRECISION_TARGET,
    TARGET_EFFECT_PROBABILITY,
    MAX_LIGAND_VOLUME_FRACTION,
)

# DNA concentration conversion (Phase 5)
from .dna_converter import DNAConcentrationConverter

# Volume calculations (reaction_calculator.py - renamed from volume_calculator.py per PRD)
from .reaction_calculator import (
    LigandConfig,
    ComponentVolume,
    DNAAddition,
    SingleReactionVolumes,
    SplitCalculation,
    round_volume_up,
    calculate_reaction_volume,
    calculate_buffer_volume,
    calculate_component_volume,
    calculate_dna_volume,
    ng_ul_to_nM,
    calculate_dna_volume_nM,
    calculate_enzyme_volume,
    calculate_single_reaction_volumes,
    calculate_dna_additions,
    calculate_split_wells,
    validate_well_volume,
)

# Master mix calculations
from .master_mix import (
    MasterMixComponent,
    MasterMixCalculation,
    calculate_master_mix,
    calculate_total_wells,
    calculate_total_reactions,
    format_master_mix_table,
)

# DNA dilution (dilution_calculator.py - renamed from dna_dilution.py per PRD)
from .dilution_calculator import (
    DilutionStep,
    DilutionProtocol,
    SerialDilutionProtocol,
    calculate_simple_dilution,
    calculate_dilution_for_target_dna_volume,
    calculate_serial_dilution,
    normalize_dna_stocks,
    format_dilution_protocol,
)

# Volume interventions
from .volume_intervention import (
    InterventionType,
    DilutionOption,
    ScaleUpOption,
    SplitWellOption,
    VolumeIntervention,
    recommend_dna_volume_intervention,
    recommend_well_volume_intervention,
    validate_all_volumes,
    format_intervention,
)

# Protocol generation
from .protocol_generator import (
    ProtocolStep,
    PipettingProtocol,
    generate_protocol,
    format_protocol_text,
    format_protocol_csv,
    generate_protocol_summary,
)

# Validators
from .validators import (
    ValidationLevel,
    ValidationMessage,
    ValidationResult,
    validate_volume,
    validate_concentration,
    validate_reaction_parameters,
    validate_construct_list,
    validate_well_volume as validate_well_volume_constraints,
    validate_checkerboard_position,
    format_validation_result,
)

# Power analysis
from .power_analysis import (
    PowerResult,
    SampleSizeResult,
    calculate_power_for_fold_change,
    calculate_sample_size_for_power,
    calculate_ci_width,
    calculate_se_from_ci_width,
    calculate_sample_size_for_precision,
    estimate_precision_improvement,
    calculate_precision_gap_score,
    calculate_untested_score,
    estimate_coplating_benefit,
)

# Recommendation engine
from .recommendation import (
    RecommendationConfidence,
    ConstructStats,
    ConstructRecommendation,
    DFHBIRecommendation,
    ExperimentPlan,
    RecommendationEngine,
    recommend_dfhbi_controls,
    check_template_limit,
    calculate_wells_needed,
    check_capacity,
)

# Smart planner
from .smart_planner import (
    PlannerMode,
    FirstExperimentSuggestion,
    ImpactPreview,
    PlanValidation,
    SmartPlanner,
    create_planner_for_project,
)

__all__ = [
    # DNA concentration converter (Phase 5)
    'DNAConcentrationConverter',
    # Constants
    'PlateFormat',
    'VolumeConstraints',
    'PLATE_CONSTRAINTS',
    'MIN_PIPETTABLE_VOLUME_UL',
    'WARN_PIPETTABLE_VOLUME_UL',
    'TARGET_DNA_VOLUME_UL',
    'DEFAULT_OVERAGE_PERCENT',
    'DEFAULT_DNA_MASS_UG',
    'DNA_MASS_TO_VOLUME_FACTOR',
    'STANDARD_COMPONENTS',
    'MIN_REPLICATES',
    'MAX_TEMPLATES_RECOMMENDED',
    'MAX_TEMPLATES_ABSOLUTE',
    'CHECKERBOARD_USABLE_WELLS_384',
    'DEFAULT_PRECISION_TARGET',
    'TARGET_EFFECT_PROBABILITY',
    'MAX_LIGAND_VOLUME_FRACTION',
    # Volume calculations
    'LigandConfig',
    'ComponentVolume',
    'DNAAddition',
    'SingleReactionVolumes',
    'SplitCalculation',
    'round_volume_up',
    'calculate_reaction_volume',
    'calculate_buffer_volume',
    'calculate_component_volume',
    'calculate_dna_volume',
    'calculate_enzyme_volume',
    'calculate_single_reaction_volumes',
    'calculate_dna_additions',
    'calculate_split_wells',
    'validate_well_volume',
    # Master mix
    'MasterMixComponent',
    'MasterMixCalculation',
    'calculate_master_mix',
    'calculate_total_wells',
    'calculate_total_reactions',
    'format_master_mix_table',
    # DNA dilution
    'DilutionStep',
    'DilutionProtocol',
    'SerialDilutionProtocol',
    'calculate_simple_dilution',
    'calculate_dilution_for_target_dna_volume',
    'calculate_serial_dilution',
    'normalize_dna_stocks',
    'format_dilution_protocol',
    # Volume interventions
    'InterventionType',
    'DilutionOption',
    'ScaleUpOption',
    'SplitWellOption',
    'VolumeIntervention',
    'recommend_dna_volume_intervention',
    'recommend_well_volume_intervention',
    'validate_all_volumes',
    'format_intervention',
    # Protocol generation
    'ProtocolStep',
    'PipettingProtocol',
    'generate_protocol',
    'format_protocol_text',
    'format_protocol_csv',
    'generate_protocol_summary',
    # Validators
    'ValidationLevel',
    'ValidationMessage',
    'ValidationResult',
    'validate_volume',
    'validate_concentration',
    'validate_reaction_parameters',
    'validate_construct_list',
    'validate_well_volume_constraints',
    'validate_checkerboard_position',
    'format_validation_result',
    # Power analysis
    'PowerResult',
    'SampleSizeResult',
    'calculate_power_for_fold_change',
    'calculate_sample_size_for_power',
    'calculate_ci_width',
    'calculate_se_from_ci_width',
    'calculate_sample_size_for_precision',
    'estimate_precision_improvement',
    'calculate_precision_gap_score',
    'calculate_untested_score',
    'estimate_coplating_benefit',
    # Recommendation engine
    'RecommendationConfidence',
    'ConstructStats',
    'ConstructRecommendation',
    'DFHBIRecommendation',
    'ExperimentPlan',
    'RecommendationEngine',
    'recommend_dfhbi_controls',
    'check_template_limit',
    'calculate_wells_needed',
    'check_capacity',
    # Smart planner
    'PlannerMode',
    'FirstExperimentSuggestion',
    'ImpactPreview',
    'PlanValidation',
    'SmartPlanner',
    'create_planner_for_project',
]
