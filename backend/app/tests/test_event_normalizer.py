"""Unit tests for EventNormalizer service."""

from datetime import datetime, timezone
from app.schemas.event import EventCreate
from app.services.event_normalizer import EventNormalizer


def test_event_normalizer_trims_and_lowercases():
    raw = EventCreate(
        source="  RING  ",
        external_event_id="  ext-abc-123  ",
        event_type="  MOTION  ",
        occurred_at=datetime(2026, 10, 21, 10, 0, 0, tzinfo=timezone.utc),
        device_id="  cam-1  ",
        metadata={"key": "value"},
    )
    normalized = EventNormalizer.normalize(raw)

    assert normalized.source == "ring"
    assert normalized.external_event_id == "ext-abc-123"
    assert normalized.event_type == "motion"
    assert normalized.device_id == "cam-1"
    assert normalized.metadata == {"key": "value"}


def test_event_normalizer_preserves_none_fields():
    raw = EventCreate(
        source="demo",
        external_event_id=None,
        event_type="ding",
        occurred_at=datetime.now(timezone.utc),
        device_id=None,
    )
    normalized = EventNormalizer.normalize(raw)

    assert normalized.external_event_id is None
    assert normalized.device_id is None
