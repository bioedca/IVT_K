"""
Upload model for secure, database-backed file upload tracking.

Phase 1 Security Fix: Replaces in-memory upload storage with database persistence.
Addresses: Thread safety, data persistence, secure ID generation, expiration.
"""
import enum
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Enum, Text, JSON, ForeignKey
from sqlalchemy.dialects.sqlite import TEXT
from sqlalchemy.orm import relationship

from app.extensions import db
from app.models.base import TimestampMixin


class UploadStatus(enum.Enum):
    """Upload processing status."""
    PENDING = "pending"           # Uploaded, not yet parsed
    PARSING = "parsing"           # Currently being parsed
    PARSED = "parsed"             # Successfully parsed
    PARSE_FAILED = "parse_failed" # Parsing failed
    VALIDATING = "validating"     # Being validated against layout
    VALIDATED = "validated"       # Validation passed
    VALIDATION_FAILED = "validation_failed"  # Validation failed
    PROCESSING = "processing"     # Being processed into database records
    PROCESSED = "processed"       # Successfully processed
    PROCESS_FAILED = "process_failed"  # Processing failed
    EXPIRED = "expired"           # TTL exceeded, marked for cleanup


class Upload(db.Model, TimestampMixin):
    """
    Database-backed upload tracking with secure IDs and expiration.

    Replaces the in-memory _upload_storage dict with:
    - Cryptographically secure UUID primary keys (not sequential)
    - Persistence across server restarts
    - Thread-safe database operations
    - Automatic expiration for cleanup
    - Content hash for deduplication
    """
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True)

    # Secure, non-sequential public identifier (UUID4)
    upload_id = Column(String(36), unique=True, nullable=False, index=True,
                       default=lambda: str(uuid.uuid4()))

    # Foreign keys
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    layout_id = Column(Integer, ForeignKey("plate_layouts.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("experimental_sessions.id"), nullable=True)

    # File info
    filename = Column(String(255), nullable=False)
    file_format = Column(String(10), nullable=False, default="txt")
    content_hash = Column(String(64), nullable=True)  # SHA-256 hash
    file_size_bytes = Column(Integer, nullable=True)

    # Content storage (TEXT for SQLite compatibility)
    content = Column(TEXT, nullable=True)  # Raw file content

    # Status tracking
    status = Column(Enum(UploadStatus), default=UploadStatus.PENDING, nullable=False, index=True)

    # User tracking
    username = Column(String(100), nullable=False, default="anonymous")
    client_ip = Column(String(45), nullable=True)  # IPv6 max length

    # Parsed metadata (JSON) - named 'parsed_metadata' to avoid SQLAlchemy reserved name
    parsed_metadata = Column(JSON, nullable=True)  # plate_format, temperature, etc.
    validation_result = Column(JSON, nullable=True)  # Validation details

    # Error tracking
    errors = Column(JSON, nullable=True)  # List of error messages
    warnings = Column(JSON, nullable=True)  # List of warning objects

    # Processing results
    plate_id = Column(Integer, ForeignKey("plates.id"), nullable=True)

    # Expiration (default 24 hours from creation)
    expires_at = Column(DateTime, nullable=False,
                        default=lambda: datetime.now(timezone.utc) + timedelta(hours=24))

    # Relationships
    project = relationship("Project")
    layout = relationship("PlateLayout")
    session = relationship("ExperimentalSession")
    plate = relationship("Plate")

    def __repr__(self):
        return f"<Upload id={self.id} {self.upload_id[:8]}... [{self.status.value}]>"

    @classmethod
    def create(
        cls,
        project_id: int,
        layout_id: int,
        filename: str,
        content: str,
        username: str,
        client_ip: Optional[str] = None,
        session_id: Optional[int] = None,
        file_format: str = "txt",
        ttl_hours: int = 24
    ) -> "Upload":
        """
        Create a new upload with secure defaults.

        Args:
            project_id: Target project ID
            layout_id: Target layout ID
            filename: Original filename
            content: Raw file content
            username: User performing upload
            client_ip: Client IP address for audit
            session_id: Optional existing session ID
            file_format: File format hint
            ttl_hours: Hours until expiration (default 24)

        Returns:
            New Upload instance (not yet committed)
        """
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        upload = cls(
            project_id=project_id,
            layout_id=layout_id,
            session_id=session_id,
            filename=filename,
            file_format=file_format,
            content=content,
            content_hash=content_hash,
            file_size_bytes=len(content.encode('utf-8')),
            username=username,
            client_ip=client_ip,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        )
        db.session.add(upload)
        return upload

    @classmethod
    def get_by_upload_id(cls, upload_id: str) -> Optional["Upload"]:
        """
        Get upload by public UUID, excluding expired uploads.

        Args:
            upload_id: Public UUID string

        Returns:
            Upload instance or None if not found/expired
        """
        return cls.query.filter(
            cls.upload_id == upload_id,
            cls.expires_at > datetime.now(timezone.utc),
            cls.status != UploadStatus.EXPIRED
        ).first()

    @classmethod
    def cleanup_expired(cls) -> int:
        """
        Mark expired uploads for cleanup.

        Returns:
            Number of uploads marked as expired
        """
        now = datetime.now(timezone.utc)
        expired = cls.query.filter(
            cls.expires_at <= now,
            cls.status != UploadStatus.EXPIRED
        ).all()

        count = 0
        for upload in expired:
            upload.status = UploadStatus.EXPIRED
            upload.content = None  # Clear content to free memory
            count += 1

        if count > 0:
            db.session.commit()

        return count

    def update_status(self, status: UploadStatus, errors: list = None, warnings: list = None):
        """
        Update upload status with optional error/warning info.

        Args:
            status: New status
            errors: List of error messages
            warnings: List of warning objects
        """
        self.status = status
        if errors is not None:
            self.errors = errors
        if warnings is not None:
            self.warnings = warnings
        db.session.flush()

    def set_metadata(self, metadata: dict):
        """Set parsed metadata."""
        self.parsed_metadata = metadata
        db.session.flush()

    def set_validation_result(self, result: dict):
        """Set validation result."""
        self.validation_result = result
        db.session.flush()

    def mark_processed(self, plate_id: int, session_id: int):
        """Mark upload as successfully processed."""
        self.status = UploadStatus.PROCESSED
        self.plate_id = plate_id
        self.session_id = session_id
        # Clear content after successful processing to free space
        self.content = None
        db.session.flush()

    def is_expired(self) -> bool:
        """Check if upload has expired."""
        if self.status == UploadStatus.EXPIRED:
            return True
        if not self.expires_at:
            return False
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > expires

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "upload_id": self.upload_id,
            "project_id": self.project_id,
            "layout_id": self.layout_id,
            "session_id": self.session_id,
            "filename": self.filename,
            "file_format": self.file_format,
            "file_size_bytes": self.file_size_bytes,
            "status": self.status.value if self.status else None,
            "username": self.username,
            "metadata": self.parsed_metadata,  # Use parsed_metadata to avoid reserved name
            "validation_result": self.validation_result,
            "errors": self.errors,
            "warnings": self.warnings,
            "plate_id": self.plate_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
