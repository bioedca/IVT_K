"""ProjectArchive model - archived project tracking."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.extensions import db


class ProjectArchive(db.Model):
    """
    Tracks archived projects for cold storage management.

    When a project is archived, its files are compressed and stored,
    with database records retained for reference.
    """
    __tablename__ = "project_archives"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), unique=True, nullable=False)
    archive_path = Column(String(500), nullable=False)
    archived_at = Column(DateTime, default=datetime.utcnow)
    archived_by = Column(String(100), nullable=False)
    original_size_bytes = Column(Integer, nullable=False)
    compressed_size_bytes = Column(Integer, nullable=False)
    restored_at = Column(DateTime, nullable=True)
    restored_by = Column(String(100), nullable=True)

    # Relationships
    project = relationship("Project")

    def __repr__(self):
        status = "restored" if self.restored_at else "archived"
        return f"<ProjectArchive id={self.id} project={self.project_id} [{status}]>"

    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio."""
        if self.original_size_bytes > 0:
            return self.compressed_size_bytes / self.original_size_bytes
        return 1.0

    @property
    def is_restored(self) -> bool:
        """Check if project has been restored."""
        return self.restored_at is not None
