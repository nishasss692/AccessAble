"""Signature, normalization, persistence, and idempotency tests for Ring webhooks."""

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.main import app
from app.models.event import Event
from app.integrations.ring.webhook import normalize_webhook, verify_signature

TEST_KEY = "synthetic-ring-signing-key"


def ring_payload(**overrides):
    payload = {
        "meta": {
            "version": "1.1",
            "time": "2026-10-21T12:30:00Z",
            "request_id": "request-123",
            "account_id": "synthetic-account",
        },
        "data": {
            "id": "device-456_motion_detected_1792585800000",
            "type": "motion_detected",
            "attributes": {
                "source": "device-456",
                "source_type": "devices",
                "timestamp": 1792585800000,
                "sub_type": "human",
                "component_ids": ["front-camera"],
                "access_token": "never-copy-this",
            },
            "relationships": {},
        },
    }
    for key, value in overrides.items():
        payload[key] = value
    return payload


def signature(body: bytes) -> str:
    digest = hmac.new(TEST_KEY.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.fixture
def ring_key(monkeypatch):
    monkeypatch.setattr(settings, "ring_hmac_signing_key", TEST_KEY)


def test_signature_uses_raw_body_and_exact_prefix():
    raw = b'{ "data": {"x":1} }'
    assert verify_signature(TEST_KEY, raw, signature(raw))
    assert not verify_signature(TEST_KEY, raw + b" ", signature(raw))
    assert not verify_signature(TEST_KEY, raw, signature(raw).removeprefix("sha256="))
    assert not verify_signature(TEST_KEY, raw, None)


@pytest.mark.parametrize(
    ("ring_type", "expected"),
    [
        ("motion_detected", "motion"),
        ("button_press", "doorbell_press"),
        ("device_added", "device_added"),
        ("device_removed", "device_removed"),
        ("device_online", "device_online"),
        ("device_offline", "device_offline"),
    ],
)
def test_normalizes_supported_ring_event_types(ring_type, expected):
    payload = ring_payload()
    payload["data"]["type"] = ring_type
    normalized = normalize_webhook(payload)
    assert normalized["event_type"] == expected
    assert normalized["external_event_id"] == "request-123"
    assert normalized["metadata"]["ring_event_id"].startswith("device-456_")
    assert "access_token" not in normalized["metadata"]
    assert "account_id" not in normalized["metadata"]


def test_normalizer_supports_iso_time_fallback_and_ignores_unknown():
    payload = ring_payload()
    payload["data"]["attributes"].pop("timestamp")
    assert normalize_webhook(payload)["occurred_at"].isoformat().startswith("2026-10-21T12:30:00")
    payload["data"]["type"] = "subscription_activated"
    assert normalize_webhook(payload) is None


def test_normalizer_handles_bad_optional_timestamp_with_meta_fallback():
    payload = ring_payload()
    payload["data"]["attributes"]["timestamp"] = "bad timestamp"
    assert normalize_webhook(payload)["occurred_at"].isoformat().startswith("2026-10-21T12:30:00")


def test_valid_signed_webhook_persists_and_duplicate_is_idempotent(client: TestClient, ring_key):
    raw = json.dumps(ring_payload(), separators=(",", ":")).encode()
    first = client.post("/api/v1/integrations/ring/webhook", content=raw, headers={"X-Signature": signature(raw)})
    second = client.post("/api/v1/integrations/ring/webhook", content=raw, headers={"X-Signature": signature(raw)})

    assert first.status_code == 200
    assert first.json() == {"status": "processed", "is_duplicate": False}
    assert second.status_code == 200
    assert second.json() == {"status": "processed", "is_duplicate": True}
    events = client.get("/api/v1/events", params={"source": "ring"}).json()
    assert events["total"] == 1
    assert events["items"][0]["external_event_id"] == "request-123"
    assert events["items"][0]["metadata"]["sub_type"] == "human"


@pytest.mark.parametrize("headers", [{}, {"X-Signature": "sha256=wrong"}])
def test_missing_or_invalid_signature_does_not_persist(client: TestClient, ring_key, headers):
    raw = json.dumps(ring_payload()).encode()
    response = client.post("/api/v1/integrations/ring/webhook", content=raw, headers=headers)
    assert response.status_code == 401
    assert client.get("/api/v1/events", params={"source": "ring"}).json()["total"] == 0


def test_distinct_request_ids_remain_distinct_deliveries(client: TestClient, ring_key):
    payload = ring_payload()
    first_body = json.dumps(payload).encode()
    first = client.post("/api/v1/integrations/ring/webhook", content=first_body, headers={"X-Signature": signature(first_body)})

    payload["meta"]["request_id"] = "request-456"
    second_body = json.dumps(payload).encode()
    second = client.post("/api/v1/integrations/ring/webhook", content=second_body, headers={"X-Signature": signature(second_body)})

    assert first.status_code == 200 and first.json()["is_duplicate"] is False
    assert second.status_code == 200 and second.json()["is_duplicate"] is False
    assert client.get("/api/v1/events", params={"source": "ring"}).json()["total"] == 2


def test_altered_raw_body_is_rejected(client: TestClient, ring_key):
    raw = json.dumps(ring_payload()).encode()
    response = client.post(
        "/api/v1/integrations/ring/webhook",
        content=raw + b" ",
        headers={"X-Signature": signature(raw)},
    )
    assert response.status_code == 401
    assert client.get("/api/v1/events", params={"source": "ring"}).json()["total"] == 0


def test_signed_malformed_payload_is_rejected(client: TestClient, ring_key):
    raw = b"{not-json"
    response = client.post("/api/v1/integrations/ring/webhook", content=raw, headers={"X-Signature": signature(raw)})
    assert response.status_code == 400
    assert client.get("/api/v1/events", params={"source": "ring"}).json()["total"] == 0


def test_signed_unknown_event_is_safely_acknowledged(client: TestClient, ring_key):
    payload = ring_payload()
    payload["data"]["type"] = "subscription_activated"
    raw = json.dumps(payload).encode()
    response = client.post("/api/v1/integrations/ring/webhook", content=raw, headers={"X-Signature": signature(raw)})
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert client.get("/api/v1/events", params={"source": "ring"}).json()["total"] == 0


def test_webhook_receipt_updates_safe_status(client: TestClient, ring_key):
    raw = json.dumps(ring_payload()).encode()
    client.post("/api/v1/integrations/ring/webhook", content=raw, headers={"X-Signature": signature(raw)})
    status_response = client.get("/api/v1/integrations/ring/status")
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["status"] == "unknown"
    assert body["is_connected"] is False
    assert body["last_successful_sync_at"]
    assert "synthetic-ring-signing-key" not in status_response.text


def test_persistence_failure_returns_retryable_server_error(client: TestClient, ring_key, monkeypatch):
    from app.dependencies import get_event_ingestion_service

    class BrokenIngestion:
        def ingest_event(self, _event):
            raise RuntimeError("database unavailable")

    app.dependency_overrides[get_event_ingestion_service] = lambda: BrokenIngestion()
    try:
        raw = json.dumps(ring_payload()).encode()
        response = client.post("/api/v1/integrations/ring/webhook", content=raw, headers={"X-Signature": signature(raw)})
        assert response.status_code == 503
    finally:
        app.dependency_overrides.pop(get_event_ingestion_service, None)
