"""Pydantic schemas for Event ingestion, response, and listing."""

import json
from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

FORBIDDEN_METADATA_KEYS = {
    "token",
    "secret",
    "password",
    "auth_token",
    "access_token",
    "refresh_token",
    "api_key",
    "client_secret",
    "authorization",
}


def normalize_to_utc(dt: datetime) -> datetime:
    """Ensure a datetime object is timezone-aware and set to UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class EventBase(BaseModel):
    """Base schema containing common event properties."""

    source: str = Field(..., min_length=1, description="Event source (e.g., 'ring', 'demo')")
    external_event_id: Optional[str] = Field(
        default=None,
        description="Source-specific event ID when available for deduplication",
    )
    event_type: str = Field(..., min_length=1, description="Event type (e.g., 'motion', 'doorbell_ring')")
    occurred_at: datetime = Field(..., description="Timestamp when the event occurred in UTC")
    device_id: Optional[str] = Field(default=None, description="Source device identifier")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON-compatible payload for supplemental event data",
    )


class EventCreate(EventBase):
    """Schema for validating event creation requests."""

    model_config = ConfigDict(extra="forbid")

    @field_validator("source", "event_type")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Field must not be empty or whitespace only")
        return trimmed

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, v: datetime) -> datetime:
        return normalize_to_utc(v)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v: dict[str, Any]) -> dict[str, Any]:
        # Ensure metadata is strictly JSON-serializable
        try:
            json.dumps(v)
        except (TypeError, ValueError) as err:
            raise ValueError(f"Metadata must be JSON-serializable: {err}") from err

        # Reject secret or credential-bearing keys
        for key in v.keys():
            if str(key).lower().strip() in FORBIDDEN_METADATA_KEYS:
                raise ValueError(
                    f"Metadata contains forbidden sensitive key '{key}'. "
                    "Secrets and credentials must not be stored in event metadata."
                )
        return v


class EventResponse(BaseModel):
    """Schema for returning an event across the API boundary.

    Exposes the public field `metadata`, properly resolving from the internal ORM
    property `metadata_json` (since SQLAlchemy declarative reserves `metadata`).
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    id: int
    source: str
    external_event_id: Optional[str] = None
    event_type: str
    occurred_at: datetime
    device_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    received_at: datetime

    @model_validator(mode="before")
    @classmethod
    def resolve_orm_metadata(cls, data: Any) -> Any:
        """Map ORM attribute `metadata_json` to public schema field `metadata`.

        Avoids reading `data.metadata` on ORM models where it references SQLAlchemy's
        internal MetaData object.
        """
        if hasattr(data, "metadata_json"):
            return {
                "id": getattr(data, "id", None),
                "source": getattr(data, "source", None),
                "external_event_id": getattr(data, "external_event_id", None),
                "event_type": getattr(data, "event_type", None),
                "occurred_at": getattr(data, "occurred_at", None),
                "device_id": getattr(data, "device_id", None),
                "metadata": getattr(data, "metadata_json", {}),
                "received_at": getattr(data, "received_at", None),
            }
        if isinstance(data, dict) and "metadata_json" in data and "metadata" not in data:
            data = dict(data)
            data["metadata"] = data.pop("metadata_json")
        return data

    @field_validator("occurred_at", "received_at", mode="after")
    @classmethod
    def ensure_utc_timestamps(cls, v: datetime) -> datetime:
        return normalize_to_utc(v)


class EventListResponse(BaseModel):
    """Schema for paginated event listing responses."""

    items: list[EventResponse]
    total: int
    limit: int
    offset: int
