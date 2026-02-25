"""Integration tests for plate layout API endpoints."""
import pytest
from flask import json

from app.models import Project
from app.models.plate_layout import PlateLayout, WellAssignment, WellType
from app.services.project_service import ProjectService
from app.services.construct_service import ConstructService


class TestLayoutAPI:
    """Tests for plate layout API endpoints."""

    @pytest.fixture
    def project(self, db_session):
        """Create a test project."""
        return ProjectService.create_project(
            name="API Test Project",
            username="tester"
        )

    @pytest.fixture
    def construct(self, db_session, project):
        """Create a test construct."""
        return ConstructService.create_construct(
            project_id=project.id,
            identifier="Test_Construct",
            family="TestFamily",
            username="tester"
        )

    def test_list_layouts_empty(self, client, db_session, project):
        """Test listing layouts when none exist."""
        response = client.get(f'/api/projects/{project.id}/layouts')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['layouts'] == []

    def test_create_layout(self, client, db_session, project):
        """Test creating a new layout."""
        response = client.post(
            f'/api/projects/{project.id}/layouts',
            json={'name': 'Test Layout'},
            headers={'X-Username': 'tester'}
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['name'] == 'Test Layout'
        assert data['plate_format'] == '384'
        assert data['rows'] == 16
        assert data['cols'] == 24
        assert data['is_draft'] is True

    def test_create_layout_missing_name(self, client, db_session, project):
        """Test creating layout without name fails."""
        response = client.post(
            f'/api/projects/{project.id}/layouts',
            json={},
            headers={'X-Username': 'tester'}
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_get_layout(self, client, db_session, project):
        """Test getting a layout by ID."""
        # Create a layout
        create_response = client.post(
            f'/api/projects/{project.id}/layouts',
            json={'name': 'Test Layout'},
            headers={'X-Username': 'tester'}
        )
        layout_id = json.loads(create_response.data)['id']

        # Get the layout
        response = client.get(f'/api/layouts/{layout_id}')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['id'] == layout_id
        assert data['name'] == 'Test Layout'

    def test_get_layout_not_found(self, client, db_session):
        """Test getting non-existent layout returns 404."""
        response = client.get('/api/layouts/99999')

        assert response.status_code == 404

    def test_assign_well(self, client, db_session, project, construct):
        """Test assigning a construct to a well."""
        # Create layout
        create_response = client.post(
            f'/api/projects/{project.id}/layouts',
            json={'name': 'Test Layout'},
            headers={'X-Username': 'tester'}
        )
        layout_id = json.loads(create_response.data)['id']

        # Assign well
        response = client.post(
            f'/api/layouts/{layout_id}/wells',
            json={
                'well_position': 'A1',
                'construct_id': construct.id,
                'well_type': 'sample'
            },
            headers={'X-Username': 'tester'}
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['well_position'] == 'A1'
        assert data['construct_id'] == construct.id
        assert data['well_type'] == 'sample'

    def test_assign_negative_control(self, client, db_session, project):
        """Test assigning a negative control well."""
        # Create layout
        create_response = client.post(
            f'/api/projects/{project.id}/layouts',
            json={'name': 'Test Layout'},
            headers={'X-Username': 'tester'}
        )
        layout_id = json.loads(create_response.data)['id']

        # Assign negative control
        response = client.post(
            f'/api/layouts/{layout_id}/wells',
            json={
                'well_position': 'H12',
                'well_type': 'negative_control_no_template'
            },
            headers={'X-Username': 'tester'}
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['well_type'] == 'negative_control_no_template'
        assert data['construct_id'] is None

    def test_bulk_assign_wells(self, client, db_session, project, construct):
        """Test bulk assignment of wells."""
        # Create layout
        create_response = client.post(
            f'/api/projects/{project.id}/layouts',
            json={'name': 'Test Layout'},
            headers={'X-Username': 'tester'}
        )
        layout_id = json.loads(create_response.data)['id']

        # Bulk assign
        response = client.post(
            f'/api/layouts/{layout_id}/wells/bulk',
            json={
                'well_positions': ['A1', 'A2', 'A3', 'A4'],
                'construct_id': construct.id,
                'well_type': 'sample',
                'replicate_group': 'Test_rep'
            },
            headers={'X-Username': 'tester'}
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['assigned_count'] == 4
        assert len(data['assignments']) == 4

    def test_clear_well(self, client, db_session, project, construct):
        """Test clearing a well assignment."""
        # Create layout and assign well
        create_response = client.post(
            f'/api/projects/{project.id}/layouts',
            json={'name': 'Test Layout'},
            headers={'X-Username': 'tester'}
        )
        layout_id = json.loads(create_response.data)['id']

        client.post(
            f'/api/layouts/{layout_id}/wells',
            json={
                'well_position': 'A1',
                'construct_id': construct.id,
                'well_type': 'sample'
            },
            headers={'X-Username': 'tester'}
        )

        # Clear the well
        response = client.delete(
            f'/api/layouts/{layout_id}/wells/A1',
            headers={'X-Username': 'tester'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'cleared' in data['message']

    def test_get_layout_summary(self, client, db_session, project, construct):
        """Test getting layout summary."""
        # Create layout with assignments
        create_response = client.post(
            f'/api/projects/{project.id}/layouts',
            json={'name': 'Test Layout'},
            headers={'X-Username': 'tester'}
        )
        layout_id = json.loads(create_response.data)['id']

        client.post(
            f'/api/layouts/{layout_id}/wells/bulk',
            json={
                'well_positions': ['A1', 'A2'],
                'construct_id': construct.id,
                'well_type': 'sample'
            },
            headers={'X-Username': 'tester'}
        )

        # Get summary
        response = client.get(f'/api/layouts/{layout_id}/summary')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['assigned_wells'] == 2
        assert data['by_type']['sample'] == 2

    def test_get_layout_grid(self, client, db_session, project, construct):
        """Test getting layout as grid."""
        # Create layout with an assignment
        create_response = client.post(
            f'/api/projects/{project.id}/layouts',
            json={'name': 'Test Layout'},
            headers={'X-Username': 'tester'}
        )
        layout_id = json.loads(create_response.data)['id']

        client.post(
            f'/api/layouts/{layout_id}/wells',
            json={
                'well_position': 'A1',
                'construct_id': construct.id,
                'well_type': 'sample'
            },
            headers={'X-Username': 'tester'}
        )

        # Get grid
        response = client.get(f'/api/layouts/{layout_id}/grid')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['grid']) == 16  # 16 rows
        assert len(data['grid'][0]) == 24  # 24 cols
        assert data['grid'][0][0]['position'] == 'A1'
        assert data['grid'][0][0]['well_type'] == 'sample'

    def test_validate_layout_empty(self, client, db_session, project):
        """Test validating empty layout fails."""
        # Create empty layout
        create_response = client.post(
            f'/api/projects/{project.id}/layouts',
            json={'name': 'Test Layout'},
            headers={'X-Username': 'tester'}
        )
        layout_id = json.loads(create_response.data)['id']

        # Validate
        response = client.get(f'/api/layouts/{layout_id}/validate')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['is_valid'] is False
        assert len(data['issues']) > 0

    def test_validate_layout_valid(self, client, db_session, project, construct):
        """Test validating a valid layout."""
        # Create layout with proper assignments
        create_response = client.post(
            f'/api/projects/{project.id}/layouts',
            json={'name': 'Test Layout'},
            headers={'X-Username': 'tester'}
        )
        layout_id = json.loads(create_response.data)['id']

        # Add sample wells
        client.post(
            f'/api/layouts/{layout_id}/wells/bulk',
            json={
                'well_positions': ['A1', 'A2'],
                'construct_id': construct.id,
                'well_type': 'sample'
            },
            headers={'X-Username': 'tester'}
        )

        # Add negative controls
        client.post(
            f'/api/layouts/{layout_id}/wells/bulk',
            json={
                'well_positions': ['P23', 'P24'],
                'well_type': 'negative_control_no_template'
            },
            headers={'X-Username': 'tester'}
        )

        # Validate
        response = client.get(f'/api/layouts/{layout_id}/validate')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['is_valid'] is True
        assert len(data['issues']) == 0

    def test_publish_layout(self, client, db_session, project, construct):
        """Test publishing a valid layout."""
        # Create layout with proper assignments
        create_response = client.post(
            f'/api/projects/{project.id}/layouts',
            json={'name': 'Test Layout'},
            headers={'X-Username': 'tester'}
        )
        layout_id = json.loads(create_response.data)['id']

        client.post(
            f'/api/layouts/{layout_id}/wells/bulk',
            json={
                'well_positions': ['A1', 'A2'],
                'construct_id': construct.id,
                'well_type': 'sample'
            },
            headers={'X-Username': 'tester'}
        )
        client.post(
            f'/api/layouts/{layout_id}/wells/bulk',
            json={
                'well_positions': ['P23', 'P24'],
                'well_type': 'negative_control_no_template'
            },
            headers={'X-Username': 'tester'}
        )

        # Publish
        response = client.post(
            f'/api/layouts/{layout_id}/publish',
            headers={'X-Username': 'tester'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['is_draft'] is False

    def test_publish_invalid_layout_fails(self, client, db_session, project):
        """Test publishing invalid layout fails."""
        # Create empty layout
        create_response = client.post(
            f'/api/projects/{project.id}/layouts',
            json={'name': 'Test Layout'},
            headers={'X-Username': 'tester'}
        )
        layout_id = json.loads(create_response.data)['id']

        # Try to publish
        response = client.post(
            f'/api/layouts/{layout_id}/publish',
            headers={'X-Username': 'tester'}
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_unpublish_layout(self, client, db_session, project, construct):
        """Test unpublishing a layout."""
        # Create and publish layout
        create_response = client.post(
            f'/api/projects/{project.id}/layouts',
            json={'name': 'Test Layout'},
            headers={'X-Username': 'tester'}
        )
        layout_id = json.loads(create_response.data)['id']

        client.post(
            f'/api/layouts/{layout_id}/wells/bulk',
            json={
                'well_positions': ['A1', 'A2'],
                'construct_id': construct.id,
                'well_type': 'sample'
            },
            headers={'X-Username': 'tester'}
        )
        client.post(
            f'/api/layouts/{layout_id}/wells/bulk',
            json={
                'well_positions': ['P23', 'P24'],
                'well_type': 'negative_control_no_template'
            },
            headers={'X-Username': 'tester'}
        )
        client.post(f'/api/layouts/{layout_id}/publish', headers={'X-Username': 'tester'})

        # Unpublish
        response = client.post(
            f'/api/layouts/{layout_id}/unpublish',
            headers={'X-Username': 'tester'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['is_draft'] is True

    def test_create_layout_version(self, client, db_session, project, construct):
        """Test creating a new version of a layout."""
        # Create layout with assignments
        create_response = client.post(
            f'/api/projects/{project.id}/layouts',
            json={'name': 'Test Layout'},
            headers={'X-Username': 'tester'}
        )
        layout_id = json.loads(create_response.data)['id']

        client.post(
            f'/api/layouts/{layout_id}/wells',
            json={
                'well_position': 'A1',
                'construct_id': construct.id,
                'well_type': 'sample'
            },
            headers={'X-Username': 'tester'}
        )

        # Create new version
        response = client.post(
            f'/api/layouts/{layout_id}/version',
            headers={'X-Username': 'tester'}
        )

        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['version'] == 2
        assert data['source_layout_id'] == layout_id

    def test_list_layouts_with_filter(self, client, db_session, project, construct):
        """Test listing layouts with filters."""
        # Create and publish a layout
        create_response = client.post(
            f'/api/projects/{project.id}/layouts',
            json={'name': 'Published Layout'},
            headers={'X-Username': 'tester'}
        )
        layout_id = json.loads(create_response.data)['id']

        client.post(
            f'/api/layouts/{layout_id}/wells/bulk',
            json={
                'well_positions': ['A1', 'A2'],
                'construct_id': construct.id,
                'well_type': 'sample'
            },
            headers={'X-Username': 'tester'}
        )
        client.post(
            f'/api/layouts/{layout_id}/wells/bulk',
            json={
                'well_positions': ['P23', 'P24'],
                'well_type': 'negative_control_no_template'
            },
            headers={'X-Username': 'tester'}
        )
        client.post(f'/api/layouts/{layout_id}/publish', headers={'X-Username': 'tester'})

        # Create another draft layout
        client.post(
            f'/api/projects/{project.id}/layouts',
            json={'name': 'Draft Layout'},
            headers={'X-Username': 'tester'}
        )

        # List all layouts
        response = client.get(f'/api/projects/{project.id}/layouts')
        data = json.loads(response.data)
        assert len(data['layouts']) == 2

        # List only published
        response = client.get(f'/api/projects/{project.id}/layouts?include_draft=false')
        data = json.loads(response.data)
        assert len(data['layouts']) == 1
        assert data['layouts'][0]['is_draft'] is False
