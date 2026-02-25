"""
E2E tests for project workflow.

PRD Reference: Section 4.1 - E2E testing

Tests the complete project creation and setup workflow:
- Create new project
- Configure project settings
- Add constructs
- Set up plate layout
"""
import pytest
from pathlib import Path


class TestProjectCreationWorkflow:
    """Test project creation workflow."""

    def test_create_project_via_client(self, test_client, db_session):
        """Test creating a project via test client."""
        from app.models import Project
        from app.models.project import PlateFormat

        # Create project directly (simulating API call)
        project = Project(
            name="E2E Test Project",
            plate_format=PlateFormat.PLATE_384,
            precision_target=0.2
        )
        db_session.add(project)
        db_session.commit()

        # Verify project was created
        assert project.id is not None
        assert project.name == "E2E Test Project"
        assert project.plate_format == PlateFormat.PLATE_384

    def test_project_with_constructs(self, test_client, db_session, project_factory, construct_factory):
        """Test creating a project with constructs."""
        # Create project
        project = project_factory(name="Project with Constructs")

        # Add constructs
        wt_construct = construct_factory(
            project_id=project.id,
            identifier="WT-001",
            family="Family A",
            is_wt=True
        )
        variant1 = construct_factory(
            project_id=project.id,
            identifier="VAR-001",
            family="Family A",
            is_wt=False
        )
        variant2 = construct_factory(
            project_id=project.id,
            identifier="VAR-002",
            family="Family A",
            is_wt=False
        )

        # Verify constructs
        assert len(project.constructs) == 3
        assert wt_construct.is_wildtype
        assert not variant1.is_wildtype



class TestProjectSettingsWorkflow:
    """Test project settings configuration workflow."""

    def test_update_project_settings(self, db_session, project_factory):
        """Test updating project settings."""
        from app.models.project import PlateFormat

        project = project_factory(name="Settings Test")

        # Update settings
        project.precision_target = 0.15
        project.plate_format = PlateFormat.PLATE_96
        db_session.commit()

        # Refresh and verify
        db_session.refresh(project)
        assert project.precision_target == 0.15
        assert project.plate_format == PlateFormat.PLATE_96

    def test_project_precision_target_range(self, db_session, project_factory):
        """Test that precision target is within valid range."""
        project = project_factory()

        # Valid range is typically 0.1 to 0.5
        valid_targets = [0.1, 0.2, 0.3, 0.5]
        for target in valid_targets:
            project.precision_target = target
            db_session.commit()
            assert project.precision_target == target


class TestConstructManagementWorkflow:
    """Test construct management workflow."""

    def test_add_construct_to_project(self, db_session, project_factory, construct_factory):
        """Test adding a construct to a project."""
        project = project_factory()

        construct = construct_factory(
            project_id=project.id,
            identifier="NEW-001",
            family="Test Family"
        )

        assert construct in project.constructs
        assert construct.project_id == project.id

    def test_construct_family_grouping(self, db_session, project_factory, construct_factory):
        """Test that constructs are grouped by family."""
        project = project_factory()

        # Add constructs from different families
        c1 = construct_factory(project.id, "A-001", "Family A")
        c2 = construct_factory(project.id, "A-002", "Family A")
        c3 = construct_factory(project.id, "B-001", "Family B")

        # Verify family assignment
        assert c1.family == c2.family == "Family A"
        assert c3.family == "Family B"

        # Get constructs by family
        family_a = [c for c in project.constructs if c.family == "Family A"]
        family_b = [c for c in project.constructs if c.family == "Family B"]

        assert len(family_a) == 2
        assert len(family_b) == 1

    def test_wild_type_designation(self, db_session, project_factory, construct_factory):
        """Test wild type construct designation."""
        project = project_factory()

        wt = construct_factory(project.id, "WT", "Family A", is_wt=True)
        var = construct_factory(project.id, "VAR", "Family A", is_wt=False)

        assert wt.is_wildtype
        assert not var.is_wildtype


class TestPlateLayoutWorkflow:
    """Test plate layout configuration workflow."""

    def test_create_plate_layout(self, db_session, project_factory):
        """Test creating a plate layout for a project."""
        from app.models import PlateLayout

        project = project_factory()

        # Create plate layout
        layout = PlateLayout(
            project_id=project.id,
            name="Layout 1"
        )
        db_session.add(layout)
        db_session.commit()

        assert layout.id is not None
        assert layout.project_id == project.id

    def test_plate_layout_with_wells(self, db_session, project_factory, construct_factory):
        """Test plate layout with well assignments."""
        from app.models import PlateLayout, WellAssignment
        from app.models.plate_layout import WellType

        project = project_factory()
        construct = construct_factory(project.id, "TEST-001")

        # Create layout
        layout = PlateLayout(
            project_id=project.id,
            name="Test Layout"
        )
        db_session.add(layout)
        db_session.commit()

        # Add well assignments
        well = WellAssignment(
            layout_id=layout.id,
            well_position="A1",
            construct_id=construct.id,
            well_type=WellType.SAMPLE
        )
        db_session.add(well)
        db_session.commit()

        assert len(layout.well_assignments) >= 1


class TestProjectWorkflowIntegration:
    """Integration tests for complete project workflow."""

    def test_complete_project_setup(self, db_session, project_factory, construct_factory):
        """Test complete project setup workflow."""
        from app.models import PlateLayout, WellAssignment
        from app.models.plate_layout import WellType

        # 1. Create project
        project = project_factory(name="Complete Workflow Test")

        # 2. Add constructs
        wt = construct_factory(project.id, "WT-001", "Main Family", is_wt=True)
        var1 = construct_factory(project.id, "VAR-001", "Main Family")
        var2 = construct_factory(project.id, "VAR-002", "Main Family")
        ctrl = construct_factory(project.id, "CTRL-001", "Control")

        # 3. Create plate layout
        layout = PlateLayout(
            project_id=project.id,
            name="Experiment Layout"
        )
        db_session.add(layout)
        db_session.commit()

        # 4. Assign wells
        wells_data = [
            ("A1", wt.id, WellType.SAMPLE),
            ("A2", var1.id, WellType.SAMPLE),
            ("A3", var2.id, WellType.SAMPLE),
            ("A4", ctrl.id, WellType.NEGATIVE_CONTROL_NO_TEMPLATE),
        ]
        for pos, cid, wtype in wells_data:
            well = WellAssignment(
                layout_id=layout.id,
                well_position=pos,
                construct_id=cid,
                well_type=wtype
            )
            db_session.add(well)
        db_session.commit()

        # Verify complete setup
        assert len(project.constructs) == 4
        assert len(layout.well_assignments) == 4
        assert project.precision_target == 0.2
