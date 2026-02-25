"""
Sprint 10: API Middleware Tests

Tests for API security enhancements.

PRD Reference:
- T10.14: Rate limiting enforced
- T10.15: Large payload rejection
"""
import pytest
import time
from unittest.mock import MagicMock, patch
from flask import Flask

from app.api.middleware import (
    RateLimiter,
    PayloadSizeValidator,
    get_rate_limiter,
    get_payload_validator,
)


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    return app


class TestRateLimiter:
    """Tests for rate limiting (T10.14)."""

    def test_basic_rate_limiting(self):
        """Test basic rate limiting functionality."""
        limiter = RateLimiter(requests_per_minute=10)
        client_ip = "192.168.1.1"

        # First 10 requests should be allowed
        for i in range(10):
            allowed, remaining, reset = limiter.is_allowed(client_ip)
            assert allowed, f"Request {i+1} should be allowed"
            assert remaining == 10 - i - 1

        # 11th request should be rejected
        allowed, remaining, reset = limiter.is_allowed(client_ip)
        assert not allowed
        assert remaining == 0

    def test_rate_limit_per_ip(self):
        """Rate limits are per IP address."""
        limiter = RateLimiter(requests_per_minute=5)

        ip1 = "192.168.1.1"
        ip2 = "192.168.1.2"

        # Exhaust limit for IP1
        for _ in range(5):
            limiter.is_allowed(ip1)

        # IP1 should be limited
        allowed1, _, _ = limiter.is_allowed(ip1)
        assert not allowed1

        # IP2 should still be allowed
        allowed2, remaining2, _ = limiter.is_allowed(ip2)
        assert allowed2
        assert remaining2 == 4

    def test_burst_limiting(self):
        """Test burst traffic limiting."""
        limiter = RateLimiter(requests_per_minute=100, burst_size=5)
        client_ip = "192.168.1.1"

        # Make 5 requests in quick succession (within 1 second)
        for _ in range(5):
            allowed, _, _ = limiter.is_allowed(client_ip)
            assert allowed

        # 6th request in same second should be burst-limited
        allowed, _, _ = limiter.is_allowed(client_ip)
        assert not allowed

    def test_rate_limit_window_reset(self):
        """Rate limit should reset after window expires."""
        limiter = RateLimiter(requests_per_minute=5)
        limiter.window_seconds = 1  # 1 second window for testing

        client_ip = "192.168.1.1"

        # Exhaust limit
        for _ in range(5):
            limiter.is_allowed(client_ip)

        # Should be limited
        allowed, _, _ = limiter.is_allowed(client_ip)
        assert not allowed

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        allowed, remaining, _ = limiter.is_allowed(client_ip)
        assert allowed
        assert remaining == 4

    def test_get_stats(self):
        """Test statistics retrieval."""
        limiter = RateLimiter(requests_per_minute=100)
        client_ip = "192.168.1.1"

        # Make some requests
        for _ in range(10):
            limiter.is_allowed(client_ip)

        stats = limiter.get_stats(client_ip)

        assert stats["requests_in_window"] == 10
        assert stats["limit"] == 100
        assert stats["remaining"] == 90


class TestPayloadSizeValidator:
    """Tests for payload size validation (T10.15)."""

    def test_string_length_validation(self):
        """Test string length validation."""
        validator = PayloadSizeValidator(max_string_length=100)

        # Short string is OK
        result = validator.validate_json_payload({"name": "short"})
        assert result is None

        # Long string is rejected
        result = validator.validate_json_payload({"name": "x" * 150})
        assert result is not None
        assert result[1] == 413  # HTTP 413 Payload Too Large

    def test_array_length_validation(self):
        """Test array length validation."""
        validator = PayloadSizeValidator(max_array_length=100)

        # Small array is OK
        result = validator.validate_json_payload({"items": list(range(50))})
        assert result is None

        # Large array is rejected
        result = validator.validate_json_payload({"items": list(range(200))})
        assert result is not None
        assert result[1] == 413

    def test_nested_validation(self):
        """Test nested structure validation."""
        validator = PayloadSizeValidator(max_string_length=50)

        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "long_string": "x" * 100
                    }
                }
            }
        }

        result = validator.validate_json_payload(data)
        assert result is not None
        assert "level1.level2.level3.long_string" in str(result[0])

    def test_array_nested_validation(self):
        """Test validation of strings in arrays."""
        validator = PayloadSizeValidator(max_string_length=50)

        data = {
            "items": [
                {"name": "short"},
                {"name": "x" * 100},  # This should fail
                {"name": "also_short"}
            ]
        }

        result = validator.validate_json_payload(data)
        assert result is not None
        assert "items[1]" in str(result[0])

    def test_content_length_validation(self, app):
        """Test content length validation."""
        validator = PayloadSizeValidator(max_content_length=1024)

        # Test with Flask app context
        with app.test_request_context(content_length=500):
            result = validator.validate_content_length()
            assert result is None

        with app.test_request_context(content_length=2000):
            result = validator.validate_content_length()
            assert result is not None
            assert result[1] == 413

    def test_complex_payload(self):
        """Test complex payload with multiple violations."""
        validator = PayloadSizeValidator(
            max_string_length=50,
            max_array_length=10
        )

        data = {
            "long_name": "x" * 100,  # Too long
            "big_array": list(range(50)),  # Too many
            "nested": {
                "also_long": "y" * 100  # Also too long
            }
        }

        result = validator.validate_json_payload(data)
        assert result is not None

        # Should have multiple violations
        violations = result[0].get("violations", [])
        assert len(violations) >= 2


class TestGlobalInstances:
    """Tests for global singleton instances."""

    def test_get_rate_limiter_singleton(self):
        """Rate limiter should be singleton."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()

        assert limiter1 is limiter2

    def test_get_payload_validator_singleton(self):
        """Payload validator should be singleton."""
        validator1 = get_payload_validator()
        validator2 = get_payload_validator()

        assert validator1 is validator2


class TestDecoratorIntegration:
    """Integration tests for decorators."""

    def test_rate_limit_decorator(self):
        """Test rate_limit decorator applies correctly."""
        from app.api.middleware import rate_limit

        @rate_limit
        def dummy_endpoint():
            return "OK"

        # Function should be wrapped
        assert hasattr(dummy_endpoint, '__wrapped__')

    def test_validate_payload_size_decorator(self):
        """Test validate_payload_size decorator applies correctly."""
        from app.api.middleware import validate_payload_size

        @validate_payload_size
        def dummy_endpoint():
            return "OK"

        # Function should be wrapped
        assert hasattr(dummy_endpoint, '__wrapped__')

    def test_api_protection_decorator(self):
        """Test combined api_protection decorator."""
        from app.api.middleware import api_protection

        @api_protection
        def dummy_endpoint():
            return "OK"

        # Function should be wrapped
        assert hasattr(dummy_endpoint, '__wrapped__')
