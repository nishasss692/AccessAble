"""Event model for AccessAble."""

from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import DateTime, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    """Return current timezone-aware UTC datetime.
    
    Compatible with Python 3.11+ / 3.13 where datetime.utcnow() is deprecated.
    """
    return datetime.now(timezone.utc)


class Event(Base):
    """SQLAlchemy model representing an accessibility event.
    
    Fields:
        id: Auto-incrementing integer primary key.
        source: Event source identifier (e.g., 'ring', 'demo').
        external_event_id: Source-provided external event ID, nullable.
        event_type: Category/type of event (e.g., 'motion', 'doorbell_ring').
        occurred_at: Timestamp when the event actually occurred (UTC).
        device_id: Source device identifier, nullable.
        metadata_json: Flexible JSON payload mapped to column 'metadata'.
        received_at: Timestamp when the backend recorded the event (UTC).
        
    Duplicate Policy:
        A unique constraint `uq_events_source_external_event_id` is enforced on
        (source, external_event_id). Note that in SQLite (and standard SQL),
        NULL values in unique constraints do not collide; therefore, events with
        external_event_id=None are not deduplicated by this database constraint.
        A dedicated application-level deduplication policy applies to them.
    """

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    external_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    device_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("source", "external_event_id", name="uq_events_source_external_event_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Event(id={self.id}, source='{self.source}', "
            f"event_type='{self.event_type}', occurred_at='{self.occurred_at}')>"
        )
