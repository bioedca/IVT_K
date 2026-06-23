"""ReagentInventory model - per-project reagent stock/final concentrations.

This is the single source of truth for the stock and final (target) concentrations
of every IVT reaction component. The reaction calculator and the project settings
screen both read from and write to this one row per project, so a scientist who
opens a new reagent lot (a different certified stock concentration) records it once
and every calculation uses it.

Default concentrations are derived from
:data:`app.calculator.constants.STANDARD_COMPONENTS` (the authoritative defaults);
the column-level defaults below mirror those values and are kept honest by a unit
test. Units are fixed per column (encoded in the column name): X for buffer,
mM for MgCl2/NTPs, uM for DFHBI, U/uL for enzymes.
"""
from sqlalchemy import Column, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TimestampMixin

# Maps app.calculator.constants ReactionComponent.name -> (stock_column, final_column)
# on this model. The "Nuclease-free water" component has no stock and is excluded.
# This bridge keeps STANDARD_COMPONENTS authoritative for seeding (see
# ReagentInventoryService.create_default).
COMPONENT_COLUMN_MAP = {
    "10X Reaction buffer": ("buffer_stock_x", "buffer_final_x"),
    "MgCl₂": ("mgcl2_stock_mm", "mgcl2_final_mm"),
    "GTP": ("gtp_stock_mm", "gtp_final_mm"),
    "ATP": ("atp_stock_mm", "atp_final_mm"),
    "CTP": ("ctp_stock_mm", "ctp_final_mm"),
    "UTP": ("utp_stock_mm", "utp_final_mm"),
    "DFHBI dye": ("dfhbi_stock_um", "dfhbi_final_um"),
    "Pyrophosphatase": ("ppi_stock_u_ul", "ppi_final_u_ul"),
    "RNAsin": ("rnasin_stock_u_ul", "rnasin_final_u_ul"),
    "T7 RNA Polymerase": ("t7_stock_u_ul", "t7_final_u_ul"),
}

# Flat list of every editable concentration column (stock + final, all components).
# Used to validate field names passed to ReagentInventoryService.update_inventory.
CONCENTRATION_FIELDS: tuple[str, ...] = tuple(
    col for pair in COMPONENT_COLUMN_MAP.values() for col in pair
)


class ReagentInventory(db.Model, TimestampMixin):
    """Per-project stock + final concentrations for all IVT reaction components.

    Exactly one row per project (``project_id`` is unique). Created with defaults
    when a project is created and lazily back-filled for pre-existing projects via
    :meth:`ReagentInventoryService.get_or_create`.
    """
    __tablename__ = "reagent_inventories"

    # Named to match the migration's UniqueConstraint, so the create_all() path
    # (tests) and the Alembic path (production) declare uniqueness identically.
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_reagent_inventories_project_id"),
    )

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    # 10X Reaction buffer (X)
    buffer_stock_x = Column(Float, nullable=False, default=10.0)
    buffer_final_x = Column(Float, nullable=False, default=1.0)

    # MgCl2 (mM)
    mgcl2_stock_mm = Column(Float, nullable=False, default=1000.0)
    mgcl2_final_mm = Column(Float, nullable=False, default=10.0)

    # NTPs (mM) - lot-specific stock concentrations from the certificate of analysis
    gtp_stock_mm = Column(Float, nullable=False, default=467.3)
    gtp_final_mm = Column(Float, nullable=False, default=6.0)
    atp_stock_mm = Column(Float, nullable=False, default=364.8)
    atp_final_mm = Column(Float, nullable=False, default=5.0)
    ctp_stock_mm = Column(Float, nullable=False, default=343.3)
    ctp_final_mm = Column(Float, nullable=False, default=5.0)
    utp_stock_mm = Column(Float, nullable=False, default=407.8)
    utp_final_mm = Column(Float, nullable=False, default=5.0)

    # DFHBI dye (uM)
    dfhbi_stock_um = Column(Float, nullable=False, default=40000.0)
    dfhbi_final_um = Column(Float, nullable=False, default=100.0)

    # Enzymes (U/uL)
    ppi_stock_u_ul = Column(Float, nullable=False, default=0.1)
    ppi_final_u_ul = Column(Float, nullable=False, default=0.0008)
    rnasin_stock_u_ul = Column(Float, nullable=False, default=40.0)
    rnasin_final_u_ul = Column(Float, nullable=False, default=0.16)
    t7_stock_u_ul = Column(Float, nullable=False, default=1.0)
    t7_final_u_ul = Column(Float, nullable=False, default=0.002)

    # Relationships
    project = relationship("Project", back_populates="reagent_inventory")

    def __repr__(self):
        return f"<ReagentInventory id={self.id} project={self.project_id}>"
