"""Service layer for event acknowledgement management and validation."""

import logging
from typing import Optional, Sequence

from app.models.acknowledgement import Acknowledgement, utc_now
from app.repositories.acknowledgement_repository import AcknowledgementRepository
from app.repositories.event_repository import EventRepository
from app.schemas.acknowledgement import AcknowledgementCreate

logger = logging.getLogger(__name__)


class EventNotFoundError(Exception):
    """Raised when an acknowledgement references a non-existent event."""


class DuplicateAcknowledgementError(Exception):
    """Raised when an acknowledgement duplicates the current state of an event."""


class AcknowledgementService:
    """Coordinates acknowledgement creation, event validation, and history queries."""

    def __init__(
        self,
        acknowledgement_repo: AcknowledgementRepository,
        event_repo: EventRepository,
    ) -> None:
        self.acknowledgement_repo = acknowledgement_repo
        self.event_repo = event_repo

    def create_acknowledgement(self, ack_in: AcknowledgementCreate) -> Acknowledgement:
        """Create a new acknowledgement action for an event.

        Validates that:
        1. The referenced event actually exists in the database.
        2. Unintended duplicate operations (e.g., repeatedly submitting the same
           action on an event that is already in that state) are prevented.

        Returns:
            The newly created Acknowledgement record with associated Event relationship.
        """
        # 1. Verify referenced event exists
        event = self.event_repo.get_by_id(ack_in.event_id)
        if event is None:
            raise EventNotFoundError(f"Event with id {ack_in.event_id} does not exist.")

        # 2. Check for unintended duplicate action
        latest_ack = self.acknowledgement_repo.get_latest_by_event_id(ack_in.event_id)
        if latest_ack is not None and latest_ack.action == ack_in.action:
            raise DuplicateAcknowledgementError(
                f"Event {ack_in.event_id} has already been {ack_in.action}."
            )

        # 3. Create and persist new history record
        ack = Acknowledgement(
            event_id=ack_in.event_id,
            action=ack_in.action,
            note=ack_in.note,
            acknowledged_at=utc_now(),
        )
        return self.acknowledgement_repo.create(ack)

    def list_acknowledgements(
        self,
        event_id: Optional[int] = None,
        action: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Acknowledgement], int]:
        """Query acknowledgement history."""
        return self.acknowledgement_repo.list_acknowledgements(
            event_id=event_id,
            action=action,
            limit=limit,
            offset=offset,
        )
