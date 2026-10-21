"""Tests for Event schemas, repository, and ingestion service."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.event import Event
from app.repositories.event_repository import EventRepository
from app.schemas.event import EventCreate, EventResponse
from app.services.event_ingestion_service import EventIngestionService


class TestEventSchemas:
    """Tests for Pydantic event schema validation."""

    def test_valid_event_schema(self):
        payload = {
            "source": "ring",
            "external_event_id": "event-123",
            "event_type": "motion",
            "occurred_at": "2026-10-21T12:30:00Z",
            "device_id": "device-456",
            "metadata": {"battery_level": 92},
        }
        event_in = EventCreate.model_validate(payload)
        assert event_in.source == "ring"
        assert event_in.external_event_id == "event-123"
        assert event_in.event_type == "motion"
        assert event_in.device_id == "device-456"
        assert event_in.metadata == {"battery_level": 92}
        assert event_in.occurred_at.tzinfo == timezone.utc

    def test_missing_required_fields(self):
        # Missing source
        with pytest.raises(ValidationError):
            EventCreate.model_validate({
                "event_type": "motion",
                "occurred_at": "2026-10-21T12:30:00Z",
            })

        # Missing event_type
        with pytest.raises(ValidationError):
            EventCreate.model_validate({
                "source": "ring",
                "occurred_at": "2026-10-21T12:30:00Z",
            })

        # Missing occurred_at
        with pytest.raises(ValidationError):
            EventCreate.model_validate({
                "source": "ring",
                "event_type": "motion",
            })

    def test_empty_or_whitespace_strings_rejected(self):
        with pytest.raises(ValidationError):
            EventCreate(
                source="   ",
                event_type="motion",
                occurred_at=datetime.now(timezone.utc),
            )

        with pytest.raises(ValidationError):
            EventCreate(
                source="ring",
                event_type="",
                occurred_at=datetime.now(timezone.utc),
            )

    def test_invalid_timestamps_rejected(self):
        with pytest.raises(ValidationError):
            EventCreate.model_validate({
                "source": "ring",
                "event_type": "motion",
                "occurred_at": "not-a-valid-timestamp",
            })

    def test_nullable_external_id_and_device_id(self):
        event_in = EventCreate(
            source="ring",
            external_event_id=None,
            event_type="motion",
            occurred_at=datetime.now(timezone.utc),
            device_id=None,
        )
        assert event_in.external_event_id is None
        assert event_in.device_id is None
        assert event_in.metadata == {}

    def test_forbidden_credentials_in_metadata_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            EventCreate(
                source="ring",
                event_type="motion",
                occurred_at=datetime.now(timezone.utc),
                metadata={"api_key": "secret-token-123"},
            )
        assert "forbidden sensitive key" in str(exc_info.value)

    def test_response_schema_field_mapping_and_timestamp_utc(self):
        # Simulate ORM model where attribute is metadata_json and timestamps are naive
        naive_time = datetime(2026, 10, 21, 14, 0, 0)
        orm_event = Event(
            id=42,
            source="demo",
            external_event_id=None,
            event_type="doorbell_press",
            occurred_at=naive_time,
            device_id="front_door",
            metadata_json={"chime": "ding-dong"},
            received_at=naive_time,
        )

        resp = EventResponse.model_validate(orm_event)
        assert resp.id == 42
        assert resp.source == "demo"
        # Verify metadata_json is exposed as public field metadata
        assert resp.metadata == {"chime": "ding-dong"}
        # Verify naive timestamps are normalized with UTC timezone
        assert resp.occurred_at.tzinfo == timezone.utc
        assert resp.received_at.tzinfo == timezone.utc

        # Verify JSON serialization uses "metadata" key
        dumped = resp.model_dump()
        assert "metadata" in dumped
        assert "metadata_json" not in dumped


class TestEventPersistenceAndRepository:
    """Tests for EventRepository and database operations."""

    def test_successful_persistence_and_retrieval(self, event_repo: EventRepository):
        occurred = datetime(2026, 10, 21, 12, 0, 0, tzinfo=timezone.utc)
        event = Event(
            source="ring",
            external_event_id="ext-001",
            event_type="motion",
            occurred_at=occurred,
            device_id="cam-1",
            metadata_json={"zone": "front_yard"},
        )
        saved = event_repo.create(event)

        assert saved.id is not None
        assert saved.source == "ring"
        assert saved.metadata_json == {"zone": "front_yard"}

        retrieved = event_repo.get_by_id(saved.id)
        assert retrieved is not None
        assert retrieved.id == saved.id
        assert retrieved.external_event_id == "ext-001"

    def test_retrieval_by_source_and_external_id(self, event_repo: EventRepository):
        event = Event(
            source="ring",
            external_event_id="ext-unique-99",
            event_type="ding",
            occurred_at=datetime.now(timezone.utc),
            metadata_json={},
        )
        event_repo.create(event)

        found = event_repo.get_by_source_and_external_id("ring", "ext-unique-99")
        assert found is not None
        assert found.external_event_id == "ext-unique-99"

        not_found = event_repo.get_by_source_and_external_id("ring", "non-existent")
        assert not_found is None

    def test_transaction_rollback_on_persistence_failure(
        self,
        event_repo: EventRepository,
        db_session: Session,
    ):
        event1 = Event(
            source="ring",
            external_event_id="duplicate-id",
            event_type="motion",
            occurred_at=datetime.now(timezone.utc),
            metadata_json={},
        )
        event_repo.create(event1)

        # Attempt to insert identical (source, external_event_id)
        event2 = Event(
            source="ring",
            external_event_id="duplicate-id",
            event_type="motion",
            occurred_at=datetime.now(timezone.utc),
            metadata_json={},
        )

        with pytest.raises(IntegrityError):
            event_repo.create(event2)

        # Confirm session is still usable after repository rolled back
        assert db_session.is_active


class TestEventIngestionService:
    """Tests for EventIngestionService deduplication and ingestion workflow."""

    def test_ingest_new_event(self, ingestion_service: EventIngestionService):
        event_in = EventCreate(
            source="ring",
            external_event_id="evt-new-1",
            event_type="motion",
            occurred_at=datetime.now(timezone.utc),
            device_id="cam-front",
            metadata={"sensitivity": "high"},
        )
        result = ingestion_service.ingest_event(event_in)

        assert result.is_duplicate is False
        assert result.event.id is not None
        assert result.event.external_event_id == "evt-new-1"
        assert result.event.metadata_json == {"sensitivity": "high"}

    def test_duplicate_detection_with_external_id(
        self,
        ingestion_service: EventIngestionService,
    ):
        event_in = EventCreate(
            source="ring",
            external_event_id="evt-dup-1",
            event_type="motion",
            occurred_at=datetime.now(timezone.utc),
            device_id="cam-front",
        )
        # First ingestion -> created
        first_result = ingestion_service.ingest_event(event_in)
        assert first_result.is_duplicate is False
        first_id = first_result.event.id

        # Second ingestion with same source and external_id -> duplicate
        second_result = ingestion_service.ingest_event(event_in)
        assert second_result.is_duplicate is True
        assert second_result.event.id == first_id

    def test_multiple_events_without_external_id_interim_policy(
        self,
        ingestion_service: EventIngestionService,
    ):
        """Under the documented interim policy, events without external_event_id

        are treated as distinct and not deduplicated.
        """
        occurred_time = datetime(2026, 10, 21, 15, 0, 0, tzinfo=timezone.utc)
        event_in1 = EventCreate(
            source="demo",
            external_event_id=None,
            event_type="doorbell_press",
            occurred_at=occurred_time,
            device_id="door-button",
        )
        event_in2 = EventCreate(
            source="demo",
            external_event_id=None,
            event_type="doorbell_press",
            occurred_at=occurred_time,
            device_id="door-button",
        )

        res1 = ingestion_service.ingest_event(event_in1)
        res2 = ingestion_service.ingest_event(event_in2)

        # Both should be persisted as distinct records
        assert res1.is_duplicate is False
        assert res2.is_duplicate is False
        assert res1.event.id != res2.event.id
