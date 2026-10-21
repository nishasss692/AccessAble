"""Event deduplication service and interim policy definition."""

import logging
from typing import Optional
from app.models.event import Event
from app.repositories.event_repository import EventRepository

logger = logging.getLogger(__name__)


class EventDeduplicator:
    """Handles event deduplication logic and policies.

    Deduplication Policy:
    1. Events WITH `external_event_id`:
       - Deduplicated using the composite unique key (source, external_event_id).
       - If an event with the same source and non-null external_event_id exists,
         it is identified as a duplicate and the existing event record is returned.

    2. Events WITHOUT `external_event_id` (Interim Policy):
       - Treated as distinct and are NOT deduplicated.
       - Rationale: Physical event sources (e.g. repeated button presses, sensors)
         can legitimately emit multiple events with identical timestamps or payloads.
         Attempting to deduplicate without a definitive external identifier or a
         strict event-window hash runs the risk of silently dropping valid events.
       - This interim policy is pending team review and confirmation before the API
         contract is finalized.
    """

    @staticmethod
    def find_duplicate(
        repo: EventRepository,
        source: str,
        external_event_id: Optional[str],
    ) -> Optional[Event]:
        """Check if an event is a duplicate based on the deduplication policy.

        Returns:
            The existing Event if a duplicate is found, otherwise None.
        """
        if not external_event_id:
            # Under the documented interim policy, events without external_event_id
            # are not deduplicated and are treated as distinct.
            return None

        return repo.get_by_source_and_external_id(
            source=source,
            external_event_id=external_event_id,
        )
