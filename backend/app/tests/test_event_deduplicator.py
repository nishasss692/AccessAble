"""Unit tests for EventDeduplicator."""

from datetime import datetime, timezone
from app.models.event import Event
from app.repositories.event_repository import EventRepository
from app.services.event_deduplicator import EventDeduplicator


def test_deduplicator_returns_existing_when_external_id_matches(event_repo: EventRepository):
    event = Event(
        source="ring",
        external_event_id="ext-dedup-1",
        event_type="motion",
        occurred_at=datetime.now(timezone.utc),
        metadata_json={},
    )
    event_repo.create(event)

    duplicate = EventDeduplicator.find_duplicate(
        repo=event_repo,
        source="ring",
        external_event_id="ext-dedup-1",
    )
    assert duplicate is not None
    assert duplicate.id == event.id


def test_deduplicator_returns_none_when_no_match(event_repo: EventRepository):
    duplicate = EventDeduplicator.find_duplicate(
        repo=event_repo,
        source="ring",
        external_event_id="unseen-id",
    )
    assert duplicate is None


def test_deduplicator_returns_none_when_external_id_is_none(event_repo: EventRepository):
    # Under interim policy, events without external_id are not deduplicated
    duplicate = EventDeduplicator.find_duplicate(
        repo=event_repo,
        source="ring",
        external_event_id=None,
    )
    assert duplicate is None
