"""Source connection model representing external integration status."""

from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import Boolean, DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class SourceConnection(Base):
    """SQLAlchemy model tracking external source integration status (e.g. Ring, Demo).

    Fields:
        source: Name of external source (e.g., 'ring'). Unique key.
        status: Integration state ('connected', 'disconnected', 'error', 'unknown').
        is_connected: Boolean flag indicating if active live connection is verified.
        last_checked_at: Timestamp when health or connection was last checked.
        last_successful_sync_at: Timestamp of last successful event sync, nullable.
        error_message: Safe, non-sensitive error description if status == 'error'.
        details: Supplemental diagnostics (e.g., mode, capabilities).
        updated_at: Timestamp when record was updated.
    """

    __tablename__ = "source_connections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    is_connected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    def __repr__(self) -> str:
        return (
            f"<SourceConnection(source='{self.source}', status='{self.status}', "
            f"is_connected={self.is_connected}, last_checked_at='{self.last_checked_at}')>"
        )
