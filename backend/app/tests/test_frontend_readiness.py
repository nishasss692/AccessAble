"""Integration readiness tests for frontend compatibility, CORS, error contracts, and demo workflows."""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


class TestCORSConfiguration:
    """Verify CORS headers for frontend integration."""

    def test_cors_allowed_origin_preflight(self, client: TestClient):
        """Preflight OPTIONS request from configured origin must return CORS allow headers."""
        headers = {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
        response = client.options("/api/v1/events", headers=headers)
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
        allow_methods = response.headers.get("access-control-allow-methods", "")
        assert "POST" in allow_methods
        assert "GET" in allow_methods
        assert "PUT" in allow_methods

    def test_cors_allowed_origin_get_request(self, client: TestClient):
        """GET request from configured origin must include access-control-allow-origin."""
        headers = {"Origin": "http://localhost:5173"}
        response = client.get("/api/v1/health", headers=headers)
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"

    def test_cors_disallowed_origin_does_not_receive_allow_header(self, client: TestClient):
        """Requests from unconfigured origins must not receive access-control-allow-origin."""
        headers = {
            "Origin": "http://malicious-site.example.com",
            "Access-Control-Request-Method": "POST",
        }
        response = client.options("/api/v1/events", headers=headers)
        assert response.headers.get("access-control-allow-origin") is None


class TestFrontendRouteCoverageAndContracts:
    """Verify that all endpoints expected by the frontend exist and adhere to contracts."""

    EXPECTED_ENDPOINTS = [
        ("GET", "/api/v1/health"),
        ("POST", "/api/v1/events"),
        ("GET", "/api/v1/events"),
        ("GET", "/api/v1/preferences"),
        ("PUT", "/api/v1/preferences"),
        ("POST", "/api/v1/acknowledgements"),
        ("GET", "/api/v1/acknowledgements"),
        ("GET", "/api/v1/integrations/ring/status"),
    ]

    def test_all_expected_routes_exist_in_openapi_schema(self, client: TestClient):
        """OpenAPI JSON must register all canonical frontend integration endpoints."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        openapi = response.json()
        paths = openapi.get("paths", {})

        for method, path in self.EXPECTED_ENDPOINTS:
            assert path in paths, f"Path {path} missing from OpenAPI schema"
            method_lower = method.lower()
            assert method_lower in paths[path], f"Method {method} missing from path {path}"

    def test_empty_collection_responses_are_predictable(self, client: TestClient):
        """Empty lists must return items: [], total: 0 rather than null or missing keys."""
        # Events
        res_events = client.get("/api/v1/events")
        assert res_events.status_code == 200
        body_events = res_events.json()
        assert body_events["items"] == []
        assert body_events["total"] == 0
        assert body_events["limit"] == 20
        assert body_events["offset"] == 0

        # Acknowledgements
        res_acks = client.get("/api/v1/acknowledgements")
        assert res_acks.status_code == 200
        body_acks = res_acks.json()
        assert body_acks["items"] == []
        assert body_acks["total"] == 0
        assert body_acks["limit"] == 20
        assert body_acks["offset"] == 0


class TestFrontendErrorHandling:
    """Verify that standard error states produce frontend-consumable JSON responses."""

    def test_missing_event_returns_404_detail(self, client: TestClient):
        """Acknowledging a non-existent event must return 404 with a string detail."""
        response = client.post(
            "/api/v1/acknowledgements",
            json={"event_id": 999999, "action": "acknowledged"},
        )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], str)

    def test_duplicate_acknowledgement_returns_409_detail(self, client: TestClient):
        """Repeating an identical action on an event must return 409 Conflict with detail."""
        # Create event
        ev_res = client.post(
            "/api/v1/events",
            json={
                "source": "demo",
                "event_type": "motion",
                "occurred_at": "2026-10-21T18:00:00Z",
            },
        )
        event_id = ev_res.json()["event"]["id"]

        # First ack: 201
        ack1 = client.post(
            "/api/v1/acknowledgements",
            json={"event_id": event_id, "action": "acknowledged"},
        )
        assert ack1.status_code == 201

        # Second identical ack: 409
        ack2 = client.post(
            "/api/v1/acknowledgements",
            json={"event_id": event_id, "action": "acknowledged"},
        )
        assert ack2.status_code == 409
        data = ack2.json()
        assert "detail" in data
        assert "already been acknowledged" in data["detail"]

    def test_schema_validation_failure_returns_422_with_loc(self, client: TestClient):
        """Invalid fields return 422 with standard structured validation errors."""
        response = client.put(
            "/api/v1/preferences",
            json={"text_scale": "enormous"},
        )
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert isinstance(errors, list)
        assert any("text_scale" in e["loc"] for e in errors)

    def test_invalid_query_parameters_return_400_or_422(self, client: TestClient):
        """Invalid time range returns 400 Bad Request; invalid limit returns 422."""
        # start_time > end_time -> 400
        res_time = client.get(
            "/api/v1/events",
            params={
                "start_time": "2026-10-21T20:00:00Z",
                "end_time": "2026-10-21T10:00:00Z",
            },
        )
        assert res_time.status_code == 400
        assert "start_time cannot be later than end_time" in res_time.json()["detail"]

        # limit > 100 -> 422
        res_limit = client.get("/api/v1/events", params={"limit": 200})
        assert res_limit.status_code == 422


class TestRepeatableDemoWorkflow:
    """Verify that a frontend developer can execute a full demo workflow using documented APIs."""

    def test_full_frontend_demo_lifecycle(self, client: TestClient):
        """Simulate the 9-step demo flow a frontend developer will execute."""
        # Step 1 & 2: Verify API availability via health check
        health_res = client.get("/api/v1/health")
        assert health_res.status_code == 200
        assert health_res.json()["status"] == "ok"

        # Step 3: Ingest demo motion event with external_id
        post_res1 = client.post(
            "/api/v1/events",
            json={
                "source": "demo",
                "external_event_id": "demo-front-porch-001",
                "event_type": "motion",
                "occurred_at": "2026-10-21T19:00:00Z",
                "device_id": "demo-cam-1",
                "metadata": {"lux": 14, "simulation": True},
            },
        )
        assert post_res1.status_code == 201
        body1 = post_res1.json()
        assert body1["is_duplicate"] is False
        event_id = body1["event"]["id"]
        assert body1["event"]["source"] == "demo"

        # Resubmitting same external ID is idempotent (200 OK, is_duplicate=True)
        dup_res = client.post(
            "/api/v1/events",
            json={
                "source": "demo",
                "external_event_id": "demo-front-porch-001",
                "event_type": "motion",
                "occurred_at": "2026-10-21T19:00:00Z",
            },
        )
        assert dup_res.status_code == 200
        assert dup_res.json()["is_duplicate"] is True
        assert dup_res.json()["event"]["id"] == event_id

        # Step 4: Retrieve the event via listing
        list_res = client.get("/api/v1/events", params={"source": "demo"})
        assert list_res.status_code == 200
        items = list_res.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == event_id

        # Step 5: Acknowledge the event
        ack_res = client.post(
            "/api/v1/acknowledgements",
            json={
                "event_id": event_id,
                "action": "acknowledged",
                "note": "Demo user saw the porch light notification",
            },
        )
        assert ack_res.status_code == 201
        assert ack_res.json()["action"] == "acknowledged"

        # Transition action: dismiss the event
        dismiss_res = client.post(
            "/api/v1/acknowledgements",
            json={
                "event_id": event_id,
                "action": "dismissed",
                "note": "Alert dismissed after inspection",
            },
        )
        assert dismiss_res.status_code == 201
        assert dismiss_res.json()["action"] == "dismissed"

        # Step 6: Retrieve acknowledgement history
        hist_res = client.get("/api/v1/acknowledgements", params={"event_id": event_id})
        assert hist_res.status_code == 200
        hist_items = hist_res.json()["items"]
        assert len(hist_items) == 2
        # Deterministic ordering: newest first (dismissed, then acknowledged)
        assert hist_items[0]["action"] == "dismissed"
        assert hist_items[1]["action"] == "acknowledged"

        # Step 7: Change accessibility preferences
        pref_put_res = client.put(
            "/api/v1/preferences",
            json={
                "visual_alerts_enabled": True,
                "audio_alerts_enabled": False,
                "high_contrast_enabled": True,
                "text_scale": "large",
            },
        )
        assert pref_put_res.status_code == 200
        pref_data = pref_put_res.json()
        assert pref_data["high_contrast_enabled"] is True
        assert pref_data["audio_alerts_enabled"] is False
        assert pref_data["text_scale"] == "large"

        # Verify preferences persist
        pref_get_res = client.get("/api/v1/preferences")
        assert pref_get_res.status_code == 200
        assert pref_get_res.json()["text_scale"] == "large"

        # Step 8: View Ring integration status
        ring_res = client.get("/api/v1/integrations/ring/status")
        assert ring_res.status_code == 200
        ring_data = ring_res.json()
        assert ring_data["source"] == "ring"
        assert ring_data["status"] == "unknown"
        assert ring_data["is_connected"] is False
        assert ring_data["details"]["demo_events_supported"] is True

        # Step 9: Re-verify source separation - demo events have source "demo", not "ring"
        ring_events_res = client.get("/api/v1/events", params={"source": "ring"})
        assert ring_events_res.status_code == 200
        assert ring_events_res.json()["total"] == 0
