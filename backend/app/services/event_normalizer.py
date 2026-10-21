"""Event normalization service.

Standardizes incoming event attributes to ensure consistent representations across sources.
"""

from app.schemas.event import EventCreate, normalize_to_utc


class EventNormalizer:
    """Normalizes EventCreate schema instances into a canonical representation."""

    @staticmethod
    def normalize(event_in: EventCreate) -> EventCreate:
        """Return a normalized EventCreate instance.

        - Standardizes `source` to lowercase stripped string.
        - Standardizes `event_type` to lowercase stripped string.
        - Standardizes `device_id` and `external_event_id` to stripped strings if present.
        - Normalizes `occurred_at` to timezone-aware UTC datetime.
        """
        norm_source = event_in.source.strip().lower()
        norm_event_type = event_in.event_type.strip().lower()
        norm_external_id = (
            event_in.external_event_id.strip()
            if event_in.external_event_id is not None
            else None
        )
        norm_device_id = (
            event_in.device_id.strip()
            if event_in.device_id is not None
            else None
        )
        norm_occurred_at = normalize_to_utc(event_in.occurred_at)

        return EventCreate(
            source=norm_source,
            external_event_id=norm_external_id,
            event_type=norm_event_type,
            occurred_at=norm_occurred_at,
            device_id=norm_device_id,
            metadata=dict(event_in.metadata),
        )
