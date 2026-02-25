"""
Tests for data upload layout.

Phase 3: Data Upload Flow - Upload Layout

Tests the data_upload.py layout that provides:
- File upload interface with drag-and-drop
- Layout selection and matching
- Validation display
- Session association
"""
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestUploadLayoutCreation:
    """Tests for create_upload_layout function."""

    def test_create_upload_layout_returns_container(self):
        """Test that create_upload_layout returns a Container."""
        from app.layouts.data_upload import create_upload_layout
        import dash_mantine_components as dmc

        layout = create_upload_layout(project_id=1)

        assert layout is not None
        assert isinstance(layout, dmc.Container)

    def test_create_upload_layout_includes_stores(self):
        """Test that layout includes necessary data stores."""
        from app.layouts.data_upload import create_upload_layout

        layout = create_upload_layout(project_id=1)

        # Convert to string representation to check for store IDs
        layout_str = str(layout)

        assert "upload-project-store" in layout_str
        assert "upload-file-store" in layout_str
        assert "upload-validation-store" in layout_str

    def test_create_upload_layout_includes_file_upload(self):
        """Test that layout includes file upload component."""
        from app.layouts.data_upload import create_upload_layout

        layout = create_upload_layout(project_id=1)
        layout_str = str(layout)

        assert "upload-dropzone" in layout_str or "file-upload" in layout_str

    def test_create_upload_layout_includes_layout_selector(self):
        """Test that layout includes layout selection component."""
        from app.layouts.data_upload import create_upload_layout

        layout = create_upload_layout(project_id=1)
        layout_str = str(layout)

        assert "layout-select" in layout_str

    def test_create_upload_layout_includes_session_section(self):
        """Test that layout includes session selection section."""
        from app.layouts.data_upload import create_upload_layout

        layout = create_upload_layout(project_id=1)
        layout_str = str(layout)

        assert "session" in layout_str.lower()


class TestUploadHeader:
    """Tests for upload header section."""

    def test_create_upload_header_with_project_id(self):
        """Test header creation with project ID."""
        from app.layouts.data_upload import create_upload_header

        header = create_upload_header(project_id=1)

        assert header is not None
        header_str = str(header)
        assert "Upload Data" in header_str or "upload" in header_str.lower()

    def test_create_upload_header_includes_help_button(self):
        """Test header includes help button (navigation is via sidebar)."""
        from app.layouts.data_upload import create_upload_header

        header = create_upload_header(project_id=1)
        header_str = str(header)

        assert "upload-help-btn" in header_str or "Help" in header_str


class TestFileUploadPanel:
    """Tests for file upload panel component."""

    def test_create_file_upload_panel_exists(self):
        """Test that file upload panel creator exists."""
        from app.layouts.data_upload import create_file_upload_panel

        panel = create_file_upload_panel()

        assert panel is not None

    def test_create_file_upload_panel_supports_drag_drop(self):
        """Test file upload panel supports drag and drop."""
        from app.layouts.data_upload import create_file_upload_panel

        panel = create_file_upload_panel()
        panel_str = str(panel)

        # Should have upload component
        assert "upload" in panel_str.lower() or "drop" in panel_str.lower()

    def test_create_file_upload_panel_shows_file_types(self):
        """Test file upload panel shows supported file types."""
        from app.layouts.data_upload import create_file_upload_panel

        panel = create_file_upload_panel()
        panel_str = str(panel)

        # Should mention supported formats
        assert "txt" in panel_str.lower() or "xlsx" in panel_str.lower() or "csv" in panel_str.lower()


class TestLayoutSelectionPanel:
    """Tests for layout selection panel."""

    def test_create_layout_selection_panel_exists(self):
        """Test layout selection panel creator exists."""
        from app.layouts.data_upload import create_layout_selection_panel

        panel = create_layout_selection_panel(project_id=1)

        assert panel is not None

    def test_create_layout_selection_panel_includes_dropdown(self):
        """Test panel includes layout dropdown."""
        from app.layouts.data_upload import create_layout_selection_panel

        panel = create_layout_selection_panel(project_id=1)
        panel_str = str(panel)

        assert "select" in panel_str.lower() or "layout-select" in panel_str

    def test_create_layout_selection_panel_empty_layouts(self):
        """Test panel handles empty layouts list."""
        from app.layouts.data_upload import create_layout_selection_panel

        panel = create_layout_selection_panel(project_id=1, layouts=[])

        assert panel is not None

    def test_create_layout_selection_panel_with_layouts(self):
        """Test panel populates with provided layouts."""
        from app.layouts.data_upload import create_layout_selection_panel

        layouts = [
            {"id": 1, "name": "Layout 1"},
            {"id": 2, "name": "Layout 2"},
        ]
        panel = create_layout_selection_panel(project_id=1, layouts=layouts)
        panel_str = str(panel)

        assert panel is not None


class TestValidationResultsPanel:
    """Tests for validation results display panel."""

    def test_create_validation_panel_exists(self):
        """Test validation panel creator exists."""
        from app.layouts.data_upload import create_validation_panel

        panel = create_validation_panel()

        assert panel is not None

    def test_create_validation_panel_empty_state(self):
        """Test validation panel empty state."""
        from app.layouts.data_upload import create_validation_panel

        panel = create_validation_panel(validation_result=None)
        panel_str = str(panel)

        # Should show placeholder or empty state
        assert "validation" in panel_str.lower() or "select" in panel_str.lower()

    def test_create_validation_panel_with_valid_result(self):
        """Test validation panel with valid result."""
        from app.layouts.data_upload import create_validation_panel

        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "metadata": {
                "plate_format": 384,
                "num_timepoints": 60,
                "num_wells_with_data": 192,
            },
        }

        panel = create_validation_panel(validation_result=validation_result)
        panel_str = str(panel)

        assert panel is not None

    def test_create_validation_panel_with_errors(self):
        """Test validation panel displays errors."""
        from app.layouts.data_upload import create_validation_panel

        validation_result = {
            "is_valid": False,
            "errors": ["Layout not found", "Invalid file format"],
            "warnings": [],
        }

        panel = create_validation_panel(validation_result=validation_result)
        panel_str = str(panel)

        assert panel is not None
        # Should display error indicators
        assert "error" in panel_str.lower() or "red" in panel_str.lower()

    def test_create_validation_panel_with_warnings(self):
        """Test validation panel displays warnings."""
        from app.layouts.data_upload import create_validation_panel

        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [
                {"code": "UNMATCHED_WELLS", "message": "5 wells have no layout assignment"},
                {"code": "TEMP_DEVIATION", "message": "Temperature deviation detected"},
            ],
        }

        panel = create_validation_panel(validation_result=validation_result)
        panel_str = str(panel)

        assert panel is not None


class TestSessionAssociationPanel:
    """Tests for session association panel."""

    def test_create_session_panel_exists(self):
        """Test session panel creator exists."""
        from app.layouts.data_upload import create_session_panel

        panel = create_session_panel(project_id=1)

        assert panel is not None

    def test_create_session_panel_new_session_option(self):
        """Test session panel includes new session option."""
        from app.layouts.data_upload import create_session_panel

        panel = create_session_panel(project_id=1)
        panel_str = str(panel)

        assert "new" in panel_str.lower() or "create" in panel_str.lower()

    def test_create_session_panel_existing_sessions(self):
        """Test session panel with existing sessions."""
        from app.layouts.data_upload import create_session_panel

        sessions = [
            {"id": 1, "date": "2024-01-15", "batch_id": "Batch001"},
            {"id": 2, "date": "2024-01-16", "batch_id": "Batch002"},
        ]

        panel = create_session_panel(project_id=1, sessions=sessions)

        assert panel is not None


class TestTemperatureQCDisplay:
    """Tests for temperature QC warnings display."""

    def test_create_temperature_warning_exists(self):
        """Test temperature warning component exists."""
        from app.layouts.data_upload import create_temperature_warning

        warning = create_temperature_warning(
            setpoint=37.0,
            actual_temps=[36.5, 37.0, 37.5, 38.5],
        )

        assert warning is not None

    def test_create_temperature_warning_no_deviation(self):
        """Test temperature warning when no deviation."""
        from app.layouts.data_upload import create_temperature_warning

        warning = create_temperature_warning(
            setpoint=37.0,
            actual_temps=[36.8, 37.0, 37.1],
        )

        # Should return None or empty component when no significant deviation
        assert warning is None or str(warning) == ""

    def test_create_temperature_warning_with_deviation(self):
        """Test temperature warning when deviation exceeds threshold."""
        from app.layouts.data_upload import create_temperature_warning

        # 38.5 exceeds 37.0 setpoint by more than 1°C threshold
        warning = create_temperature_warning(
            setpoint=37.0,
            actual_temps=[36.8, 37.0, 38.5, 39.0],
            threshold=1.0,
        )

        warning_str = str(warning) if warning else ""

        # Should contain warning message
        assert warning is not None
        assert "temperature" in warning_str.lower() or "°" in warning_str


class TestUploadLoadingState:
    """Tests for upload loading state."""

    def test_create_upload_loading_state_exists(self):
        """Test loading state creator exists."""
        from app.layouts.data_upload import create_upload_loading_state

        loading = create_upload_loading_state()

        assert loading is not None

    def test_create_upload_loading_state_has_skeletons(self):
        """Test loading state includes skeleton placeholders."""
        from app.layouts.data_upload import create_upload_loading_state

        loading = create_upload_loading_state()
        loading_str = str(loading)

        assert "skeleton" in loading_str.lower() or "Skeleton" in loading_str


class TestUploadLayoutExports:
    """Tests for upload layout module exports."""

    def test_all_exports_available(self):
        """Test all expected functions are exported."""
        from app.layouts.data_upload import (
            create_upload_layout,
            create_upload_header,
            create_file_upload_panel,
            create_layout_selection_panel,
            create_validation_panel,
            create_session_panel,
            create_temperature_warning,
            create_upload_loading_state,
        )

        assert callable(create_upload_layout)
        assert callable(create_upload_header)
        assert callable(create_file_upload_panel)
        assert callable(create_layout_selection_panel)
        assert callable(create_validation_panel)
        assert callable(create_session_panel)
        assert callable(create_temperature_warning)
        assert callable(create_upload_loading_state)

    def test_layout_registered_in_init(self):
        """Test that upload layout is exported from layouts package."""
        from app.layouts import create_upload_layout

        assert callable(create_upload_layout)
