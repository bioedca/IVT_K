"""
Pytest fixtures for IVT Kinetics Analyzer tests.
"""
import pytest
from pathlib import Path
import tempfile
import shutil

from app import create_app
from app.config import TestingConfig
from app.extensions import db


@pytest.fixture(scope="session")
def app():
    """Create application for testing."""
    app = create_app(TestingConfig)
    yield app


@pytest.fixture(scope="function")
def client(app):
    """Create test client."""
    return app.server.test_client()


@pytest.fixture(scope="function")
def db_session(app):
    """Create database session for testing."""
    with app.server.app_context():
        # Import all models to ensure they are registered
        from app import models  # noqa: F401
        db.create_all()
        yield db.session
        db.session.rollback()
        db.session.remove()
        # Disable foreign key checks for clean drop
        with db.engine.connect() as conn:
            conn.execute(db.text("PRAGMA foreign_keys=OFF"))
            conn.commit()
        db.drop_all()
        with db.engine.connect() as conn:
            conn.execute(db.text("PRAGMA foreign_keys=ON"))
            conn.commit()


@pytest.fixture(scope="function")
def temp_data_dir():
    """Create temporary data directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_biotek_file(temp_data_dir):
    """Provide path to sample BioTek file."""
    # Copy sample file to temp directory if needed
    sample_path = Path(__file__).parent.parent / "example_files"
    if sample_path.exists():
        for f in sample_path.glob("*.txt"):
            shutil.copy(f, temp_data_dir)
    return temp_data_dir


@pytest.fixture(scope="function")
def test_project(db_session):
    """
    Factory fixture for creating test projects.

    Usage:
        project = test_project()  # Creates with default name
        project = test_project(name="Custom Name")  # Creates with custom name
    """
    from app.models import Project
    from app.models.project import PlateFormat

    created_projects = []
    counter = [0]  # Use list to make it mutable in closure

    def _create_project(name=None, plate_format=PlateFormat.PLATE_384, precision_target=0.2):
        counter[0] += 1
        if name is None:
            name = f"Test Project {counter[0]}"

        project = Project(
            name=name,
            plate_format=plate_format,
            precision_target=precision_target,
        )
        db.session.add(project)
        db.session.commit()
        created_projects.append(project.id)
        return project

    yield _create_project

    # Cleanup handled by db_session fixture
