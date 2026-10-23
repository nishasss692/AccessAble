"""Provider-independent, evidence-labelled event summary primitives."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

MAX_SUMMARY_VIDEO_BYTES = 25 * 1024 * 1024


class SummaryStatus(str):
    PENDING = "pending"
    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class SummaryProvider(Protocol):
    """Return only observable actions; put ambiguity in ``uncertainties``.

    Providers must not infer identity, intent, criminal behavior, or danger.
    The interface expects ``summary``, ``observed_actions``, ``uncertainties``,
    optional ``confidence``, and ``limitations``.
    """

    def summarize_video(self, video_bytes: bytes, event_context: Mapping[str, Any]) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class EventSummary:
    summary: str
    event_time: str
    observed_actions: tuple[str, ...]
    uncertainties: tuple[str, ...]
    importance: int
    confidence: float | None
    evidence_type: str
    recording_available: bool | None
    limitations: tuple[str, ...]
    status: str = SummaryStatus.COMPLETED
    category: str = "unknown"
    provider_name: str | None = None
    model_id: str | None = None
    processed_at: str | None = None
    retryable: bool = False

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result.pop("retryable", None)
        result["observed_actions"] = list(self.observed_actions)
        result["uncertainties"] = list(self.uncertainties)
        result["limitations"] = list(self.limitations)
        return result


def _event_time(event: Mapping[str, Any]) -> str:
    value = event.get("occurred_at")
    if not isinstance(value, (str, datetime)):
        return "unknown"
    return value.isoformat() if isinstance(value, datetime) else value


def _event_importance(event: Mapping[str, Any]) -> int:
    return {
        "doorbell_press": 30,
        "motion": 20,
        "device_offline": 25,
        "device_added": 10,
        "device_removed": 20,
        "device_online": 10,
    }.get(str(event.get("event_type", "")), 10)


def metadata_summary(event: Mapping[str, Any], *, limitations: tuple[str, ...] = ()) -> EventSummary:
    """Return a conservative description based only on normalized metadata."""
    kind = event.get("event_type")
    timestamp = _event_time(event)
    label = {
        "motion": "Motion detected",
        "doorbell_press": "Doorbell pressed",
        "device_offline": "Ring device went offline",
        "device_online": "Ring device came online",
        "device_added": "Ring device added",
        "device_removed": "Ring device removed",
    }.get(str(kind), "Ring event detected")
    text = f"{label} at {timestamp}."
    category = str(kind) if kind in {"motion", "doorbell_press", "device_added", "device_removed", "device_online", "device_offline"} else "unknown"
    return EventSummary(
        summary=text,
        event_time=timestamp,
        observed_actions=(),
        uncertainties=(),
        importance=_event_importance(event),
        confidence=None,
        evidence_type="event_metadata",
        recording_available=None,
        limitations=("No video was supplied; this summary describes event metadata only.", *limitations),
        category=category,
        processed_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    )


def summarize_event(
    event: Mapping[str, Any],
    *,
    video_bytes: bytes | None = None,
    provider: SummaryProvider | None = None,
) -> EventSummary:
    """Use video only when actual bounded bytes and an explicit provider exist."""
    if video_bytes is None:
        return metadata_summary(event)
    if not isinstance(video_bytes, bytes) or not video_bytes:
        raise ValueError("video_bytes must contain actual non-empty video data")
    if len(video_bytes) > MAX_SUMMARY_VIDEO_BYTES:
        raise ValueError("video_bytes exceeds the configured summary size limit")
    if provider is None:
        return EventSummary(
            summary="Video is available, but no video-summary provider is configured.",
            event_time=_event_time(event),
            observed_actions=(),
            uncertainties=(),
            importance=_event_importance(event),
            confidence=None,
            evidence_type="event_metadata",
            recording_available=True,
            limitations=("Video was not analyzed because no provider was configured.",),
            status=SummaryStatus.UNAVAILABLE,
            category=str(event.get("event_type", "unknown")),
            processed_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        )
    try:
        result = provider.summarize_video(video_bytes, dict(event))
    except Exception as exc:
        return EventSummary(
            summary="Video summary could not be generated.",
            event_time=_event_time(event),
            observed_actions=(),
            uncertainties=(),
            importance=_event_importance(event),
            confidence=None,
            evidence_type="event_metadata",
            recording_available=True,
            limitations=("The configured video-summary provider failed; no video description is available.",),
            status=SummaryStatus.FAILED,
            category=str(event.get("event_type", "unknown")),
            processed_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            retryable=bool(getattr(exc, "retryable", False)),
        )
    if not isinstance(result, Mapping):
        raise ValueError("Summary provider returned an invalid result")
    summary = result.get("summary")
    actions = result.get("observed_actions", [])
    uncertainties = result.get("uncertainties")
    confidence = result.get("confidence")
    limitations = result.get("limitations", [])
    provider_name = result.get("provider_name", getattr(provider, "provider_name", "custom"))
    model_id = result.get("model_id", getattr(provider, "model", None))
    if (
        not isinstance(summary, str) or not summary.strip() or len(summary) > 2000
        or not isinstance(actions, (list, tuple)) or len(actions) > 20
        or any(not isinstance(item, str) or not item.strip() or len(item) > 500 for item in actions)
        or not isinstance(uncertainties, (list, tuple)) or len(uncertainties) > 20
        or any(not isinstance(item, str) or not item.strip() or len(item) > 500 for item in uncertainties)
        or (confidence is not None and (isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1))
        or not isinstance(limitations, (list, tuple))
        or any(not isinstance(item, str) or len(item) > 500 for item in limitations)
        or not isinstance(provider_name, str) or not provider_name or len(provider_name) > 80
        or (model_id is not None and (not isinstance(model_id, str) or len(model_id) > 80))
    ):
        raise ValueError("Summary provider returned malformed summary fields")
    return EventSummary(
        summary=summary.strip(),
        event_time=_event_time(event),
        observed_actions=tuple(item.strip() for item in actions),
        uncertainties=tuple(item.strip() for item in uncertainties),
        importance=_event_importance(event),
        confidence=float(confidence) if confidence is not None else None,
        evidence_type="video",
        recording_available=True,
        limitations=tuple(item.strip() for item in limitations),
        category=str(event.get("event_type", "unknown")) if event.get("event_type") in {"motion", "doorbell_press", "device_added", "device_removed", "device_online", "device_offline"} else "unknown",
        provider_name=provider_name,
        model_id=model_id,
        processed_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    )
