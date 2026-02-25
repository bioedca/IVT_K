"""Family model - Groups constructs into families."""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TimestampMixin


class Family(db.Model, TimestampMixin):
    """
    A family of constructs (e.g., Tbox1, Tbox2).
    
    Each family has exactly one Wild-Type (WT) construct and multiple Mutants.
    Comparisons are primarily done within families (Mutant vs WT).
    """
    __tablename__ = "families"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Relationships
    project = relationship("Project", backref="families")
    constructs = relationship("Construct", back_populates="family_rel")
    
    # We might want relationships to wells/assignments too, but can add later if needed
    
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_family_project_name"),
    )

    def __repr__(self):
        return f"<Family id={self.id} {self.name!r}>"
