"""Explicit summary-processing entry point; no worker or polling loop is started."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any, Mapping, Protocol

from .summaries import EventSummary, SummaryProvider, SummaryStatus, metadata_summary, summarize_event


class RecordingSource(Protocol):
    def get_video(self, event: Mapping[str, Any]) -> bytes: ...


class ProcessingStore(Protocol):
    def claim(self, event_key: str) -> bool: ...
    def get(self, event_key: str) -> "ProcessingResult | None": ...
    def save(self, event_key: str, result: "ProcessingResult") -> None: ...


@dataclass(frozen=True)
class ProcessingResult:
    event_key: str
    status: str
    event: dict[str, Any]
    summary: EventSummary | None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_key": self.event_key,
            "status": self.status,
            "event": self.event,
            "summary": self.summary.to_dict() if self.summary else None,
            "error": self.error,
        }


class InMemoryProcessingStore:
    """Thread-safe test/demo store only; production requires backend persistence."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._claimed: set[str] = set()
        self._results: dict[str, ProcessingResult] = {}

    def claim(self, event_key: str) -> bool:
        with self._lock:
            if event_key in self._claimed:
                return False
            self._claimed.add(event_key)
            return True

    def get(self, event_key: str) -> ProcessingResult | None:
        with self._lock:
            return self._results.get(event_key)

    def save(self, event_key: str, result: ProcessingResult) -> None:
        with self._lock:
            self._results[event_key] = result


def stable_event_key(event: Mapping[str, Any]) -> str:
    source = event.get("source")
    external_id = event.get("external_event_id")
    if not isinstance(source, str) or not source or not isinstance(external_id, str) or not external_id:
        raise ValueError("Summary processing requires source and external_event_id")
    return f"{source}:{external_id}"


def process_event(
    event: Mapping[str, Any],
    *,
    store: ProcessingStore,
    recording_source: RecordingSource | None = None,
    summary_provider: SummaryProvider | None = None,
) -> ProcessingResult:
    """Run once for a stable event ID; caller owns scheduling and durable store."""
    key = stable_event_key(event)
    existing = store.get(key)
    if existing is not None and existing.status in {SummaryStatus.COMPLETED, SummaryStatus.UNAVAILABLE}:
        return existing
    if not store.claim(key):
        return existing or ProcessingResult(key, SummaryStatus.PENDING, dict(event), None)

    limitations: tuple[str, ...] = ()
    video: bytes | None = None
    if recording_source is not None:
        try:
            video = recording_source.get_video(event)
        except Exception:
            limitations = ("Recording retrieval failed; the original event is retained and only metadata is summarized.",)
    try:
        summary = summarize_event(event, video_bytes=video, provider=summary_provider) if not limitations else metadata_summary(event, limitations=limitations)
    except Exception:
        result = ProcessingResult(
            key,
            SummaryStatus.FAILED,
            dict(event),
            None,
            error="Summary processing failed validation.",
        )
        store.save(key, result)
        return result
    status = summary.status
    result = ProcessingResult(key, status, dict(event), summary)
    store.save(key, result)
    return result
