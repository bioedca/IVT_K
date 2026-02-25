"""
Conflict detection service for concurrent edit handling.

Phase 1.12: Concurrent edit detection (updated_at tracking)

Implements the "last-write-wins with warning" strategy:
- When loading an entity, capture the updated_at timestamp
- Before saving, check if updated_at has changed
- If changed, warn the user and offer options: overwrite, reload, or cancel
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, TypeVar, Generic
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import inspect
from app.extensions import db


class ConflictResolution(Enum):
    """Options for resolving edit conflicts."""
    OVERWRITE = "overwrite"  # Discard other changes, save mine
    RELOAD = "reload"        # Discard my changes, load current
    CANCEL = "cancel"        # Abort the save operation


@dataclass
class ConflictInfo:
    """Information about a detected conflict."""
    entity_type: str
    entity_id: int
    loaded_at: datetime
    current_updated_at: datetime
    other_user: Optional[str]
    field_changes: Dict[str, Tuple[Any, Any]]  # field -> (old_value, new_value)

    @property
    def has_conflict(self) -> bool:
        """Check if there is a conflict."""
        return self.current_updated_at > self.loaded_at

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "loaded_at": self.loaded_at.isoformat() if self.loaded_at else None,
            "current_updated_at": self.current_updated_at.isoformat() if self.current_updated_at else None,
            "other_user": self.other_user,
            "field_changes": {
                k: {"old": str(v[0]), "new": str(v[1])}
                for k, v in self.field_changes.items()
            },
            "has_conflict": self.has_conflict
        }


class ConflictDetectionService:
    """
    Service for detecting and handling concurrent edit conflicts.

    Usage:
        1. When loading an entity for editing, call track_entity_load()
        2. Before saving changes, call check_for_conflict()
        3. If conflict detected, present user with ConflictResolution options
        4. Call resolve_conflict() with user's choice
    """

    # In-memory tracking of loaded entities (session-scoped)
    # In a multi-user scenario, this would need to be stored differently
    _loaded_entities: Dict[str, Dict[str, datetime]] = {}

    @classmethod
    def track_entity_load(cls, entity_type: str, entity_id: int,
                          updated_at: datetime, session_id: str = "default") -> None:
        """
        Track when an entity was loaded for editing.

        Args:
            entity_type: Type of entity (e.g., "project", "construct")
            entity_id: ID of the entity
            updated_at: The updated_at timestamp when loaded
            session_id: Unique identifier for the editing session
        """
        key = f"{entity_type}:{entity_id}"
        if session_id not in cls._loaded_entities:
            cls._loaded_entities[session_id] = {}
        cls._loaded_entities[session_id][key] = updated_at

    @classmethod
    def get_loaded_timestamp(cls, entity_type: str, entity_id: int,
                             session_id: str = "default") -> Optional[datetime]:
        """
        Get the timestamp when an entity was loaded.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            session_id: Editing session identifier

        Returns:
            The loaded timestamp, or None if not tracked
        """
        key = f"{entity_type}:{entity_id}"
        session_data = cls._loaded_entities.get(session_id, {})
        return session_data.get(key)

    @classmethod
    def check_for_conflict(cls, entity, loaded_at: datetime,
                           original_state: dict = None) -> Optional[ConflictInfo]:
        """
        Check if an entity has been modified since it was loaded.

        Args:
            entity: The SQLAlchemy model instance
            loaded_at: When the entity was loaded for editing
            original_state: Optional dict of original field values

        Returns:
            ConflictInfo if conflict detected, None otherwise
        """
        # Get the entity's table name and ID
        mapper = inspect(entity.__class__)
        entity_type = mapper.mapped_table.name
        entity_id = entity.id

        # Refresh from database to get current state
        db.session.refresh(entity)
        current_updated_at = getattr(entity, 'updated_at', None)

        if current_updated_at is None:
            return None

        # Check if updated_at has changed
        if current_updated_at <= loaded_at:
            return None

        # Conflict detected - gather details
        field_changes = {}
        if original_state:
            for field, original_value in original_state.items():
                current_value = getattr(entity, field, None)
                if current_value != original_value:
                    field_changes[field] = (original_value, current_value)

        # Try to get the user who made the change from audit log
        other_user = cls._get_last_modifier(entity_type, entity_id)

        return ConflictInfo(
            entity_type=entity_type,
            entity_id=entity_id,
            loaded_at=loaded_at,
            current_updated_at=current_updated_at,
            other_user=other_user,
            field_changes=field_changes
        )

    @classmethod
    def _get_last_modifier(cls, entity_type: str, entity_id: int) -> Optional[str]:
        """Get the username of the last person to modify an entity."""
        from app.models import AuditLog

        log = AuditLog.query.filter_by(
            entity_type=entity_type,
            entity_id=entity_id
        ).order_by(AuditLog.timestamp.desc()).first()

        return log.username if log else None

    @classmethod
    def clear_tracking(cls, session_id: str = "default") -> None:
        """Clear all tracked entities for a session."""
        if session_id in cls._loaded_entities:
            del cls._loaded_entities[session_id]

    @classmethod
    def clear_entity_tracking(cls, entity_type: str, entity_id: int,
                              session_id: str = "default") -> None:
        """Clear tracking for a specific entity."""
        key = f"{entity_type}:{entity_id}"
        if session_id in cls._loaded_entities:
            cls._loaded_entities[session_id].pop(key, None)


def check_and_save_with_conflict_detection(
    entity,
    changes: dict,
    loaded_at: datetime,
    username: str,
    resolution: ConflictResolution = None
) -> Tuple[bool, Optional[ConflictInfo]]:
    """
    Attempt to save changes with conflict detection.

    Args:
        entity: The SQLAlchemy model instance to update
        changes: Dict of field -> new_value to apply
        loaded_at: When the entity was loaded for editing
        username: Current user making the change
        resolution: If a previous conflict was detected, the resolution choice

    Returns:
        Tuple of (success, conflict_info)
        - If success is True, changes were saved
        - If success is False and conflict_info is not None, there's a conflict
        - If success is False and conflict_info is None, there was an error
    """
    # Get original state for comparison
    original_state = {field: getattr(entity, field) for field in changes.keys()}

    # Check for conflict
    conflict = ConflictDetectionService.check_for_conflict(
        entity, loaded_at, original_state
    )

    if conflict and conflict.has_conflict:
        # Conflict detected
        if resolution is None:
            # No resolution provided - return conflict for user to decide
            return False, conflict

        if resolution == ConflictResolution.CANCEL:
            # User chose to cancel
            return False, conflict

        if resolution == ConflictResolution.RELOAD:
            # User chose to reload - return conflict but don't save
            return False, conflict

        # resolution == ConflictResolution.OVERWRITE - proceed with save

    # Apply changes
    for field, value in changes.items():
        setattr(entity, field, value)

    try:
        # Log the change
        from app.models import AuditLog
        AuditLog.log_action(
            username=username,
            action_type="update",
            entity_type=entity.__tablename__,
            entity_id=entity.id,
            changes=[
                {"field": k, "old": str(original_state.get(k)), "new": str(v)}
                for k, v in changes.items()
            ]
        )

        db.session.commit()
        return True, None

    except Exception as e:
        db.session.rollback()
        raise


class ConflictAwareModel:
    """
    Mixin for models that support conflict detection.

    Usage:
        class Project(db.Model, ConflictAwareModel, TimestampMixin):
            ...

        # When loading for edit
        project = Project.query.get(id)
        loaded_at = project.track_load()

        # When saving
        conflict = project.check_conflict(loaded_at)
        if conflict:
            # Handle conflict
            ...
    """

    def track_load(self, session_id: str = "default") -> datetime:
        """
        Track that this entity was loaded for editing.

        Returns:
            The current updated_at timestamp
        """
        updated_at = getattr(self, 'updated_at', datetime.now(timezone.utc))
        ConflictDetectionService.track_entity_load(
            entity_type=self.__tablename__,
            entity_id=self.id,
            updated_at=updated_at,
            session_id=session_id
        )
        return updated_at

    def check_conflict(self, loaded_at: datetime,
                       original_state: dict = None) -> Optional[ConflictInfo]:
        """
        Check if this entity has been modified since loaded_at.

        Args:
            loaded_at: Timestamp when entity was loaded
            original_state: Optional dict of original field values

        Returns:
            ConflictInfo if conflict exists, None otherwise
        """
        return ConflictDetectionService.check_for_conflict(
            self, loaded_at, original_state
        )
