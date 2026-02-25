"""
Construct management service.

Phase 2.2: Construct registry with family management (F3.1, F3.3-F3.5)
Phase 2.3: Anchor construct types (WT, Unregulated, Negative) (F3.2, F3.7, F3.8)
"""
from typing import Optional, List, Tuple
from datetime import datetime, timezone

from sqlalchemy import or_, and_

from app.extensions import db
from app.models import Project, Construct, AuditLog


class ConstructValidationError(Exception):
    """Raised when construct validation fails."""
    pass


class ConstructService:
    """
    Service for managing constructs with family and anchor type support.

    Anchor construct types:
    - Unregulated (Reporter-only): One per project, required on every plate
    - Wild-type (WT): One per family, required for each T-box family
    - Negative Control: Wells without template DNA (handled at layout level)

    Family rules:
    - Each construct belongs to exactly one family
    - Each family can have only one WT
    - The unregulated construct belongs to the special "universal" family
    """

    @staticmethod
    def create_construct(
        project_id: int,
        identifier: str,
        username: str,
        family: str = None,
        description: str = None,
        sequence: str = None,
        is_wildtype: bool = False,
        is_unregulated: bool = False,
        notes: str = None,
        plasmid_size_bp: int = None,
    ) -> Construct:
        """
        Create a new construct in draft state.

        Args:
            project_id: Parent project ID
            identifier: Unique identifier within project
            username: User creating the construct
            family: T-box family name (auto-assigned if unregulated)
            description: Optional description
            sequence: Optional DNA sequence
            is_wildtype: Mark as wild-type for its family
            is_unregulated: Mark as reporter-only (unregulated) control
            notes: Optional notes

        Returns:
            Created Construct instance

        Raises:
            ConstructValidationError: If validation fails
        """
        # Validate project exists
        project = Project.query.get(project_id)
        if not project:
            raise ConstructValidationError(f"Project {project_id} not found")

        if not identifier or not identifier.strip():
            raise ConstructValidationError("Construct identifier cannot be empty")

        identifier = identifier.strip()

        # Check for duplicate identifier in project
        existing = Construct.query.filter_by(
            project_id=project_id,
            identifier=identifier,
            is_deleted=False
        ).first()
        if existing:
            raise ConstructValidationError(
                f"Construct '{identifier}' already exists in this project"
            )

        # Validate unregulated construct rules
        if is_unregulated:
            existing_unregulated = Construct.query.filter_by(
                project_id=project_id,
                is_unregulated=True,
                is_deleted=False
            ).first()
            if existing_unregulated:
                raise ConstructValidationError(
                    f"Project already has a reporter-only construct: "
                    f"'{existing_unregulated.identifier}'. "
                    "Only one reporter-only construct allowed per project."
                )
            family = "universal"  # Force universal family for unregulated
            is_wildtype = False  # Unregulated cannot be WT

        # Validate family
        if not is_unregulated:
            if not family or not family.strip():
                raise ConstructValidationError(
                    "Family is required for non-reporter-only constructs"
                )
            family = family.strip()

        # Validate WT rules
        if is_wildtype:
            existing_wt = Construct.query.filter_by(
                project_id=project_id,
                family=family,
                is_wildtype=True,
                is_deleted=False
            ).first()
            if existing_wt:
                raise ConstructValidationError(
                    f"Family '{family}' already has a wild-type: "
                    f"'{existing_wt.identifier}'. "
                    "Only one WT allowed per family."
                )

        construct = Construct(
            project_id=project_id,
            identifier=identifier,
            family=family,
            description=description,
            sequence=sequence,
            plasmid_size_bp=plasmid_size_bp,
            is_wildtype=is_wildtype,
            is_unregulated=is_unregulated,
            notes=notes,
            is_draft=True
        )

        db.session.add(construct)
        db.session.flush()  # Assigns construct.id without committing

        AuditLog.log_action(
            username=username,
            action_type="create",
            entity_type="construct",
            entity_id=construct.id,
            project_id=project_id,
            changes=[
                {"field": "identifier", "old": None, "new": identifier},
                {"field": "family", "old": None, "new": family},
                {"field": "is_wildtype", "old": None, "new": str(is_wildtype)},
                {"field": "is_unregulated", "old": None, "new": str(is_unregulated)}
            ]
        )

        db.session.commit()

        return construct

    @staticmethod
    def get_construct(construct_id: int) -> Optional[Construct]:
        """Get a construct by ID."""
        return Construct.query.get(construct_id)

    @staticmethod
    def list_constructs(
        project_id: int,
        family: str = None,
        include_draft: bool = True,
        anchor_only: bool = False
    ) -> List[Construct]:
        """
        List constructs for a project with optional filters.

        Args:
            project_id: Project to list constructs for
            family: Filter by family name
            include_draft: Include draft constructs
            anchor_only: Only return anchor constructs (WT or unregulated)

        Returns:
            List of Construct instances
        """
        query = Construct.query.filter_by(project_id=project_id, is_deleted=False)

        if family:
            query = query.filter_by(family=family)

        if not include_draft:
            query = query.filter_by(is_draft=False)

        if anchor_only:
            query = query.filter(
                or_(
                    Construct.is_wildtype == True,
                    Construct.is_unregulated == True
                )
            )

        return query.order_by(Construct.family, Construct.identifier).all()

    @staticmethod
    def get_families(project_id: int) -> List[dict]:
        """
        Get all families in a project with their constructs.

        Returns:
            List of family dicts with construct counts and WT status
        """
        constructs = Construct.query.filter_by(
            project_id=project_id,
            is_deleted=False
        ).all()

        families = {}
        for c in constructs:
            if c.family not in families:
                families[c.family] = {
                    "name": c.family,
                    "construct_count": 0,
                    "has_wildtype": False,
                    "wildtype_id": None,
                    "wildtype_identifier": None,
                    "is_universal": c.family == "universal"
                }
            families[c.family]["construct_count"] += 1
            if c.is_wildtype:
                families[c.family]["has_wildtype"] = True
                families[c.family]["wildtype_id"] = c.id
                families[c.family]["wildtype_identifier"] = c.identifier

        return list(families.values())

    @staticmethod
    def update_construct(
        construct_id: int,
        username: str,
        **updates
    ) -> Tuple[Construct, List[str]]:
        """
        Update construct fields.

        Note: is_wildtype and is_unregulated can only be changed if construct
        is still in draft state.

        Args:
            construct_id: Construct ID to update
            username: User making the update
            **updates: Field values to update

        Returns:
            Tuple of (updated Construct, list of changed field names)

        Raises:
            ConstructValidationError: If validation fails
        """
        construct = Construct.query.get(construct_id)
        if not construct:
            raise ConstructValidationError(f"Construct {construct_id} not found")

        changes = []
        allowed_fields = {'identifier', 'description', 'sequence', 'notes', 'plasmid_size_bp'}

        # Family can change only for non-anchor constructs in draft
        if 'family' in updates and construct.is_draft:
            if not construct.is_unregulated:  # Can't change universal family
                allowed_fields.add('family')

        # Anchor type changes only in draft
        if construct.is_draft:
            if 'is_wildtype' in updates and not construct.is_unregulated:
                new_wt = updates['is_wildtype']
                if new_wt:
                    # Check no other WT exists in family
                    existing_wt = Construct.query.filter(
                        Construct.project_id == construct.project_id,
                        Construct.family == construct.family,
                        Construct.is_wildtype == True,
                        Construct.id != construct_id,
                        Construct.is_deleted == False
                    ).first()
                    if existing_wt:
                        raise ConstructValidationError(
                            f"Family '{construct.family}' already has a WT"
                        )
                allowed_fields.add('is_wildtype')

        for field, new_value in updates.items():
            if field not in allowed_fields:
                continue

            old_value = getattr(construct, field)
            if old_value != new_value:
                setattr(construct, field, new_value)
                changes.append({
                    "field": field,
                    "old": str(old_value) if old_value is not None else None,
                    "new": str(new_value) if new_value is not None else None
                })

        if changes:
            AuditLog.log_action(
                username=username,
                action_type="update",
                entity_type="construct",
                entity_id=construct_id,
                project_id=construct.project_id,
                changes=changes
            )
            db.session.commit()

        return construct, [c["field"] for c in changes]

    @staticmethod
    def publish_construct(construct_id: int, username: str) -> Construct:
        """
        Publish a construct (mark as non-draft).

        Args:
            construct_id: Construct to publish
            username: User performing the action

        Returns:
            Updated Construct
        """
        construct = Construct.query.get(construct_id)
        if not construct:
            raise ConstructValidationError(f"Construct {construct_id} not found")

        if not construct.is_draft:
            return construct  # Already published

        # Validate required fields
        if not construct.identifier:
            raise ConstructValidationError("Construct must have an identifier")

        if not construct.family:
            raise ConstructValidationError("Construct must have a family")

        construct.is_draft = False

        AuditLog.log_action(
            username=username,
            action_type="publish",
            entity_type="construct",
            entity_id=construct_id,
            project_id=construct.project_id,
            changes=[{"field": "is_draft", "old": "True", "new": "False"}]
        )

        db.session.commit()
        return construct

    @staticmethod
    def unpublish_construct(construct_id: int, username: str) -> Construct:
        """
        Revert a construct to draft state.

        This also unpublishes the parent project if it's published.

        Args:
            construct_id: Construct to unpublish
            username: User performing the action

        Returns:
            Updated Construct
        """
        construct = Construct.query.get(construct_id)
        if not construct:
            raise ConstructValidationError(f"Construct {construct_id} not found")

        if construct.is_draft:
            return construct  # Already draft

        construct.is_draft = True

        # Also unpublish parent project
        project = construct.project
        if not project.is_draft:
            project.is_draft = True
            project.results_valid = False

        AuditLog.log_action(
            username=username,
            action_type="unpublish",
            entity_type="construct",
            entity_id=construct_id,
            project_id=construct.project_id,
            changes=[{"field": "is_draft", "old": "False", "new": "True"}]
        )

        db.session.commit()
        return construct

    @staticmethod
    def delete_construct(construct_id: int, username: str) -> bool:
        """
        Soft-delete a construct.

        Args:
            construct_id: Construct to delete
            username: User performing the action

        Returns:
            True if deleted

        Raises:
            ConstructValidationError: If deletion not allowed
        """
        construct = Construct.query.get(construct_id)
        if not construct:
            raise ConstructValidationError(f"Construct {construct_id} not found")

        if construct.is_deleted:
            return True  # Already deleted

        # Check if construct is used in any wells (has data)
        from app.models import WellAssignment
        has_data = WellAssignment.query.filter_by(
            construct_id=construct_id
        ).first() is not None

        if has_data and not construct.is_draft:
            raise ConstructValidationError(
                "Cannot delete construct with experimental data. "
                "Use exclusion workflow instead."
            )

        construct.is_deleted = True
        construct.deleted_at = datetime.now(timezone.utc)
        
        # Rename identifier to free it up for reuse (while keeping uniqueness)
        old_identifier = construct.identifier
        suffix = f"_deleted_{int(datetime.now(timezone.utc).timestamp())}"
        # Truncate if necessary (max 100 chars)
        if len(construct.identifier) + len(suffix) > 95:
             construct.identifier = construct.identifier[:(95-len(suffix))] + suffix
        else:
             construct.identifier = construct.identifier + suffix

        AuditLog.log_action(
            username=username,
            action_type="delete",
            entity_type="construct",
            entity_id=construct_id,
            project_id=construct.project_id,
            changes=[{"field": "is_deleted", "old": "False", "new": "True"}]
        )

        db.session.commit()
        return True

    @staticmethod
    def get_unregulated_construct(project_id: int) -> Optional[Construct]:
        """Get the reporter-only (unregulated) construct for a project."""
        return Construct.query.filter_by(
            project_id=project_id,
            is_unregulated=True,
            is_deleted=False
        ).first()

    @staticmethod
    def get_wildtype_for_family(project_id: int, family: str) -> Optional[Construct]:
        """Get the wild-type construct for a specific family."""
        return Construct.query.filter_by(
            project_id=project_id,
            family=family,
            is_wildtype=True,
            is_deleted=False
        ).first()

    @staticmethod
    def validate_project_anchors(project_id: int) -> Tuple[bool, List[str]]:
        """
        Validate that a project has all required anchor constructs.

        Returns:
            Tuple of (is_valid, list of missing requirements)
        """
        issues = []

        # Check for unregulated construct
        unregulated = Construct.query.filter_by(
            project_id=project_id,
            is_unregulated=True,
            is_deleted=False
        ).first()

        if not unregulated:
            issues.append("Missing reporter-only (unregulated) construct")

        # Check each family has a WT
        families = ConstructService.get_families(project_id)
        for family in families:
            if family["is_universal"]:
                continue  # Universal family doesn't need a WT
            if not family["has_wildtype"]:
                issues.append(f"Family '{family['name']}' is missing a wild-type construct")

        return len(issues) == 0, issues
