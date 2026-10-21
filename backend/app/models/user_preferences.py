"""User preferences SQLAlchemy model."""

from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class UserPreference(Base):
    """SQLAlchemy model representing user accessibility preferences.

    Supports a default single profile for the MVP while preserving the profile_name
    field for future multi-user extensions without requiring schema rewrites.
    """

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        default="default",
        index=True,
    )
    visual_alerts_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    audio_alerts_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    high_contrast_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    text_scale: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    def __repr__(self) -> str:
        return (
            f"<UserPreference(id={self.id}, profile_name='{self.profile_name}', "
            f"visual={self.visual_alerts_enabled}, audio={self.audio_alerts_enabled}, "
            f"high_contrast={self.high_contrast_enabled}, text_scale='{self.text_scale}')>"
        )
