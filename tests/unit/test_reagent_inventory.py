"""Unit tests for the per-project reagent inventory (model + service)."""
import pytest

from app.calculator.constants import STANDARD_COMPONENTS
from app.extensions import db
from app.models import Project, ReagentInventory
from app.models.project import PlateFormat
from app.models.reagent_inventory import COMPONENT_COLUMN_MAP, CONCENTRATION_FIELDS
from app.services.project_service import ProjectService
from app.services.reagent_inventory_service import ReagentInventoryService


def _expected_defaults() -> dict:
    """Stock/final defaults keyed by column name, derived from STANDARD_COMPONENTS."""
    expected = {}
    for comp in STANDARD_COMPONENTS:
        cols = COMPONENT_COLUMN_MAP.get(comp.name)
        if cols is None:
            continue
        stock_col, final_col = cols
        expected[stock_col] = comp.stock_concentration
        expected[final_col] = comp.final_concentration
    return expected


class TestReagentInventorySeeding:
    def test_create_project_seeds_inventory(self, db_session):
        """A project created through the service gets a default inventory."""
        project = ProjectService.create_project(
            name="Seeded Project", username="tester", plate_format=PlateFormat.PLATE_384
        )

        inv = project.reagent_inventory
        assert inv is not None
        assert inv.project_id == project.id
        for col, value in _expected_defaults().items():
            assert getattr(inv, col) == pytest.approx(value), col

    def test_seeded_values_match_standard_components(self, db_session):
        """Spot-check that the well-known NTP/buffer defaults are seeded."""
        project = ProjectService.create_project(name="Defaults Project", username="tester")
        inv = project.reagent_inventory

        assert inv.gtp_stock_mm == pytest.approx(467.3)
        assert inv.gtp_final_mm == pytest.approx(6.0)
        assert inv.atp_stock_mm == pytest.approx(364.8)
        assert inv.buffer_stock_x == pytest.approx(10.0)
        assert inv.buffer_final_x == pytest.approx(1.0)
        assert inv.mgcl2_stock_mm == pytest.approx(1000.0)
        assert inv.t7_stock_u_ul == pytest.approx(1.0)
        assert inv.t7_final_u_ul == pytest.approx(0.002)

    def test_column_defaults_match_standard_components(self, db_session):
        """Drift guard: bare-insert column defaults equal STANDARD_COMPONENTS.

        Catches divergence between the model's literal column defaults and the
        authoritative STANDARD_COMPONENTS values.
        """
        project = Project(name="Bare Insert", plate_format=PlateFormat.PLATE_384)
        db.session.add(project)
        db.session.flush()

        inv = ReagentInventory(project_id=project.id)  # rely on column defaults only
        db.session.add(inv)
        db.session.flush()

        for col, value in _expected_defaults().items():
            assert getattr(inv, col) == pytest.approx(value), col


class TestReagentInventoryService:
    def test_get_returns_none_when_absent(self, db_session):
        project = Project(name="No Inventory", plate_format=PlateFormat.PLATE_384)
        db.session.add(project)
        db.session.commit()

        assert ReagentInventoryService.get(project.id) is None

    def test_get_or_create_backfills_existing_project(self, db_session):
        """A project created without the service is back-filled lazily."""
        project = Project(name="Legacy Project", plate_format=PlateFormat.PLATE_384)
        db.session.add(project)
        db.session.commit()

        assert ReagentInventoryService.get(project.id) is None

        inv = ReagentInventoryService.get_or_create(project.id)
        assert inv is not None
        assert inv.gtp_stock_mm == pytest.approx(467.3)
        # Idempotent: a second call returns the same row, not a duplicate.
        again = ReagentInventoryService.get_or_create(project.id)
        assert again.id == inv.id
        assert ReagentInventory.query.filter_by(project_id=project.id).count() == 1

    def test_update_inventory_sets_fields(self, db_session):
        project = ProjectService.create_project(name="Update Project", username="tester")

        ReagentInventoryService.update_inventory(
            project.id, gtp_stock_mm=500.0, atp_stock_mm=380.0
        )

        inv = ReagentInventoryService.get(project.id)
        assert inv.gtp_stock_mm == pytest.approx(500.0)
        assert inv.atp_stock_mm == pytest.approx(380.0)

    def test_update_inventory_ignores_none(self, db_session):
        """None values (e.g. from empty Dash inputs) never overwrite existing data."""
        project = ProjectService.create_project(name="None Project", username="tester")
        original = ReagentInventoryService.get(project.id).gtp_stock_mm

        ReagentInventoryService.update_inventory(project.id, gtp_stock_mm=None)

        assert ReagentInventoryService.get(project.id).gtp_stock_mm == pytest.approx(original)

    def test_update_inventory_rejects_unknown_field(self, db_session):
        project = ProjectService.create_project(name="Bad Field Project", username="tester")

        with pytest.raises(ValueError, match="Unknown reagent inventory field"):
            ReagentInventoryService.update_inventory(project.id, not_a_real_field=1.0)

    def test_get_or_create_recovers_from_concurrent_insert(self, db_session, mocker):
        """If a concurrent writer inserts first, get_or_create returns that row.

        Simulates the race: our initial get() misses, create_default hits the
        unique constraint (because the row already exists), and we recover by
        re-fetching instead of propagating IntegrityError.
        """
        project = Project(name="Race Project", plate_format=PlateFormat.PLATE_384)
        db.session.add(project)
        db.session.commit()

        # Pre-existing row created by the "other" writer.
        existing = ReagentInventoryService.create_default(project.id, commit=True)

        # First get() misses (race), second get() (in the except branch) finds it.
        mocker.patch.object(
            ReagentInventoryService, "get", side_effect=[None, existing]
        )

        result = ReagentInventoryService.get_or_create(project.id)

        assert result is existing
        assert ReagentInventory.query.filter_by(project_id=project.id).count() == 1

    def test_update_inventory_backfills_then_updates(self, db_session):
        """update_inventory works even if the project had no inventory yet."""
        project = Project(name="Backfill Update", plate_format=PlateFormat.PLATE_384)
        db.session.add(project)
        db.session.commit()

        ReagentInventoryService.update_inventory(project.id, utp_stock_mm=410.0)

        inv = ReagentInventoryService.get(project.id)
        assert inv is not None
        assert inv.utp_stock_mm == pytest.approx(410.0)


def test_concentration_fields_cover_all_mapped_columns():
    """CONCENTRATION_FIELDS is exactly the flattened stock/final column pairs."""
    expected = {col for pair in COMPONENT_COLUMN_MAP.values() for col in pair}
    assert set(CONCENTRATION_FIELDS) == expected
    assert len(CONCENTRATION_FIELDS) == len(expected)  # no duplicates
