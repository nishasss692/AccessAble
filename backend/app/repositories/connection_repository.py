"""Repository for managing external source connection records."""

from datetime import datetime
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.source_connection import SourceConnection, utc_now


class ConnectionRepository:
    """Repository handling database operations for SourceConnection records."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_source(self, source: str) -> Optional[SourceConnection]:
        """Retrieve connection record by source name."""
        stmt = select(SourceConnection).where(SourceConnection.source == source)
        return self.db.scalar(stmt)

    def upsert_connection_status(
        self,
        source: str,
        status: str,
        is_connected: bool,
        last_checked_at: Optional[datetime] = None,
        last_successful_sync_at: Optional[datetime] = None,
        error_message: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> SourceConnection:
        """Create or update a source connection state record."""
        try:
            record = self.get_by_source(source)
            checked_time = last_checked_at or utc_now()
            meta_details = details if details is not None else {}

            if record is None:
                record = SourceConnection(
                    source=source,
                    status=status,
                    is_connected=is_connected,
                    last_checked_at=checked_time,
                    last_successful_sync_at=last_successful_sync_at,
                    error_message=error_message,
                    details=meta_details,
                    updated_at=utc_now(),
                )
                self.db.add(record)
            else:
                record.status = status
                record.is_connected = is_connected
                record.last_checked_at = checked_time
                if last_successful_sync_at is not None:
                    record.last_successful_sync_at = last_successful_sync_at
                record.error_message = error_message
                record.details = meta_details
                record.updated_at = utc_now()

            self.db.commit()
            self.db.refresh(record)
            return record
        except SQLAlchemyError:
            self.db.rollback()
            raise
