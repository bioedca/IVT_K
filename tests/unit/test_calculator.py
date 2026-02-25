"""Tests for the IVT Reaction Calculator module."""
import pytest
from math import isclose

from app.calculator import (
    # Constants
    PlateFormat,
    PLATE_CONSTRAINTS,
    MIN_PIPETTABLE_VOLUME_UL,
    DEFAULT_DNA_MASS_UG,
    DNA_MASS_TO_VOLUME_FACTOR,
    # Volume calculations
    calculate_reaction_volume,
    calculate_buffer_volume,
    calculate_component_volume,
    calculate_dna_volume,
    calculate_enzyme_volume,
    calculate_single_reaction_volumes,
    calculate_dna_additions,
    calculate_split_wells,
    # Master mix
    calculate_master_mix,
    calculate_total_wells,
    format_master_mix_table,
    # Dilution
    calculate_simple_dilution,
    calculate_dilution_for_target_dna_volume,
    calculate_serial_dilution,
    # Interventions
    recommend_dna_volume_intervention,
    recommend_well_volume_intervention,
    InterventionType,
    # Protocol
    generate_protocol,
    format_protocol_text,
    format_protocol_csv,
    # Validators
    validate_volume,
    validate_reaction_parameters,
    validate_construct_list,
    validate_checkerboard_position,
    ValidationLevel,
)


class TestVolumeCalculations:
    """Tests for core volume calculation functions (F4.11)."""

    def test_calculate_reaction_volume_default(self):
        """Test V_rxn = m_DNA × 10 with default DNA mass."""
        volume = calculate_reaction_volume()
        assert volume == DEFAULT_DNA_MASS_UG * DNA_MASS_TO_VOLUME_FACTOR
        assert volume == 200.0  # 20 µg × 10 = 200 µL

    def test_calculate_reaction_volume_custom(self):
        """Test reaction volume with custom DNA mass."""
        assert calculate_reaction_volume(10.0) == 100.0
        assert calculate_reaction_volume(50.0) == 500.0
        assert calculate_reaction_volume(5.0) == 50.0

    def test_calculate_buffer_volume(self):
        """Test buffer dilution V_buffer = V_rxn / 10."""
        assert calculate_buffer_volume(200.0) == 20.0
        assert calculate_buffer_volume(100.0) == 10.0
        assert calculate_buffer_volume(50.0) == 5.0

    def test_calculate_component_volume(self):
        """Test V = (C_final × V_rxn) / C_stock."""
        # GTP: 6 mM final, 467.3 mM stock, 200 µL rxn
        gtp_vol = calculate_component_volume(200.0, 6.0, 467.3)
        expected = (6.0 * 200.0) / 467.3
        assert isclose(gtp_vol, expected, rel_tol=1e-6)

    def test_calculate_dna_volume(self):
        """Test V_DNA = m_DNA / (C_DNA / 1000)."""
        # 20 µg DNA, 100 ng/µL stock
        # 20 µg = 20000 ng, so V = 20000 / 100 = 200 µL
        dna_vol = calculate_dna_volume(20.0, 100.0)
        assert isclose(dna_vol, 200.0, rel_tol=1e-6)

        # 20 µg DNA, 500 ng/µL stock -> 40 µL
        dna_vol_conc = calculate_dna_volume(20.0, 500.0)
        assert isclose(dna_vol_conc, 40.0, rel_tol=1e-6)

    def test_calculate_dna_volume_high_concentration(self):
        """Test DNA volume with very high concentration stock."""
        # 20 µg DNA, 1000 ng/µL -> 20 µL
        dna_vol = calculate_dna_volume(20.0, 1000.0)
        assert isclose(dna_vol, 20.0, rel_tol=1e-6)

        # Very high concentration results in low volume
        dna_vol_high = calculate_dna_volume(20.0, 5000.0)
        assert isclose(dna_vol_high, 4.0, rel_tol=1e-6)

    def test_calculate_enzyme_volume(self):
        """Test enzyme volume formula V = (V_rxn × factor) / 200."""
        # Pyrophosphatase: factor 1.6, 200 µL rxn
        ppi_vol = calculate_enzyme_volume(200.0, 1.6)
        assert isclose(ppi_vol, 1.6, rel_tol=1e-6)

        # RNAsin: factor 0.8
        rnasin_vol = calculate_enzyme_volume(200.0, 0.8)
        assert isclose(rnasin_vol, 0.8, rel_tol=1e-6)

    def test_calculate_single_reaction_volumes(self):
        """Test complete single reaction calculation."""
        result = calculate_single_reaction_volumes(dna_mass_ug=20.0)

        assert result.reaction_volume_ul == 200.0
        assert result.dna_mass_ug == 20.0
        assert len(result.components) > 0
        assert result.is_valid

        # Check that buffer is included
        buffer = next(c for c in result.components if "buffer" in c.name.lower())
        assert isclose(buffer.volume_ul, 20.0, rel_tol=1e-6)


class TestMasterMixCalculations:
    """Tests for master mix calculations (F4.12)."""

    def test_master_mix_single_reaction(self):
        """Test master mix with 1 reaction."""
        mm = calculate_master_mix(n_reactions=1)

        assert mm.n_reactions == 1
        assert mm.overage_factor == 1.2  # 20% overage
        assert mm.n_effective == 1.2
        # With 1 reaction and 20% overage, smallest volumes (T7 @ 0.4*1.2=0.5)
        # just meet the MIN_PIPETTABLE_VOLUME_UL threshold, so MM is valid
        assert mm.is_valid
        # But there should be warnings for marginal volumes
        assert len(mm.warnings) > 0

    def test_master_mix_multiple_reactions(self):
        """Test master mix with 10 reactions."""
        mm = calculate_master_mix(n_reactions=10, overage_percent=10.0)

        assert mm.n_reactions == 10
        assert mm.n_effective == 11.0  # 10 × 1.1
        assert mm.total_master_mix_volume_ul > 0

    def test_master_mix_with_constructs(self):
        """Test master mix with construct DNA calculations."""
        constructs = [
            {'name': 'Reporter-only', 'stock_concentration_ng_ul': 100.0},
            {'name': 'WT', 'stock_concentration_ng_ul': 200.0},
        ]

        mm = calculate_master_mix(
            n_reactions=8,
            constructs=constructs,
            negative_template_count=3,
        )

        assert len(mm.dna_additions) == 5  # 2 constructs + 3 neg controls
        assert mm.max_dna_volume_ul > 0

    def test_master_mix_overage_percentage(self):
        """Test custom overage percentage."""
        mm_10 = calculate_master_mix(n_reactions=10, overage_percent=10.0)
        mm_20 = calculate_master_mix(n_reactions=10, overage_percent=20.0)

        assert mm_20.total_master_mix_volume_ul > mm_10.total_master_mix_volume_ul

    def test_calculate_total_wells(self):
        """Test total well calculation."""
        wells = calculate_total_wells(
            n_constructs=4,
            replicates_per_construct=4,
            negative_template_count=3,
            negative_dye_count=2,
        )
        # 4 × 4 + 3 + 2 = 21 wells
        assert wells == 21


class TestDNAStockConcentration:
    """Tests for variable DNA stock concentration handling (F4.13)."""

    def test_water_adjustment_for_different_stocks(self):
        """Test that water adjusts to normalize total addition volume."""
        constructs = [
            {'name': 'A', 'stock_concentration_ng_ul': 100.0},  # Low conc -> high DNA vol
            {'name': 'B', 'stock_concentration_ng_ul': 500.0},  # High conc -> low DNA vol
        ]

        additions, max_dna = calculate_dna_additions(
            dna_mass_ug=20.0,
            constructs=constructs,
        )

        # max_dna should be from construct A (lower concentration)
        assert additions[0].dna_volume_ul > additions[1].dna_volume_ul
        assert isclose(max_dna, additions[0].dna_volume_ul, rel_tol=1e-6)

        # Water adjustment for B should compensate
        assert additions[0].water_adjustment_ul == 0.0  # Reference, no adjustment
        assert additions[1].water_adjustment_ul > 0.0

        # Total additions should be equal
        assert isclose(
            additions[0].total_addition_ul,
            additions[1].total_addition_ul,
            rel_tol=1e-6
        )


class TestDNADilution:
    """Tests for DNA dilution calculator (F4.17)."""

    def test_simple_dilution(self):
        """Test simple 1:10 dilution."""
        protocol = calculate_simple_dilution(
            original_concentration_ng_ul=1000.0,
            target_concentration_ng_ul=100.0,
            stock_volume_ul=10.0,
        )

        assert protocol.dilution_factor == 10.0
        assert protocol.final_volume_ul == 100.0
        assert protocol.diluent_volume_ul == 90.0
        assert len(protocol.steps) >= 3

    def test_dilution_1_100(self):
        """Test 1:100 dilution."""
        protocol = calculate_simple_dilution(
            original_concentration_ng_ul=1000.0,
            target_concentration_ng_ul=10.0,
            stock_volume_ul=10.0,
        )

        assert protocol.dilution_factor == 100.0
        assert protocol.final_volume_ul == 1000.0

    def test_dilution_for_target_dna_volume(self):
        """Test dilution to achieve target pipetting volume."""
        # If current DNA volume is 0.3 µL, need to dilute to get 2.0 µL
        protocol = calculate_dilution_for_target_dna_volume(
            current_stock_ng_ul=1000.0,
            current_dna_volume_ul=0.3,
            target_dna_volume_ul=2.0,
        )

        # Dilution factor should be 2.0 / 0.3 = 6.67
        assert isclose(protocol.dilution_factor, 2.0 / 0.3, rel_tol=0.01)

    def test_serial_dilution_large_factor(self):
        """Test serial dilution for very large dilution factors."""
        protocol = calculate_serial_dilution(
            original_concentration_ng_ul=10000.0,
            target_concentration_ng_ul=1.0,
            max_single_dilution=100.0,
        )

        # Should require at least 2 steps for 10000-fold dilution
        assert len(protocol.dilutions) >= 2
        assert protocol.total_dilution_factor == 10000.0


class TestVolumeValidation:
    """Tests for volume validation (F4.15)."""

    def test_volume_below_minimum_invalid(self):
        """Test that volumes below 0.5 µL are invalid."""
        result = validate_volume(0.4, "test_volume")
        assert not result.is_valid
        assert len(result.errors) > 0

    def test_volume_warning_range(self):
        """Test that volumes 0.5-1.0 µL get warnings."""
        result = validate_volume(0.5, "test_volume")
        assert result.is_valid
        assert len(result.warnings) > 0

    def test_volume_ok_above_threshold(self):
        """Test that volumes ≥1.0 µL are OK."""
        result = validate_volume(1.5, "test_volume")
        assert result.is_valid
        assert len(result.warnings) == 0
        assert len(result.errors) == 0


class TestVolumeIntervention:
    """Tests for volume intervention recommendations (F4.25-F4.27)."""

    def test_no_intervention_needed(self):
        """Test when DNA volume is adequate."""
        intervention = recommend_dna_volume_intervention(
            dna_volume_ul=2.0,
            reaction_volume_ul=200.0,
            dna_stock_ng_ul=100.0,
        )

        assert not intervention.required
        assert intervention.intervention_type == InterventionType.NONE

    def test_warning_only(self):
        """Test warning when DNA volume is borderline."""
        intervention = recommend_dna_volume_intervention(
            dna_volume_ul=0.7,
            reaction_volume_ul=200.0,
            dna_stock_ng_ul=100.0,
        )

        assert not intervention.required
        assert intervention.intervention_type == InterventionType.WARNING
        assert intervention.warning is not None

    def test_intervention_required_dilution(self):
        """Test intervention required with dilution option."""
        intervention = recommend_dna_volume_intervention(
            dna_volume_ul=0.3,
            reaction_volume_ul=200.0,
            dna_stock_ng_ul=1000.0,
            dna_stock_available_ul=100.0,
        )

        assert intervention.required
        assert intervention.dilution_option is not None
        assert intervention.scaleup_option is not None
        assert intervention.recommended is not None

    def test_well_volume_split_required(self):
        """Test well splitting when volume exceeds maximum."""
        intervention = recommend_well_volume_intervention(
            reaction_volume_ul=200.0,
            plate_format=PlateFormat.WELL_384,
        )

        assert intervention.required
        assert intervention.intervention_type == InterventionType.SPLIT_WELLS
        assert intervention.split_option is not None
        assert intervention.split_option.wells_needed >= 3


class TestSplitWells:
    """Tests for split well calculations (F4.28-F4.30)."""

    def test_no_split_needed(self):
        """Test when volume fits in single well."""
        result = calculate_split_wells(50.0, max_well_volume_ul=80.0)
        assert result.wells_needed == 1
        assert len(result.volume_per_well) == 1

    def test_split_two_wells(self):
        """Test splitting into 2 wells."""
        result = calculate_split_wells(120.0, max_well_volume_ul=80.0)
        assert result.wells_needed == 2
        # Each well should be 60 µL
        assert all(isclose(v, 60.0, rel_tol=0.01) for v in result.volume_per_well)

    def test_split_three_wells(self):
        """Test splitting into 3 wells."""
        result = calculate_split_wells(200.0, max_well_volume_ul=80.0)
        assert result.wells_needed == 3
        # Total should equal original
        assert isclose(sum(result.volume_per_well), 200.0, rel_tol=0.01)


class TestValidators:
    """Tests for input validators."""

    def test_validate_reaction_parameters_valid(self):
        """Test valid reaction parameters."""
        result = validate_reaction_parameters(
            dna_mass_ug=20.0,
            n_replicates=4,
            n_constructs=4,
            negative_template_count=3,
            plate_format=PlateFormat.WELL_384,
        )
        assert result.is_valid

    def test_validate_reaction_parameters_low_replicates(self):
        """Test that replicates below 4 are rejected."""
        result = validate_reaction_parameters(
            dna_mass_ug=20.0,
            n_replicates=3,  # Below minimum
            n_constructs=4,
            negative_template_count=3,
        )
        assert not result.is_valid

    def test_validate_reaction_parameters_too_many_templates(self):
        """Test warning for >4 templates."""
        result = validate_reaction_parameters(
            dna_mass_ug=20.0,
            n_replicates=4,
            n_constructs=5,  # Above recommended
            negative_template_count=3,
        )
        assert result.is_valid  # Still valid, but has warning
        assert len(result.warnings) > 0

    def test_validate_construct_list_valid(self):
        """Test valid construct list."""
        constructs = [
            {'name': 'Reporter', 'stock_concentration_ng_ul': 100, 'is_unregulated': True},
            {'name': 'WT', 'stock_concentration_ng_ul': 100, 'is_wildtype': True, 'family': 'F1'},
            {'name': 'M1', 'stock_concentration_ng_ul': 100, 'family': 'F1'},
        ]
        result = validate_construct_list(constructs)
        assert result.is_valid

    def test_validate_construct_list_missing_unregulated(self):
        """Test that missing unregulated construct is flagged."""
        constructs = [
            {'name': 'WT', 'stock_concentration_ng_ul': 100, 'is_wildtype': True, 'family': 'F1'},
            {'name': 'M1', 'stock_concentration_ng_ul': 100, 'family': 'F1'},
        ]
        result = validate_construct_list(constructs, require_unregulated=True)
        assert not result.is_valid

    def test_validate_construct_list_missing_wt(self):
        """Test that mutants without WT are flagged."""
        constructs = [
            {'name': 'Reporter', 'stock_concentration_ng_ul': 100, 'is_unregulated': True},
            {'name': 'M1', 'stock_concentration_ng_ul': 100, 'family': 'F1'},  # No WT for F1
        ]
        result = validate_construct_list(constructs)
        assert not result.is_valid


class TestCheckerboardValidation:
    """Tests for 384-well checkerboard pattern (F4.32)."""

    def test_valid_checkerboard_positions(self):
        """Test valid checkerboard positions."""
        # A1 (0,0) -> 0+0=0 even, valid
        valid, msg = validate_checkerboard_position(0, 0)
        assert valid

        # B2 (1,1) -> 1+1=2 even, valid
        valid, msg = validate_checkerboard_position(1, 1)
        assert valid

        # A3 (0,2) -> 0+2=2 even, valid
        valid, msg = validate_checkerboard_position(0, 2)
        assert valid

    def test_invalid_checkerboard_positions(self):
        """Test invalid checkerboard positions."""
        # A2 (0,1) -> 0+1=1 odd, invalid
        valid, msg = validate_checkerboard_position(0, 1)
        assert not valid

        # B1 (1,0) -> 1+0=1 odd, invalid
        valid, msg = validate_checkerboard_position(1, 0)
        assert not valid


class TestProtocolGeneration:
    """Tests for protocol generation (F4.14, F4.16)."""

    def test_generate_protocol(self):
        """Test basic protocol generation."""
        constructs = [
            {'name': 'Reporter', 'stock_concentration_ng_ul': 100},
            {'name': 'WT', 'stock_concentration_ng_ul': 150},
        ]

        mm = calculate_master_mix(
            n_reactions=8,
            constructs=constructs,
            negative_template_count=3,
        )

        protocol = generate_protocol(mm, title="Test Protocol")

        assert protocol.title == "Test Protocol"
        assert len(protocol.steps) > 0
        assert protocol.calculation == mm

    def test_format_protocol_text(self):
        """Test protocol text formatting."""
        mm = calculate_master_mix(n_reactions=4)
        protocol = generate_protocol(mm)
        text = format_protocol_text(protocol)

        assert "MASTER MIX" in text.upper()
        assert "STEP" in text.upper()
        assert len(text) > 100

    def test_format_protocol_csv(self):
        """Test protocol CSV export."""
        mm = calculate_master_mix(n_reactions=4)
        protocol = generate_protocol(mm)
        csv = format_protocol_csv(protocol)

        # Should have header row
        assert "Step" in csv
        assert "Section" in csv
        assert "Action" in csv

        # Should have multiple lines
        lines = csv.strip().split('\n')
        assert len(lines) > 5


class TestMasterMixTable:
    """Tests for master mix table formatting."""

    def test_format_master_mix_table(self):
        """Test master mix table output."""
        mm = calculate_master_mix(n_reactions=10)
        table = format_master_mix_table(mm)

        assert "MASTER MIX" in table
        assert "10" in table  # n_reactions
        assert "Component" in table


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_zero_dna_concentration(self):
        """Test handling of zero DNA concentration."""
        dna_vol = calculate_dna_volume(20.0, 0.0)
        assert dna_vol == 0.0

    def test_very_small_dna_mass(self):
        """Test with very small DNA mass."""
        result = calculate_single_reaction_volumes(dna_mass_ug=0.1)
        assert result.reaction_volume_ul == 1.0  # 0.1 × 10

    def test_dilution_target_equals_original(self):
        """Test error when target equals original concentration."""
        with pytest.raises(ValueError):
            calculate_simple_dilution(
                original_concentration_ng_ul=100.0,
                target_concentration_ng_ul=100.0,
            )

    def test_dilution_target_greater_than_original(self):
        """Test error when target exceeds original concentration."""
        with pytest.raises(ValueError):
            calculate_simple_dilution(
                original_concentration_ng_ul=100.0,
                target_concentration_ng_ul=200.0,
            )

    def test_empty_construct_list(self):
        """Test validation with empty construct list."""
        result = validate_construct_list([])
        assert not result.is_valid

    def test_very_large_reaction_count(self):
        """Test with many reactions (stress test)."""
        mm = calculate_master_mix(n_reactions=96)
        assert mm.n_reactions == 96
        assert mm.total_master_mix_volume_ul > 0


class TestWellVolumeConstraints:
    """Tests for well volume constraints (F4.24)."""

    def test_384_well_constraints(self):
        """Test 384-well plate volume constraints."""
        constraints = PLATE_CONSTRAINTS[PlateFormat.WELL_384]
        assert constraints.min_well_volume_ul == 20.0
        assert constraints.max_well_volume_ul == 50.0

    def test_96_well_constraints(self):
        """Test 96-well plate volume constraints."""
        constraints = PLATE_CONSTRAINTS[PlateFormat.WELL_96]
        assert constraints.min_well_volume_ul == 100.0
        assert constraints.max_well_volume_ul == 250.0
