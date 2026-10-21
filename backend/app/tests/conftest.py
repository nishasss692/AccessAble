"""Pytest fixtures and isolated test database setup."""

from typing import Generator
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.event import Event  # noqa: F401
from app.repositories.event_repository import EventRepository
from app.services.event_ingestion_service import EventIngestionService

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
