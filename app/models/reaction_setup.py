"""ReactionSetup models - IVT Reaction Calculator outputs."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TimestampMixin


class ReactionSetup(db.Model, TimestampMixin):
    """
    IVT Reaction Calculator output.

    Stores calculated volumes and protocol for setting up IVT reactions.
    Can optionally be linked to an experimental session after the experiment.
    """
    __tablename__ = "reaction_setups"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    created_by = Column(String(100), nullable=True)

    # Experimental design
    n_constructs = Column(Integer, nullable=False)
    n_replicates = Column(Integer, nullable=False)
    include_negative_template = Column(Boolean, default=True)
    n_negative_template = Column(Integer, default=3)
    include_negative_dye = Column(Boolean, default=False)
    n_negative_dye = Column(Integer, default=0)
    # Must match DEFAULT_OVERAGE_PERCENT in app/calculator/constants.py
    overage_percent = Column(Float, default=20.0)

    # DNA parameters
    dna_mass_ug = Column(Float, default=20.0)
    total_reaction_volume_ul = Column(Float, nullable=False)

    # NTP concentrations (mM)
    gtp_final_mm = Column(Float, default=6.0)
    gtp_stock_mm = Column(Float, default=467.3)
    atp_final_mm = Column(Float, default=5.0)
    atp_stock_mm = Column(Float, default=364.8)
    ctp_final_mm = Column(Float, default=5.0)
    ctp_stock_mm = Column(Float, default=343.3)
    utp_final_mm = Column(Float, default=5.0)
    utp_stock_mm = Column(Float, default=407.8)

    # Dye parameters (µM)
    dfhbi_final_um = Column(Float, default=100.0)
    dfhbi_stock_um = Column(Float, default=40000.0)

    # Calculated volumes stored as JSON
    master_mix_volumes = Column(JSON, nullable=True)
    total_master_mix_volume_ul = Column(Float, nullable=True)
    n_reactions = Column(Integer, nullable=True)
    master_mix_per_tube_ul = Column(Float, nullable=True)

    # Ligand workflow parameters
    ligand_stock_concentration_um = Column(Float, nullable=True)
    ligand_final_concentration_um = Column(Float, nullable=True)
    ligand_volume_per_rxn_ul = Column(Float, nullable=True)

    # Generated protocol text
    protocol_text = Column(Text, nullable=True)

    # Link to experimental session (optional)
    session_id = Column(Integer, ForeignKey("experimental_sessions.id"), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="reaction_setups")
    session = relationship("ExperimentalSession", back_populates="reaction_setups")
    dna_additions = relationship("ReactionDNAAddition", back_populates="reaction_setup", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ReactionSetup id={self.id} {self.name!r}>"


class ReactionDNAAddition(db.Model):
    """
    DNA addition for a reaction setup.

    Stores calculated volumes for adding DNA to each reaction tube.
    """
    __tablename__ = "reaction_dna_additions"

    id = Column(Integer, primary_key=True)
    reaction_setup_id = Column(Integer, ForeignKey("reaction_setups.id"), nullable=False)
    construct_id = Column(Integer, ForeignKey("constructs.id"), nullable=True)
    construct_name = Column(String(100), nullable=False)  # Stored for historical reference
    is_negative_control = Column(Boolean, default=False)
    negative_control_type = Column(String(50), nullable=True)  # 'no_template' or 'no_dye'

    # DNA stock info
    dna_stock_concentration_ng_ul = Column(Float, nullable=True)
    stock_concentration_nM = Column(Float, nullable=True)
    plasmid_size_bp = Column(Integer, nullable=True)
    achieved_nM = Column(Float, nullable=True)

    # Ligand condition (+Lig/-Lig/None)
    ligand_condition = Column(String(10), nullable=True)

    # Calculated volumes (µL)
    dna_volume_ul = Column(Float, nullable=False)
    water_adjustment_ul = Column(Float, nullable=False)
    total_addition_ul = Column(Float, nullable=False)

    # Relationships
    reaction_setup = relationship("ReactionSetup", back_populates="dna_additions")
    construct = relationship("Construct")

    def __repr__(self):
        return f"<ReactionDNAAddition id={self.id} {self.construct_name}>"
