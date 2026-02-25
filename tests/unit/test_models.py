"""Unit tests for database models."""
import pytest
from datetime import datetime, date

from app.models import (
    Project, Construct, PlateLayout, WellAssignment,
    ExperimentalSession, Plate, Well, RawDataPoint,
    FitResult, AnalysisVersion, AuditLog
)
from app.models.project import PlateFormat
from app.models.plate_layout import WellType
from app.models.experiment import FitStatus
from app.models.analysis_version import AnalysisStatus


class TestProjectModel:
    """Tests for Project model."""

    def test_project_creation(self, db_session):
        """Test creating a project with auto-generated slug."""
        project = Project(
            name="Test Project",
            description="A test project",
            reporter_system="iSpinach"
        )
        db_session.add(project)
        db_session.commit()

        assert project.id is not None
        assert project.name == "Test Project"
        assert project.name_slug == "test_project"
        assert project.plate_format == PlateFormat.PLATE_384
        assert project.is_draft is True

    def test_project_slug_special_characters(self, db_session):
        """Test slug generation with special characters."""
        project = Project(name="Tbox Analysis (v2)")
        db_session.add(project)
        db_session.commit()

        assert project.name_slug == "tbox_analysis_v2"

    def test_project_plate_dimensions(self, db_session):
        """Test plate dimension properties."""
        project_384 = Project(name="384 Project", plate_format=PlateFormat.PLATE_384)
        project_96 = Project(name="96 Project", plate_format=PlateFormat.PLATE_96)

        assert project_384.plate_rows == 16
        assert project_384.plate_cols == 24
        assert project_96.plate_rows == 8
        assert project_96.plate_cols == 12


class TestConstructModel:
    """Tests for Construct model."""

    def test_construct_creation(self, db_session):
        """Test creating a construct."""
        project = Project(name="Test Project")
        db_session.add(project)
        db_session.commit()

        construct = Construct(
            project_id=project.id,
            identifier="Tbox1_WT",
            family="Tbox1",
            is_wildtype=True
        )
        db_session.add(construct)
        db_session.commit()

        assert construct.id is not None
        assert construct.identifier == "Tbox1_WT"
        assert construct.is_wildtype is True
        assert construct.display_name == "Tbox1_WT (WT)"

    def test_unregulated_construct(self, db_session):
        """Test unregulated construct display name."""
        project = Project(name="Test Project")
        db_session.add(project)
        db_session.commit()

        construct = Construct(
            project_id=project.id,
            identifier="Reporter_Only",
            family="universal",
            is_unregulated=True
        )
        db_session.add(construct)
        db_session.commit()

        assert construct.display_name == "Reporter_Only (Unregulated)"


class TestPlateLayoutModel:
    """Tests for PlateLayout model."""

    def test_layout_creation_384(self, db_session):
        """Test creating a 384-well layout."""
        project = Project(name="Test Project")
        db_session.add(project)
        db_session.commit()

        layout = PlateLayout(
            project_id=project.id,
            name="Standard Layout",
            plate_format="384"
        )
        db_session.add(layout)
        db_session.commit()

        assert layout.rows == 16
        assert layout.cols == 24
        assert layout.total_wells == 384

    def test_layout_creation_96(self, db_session):
        """Test creating a 96-well layout."""
        project = Project(name="Test Project")
        db_session.add(project)
        db_session.commit()

        layout = PlateLayout(
            project_id=project.id,
            name="96 Well Layout",
            plate_format="96"
        )
        db_session.add(layout)
        db_session.commit()

        assert layout.rows == 8
        assert layout.cols == 12
        assert layout.total_wells == 96


class TestWellModel:
    """Tests for Well model."""

    def test_well_position_parsing(self, db_session):
        """Test well position property parsing."""
        project = Project(name="Test Project")
        db_session.add(project)
        db_session.commit()

        session = ExperimentalSession(
            project_id=project.id,
            date=date.today(),
            batch_identifier="Batch001"
        )
        db_session.add(session)

        layout = PlateLayout(project_id=project.id, name="Layout")
        db_session.add(layout)
        db_session.commit()

        plate = Plate(
            session_id=session.id,
            layout_id=layout.id,
            plate_number=1
        )
        db_session.add(plate)
        db_session.commit()

        well = Well(
            plate_id=plate.id,
            position="B12",
            well_type=WellType.SAMPLE
        )
        db_session.add(well)
        db_session.commit()

        assert well.row_letter == "B"
        assert well.col_number == 12


class TestAuditLogModel:
    """Tests for AuditLog model."""

    def test_audit_log_creation(self, db_session):
        """Test creating an audit log entry."""
        log = AuditLog.log_action(
            username="test_user",
            action_type="create",
            entity_type="project",
            entity_id=1,
            changes=[{"field": "name", "old": None, "new": "Test Project"}]
        )
        db_session.commit()

        assert log.id is not None
        assert log.username == "test_user"
        assert log.action_type == "create"
        assert len(log.changes) == 1


class TestAnalysisVersionModel:
    """Tests for AnalysisVersion model."""

    def test_analysis_version_creation(self, db_session):
        """Test creating an analysis version."""
        project = Project(name="Test Project")
        db_session.add(project)
        db_session.commit()

        version = AnalysisVersion(
            project_id=project.id,
            name="Initial Analysis",
            model_type="delayed_exponential"
        )
        db_session.add(version)
        db_session.commit()

        assert version.id is not None
        assert version.status == AnalysisStatus.RUNNING
        assert version.is_complete is False

    def test_analysis_version_completion(self, db_session):
        """Test analysis version completion status."""
        project = Project(name="Test Project")
        db_session.add(project)
        db_session.commit()

        version = AnalysisVersion(
            project_id=project.id,
            name="Completed Analysis",
            model_type="delayed_exponential",
            status=AnalysisStatus.COMPLETED
        )
        db_session.add(version)
        db_session.commit()

        assert version.is_complete is True
