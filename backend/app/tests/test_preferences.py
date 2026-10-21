"""Automated tests for accessibility preferences (Phase 4)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.user_preferences import UserPreference
from app.repositories.preferences_repository import PreferencesRepository
from app.schemas.preferences import PreferencesUpdate
from app.services.preference_service import PreferenceService


class TestPreferencesAPI:
    """Integration test suite for /api/v1/preferences endpoints."""

    def test_get_returns_defaults_when_empty(self, client: TestClient):
        response = client.get("/api/v1/preferences")
        assert response.status_code == 200
        data = response.json()

        # Documented sensible defaults
        assert data["visual_alerts_enabled"] is True
        assert data["audio_alerts_enabled"] is True
        assert data["high_contrast_enabled"] is False
        assert data["text_scale"] == "medium"
        assert "updated_at" in data

    def test_put_saves_valid_preferences(self, client: TestClient):
        payload = {
            "visual_alerts_enabled": False,
            "audio_alerts_enabled": True,
            "high_contrast_enabled": True,
            "text_scale": "large",
        }
        put_resp = client.put("/api/v1/preferences", json=payload)
        assert put_resp.status_code == 200
        data = put_resp.json()

        assert data["visual_alerts_enabled"] is False
        assert data["audio_alerts_enabled"] is True
        assert data["high_contrast_enabled"] is True
        assert data["text_scale"] == "large"
        assert "updated_at" in data

    def test_get_returns_values_saved_by_put(self, client: TestClient):
        payload = {
            "visual_alerts_enabled": False,
            "audio_alerts_enabled": False,
            "high_contrast_enabled": True,
            "text_scale": "small",
        }
        client.put("/api/v1/preferences", json=payload)

        get_resp = client.get("/api/v1/preferences")
        assert get_resp.status_code == 200
        data = get_resp.json()

        assert data["visual_alerts_enabled"] is False
        assert data["audio_alerts_enabled"] is False
        assert data["high_contrast_enabled"] is True
        assert data["text_scale"] == "small"

    def test_second_put_updates_existing_record_without_duplication(
        self,
        client: TestClient,
        db_session: Session,
    ):
        first_payload = {
            "visual_alerts_enabled": True,
            "audio_alerts_enabled": True,
            "high_contrast_enabled": False,
            "text_scale": "medium",
        }
        r1 = client.put("/api/v1/preferences", json=first_payload)
        assert r1.status_code == 200

        second_payload = {
            "visual_alerts_enabled": False,
            "audio_alerts_enabled": False,
            "high_contrast_enabled": True,
            "text_scale": "large",
        }
        r2 = client.put("/api/v1/preferences", json=second_payload)
        assert r2.status_code == 200
        assert r2.json()["text_scale"] == "large"

        # Verify database has exactly 1 preference record
        all_records = db_session.scalars(select(UserPreference)).all()
        assert len(all_records) == 1
        assert all_records[0].text_scale == "large"
        assert all_records[0].high_contrast_enabled is True

    def test_invalid_text_scale_rejected(self, client: TestClient):
        invalid_payload = {
            "visual_alerts_enabled": True,
            "audio_alerts_enabled": True,
            "high_contrast_enabled": False,
            "text_scale": "huge",  # Unsupported
        }
        response = client.put("/api/v1/preferences", json=invalid_payload)
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("text_scale" in str(err["loc"]) for err in errors)

    def test_invalid_boolean_values_rejected(self, client: TestClient):
        invalid_payload = {
            "visual_alerts_enabled": "not-a-bool",
            "audio_alerts_enabled": True,
            "high_contrast_enabled": False,
            "text_scale": "medium",
        }
        response = client.put("/api/v1/preferences", json=invalid_payload)
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("visual_alerts_enabled" in str(err["loc"]) for err in errors)

    def test_tables_coexist_correctly(
        self,
        client: TestClient,
        db_session: Session,
    ):
        # 1. Ingest an event
        client.post("/api/v1/events", json={
            "source": "ring",
            "external_event_id": "pref-test-evt-1",
            "event_type": "motion",
            "occurred_at": "2026-10-21T12:00:00Z",
        })

        # 2. Update preferences
        client.put("/api/v1/preferences", json={
            "visual_alerts_enabled": True,
            "audio_alerts_enabled": True,
            "high_contrast_enabled": True,
            "text_scale": "large",
        })

        # 3. Verify both tables contain their respective records
        event_count = len(db_session.scalars(select(Event)).all())
        pref_count = len(db_session.scalars(select(UserPreference)).all())

        assert event_count == 1
        assert pref_count == 1

    def test_existing_event_api_and_health_remain_unaffected(self, client: TestClient):
        # Health check
        h_resp = client.get("/api/v1/health")
        assert h_resp.status_code == 200
        assert h_resp.json()["status"] == "ok"

        # Events list
        e_resp = client.get("/api/v1/events")
        assert e_resp.status_code == 200
        assert "items" in e_resp.json()
