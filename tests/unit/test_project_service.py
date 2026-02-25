"""Unit tests for ProjectService and ConstructService."""
import pytest
from datetime import datetime

from app.models import Project, Construct
from app.models.project import PlateFormat
from app.services.project_service import ProjectService, ProjectValidationError
from app.services.construct_service import ConstructService, ConstructValidationError


class TestProjectService:
    """Tests for ProjectService (Phase 2.1)."""

    def test_create_project_with_draft_status(self, db_session):
        """T2.1: Project created with draft status."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        assert project.id is not None
        assert project.name == "Test Project"
        assert project.is_draft is True

    def test_project_slug_generated_correctly(self, db_session):
        """T2.2: Project slug generated correctly."""
        project = ProjectService.create_project(
            name="My Test Project",
            username="researcher"
        )

        assert project.name_slug == "my_test_project"

    def test_project_slug_special_characters(self, db_session):
        """T2.2: Slug handles special characters."""
        project = ProjectService.create_project(
            name="Tbox Analysis (v2.0)",
            username="researcher"
        )

        assert project.name_slug == "tbox_analysis_v2_0"

    def test_project_empty_name_rejected(self, db_session):
        """T2.1 edge case: Empty name rejected."""
        with pytest.raises(ProjectValidationError) as excinfo:
            ProjectService.create_project(name="", username="researcher")
        assert "cannot be empty" in str(excinfo.value)

    def test_project_duplicate_name_rejected(self, db_session):
        """T2.1 edge case: Duplicate name rejected."""
        ProjectService.create_project(name="Test Project", username="researcher")

        with pytest.raises(ProjectValidationError) as excinfo:
            ProjectService.create_project(name="Test Project", username="researcher")
        assert "already exists" in str(excinfo.value)

    def test_project_publish_requires_published_constructs(self, db_session):
        """T2.3: Project publish requires published constructs."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        # Create a draft unregulated construct
        ConstructService.create_construct(
            project_id=project.id,
            identifier="Reporter_Only",
            username="researcher",
            is_unregulated=True
        )

        with pytest.raises(ProjectValidationError) as excinfo:
            ProjectService.publish_project(project.id, "researcher")
        assert "draft" in str(excinfo.value).lower()

    def test_project_publish_requires_unregulated(self, db_session):
        """T2.3: Project publish requires unregulated construct."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        with pytest.raises(ProjectValidationError) as excinfo:
            ProjectService.publish_project(project.id, "researcher")
        assert "reporter-only" in str(excinfo.value).lower()

    def test_project_publish_success(self, db_session):
        """Test successful project publication."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        # Create and publish unregulated construct
        construct = ConstructService.create_construct(
            project_id=project.id,
            identifier="Reporter_Only",
            username="researcher",
            is_unregulated=True
        )
        ConstructService.publish_construct(construct.id, "researcher")

        # Now publish project
        project = ProjectService.publish_project(project.id, "researcher")

        assert project.is_draft is False

    def test_project_unpublish_reverts_to_draft(self, db_session):
        """T2.4: Project unpublish reverts to draft."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        # Set up and publish
        construct = ConstructService.create_construct(
            project_id=project.id,
            identifier="Reporter_Only",
            username="researcher",
            is_unregulated=True
        )
        ConstructService.publish_construct(construct.id, "researcher")
        ProjectService.publish_project(project.id, "researcher")

        # Now unpublish
        project = ProjectService.unpublish_project(project.id, "researcher")

        assert project.is_draft is True
        assert project.results_valid is False

    def test_precision_target_stored(self, db_session):
        """T2.16: Precision target stored in project settings."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher",
            precision_target=0.5
        )

        assert project.precision_target == 0.5

    def test_precision_target_default(self, db_session):
        """T2.16: Default precision target."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        assert project.precision_target == 0.3  # Default

    def test_project_statistics(self, db_session):
        """Test project statistics gathering."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        ConstructService.create_construct(
            project_id=project.id,
            identifier="Reporter_Only",
            username="researcher",
            is_unregulated=True
        )

        stats = ProjectService.get_project_statistics(project.id)

        assert stats["name"] == "Test Project"
        assert stats["is_draft"] is True
        assert stats["construct_count"] == 1
        assert stats["draft_construct_count"] == 1


class TestConstructService:
    """Tests for ConstructService (Phase 2.2-2.3)."""

    def test_construct_created_with_family(self, db_session):
        """T2.5: Construct created with family assignment."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        construct = ConstructService.create_construct(
            project_id=project.id,
            identifier="Tbox1_M1",
            family="Tbox1",
            username="researcher"
        )

        assert construct.id is not None
        assert construct.family == "Tbox1"
        assert construct.is_draft is True

    def test_construct_family_required(self, db_session):
        """T2.5 edge case: Family required for non-unregulated."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        with pytest.raises(ConstructValidationError) as excinfo:
            ConstructService.create_construct(
                project_id=project.id,
                identifier="Test_Construct",
                family=None,
                username="researcher"
            )
        assert "Family is required" in str(excinfo.value)

    def test_wt_construct_flagged_correctly(self, db_session):
        """T2.6: WT construct flagged correctly."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        construct = ConstructService.create_construct(
            project_id=project.id,
            identifier="Tbox1_WT",
            family="Tbox1",
            is_wildtype=True,
            username="researcher"
        )

        assert construct.is_wildtype is True
        assert "WT" in construct.display_name

    def test_one_wt_per_family_enforced(self, db_session):
        """T2.6: One WT per family enforced."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        # Create first WT
        ConstructService.create_construct(
            project_id=project.id,
            identifier="Tbox1_WT",
            family="Tbox1",
            is_wildtype=True,
            username="researcher"
        )

        # Attempt second WT in same family
        with pytest.raises(ConstructValidationError) as excinfo:
            ConstructService.create_construct(
                project_id=project.id,
                identifier="Tbox1_WT2",
                family="Tbox1",
                is_wildtype=True,
                username="researcher"
            )
        assert "already has a wild-type" in str(excinfo.value)

    def test_wt_allowed_in_different_families(self, db_session):
        """Multiple WTs allowed in different families."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        wt1 = ConstructService.create_construct(
            project_id=project.id,
            identifier="Tbox1_WT",
            family="Tbox1",
            is_wildtype=True,
            username="researcher"
        )

        wt2 = ConstructService.create_construct(
            project_id=project.id,
            identifier="Tbox2_WT",
            family="Tbox2",
            is_wildtype=True,
            username="researcher"
        )

        assert wt1.is_wildtype is True
        assert wt2.is_wildtype is True

    def test_unregulated_construct_project_unique(self, db_session):
        """T2.7: Unregulated construct is project-wide unique."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        # Create first unregulated
        ConstructService.create_construct(
            project_id=project.id,
            identifier="Reporter_Only",
            username="researcher",
            is_unregulated=True
        )

        # Attempt second unregulated
        with pytest.raises(ConstructValidationError) as excinfo:
            ConstructService.create_construct(
                project_id=project.id,
                identifier="Reporter_Only_2",
                username="researcher",
                is_unregulated=True
            )
        assert "already has a reporter-only" in str(excinfo.value)

    def test_unregulated_gets_universal_family(self, db_session):
        """Unregulated construct automatically gets universal family."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        construct = ConstructService.create_construct(
            project_id=project.id,
            identifier="Reporter_Only",
            username="researcher",
            is_unregulated=True
        )

        assert construct.family == "universal"
        assert construct.is_unregulated is True

    def test_unregulated_cannot_be_wt(self, db_session):
        """Unregulated construct cannot be marked as WT."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        construct = ConstructService.create_construct(
            project_id=project.id,
            identifier="Reporter_Only",
            username="researcher",
            is_unregulated=True,
            is_wildtype=True  # This should be ignored
        )

        assert construct.is_unregulated is True
        assert construct.is_wildtype is False

    def test_construct_publish_and_unpublish(self, db_session):
        """Test construct publish/unpublish workflow."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        construct = ConstructService.create_construct(
            project_id=project.id,
            identifier="Reporter_Only",
            username="researcher",
            is_unregulated=True
        )

        # Publish construct
        construct = ConstructService.publish_construct(construct.id, "researcher")
        assert construct.is_draft is False

        # Unpublish construct
        construct = ConstructService.unpublish_construct(construct.id, "researcher")
        assert construct.is_draft is True

    def test_list_families(self, db_session):
        """Test family listing with WT status."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        # Create constructs in different families
        ConstructService.create_construct(
            project_id=project.id,
            identifier="Tbox1_WT",
            family="Tbox1",
            is_wildtype=True,
            username="researcher"
        )

        ConstructService.create_construct(
            project_id=project.id,
            identifier="Tbox1_M1",
            family="Tbox1",
            username="researcher"
        )

        ConstructService.create_construct(
            project_id=project.id,
            identifier="Tbox2_M1",
            family="Tbox2",
            username="researcher"
        )

        families = ConstructService.get_families(project.id)
        family_dict = {f["name"]: f for f in families}

        assert len(families) == 2
        assert family_dict["Tbox1"]["construct_count"] == 2
        assert family_dict["Tbox1"]["has_wildtype"] is True
        assert family_dict["Tbox2"]["construct_count"] == 1
        assert family_dict["Tbox2"]["has_wildtype"] is False

    def test_validate_project_anchors_missing_unregulated(self, db_session):
        """Test anchor validation catches missing unregulated."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        ConstructService.create_construct(
            project_id=project.id,
            identifier="Tbox1_WT",
            family="Tbox1",
            is_wildtype=True,
            username="researcher"
        )

        is_valid, issues = ConstructService.validate_project_anchors(project.id)

        assert is_valid is False
        assert any("reporter-only" in issue.lower() for issue in issues)

    def test_validate_project_anchors_missing_wt(self, db_session):
        """Test anchor validation catches missing WT."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        ConstructService.create_construct(
            project_id=project.id,
            identifier="Reporter_Only",
            username="researcher",
            is_unregulated=True
        )

        ConstructService.create_construct(
            project_id=project.id,
            identifier="Tbox1_M1",
            family="Tbox1",
            username="researcher"
        )

        is_valid, issues = ConstructService.validate_project_anchors(project.id)

        assert is_valid is False
        assert any("wild-type" in issue.lower() for issue in issues)

    def test_validate_project_anchors_success(self, db_session):
        """Test anchor validation passes with all anchors."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        # Add unregulated
        ConstructService.create_construct(
            project_id=project.id,
            identifier="Reporter_Only",
            username="researcher",
            is_unregulated=True
        )

        # Add WT for family
        ConstructService.create_construct(
            project_id=project.id,
            identifier="Tbox1_WT",
            family="Tbox1",
            is_wildtype=True,
            username="researcher"
        )

        is_valid, issues = ConstructService.validate_project_anchors(project.id)

        assert is_valid is True
        assert len(issues) == 0
