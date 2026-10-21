"""Pydantic schemas for event acknowledgements and history."""

from datetime import datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.event import EventResponse, normalize_to_utc

ActionType = Literal["acknowledged", "dismissed"]


class AcknowledgementCreate(BaseModel):
    """Schema for creating a new acknowledgement."""

    model_config = ConfigDict(extra="forbid")

    event_id: int = Field(
        ...,
        gt=0,
        description="Internal ID of the event to acknowledge",
    )
    action: ActionType = Field(
        default="acknowledged",
        description="Action applied to the event: 'acknowledged' or 'dismissed'",
    )
    note: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional human-readable note or comment regarding the action",
    )

    @field_validator("note")
    @classmethod
    def clean_note(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            return trimmed if trimmed else None
        return None


class AcknowledgementResponse(BaseModel):
    """Schema for returning an acknowledgement record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    action: ActionType
    note: Optional[str] = None
    acknowledged_at: datetime
    event: Optional[EventResponse] = Field(
        default=None,
        description="Details of the referenced event when available",
    )

    @field_validator("acknowledged_at", mode="after")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        return normalize_to_utc(v)


class AcknowledgementListResponse(BaseModel):
    """Schema for paginated acknowledgement history listings."""

    items: list[AcknowledgementResponse]
    total: int
    limit: int
    offset: int
