"""Ring webhook signature verification and v1.1 event normalization."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
from typing import Any


EVENT_TYPE_MAP = {
    "motion_detected": "motion",
    "button_press": "doorbell_press",
    "device_added": "device_added",
    "device_removed": "device_removed",
    "device_online": "device_online",
    "device_offline": "device_offline",
}

SAFE_ATTRIBUTE_KEYS = {"source", "source_type", "sub_type", "component_ids", "timestamp"}


def verify_signature(signing_key: str, raw_body: bytes, signature: str | None) -> bool:
    """Verify Ring's sha256=<lowercase hex digest> over the original body bytes."""
    if not signing_key or not signature or not signature.startswith("sha256="):
        return False
    supplied = signature.removeprefix("sha256=")
    expected = hmac.new(signing_key.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied)


def _as_safe_value(value: Any) -> Any:
    """Retain only bounded JSON scalars and lists from documented attributes."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list) and len(value) <= 32:
        return [item for item in value if isinstance(item, (str, int, float, bool))]
    return None


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            seconds = value / 1000 if abs(value) >= 100_000_000_000 else value
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return None
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def normalize_webhook(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Map documented Ring v1.1 device events to the existing EventCreate contract.

    Returns None for valid but unsupported event types, which the route safely
    acknowledges without creating a user-visible event.
    """
    meta = payload.get("meta")
    data = payload.get("data")
    if not isinstance(meta, dict) or not isinstance(data, dict):
        raise ValueError("Invalid Ring webhook envelope")

    request_id = meta.get("request_id")
    event_id = data.get("id")
    ring_type = data.get("type")
    attributes = data.get("attributes", {})
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("Missing Ring request ID")
    if not isinstance(event_id, str) or not event_id.strip():
        raise ValueError("Missing Ring event ID")
    if not isinstance(ring_type, str) or not ring_type.strip():
        raise ValueError("Missing Ring event type")
    if not isinstance(attributes, dict):
        raise ValueError("Invalid Ring event attributes")

    normalized_type = EVENT_TYPE_MAP.get(ring_type)
    if normalized_type is None:
        return None

    occurred_at = _parse_timestamp(attributes.get("timestamp"))
    if occurred_at is None:
        occurred_at = _parse_timestamp(meta.get("time"))
    if occurred_at is None:
        occurred_at = datetime.now(timezone.utc)

    device_id = attributes.get("source")
    if not isinstance(device_id, str) or not device_id:
        device_id = None
        relationships = data.get("relationships")
        if isinstance(relationships, dict):
            devices = relationships.get("devices")
            related = devices.get("data") if isinstance(devices, dict) else None
            if isinstance(related, dict):
                device_id = related.get("id") if isinstance(related.get("id"), str) else None
            elif isinstance(related, list) and related and isinstance(related[0], dict):
                candidate = related[0].get("id")
                device_id = candidate if isinstance(candidate, str) else None

    safe_attributes = {
        key: safe_value
        for key in SAFE_ATTRIBUTE_KEYS
        if (safe_value := _as_safe_value(attributes.get(key))) is not None
    }
    return {
        "source": "ring",
        # Ring documents request_id as the delivery idempotency key. The DB's
        # unique (source, external_event_id) constraint makes it atomic.
        "external_event_id": request_id,
        "event_type": normalized_type,
        "occurred_at": occurred_at,
        "device_id": device_id,
        "metadata": {
            "ring_event_id": event_id,
            "ring_event_type": ring_type,
            "ring_request_id": request_id,
            **safe_attributes,
        },
    }
