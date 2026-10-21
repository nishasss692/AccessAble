"""Automated tests for Ring integration status API and adapter (Phase 6)."""

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
from app.repositories.connection_repository import ConnectionRepository


class TestRingAdapterUnit:
    """Unit tests for RingAdapter state probing."""

    def test_default_probe_status_is_unknown(self):
        adapter = RingAdapter()
        probed = adapter.probe_status()

        assert probed["status"] == "unknown"
        assert probed["is_connected"] is False
        assert probed["error_message"] is None
        assert probed["details"]["mode"] == "unconfigured"
        assert "password" not in str(probed)
        assert "token" not in str(probed)

    def test_probe_forced_states(self):
        # Connected state
        adapter_conn = RingAdapter(forced_status="connected")
        assert adapter_conn.probe_status()["status"] == "connected"
        assert adapter_conn.probe_status()["is_connected"] is True

        # Disconnected state
        adapter_disc = RingAdapter(forced_status="disconnected")
        assert adapter_disc.probe_status()["status"] == "disconnected"
        assert adapter_disc.probe_status()["is_connected"] is False

        # Error state
        adapter_err = RingAdapter(forced_status="error", forced_error="Upstream unreachable")
        err_probe = adapter_err.probe_status()
        assert err_probe["status"] == "error"
        assert err_probe["is_connected"] is False
        assert err_probe["error_message"] == "Upstream unreachable"


class TestRingStatusAPI:
    """Integration tests for GET /api/v1/integrations/ring/status."""

    def test_get_ring_status_returns_default_unknown_state(self, client: TestClient):
        response = client.get("/api/v1/integrations/ring/status")
        assert response.status_code == 200
        data = response.json()

        assert data["source"] == "ring"
        assert data["status"] == "unknown"
        assert data["is_connected"] is False
        assert data["error_message"] is None
        assert "mode" in data["details"]
        assert "last_checked_at" in data

    def test_ring_status_persistence(
        self,
        client: TestClient,
        db_session: Session,
    ):
        # Initial call creates record
        r1 = client.get("/api/v1/integrations/ring/status")
        assert r1.status_code == 200

        # Verify record exists in database
        records = db_session.scalars(select(SourceConnection).where(SourceConnection.source == "ring")).all()
        assert len(records) == 1
        assert records[0].status == "unknown"

        # Subsequent call retrieves the record
        r2 = client.get("/api/v1/integrations/ring/status")
        assert r2.status_code == 200
        assert r2.json()["status"] == "unknown"

    def test_ring_status_connected_state_override(self, client: TestClient):
        def override_adapter():
            return RingAdapter(forced_status="connected", forced_details={"devices": 2})

        app.dependency_overrides[get_ring_adapter] = override_adapter
        try:
            resp = client.get("/api/v1/integrations/ring/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "connected"
            assert data["is_connected"] is True
            assert data["details"]["devices"] == 2
        finally:
            app.dependency_overrides.pop(get_ring_adapter, None)

    def test_ring_status_error_state_override(self, client: TestClient):
        def override_adapter():
            return RingAdapter(forced_status="error", forced_error="Device offline")

        app.dependency_overrides[get_ring_adapter] = override_adapter
        try:
            resp = client.get("/api/v1/integrations/ring/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "error"
            assert data["is_connected"] is False
            assert data["error_message"] == "Device offline"
        finally:
            app.dependency_overrides.pop(get_ring_adapter, None)

    def test_all_four_database_tables_coexist(
        self,
        client: TestClient,
        db_session: Session,
    ):
        # Ingest event
        evt_resp = client.post("/api/v1/events", json={
            "source": "ring",
            "external_event_id": "coexist-evt-ring",
            "event_type": "motion",
            "occurred_at": "2026-10-21T12:00:00Z",
        })
        evt_id = evt_resp.json()["event"]["id"]

        # Acknowledge event
        client.post("/api/v1/acknowledgements", json={
            "event_id": evt_id,
            "action": "acknowledged",
        })

        # Update preferences
        client.put("/api/v1/preferences", json={
            "visual_alerts_enabled": True,
            "audio_alerts_enabled": True,
            "high_contrast_enabled": True,
            "text_scale": "medium",
        })

        # Check ring status
        client.get("/api/v1/integrations/ring/status")

        # Verify all four tables have records
        assert len(db_session.scalars(select(Event)).all()) >= 1
        assert len(db_session.scalars(select(Acknowledgement)).all()) >= 1
        assert len(db_session.scalars(select(UserPreference)).all()) >= 1
        assert len(db_session.scalars(select(SourceConnection)).all()) >= 1
