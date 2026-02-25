"""MethodsText model - auto-generated methods section text."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.extensions import db


class MethodsText(db.Model):
    """
    Auto-generated and user-edited methods text with diff tracking.

    Stores the methods section text that can be included in publications,
    with tracking of user edits.
    """
    __tablename__ = "methods_texts"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), unique=True, nullable=False)
    original_text = Column(Text, nullable=False)
    edited_text = Column(Text, nullable=False)
    diff_text = Column(Text, nullable=True)
    edited_at = Column(DateTime, nullable=True)
    edited_by = Column(String(100), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="methods_text")

    def __repr__(self):
        edited = " [edited]" if self.edited_at else ""
        return f"<MethodsText id={self.id} project={self.project_id}{edited}>"

    @property
    def is_edited(self) -> bool:
        """Check if the text has been edited from original."""
        return self.original_text != self.edited_text
