"""
API Middleware for IVT Kinetics Analyzer.

Sprint 10: Edge Cases & Polish
Phase 1 Security: Authentication tracking and username sanitization

Provides:
- T10.14: Rate limiting
- T10.15: Large payload rejection
- Phase 1: User identity extraction and sanitization
"""
import re
import time
from collections import defaultdict
from functools import wraps
from typing import Dict, Optional, Callable
from flask import current_app, request, jsonify, g
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Phase 1 Security: User Identity Tracking
# =============================================================================

# Maximum username length
MAX_USERNAME_LENGTH = 64

# Pattern for valid username characters (alphanumeric, underscore, hyphen, dot)
USERNAME_PATTERN = re.compile(r'^[\w\-\.]+$')


def sanitize_username(username: Optional[str]) -> str:
    """
    Sanitize username to prevent log injection and other attacks.

    Phase 1 Security Fix: Ensures usernames are safe for logging and storage.

    Args:
        username: Raw username from header

    Returns:
        Sanitized username, or 'anonymous' if invalid/empty
    """
    if not username:
        return 'anonymous'

    # Strip whitespace
    username = username.strip()

    if not username:
        return 'anonymous'

    # Remove any control characters and newlines (prevent log injection)
    username = ''.join(c for c in username if c.isprintable() and c not in '\r\n\t')

    # Only allow safe characters (alphanumeric, underscore, hyphen, dot)
    # Replace invalid characters with underscore
    sanitized = re.sub(r'[^\w\-\.]', '_', username)

    # Collapse multiple consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)

    # Strip leading/trailing underscores
    sanitized = sanitized.strip('_')

    # Limit length
    if len(sanitized) > MAX_USERNAME_LENGTH:
        sanitized = sanitized[:MAX_USERNAME_LENGTH]

    # If nothing left after sanitization, return anonymous
    if not sanitized:
        return 'anonymous'

    return sanitized


def extract_user_identity():
    """
    Extract and validate user identity from request.

    Phase 1 Security Fix: Centralizes user identity extraction with sanitization.
    Sets g.username and g.client_ip for use in request handlers.

    Should be called via before_request hook.
    """
    # Extract and sanitize username
    raw_username = request.headers.get('X-Username', 'anonymous')
    g.username = sanitize_username(raw_username)

    # Log if username was sanitized differently
    if raw_username and raw_username != 'anonymous' and g.username != raw_username:
        logger.warning(
            "Username sanitized",
            extra={
                "original": repr(raw_username)[:100],  # Limit logged length
                "sanitized": g.username,
                "client_ip": request.remote_addr
            }
        )

    # Extract client IP (handles proxies via X-Forwarded-For if present)
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        # Take the first IP in the chain (original client)
        g.client_ip = forwarded_for.split(',')[0].strip()
    else:
        g.client_ip = request.remote_addr or 'unknown'

    # Extract user agent for additional audit context
    g.user_agent = request.headers.get('User-Agent', 'unknown')[:500]  # Limit length


def register_user_identity_middleware(app):
    """
    Register user identity extraction as a before_request handler.

    Phase 1 Security Fix: Ensures all requests have sanitized user identity.

    Args:
        app: Flask application
    """
    @app.before_request
    def before_request_extract_identity():
        extract_user_identity()

    logger.info("User identity middleware registered")


class RateLimiter:
    """
    Simple in-memory rate limiter.

    T10.14: Rate limiting enforced (100 requests/min)

    Uses a sliding window approach to track requests per IP.
    """

    def __init__(
        self,
        requests_per_minute: int = 100,
        burst_size: int = 20
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests allowed per minute
            burst_size: Maximum burst requests in short window
        """
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.window_seconds = 60

        # Track requests: IP -> list of timestamps
        self._requests: Dict[str, list] = defaultdict(list)

        # Burst tracking: IP -> (timestamp, count)
        self._burst: Dict[str, tuple] = {}
        self._burst_window = 1  # 1 second burst window

    def is_allowed(self, client_ip: str) -> tuple:
        """
        Check if request is allowed under rate limit.

        Args:
            client_ip: Client IP address

        Returns:
            (allowed: bool, remaining: int, reset_seconds: int)
        """
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old requests
        self._requests[client_ip] = [
            ts for ts in self._requests[client_ip]
            if ts > window_start
        ]

        request_count = len(self._requests[client_ip])
        remaining = max(0, self.requests_per_minute - request_count)
        reset_seconds = int(self.window_seconds - (now - window_start))

        # Check burst limit
        burst_info = self._burst.get(client_ip, (0, 0))
        if now - burst_info[0] < self._burst_window:
            burst_count = burst_info[1]
        else:
            burst_count = 0

        if burst_count >= self.burst_size:
            logger.warning(f"Burst limit exceeded for {client_ip}")
            return False, 0, 1

        if request_count >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for {client_ip}: {request_count}/{self.requests_per_minute}")
            return False, 0, reset_seconds

        # Record this request
        self._requests[client_ip].append(now)

        # Update burst tracking
        if now - burst_info[0] < self._burst_window:
            self._burst[client_ip] = (burst_info[0], burst_count + 1)
        else:
            self._burst[client_ip] = (now, 1)

        return True, remaining - 1, reset_seconds

    def get_stats(self, client_ip: str) -> Dict:
        """Get rate limit statistics for a client."""
        now = time.time()
        window_start = now - self.window_seconds

        requests = [ts for ts in self._requests.get(client_ip, []) if ts > window_start]

        return {
            "requests_in_window": len(requests),
            "limit": self.requests_per_minute,
            "remaining": max(0, self.requests_per_minute - len(requests)),
            "window_seconds": self.window_seconds
        }


# Global rate limiter instances for different endpoint types
_rate_limiters: Dict[str, RateLimiter] = {}

# Rate limit configurations (Phase 3.3)
RATE_LIMIT_CONFIGS = {
    "default": {"requests_per_minute": 100, "burst_size": 20},
    "read": {"requests_per_minute": 100, "burst_size": 20},       # Read operations
    "write": {"requests_per_minute": 30, "burst_size": 10},       # Write operations
    "analysis": {"requests_per_minute": 5, "burst_size": 2},      # Analysis triggers (expensive)
    "upload": {"requests_per_minute": 20, "burst_size": 5},       # File uploads
}


def get_rate_limiter(limiter_type: str = "default") -> RateLimiter:
    """
    Get or create a rate limiter for the specified type.

    Phase 3.3: Configurable rate limits for different endpoint types.

    Args:
        limiter_type: Type of rate limiter (default, read, write, analysis, upload)

    Returns:
        Configured RateLimiter instance
    """
    global _rate_limiters
    if limiter_type not in _rate_limiters:
        config = RATE_LIMIT_CONFIGS.get(limiter_type, RATE_LIMIT_CONFIGS["default"])
        _rate_limiters[limiter_type] = RateLimiter(**config)
    return _rate_limiters[limiter_type]


def rate_limit(f: Callable = None, *, limiter_type: str = "default") -> Callable:
    """
    Decorator to apply rate limiting to an endpoint.

    T10.14: Rate limiting enforced
    Phase 3.3: Configurable rate limits by endpoint type

    Can be used with or without arguments:
        @rate_limit                         # Default limit (100/min)
        @rate_limit(limiter_type="write")   # Write limit (30/min)
        @rate_limit(limiter_type="analysis") # Analysis limit (5/min)

    Returns HTTP 429 if rate limit exceeded.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def decorated_function(*args, **kwargs):
            # Skip rate limiting when disabled (e.g., in tests)
            if not current_app.config.get("RATELIMIT_ENABLED", True):
                return func(*args, **kwargs)

            limiter = get_rate_limiter(limiter_type)
            client_ip = request.remote_addr or "unknown"

            allowed, remaining, reset_seconds = limiter.is_allowed(client_ip)

            # Add rate limit headers
            g.rate_limit_remaining = remaining
            g.rate_limit_reset = reset_seconds
            g.rate_limit_type = limiter_type

            if not allowed:
                response = jsonify({
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Try again in {reset_seconds} seconds.",
                    "retry_after": reset_seconds,
                    "limit_type": limiter_type
                })
                response.status_code = 429
                response.headers['Retry-After'] = str(reset_seconds)
                response.headers['X-RateLimit-Limit'] = str(limiter.requests_per_minute)
                response.headers['X-RateLimit-Remaining'] = '0'
                response.headers['X-RateLimit-Reset'] = str(int(time.time()) + reset_seconds)
                return response

            return func(*args, **kwargs)

        return decorated_function

    # Support both @rate_limit and @rate_limit(limiter_type="...")
    if f is not None:
        return decorator(f)
    return decorator


class PayloadSizeValidator:
    """
    Validate payload sizes for API requests.

    T10.15: Large payload rejection (>10MB)
    """

    # Default limits
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
    MAX_STRING_LENGTH = 100000  # 100K characters
    MAX_ARRAY_LENGTH = 10000  # 10K items

    def __init__(
        self,
        max_content_length: int = MAX_CONTENT_LENGTH,
        max_string_length: int = MAX_STRING_LENGTH,
        max_array_length: int = MAX_ARRAY_LENGTH
    ):
        """
        Initialize payload validator.

        Args:
            max_content_length: Maximum request body size in bytes
            max_string_length: Maximum string field length
            max_array_length: Maximum array/list length
        """
        self.max_content_length = max_content_length
        self.max_string_length = max_string_length
        self.max_array_length = max_array_length

    def validate_content_length(self) -> Optional[tuple]:
        """
        Validate request content length.

        Returns:
            None if valid, (error_dict, status_code) if invalid
        """
        content_length = request.content_length

        if content_length is not None and content_length > self.max_content_length:
            size_mb = content_length / (1024 * 1024)
            max_mb = self.max_content_length / (1024 * 1024)
            return {
                "error": "Payload too large",
                "message": f"Request body ({size_mb:.1f} MB) exceeds maximum allowed size ({max_mb:.0f} MB).",
                "max_size_bytes": self.max_content_length
            }, 413

        return None

    def validate_json_payload(self, data: dict) -> Optional[tuple]:
        """
        Validate JSON payload structure and sizes.

        Args:
            data: Parsed JSON data

        Returns:
            None if valid, (error_dict, status_code) if invalid
        """
        violations = []
        self._check_value(data, "", violations)

        if violations:
            return {
                "error": "Payload validation failed",
                "message": "Request contains fields that exceed size limits.",
                "violations": violations[:5]  # Limit to first 5
            }, 413

        return None

    def _check_value(self, value, path: str, violations: list) -> None:
        """Recursively check values for size violations."""
        if isinstance(value, str):
            if len(value) > self.max_string_length:
                violations.append({
                    "path": path,
                    "type": "string_too_long",
                    "length": len(value),
                    "max_length": self.max_string_length
                })

        elif isinstance(value, (list, tuple)):
            if len(value) > self.max_array_length:
                violations.append({
                    "path": path,
                    "type": "array_too_long",
                    "length": len(value),
                    "max_length": self.max_array_length
                })
            else:
                for i, item in enumerate(value):
                    self._check_value(item, f"{path}[{i}]", violations)

        elif isinstance(value, dict):
            for key, val in value.items():
                self._check_value(val, f"{path}.{key}" if path else key, violations)


# Global payload validator instance
_payload_validator: Optional[PayloadSizeValidator] = None


def get_payload_validator() -> PayloadSizeValidator:
    """Get or create the global payload validator."""
    global _payload_validator
    if _payload_validator is None:
        _payload_validator = PayloadSizeValidator()
    return _payload_validator


def validate_payload_size(f: Callable) -> Callable:
    """
    Decorator to validate payload size.

    T10.15: Large payload rejection

    Returns HTTP 413 if payload too large.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        validator = get_payload_validator()

        # Check content length
        error = validator.validate_content_length()
        if error:
            response = jsonify(error[0])
            response.status_code = error[1]
            return response

        # Check JSON payload if present
        if request.is_json and request.content_length and request.content_length > 0:
            try:
                data = request.get_json(silent=True)
                if data:
                    error = validator.validate_json_payload(data)
                    if error:
                        response = jsonify(error[0])
                        response.status_code = error[1]
                        return response
            except Exception:
                pass  # Let the endpoint handle malformed JSON

        return f(*args, **kwargs)

    return decorated_function


def api_protection(f: Callable = None, *, limiter_type: str = "default") -> Callable:
    """
    Combined decorator for API protection.

    Phase 3.3: Applies both rate limiting and payload validation.

    Can be used with or without arguments:
        @api_protection                         # Default limit
        @api_protection(limiter_type="write")   # Write limit
        @api_protection(limiter_type="analysis") # Analysis limit

    Rate limit types:
        - "default"/"read": 100 requests/minute (read operations)
        - "write": 30 requests/minute (create/update operations)
        - "analysis": 5 requests/minute (expensive MCMC analysis)
        - "upload": 20 requests/minute (file uploads)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def decorated_function(*args, **kwargs):
            # Skip rate limiting when disabled (e.g., in tests)
            rate_limit_enabled = current_app.config.get("RATELIMIT_ENABLED", True)

            if rate_limit_enabled:
                # Apply rate limiting
                limiter = get_rate_limiter(limiter_type)
                client_ip = request.remote_addr or "unknown"

                allowed, remaining, reset_seconds = limiter.is_allowed(client_ip)
                g.rate_limit_remaining = remaining
                g.rate_limit_reset = reset_seconds
                g.rate_limit_type = limiter_type

                if not allowed:
                    response = jsonify({
                        "error": "Rate limit exceeded",
                        "message": f"Too many requests. Try again in {reset_seconds} seconds.",
                        "retry_after": reset_seconds,
                        "limit_type": limiter_type
                    })
                    response.status_code = 429
                    response.headers['Retry-After'] = str(reset_seconds)
                    response.headers['X-RateLimit-Limit'] = str(limiter.requests_per_minute)
                    response.headers['X-RateLimit-Remaining'] = '0'
                    response.headers['X-RateLimit-Reset'] = str(int(time.time()) + reset_seconds)
                    return response

            # Apply payload size validation
            validator = get_payload_validator()
            error = validator.validate_content_length()
            if error:
                response = jsonify(error[0])
                response.status_code = error[1]
                return response

            if request.is_json and request.content_length and request.content_length > 0:
                try:
                    data = request.get_json(silent=True)
                    if data:
                        error = validator.validate_json_payload(data)
                        if error:
                            response = jsonify(error[0])
                            response.status_code = error[1]
                            return response
                except Exception:
                    pass

            return func(*args, **kwargs)

        return decorated_function

    # Support both @api_protection and @api_protection(limiter_type="...")
    if f is not None:
        return decorator(f)
    return decorator


def configure_app_limits(app, max_content_length: int = 10 * 1024 * 1024):
    """
    Configure Flask app with request size limits.

    Args:
        app: Flask application
        max_content_length: Maximum content length in bytes
    """
    app.config['MAX_CONTENT_LENGTH'] = max_content_length

    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify({
            "error": "Payload too large",
            "message": "Request body exceeds maximum allowed size.",
            "max_size_bytes": max_content_length
        }), 413


def add_rate_limit_headers(response):
    """Add rate limit headers to response."""
    if hasattr(g, 'rate_limit_remaining'):
        limiter = get_rate_limiter()
        response.headers['X-RateLimit-Limit'] = str(limiter.requests_per_minute)
        response.headers['X-RateLimit-Remaining'] = str(g.rate_limit_remaining)
        response.headers['X-RateLimit-Reset'] = str(int(time.time()) + g.rate_limit_reset)
    return response
