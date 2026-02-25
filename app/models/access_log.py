"""AccessLog model - tracks PIN authentication events."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text

from app.extensions import db


class AccessLog(db.Model):
    """
    Log of access gate events (PIN verification attempts, logins, logouts).

    Kept separate from AuditLog to avoid mixing auth events with science audit trail.
    """
    __tablename__ = "access_logs"

    id = Column(Integer, primary_key=True)
    event_type = Column(String(30), nullable=False)  # 'pin_attempt', 'login', 'logout'
    success = Column(Boolean, nullable=False)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    details = Column(String(200), nullable=True)  # e.g. "wrong pin", "session expired"

    def __repr__(self):
        return f"<AccessLog id={self.id} {self.event_type} success={self.success} {self.ip_address}>"

    @classmethod
    def log_event(
        cls,
        event_type: str,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[str] = None,
    ) -> "AccessLog":
        """Create and persist a new access log entry."""
        entry = cls(
            event_type=event_type,
            success=success,
            ip_address=ip_address,
            user_agent=(user_agent[:500] if user_agent else None),
            details=(details[:200] if details else None),
        )
        db.session.add(entry)
        db.session.commit()
        return entry
