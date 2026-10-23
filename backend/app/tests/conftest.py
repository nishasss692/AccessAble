"""Pytest fixtures and isolated test database setup."""

import os
os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT", "1")

from typing import Generator
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.acknowledgement import Acknowledgement  # noqa: F401
from app.models.event import Event  # noqa: F401
from app.models.source_connection import SourceConnection  # noqa: F401
from app.models.user_preferences import UserPreference  # noqa: F401
from app.repositories.acknowledgement_repository import AcknowledgementRepository
from app.repositories.connection_repository import ConnectionRepository
from app.repositories.event_repository import EventRepository
from app.repositories.preferences_repository import PreferencesRepository
from app.services.acknowledgement_service import AcknowledgementService
from app.services.event_ingestion_service import EventIngestionService
from app.services.preference_service import PreferenceService

# Isolated SQLite in-memory database shared only within the test thread
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all tables in the isolated test database."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a clean database session for each test, rolling back any changes."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    # Override get_db in FastAPI app
    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def event_repo(db_session: Session) -> EventRepository:
    """Provide an EventRepository bound to the test session."""
    return EventRepository(db_session)


@pytest.fixture
def ingestion_service(event_repo: EventRepository) -> EventIngestionService:
    """Provide an EventIngestionService bound to the test repository."""
    return EventIngestionService(event_repo)


@pytest.fixture
def preferences_repo(db_session: Session) -> PreferencesRepository:
    """Provide a PreferencesRepository bound to the test session."""
    return PreferencesRepository(db_session)


@pytest.fixture
def preference_service(preferences_repo: PreferencesRepository) -> PreferenceService:
    """Provide a PreferenceService bound to the test repository."""
    return PreferenceService(preferences_repo)


@pytest.fixture
def acknowledgement_repo(db_session: Session) -> AcknowledgementRepository:
    """Provide an AcknowledgementRepository bound to the test session."""
    return AcknowledgementRepository(db_session)


@pytest.fixture
def acknowledgement_service(
    acknowledgement_repo: AcknowledgementRepository,
    event_repo: EventRepository,
) -> AcknowledgementService:
    """Provide an AcknowledgementService bound to test repositories."""
    return AcknowledgementService(
        acknowledgement_repo=acknowledgement_repo,
        event_repo=event_repo,
    )


@pytest.fixture
def connection_repo(db_session: Session) -> ConnectionRepository:
    """Provide a ConnectionRepository bound to the test session."""
    return ConnectionRepository(db_session)


@pytest.fixture
def client(db_session: Session):
    """Provide a TestClient with database session overridden by test memory DB."""
    from fastapi.testclient import TestClient
    with TestClient(app) as test_client:
        yield test_client
