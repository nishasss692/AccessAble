"""Repository layer for Event persistence and querying."""

from datetime import datetime
from typing import Optional, Sequence
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.event import Event


class EventRepository:
    """Encapsulates database access for Event records using an injected SQLAlchemy session."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, event: Event) -> Event:
        """Persist a new Event record and commit the transaction.

        If a database integrity error occurs (such as a unique constraint violation),
        the session is rolled back and the IntegrityError is re-raised for the service
        layer to handle.
        """
        try:
            self.db.add(event)
            self.db.commit()
            self.db.refresh(event)
            return event
        except IntegrityError:
            self.db.rollback()
            raise
        except SQLAlchemyError:
            self.db.rollback()
            raise

    def get_by_id(self, event_id: int) -> Optional[Event]:
        """Retrieve an Event by its primary key ID."""
        return self.db.get(Event, event_id)

    def get_by_source_and_external_id(
        self,
        source: str,
        external_event_id: str,
    ) -> Optional[Event]:
        """Find an existing Event matching source and external_event_id.

        Returns None if external_event_id is None/empty or no matching record exists.
        """
        if not external_event_id:
            return None
        stmt = select(Event).where(
            Event.source == source,
            Event.external_event_id == external_event_id,
        )
        return self.db.scalar(stmt)

    def list_events(
        self,
        source: Optional[str] = None,
        event_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Event], int]:
        """Query events with optional filtering, stable ordering, and pagination.

        Returns:
            A tuple of (events, total_matching_count).
        """
        stmt: Select = select(Event)

        if source:
            stmt = stmt.where(Event.source == source)
        if event_type:
            stmt = stmt.where(Event.event_type == event_type)
        if start_time:
            stmt = stmt.where(Event.occurred_at >= start_time)
        if end_time:
            stmt = stmt.where(Event.occurred_at <= end_time)

        # Count total matching records before pagination
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt) or 0

        # Apply stable ordering: newest received first, tie-break by id desc
        paged_stmt = stmt.order_by(Event.received_at.desc(), Event.id.desc())
        paged_stmt = paged_stmt.limit(limit).offset(offset)

        items = self.db.scalars(paged_stmt).all()
        return items, total
