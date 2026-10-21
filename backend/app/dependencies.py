"""FastAPI dependency providers for AccessAble."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.event_repository import EventRepository
from app.services.event_ingestion_service import EventIngestionService


def get_event_repository(db: Session = Depends(get_db)) -> EventRepository:
    """Dependency provider for EventRepository."""
    return EventRepository(db)


def get_event_ingestion_service(
    repo: EventRepository = Depends(get_event_repository),
) -> EventIngestionService:
    """Dependency provider for EventIngestionService."""
    return EventIngestionService(repo)
