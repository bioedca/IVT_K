"""
Workflow test fixtures and configuration.

This module provides fixtures for workflow/integration testing including:
- Application test client setup
- Database session management
- Test data factories and teardown
"""
import pytest
from pathlib import Path
import tempfile
import shutil

# Import application components
from app import create_app
from app.config import TestingConfig
from app.extensions import db


@pytest.fixture(scope="session")
def app():
    """Create application instance for workflow testing."""
    app = create_app(TestingConfig)
    yield app


@pytest.fixture(scope="session")
def test_client(app):
    """Create Flask test client for workflow testing."""
    return app.server.test_client()


@pytest.fixture(scope="function")
def db_session(app):
    """Create database session for workflow testing."""
    with app.server.app_context():
        from app import models  # noqa: F401
        db.create_all()
        yield db.session
        db.session.rollback()
        db.session.remove()
        # Clean up tables
        with db.engine.connect() as conn:
            conn.execute(db.text("PRAGMA foreign_keys=OFF"))
            conn.commit()
        db.drop_all()
        with db.engine.connect() as conn:
            conn.execute(db.text("PRAGMA foreign_keys=ON"))
            conn.commit()


@pytest.fixture(scope="function")
def temp_dir():
    """Create temporary directory for workflow test files."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture(scope="function")
def sample_data_dir():
    """Provide path to sample test data."""
    data_dir = Path(__file__).parent.parent / "data"
    if not data_dir.exists():
        pytest.skip("Test data directory not available")
    return data_dir


@pytest.fixture
def project_factory(db_session):
    """Factory fixture for creating test projects in workflow tests."""
    from app.models import Project
    from app.models.project import PlateFormat

    created_ids = []

    def _create(name="Workflow Test Project", plate_format=PlateFormat.PLATE_384):
        project = Project(
            name=name,
            plate_format=plate_format,
            precision_target=0.2
        )
        db.session.add(project)
        db.session.commit()
        created_ids.append(project.id)
        return project

    yield _create
    # Cleanup handled by db_session fixture


@pytest.fixture
def construct_factory(db_session):
    """Factory fixture for creating test constructs in workflow tests."""
    from app.models import Construct

    def _create(project_id, identifier="TEST-001", family="Default Family", is_wt=False):
        construct = Construct(
            project_id=project_id,
            identifier=identifier,
            family=family if family else "Default Family",
            is_wildtype=is_wt
        )
        db.session.add(construct)
        db.session.commit()
        return construct

    yield _create
