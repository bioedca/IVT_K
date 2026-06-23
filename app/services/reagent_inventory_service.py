"""Service for the per-project reagent inventory.

The reagent inventory is the single source of truth for every IVT component's
stock and final concentration. Both the calculator and the project settings screen
read and write through this service so the values stay consistent.

Defaults are seeded from :data:`app.calculator.constants.STANDARD_COMPONENTS` so the
calculator constants remain the one authoritative definition of the components and
their default concentrations.
"""

from app.calculator.constants import STANDARD_COMPONENTS
from app.extensions import db
from app.models.reagent_inventory import (
    COMPONENT_COLUMN_MAP,
    CONCENTRATION_FIELDS,
    ReagentInventory,
)


class ReagentInventoryService:
    """Create, read, and update a project's reagent inventory."""

    @staticmethod
    def _default_values() -> dict:
        """Build the default column values from STANDARD_COMPONENTS."""
        values: dict = {}
        for comp in STANDARD_COMPONENTS:
            cols = COMPONENT_COLUMN_MAP.get(comp.name)
            if cols is None:
                continue  # e.g. "Nuclease-free water" has no stock
            stock_col, final_col = cols
            values[stock_col] = comp.stock_concentration
            values[final_col] = comp.final_concentration
        return values

    @staticmethod
    def create_default(project_id: int, *, commit: bool = False) -> ReagentInventory:
        """Create a project's inventory seeded with the STANDARD_COMPONENTS defaults.

        Args:
            project_id: Project to attach the inventory to.
            commit: When True, commit the session. When False (the default), the row
                is flushed but not committed so it can share the caller's transaction
                (e.g. project creation).

        Returns:
            The newly created ReagentInventory.
        """
        inventory = ReagentInventory(
            project_id=project_id,
            **ReagentInventoryService._default_values(),
        )
        db.session.add(inventory)
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return inventory

    @staticmethod
    def get(project_id: int) -> ReagentInventory | None:
        """Return a project's inventory, or None if it has not been created yet."""
        return ReagentInventory.query.filter_by(project_id=project_id).first()

    @staticmethod
    def get_or_create(project_id: int) -> ReagentInventory:
        """Return a project's inventory, lazily seeding defaults if missing.

        This is the accessor every reader should use. It guarantees a row exists,
        which back-fills projects created before the inventory feature without a
        data migration.
        """
        inventory = ReagentInventoryService.get(project_id)
        if inventory is None:
            inventory = ReagentInventoryService.create_default(project_id, commit=True)
        return inventory

    @staticmethod
    def update_inventory(project_id: int, **fields) -> ReagentInventory:
        """Update concentration fields on a project's inventory and commit.

        Only known concentration columns (see CONCENTRATION_FIELDS) are accepted;
        unknown keys raise ValueError. None values are ignored so callers can pass
        raw Dash inputs without clobbering existing values with NULLs.

        Returns:
            The updated ReagentInventory.
        """
        inventory = ReagentInventoryService.get_or_create(project_id)
        for key, value in fields.items():
            if key not in CONCENTRATION_FIELDS:
                raise ValueError(f"Unknown reagent inventory field: {key!r}")
            if value is None:
                continue
            setattr(inventory, key, float(value))
        db.session.commit()
        return inventory
