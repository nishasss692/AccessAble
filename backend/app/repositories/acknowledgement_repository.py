"""Repository for Acknowledgement persistence and queries."""

from typing import Optional, Sequence
from sqlalchemy import Select, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.acknowledgement import Acknowledgement


class AcknowledgementRepository:
    """Repository handling database operations for Acknowledgement records."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, acknowledgement: Acknowledgement) -> Acknowledgement:
        """Persist a new Acknowledgement record and commit the transaction."""
        try:
            self.db.add(acknowledgement)
            self.db.commit()
            self.db.refresh(acknowledgement)
            return acknowledgement
        except SQLAlchemyError:
            self.db.rollback()
            raise

    def get_by_id(self, ack_id: int) -> Optional[Acknowledgement]:
        """Fetch an Acknowledgement by its primary key ID."""
        stmt = select(Acknowledgement).where(Acknowledgement.id == ack_id)
        return self.db.scalar(stmt)

    def get_latest_by_event_id(self, event_id: int) -> Optional[Acknowledgement]:
        """Fetch the most recent Acknowledgement record for an event."""
        stmt = (
            select(Acknowledgement)
            .where(Acknowledgement.event_id == event_id)
            .order_by(Acknowledgement.acknowledged_at.desc(), Acknowledgement.id.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def list_acknowledgements(
        self,
        event_id: Optional[int] = None,
        action: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Acknowledgement], int]:
        """List acknowledgements with optional filters, deterministic ordering, and pagination.

        Returns:
            A tuple of (items, total_matching_count).
        """
        stmt: Select = select(Acknowledgement)

        if event_id is not None:
            stmt = stmt.where(Acknowledgement.event_id == event_id)
        if action is not None:
            stmt = stmt.where(Acknowledgement.action == action)

        # Count total matching records before pagination
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.scalar(count_stmt) or 0

        # Stable ordering: newest acknowledgements first, break ties with ID desc
        paged_stmt = stmt.order_by(
            Acknowledgement.acknowledged_at.desc(),
            Acknowledgement.id.desc(),
        )
        paged_stmt = paged_stmt.limit(limit).offset(offset)

        items = self.db.scalars(paged_stmt).all()
        return items, total
