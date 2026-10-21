"""Validation services for incoming event data."""

from typing import Any
from pydantic import ValidationError

from app.schemas.event import EventCreate


class EventValidationError(Exception):
    """Raised when an event payload fails validation."""

    def __init__(self, message: str, errors: Any = None) -> None:
        super().__init__(message)
        self.errors = errors


def validate_event_create_payload(payload: dict[str, Any]) -> EventCreate:
    """Validate a raw dictionary payload against the EventCreate schema.

    Raises:
        EventValidationError: If payload fails Pydantic schema validation.
    """
    try:
        return EventCreate.model_validate(payload)
    except ValidationError as err:
        raise EventValidationError(
            f"Event payload validation failed: {err.error_count()} error(s)",
            errors=err.errors(),
        ) from err
