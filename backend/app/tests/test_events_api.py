"""API integration tests for Event ingestion and listing endpoints."""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.event import Event
from app.repositories.event_repository import EventRepository


class TestPostEventsEndpoint:
    """Test suite for POST /api/v1/events."""

    def test_post_valid_event_returns_201_and_persists(self, client: TestClient):
        payload = {
            "source": "ring",
            "external_event_id": "ext-test-1",
            "event_type": "motion",
            "occurred_at": "2026-10-21T12:00:00Z",
            "device_id": "cam-101",
            "metadata": {"zone": "front"},
        }
        response = client.post("/api/v1/events", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["is_duplicate"] is False
        event = data["event"]
        assert event["id"] is not None
        assert event["source"] == "ring"
        assert event["external_event_id"] == "ext-test-1"
        assert event["event_type"] == "motion"
        assert event["metadata"] == {"zone": "front"}

        # Subsequent GET retrieves the event
        get_resp = client.get("/api/v1/events")
        assert get_resp.status_code == 200
        items = get_resp.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == event["id"]

    def test_reposting_same_event_returns_200_duplicate(self, client: TestClient):
        payload = {
            "source": "ring",
            "external_event_id": "ext-dup-unique",
            "event_type": "doorbell_press",
            "occurred_at": "2026-10-21T12:00:00Z",
            "device_id": "doorbell-1",
        }
        # First post -> 201 Created
        resp1 = client.post("/api/v1/events", json=payload)
        assert resp1.status_code == 201
        orig_id = resp1.json()["event"]["id"]
        assert resp1.json()["is_duplicate"] is False

        # Duplicate post -> 200 OK
        resp2 = client.post("/api/v1/events", json=payload)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["is_duplicate"] is True
        assert data2["event"]["id"] == orig_id

        # Verify no duplicate database row was created
        list_resp = client.get("/api/v1/events")
        assert list_resp.json()["total"] == 1

    def test_events_with_null_external_id_treated_as_distinct(self, client: TestClient):
        payload = {
            "source": "demo",
            "external_event_id": None,
            "event_type": "chime",
            "occurred_at": "2026-10-21T12:00:00Z",
            "device_id": None,
            "metadata": {},
        }
        # First post
        r1 = client.post("/api/v1/events", json=payload)
        assert r1.status_code == 201
        assert r1.json()["is_duplicate"] is False

        # Second post with null external ID -> also 201 distinct event
        r2 = client.post("/api/v1/events", json=payload)
        assert r2.status_code == 201
        assert r2.json()["is_duplicate"] is False
        assert r1.json()["event"]["id"] != r2.json()["event"]["id"]

        # Total count should be 2
        list_resp = client.get("/api/v1/events")
        assert list_resp.json()["total"] == 2

    def test_missing_required_fields_returns_422(self, client: TestClient):
        # Missing source
        r1 = client.post("/api/v1/events", json={
            "event_type": "motion",
            "occurred_at": "2026-10-21T12:00:00Z",
        })
        assert r1.status_code == 422

        # Missing event_type
        r2 = client.post("/api/v1/events", json={
            "source": "ring",
            "occurred_at": "2026-10-21T12:00:00Z",
        })
        assert r2.status_code == 422

        # Missing occurred_at
        r3 = client.post("/api/v1/events", json={
            "source": "ring",
            "event_type": "motion",
        })
        assert r3.status_code == 422

    def test_empty_source_or_event_type_returns_422(self, client: TestClient):
        r1 = client.post("/api/v1/events", json={
            "source": "   ",
            "event_type": "motion",
            "occurred_at": "2026-10-21T12:00:00Z",
        })
        assert r1.status_code == 422

        r2 = client.post("/api/v1/events", json={
            "source": "ring",
            "event_type": "",
            "occurred_at": "2026-10-21T12:00:00Z",
        })
        assert r2.status_code == 422

    def test_invalid_timestamps_return_422(self, client: TestClient):
        r = client.post("/api/v1/events", json={
            "source": "ring",
            "event_type": "motion",
            "occurred_at": "not-a-timestamp",
        })
        assert r.status_code == 422

    def test_persistence_failure_leaves_session_intact(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ):
        from app.repositories.event_repository import EventRepository
        from sqlalchemy.exc import OperationalError

        # Simulate a transient operational failure on create
        def faulty_create(self, event):
            self.db.rollback()
            raise OperationalError("simulated error", params={}, orig=Exception("disk error"))

        monkeypatch.setattr(EventRepository, "create", faulty_create)

        r = client.post("/api/v1/events", json={
            "source": "ring",
            "event_type": "motion",
            "occurred_at": "2026-10-21T12:00:00Z",
        })
        assert r.status_code == 500
        assert "unexpected error" in r.json()["detail"].lower()


class TestGetEventsEndpoint:
    """Test suite for GET /api/v1/events."""

    def test_empty_database_returns_empty_items_and_total_zero(self, client: TestClient):
        response = client.get("/api/v1/events")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["limit"] == 20
        assert data["offset"] == 0

    def test_list_events_and_filtering(self, client: TestClient):
        base_time = datetime(2026, 10, 21, 10, 0, 0, tzinfo=timezone.utc)

        # Ingest 3 distinct events
        client.post("/api/v1/events", json={
            "source": "ring",
            "external_event_id": "r1",
            "event_type": "motion",
            "occurred_at": (base_time + timedelta(minutes=10)).isoformat(),
        })
        client.post("/api/v1/events", json={
            "source": "ring",
            "external_event_id": "r2",
            "event_type": "doorbell_press",
            "occurred_at": (base_time + timedelta(minutes=20)).isoformat(),
        })
        client.post("/api/v1/events", json={
            "source": "demo",
            "external_event_id": "d1",
            "event_type": "motion",
            "occurred_at": (base_time + timedelta(minutes=30)).isoformat(),
        })

        # List all
        all_res = client.get("/api/v1/events")
        assert all_res.json()["total"] == 3
        assert len(all_res.json()["items"]) == 3

        # Filter by source
        ring_res = client.get("/api/v1/events?source=ring")
        assert ring_res.json()["total"] == 2
        for item in ring_res.json()["items"]:
            assert item["source"] == "ring"

        # Filter by event_type
        press_res = client.get("/api/v1/events?event_type=doorbell_press")
        assert press_res.json()["total"] == 1
        assert press_res.json()["items"][0]["event_type"] == "doorbell_press"

        # Filter by source AND event_type
        combo_res = client.get("/api/v1/events?source=demo&event_type=motion")
        assert combo_res.json()["total"] == 1
        assert combo_res.json()["items"][0]["source"] == "demo"

    def test_time_range_filtering_including_boundaries(self, client: TestClient):
        t1 = datetime(2026, 10, 21, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 10, 21, 11, 0, 0, tzinfo=timezone.utc)
        t3 = datetime(2026, 10, 21, 12, 0, 0, tzinfo=timezone.utc)

        for i, t in enumerate([t1, t2, t3], start=1):
            client.post("/api/v1/events", json={
                "source": "ring",
                "external_event_id": f"time-{i}",
                "event_type": "motion",
                "occurred_at": t.isoformat(),
            })

        # Filter t1 to t2 inclusive
        r_range = client.get(
            "/api/v1/events",
            params={"start_time": t1.isoformat(), "end_time": t2.isoformat()},
        )
        assert r_range.json()["total"] == 2

        # Filter exact single boundary point
        r_single = client.get(
            "/api/v1/events",
            params={"start_time": t2.isoformat(), "end_time": t2.isoformat()},
        )
        assert r_single.json()["total"] == 1
        assert r_single.json()["items"][0]["external_event_id"] == "time-2"

    def test_start_time_after_end_time_returns_400(self, client: TestClient):
        t_early = "2026-10-21T10:00:00Z"
        t_late = "2026-10-21T12:00:00Z"
        # start_time later than end_time
        res = client.get(f"/api/v1/events?start_time={t_late}&end_time={t_early}")
        assert res.status_code == 400
        assert "start_time cannot be later than end_time" in res.json()["detail"]

    def test_pagination_limit_and_offset(self, client: TestClient):
        base_time = datetime(2026, 10, 21, 10, 0, 0, tzinfo=timezone.utc)
        for i in range(5):
            client.post("/api/v1/events", json={
                "source": "ring",
                "external_event_id": f"page-{i}",
                "event_type": "motion",
                "occurred_at": (base_time + timedelta(minutes=i)).isoformat(),
            })

        # Page 1: limit 2, offset 0
        p1 = client.get("/api/v1/events?limit=2&offset=0")
        assert p1.json()["total"] == 5
        assert len(p1.json()["items"]) == 2

        # Page 2: limit 2, offset 2
        p2 = client.get("/api/v1/events?limit=2&offset=2")
        assert p2.json()["total"] == 5
        assert len(p2.json()["items"]) == 2

        # Page 3: limit 2, offset 4
        p3 = client.get("/api/v1/events?limit=2&offset=4")
        assert p3.json()["total"] == 5
        assert len(p3.json()["items"]) == 1

        # Items across pages must not overlap
        p1_ids = {e["id"] for e in p1.json()["items"]}
        p2_ids = {e["id"] for e in p2.json()["items"]}
        p3_ids = {e["id"] for e in p3.json()["items"]}
        assert p1_ids.isdisjoint(p2_ids)
        assert p2_ids.isdisjoint(p3_ids)

    def test_invalid_limit_and_offset_rejected(self, client: TestClient):
        # limit < 1
        r1 = client.get("/api/v1/events?limit=0")
        assert r1.status_code == 422

        # limit > 100
        r2 = client.get("/api/v1/events?limit=101")
        assert r2.status_code == 422

        # offset < 0
        r3 = client.get("/api/v1/events?offset=-1")
        assert r3.status_code == 422

    def test_deterministic_ordering_for_equal_timestamps(self, client: TestClient):
        fixed_time = "2026-10-21T10:00:00Z"
        # Ingest 3 events with identical occurred_at
        r1 = client.post("/api/v1/events", json={
            "source": "ring",
            "external_event_id": "eq-1",
            "event_type": "motion",
            "occurred_at": fixed_time,
        })
        r2 = client.post("/api/v1/events", json={
            "source": "ring",
            "external_event_id": "eq-2",
            "event_type": "motion",
            "occurred_at": fixed_time,
        })
        r3 = client.post("/api/v1/events", json={
            "source": "ring",
            "external_event_id": "eq-3",
            "event_type": "motion",
            "occurred_at": fixed_time,
        })
        id1, id2, id3 = r1.json()["event"]["id"], r2.json()["event"]["id"], r3.json()["event"]["id"]

        list_resp = client.get("/api/v1/events")
        items = list_resp.json()["items"]
        # Expected order: newest first (id3, then id2, then id1)
        item_ids = [e["id"] for e in items]
        assert item_ids == [id3, id2, id1]
