"""Transparent, deterministic importance scoring from explicit metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class ImportanceRules:
    event_points: Mapping[str, int] = field(default_factory=lambda: {
        "doorbell_press": 30,
        "motion": 20,
        "device_offline": 25,
        "device_online": 10,
        "device_added": 10,
        "device_removed": 20,
    })
    repeat_window: timedelta = timedelta(minutes=10)
    repeat_points: int = 5
    max_repeat_points: int = 20
    duration_points_per_minute: int = 0
    max_duration_points: int = 0
    preference_points: Mapping[str, int] = field(default_factory=dict)
    max_score: int = 100


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


def rank_importance(
    event: Mapping[str, Any],
    *,
    recent_events: Iterable[Mapping[str, Any]] = (),
    rules: ImportanceRules | None = None,
    user_preference_points: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Rank without changing/removing events; report reasons separately from confidence."""
    rules = rules or ImportanceRules()
    event_type = str(event.get("event_type", "unknown"))
    base = int(rules.event_points.get(event_type, 10))
    reasons = [f"event_type:{event_type}"]
    timestamp = _parse_time(event.get("occurred_at"))
    device_id = event.get("device_id")
    current_external_id = event.get("external_event_id")
    repeat_events: set[tuple[str, str]] = set()
    if timestamp is not None and isinstance(device_id, str) and device_id:
        for previous in recent_events:
            if previous.get("device_id") != device_id or previous.get("event_type") != event_type:
                continue
            previous_external_id = previous.get("external_event_id")
            # Stable IDs keep duplicate deliveries from inflating the score.
            if current_external_id and previous_external_id == current_external_id:
                continue
            previous_time = _parse_time(previous.get("occurred_at"))
            if previous_time is None or abs(timestamp - previous_time) > rules.repeat_window:
                continue
            if previous_external_id:
                repeat_events.add((str(previous.get("source", "")), str(previous_external_id)))
            else:
                # Without a stable ID, count at most one event per timestamp.
                repeat_events.add((device_id, previous_time.isoformat()))
    repeat_count = len(repeat_events)
    repeat_bonus = min(repeat_count * max(0, rules.repeat_points), max(0, rules.max_repeat_points))
    if repeat_count:
        reasons.append(f"same_device_repeat_within_{int(rules.repeat_window.total_seconds())}s:{repeat_count}")

    duration_raw = event.get("duration_ms")
    duration_bonus = 0
    if isinstance(duration_raw, int) and not isinstance(duration_raw, bool) and duration_raw > 0:
        duration_minutes = duration_raw // 60_000
        duration_bonus = min(duration_minutes * max(0, rules.duration_points_per_minute), max(0, rules.max_duration_points))
        if duration_bonus:
            reasons.append(f"duration_minutes:{duration_minutes}")

    preferences = user_preference_points if user_preference_points is not None else rules.preference_points
    preference_bonus = int(preferences.get(event_type, 0))
    if preference_bonus:
        reasons.append(f"configured_user_preference:{event_type}")

    score = min(max(0, base + repeat_bonus + duration_bonus + preference_bonus), max(0, rules.max_score))
    return {
        "importance_score": score,
        "base_points": base,
        "repeat_count": repeat_count,
        "repeat_points": repeat_bonus,
        "duration_points": duration_bonus,
        "preference_points": preference_bonus,
        "reason_codes": reasons,
        "confidence": "metadata_only" if timestamp is None or not device_id else "metadata_based",
        "rules": {
            "repeat_window_seconds": int(rules.repeat_window.total_seconds()),
            "repeat_points": rules.repeat_points,
            "max_repeat_points": rules.max_repeat_points,
            "duration_points_per_minute": rules.duration_points_per_minute,
            "max_duration_points": rules.max_duration_points,
            "preference_points": dict(preferences),
            "max_score": rules.max_score,
        },
    }
