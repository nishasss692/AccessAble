from datetime import datetime, timezone
import math
from typing import Any

FORBIDDEN_METADATA_KEYS = {
    "token",
    "secret",
    "password",
    "auth_token",
    "access_token",
    "refresh_token",
    "api_key",
    "client_secret",
    "authorization",
}

RING_EVENT_TYPES = {
    "motion_detected": "motion",
    "button_press": "doorbell_press",
    "device_added": "device_added",
    "device_removed": "device_removed",
    "device_online": "device_online",
    "device_offline": "device_offline",
}


class UnsupportedRingEventError(ValueError):
    """A well-formed Ring event whose type is not mapped by this integration."""


def _timestamp(value: Any) -> datetime:
    if isinstance(value, bool):
        raise ValueError("Invalid event timestamp")
    try:
        if isinstance(value, (int, float)):
            if not math.isfinite(value):
                raise ValueError
            seconds = value / 1000 if abs(value) >= 100_000_000_000 else value
            parsed = datetime.fromtimestamp(seconds, tz=timezone.utc)
        elif isinstance(value, str) and value.strip():
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        else:
            raise ValueError
    except (ValueError, OverflowError, OSError) as exc:
        raise ValueError("Invalid event timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("Event timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def normalize_event(raw: dict[str, Any], source: str = "demo") -> dict:
    if source not in {"ring", "demo"}:
        raise ValueError("Source must be 'ring' or 'demo'")
    if not isinstance(raw, dict):
        raise ValueError("Event payload must be an object")

    attributes: dict[str, Any] = {}
    metadata = raw.get("metadata") or {}
    if source == "ring":
        if not isinstance(raw.get("meta"), dict) or not isinstance(raw.get("data"), dict):
            raise ValueError("Malformed Ring webhook envelope")
        data = raw["data"]
        meta = raw["meta"]
        attributes = data.get("attributes", {})
        if not isinstance(attributes, dict):
            raise ValueError("Ring attributes must be an object")
        event_type = RING_EVENT_TYPES.get(data.get("type"))
        if not event_type:
            raise UnsupportedRingEventError("Unsupported Ring event type")
        external_id = meta.get("request_id")
        if not isinstance(external_id, str) or not external_id.strip():
            raise ValueError("Ring request ID is required for idempotency")
        event_id = data.get("id")
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("Ring event ID is required")
        occurred_at = attributes.get("timestamp") or meta.get("time")
        device_id = attributes.get("source")
        if not isinstance(device_id, str) or not device_id.strip():
            raise ValueError("Ring device identifier is required")
        metadata = {
            "ring_event_id": event_id,
            "ring_event_type": data.get("type"),
            "ring_request_id": external_id,
            **{key: attributes[key] for key in ("source_type", "sub_type", "component_ids") if key in attributes},
        }
    else:
        event_type = raw.get("event_type") or raw.get("type")
        external_id = raw.get("external_event_id") or raw.get("event_id")
        occurred_at = raw.get("occurred_at") or raw.get("timestamp")
        device_id = raw.get("device_id")

    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError("Invalid event type")
    if occurred_at is None:
        raise ValueError("Event timestamp is required")
    parsed_occurred_at = _timestamp(occurred_at)
    precision = "milliseconds" if parsed_occurred_at.microsecond else "seconds"
    occurred_at = parsed_occurred_at.isoformat(timespec=precision).replace("+00:00", "Z")
    if not isinstance(metadata, dict):
        raise ValueError("Metadata must be a JSON object")
    for key in metadata:
        if str(key).lower().strip() in FORBIDDEN_METADATA_KEYS:
            raise ValueError(f"Metadata contains forbidden sensitive key '{key}'")

    if device_id is not None and not isinstance(device_id, str):
        raise ValueError("Device ID must be a string or null")
    if device_id == "":
        raise ValueError("Device ID must not be empty")

    return {
        "source": source,
        "external_event_id": (
            str(external_id) if external_id is not None else None
        ),
        "event_type": event_type.strip().lower(),
        "occurred_at": occurred_at,
        "device_id": device_id,
        "metadata": metadata,
    }
