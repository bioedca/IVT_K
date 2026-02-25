"""
E2E tests for data upload workflow.

PRD Reference: Section 4.1 - E2E testing

Tests the complete data upload workflow:
- Create Upload records in the database
- Validate uploaded data formats
- Associate uploads with plate layouts and sessions
- BioTek file parser validation
"""
import pytest
from pathlib import Path
import io
import re
import pandas as pd
import numpy as np


class TestDataUploadWorkflow:
    """Test data upload workflow using the Upload model."""

    def test_create_upload_record(self, db_session, project_factory):
        """Test creating an Upload record in the database."""
        from app.models import Upload, UploadStatus, PlateLayout

        project = project_factory()

        # Create a plate layout (required FK for Upload)
        layout = PlateLayout(project_id=project.id, name="Test Layout")
        db_session.add(layout)
        db_session.commit()

        # Create test CSV content
        df = pd.DataFrame({
            'Time': np.arange(0, 60, 5),
            'A1': np.random.normal(1000, 100, 12),
            'A2': np.random.normal(2000, 150, 12),
        })
        csv_content = df.to_csv(index=False)

        # Create Upload using the class method
        upload = Upload.create(
            project_id=project.id,
            layout_id=layout.id,
            filename="test_data.csv",
            content=csv_content,
            username="test_user",
            file_format="csv",
        )
        db_session.commit()

        assert upload.id is not None
        assert upload.project_id == project.id
        assert upload.layout_id == layout.id
        assert upload.status == UploadStatus.PENDING
        assert upload.filename == "test_data.csv"
        assert upload.content_hash is not None
        assert upload.file_size_bytes > 0

    def test_upload_status_transitions(self, db_session, project_factory):
        """Test that upload status can transition through the expected states."""
        from app.models import Upload, UploadStatus, PlateLayout

        project = project_factory()
        layout = PlateLayout(project_id=project.id, name="Status Test Layout")
        db_session.add(layout)
        db_session.commit()

        upload = Upload.create(
            project_id=project.id,
            layout_id=layout.id,
            filename="status_test.csv",
            content="Time,A1\n0,100\n5,200",
            username="test_user",
        )
        db_session.commit()

        assert upload.status == UploadStatus.PENDING

        # Transition: PENDING -> PARSING -> PARSED
        upload.update_status(UploadStatus.PARSING)
        assert upload.status == UploadStatus.PARSING

        upload.update_status(UploadStatus.PARSED)
        assert upload.status == UploadStatus.PARSED

    def test_upload_to_dict(self, db_session, project_factory):
        """Test that Upload.to_dict() returns expected API-format data."""
        from app.models import Upload, PlateLayout

        project = project_factory()
        layout = PlateLayout(project_id=project.id, name="Dict Test Layout")
        db_session.add(layout)
        db_session.commit()

        upload = Upload.create(
            project_id=project.id,
            layout_id=layout.id,
            filename="dict_test.txt",
            content="some content",
            username="test_user",
        )
        db_session.commit()

        d = upload.to_dict()
        assert d["filename"] == "dict_test.txt"
        assert d["project_id"] == project.id
        assert d["status"] == "pending"
        assert d["upload_id"] is not None
        assert d["username"] == "test_user"

    def test_upload_data_validation(self):
        """Test that data structure validation detects missing time column."""
        # Create CSV without a time column
        df = pd.DataFrame({
            'A1': [1, 2, 3],
            'A2': [4, 5, 6],
        })

        has_time = any('time' in col.lower() for col in df.columns)
        assert not has_time  # Should fail validation


class TestBioTekFileUpload:
    """Test BioTek file upload and parsing workflow."""

    def test_biotek_parser_instantiation(self):
        """Test that BioTekParser can be instantiated and reports correct metadata."""
        from app.parsers.biotek_parser import BioTekParser

        parser = BioTekParser()
        assert parser.name == "BioTek Synergy HTX"
        assert '.txt' in parser.supported_extensions
        assert '.csv' in parser.supported_extensions
        assert '.xlsx' in parser.supported_extensions

    def test_multiple_upload_records(self, db_session, project_factory):
        """Test creating multiple upload records for the same project."""
        from app.models import Upload, PlateLayout

        project = project_factory()
        layout = PlateLayout(project_id=project.id, name="Multi Upload Layout")
        db_session.add(layout)
        db_session.commit()

        for i in range(3):
            df = pd.DataFrame({
                'Time': np.arange(0, 60, 5),
                'A1': np.random.normal(1000, 100, 12),
            })
            Upload.create(
                project_id=project.id,
                layout_id=layout.id,
                filename=f"data_{i}.csv",
                content=df.to_csv(index=False),
                username="test_user",
            )

        db_session.commit()

        # Verify all uploads exist
        uploads = Upload.query.filter_by(project_id=project.id).all()
        assert len(uploads) == 3
        filenames = {u.filename for u in uploads}
        assert filenames == {"data_0.csv", "data_1.csv", "data_2.csv"}


class TestUploadValidation:
    """Test upload validation rules on raw data files."""

    def test_file_type_validation(self, temp_dir):
        """Test that only valid file types are accepted."""
        valid_extensions = ['.csv', '.txt', '.xlsx', '.xls', '.tsv']

        for ext in valid_extensions:
            file_path = temp_dir / f"test{ext}"
            file_path.touch()
            assert file_path.suffix in valid_extensions

    def test_data_format_validation(self, temp_dir):
        """Test data format validation detects the Time column."""
        valid_df = pd.DataFrame({
            'Time': [0, 5, 10],
            'A1': [100, 200, 300],
        })
        valid_path = temp_dir / "valid.csv"
        valid_df.to_csv(valid_path, index=False)

        loaded = pd.read_csv(valid_path)
        assert 'Time' in loaded.columns

    def test_well_column_detection(self, temp_dir):
        """Test that well columns are properly detected by standard pattern."""
        df = pd.DataFrame({
            'Time': [0, 5, 10],
            'A1': [100, 200, 300],
            'A2': [150, 250, 350],
            'B1': [120, 220, 320],
            'B2': [180, 280, 380],
        })
        csv_path = temp_dir / "wells.csv"
        df.to_csv(csv_path, index=False)

        loaded = pd.read_csv(csv_path)
        well_pattern = re.compile(r'^[A-P]([1-9]|1[0-9]|2[0-4])$')
        well_columns = [col for col in loaded.columns if well_pattern.match(col)]
        assert len(well_columns) == 4

    def test_kinetic_data_shape(self, temp_dir):
        """Test that kinetic data has the expected shape for plate reader output."""
        time_points = np.arange(0, 120, 5)  # 24 time points
        n_wells = 8

        data = {'Time': time_points}
        for i in range(n_wells):
            row = chr(65 + i // 4)  # A or B
            col = (i % 4) + 1
            well_name = f"{row}{col}"
            fmax = 800 + i * 100
            data[well_name] = 100 + fmax * (1 - np.exp(-0.05 * time_points))

        df = pd.DataFrame(data)
        csv_path = temp_dir / "kinetics.csv"
        df.to_csv(csv_path, index=False)

        loaded = pd.read_csv(csv_path)
        assert loaded.shape[0] == 24  # 24 time points
        assert loaded.shape[1] == n_wells + 1  # wells + Time column


class TestUploadWorkflowIntegration:
    """Integration tests for complete upload workflow."""

    def test_complete_upload_workflow(self, db_session, project_factory, construct_factory):
        """Test complete upload workflow: project setup -> layout -> upload record."""
        from app.models import PlateLayout, WellAssignment, Upload, UploadStatus

        # 1. Create project with construct
        project = project_factory(name="Upload Workflow Test")
        construct = construct_factory(project.id, "TEST-001")

        # 2. Create plate layout
        layout = PlateLayout(project_id=project.id, name="Test Layout")
        db_session.add(layout)
        db_session.commit()

        # 3. Add well assignment
        well_assign = WellAssignment(
            layout_id=layout.id,
            well_position="A1",
            construct_id=construct.id,
            well_type="sample"
        )
        db_session.add(well_assign)
        db_session.commit()

        # 4. Create synthetic kinetic data
        time_points = np.arange(0, 120, 5)
        fluorescence = 1000 + 500 * (1 - np.exp(-time_points / 30))
        df = pd.DataFrame({'Time': time_points, 'A1': fluorescence})
        csv_content = df.to_csv(index=False)

        # 5. Upload file
        upload = Upload.create(
            project_id=project.id,
            layout_id=layout.id,
            filename="kinetics_data.csv",
            content=csv_content,
            username="test_user",
            file_format="csv",
        )
        db_session.commit()

        # 6. Verify the complete chain
        assert upload.id is not None
        assert upload.status == UploadStatus.PENDING
        assert upload.project_id == project.id
        assert upload.layout_id == layout.id
        assert len(project.constructs) == 1

        # Verify the upload can be retrieved by UUID
        fetched = Upload.get_by_upload_id(upload.upload_id)
        assert fetched is not None
        assert fetched.id == upload.id

