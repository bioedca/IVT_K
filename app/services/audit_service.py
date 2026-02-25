"""
Audit service for IVT Kinetics Analyzer.

Phase 10.4-10.6: Audit Trail Enhancement (F18.1-F18.4)

Provides:
- Comprehensive action logging with field-level diffs
- Query interface by project, user, action type, date range
- Export to JSON and Markdown formats
"""
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
import json

from sqlalchemy import and_, or_
from app.extensions import db
from app.models.audit_log import AuditLog, UserSession


@dataclass
class AuditQueryFilter:
    """Filter criteria for audit log queries."""
    project_id: Optional[int] = None
    username: Optional[str] = None
    action_type: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 100
    offset: int = 0


class AuditService:
    """Service for audit trail management."""

    # Standard action types
    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_DELETE = "delete"
    ACTION_UPLOAD = "upload"
    ACTION_EXPORT = "export"
    ACTION_ANALYZE = "analyze"
    ACTION_EXCLUDE = "exclude"
    ACTION_INCLUDE = "include"
    ACTION_ARCHIVE = "archive"
    ACTION_RESTORE = "restore"

    # Standard entity types
    ENTITY_PROJECT = "project"
    ENTITY_CONSTRUCT = "construct"
    ENTITY_PLATE_LAYOUT = "plate_layout"
    ENTITY_WELL = "well"
    ENTITY_SESSION = "session"
    ENTITY_ANALYSIS = "analysis"
    ENTITY_FIT = "fit"
    ENTITY_COMPARISON = "comparison"
    ENTITY_SETTINGS = "settings"

    @staticmethod
    def log_action(
        username: str,
        action_type: str,
        entity_type: str,
        entity_id: int,
        project_id: Optional[int] = None,
        changes: Optional[List[Dict[str, Any]]] = None,
        details: Optional[Dict[str, Any]] = None,
        commit: bool = True,
    ) -> AuditLog:
        """
        Log an action to the audit trail.

        Args:
            username: User who performed the action
            action_type: Type of action (create, update, delete, etc.)
            entity_type: Type of entity affected
            entity_id: ID of the affected entity
            project_id: Optional project ID for context
            changes: List of field changes [{field, old, new}, ...]
            details: Additional context dictionary
            commit: Whether to commit the transaction

        Returns:
            Created AuditLog entry
        """
        log = AuditLog.log_action(
            username=username,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            project_id=project_id,
            changes=changes,
            details=details,
        )

        if commit:
            db.session.commit()

        return log

    @staticmethod
    def compute_field_diff(
        old_state: Dict[str, Any],
        new_state: Dict[str, Any],
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Compute field-level differences between two states.

        Args:
            old_state: Previous state dictionary
            new_state: New state dictionary
            fields: Optional list of fields to compare (all if None)

        Returns:
            List of changes [{field, old, new}, ...]
        """
        changes = []

        # Determine fields to compare
        if fields is None:
            fields = set(old_state.keys()) | set(new_state.keys())

        for field in fields:
            old_value = old_state.get(field)
            new_value = new_state.get(field)

            # Normalize None and empty string
            if old_value == "":
                old_value = None
            if new_value == "":
                new_value = None

            if old_value != new_value:
                changes.append({
                    "field": field,
                    "old": old_value,
                    "new": new_value,
                })

        return changes

    @staticmethod
    def log_entity_create(
        username: str,
        entity_type: str,
        entity_id: int,
        entity_data: Dict[str, Any],
        project_id: Optional[int] = None,
        commit: bool = True,
    ) -> AuditLog:
        """
        Log entity creation.

        Args:
            username: User who created the entity
            entity_type: Type of entity
            entity_id: ID of new entity
            entity_data: Data of the created entity
            project_id: Optional project context
            commit: Whether to commit

        Returns:
            AuditLog entry
        """
        return AuditService.log_action(
            username=username,
            action_type=AuditService.ACTION_CREATE,
            entity_type=entity_type,
            entity_id=entity_id,
            project_id=project_id,
            details={"created_data": entity_data},
            commit=commit,
        )

    @staticmethod
    def log_entity_update(
        username: str,
        entity_type: str,
        entity_id: int,
        old_state: Dict[str, Any],
        new_state: Dict[str, Any],
        project_id: Optional[int] = None,
        commit: bool = True,
    ) -> AuditLog:
        """
        Log entity update with field-level diff.

        Args:
            username: User who updated the entity
            entity_type: Type of entity
            entity_id: ID of entity
            old_state: State before update
            new_state: State after update
            project_id: Optional project context
            commit: Whether to commit

        Returns:
            AuditLog entry
        """
        changes = AuditService.compute_field_diff(old_state, new_state)

        return AuditService.log_action(
            username=username,
            action_type=AuditService.ACTION_UPDATE,
            entity_type=entity_type,
            entity_id=entity_id,
            project_id=project_id,
            changes=changes,
            commit=commit,
        )

    @staticmethod
    def log_entity_delete(
        username: str,
        entity_type: str,
        entity_id: int,
        entity_data: Dict[str, Any],
        project_id: Optional[int] = None,
        commit: bool = True,
    ) -> AuditLog:
        """
        Log entity deletion with final state.

        Args:
            username: User who deleted the entity
            entity_type: Type of entity
            entity_id: ID of deleted entity
            entity_data: Final state before deletion
            project_id: Optional project context
            commit: Whether to commit

        Returns:
            AuditLog entry
        """
        return AuditService.log_action(
            username=username,
            action_type=AuditService.ACTION_DELETE,
            entity_type=entity_type,
            entity_id=entity_id,
            project_id=project_id,
            details={"deleted_data": entity_data},
            commit=commit,
        )

    @staticmethod
    def query_logs(
        filters: AuditQueryFilter,
    ) -> List[AuditLog]:
        """
        Query audit logs with filters.

        Args:
            filters: Query filter criteria

        Returns:
            List of matching AuditLog entries
        """
        query = AuditLog.query

        if filters.project_id is not None:
            query = query.filter(AuditLog.project_id == filters.project_id)

        if filters.username is not None:
            query = query.filter(AuditLog.username == filters.username)

        if filters.action_type is not None:
            query = query.filter(AuditLog.action_type == filters.action_type)

        if filters.entity_type is not None:
            query = query.filter(AuditLog.entity_type == filters.entity_type)

        if filters.entity_id is not None:
            query = query.filter(AuditLog.entity_id == filters.entity_id)

        if filters.start_date is not None:
            query = query.filter(AuditLog.timestamp >= filters.start_date)

        if filters.end_date is not None:
            query = query.filter(AuditLog.timestamp <= filters.end_date)

        query = query.order_by(AuditLog.timestamp.desc())
        query = query.offset(filters.offset).limit(filters.limit)

        return query.all()

    @staticmethod
    def get_project_history(
        project_id: int,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Get audit history for a project.

        Args:
            project_id: Project ID
            limit: Maximum entries to return

        Returns:
            List of AuditLog entries
        """
        return AuditService.query_logs(
            AuditQueryFilter(project_id=project_id, limit=limit)
        )

    @staticmethod
    def get_user_history(
        username: str,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Get audit history for a user.

        Args:
            username: Username
            limit: Maximum entries to return

        Returns:
            List of AuditLog entries
        """
        return AuditService.query_logs(
            AuditQueryFilter(username=username, limit=limit)
        )

    @staticmethod
    def get_entity_history(
        entity_type: str,
        entity_id: int,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Get audit history for a specific entity.

        Args:
            entity_type: Entity type
            entity_id: Entity ID
            limit: Maximum entries to return

        Returns:
            List of AuditLog entries
        """
        return AuditService.query_logs(
            AuditQueryFilter(entity_type=entity_type, entity_id=entity_id, limit=limit)
        )

    @staticmethod
    def get_recent_activity(
        days: int = 7,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Get recent audit activity.

        Args:
            days: Number of days to look back
            limit: Maximum entries to return

        Returns:
            List of AuditLog entries
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        return AuditService.query_logs(
            AuditQueryFilter(start_date=start_date, limit=limit)
        )

    @staticmethod
    def export_to_json(
        logs: List[AuditLog],
        include_details: bool = True,
    ) -> str:
        """
        Export audit logs to JSON format.

        Args:
            logs: List of AuditLog entries
            include_details: Whether to include details field

        Returns:
            JSON string
        """
        def serialize_log(log: AuditLog) -> Dict[str, Any]:
            data = {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "username": log.username,
                "action_type": log.action_type,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "project_id": log.project_id,
                "changes": log.changes,
            }
            if include_details:
                data["details"] = log.details
            return data

        export_data = {
            "export_date": datetime.now(timezone.utc).isoformat(),
            "total_entries": len(logs),
            "entries": [serialize_log(log) for log in logs],
        }

        return json.dumps(export_data, indent=2, default=str)

    @staticmethod
    def export_to_markdown(
        logs: List[AuditLog],
        title: str = "Audit Log",
    ) -> str:
        """
        Export audit logs to Markdown format.

        Args:
            logs: List of AuditLog entries
            title: Document title

        Returns:
            Markdown string
        """
        lines = [
            f"# {title}",
            "",
            f"Exported: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Total entries: {len(logs)}",
            "",
            "---",
            "",
        ]

        for log in logs:
            timestamp = log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"## {timestamp} - {log.action_type.upper()}")
            lines.append("")
            lines.append(f"- **User**: {log.username}")
            lines.append(f"- **Entity**: {log.entity_type} (ID: {log.entity_id})")
            if log.project_id:
                lines.append(f"- **Project ID**: {log.project_id}")

            if log.changes:
                lines.append("")
                lines.append("### Changes")
                lines.append("")
                lines.append("| Field | Old Value | New Value |")
                lines.append("|-------|-----------|-----------|")
                for change in log.changes:
                    old = change.get("old", "-")
                    new = change.get("new", "-")
                    field = change.get("field", "unknown")
                    # Truncate long values
                    old_str = str(old)[:50] if old is not None else "-"
                    new_str = str(new)[:50] if new is not None else "-"
                    lines.append(f"| {field} | {old_str} | {new_str} |")

            if log.details:
                lines.append("")
                lines.append("### Details")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(log.details, indent=2, default=str))
                lines.append("```")

            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def get_action_summary(
        project_id: Optional[int] = None,
        days: int = 30,
    ) -> Dict[str, int]:
        """
        Get summary of actions by type.

        Args:
            project_id: Optional project filter
            days: Number of days to look back

        Returns:
            Dictionary of action_type -> count
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        query = db.session.query(
            AuditLog.action_type,
            db.func.count(AuditLog.id)
        ).filter(AuditLog.timestamp >= start_date)

        if project_id is not None:
            query = query.filter(AuditLog.project_id == project_id)

        query = query.group_by(AuditLog.action_type)

        return dict(query.all())

    @staticmethod
    def get_user_summary(
        project_id: Optional[int] = None,
        days: int = 30,
    ) -> Dict[str, int]:
        """
        Get summary of actions by user.

        Args:
            project_id: Optional project filter
            days: Number of days to look back

        Returns:
            Dictionary of username -> count
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        query = db.session.query(
            AuditLog.username,
            db.func.count(AuditLog.id)
        ).filter(AuditLog.timestamp >= start_date)

        if project_id is not None:
            query = query.filter(AuditLog.project_id == project_id)

        query = query.group_by(AuditLog.username)

        return dict(query.all())


class AuditServiceError(Exception):
    """Exception raised for audit service errors."""
    pass
