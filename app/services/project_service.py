"""
Project management service.

Phase 2.1: Project CRUD with draft/publish states (F2.1-F2.4)
"""
from typing import Optional, List, Tuple
from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Project, Construct, AuditLog
from app.models.project import PlateFormat


class ProjectValidationError(Exception):
    """Raised when project validation fails."""
    pass


class ProjectService:
    """
    Service for managing projects with draft/publish workflow.

    Projects follow a strict hierarchy:
    - Must publish children (constructs) before parent (project)
    - Cannot delete published projects with data
    - Format (96/384-well) locked after plates added
    """

    @staticmethod
    def create_project(
        name: str,
        username: str,
        description: str = None,
        reporter_system: str = "iSpinach",
        plate_format: PlateFormat = PlateFormat.PLATE_384,
        precision_target: float = 0.3
    ) -> Project:
        """
        Create a new project in draft state.

        Args:
            name: Project name (used to generate slug)
            username: User creating the project
            description: Optional project description
            reporter_system: Fluorogenic aptamer system (default: iSpinach)
            plate_format: 96 or 384-well format
            precision_target: Target CI width for fold change (default: ±0.3)

        Returns:
            Created Project instance

        Raises:
            ProjectValidationError: If name is empty or duplicate
        """
        if not name or not name.strip():
            raise ProjectValidationError("Project name cannot be empty")

        name = name.strip()

        # Check for duplicate name
        existing = Project.query.filter_by(name=name).first()
        if existing:
            raise ProjectValidationError(f"Project with name '{name}' already exists")

        project = Project(
            name=name,
            description=description,
            reporter_system=reporter_system,
            plate_format=plate_format,
            precision_target=precision_target,
            is_draft=True
        )

        db.session.add(project)
        db.session.flush()  # Assigns project.id without committing

        # Log the action with the real project ID
        AuditLog.log_action(
            username=username,
            action_type="create",
            entity_type="project",
            entity_id=project.id,
            project_id=project.id,
            changes=[{"field": "name", "old": None, "new": name}]
        )

        db.session.commit()

        return project

    @staticmethod
    def get_project(project_id: int) -> Optional[Project]:
        """Get a project by ID."""
        return Project.query.get(project_id)

    @staticmethod
    def get_project_by_slug(slug: str) -> Optional[Project]:
        """Get a project by its URL slug."""
        return Project.query.filter_by(name_slug=slug).first()

    @staticmethod
    def list_projects(
        include_archived: bool = False,
        draft_only: bool = False,
        search: str = None,
        limit: int = None
    ) -> List[Project]:
        """
        List projects with optional filters.

        Args:
            include_archived: Include archived projects
            draft_only: Only return draft projects
            search: Search term for name/description
            limit: Maximum number to return

        Returns:
            List of Project instances
        """
        query = Project.query.filter_by(is_deleted=False)

        if not include_archived:
            query = query.filter_by(is_archived=False)

        if draft_only:
            query = query.filter_by(is_draft=True)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Project.name.ilike(search_term),
                    Project.description.ilike(search_term)
                )
            )

        query = query.order_by(Project.updated_at.desc())

        if limit:
            query = query.limit(limit)

        return query.all()

    @staticmethod
    def update_project(
        project_id: int,
        username: str,
        **updates
    ) -> Tuple[Project, List[str]]:
        """
        Update project fields.

        Args:
            project_id: Project ID to update
            username: User making the update
            **updates: Field values to update

        Returns:
            Tuple of (updated Project, list of changed field names)

        Raises:
            ProjectValidationError: If validation fails
        """
        project = Project.query.get(project_id)
        if not project:
            raise ProjectValidationError(f"Project {project_id} not found")

        # Track changes
        changes = []
        allowed_fields = {
            'name', 'description', 'reporter_system',
            'precision_target', 'notes',
            # Analysis settings
            'meaningful_fc_threshold', 'kinetic_model_type',
            # QC thresholds
            'qc_cv_threshold', 'qc_outlier_threshold', 'qc_drift_threshold',
            'qc_saturation_threshold', 'qc_snr_threshold', 'qc_empty_well_threshold',
            # LOD/LOQ settings
            'lod_coverage_factor', 'loq_coverage_factor',
            # Ligand settings
            'has_ligand_conditions', 'ligand_name', 'ligand_unit', 'ligand_max_concentration',
            # Archive status
            'is_archived'
        }

        # Plate format can only change if no plates exist
        if 'plate_format' in updates:
            if updates['plate_format'] != project.plate_format and ProjectService.has_plates(project_id):
                raise ProjectValidationError(
                    "Cannot change plate format after plates have been added"
                )
            allowed_fields.add('plate_format')

        for field, new_value in updates.items():
            if field not in allowed_fields:
                continue

            old_value = getattr(project, field)
            if old_value != new_value:
                setattr(project, field, new_value)
                changes.append({
                    "field": field,
                    "old": str(old_value) if old_value is not None else None,
                    "new": str(new_value) if new_value is not None else None
                })

        if changes:
            AuditLog.log_action(
                username=username,
                action_type="update",
                entity_type="project",
                entity_id=project_id,
                project_id=project_id,
                changes=changes
            )
            db.session.commit()

        return project, [c["field"] for c in changes]

    @staticmethod
    def publish_project(project_id: int, username: str) -> Project:
        """
        Publish a project (mark as non-draft).

        Requires all constructs to be published first.

        Args:
            project_id: Project to publish
            username: User performing the action

        Returns:
            Updated Project

        Raises:
            ProjectValidationError: If publication requirements not met
        """
        project = Project.query.get(project_id)
        if not project:
            raise ProjectValidationError(f"Project {project_id} not found")

        if not project.is_draft:
            return project  # Already published

        # Check all constructs are published
        draft_constructs = Construct.query.filter_by(
            project_id=project_id,
            is_draft=True
        ).count()

        if draft_constructs > 0:
            raise ProjectValidationError(
                f"Cannot publish project: {draft_constructs} construct(s) are still in draft. "
                "Publish all constructs first."
            )

        # Check required anchor constructs exist
        has_unregulated = Construct.query.filter_by(
            project_id=project_id,
            is_unregulated=True
        ).first() is not None

        if not has_unregulated:
            raise ProjectValidationError(
                "Cannot publish project: No reporter-only (unregulated) construct defined. "
                "Each project requires exactly one reporter-only construct."
            )

        project.is_draft = False

        AuditLog.log_action(
            username=username,
            action_type="publish",
            entity_type="project",
            entity_id=project_id,
            project_id=project_id,
            changes=[{"field": "is_draft", "old": "True", "new": "False"}]
        )

        db.session.commit()
        return project

    @staticmethod
    def unpublish_project(project_id: int, username: str) -> Project:
        """
        Revert a project to draft state.

        This allows adding/modifying constructs but invalidates any analysis.

        Args:
            project_id: Project to unpublish
            username: User performing the action

        Returns:
            Updated Project
        """
        project = Project.query.get(project_id)
        if not project:
            raise ProjectValidationError(f"Project {project_id} not found")

        if project.is_draft:
            return project  # Already draft

        project.is_draft = True
        project.results_valid = False  # Invalidate results

        AuditLog.log_action(
            username=username,
            action_type="unpublish",
            entity_type="project",
            entity_id=project_id,
            project_id=project_id,
            changes=[
                {"field": "is_draft", "old": "False", "new": "True"},
                {"field": "results_valid", "old": "True", "new": "False"}
            ]
        )

        db.session.commit()
        return project

    @staticmethod
    def delete_project(project_id: int, username: str, force: bool = False) -> bool:
        """
        Soft-delete a project.

        Args:
            project_id: Project to delete
            username: User performing the action
            force: Force delete even if published (still soft delete)

        Returns:
            True if deleted

        Raises:
            ProjectValidationError: If deletion not allowed
        """
        project = Project.query.get(project_id)
        if not project:
            raise ProjectValidationError(f"Project {project_id} not found")

        if project.is_deleted:
            return True  # Already deleted

        if not project.is_draft and not force:
            raise ProjectValidationError(
                "Cannot delete published project. Unpublish first or use force=True."
            )

        project.is_deleted = True
        project.deleted_at = datetime.now(timezone.utc)
        project.deleted_by = username

        AuditLog.log_action(
            username=username,
            action_type="delete",
            entity_type="project",
            entity_id=project_id,
            project_id=project_id,
            changes=[{"field": "is_deleted", "old": "False", "new": "True"}]
        )

        db.session.commit()
        return True

    @staticmethod
    def restore_project(project_id: int, username: str) -> Project:
        """
        Restore a soft-deleted project.

        Args:
            project_id: Project to restore
            username: User performing the action

        Returns:
            Restored Project
        """
        project = Project.query.get(project_id)
        if not project:
            raise ProjectValidationError(f"Project {project_id} not found")

        if not project.is_deleted:
            return project  # Not deleted

        project.is_deleted = False
        project.deleted_at = None
        project.deleted_by = None

        AuditLog.log_action(
            username=username,
            action_type="restore",
            entity_type="project",
            entity_id=project_id,
            project_id=project_id,
            changes=[{"field": "is_deleted", "old": "True", "new": "False"}]
        )

        db.session.commit()
        return project

    @staticmethod
    def get_project_statistics(project_id: int) -> dict:
        """
        Get summary statistics for a project.

        Returns:
            Dict with counts and status information
        """
        project = Project.query.get(project_id)
        if not project:
            return None

        from app.models import ExperimentalSession, Plate, Well, AnalysisVersion, ReactionSetup
        from app.models.plate_layout import PlateLayout

        construct_count = Construct.query.filter_by(
            project_id=project_id, is_deleted=False
        ).count()
        draft_construct_count = Construct.query.filter_by(
            project_id=project_id, is_draft=True, is_deleted=False
        ).count()

        # Count published layouts (is_draft=False)
        layout_count = PlateLayout.query.filter_by(
            project_id=project_id, is_draft=False
        ).count()

        # Count published reaction setups (IVT protocols)
        reaction_count = ReactionSetup.query.filter_by(
            project_id=project_id
        ).count()

        session_count = ExperimentalSession.query.filter_by(
            project_id=project_id
        ).count()

        plate_count = Plate.query.join(ExperimentalSession).filter(
            ExperimentalSession.project_id == project_id
        ).count()

        analysis_count = AnalysisVersion.query.filter_by(
            project_id=project_id
        ).count()

        # Count wells with data (for step 4/5 unlock)
        well_count = Well.query.join(Plate).join(ExperimentalSession).filter(
            ExperimentalSession.project_id == project_id
        ).count()

        # Count QC issues (excluded wells)
        from app.models.experiment import FitStatus, QCStatus
        excluded_well_count = Well.query.join(Plate).join(ExperimentalSession).filter(
            ExperimentalSession.project_id == project_id,
            Well.is_excluded == True
        ).count()

        # Count sessions by QC status
        # Pending = not yet reviewed (PENDING or IN_REVIEW)
        # Both APPROVED and REJECTED count as "resolved" for workflow purposes
        from sqlalchemy import or_
        sessions_pending_qc = ExperimentalSession.query.filter(
            ExperimentalSession.project_id == project_id,
            or_(
                ExperimentalSession.qc_status == QCStatus.PENDING,
                ExperimentalSession.qc_status == QCStatus.IN_REVIEW,
            )
        ).count()

        sessions_qc_approved = ExperimentalSession.query.filter(
            ExperimentalSession.project_id == project_id,
            ExperimentalSession.qc_status == QCStatus.APPROVED
        ).count()

        sessions_qc_rejected = ExperimentalSession.query.filter(
            ExperimentalSession.project_id == project_id,
            ExperimentalSession.qc_status == QCStatus.REJECTED
        ).count()

        # QC passes when all sessions have been reviewed (APPROVED or REJECTED)
        # Both approval and rejection resolve the QC step
        qc_passed = session_count > 0 and sessions_pending_qc == 0

        # For display: show pending QC count (sessions not yet reviewed)
        qc_issues_count = sessions_pending_qc

        # File count = plate count (each upload creates a plate)
        file_count = plate_count

        # Export count (placeholder - count export packages if model exists)
        export_count = 0

        return {
            "id": project.id,
            "name": project.name,
            "slug": project.name_slug,
            "is_draft": project.is_draft,
            "is_deleted": project.is_deleted,
            "plate_format": project.plate_format.value,
            "construct_count": construct_count,
            "draft_construct_count": draft_construct_count,
            "published_construct_count": construct_count - draft_construct_count,
            "layout_count": layout_count,
            "reaction_count": reaction_count,
            "session_count": session_count,
            "plate_count": plate_count,
            "file_count": file_count,
            "well_count": well_count,
            "qc_issues_count": qc_issues_count,
            "qc_passed": qc_passed,
            "sessions_pending_qc": sessions_pending_qc,
            "sessions_qc_approved": sessions_qc_approved,
            "sessions_qc_rejected": sessions_qc_rejected,
            "excluded_well_count": excluded_well_count,
            "analysis_count": analysis_count,
            "export_count": export_count,
            "has_plates": plate_count > 0,
            "can_change_format": plate_count == 0,
            "precision_target": project.precision_target,
            "results_valid": project.results_valid,
            "created_at": project.created_at.isoformat() if project.created_at else None,
            "updated_at": project.updated_at.isoformat() if project.updated_at else None,
        }

    @staticmethod
    def has_plates(project_id: int) -> bool:
        """
        Check if a project has any experimental plates.

        Args:
            project_id: Project ID to check

        Returns:
            True if the project has at least one plate
        """
        from app.models import Plate, ExperimentalSession
        return Plate.query.join(ExperimentalSession).filter(
            ExperimentalSession.project_id == project_id
        ).first() is not None

    @staticmethod
    def update_activity(project_id: int) -> Optional[Project]:
        """
        Update last activity timestamp for a project.

        Args:
            project_id: Project ID to update

        Returns:
            Updated Project or None if not found
        """
        project = Project.query.get(project_id)
        if not project:
            return None
        project.update_activity()
        db.session.commit()
        return project
