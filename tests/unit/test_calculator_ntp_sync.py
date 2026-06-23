"""Tests for the calculator NTP-stock inputs synced with the reagent inventory."""
from unittest.mock import MagicMock

import pytest

from app.callbacks.calculator_callbacks import (
    _master_mix_from_inventory,
    register_calculator_callbacks,
)
from app.layouts.calculator import create_calculator_layout
from app.models.reagent_inventory import CONCENTRATION_FIELDS
from app.services.project_service import ProjectService
from app.services.reagent_inventory_service import ReagentInventoryService


class _CaptureApp:
    """Fake Dash app that records @app.callback-decorated functions by name."""

    def __init__(self):
        self.funcs = {}

    def callback(self, *args, **kwargs):
        def decorator(func):
            self.funcs[func.__name__] = func
            return func
        return decorator

    def __getattr__(self, name):
        return MagicMock()


def _mgcl2(mm):
    return next(c for c in mm.components if c.name == "MgCl₂")


class TestConcentrationKwargs:
    def test_returns_all_fields_as_floats(self, db_session):
        project = ProjectService.create_project(name="Conc Project", username="tester")
        conc = ReagentInventoryService.concentration_kwargs(project.id)

        assert set(conc) == set(CONCENTRATION_FIELDS)
        assert all(isinstance(v, float) for v in conc.values())
        assert conc["gtp_stock_mm"] == pytest.approx(467.3)

    def test_reflects_inventory_edits(self, db_session):
        project = ProjectService.create_project(name="Conc Edit Project", username="tester")
        ReagentInventoryService.update_inventory(project.id, mgcl2_stock_mm=2000.0)
        assert ReagentInventoryService.concentration_kwargs(project.id)["mgcl2_stock_mm"] == 2000.0


class TestMasterMixFromInventory:
    def test_uses_inventory_concentrations(self, db_session):
        project = ProjectService.create_project(name="MM Project", username="tester")

        before = _master_mix_from_inventory(
            project.id, n_reactions=3, constructs=[], dna_mass_ug=20.0,
            negative_template_count=3, negative_dye_count=0,
            reaction_volume_ul=50.0, ligand_config=None,
        )
        assert _mgcl2(before).stock_concentration == pytest.approx(1000.0)

        ReagentInventoryService.update_inventory(project.id, mgcl2_stock_mm=2000.0)
        after = _master_mix_from_inventory(
            project.id, n_reactions=3, constructs=[], dna_mass_ug=20.0,
            negative_template_count=3, negative_dye_count=0,
            reaction_volume_ul=50.0, ligand_config=None,
        )
        assert _mgcl2(after).stock_concentration == pytest.approx(2000.0)
        assert _mgcl2(after).master_mix_volume_ul == pytest.approx(
            _mgcl2(before).master_mix_volume_ul / 2
        )


class TestLoadCalcNtpStocks:
    def test_prefills_from_inventory(self, db_session):
        app = _CaptureApp()
        register_calculator_callbacks(app)
        load = app.funcs["load_calc_ntp_stocks"]

        project = ProjectService.create_project(name="NTP Load Project", username="tester")
        ReagentInventoryService.update_inventory(project.id, gtp_stock_mm=480.0)

        gtp, atp, ctp, utp = load({"project_id": project.id})
        assert gtp == pytest.approx(480.0)
        assert atp == pytest.approx(364.8)
        assert (ctp, utp) == (pytest.approx(343.3), pytest.approx(407.8))


class TestCalculatorLayout:
    def test_layout_has_ntp_stock_inputs(self):
        layout_str = str(create_calculator_layout(1))
        for letter in ("gtp", "atp", "ctp", "utp"):
            assert f"calc-{letter}-stock-input" in layout_str
        assert "NTP stock concentrations" in layout_str
