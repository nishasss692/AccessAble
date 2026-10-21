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
