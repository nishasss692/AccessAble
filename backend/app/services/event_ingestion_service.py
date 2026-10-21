"""Event ingestion service coordinating normalization, deduplication, and persistence."""

from dataclasses import dataclass
from typing import Optional
from sqlalchemy.exc import IntegrityError

from app.models.event import Event
from app.repositories.event_repository import EventRepository
from app.schemas.event import EventCreate
from app.services.event_deduplicator import EventDeduplicator
from app.services.event_normalizer import EventNormalizer


@dataclass
class IngestionResult:
    """Represents the outcome of an event ingestion attempt."""

    event: Event
    is_duplicate: bool


class EventIngestionService:
    """Service orchestrating event ingestion, normalization, and persistence."""

    def __init__(self, repository: EventRepository) -> None:
        self.repository = repository
        self.normalizer = EventNormalizer()
        self.deduplicator = EventDeduplicator()

    def ingest_event(self, event_in: EventCreate) -> IngestionResult:
        """Process and persist an incoming validated event.

        Flow:
        1. Normalize the event schema attributes.
        2. Check for an existing duplicate if external_event_id is present.
        3. Persist the new event to the repository.
        4. If a concurrent duplicate insertion causes an IntegrityError,
           catch it, fetch the duplicate record, and return it safely.

        Returns:
            IngestionResult with the persisted/found Event and a boolean indicating
            whether it was an existing duplicate.
        """
        normalized = self.normalizer.normalize(event_in)

        # 1. Check for known duplicate using the deduplication policy
        existing = self.deduplicator.find_duplicate(
            repo=self.repository,
            source=normalized.source,
            external_event_id=normalized.external_event_id,
        )
        if existing is not None:
            return IngestionResult(event=existing, is_duplicate=True)

        # 2. Build ORM model instance
        event_model = Event(
            source=normalized.source,
            external_event_id=normalized.external_event_id,
            event_type=normalized.event_type,
            occurred_at=normalized.occurred_at,
            device_id=normalized.device_id,
            metadata_json=normalized.metadata,
        )

        # 3. Attempt creation, catching concurrent integrity conflicts
        try:
            persisted = self.repository.create(event_model)
            return IngestionResult(event=persisted, is_duplicate=False)
        except IntegrityError:
            # Race condition handling: another worker inserted with same (source, external_event_id)
            if normalized.external_event_id:
                concurrent_match = self.repository.get_by_source_and_external_id(
                    source=normalized.source,
                    external_event_id=normalized.external_event_id,
                )
                if concurrent_match is not None:
                    return IngestionResult(event=concurrent_match, is_duplicate=True)
            # Re-raise if not resolved by duplicate key collision
            raise
