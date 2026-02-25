"""Unit tests for PlateLayoutService."""
import pytest
from datetime import datetime

from app.models import Project, Construct
from app.models.plate_layout import PlateLayout, WellAssignment, WellType
from app.services.project_service import ProjectService
from app.services.construct_service import ConstructService
from app.services.plate_layout_service import PlateLayoutService, PlateLayoutValidationError


class TestPlateLayoutService:
    """Tests for PlateLayoutService (Phase 2.4)."""

    def test_create_layout_384(self, db_session):
        """Test creating a 384-well layout."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        layout = PlateLayoutService.create_layout(
            project_id=project.id,
            name="Test Layout",
            username="researcher",
            plate_format="384"
        )

        assert layout.id is not None
        assert layout.name == "Test Layout"
        assert layout.plate_format == "384"
        assert layout.rows == 16
        assert layout.cols == 24
        assert layout.total_wells == 384
        assert layout.is_draft is True
        assert layout.is_template is True

    def test_create_layout_96(self, db_session):
        """Test creating a 96-well layout."""
        from app.models.project import PlateFormat
        project = ProjectService.create_project(
            name="Test Project 96",
            username="researcher",
            plate_format=PlateFormat.PLATE_96
        )

        layout = PlateLayoutService.create_layout(
            project_id=project.id,
            name="Test Layout 96",
            username="researcher",
            plate_format="96"
        )

        assert layout.plate_format == "96"
        assert layout.rows == 8
        assert layout.cols == 12
        assert layout.total_wells == 96

    def test_create_layout_format_mismatch(self, db_session):
        """Test that layout format must match project format."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )  # Default is 384

        with pytest.raises(PlateLayoutValidationError) as excinfo:
            PlateLayoutService.create_layout(
                project_id=project.id,
                name="Test Layout",
                username="researcher",
                plate_format="96"
            )
        assert "must match project format" in str(excinfo.value)

    def test_create_layout_duplicate_name(self, db_session):
        """Test that duplicate layout names are rejected."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        PlateLayoutService.create_layout(
            project_id=project.id,
            name="Test Layout",
            username="researcher"
        )

        with pytest.raises(PlateLayoutValidationError) as excinfo:
            PlateLayoutService.create_layout(
                project_id=project.id,
                name="Test Layout",
                username="researcher"
            )
        assert "already exists" in str(excinfo.value)

    def test_create_layout_empty_name(self, db_session):
        """Test that empty layout name is rejected."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )

        with pytest.raises(PlateLayoutValidationError) as excinfo:
            PlateLayoutService.create_layout(
                project_id=project.id,
                name="",
                username="researcher"
            )
        assert "cannot be empty" in str(excinfo.value)


class TestWellAssignment:
    """Tests for well assignment functionality."""

    @pytest.fixture
    def project_with_layout(self, db_session):
        """Create a project with a layout and construct."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )
        layout = PlateLayoutService.create_layout(
            project_id=project.id,
            name="Test Layout",
            username="researcher"
        )
        construct = ConstructService.create_construct(
            project_id=project.id,
            identifier="Tbox1_WT",
            family="Tbox1",
            is_wildtype=True,
            username="researcher"
        )
        return project, layout, construct

    def test_assign_sample_well(self, db_session, project_with_layout):
        """Test assigning a construct to a well."""
        project, layout, construct = project_with_layout

        assignment = PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A1",
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE
        )

        assert assignment.id is not None
        assert assignment.well_position == "A1"
        assert assignment.construct_id == construct.id
        assert assignment.well_type == WellType.SAMPLE

    def test_assign_negative_control_no_template(self, db_session, project_with_layout):
        """Test assigning a negative control (no template) well."""
        project, layout, construct = project_with_layout

        assignment = PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="H12",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )

        assert assignment.well_type == WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        assert assignment.construct_id is None

    def test_assign_negative_control_no_dye(self, db_session, project_with_layout):
        """Test assigning a negative control (no dye) well."""
        project, layout, construct = project_with_layout

        assignment = PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="H11",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_DYE
        )

        assert assignment.well_type == WellType.NEGATIVE_CONTROL_NO_DYE

    def test_assign_blank_well(self, db_session, project_with_layout):
        """Test assigning a blank well."""
        project, layout, construct = project_with_layout

        assignment = PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A24",
            username="researcher",
            well_type=WellType.BLANK
        )

        assert assignment.well_type == WellType.BLANK
        assert assignment.construct_id is None

    def test_assign_invalid_well_position(self, db_session, project_with_layout):
        """Test that invalid well positions are rejected."""
        project, layout, construct = project_with_layout

        with pytest.raises(PlateLayoutValidationError) as excinfo:
            PlateLayoutService.assign_well(
                layout_id=layout.id,
                well_position="Z99",
                username="researcher",
                well_type=WellType.BLANK
            )
        assert "Invalid well position" in str(excinfo.value)

    def test_assign_sample_requires_construct(self, db_session, project_with_layout):
        """Test that sample wells require a construct."""
        project, layout, construct = project_with_layout

        with pytest.raises(PlateLayoutValidationError) as excinfo:
            PlateLayoutService.assign_well(
                layout_id=layout.id,
                well_position="A1",
                username="researcher",
                well_type=WellType.SAMPLE
            )
        assert "require a construct" in str(excinfo.value)

    def test_assign_well_updates_existing(self, db_session, project_with_layout):
        """Test that assigning to an existing position updates it."""
        project, layout, construct = project_with_layout

        # First assignment
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A1",
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE
        )

        # Second assignment to same position
        updated = PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A1",
            username="researcher",
            well_type=WellType.BLANK
        )

        assert updated.well_type == WellType.BLANK
        assert updated.construct_id is None

        # Verify only one assignment exists
        assignments = WellAssignment.query.filter_by(
            layout_id=layout.id,
            well_position="A1"
        ).all()
        assert len(assignments) == 1

    def test_bulk_assign_wells(self, db_session, project_with_layout):
        """Test bulk assignment of wells."""
        project, layout, construct = project_with_layout

        assignments = PlateLayoutService.bulk_assign_wells(
            layout_id=layout.id,
            well_positions=["A1", "A2", "A3", "A4"],
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE,
            replicate_group="Tbox1_WT_rep"
        )

        assert len(assignments) == 4
        for a in assignments:
            assert a.construct_id == construct.id
            assert a.replicate_group == "Tbox1_WT_rep"

    def test_clear_well(self, db_session, project_with_layout):
        """Test clearing a well assignment."""
        project, layout, construct = project_with_layout

        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A1",
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE
        )

        result = PlateLayoutService.clear_well(layout.id, "A1", "researcher")
        assert result is True

        # Verify well is cleared
        assignment = WellAssignment.query.filter_by(
            layout_id=layout.id,
            well_position="A1"
        ).first()
        assert assignment is None

    def test_clear_nonexistent_well(self, db_session, project_with_layout):
        """Test clearing a well that has no assignment."""
        project, layout, construct = project_with_layout

        result = PlateLayoutService.clear_well(layout.id, "A1", "researcher")
        assert result is False


class TestLayoutValidation:
    """Tests for layout validation (Phase 2.5)."""

    @pytest.fixture
    def project_with_layout(self, db_session):
        """Create a project with a layout and constructs."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )
        layout = PlateLayoutService.create_layout(
            project_id=project.id,
            name="Test Layout",
            username="researcher"
        )
        construct = ConstructService.create_construct(
            project_id=project.id,
            identifier="Tbox1_WT",
            family="Tbox1",
            is_wildtype=True,
            username="researcher"
        )
        return project, layout, construct

    def test_validate_empty_layout(self, db_session, project_with_layout):
        """Test validation fails for empty layout."""
        project, layout, construct = project_with_layout

        is_valid, issues = PlateLayoutService.validate_layout(layout.id)

        assert is_valid is False
        assert "no well assignments" in " ".join(issues).lower()

    def test_validate_missing_negative_controls(self, db_session, project_with_layout):
        """T2.8: Test minimum negative controls enforced."""
        project, layout, construct = project_with_layout

        # Add sample wells but no negative controls
        PlateLayoutService.bulk_assign_wells(
            layout_id=layout.id,
            well_positions=["A1", "A2", "A3", "A4"],
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE
        )

        is_valid, issues = PlateLayoutService.validate_layout(layout.id)

        assert is_valid is False
        assert any("negative control" in issue.lower() for issue in issues)

    def test_validate_one_negative_control_insufficient(self, db_session, project_with_layout):
        """T2.8: Test that 1 negative control is insufficient."""
        project, layout, construct = project_with_layout

        PlateLayoutService.bulk_assign_wells(
            layout_id=layout.id,
            well_positions=["A1", "A2", "A3", "A4"],
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE
        )

        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="H24",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )

        is_valid, issues = PlateLayoutService.validate_layout(layout.id)

        assert is_valid is False
        assert any("2 negative control" in issue.lower() for issue in issues)

    def test_validate_two_negative_controls_sufficient(self, db_session, project_with_layout):
        """T2.8: Test that 2+ negative controls is sufficient."""
        project, layout, construct = project_with_layout

        PlateLayoutService.bulk_assign_wells(
            layout_id=layout.id,
            well_positions=["A1", "A2", "A3", "A4"],
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE
        )

        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="H23",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )

        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="H24",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )

        is_valid, issues = PlateLayoutService.validate_layout(layout.id)

        assert is_valid is True
        assert len(issues) == 0

    def test_validate_mixed_negative_control_types(self, db_session, project_with_layout):
        """Test that mixed negative control types count toward minimum."""
        project, layout, construct = project_with_layout

        PlateLayoutService.bulk_assign_wells(
            layout_id=layout.id,
            well_positions=["A1", "A2"],
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE
        )

        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="H23",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )

        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="H24",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_DYE
        )

        is_valid, issues = PlateLayoutService.validate_layout(layout.id)

        assert is_valid is True

    def test_publish_layout_validates(self, db_session, project_with_layout):
        """Test that publishing validates the layout first."""
        project, layout, construct = project_with_layout

        with pytest.raises(PlateLayoutValidationError) as excinfo:
            PlateLayoutService.publish_layout(layout.id, "researcher")
        assert "validation failed" in str(excinfo.value).lower()

    def test_publish_valid_layout(self, db_session, project_with_layout):
        """Test publishing a valid layout."""
        project, layout, construct = project_with_layout

        # Set up valid layout
        PlateLayoutService.bulk_assign_wells(
            layout_id=layout.id,
            well_positions=["A1", "A2"],
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="H23",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="H24",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )

        layout = PlateLayoutService.publish_layout(layout.id, "researcher")

        assert layout.is_draft is False


class TestLayoutSummaryAndGrid:
    """Tests for layout summary and grid display."""

    @pytest.fixture
    def populated_layout(self, db_session):
        """Create a populated layout for testing."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )
        layout = PlateLayoutService.create_layout(
            project_id=project.id,
            name="Test Layout",
            username="researcher"
        )
        construct1 = ConstructService.create_construct(
            project_id=project.id,
            identifier="Tbox1_WT",
            family="Tbox1",
            is_wildtype=True,
            username="researcher"
        )
        construct2 = ConstructService.create_construct(
            project_id=project.id,
            identifier="Tbox1_M1",
            family="Tbox1",
            username="researcher"
        )

        # Add assignments
        PlateLayoutService.bulk_assign_wells(
            layout_id=layout.id,
            well_positions=["A1", "A2", "A3", "A4"],
            username="researcher",
            construct_id=construct1.id,
            well_type=WellType.SAMPLE
        )
        PlateLayoutService.bulk_assign_wells(
            layout_id=layout.id,
            well_positions=["B1", "B2", "B3", "B4"],
            username="researcher",
            construct_id=construct2.id,
            well_type=WellType.SAMPLE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="P23",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="P24",
            username="researcher",
            well_type=WellType.BLANK
        )

        return project, layout, construct1, construct2

    def test_get_layout_summary(self, db_session, populated_layout):
        """Test getting layout summary statistics."""
        project, layout, construct1, construct2 = populated_layout

        summary = PlateLayoutService.get_layout_summary(layout.id)

        assert summary["layout_id"] == layout.id
        assert summary["name"] == "Test Layout"
        assert summary["plate_format"] == "384"
        assert summary["total_wells"] == 384
        assert summary["assigned_wells"] == 10
        assert summary["empty_wells"] == 374
        assert summary["by_type"]["sample"] == 8
        assert summary["by_type"]["negative_control_no_template"] == 1
        assert summary["by_type"]["blank"] == 1
        assert len(summary["constructs"]) == 2

    def test_get_layout_grid(self, db_session, populated_layout):
        """Test getting layout as 2D grid."""
        project, layout, construct1, construct2 = populated_layout

        grid = PlateLayoutService.get_layout_grid(layout.id)

        assert len(grid) == 16  # 16 rows
        assert len(grid[0]) == 24  # 24 columns

        # Check A1 (construct1)
        assert grid[0][0]["position"] == "A1"
        assert grid[0][0]["well_type"] == "sample"
        assert grid[0][0]["construct_identifier"] == "Tbox1_WT"

        # Check B1 (construct2)
        assert grid[1][0]["position"] == "B1"
        assert grid[1][0]["construct_identifier"] == "Tbox1_M1"

        # Check empty cell
        assert grid[2][0]["position"] == "C1"
        assert grid[2][0]["well_type"] == "empty"
        assert grid[2][0]["construct_id"] is None


class TestLayoutVersioning:
    """Tests for layout versioning."""

    def test_create_version(self, db_session):
        """Test creating a new version of a layout."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )
        layout = PlateLayoutService.create_layout(
            project_id=project.id,
            name="Test Layout",
            username="researcher"
        )
        construct = ConstructService.create_construct(
            project_id=project.id,
            identifier="Tbox1_WT",
            family="Tbox1",
            is_wildtype=True,
            username="researcher"
        )

        # Add some assignments
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A1",
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE
        )

        # Create new version
        new_layout = PlateLayoutService.create_version(layout.id, "researcher")

        assert new_layout.id != layout.id
        assert new_layout.name == layout.name
        assert new_layout.version == 2
        assert new_layout.is_draft is True

        # Check assignments were copied
        new_assignments = WellAssignment.query.filter_by(layout_id=new_layout.id).all()
        assert len(new_assignments) == 1
        assert new_assignments[0].well_position == "A1"

    def test_version_numbers_increment(self, db_session):
        """Test that version numbers increment correctly."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )
        layout = PlateLayoutService.create_layout(
            project_id=project.id,
            name="Test Layout",
            username="researcher"
        )

        v2 = PlateLayoutService.create_version(layout.id, "researcher")
        v3 = PlateLayoutService.create_version(v2.id, "researcher")

        assert layout.version == 1
        assert v2.version == 2
        assert v3.version == 3


class TestLayoutWellPositionValidation:
    """Tests for well position validation in different formats."""

    def test_96_well_valid_positions(self, db_session):
        """T2.9: Test valid positions for 96-well plate."""
        from app.models.project import PlateFormat
        project = ProjectService.create_project(
            name="Test Project 96",
            username="researcher",
            plate_format=PlateFormat.PLATE_96
        )
        layout = PlateLayoutService.create_layout(
            project_id=project.id,
            name="Test Layout",
            username="researcher",
            plate_format="96"
        )

        # Valid corners
        assert PlateLayoutService._validate_well_position("A1", 8, 12) is True
        assert PlateLayoutService._validate_well_position("A12", 8, 12) is True
        assert PlateLayoutService._validate_well_position("H1", 8, 12) is True
        assert PlateLayoutService._validate_well_position("H12", 8, 12) is True

        # Invalid positions
        assert PlateLayoutService._validate_well_position("A13", 8, 12) is False
        assert PlateLayoutService._validate_well_position("I1", 8, 12) is False
        assert PlateLayoutService._validate_well_position("P24", 8, 12) is False

    def test_384_well_valid_positions(self, db_session):
        """Test valid positions for 384-well plate."""
        project = ProjectService.create_project(
            name="Test Project",
            username="researcher"
        )
        layout = PlateLayoutService.create_layout(
            project_id=project.id,
            name="Test Layout",
            username="researcher"
        )

        # Valid corners
        assert PlateLayoutService._validate_well_position("A1", 16, 24) is True
        assert PlateLayoutService._validate_well_position("A24", 16, 24) is True
        assert PlateLayoutService._validate_well_position("P1", 16, 24) is True
        assert PlateLayoutService._validate_well_position("P24", 16, 24) is True

        # Invalid positions
        assert PlateLayoutService._validate_well_position("A25", 16, 24) is False
        assert PlateLayoutService._validate_well_position("Q1", 16, 24) is False


class TestAnchorValidation:
    """Tests for anchor construct validation (Phase 2.5 - F5.6, F5.11)."""

    @pytest.fixture
    def project_with_constructs(self, db_session):
        """Create a project with various constructs for testing."""
        project = ProjectService.create_project(
            name="Anchor Test Project",
            username="researcher"
        )
        layout = PlateLayoutService.create_layout(
            project_id=project.id,
            name="Test Layout",
            username="researcher"
        )

        # Create unregulated construct
        unregulated = ConstructService.create_construct(
            project_id=project.id,
            identifier="Reporter_Only",
            username="researcher",
            is_unregulated=True
        )

        # Create WT for Tbox1 family
        wt = ConstructService.create_construct(
            project_id=project.id,
            identifier="Tbox1_WT",
            family="Tbox1",
            is_wildtype=True,
            username="researcher"
        )

        # Create mutant for Tbox1 family
        mutant = ConstructService.create_construct(
            project_id=project.id,
            identifier="Tbox1_M1",
            family="Tbox1",
            username="researcher"
        )

        return project, layout, unregulated, wt, mutant

    def test_validate_missing_unregulated_on_plate(self, db_session, project_with_constructs):
        """T2.11: Test validation fails when unregulated is missing from plate."""
        project, layout, unregulated, wt, mutant = project_with_constructs

        # Add WT and mutant but not unregulated
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A1",
            username="researcher",
            construct_id=wt.id,
            well_type=WellType.SAMPLE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A2",
            username="researcher",
            construct_id=mutant.id,
            well_type=WellType.SAMPLE
        )
        # Add required negative controls
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="P23",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="P24",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )

        is_valid, issues = PlateLayoutService.validate_layout(layout.id, check_anchors=True)

        assert is_valid is False
        assert any("reporter-only" in issue.lower() or "unregulated" in issue.lower() for issue in issues)

    def test_validate_missing_wt_for_family(self, db_session, project_with_constructs):
        """F5.11: Test validation fails when family has mutants but no WT on plate."""
        project, layout, unregulated, wt, mutant = project_with_constructs

        # Add unregulated and mutant but NOT the WT
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A1",
            username="researcher",
            construct_id=unregulated.id,
            well_type=WellType.SAMPLE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A2",
            username="researcher",
            construct_id=mutant.id,
            well_type=WellType.SAMPLE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="P23",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="P24",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )

        is_valid, issues = PlateLayoutService.validate_layout(layout.id, check_anchors=True)

        assert is_valid is False
        assert any("wild-type" in issue.lower() or "no wild-type" in issue.lower() for issue in issues)

    def test_validate_valid_layout_with_anchors(self, db_session, project_with_constructs):
        """Test validation passes when all anchors are present."""
        project, layout, unregulated, wt, mutant = project_with_constructs

        # Add all required constructs
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A1",
            username="researcher",
            construct_id=unregulated.id,
            well_type=WellType.SAMPLE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A2",
            username="researcher",
            construct_id=wt.id,
            well_type=WellType.SAMPLE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A3",
            username="researcher",
            construct_id=mutant.id,
            well_type=WellType.SAMPLE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="P23",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="P24",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )

        is_valid, issues = PlateLayoutService.validate_layout(layout.id, check_anchors=True)

        assert is_valid is True
        assert len(issues) == 0

    def test_validate_wt_only_family_passes(self, db_session, project_with_constructs):
        """Test that a family with only WT (no mutants) passes validation."""
        project, layout, unregulated, wt, mutant = project_with_constructs

        # Add unregulated and WT only (no mutant) - should pass
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A1",
            username="researcher",
            construct_id=unregulated.id,
            well_type=WellType.SAMPLE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A2",
            username="researcher",
            construct_id=wt.id,
            well_type=WellType.SAMPLE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="P23",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="P24",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )

        is_valid, issues = PlateLayoutService.validate_layout(layout.id, check_anchors=True)

        assert is_valid is True

    def test_validate_invalid_paired_well_reference(self, db_session, project_with_constructs):
        """F5.6: Test that invalid paired_with references are silently ignored.

        When a paired_with position doesn't have an assignment, the relationship
        is simply not set (remains None). This is acceptable behavior since the
        target well may not exist yet during layout construction.
        """
        project, layout, unregulated, wt, mutant = project_with_constructs

        # Add wells with pairing to a position that has no assignment
        # (valid position, but no well assignment there)
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A1",
            username="researcher",
            construct_id=unregulated.id,
            well_type=WellType.SAMPLE
        )
        assignment = PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A2",
            username="researcher",
            construct_id=wt.id,
            well_type=WellType.SAMPLE,
            paired_with="B10"  # Valid position but not assigned - will be silently ignored
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="P23",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="P24",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )

        # The paired_with should be None since B10 has no assignment
        assert assignment.paired_with is None

        # Validation should pass (invalid references are silently ignored)
        is_valid, issues = PlateLayoutService.validate_layout(layout.id, check_anchors=True)
        assert is_valid is True

    def test_validate_for_publish_comprehensive(self, db_session, project_with_constructs):
        """Test comprehensive publish validation."""
        project, layout, unregulated, wt, mutant = project_with_constructs

        # Set up a complete valid layout
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A1",
            username="researcher",
            construct_id=unregulated.id,
            well_type=WellType.SAMPLE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A2",
            username="researcher",
            construct_id=wt.id,
            well_type=WellType.SAMPLE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A3",
            username="researcher",
            construct_id=mutant.id,
            well_type=WellType.SAMPLE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="P23",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="P24",
            username="researcher",
            well_type=WellType.NEGATIVE_CONTROL_NO_TEMPLATE
        )

        is_valid, issues = PlateLayoutService.validate_layout_for_publish(layout.id)

        assert is_valid is True
        assert len(issues) == 0


class TestLigandAssignment:
    """Tests for ligand concentration assignment (Phase 2.7 - F5.10)."""

    @pytest.fixture
    def project_with_layout_and_construct(self, db_session):
        """Create a project with layout and construct for ligand testing."""
        project = ProjectService.create_project(
            name="Ligand Test Project",
            username="researcher"
        )
        layout = PlateLayoutService.create_layout(
            project_id=project.id,
            name="Test Layout",
            username="researcher"
        )
        construct = ConstructService.create_construct(
            project_id=project.id,
            identifier="Test_Construct",
            family="TestFamily",
            username="researcher"
        )
        return project, layout, construct

    def test_assign_well_with_ligand(self, db_session, project_with_layout_and_construct):
        """T2.14: Test assigning ligand concentration to a well."""
        project, layout, construct = project_with_layout_and_construct

        assignment = PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A1",
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE,
            ligand_concentration=10.0
        )

        assert assignment.ligand_concentration == 10.0
        assert assignment.has_ligand is True

    def test_assign_well_without_ligand_defaults_to_none(self, db_session, project_with_layout_and_construct):
        """T2.14: Test that ligand defaults to None (no ligand)."""
        project, layout, construct = project_with_layout_and_construct

        assignment = PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A1",
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE
        )

        assert assignment.ligand_concentration is None
        assert assignment.has_ligand is False

    def test_assign_well_with_zero_ligand(self, db_session, project_with_layout_and_construct):
        """Test assigning zero ligand concentration."""
        project, layout, construct = project_with_layout_and_construct

        assignment = PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A1",
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE,
            ligand_concentration=0.0
        )

        assert assignment.ligand_concentration == 0.0
        assert assignment.has_ligand is False  # 0 means no ligand

    def test_assign_well_negative_ligand_rejected(self, db_session, project_with_layout_and_construct):
        """Test that negative ligand concentration is rejected."""
        project, layout, construct = project_with_layout_and_construct

        with pytest.raises(PlateLayoutValidationError) as excinfo:
            PlateLayoutService.assign_well(
                layout_id=layout.id,
                well_position="A1",
                username="researcher",
                construct_id=construct.id,
                well_type=WellType.SAMPLE,
                ligand_concentration=-5.0
            )
        assert "negative" in str(excinfo.value).lower()

    def test_bulk_assign_wells_with_ligand(self, db_session, project_with_layout_and_construct):
        """T2.13: Test bulk assignment with ligand concentration."""
        project, layout, construct = project_with_layout_and_construct

        assignments = PlateLayoutService.bulk_assign_wells(
            layout_id=layout.id,
            well_positions=["A1", "A2", "A3", "A4"],
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE,
            ligand_concentration=25.0
        )

        assert len(assignments) == 4
        for a in assignments:
            assert a.ligand_concentration == 25.0

    def test_bulk_assign_ligand_to_existing_wells(self, db_session, project_with_layout_and_construct):
        """T2.13: Test bulk ligand assignment to existing wells."""
        project, layout, construct = project_with_layout_and_construct

        # First create wells without ligand
        PlateLayoutService.bulk_assign_wells(
            layout_id=layout.id,
            well_positions=["A1", "A2", "A3", "A4"],
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE
        )

        # Now assign ligand to them
        updated = PlateLayoutService.bulk_assign_ligand(
            layout_id=layout.id,
            well_positions=["A1", "A2", "A3", "A4"],
            ligand_concentration=50.0,
            username="researcher"
        )

        assert len(updated) == 4
        for a in updated:
            assert a.ligand_concentration == 50.0

    def test_bulk_assign_ligand_skips_unassigned_wells(self, db_session, project_with_layout_and_construct):
        """Test that bulk ligand assignment only updates existing wells."""
        project, layout, construct = project_with_layout_and_construct

        # Create only 2 wells
        PlateLayoutService.bulk_assign_wells(
            layout_id=layout.id,
            well_positions=["A1", "A2"],
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE
        )

        # Try to assign ligand to 4 wells (2 don't exist)
        updated = PlateLayoutService.bulk_assign_ligand(
            layout_id=layout.id,
            well_positions=["A1", "A2", "A3", "A4"],
            ligand_concentration=100.0,
            username="researcher"
        )

        # Only 2 should be updated
        assert len(updated) == 2

    def test_layout_summary_includes_ligand_info(self, db_session, project_with_layout_and_construct):
        """Test that layout summary includes ligand statistics."""
        project, layout, construct = project_with_layout_and_construct

        # Create wells with different ligand concentrations
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A1",
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE,
            ligand_concentration=10.0
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A2",
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE,
            ligand_concentration=50.0
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A3",
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE,
            ligand_concentration=50.0  # Same as A2
        )
        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A4",
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE
            # No ligand
        )

        summary = PlateLayoutService.get_layout_summary(layout.id)

        assert summary["ligand"]["wells_with_ligand"] == 3
        assert summary["ligand"]["concentration_count"] == 2
        assert 10.0 in summary["ligand"]["unique_concentrations"]
        assert 50.0 in summary["ligand"]["unique_concentrations"]

    def test_layout_grid_includes_ligand_concentration(self, db_session, project_with_layout_and_construct):
        """Test that layout grid includes ligand concentration."""
        project, layout, construct = project_with_layout_and_construct

        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A1",
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE,
            ligand_concentration=25.5
        )

        grid = PlateLayoutService.get_layout_grid(layout.id)

        # A1 is first cell
        assert grid[0][0]["position"] == "A1"
        assert grid[0][0]["ligand_concentration"] == 25.5

        # Empty cell should have None
        assert grid[0][1]["position"] == "A2"
        assert grid[0][1]["ligand_concentration"] is None

    def test_create_version_copies_ligand(self, db_session, project_with_layout_and_construct):
        """Test that creating a new version copies ligand concentration."""
        project, layout, construct = project_with_layout_and_construct

        PlateLayoutService.assign_well(
            layout_id=layout.id,
            well_position="A1",
            username="researcher",
            construct_id=construct.id,
            well_type=WellType.SAMPLE,
            ligand_concentration=75.0
        )

        new_layout = PlateLayoutService.create_version(layout.id, "researcher")

        # Check ligand was copied
        new_assignments = WellAssignment.query.filter_by(layout_id=new_layout.id).all()
        assert len(new_assignments) == 1
        assert new_assignments[0].ligand_concentration == 75.0
