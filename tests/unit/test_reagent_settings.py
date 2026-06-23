"""Tests for the Settings reagent-inventory editor (layout + callbacks)."""
from unittest.mock import MagicMock

import pytest

from app.callbacks.project_callbacks import register_project_callbacks
from app.layouts.project_settings import create_project_settings_layout
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

    def __getattr__(self, name):  # tolerate clientside_callback etc.
        return MagicMock()


class TestReagentSettingsLayout:
    def test_layout_has_every_reagent_input(self):
        layout_str = str(create_project_settings_layout(1))
        for col in CONCENTRATION_FIELDS:
            assert f"settings-reagent-{col}" in layout_str, col

    def test_layout_has_reagents_tab_and_save_button(self):
        layout_str = str(create_project_settings_layout(1))
        assert "Reagents" in layout_str
        assert "settings-reagents-save-btn" in layout_str
        assert "settings-reagents-notification" in layout_str


class TestReagentSettingsCallbacks:
    def _callbacks(self):
        app = _CaptureApp()
        register_project_callbacks(app)
        return app.funcs

    def test_load_prefills_from_inventory(self, db_session):
        funcs = self._callbacks()
        load = funcs["load_reagent_inventory"]

        project = ProjectService.create_project(name="Load Project", username="tester")
        values = load({"project_id": project.id})

        inv = ReagentInventoryService.get(project.id)
        assert values == [getattr(inv, col) for col in CONCENTRATION_FIELDS]

    def test_save_persists_edits(self, db_session):
        funcs = self._callbacks()
        save = funcs["save_reagent_inventory"]
        load = funcs["load_reagent_inventory"]

        project = ProjectService.create_project(name="Save Project", username="tester")
        values = list(load({"project_id": project.id}))
        values[CONCENTRATION_FIELDS.index("gtp_stock_mm")] = 500.0
        values[CONCENTRATION_FIELDS.index("mgcl2_stock_mm")] = 1200.0

        save(1, {"project_id": project.id}, *values)

        inv = ReagentInventoryService.get(project.id)
        assert inv.gtp_stock_mm == pytest.approx(500.0)
        assert inv.mgcl2_stock_mm == pytest.approx(1200.0)

    def test_save_ignores_blank_inputs(self, db_session):
        funcs = self._callbacks()
        save = funcs["save_reagent_inventory"]

        project = ProjectService.create_project(name="Blank Project", username="tester")
        original = ReagentInventoryService.get(project.id).gtp_stock_mm

        # All-None (e.g. tab never populated) must not overwrite stored values.
        save(1, {"project_id": project.id}, *([None] * len(CONCENTRATION_FIELDS)))

        assert ReagentInventoryService.get(project.id).gtp_stock_mm == pytest.approx(original)
