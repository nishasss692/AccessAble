"""Pydantic schemas for accessibility preferences."""

from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

TextScaleType = Literal["small", "medium", "large"]


def normalize_to_utc(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware and set to UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class PreferencesBase(BaseModel):
    """Base schema for accessibility preferences."""

    visual_alerts_enabled: bool = Field(
        default=True,
        description="Whether visual alert notifications and flashing indicators are enabled",
    )
    audio_alerts_enabled: bool = Field(
        default=True,
        description="Whether sound cues and chime alerts are enabled",
    )
    high_contrast_enabled: bool = Field(
        default=False,
        description="Whether high contrast color mode is enabled for low-vision accessibility",
    )
    text_scale: TextScaleType = Field(
        default="medium",
        description="Text scaling preference: 'small', 'medium', or 'large'",
    )


class PreferencesUpdate(PreferencesBase):
    """Schema for updating preferences via PUT /api/v1/preferences."""

    model_config = ConfigDict(extra="forbid")


class PreferencesResponse(PreferencesBase):
    """Schema for returning saved accessibility preferences."""

    model_config = ConfigDict(from_attributes=True)

    updated_at: datetime = Field(
        description="Timestamp when preferences were last created or updated in UTC",
    )

    @field_validator("updated_at", mode="after")
    @classmethod
    def ensure_utc_updated_at(cls, v: datetime) -> datetime:
        return normalize_to_utc(v)
