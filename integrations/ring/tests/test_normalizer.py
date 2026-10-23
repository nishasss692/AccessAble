import pytest
from integrations.ring.app.normalizer import normalize_event
def test_normalizes_demo_event():
    raw = {
        "event_id": "demo-001",
        "type": "motion",
        "timestamp": "2026-10-21T12:30:00Z",
        "device_id": "device-01",
        "metadata": {"is_simulated": True},
    }
    result = normalize_event(raw)
    assert result["source"] == "demo"
    assert result["external_event_id"] == "demo-001"
    assert result["event_type"] == "motion"
    assert result["occurred_at"] == "2026-10-21T12:30:00Z"
    assert result["device_id"] == "device-01"
def test_missing_event_type_is_rejected():
    with pytest.raises(ValueError, match="event type"):
        normalize_event({"event_id": "demo-001"})
def test_missing_timestamp_is_rejected():
    with pytest.raises(ValueError, match="required"):
        normalize_event({"event_id": "demo-002", "type": "motion"})
def test_invalid_metadata_is_rejected():
    with pytest.raises(ValueError, match="Metadata"):
        normalize_event({
            "type": "motion",
            "timestamp": "2026-10-21T12:30:00Z",
            "metadata": ["not", "an", "object"],
        })
def test_timezone_is_required():
    with pytest.raises(ValueError, match="timezone"):
        normalize_event({
            "type": "motion",
            "timestamp": "2026-10-21T12:30:00",
        })

def test_sensitive_metadata_key_is_rejected():
    with pytest.raises(ValueError, match="forbidden sensitive key"):
        normalize_event({
            "type": "motion",
            "timestamp": "2026-10-21T12:30:00Z",
            "metadata": {"access_token": "must-not-be-stored"},
        })


@pytest.mark.parametrize("ring_type,expected", [
    ("motion_detected", "motion"), ("button_press", "doorbell_press"),
    ("device_added", "device_added"), ("device_removed", "device_removed"),
    ("device_online", "device_online"), ("device_offline", "device_offline"),
])
def test_normalizes_documented_ring_v11_types(ring_type, expected):
    payload = {
        "meta": {"request_id": "delivery-1", "time": "2026-10-21T12:30:00Z", "account_id": "private"},
        "data": {"id": "evt-1", "type": ring_type, "attributes": {"source": "device-1", "timestamp": 1792585800000, "sub_type": "human"}},
    }
    event = normalize_event(payload, source="ring")
    assert event["event_type"] == expected
    assert event["source"] == "ring"
    assert event["external_event_id"] == "delivery-1"
    assert event["device_id"] == "device-1"
    assert "account_id" not in event["metadata"]


def test_preserves_ring_event_timestamp_milliseconds():
    payload = {
        "meta": {"request_id": "delivery-ms", "time": "2026-10-21T12:30:00Z"},
        "data": {"id": "evt-ms", "type": "motion_detected", "attributes": {
            "source": "device-1", "timestamp": 1792585800123,
        }},
    }
    event = normalize_event(payload, source="ring")
    assert event["occurred_at"] == "2026-10-21T12:30:00.123Z"


def test_rejects_malformed_ring_and_unknown_type():
    with pytest.raises(ValueError, match="Unsupported"):
        normalize_event({"meta": {"request_id": "r"}, "data": {"id": "i", "type": "invented", "attributes": {}}}, "ring")
    with pytest.raises(ValueError, match="Ring attributes"):
        normalize_event({"meta": {"request_id": "r"}, "data": {"id": "i", "type": "motion_detected", "attributes": []}}, "ring")


@pytest.mark.parametrize("meta,data", [
    ({}, {"id": "i", "type": "motion_detected", "attributes": {"source": "d", "timestamp": 1792585800000}}),
    ({"request_id": "  "}, {"id": "i", "type": "motion_detected", "attributes": {"source": "d", "timestamp": 1792585800000}}),
    ({"request_id": "r"}, {"id": "", "type": "motion_detected", "attributes": {"source": "d", "timestamp": 1792585800000}}),
    ({"request_id": "r"}, {"id": "i", "type": "motion_detected", "attributes": {"source": "", "timestamp": 1792585800000}}),
])
def test_ring_payload_requires_delivery_event_and_device_identifiers(meta, data):
    with pytest.raises(ValueError):
        normalize_event({"meta": meta, "data": data}, "ring")


def test_rejects_invalid_device_identifier_and_timestamp():
    with pytest.raises(ValueError, match="Device ID"):
        normalize_event({"type": "motion", "timestamp": "2026-10-21T12:30:00Z", "device_id": 4})
    with pytest.raises(ValueError, match="Invalid event timestamp"):
        normalize_event({"type": "motion", "timestamp": "bad"})
