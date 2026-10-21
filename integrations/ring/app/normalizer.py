from datetime import datetime, timezone
from typing import Any

def normalize_event(raw: dict[str, Any], source: str = "demo") -> dict:
    if source not in {"ring", "demo"}:
        raise ValueError("ring/demo rehna hai")

    event_type = raw.get("event_type") or raw.get("type")
    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError("invalid")

    external_id = raw.get("external_event_id") or raw.get("event_id")

    occurred_at = raw.get("occurred_at") or raw.get("timestamp")

    if occurred_at is not None:
        if not isinstance(occurred_at, str):
            raise ValueError("must be string or nlul")

        try:
            parsed = datetime.fromisoformat(
                occurred_at.replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise ValueError("Invalid event timestamp") from exc

        # A timestamp without timezone information is ambiguous.
        if parsed.tzinfo is None:
            raise ValueError("Event timestamp must include a timezone")

        occurred_at = (
            parsed.astimezone(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )

    metadata = raw.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise ValueError("Metadata must be a JSON object")

    device_id = raw.get("device_id")

    if device_id is not None and not isinstance(device_id, str):
        raise ValueError("Device ID must be a string or null")

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
