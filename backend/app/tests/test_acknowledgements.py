"""Automated tests for event acknowledgements and history API (Phase 5)."""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.acknowledgement import Acknowledgement
from app.models.event import Event
from app.models.user_preferences import UserPreference
from app.repositories.acknowledgement_repository import AcknowledgementRepository
from app.schemas.acknowledgement import AcknowledgementCreate
from app.services.acknowledgement_service import AcknowledgementService


def create_test_event(client: TestClient, external_id: str = "ack-test-1") -> int:
    """Helper to ingest an event and return its internal ID."""
    resp = client.post("/api/v1/events", json={
        "source": "ring",
        "external_event_id": external_id,
        "event_type": "motion",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "device_id": "cam-porch",
        "metadata": {"zone": "driveway"},
    })
    assert resp.status_code == 201
    return resp.json()["event"]["id"]


class TestCreateAcknowledgement:
    """Test suite for POST /api/v1/acknowledgements."""

    def test_create_valid_acknowledgement_returns_201(self, client: TestClient):
        event_id = create_test_event(client, "evt-valid-ack")

        payload = {
            "event_id": event_id,
            "action": "acknowledged",
            "note": "Resident checked front door camera",
        }
        resp = client.post("/api/v1/acknowledgements", json=payload)
        assert resp.status_code == 201
        data = resp.json()

        assert data["id"] is not None
        assert data["event_id"] == event_id
        assert data["action"] == "acknowledged"
        assert data["note"] == "Resident checked front door camera"
        assert "acknowledged_at" in data
        assert data["event"] is not None
        assert data["event"]["id"] == event_id
        assert data["event"]["source"] == "ring"

    def test_nonexistent_event_returns_404(self, client: TestClient):
        payload = {
            "event_id": 999999,
            "action": "acknowledged",
        }
        resp = client.post("/api/v1/acknowledgements", json=payload)
        assert resp.status_code == 404
        assert "does not exist" in resp.json()["detail"].lower()

    def test_duplicate_action_returns_409_conflict(self, client: TestClient):
        event_id = create_test_event(client, "evt-dup-action")

        payload = {
            "event_id": event_id,
            "action": "acknowledged",
        }
        # First call succeeds
        r1 = client.post("/api/v1/acknowledgements", json=payload)
        assert r1.status_code == 201

        # Second identical call raises 409 Conflict
        r2 = client.post("/api/v1/acknowledgements", json=payload)
        assert r2.status_code == 409
        assert "already been acknowledged" in r2.json()["detail"].lower()

    def test_transition_action_creates_new_history_record(
        self,
        client: TestClient,
        db_session: Session,
    ):
        event_id = create_test_event(client, "evt-state-transition")

        # 1. Acknowledge
        r1 = client.post("/api/v1/acknowledgements", json={
            "event_id": event_id,
            "action": "acknowledged",
            "note": "First action",
        })
        assert r1.status_code == 201

        # 2. Dismiss
        r2 = client.post("/api/v1/acknowledgements", json={
            "event_id": event_id,
            "action": "dismissed",
            "note": "Second action",
        })
        assert r2.status_code == 201

        # 3. Both actions are preserved in history
        history_resp = client.get(f"/api/v1/acknowledgements?event_id={event_id}")
        assert history_resp.status_code == 200
        items = history_resp.json()["items"]
        assert len(items) == 2
        assert items[0]["action"] == "dismissed"
        assert items[1]["action"] == "acknowledged"

    def test_invalid_action_rejected(self, client: TestClient):
        event_id = create_test_event(client, "evt-bad-action")
        resp = client.post("/api/v1/acknowledgements", json={
            "event_id": event_id,
            "action": "invalid_action",
        })
        assert resp.status_code == 422

    def test_invalid_event_id_rejected(self, client: TestClient):
        resp = client.post("/api/v1/acknowledgements", json={
            "event_id": 0,
            "action": "acknowledged",
        })
        assert resp.status_code == 422


class TestListAcknowledgements:
    """Test suite for GET /api/v1/acknowledgements."""

    def test_empty_database_returns_empty_items(self, client: TestClient):
        resp = client.get("/api/v1/acknowledgements")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["limit"] == 20
        assert data["offset"] == 0

    def test_filter_by_event_id_and_action(self, client: TestClient):
        e1 = create_test_event(client, "filter-evt-1")
        e2 = create_test_event(client, "filter-evt-2")

        client.post("/api/v1/acknowledgements", json={"event_id": e1, "action": "acknowledged"})
        client.post("/api/v1/acknowledgements", json={"event_id": e2, "action": "dismissed"})

        # Filter by event_id
        r_e1 = client.get(f"/api/v1/acknowledgements?event_id={e1}")
        assert r_e1.json()["total"] == 1
        assert r_e1.json()["items"][0]["event_id"] == e1

        # Filter by action
        r_dismissed = client.get("/api/v1/acknowledgements?action=dismissed")
        assert r_dismissed.json()["total"] == 1
        assert r_dismissed.json()["items"][0]["action"] == "dismissed"

    def test_deterministic_ordering(self, client: TestClient):
        e1 = create_test_event(client, "ord-1")
        e2 = create_test_event(client, "ord-2")
        e3 = create_test_event(client, "ord-3")

        r1 = client.post("/api/v1/acknowledgements", json={"event_id": e1, "action": "acknowledged"})
        r2 = client.post("/api/v1/acknowledgements", json={"event_id": e2, "action": "acknowledged"})
        r3 = client.post("/api/v1/acknowledgements", json={"event_id": e3, "action": "acknowledged"})

        id1, id2, id3 = r1.json()["id"], r2.json()["id"], r3.json()["id"]

        list_resp = client.get("/api/v1/acknowledgements")
        ids = [item["id"] for item in list_resp.json()["items"]]
        # Newest first
        assert ids == [id3, id2, id1]

    def test_pagination(self, client: TestClient):
        event_ids = [create_test_event(client, f"page-evt-{i}") for i in range(5)]
        for eid in event_ids:
            client.post("/api/v1/acknowledgements", json={"event_id": eid, "action": "acknowledged"})

        # Page 1: limit 2, offset 0
        p1 = client.get("/api/v1/acknowledgements?limit=2&offset=0")
        assert p1.json()["total"] == 5
        assert len(p1.json()["items"]) == 2

        # Page 2: limit 2, offset 2
        p2 = client.get("/api/v1/acknowledgements?limit=2&offset=2")
        assert p2.json()["total"] == 5
        assert len(p2.json()["items"]) == 2

        # Page 3: limit 2, offset 4
        p3 = client.get("/api/v1/acknowledgements?limit=2&offset=4")
        assert p3.json()["total"] == 5
        assert len(p3.json()["items"]) == 1

        p1_ids = {a["id"] for a in p1.json()["items"]}
        p2_ids = {a["id"] for a in p2.json()["items"]}
        p3_ids = {a["id"] for a in p3.json()["items"]}
        assert p1_ids.isdisjoint(p2_ids)
        assert p2_ids.isdisjoint(p3_ids)

    def test_coexistence_with_events_and_preferences(
        self,
        client: TestClient,
        db_session: Session,
    ):
        # Ingest event
        eid = create_test_event(client, "coexist-evt")
        # Update preferences
        client.put("/api/v1/preferences", json={
            "visual_alerts_enabled": True,
            "audio_alerts_enabled": True,
            "high_contrast_enabled": True,
            "text_scale": "large",
        })
        # Acknowledge event
        client.post("/api/v1/acknowledgements", json={"event_id": eid, "action": "acknowledged"})

        # Verify all tables exist and have their records
        assert len(db_session.scalars(select(Event)).all()) >= 1
        assert len(db_session.scalars(select(UserPreference)).all()) == 1
        assert len(db_session.scalars(select(Acknowledgement)).all()) >= 1

    def test_persistence_failure_handling(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ):
        from sqlalchemy.exc import OperationalError

        eid = create_test_event(client, "fail-evt")

        def faulty_create(self, ack):
            self.db.rollback()
            raise OperationalError("simulated error", params={}, orig=Exception("disk error"))

        monkeypatch.setattr(AcknowledgementRepository, "create", faulty_create)

        resp = client.post("/api/v1/acknowledgements", json={"event_id": eid, "action": "acknowledged"})
        assert resp.status_code == 500
        assert "unexpected error" in resp.json()["detail"].lower()
