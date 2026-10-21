"""FastAPI dependency providers for AccessAble."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.integrations.ring.adapter import RingAdapter
from app.repositories.acknowledgement_repository import AcknowledgementRepository
from app.repositories.connection_repository import ConnectionRepository
from app.repositories.event_repository import EventRepository
from app.repositories.preferences_repository import PreferencesRepository
from app.services.acknowledgement_service import AcknowledgementService
from app.services.event_ingestion_service import EventIngestionService
from app.services.preference_service import PreferenceService


def get_event_repository(db: Session = Depends(get_db)) -> EventRepository:
    """Dependency provider for EventRepository."""
    return EventRepository(db)


def get_event_ingestion_service(
    repo: EventRepository = Depends(get_event_repository),
) -> EventIngestionService:
    """Dependency provider for EventIngestionService."""
    return EventIngestionService(repo)


def get_preferences_repository(db: Session = Depends(get_db)) -> PreferencesRepository:
    """Dependency provider for PreferencesRepository."""
    return PreferencesRepository(db)


def get_preference_service(
    repo: PreferencesRepository = Depends(get_preferences_repository),
) -> PreferenceService:
    """Dependency provider for PreferenceService."""
    return PreferenceService(repo)


def get_acknowledgement_repository(
    db: Session = Depends(get_db),
) -> AcknowledgementRepository:
    """Dependency provider for AcknowledgementRepository."""
    return AcknowledgementRepository(db)


def get_acknowledgement_service(
    ack_repo: AcknowledgementRepository = Depends(get_acknowledgement_repository),
    event_repo: EventRepository = Depends(get_event_repository),
) -> AcknowledgementService:
    """Dependency provider for AcknowledgementService."""
    return AcknowledgementService(
        acknowledgement_repo=ack_repo,
        event_repo=event_repo,
    )


def get_connection_repository(
    db: Session = Depends(get_db),
) -> ConnectionRepository:
    """Dependency provider for ConnectionRepository."""
    return ConnectionRepository(db)


def get_ring_adapter() -> RingAdapter:
    """Dependency provider for RingAdapter."""
    return RingAdapter()
