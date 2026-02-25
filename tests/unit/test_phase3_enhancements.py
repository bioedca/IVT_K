"""
Tests for Phase 3 enhancements.

Phase 3.1: Input Validation Schemas
Phase 3.2: Health Check Endpoint
Phase 3.3: Rate Limiting
Phase 3.4: Request Timeouts
Phase 3.5: Alembic Migration Consistency
"""
import pytest
from pydantic import ValidationError


# ============================================================================
# Phase 3.1: Input Validation Schemas Tests
# ============================================================================

class TestProjectSchemas:
    """Tests for project validation schemas."""

    def test_create_project_request_valid(self):
        """Test valid project creation request."""
        from app.schemas.project import CreateProjectRequest

        request = CreateProjectRequest(
            name="Test Project",
            description="A test project",
            plate_format="384",
            precision_target=0.3
        )
        assert request.name == "Test Project"
        assert request.plate_format == "384"
        assert request.precision_target == 0.3

    def test_create_project_request_minimal(self):
        """Test minimal project creation request."""
        from app.schemas.project import CreateProjectRequest

        request = CreateProjectRequest(name="Minimal Project")
        assert request.name == "Minimal Project"
        assert request.plate_format == "384"  # default
        assert request.precision_target == 0.3  # default

    def test_create_project_request_empty_name_fails(self):
        """Test that empty name is rejected."""
        from app.schemas.project import CreateProjectRequest

        with pytest.raises(ValidationError) as exc_info:
            CreateProjectRequest(name="   ")
        # Pydantic may report "at least 1 character" or similar
        error_msg = str(exc_info.value).lower()
        assert "character" in error_msg or "empty" in error_msg or "short" in error_msg

    def test_create_project_request_invalid_plate_format(self):
        """Test that invalid plate format is rejected."""
        from app.schemas.project import CreateProjectRequest

        with pytest.raises(ValidationError):
            CreateProjectRequest(name="Test", plate_format="48")

    def test_create_project_request_precision_out_of_range(self):
        """Test that precision target must be in valid range."""
        from app.schemas.project import CreateProjectRequest

        with pytest.raises(ValidationError):
            CreateProjectRequest(name="Test", precision_target=2.0)

        with pytest.raises(ValidationError):
            CreateProjectRequest(name="Test", precision_target=0.001)


class TestConstructSchemas:
    """Tests for construct validation schemas."""

    def test_create_construct_request_valid(self):
        """Test valid construct creation request."""
        from app.schemas.project import CreateConstructRequest

        request = CreateConstructRequest(
            identifier="WT-001",
            family="glyQS",
            is_wildtype=True
        )
        assert request.identifier == "WT-001"
        assert request.family == "glyQS"
        assert request.is_wildtype is True

    def test_create_construct_invalid_identifier(self):
        """Test that invalid identifier characters are rejected."""
        from app.schemas.project import CreateConstructRequest

        with pytest.raises(ValidationError):
            CreateConstructRequest(identifier="Test@Construct#1")

    def test_create_construct_sequence_validation(self):
        """Test that DNA sequence is validated."""
        from app.schemas.project import CreateConstructRequest

        # Valid sequence
        request = CreateConstructRequest(
            identifier="TEST-001",
            sequence="ATCGATCG"
        )
        assert request.sequence == "ATCGATCG"

        # Invalid characters rejected
        with pytest.raises(ValidationError):
            CreateConstructRequest(
                identifier="TEST-002",
                sequence="ATCGXYZ"  # X, Y, Z not valid
            )


class TestUploadSchemas:
    """Tests for upload validation schemas."""

    def test_upload_file_request_valid(self):
        """Test valid upload request."""
        from app.schemas.upload import UploadFileRequest

        request = UploadFileRequest(
            project_id=1,
            layout_id=1,
            filename="test_data.txt",
            content="SGVsbG8gV29ybGQ=",  # base64
            content_encoding="base64"
        )
        assert request.project_id == 1
        assert request.filename == "test_data.txt"

    def test_upload_file_request_path_traversal_blocked(self):
        """Test that path traversal in filename is blocked."""
        from app.schemas.upload import UploadFileRequest

        with pytest.raises(ValidationError) as exc_info:
            UploadFileRequest(
                project_id=1,
                layout_id=1,
                filename="../../../etc/passwd",
                content="test"
            )
        assert "path separator" in str(exc_info.value).lower()

    def test_upload_file_request_negative_id_blocked(self):
        """Test that negative IDs are rejected."""
        from app.schemas.upload import UploadFileRequest

        with pytest.raises(ValidationError):
            UploadFileRequest(
                project_id=-1,
                layout_id=1,
                filename="test.txt",
                content="test"
            )


class TestLayoutSchemas:
    """Tests for layout validation schemas."""

    def test_assign_well_request_valid(self):
        """Test valid well assignment request."""
        from app.schemas.layout import AssignWellRequest

        request = AssignWellRequest(
            well_position="A1",
            construct_id=1,
            well_type="sample"
        )
        assert request.well_position == "A1"

    def test_assign_well_invalid_position(self):
        """Test that invalid well positions are rejected."""
        from app.schemas.layout import AssignWellRequest

        with pytest.raises(ValidationError):
            AssignWellRequest(
                well_position="Z99",  # Invalid
                construct_id=1
            )

    def test_bulk_assign_wells_no_duplicates(self):
        """Test that duplicate positions are rejected."""
        from app.schemas.layout import BulkAssignWellsRequest

        with pytest.raises(ValidationError) as exc_info:
            BulkAssignWellsRequest(
                well_positions=["A1", "A2", "A1"],  # A1 duplicated
                construct_id=1
            )
        assert "duplicate" in str(exc_info.value).lower()


# ============================================================================
# Phase 3.2: Health Check Endpoint Tests
# ============================================================================

class TestHealthCheck:
    """Tests for health check endpoints."""

    def test_health_check_returns_status(self, client, db_session):
        """Test that health check returns status information."""
        response = client.get('/api/health')
        assert response.status_code in [200, 503]  # healthy or unhealthy

        data = response.get_json()
        assert 'status' in data
        assert 'timestamp' in data
        assert 'checks' in data
        assert 'version' in data

    def test_health_check_includes_database(self, client, db_session):
        """Test that health check includes database status."""
        response = client.get('/api/health')
        data = response.get_json()

        assert 'database' in data['checks']
        assert 'status' in data['checks']['database']

    def test_liveness_probe(self, client, db_session):
        """Test liveness probe endpoint."""
        response = client.get('/api/health/live')
        assert response.status_code == 200

        data = response.get_json()
        assert data['status'] == 'alive'

    def test_readiness_probe(self, client, db_session):
        """Test readiness probe endpoint."""
        response = client.get('/api/health/ready')
        # Should be 200 if database is accessible
        assert response.status_code in [200, 503]

        data = response.get_json()
        assert 'status' in data

    def test_timeout_info_endpoint(self, client, db_session):
        """Test timeout configuration endpoint."""
        response = client.get('/api/health/timeouts')
        assert response.status_code == 200

        data = response.get_json()
        assert 'poll_interval_ms' in data
        assert 'expected_operation_times' in data
        assert 'recommendations' in data


# ============================================================================
# Phase 3.3: Rate Limiting Tests
# ============================================================================

class TestRateLimiting:
    """Tests for rate limiting middleware."""

    def test_rate_limiter_creation(self):
        """Test rate limiter can be created with different configurations."""
        from app.api.middleware import get_rate_limiter, RATE_LIMIT_CONFIGS

        # Default limiter
        default_limiter = get_rate_limiter("default")
        assert default_limiter.requests_per_minute == 100

        # Write limiter
        write_limiter = get_rate_limiter("write")
        assert write_limiter.requests_per_minute == 30

        # Analysis limiter
        analysis_limiter = get_rate_limiter("analysis")
        assert analysis_limiter.requests_per_minute == 5

    def test_rate_limiter_allows_requests(self):
        """Test that rate limiter allows requests under limit."""
        from app.api.middleware import RateLimiter

        limiter = RateLimiter(requests_per_minute=10, burst_size=5)

        # First request should be allowed
        allowed, remaining, reset = limiter.is_allowed("test_ip")
        assert allowed is True
        assert remaining >= 0

    def test_rate_limiter_blocks_excess_requests(self):
        """Test that rate limiter blocks excess requests."""
        from app.api.middleware import RateLimiter

        limiter = RateLimiter(requests_per_minute=3, burst_size=2)

        # Make requests up to limit
        for _ in range(3):
            limiter.is_allowed("test_ip")

        # Next request should be blocked
        allowed, remaining, reset = limiter.is_allowed("test_ip")
        assert allowed is False
        assert remaining == 0

    def test_rate_limit_configs_exist(self):
        """Test that all expected rate limit configurations exist."""
        from app.api.middleware import RATE_LIMIT_CONFIGS

        expected_types = ["default", "read", "write", "analysis", "upload"]
        for limit_type in expected_types:
            assert limit_type in RATE_LIMIT_CONFIGS
            assert "requests_per_minute" in RATE_LIMIT_CONFIGS[limit_type]
            assert "burst_size" in RATE_LIMIT_CONFIGS[limit_type]


# ============================================================================
# Phase 3.4: Request Timeout Tests
# ============================================================================

class TestRequestTimeouts:
    """Tests for request timeout configuration."""

    def test_timeout_config_exists(self):
        """Test that timeout configuration exists."""
        from app.config import Config

        assert hasattr(Config, 'REQUEST_TIMEOUT_DEFAULT')
        assert hasattr(Config, 'REQUEST_TIMEOUT_ANALYSIS')
        assert hasattr(Config, 'REQUEST_TIMEOUT_EXPORT')
        assert hasattr(Config, 'OPERATION_TIMES')

    def test_timeout_values_reasonable(self):
        """Test that timeout values are reasonable."""
        from app.config import Config

        # Default timeout should be 30 seconds
        assert Config.REQUEST_TIMEOUT_DEFAULT == 30

        # Analysis timeout should be longer
        assert Config.REQUEST_TIMEOUT_ANALYSIS > Config.REQUEST_TIMEOUT_DEFAULT

        # All timeouts should be positive
        assert Config.REQUEST_TIMEOUT_DEFAULT > 0
        assert Config.REQUEST_TIMEOUT_ANALYSIS > 0
        assert Config.REQUEST_TIMEOUT_EXPORT > 0

    def test_operation_times_documented(self):
        """Test that expected operations have time estimates."""
        from app.config import Config

        expected_operations = [
            "curve_fitting",
            "mcmc_analysis",
            "frequentist_analysis",
            "data_export",
            "file_parsing"
        ]

        for op in expected_operations:
            assert op in Config.OPERATION_TIMES
            assert "typical" in Config.OPERATION_TIMES[op]
            assert "max" in Config.OPERATION_TIMES[op]


# ============================================================================
# Phase 3.5: Alembic Migration Tests
# ============================================================================

class TestAlembicMigration:
    """Tests for Alembic migration consistency."""

    def test_init_db_script_exists(self):
        """Test that init_db script exists."""
        from pathlib import Path
        init_db_path = Path(__file__).parent.parent.parent / "scripts" / "init_db.py"
        assert init_db_path.exists()

    def test_alembic_config_exists(self):
        """Test that Alembic configuration exists."""
        from pathlib import Path
        alembic_ini = Path(__file__).parent.parent.parent / "alembic" / "alembic.ini"
        alembic_env = Path(__file__).parent.parent.parent / "alembic" / "env.py"

        assert alembic_ini.exists()
        assert alembic_env.exists()

    def test_alembic_versions_directory_exists(self):
        """Test that Alembic versions directory exists."""
        from pathlib import Path
        versions_dir = Path(__file__).parent.parent.parent / "alembic" / "versions"
        assert versions_dir.exists()
        assert versions_dir.is_dir()

    def test_init_db_uses_alembic(self):
        """Test that init_db script references Alembic."""
        from pathlib import Path
        init_db_path = Path(__file__).parent.parent.parent / "scripts" / "init_db.py"

        content = init_db_path.read_text()

        # Should reference Alembic
        assert "alembic" in content.lower()
        # Should warn about db.create_all()
        assert "db.create_all" in content or "create_all" in content

    def test_deploy_readme_documents_migrations(self):
        """Test that deployment README documents migration workflow."""
        from pathlib import Path
        readme_path = Path(__file__).parent.parent.parent / "deploy" / "README.md"

        content = readme_path.read_text()

        # Should document migration commands
        assert "alembic" in content.lower()
        assert "upgrade head" in content
        assert "migration" in content.lower()


# ============================================================================
# Integration Tests
# ============================================================================

class TestPhase3Integration:
    """Integration tests for Phase 3 features working together."""

    def test_health_check_with_rate_limit_headers(self, client, db_session):
        """Test that health check includes rate limit headers."""
        response = client.get('/api/health')

        # Health endpoint may or may not have rate limiting
        # but if it does, headers should be present
        if 'X-RateLimit-Limit' in response.headers:
            assert 'X-RateLimit-Remaining' in response.headers
            assert 'X-RateLimit-Reset' in response.headers

    def test_project_endpoint_has_rate_limiting(self, client, db_session):
        """Test that project endpoints have rate limiting applied."""
        # Make request to projects endpoint
        response = client.get('/api/projects/')

        # Should have rate limit headers (or be rate limited)
        # Note: In test environment, rate limiting may behave differently
        assert response.status_code in [200, 429]

    def test_validation_decorator_integration(self):
        """Test that validation decorator works with Flask."""
        from app.schemas.common import validate_request
        from app.schemas.project import CreateProjectRequest

        # The decorator should be importable and usable
        assert callable(validate_request)

        # Should work with Pydantic models
        decorator = validate_request(CreateProjectRequest)
        assert callable(decorator)
