"""Acknowledgement SQLAlchemy model."""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.event import Event


def utc_now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class Acknowledgement(Base):
    """SQLAlchemy model representing an acknowledgement or dismissal of an event.

    Each action is stored as a distinct record to preserve the full audit history.
    """

    __tablename__ = "acknowledgements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    acknowledged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )

    # Joined relationship to the parent event for rich history representation
    event: Mapped["Event"] = relationship(lazy="joined")

    def __repr__(self) -> str:
        return (
            f"<Acknowledgement(id={self.id}, event_id={self.event_id}, "
            f"action='{self.action}', acknowledged_at='{self.acknowledged_at}')>"
        )
