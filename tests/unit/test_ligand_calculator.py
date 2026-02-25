"""Tests for ligand conditions in IVT calculator."""
import pytest
from app.calculator.reaction_calculator import (
    LigandConfig,
    DNAAddition,
    calculate_dna_additions,
    round_volume_up,
)
from app.calculator.master_mix import (
    calculate_master_mix,
    calculate_total_wells,
    calculate_total_reactions,
    MasterMixCalculation,
)
from app.calculator.protocol_generator import (
    generate_protocol,
    format_protocol_text,
)
from app.calculator.constants import (
    MAX_LIGAND_VOLUME_FRACTION,
    MIN_PIPETTABLE_VOLUME_UL,
    WARN_PIPETTABLE_VOLUME_UL,
)


class TestLigandConfig:
    """Tests for LigandConfig dataclass."""

    def test_default_config(self):
        cfg = LigandConfig()
        assert cfg.enabled is False
        assert cfg.stock_concentration_uM == 1000.0
        assert cfg.final_concentration_uM == 100.0

    def test_custom_config(self):
        cfg = LigandConfig(enabled=True, stock_concentration_uM=500.0, final_concentration_uM=50.0)
        assert cfg.enabled is True
        assert cfg.stock_concentration_uM == 500.0
        assert cfg.final_concentration_uM == 50.0


class TestLigandVolumeCalculation:
    """Tests for ligand volume computation."""

    def test_standard_volume(self):
        """100 µM final / 1000 µM stock * 40 µL rxn = 4 µL."""
        cfg = LigandConfig(enabled=True, stock_concentration_uM=1000.0, final_concentration_uM=100.0)
        vol = round_volume_up((cfg.final_concentration_uM * 40.0) / cfg.stock_concentration_uM)
        assert vol == 4.0

    def test_too_dilute_stock_error(self):
        """Very dilute stock → ligand volume exceeds 20% of V_rxn → error."""
        cfg = LigandConfig(enabled=True, stock_concentration_uM=10.0, final_concentration_uM=100.0)
        mm = calculate_master_mix(
            n_reactions=8,
            dna_mass_ug=4.0,
            constructs=[{"name": "C1", "stock_concentration_ng_ul": 1000, "replicates": 4}],
            reaction_volume_ul=40.0,
            ligand_config=cfg,
        )
        assert not mm.is_valid
        assert any("exceeds" in e for e in mm.errors)

    def test_too_concentrated_stock_warning(self):
        """Very concentrated stock → volume < 1 µL → error for below pipetting threshold."""
        # 10000 µM stock, 10 µM final, 40 µL rxn → 0.1 µL < 0.5 µL → error
        cfg = LigandConfig(enabled=True, stock_concentration_uM=10000.0, final_concentration_uM=10.0)
        mm = calculate_master_mix(
            n_reactions=8,
            dna_mass_ug=4.0,
            constructs=[{"name": "C1", "stock_concentration_ng_ul": 1000, "replicates": 4}],
            reaction_volume_ul=40.0,
            ligand_config=cfg,
        )
        assert not mm.is_valid
        assert any("below pipetting threshold" in e for e in mm.errors)

    def test_borderline_volume_warning(self):
        """Volume between 0.5 and 1.0 µL → warning but valid."""
        # 100 µM final / 5000 µM stock * 40 µL = 0.8 µL
        cfg = LigandConfig(enabled=True, stock_concentration_uM=5000.0, final_concentration_uM=100.0)
        mm = calculate_master_mix(
            n_reactions=8,
            dna_mass_ug=4.0,  # V_rxn = 4*10 = 40 µL, consistent
            constructs=[{"name": "C1", "stock_concentration_ng_ul": 1000, "replicates": 4}],
            reaction_volume_ul=40.0,
            ligand_config=cfg,
        )
        assert mm.is_valid
        assert any("accuracy" in w for w in mm.warnings)


class TestLigandDNAAdditions:
    """Tests for DNA additions with ligand duplication."""

    def test_additions_doubled_with_ligand(self):
        """With ligand enabled, each construct gets +Lig and -Lig additions."""
        cfg = LigandConfig(enabled=True, stock_concentration_uM=1000.0, final_concentration_uM=100.0)
        constructs = [
            {"name": "C1", "stock_concentration_ng_ul": 100, "replicates": 4},
        ]
        additions, max_vol = calculate_dna_additions(
            dna_mass_ug=4.0,
            constructs=constructs,
            negative_template_count=2,
            negative_dye_count=0,
            reaction_volume_ul=40.0,
            ligand_config=cfg,
        )
        # 1 construct + 2 controls = 3, doubled = 6
        assert len(additions) == 6

    def test_correct_ligand_labels(self):
        """Additions should have +Lig and -Lig labels."""
        cfg = LigandConfig(enabled=True, stock_concentration_uM=1000.0, final_concentration_uM=100.0)
        constructs = [
            {"name": "C1", "stock_concentration_ng_ul": 100, "replicates": 4},
        ]
        additions, _ = calculate_dna_additions(
            dna_mass_ug=4.0,
            constructs=constructs,
            negative_template_count=1,
            negative_dye_count=0,
            reaction_volume_ul=40.0,
            ligand_config=cfg,
        )
        conditions = [a.ligand_condition for a in additions]
        assert conditions.count("+Lig") == 2  # 1 construct + 1 control
        assert conditions.count("-Lig") == 2

    def test_minus_lig_gets_extra_water(self):
        """-Lig additions should have extra water replacing ligand volume."""
        cfg = LigandConfig(enabled=True, stock_concentration_uM=1000.0, final_concentration_uM=100.0)
        constructs = [
            {"name": "C1", "stock_concentration_ng_ul": 100, "replicates": 4},
        ]
        additions, _ = calculate_dna_additions(
            dna_mass_ug=4.0,
            constructs=constructs,
            negative_template_count=0,
            negative_dye_count=0,
            reaction_volume_ul=40.0,
            ligand_config=cfg,
        )
        plus_lig = [a for a in additions if a.ligand_condition == "+Lig"][0]
        minus_lig = [a for a in additions if a.ligand_condition == "-Lig"][0]
        ligand_vol = round_volume_up((100.0 * 40.0) / 1000.0)  # 4.0 µL
        assert minus_lig.water_adjustment_ul == pytest.approx(
            plus_lig.water_adjustment_ul + ligand_vol, abs=0.1
        )

    def test_backward_compatible_without_ligand(self):
        """Without ligand, additions should have no ligand_condition."""
        constructs = [
            {"name": "C1", "stock_concentration_ng_ul": 100, "replicates": 4},
        ]
        additions, _ = calculate_dna_additions(
            dna_mass_ug=4.0,
            constructs=constructs,
            negative_template_count=2,
            reaction_volume_ul=40.0,
        )
        assert all(a.ligand_condition is None for a in additions)
        assert len(additions) == 3  # 1 construct + 2 controls


class TestLigandMasterMix:
    """Tests for master mix with ligand configuration."""

    def test_ligand_only_two_tube_split(self):
        """Ligand-only workflow should produce a valid master mix."""
        cfg = LigandConfig(enabled=True, stock_concentration_uM=1000.0, final_concentration_uM=100.0)
        constructs = [
            {"name": "C1", "stock_concentration_ng_ul": 1000, "replicates": 4},
        ]
        mm = calculate_master_mix(
            n_reactions=8,  # 4 +Lig + 4 -Lig (doubled by caller)
            dna_mass_ug=4.0,
            constructs=constructs,
            negative_template_count=0,
            reaction_volume_ul=40.0,
            ligand_config=cfg,
        )
        assert mm.is_valid
        assert mm.is_ligand_workflow
        assert mm.ligand_volume_per_rxn_ul == 4.0
        # DNA additions should be doubled: (1 construct) * 2 = 2 (no neg_template)
        assert len(mm.dna_additions) == 2

    def test_ligand_plus_dfhbi_four_tube_split(self):
        """Ligand + DFHBI workflow should produce a valid master mix."""
        cfg = LigandConfig(enabled=True, stock_concentration_uM=1000.0, final_concentration_uM=100.0)
        constructs = [
            {"name": "Reporter", "stock_concentration_ng_ul": 1000, "replicates": 4, "is_unregulated": True},
        ]
        mm = calculate_master_mix(
            n_reactions=16,  # (4 + 2 + 2) * 2 = 16 doubled by caller
            dna_mass_ug=4.0,
            constructs=constructs,
            negative_template_count=2,
            negative_dye_count=2,
            reaction_volume_ul=40.0,
            ligand_config=cfg,
        )
        assert mm.is_valid
        assert mm.is_ligand_workflow
        # Both ligand and DFHBI conditions present
        has_plus_lig = any(a.ligand_condition == "+Lig" for a in mm.dna_additions)
        has_minus_lig = any(a.ligand_condition == "-Lig" for a in mm.dna_additions)
        assert has_plus_lig and has_minus_lig

    def test_negative_water_error(self):
        """When ligand volume is too large relative to reaction, water goes negative."""
        # 200 µM final / 250 µM stock * 40 µL = 32 µL → exceeds 20% of V_rxn
        cfg = LigandConfig(enabled=True, stock_concentration_uM=250.0, final_concentration_uM=200.0)
        mm = calculate_master_mix(
            n_reactions=4,
            dna_mass_ug=4.0,
            constructs=[{"name": "C1", "stock_concentration_ng_ul": 1000, "replicates": 2}],
            reaction_volume_ul=40.0,
            ligand_config=cfg,
        )
        # Should have an error about exceeding fraction limit
        assert not mm.is_valid


class TestLigandProtocol:
    """Tests for protocol generation with ligand."""

    def test_protocol_has_ligand_split_section(self):
        """Protocol should include Ligand Split section."""
        cfg = LigandConfig(enabled=True, stock_concentration_uM=1000.0, final_concentration_uM=100.0)
        constructs = [
            {"name": "C1", "stock_concentration_ng_ul": 100, "replicates": 4},
        ]
        mm = calculate_master_mix(
            n_reactions=8,
            constructs=constructs,
            negative_template_count=2,
            reaction_volume_ul=40.0,
            ligand_config=cfg,
        )
        protocol = generate_protocol(mm)
        sections = {step.section for step in protocol.steps}
        assert "Ligand Split" in sections

    def test_tube_labels_include_condition(self):
        """DNA addition tube labels should include (+Lig) or (-Lig)."""
        cfg = LigandConfig(enabled=True, stock_concentration_uM=1000.0, final_concentration_uM=100.0)
        constructs = [
            {"name": "C1", "stock_concentration_ng_ul": 100, "replicates": 2},
        ]
        mm = calculate_master_mix(
            n_reactions=4,
            constructs=constructs,
            negative_template_count=0,
            reaction_volume_ul=40.0,
            ligand_config=cfg,
        )
        protocol = generate_protocol(mm)
        dna_steps = [s for s in protocol.steps if s.section == "DNA Addition"]
        destinations = [s.destination for s in dna_steps]
        assert any("(+Lig)" in d for d in destinations)
        assert any("(-Lig)" in d for d in destinations)

    def test_text_format_shows_ligand_info(self):
        """Text protocol should show ligand info in summary."""
        cfg = LigandConfig(enabled=True, stock_concentration_uM=1000.0, final_concentration_uM=100.0)
        constructs = [
            {"name": "C1", "stock_concentration_ng_ul": 100, "replicates": 4},
        ]
        mm = calculate_master_mix(
            n_reactions=8,
            constructs=constructs,
            negative_template_count=2,
            reaction_volume_ul=40.0,
            ligand_config=cfg,
        )
        protocol = generate_protocol(mm)
        text = format_protocol_text(protocol)
        assert "Ligand: 100 µM final" in text
        assert "1000 µM stock" in text

    def test_no_ligand_section_when_disabled(self):
        """Protocol should NOT have Ligand Split section when not enabled."""
        constructs = [
            {"name": "C1", "stock_concentration_ng_ul": 100, "replicates": 4},
        ]
        mm = calculate_master_mix(
            n_reactions=4,
            constructs=constructs,
            negative_template_count=2,
            reaction_volume_ul=40.0,
        )
        protocol = generate_protocol(mm)
        sections = {step.section for step in protocol.steps}
        assert "Ligand Split" not in sections


class TestLigandWellCounting:
    """Tests for well counting with ligand multiplier."""

    def test_wells_doubled(self):
        """calculate_total_wells with ligand_multiplier=2 should double."""
        base = calculate_total_wells(3, 4, negative_template_count=2, negative_dye_count=0)
        doubled = calculate_total_wells(3, 4, negative_template_count=2, negative_dye_count=0, ligand_multiplier=2)
        assert doubled == base * 2

    def test_reactions_doubled(self):
        """calculate_total_reactions with ligand_multiplier=2 should double."""
        constructs = [
            {"name": "C1", "replicates": 4},
            {"name": "C2", "replicates": 4},
        ]
        base = calculate_total_reactions(constructs, negative_template_count=2)
        doubled = calculate_total_reactions(constructs, negative_template_count=2, ligand_multiplier=2)
        assert doubled == base * 2

    def test_no_multiplier_unchanged(self):
        """Default ligand_multiplier=1 should not change well count."""
        base = calculate_total_wells(3, 4, negative_template_count=2)
        same = calculate_total_wells(3, 4, negative_template_count=2, ligand_multiplier=1)
        assert base == same


class TestNMRounding:
    """Tests for achieved nM computation."""

    def test_achieved_nM_computed(self):
        """When using nM path, achieved_nM should be set."""
        constructs = [
            {
                "name": "C1",
                "stock_concentration_ng_ul": 100,
                "plasmid_size_bp": 5000,
                "replicates": 4,
            },
        ]
        additions, _ = calculate_dna_additions(
            dna_mass_ug=4.0,
            constructs=constructs,
            reaction_volume_ul=40.0,
            target_dna_nM=50.0,
        )
        # First addition should have achieved_nM
        assert additions[0].achieved_nM is not None
        # achieved_nM should be >= 50.0 (due to rounding up)
        assert additions[0].achieved_nM >= 50.0

    def test_achieved_nM_none_for_mass_path(self):
        """When using mass-based path (no plasmid_size_bp), achieved_nM should be None."""
        constructs = [
            {
                "name": "C1",
                "stock_concentration_ng_ul": 100,
                "replicates": 4,
            },
        ]
        additions, _ = calculate_dna_additions(
            dna_mass_ug=4.0,
            constructs=constructs,
            reaction_volume_ul=40.0,
            target_dna_nM=50.0,
        )
        assert additions[0].achieved_nM is None

    def test_achieved_nM_in_protocol(self):
        """Protocol text should include 'Achieved:' when nM data is present."""
        constructs = [
            {
                "name": "C1",
                "stock_concentration_ng_ul": 100,
                "plasmid_size_bp": 5000,
                "replicates": 4,
            },
        ]
        mm = calculate_master_mix(
            n_reactions=4,
            constructs=constructs,
            negative_template_count=0,
            reaction_volume_ul=40.0,
            target_dna_nM=50.0,
        )
        protocol = generate_protocol(mm)
        text = format_protocol_text(protocol)
        assert "Achieved:" in text
