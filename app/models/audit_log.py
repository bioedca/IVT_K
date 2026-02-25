"""AuditLog and UserSession models - audit trail and user tracking."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.extensions import db


class AuditLog(db.Model):
    """
    Audit log entry for tracking all significant actions.

    Records field-level changes for full traceability and compliance.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    username = Column(String(100), nullable=False)
    action_type = Column(String(50), nullable=False)  # 'create', 'update', 'delete', etc.
    entity_type = Column(String(50), nullable=False)  # 'project', 'construct', etc.
    entity_id = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Field-level change tracking
    changes = Column(JSON, nullable=True)  # List of {"field": ..., "old": ..., "new": ...}
    details = Column(JSON, nullable=True)  # Action-specific context

    # Relationships
    project = relationship("Project")

    def __repr__(self):
        return f"<AuditLog id={self.id} {self.action_type} {self.entity_type}:{self.entity_id}>"

    @classmethod
    def log_action(
        cls,
        username: str,
        action_type: str,
        entity_type: str,
        entity_id: int,
        project_id: int = None,
        changes: list = None,
        details: dict = None
    ) -> "AuditLog":
        """
        Create and return a new audit log entry.

        Args:
            username: User who performed the action
            action_type: Type of action ('create', 'update', 'delete', etc.)
            entity_type: Type of entity affected
            entity_id: ID of the affected entity
            project_id: Optional project ID for context
            changes: List of field changes
            details: Additional context
        """
        log = cls(
            username=username,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            project_id=project_id,
            changes=changes,
            details=details
        )
        db.session.add(log)
        return log


class UserSession(db.Model):
    """
    Lightweight user session tracking.

    Tracks the most recent username for convenience (auto-fill in forms).
    Does not provide authentication.
    """
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    current_project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)

    # Relationships
    current_project = relationship("Project")

    def __repr__(self):
        return f"<UserSession id={self.id} {self.username}>"

    @classmethod
    def get_or_create(cls, username: str) -> "UserSession":
        """Get existing session or create new one for username."""
        session = cls.query.filter_by(username=username).first()
        if not session:
            session = cls(username=username)
            db.session.add(session)
        return session
