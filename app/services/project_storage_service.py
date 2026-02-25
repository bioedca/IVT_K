"""
Project Storage and Activity Service.

Phase H.3: Storage usage tracking and inactivity flagging.

Provides:
- Storage usage calculation for projects
- Activity tracking and inactivity detection
- Archive status management
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from app.extensions import db
from app.models import Project
from app.models.archive import ProjectArchive


@dataclass
class StorageUsage:
    """Storage usage information for a project."""
    project_id: int
    total_bytes: int
    file_count: int
    breakdown: Dict[str, int]  # {category: bytes}

    @property
    def total_mb(self) -> float:
        """Total storage in megabytes."""
        return self.total_bytes / (1024 * 1024)

    @property
    def total_formatted(self) -> str:
        """Human-readable total storage."""
        if self.total_bytes < 1024:
            return f"{self.total_bytes} B"
        elif self.total_bytes < 1024 * 1024:
            return f"{self.total_bytes / 1024:.1f} KB"
        elif self.total_bytes < 1024 * 1024 * 1024:
            return f"{self.total_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{self.total_bytes / (1024 * 1024 * 1024):.2f} GB"


@dataclass
class ActivityStatus:
    """Activity status for a project."""
    project_id: int
    last_activity: Optional[datetime]
    days_inactive: int
    status: str  # active, recent, aging, inactive
    warning_sent: bool

    @property
    def status_color(self) -> str:
        """Get color for status display."""
        colors = {
            "active": "green",
            "recent": "blue",
            "aging": "yellow",
            "inactive": "red"
        }
        return colors.get(self.status, "gray")

    @property
    def status_label(self) -> str:
        """Get human-readable status label."""
        labels = {
            "active": "Active",
            "recent": "Recently Active",
            "aging": "Becoming Inactive",
            "inactive": "Inactive (6+ months)"
        }
        return labels.get(self.status, "Unknown")


class ProjectStorageService:
    """Service for project storage and activity management."""

    # Inactivity threshold in days (6 months)
    INACTIVITY_THRESHOLD_DAYS = 180

    # Warning threshold in days (5 months - warn before archival suggestion)
    WARNING_THRESHOLD_DAYS = 150

    @staticmethod
    def get_data_directory() -> Path:
        """Get the base data directory."""
        from flask import current_app
        base_dir = Path(current_app.root_path).parent
        return base_dir / "data"

    @classmethod
    def calculate_storage_usage(cls, project_id: int) -> StorageUsage:
        """
        Calculate storage usage for a project.

        Args:
            project_id: Project ID

        Returns:
            StorageUsage with breakdown by category
        """
        data_dir = cls.get_data_directory() / str(project_id)

        total_bytes = 0
        file_count = 0
        breakdown = {
            "raw_data": 0,
            "processed": 0,
            "mcmc_traces": 0,
            "figures": 0,
            "other": 0
        }

        if not data_dir.exists():
            return StorageUsage(
                project_id=project_id,
                total_bytes=0,
                file_count=0,
                breakdown=breakdown
            )

        for root, dirs, files in os.walk(data_dir):
            rel_path = Path(root).relative_to(data_dir)

            for file in files:
                file_path = Path(root) / file
                try:
                    size = file_path.stat().st_size
                    total_bytes += size
                    file_count += 1

                    # Categorize by subdirectory
                    if len(rel_path.parts) > 0:
                        category = rel_path.parts[0]
                        if category in breakdown:
                            breakdown[category] += size
                        else:
                            breakdown["other"] += size
                    else:
                        # Files in root of project directory
                        if file.endswith((".nc", ".netcdf")):
                            breakdown["mcmc_traces"] += size
                        elif file.endswith((".png", ".svg", ".pdf")):
                            breakdown["figures"] += size
                        elif file.endswith((".csv", ".xlsx")):
                            breakdown["raw_data"] += size
                        else:
                            breakdown["other"] += size
                except OSError:
                    continue

        return StorageUsage(
            project_id=project_id,
            total_bytes=total_bytes,
            file_count=file_count,
            breakdown=breakdown
        )

    @classmethod
    def get_activity_status(cls, project_id: int) -> ActivityStatus:
        """
        Get activity status for a project.

        Args:
            project_id: Project ID

        Returns:
            ActivityStatus with inactivity information
        """
        project = Project.query.get(project_id)
        if not project:
            return ActivityStatus(
                project_id=project_id,
                last_activity=None,
                days_inactive=0,
                status="unknown",
                warning_sent=False
            )

        last_activity = project.last_activity_at or project.created_at
        days_inactive = project.days_since_activity
        status = project.inactivity_status
        warning_sent = project.inactivity_warning_sent

        return ActivityStatus(
            project_id=project_id,
            last_activity=last_activity,
            days_inactive=days_inactive,
            status=status,
            warning_sent=warning_sent
        )

    @classmethod
    def update_project_activity(cls, project_id: int) -> bool:
        """
        Update last activity timestamp for a project.

        Args:
            project_id: Project ID

        Returns:
            True if updated successfully
        """
        from app.services.project_service import ProjectService
        result = ProjectService.update_activity(project_id)
        if not result:
            return False

        db.session.commit()
        return True

    @classmethod
    def get_inactive_projects(
        cls,
        threshold_days: int = None
    ) -> List[Dict[str, Any]]:
        """
        Get list of inactive projects.

        Args:
            threshold_days: Days of inactivity (default: 180)

        Returns:
            List of inactive project info dicts
        """
        threshold = threshold_days or cls.INACTIVITY_THRESHOLD_DAYS
        cutoff = datetime.now(timezone.utc) - timedelta(days=threshold)

        inactive = Project.query.filter(
            Project.is_archived == False,
            Project.is_deleted == False,
            Project.last_activity_at < cutoff
        ).all()

        return [
            {
                "id": p.id,
                "name": p.name,
                "last_activity": p.last_activity_at.isoformat() if p.last_activity_at else None,
                "days_inactive": p.days_since_activity,
                "warning_sent": p.inactivity_warning_sent
            }
            for p in inactive
        ]

    @classmethod
    def get_projects_needing_warning(cls) -> List[Dict[str, Any]]:
        """
        Get projects approaching inactivity threshold that need warning.

        Returns:
            List of project info dicts needing warning
        """
        warning_cutoff = datetime.now(timezone.utc) - timedelta(days=cls.WARNING_THRESHOLD_DAYS)
        inactive_cutoff = datetime.now(timezone.utc) - timedelta(days=cls.INACTIVITY_THRESHOLD_DAYS)

        projects = Project.query.filter(
            Project.is_archived == False,
            Project.is_deleted == False,
            Project.inactivity_warning_sent == False,
            Project.last_activity_at < warning_cutoff,
            Project.last_activity_at >= inactive_cutoff
        ).all()

        return [
            {
                "id": p.id,
                "name": p.name,
                "last_activity": p.last_activity_at.isoformat() if p.last_activity_at else None,
                "days_inactive": p.days_since_activity,
                "days_until_inactive": cls.INACTIVITY_THRESHOLD_DAYS - p.days_since_activity
            }
            for p in projects
        ]

    @classmethod
    def mark_warning_sent(cls, project_id: int) -> bool:
        """
        Mark inactivity warning as sent for a project.

        Args:
            project_id: Project ID

        Returns:
            True if marked successfully
        """
        project = Project.query.get(project_id)
        if not project:
            return False

        project.inactivity_warning_sent = True
        db.session.commit()
        return True

    @classmethod
    def get_archive_status(cls, project_id: int) -> Dict[str, Any]:
        """
        Get archive status for a project.

        Args:
            project_id: Project ID

        Returns:
            Archive status information
        """
        project = Project.query.get(project_id)
        if not project:
            return {"error": "Project not found"}

        archive = ProjectArchive.query.filter_by(project_id=project_id).first()

        if project.is_archived and archive:
            return {
                "is_archived": True,
                "archived_at": archive.archived_at.isoformat() if archive.archived_at else None,
                "archived_by": archive.archived_by,
                "archive_path": archive.archive_path,
                "original_size": archive.original_size,
                "compressed_size": archive.compressed_size,
                "compression_ratio": archive.compression_ratio,
                "can_restore": True
            }
        else:
            storage = cls.calculate_storage_usage(project_id)
            return {
                "is_archived": False,
                "current_size": storage.total_bytes,
                "current_size_formatted": storage.total_formatted,
                "file_count": storage.file_count,
                "can_archive": not project.is_archived and storage.total_bytes > 0
            }

    @classmethod
    def get_system_storage_summary(cls) -> Dict[str, Any]:
        """
        Get system-wide storage summary.

        Returns:
            Summary of storage usage across all projects
        """
        projects = Project.query.filter_by(is_deleted=False).all()

        total_active = 0
        total_archived = 0
        active_count = 0
        archived_count = 0

        for project in projects:
            if project.is_archived:
                archive = ProjectArchive.query.filter_by(project_id=project.id).first()
                if archive:
                    total_archived += archive.compressed_size or 0
                    archived_count += 1
            else:
                storage = cls.calculate_storage_usage(project.id)
                total_active += storage.total_bytes
                active_count += 1

        return {
            "active_projects": active_count,
            "archived_projects": archived_count,
            "total_active_bytes": total_active,
            "total_archived_bytes": total_archived,
            "total_bytes": total_active + total_archived,
            "active_formatted": StorageUsage(0, total_active, 0, {}).total_formatted,
            "archived_formatted": StorageUsage(0, total_archived, 0, {}).total_formatted,
            "total_formatted": StorageUsage(0, total_active + total_archived, 0, {}).total_formatted
        }
