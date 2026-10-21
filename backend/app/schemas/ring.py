"""Pydantic schemas for Ring integration status and configuration."""

from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.event import normalize_to_utc

RingConnectionStatus = Literal["connected", "disconnected", "error", "unknown"]


class RingStatusResponse(BaseModel):
    """Response schema for Ring integration status endpoint."""

    model_config = ConfigDict(from_attributes=True)

    source: str = Field(default="ring", description="Integration source identifier")
    status: RingConnectionStatus = Field(
        ...,
        description="Current state of integration: 'connected', 'disconnected', 'error', 'unknown'",
    )
    is_connected: bool = Field(
        default=False,
        description="Whether an active, verified connection to Ring exists",
    )
    last_checked_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when integration health was last verified (UTC)",
    )
    last_successful_sync_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of the most recent successful event sync (UTC)",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Safe, non-sensitive error explanation if in error state",
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Safe diagnostic information regarding integration mode and capabilities",
    )

    @field_validator("last_checked_at", "last_successful_sync_at", mode="after")
    @classmethod
    def ensure_utc_timestamps(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is not None:
            return normalize_to_utc(v)
        return None
