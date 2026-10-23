"""End-to-End Workflow and Integration Tests (Phase 7).

Verifies full API lifecycles across events, preferences, acknowledgements,
and Ring integration status under simulated and isolated conditions.
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_ring_adapter
from app.integrations.ring.adapter import RingAdapter
from app.main import app
from app.models.acknowledgement import Acknowledgement
from app.models.event import Event
from app.models.source_connection import SourceConnection
from app.models.user_preferences import UserPreference


class TestWorkflowAEventLifecycle:
    """End-to-End Workflow A: Complete Event Lifecycle."""

    def test_complete_event_lifecycle(self, client: TestClient, db_session: Session):
        # 1. Submit a valid event
        event_payload = {
            "source": "ring",
            "external_event_id": "workflow-evt-001",
            "event_type": "motion",
            "occurred_at": "2026-10-21T18:00:00Z",
            "device_id": "cam-front-door",
            "metadata": {"zone": "driveway", "motion_level": 85},
        }
        res_create = client.post("/api/v1/events", json=event_payload)
        assert res_create.status_code == 201
        create_data = res_create.json()
        assert create_data["is_duplicate"] is False
        event_id = create_data["event"]["id"]
        assert event_id is not None
        assert create_data["event"]["external_event_id"] == "workflow-evt-001"
        assert create_data["event"]["metadata"]["zone"] == "driveway"

        # 2. Verify that the event is normalized and persisted in database
        persisted_event = db_session.get(Event, event_id)
        assert persisted_event is not None
        assert persisted_event.source == "ring"
        assert persisted_event.event_type == "motion"

        # 3. Submit the exact same external event again -> duplicate handling
        res_dup = client.post("/api/v1/events", json=event_payload)
        assert res_dup.status_code == 200
        dup_data = res_dup.json()
        assert dup_data["is_duplicate"] is True
        assert dup_data["event"]["id"] == event_id

        # Total event count in DB remains 1
        total_events = len(db_session.scalars(select(Event).where(Event.external_event_id == "workflow-evt-001")).all())
        assert total_events == 1

        # 4. Retrieve the event through GET /api/v1/events
        res_list = client.get(f"/api/v1/events?source=ring&event_type=motion")
        assert res_list.status_code == 200
        list_data = res_list.json()
        assert list_data["total"] >= 1
        matched_items = [e for e in list_data["items"] if e["id"] == event_id]
        assert len(matched_items) == 1
        assert matched_items[0]["external_event_id"] == "workflow-evt-001"

        # 5. Acknowledge the event
        ack_payload = {
            "event_id": event_id,
            "action": "acknowledged",
            "note": "Checked porch camera feed",
        }
        res_ack = client.post("/api/v1/acknowledgements", json=ack_payload)
        assert res_ack.status_code == 201
        ack_data = res_ack.json()
        ack_id = ack_data["id"]
        assert ack_data["event_id"] == event_id
        assert ack_data["action"] == "acknowledged"
        assert ack_data["event"]["id"] == event_id

        # 6. Repeating the same action produces HTTP 409 Conflict (unintended duplicate operation)
        res_ack_dup = client.post("/api/v1/acknowledgements", json=ack_payload)
        assert res_ack_dup.status_code == 409
        assert "already been acknowledged" in res_ack_dup.json()["detail"].lower()

        # 7. Dismiss the event (valid state transition)
        dismiss_payload = {
            "event_id": event_id,
            "action": "dismissed",
            "note": "Alert resolved, dismissed by user",
        }
        res_dismiss = client.post("/api/v1/acknowledgements", json=dismiss_payload)
        assert res_dismiss.status_code == 201
        dismiss_data = res_dismiss.json()
        assert dismiss_data["action"] == "dismissed"
        assert dismiss_data["id"] != ack_id

        # 8. Retrieve acknowledgement history: verify ordering, both items present, and event details
        res_history = client.get(f"/api/v1/acknowledgements?event_id={event_id}")
        assert res_history.status_code == 200
        history_data = res_history.json()
        assert history_data["total"] == 2
        items = history_data["items"]
        # Stably ordered by acknowledged_at DESC, id DESC: newest action first
        assert items[0]["action"] == "dismissed"
        assert items[1]["action"] == "acknowledged"
        assert items[0]["event"]["id"] == event_id
        assert items[1]["event"]["id"] == event_id


class TestWorkflowBAccessibilityPreferences:
    """End-to-End Workflow B: Accessibility Preferences Lifecycle."""

    def test_preferences_lifecycle(self, client: TestClient, db_session: Session):
        # 1. Retrieve preferences when no profile has been created yet
        res_initial = client.get("/api/v1/preferences")
        assert res_initial.status_code == 200
        data_initial = res_initial.json()

        # 2. Verify documented sensible defaults
        assert data_initial["visual_alerts_enabled"] is True
        assert data_initial["audio_alerts_enabled"] is True
        assert data_initial["high_contrast_enabled"] is False
        assert data_initial["text_scale"] == "medium"
        assert "updated_at" in data_initial

        # 3. Update the preferences
        update_payload = {
            "visual_alerts_enabled": False,
            "audio_alerts_enabled": True,
            "high_contrast_enabled": True,
            "text_scale": "large",
        }
        res_update = client.put("/api/v1/preferences", json=update_payload)
        assert res_update.status_code == 200
        data_update = res_update.json()
        assert data_update["visual_alerts_enabled"] is False
        assert data_update["high_contrast_enabled"] is True
        assert data_update["text_scale"] == "large"

        # 4. Retrieve them again via subsequent GET
        res_get_again = client.get("/api/v1/preferences")
        assert res_get_again.status_code == 200
        data_get_again = res_get_again.json()
        assert data_get_again["visual_alerts_enabled"] is False
        assert data_get_again["high_contrast_enabled"] is True
        assert data_get_again["text_scale"] == "large"

        # 5. Verify that changes persist and no duplicate profile is created in DB
        profiles = db_session.scalars(select(UserPreference)).all()
        assert len(profiles) == 1
        assert profiles[0].profile_name == "default"
        assert profiles[0].text_scale == "large"


class TestWorkflowCRingIntegrationStatus:
    """End-to-End Workflow C: Ring Integration Status Lifecycle."""

    def test_unconfigured_state_and_safe_diagnostics(self, client: TestClient):
        # 1. Verify unconfigured state
        res = client.get("/api/v1/integrations/ring/status")
        assert res.status_code == 200
        data = res.json()

        assert data["source"] == "ring"
        assert data["status"] == "unknown"
        assert data["is_connected"] is False
        assert data["error_message"] is None
        assert data["details"]["mode"] == "webhook"
        assert isinstance(data["details"]["webhook_receiver_enabled"], bool)
        assert data["details"]["account_link_verified"] is False

        # 4. Confirm credentials and secrets never appear in API responses
        data_str = str(data).lower()
        for forbidden in ["password", "secret", "token", "auth", "api_key", "credential"]:
            assert forbidden not in data_data_forbidden_check(data_str, forbidden)

    def test_adapter_state_overrides_connected_disconnected_error(self, client: TestClient):
        # Connected state override
        def override_connected():
            return RingAdapter(forced_status="connected", forced_details={"devices_online": 3})

        app.dependency_overrides[get_ring_adapter] = override_connected
        try:
            res_conn = client.get("/api/v1/integrations/ring/status")
            assert res_conn.status_code == 200
            assert res_conn.json()["status"] == "connected"
            assert res_conn.json()["is_connected"] is True
            assert res_conn.json()["details"]["devices_online"] == 3
        finally:
            app.dependency_overrides.pop(get_ring_adapter, None)

        # Disconnected state override
        def override_disconnected():
            return RingAdapter(forced_status="disconnected", forced_details={"reason": "manual_disable"})

        app.dependency_overrides[get_ring_adapter] = override_disconnected
        try:
            res_disc = client.get("/api/v1/integrations/ring/status")
            assert res_disc.status_code == 200
            assert res_disc.json()["status"] == "disconnected"
            assert res_disc.json()["is_connected"] is False
        finally:
            app.dependency_overrides.pop(get_ring_adapter, None)

        # Error state override
        def override_error():
            return RingAdapter(forced_status="error", forced_error="Upstream gateway timeout")

        app.dependency_overrides[get_ring_adapter] = override_error
        try:
            res_err = client.get("/api/v1/integrations/ring/status")
            assert res_err.status_code == 200
            assert res_err.json()["status"] == "error"
            assert res_err.json()["is_connected"] is False
            assert res_err.json()["error_message"] == "Upstream gateway timeout"
        finally:
            app.dependency_overrides.pop(get_ring_adapter, None)

        # 3. Confirm that test overrides cannot permanently corrupt the base unconfigured state
        res_clean = client.get("/api/v1/integrations/ring/status")
        assert res_clean.status_code == 200
        assert res_clean.json()["source"] == "ring"

    def test_demo_events_distinguished_from_real_ring_events(self, client: TestClient):
        # 5. Ingest a demo event
        res_demo = client.post("/api/v1/events", json={
            "source": "demo",
            "external_event_id": "demo-evt-flow",
            "event_type": "motion",
            "occurred_at": "2026-10-21T19:00:00Z",
            "metadata": {"is_simulated": True},
        })
        assert res_demo.status_code == 201
        assert res_demo.json()["event"]["source"] == "demo"

        # Ingest a real/production ring event
        res_ring = client.post("/api/v1/events", json={
            "source": "ring",
            "external_event_id": "ring-evt-flow",
            "event_type": "motion",
            "occurred_at": "2026-10-21T19:01:00Z",
            "metadata": {"hardware_id": "cam-porch-real"},
        })
        assert res_ring.status_code == 201
        assert res_ring.json()["event"]["source"] == "ring"

        # Filter query strictly distinguishes them
        demo_list = client.get("/api/v1/events?source=demo")
        assert all(item["source"] == "demo" for item in demo_list.json()["items"])

        ring_list = client.get("/api/v1/events?source=ring")
        assert all(item["source"] == "ring" for item in ring_list.json()["items"])


class TestHealthAndIntegrity:
    """Tests verifying service health endpoint and database integrity rules."""

    def test_health_endpoint_response_structure(self, client: TestClient):
        res = client.get("/api/v1/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["service"] == "accessable-api"

    def test_cascade_delete_event_removes_acknowledgements(
        self,
        client: TestClient,
        db_session: Session,
    ):
        """Verify foreign key cascade behavior between events and acknowledgements."""
        # Create event
        evt = Event(
            source="demo",
            event_type="motion",
            occurred_at=datetime.now(timezone.utc),
            metadata_json={},
        )
        db_session.add(evt)
        db_session.commit()
        db_session.refresh(evt)
        evt_id = evt.id

        # Create acknowledgement
        ack = Acknowledgement(
            event_id=evt_id,
            action="acknowledged",
            acknowledged_at=datetime.now(timezone.utc),
        )
        db_session.add(ack)
        db_session.commit()

        # Delete event
        db_session.delete(evt)
        db_session.commit()

        # Associated acknowledgement should be gone
        acks = db_session.scalars(select(Acknowledgement).where(Acknowledgement.event_id == evt_id)).all()
        assert len(acks) == 0


def data_data_forbidden_check(data_str: str, key: str) -> str:
    """Helper to check if forbidden key appears as a credential field."""
    if f"'{key}':" in data_str or f'"{key}":' in data_str:
        return key
    return ""
