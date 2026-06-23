"""Tests for concentration-driven buffer/MgCl₂/enzyme volumes.

PR2 converts buffer, MgCl₂ and the three enzymes from hardcoded volumes (the
enzymes used a fixed V_rxn × factor / 200 ratio) to true concentration-driven
math V = C_final × V_rxn / C_stock. These tests assert the change is
behavior-preserving at the default concentrations and that a non-default stock
moves the pipetted volume the way C1V1 = C2V2 requires.
"""
import pytest

from app.calculator import (
    calculate_buffer_volume,
    calculate_component_volume,
    calculate_enzyme_volume,
    calculate_master_mix,
    calculate_single_reaction_volumes,
)

V = 50.0  # reaction volume (µL) chosen for clean arithmetic


def _components(**kwargs):
    """Return {name: volume_ul} for a single (unrounded) reaction."""
    single = calculate_single_reaction_volumes(
        reaction_volume_ul=V, round_result=False, **kwargs
    )
    return {c.name: c.volume_ul for c in single.components}


def test_buffer_volume_zero_stock_guard():
    """A zero buffer stock returns 0 instead of dividing by zero."""
    assert calculate_buffer_volume(V, stock_x=0) == 0.0


class TestDefaultEquivalence:
    """Defaults reproduce the historical volumes exactly (no-op at defaults)."""

    def test_buffer_and_mgcl2_match_legacy_formula(self):
        vols = _components()
        assert vols["10X Reaction buffer"] == pytest.approx(calculate_buffer_volume(V))
        assert vols["MgCl₂"] == pytest.approx(calculate_component_volume(V, 10.0, 1000.0))

    @pytest.mark.parametrize(
        ("name", "factor"),
        [
            ("Pyrophosphatase", 1.6),
            ("RNAsin", 0.8),
            ("T7 RNA Polymerase", 0.4),
        ],
    )
    def test_enzyme_matches_legacy_fixed_ratio(self, name, factor):
        """Concentration math equals the old V_rxn × factor / 200 at defaults."""
        vols = _components()
        assert vols[name] == pytest.approx(calculate_enzyme_volume(V, factor))

    def test_known_default_volumes(self):
        vols = _components()
        assert vols["10X Reaction buffer"] == pytest.approx(5.0)   # 50 × 1/10
        assert vols["MgCl₂"] == pytest.approx(0.5)                 # 50 × 10/1000
        assert vols["Pyrophosphatase"] == pytest.approx(0.4)      # 50 × 0.0008/0.1
        assert vols["RNAsin"] == pytest.approx(0.2)               # 50 × 0.16/40
        assert vols["T7 RNA Polymerase"] == pytest.approx(0.1)    # 50 × 0.002/1.0


class TestStockVariation:
    """A different stock changes the pipetted volume per C1V1 = C2V2."""

    def test_double_mgcl2_stock_halves_volume(self):
        base = _components()["MgCl₂"]
        doubled = _components(mgcl2_stock_mm=2000.0)["MgCl₂"]
        assert doubled == pytest.approx(base / 2)

    def test_double_t7_stock_halves_volume(self):
        base = _components()["T7 RNA Polymerase"]
        doubled = _components(t7_stock_u_ul=2.0)["T7 RNA Polymerase"]
        assert doubled == pytest.approx(base / 2)

    def test_half_buffer_stock_doubles_volume(self):
        # The buffer label reflects the stock, so a 5X stock is "5X Reaction buffer".
        base = _components()["10X Reaction buffer"]
        halved = _components(buffer_stock_x=5.0)["5X Reaction buffer"]
        assert halved == pytest.approx(base * 2)

    def test_buffer_label_reflects_stock(self):
        assert "10X Reaction buffer" in _components()  # default unchanged
        assert "5X Reaction buffer" in _components(buffer_stock_x=5.0)

    def test_ppi_and_rnasin_scale_with_stock(self):
        assert _components(ppi_stock_u_ul=0.2)["Pyrophosphatase"] == pytest.approx(0.2)
        assert _components(rnasin_stock_u_ul=20.0)["RNAsin"] == pytest.approx(0.4)

    def test_component_records_passed_stock_concentration(self):
        single = calculate_single_reaction_volumes(
            reaction_volume_ul=V, round_result=False, mgcl2_stock_mm=750.0
        )
        mgcl2 = next(c for c in single.components if c.name == "MgCl₂")
        assert mgcl2.stock_concentration == pytest.approx(750.0)


class TestMasterMixThreading:
    """calculate_master_mix forwards the new params to the per-reaction math."""

    def _mm_component(self, name, **kwargs):
        mm = calculate_master_mix(
            n_reactions=10, overage_percent=0.0, reaction_volume_ul=V, **kwargs
        )
        return next(c for c in mm.components if c.name == name)

    def test_default_mgcl2_master_mix_volume(self):
        comp = self._mm_component("MgCl₂")
        # single 0.5 µL × 10 reactions = 5.0 µL
        assert comp.master_mix_volume_ul == pytest.approx(5.0)
        assert comp.stock_concentration == pytest.approx(1000.0)

    def test_nondefault_mgcl2_stock_changes_master_mix_volume(self):
        comp = self._mm_component("MgCl₂", mgcl2_stock_mm=2000.0)
        # single 0.25 µL × 10 reactions = 2.5 µL
        assert comp.master_mix_volume_ul == pytest.approx(2.5)
        assert comp.stock_concentration == pytest.approx(2000.0)

    def test_nondefault_t7_stock_changes_master_mix_volume(self):
        default = self._mm_component("T7 RNA Polymerase")
        changed = self._mm_component("T7 RNA Polymerase", t7_stock_u_ul=2.0)
        assert changed.master_mix_volume_ul == pytest.approx(default.master_mix_volume_ul / 2)


class TestServiceReadsInventory:
    """CalculatorService.calculate_reaction_setup sources stocks from the inventory."""

    def _mgcl2(self, mm):
        return next(c for c in mm.components if c.name == "MgCl₂")

    def test_service_uses_inventory_stock(self, db_session):
        from app.services.project_service import ProjectService
        from app.services.reaction_calculator_service import CalculatorService
        from app.services.reagent_inventory_service import ReagentInventoryService

        project = ProjectService.create_project(name="Inv Calc Project", username="tester")

        # Default inventory -> default MgCl₂ stock.
        before = CalculatorService.calculate_reaction_setup(
            project.id, construct_ids=[], negative_template_count=3
        )
        assert self._mgcl2(before).stock_concentration == pytest.approx(1000.0)

        # Editing the inventory flows straight into the next calculation.
        ReagentInventoryService.update_inventory(project.id, mgcl2_stock_mm=2000.0)
        after = CalculatorService.calculate_reaction_setup(
            project.id, construct_ids=[], negative_template_count=3
        )
        comp_before = self._mgcl2(before)
        comp_after = self._mgcl2(after)
        assert comp_after.stock_concentration == pytest.approx(2000.0)
        assert comp_after.master_mix_volume_ul == pytest.approx(
            comp_before.master_mix_volume_ul / 2
        )
