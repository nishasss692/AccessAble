"""Explicit SQLite-backed local job runner; caller invokes ``run_once``."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import math
from typing import Any, Mapping, Protocol

from .ranking import ImportanceRules, rank_importance
from .ring_client import (
    RecordingAuthorizationError,
    RecordingMetadata,
    RecordingNetworkError,
    RecordingRateLimitedError,
    RecordingResponseError,
    RecordingStatus,
    RecordingUnavailableError,
    RingVideoClient,
    UnsafeRecordingRedirect,
)
from .sqlite_pipeline import ClaimedJob, SQLitePipelineStore
from .summaries import EventSummary, SummaryProvider, SummaryStatus, metadata_summary, summarize_event


class RecordingRetriever(Protocol):
    def download_event_video(self, event: dict[str, Any], **kwargs: Any) -> RecordingMetadata: ...


def _recording_json(recording: RecordingMetadata) -> dict[str, Any]:
    """Persist safe metadata only; never persist media bytes or signed URLs."""
    return {
        "external_event_id": recording.external_event_id,
        "device_id": recording.device_id,
        "component_id": recording.component_id,
        "recording_id": recording.recording_id,
        "started_at": recording.started_at.isoformat(),
        "requested_duration_ms": recording.requested_duration_ms,
        "actual_duration_ms": recording.actual_duration_ms,
        "status": recording.status.value,
        "mime_type": recording.mime_type,
        "retrieved_at": recording.retrieved_at.isoformat() if recording.retrieved_at else None,
        "limitation": recording.limitation,
        "bytes_persisted": False,
    }


class SQLiteSummaryWorker:
    """Durable local processing with atomic claims and lease recovery.

    This worker is not started automatically. Production scheduling and
    ownership-aware persistence remain a backend responsibility.
    """

    def __init__(
        self,
        store: SQLitePipelineStore,
        *,
        recording_retriever: RecordingRetriever | None,
        summary_provider: SummaryProvider | None,
        importance_rules: ImportanceRules | None = None,
        max_attempts: int = 3,
        lease_seconds: int = 120,
        retry_delay_seconds: int = 20,
        recording_duration_ms: int = 30_000,
    ):
        if not 1 <= max_attempts <= 10 or lease_seconds < 1 or retry_delay_seconds < 0:
            raise ValueError("Invalid worker retry/lease configuration")
        if not 1 <= recording_duration_ms <= 900_000:
            raise ValueError("recording_duration_ms must be 1..900000")
        self.store = store
        self.recording_retriever = recording_retriever
        self.summary_provider = summary_provider
        self.importance_rules = importance_rules or ImportanceRules()
        self.max_attempts = max_attempts
        self.lease_seconds = lease_seconds
        self.retry_delay_seconds = retry_delay_seconds
        self.recording_duration_ms = recording_duration_ms

    def run_once(self, worker_id: str, *, now: datetime | None = None) -> dict[str, Any] | None:
        instant = now or datetime.now(timezone.utc)
        job = self.store.claim_next(
            worker_id, now=instant, lease_seconds=self.lease_seconds, max_attempts=self.max_attempts,
        )
        if job is None:
            return None
        recent = self.store.recent_events(job.event, window_seconds=int(self.importance_rules.repeat_window.total_seconds()))
        rank = rank_importance(job.event, recent_events=recent, rules=self.importance_rules)
        event_type = job.event.get("event_type")
        if event_type not in {"motion", "doorbell_press"}:
            summary = replace(
                metadata_summary(job.event, limitations=("This Ring event type does not have a documented media clip." ,)),
                importance=rank["importance_score"],
                recording_available=False,
                status=SummaryStatus.UNAVAILABLE,
            )
            self.store.finish(
                job, status="skipped", importance=rank, summary=summary.to_dict(), recording=None,
                error_category="event_type_not_video_eligible", now=instant,
            )
            return self.store.get_job(job.event_key)
        if self.recording_retriever is None:
            summary = replace(
                metadata_summary(job.event, limitations=("Recording retrieval is not configured.",)),
                importance=rank["importance_score"],
                status=SummaryStatus.UNAVAILABLE,
            )
            self.store.finish(
                job, status="unavailable", importance=rank, summary=summary.to_dict(), recording=None,
                error_category="recording_retrieval_not_configured", now=instant,
            )
            return self.store.get_job(job.event_key)

        recording: RecordingMetadata | None = None
        try:
            retrieval_options: dict[str, Any] = {"duration_ms": self.recording_duration_ms}
            metadata = job.event.get("metadata")
            component_ids = metadata.get("component_ids") if isinstance(metadata, dict) else None
            if isinstance(component_ids, list):
                if len(component_ids) > 1:
                    raise RecordingUnavailableError(
                        RecordingStatus.UNSUPPORTED,
                        "This event references multiple camera modules; per-module processing is not configured.",
                    )
                if component_ids:
                    component_id = component_ids[0]
                    if not isinstance(component_id, str) or not component_id.strip():
                        raise RecordingUnavailableError(
                            RecordingStatus.UNSUPPORTED,
                            "Ring camera module metadata is invalid.",
                        )
                    retrieval_options["component_id"] = component_id
            recording = self.recording_retriever.download_event_video(
                job.event, **retrieval_options,
            )
        except RecordingUnavailableError as exc:
            if (
                exc.retryable
                and exc.status in {RecordingStatus.NOT_READY, RecordingStatus.NOT_FOUND}
                and job.attempt_count < self.max_attempts
            ):
                state = self.store.fail_or_retry(
                    job,
                    error_category="recording_not_ready" if exc.status == RecordingStatus.NOT_READY else "recording_media_not_found_recent",
                    max_attempts=self.max_attempts,
                    retry_delay_seconds=max(
                        self.retry_delay_seconds,
                        math.ceil(exc.retry_after_seconds or 0),
                    ),
                    now=instant,
                    waiting_for_recording=True,
                )
                result = self.store.get_job(job.event_key) or {}
                result["status"] = state
                return result
            unavailable = exc.status in {
                RecordingStatus.NOT_FOUND, RecordingStatus.DEVICE_NOT_FOUND,
                RecordingStatus.EXPIRED, RecordingStatus.INACCESSIBLE,
                RecordingStatus.UNSUPPORTED, RecordingStatus.NOT_READY,
            }
            error_category = {
                RecordingStatus.NOT_FOUND: "recording_not_found",
                RecordingStatus.DEVICE_NOT_FOUND: "ring_device_not_found",
                RecordingStatus.EXPIRED: "recording_expired_confirmed",
                RecordingStatus.INACCESSIBLE: "recording_inaccessible",
                RecordingStatus.UNSUPPORTED: "recording_unsupported",
                RecordingStatus.NOT_READY: "recording_not_ready_retries_exhausted",
                RecordingStatus.CORRUPT: "recording_corrupt",
            }.get(exc.status, "recording_unavailable")
            summary_status = SummaryStatus.UNAVAILABLE if unavailable else SummaryStatus.FAILED
            summary = replace(
                metadata_summary(job.event, limitations=(str(exc),)),
                importance=rank["importance_score"],
                recording_available=False,
                status=summary_status,
            )
            self.store.finish(
                job, status="unavailable" if unavailable else "failed", importance=rank,
                summary=summary.to_dict(), recording=None, error_category=error_category, now=instant,
            )
            return self.store.get_job(job.event_key)
        except RecordingAuthorizationError:
            summary = replace(
                metadata_summary(job.event, limitations=("Ring authorization does not permit media retrieval.",)),
                importance=rank["importance_score"],
                recording_available=False,
                status=SummaryStatus.UNAVAILABLE,
            )
            self.store.finish(
                job, status="unavailable", importance=rank, summary=summary.to_dict(), recording=None,
                error_category="recording_authorization", now=instant,
            )
            return self.store.get_job(job.event_key)
        except RecordingRateLimitedError as exc:
            state = self.store.fail_or_retry(
                job,
                error_category="recording_rate_limited",
                max_attempts=self.max_attempts,
                retry_delay_seconds=max(self.retry_delay_seconds, math.ceil(exc.retry_after_seconds)),
                now=instant,
            )
            result = self.store.get_job(job.event_key) or {}
            result["status"] = state
            return result
        except (RecordingResponseError, UnsafeRecordingRedirect) as exc:
            category = "recording_unsafe_redirect" if isinstance(exc, UnsafeRecordingRedirect) else "recording_invalid_response"
            failed_summary = replace(
                metadata_summary(job.event, limitations=("Ring did not return a usable recording; no video description is available.",)),
                importance=rank["importance_score"],
                recording_available=False,
                status=SummaryStatus.FAILED,
            )
            self.store.finish(
                job, status="failed", importance=rank, summary=failed_summary.to_dict(),
                recording=None, error_category=category, now=instant,
            )
            return self.store.get_job(job.event_key)
        except RecordingNetworkError:
            state = self.store.fail_or_retry(
                job, error_category="recording_network", max_attempts=self.max_attempts,
                retry_delay_seconds=self.retry_delay_seconds, now=instant,
            )
            result = self.store.get_job(job.event_key) or {}
            result["status"] = state
            return result

        if recording.status != RecordingStatus.AVAILABLE or not recording.media_bytes:
            summary = replace(
                metadata_summary(job.event, limitations=("The recording client returned no playable media bytes.",)),
                importance=rank["importance_score"],
                recording_available=False,
                status=SummaryStatus.UNAVAILABLE,
            )
            self.store.finish(
                job, status="unavailable", importance=rank, summary=summary.to_dict(),
                recording=_recording_json(recording), error_category="recording_bytes_missing", now=instant,
            )
            return self.store.get_job(job.event_key)

        self.store.update_state(job, "summarizing", now=instant, lease_seconds=self.lease_seconds)
        context = dict(job.event)
        context["recording_duration_ms"] = recording.actual_duration_ms or recording.requested_duration_ms
        try:
            summary = summarize_event(
                context,
                video_bytes=recording.media_bytes,
                provider=self.summary_provider,
            )
        except Exception:
            failed_summary = replace(
                metadata_summary(job.event, limitations=("Summary output failed validation; no video description is available.",)),
                importance=rank["importance_score"],
                recording_available=True,
                status=SummaryStatus.FAILED,
            )
            self.store.finish(
                job, status="failed", importance=rank, summary=failed_summary.to_dict(),
                recording=_recording_json(recording), error_category="summary_invalid_output", now=instant,
            )
            return self.store.get_job(job.event_key)
        summary = replace(summary, importance=rank["importance_score"])
        if summary.status == SummaryStatus.FAILED and summary.retryable and job.attempt_count < self.max_attempts:
            state = self.store.fail_or_retry(
                job,
                error_category="summary_provider_transient",
                max_attempts=self.max_attempts,
                retry_delay_seconds=self.retry_delay_seconds,
                now=instant,
            )
            result = self.store.get_job(job.event_key) or {}
            result["status"] = state
            return result
        state = {
            SummaryStatus.COMPLETED: "completed",
            SummaryStatus.UNAVAILABLE: "unavailable",
            SummaryStatus.FAILED: "failed",
        }.get(summary.status, "failed")
        self.store.finish(
            job,
            status=state,
            importance=rank,
            summary=summary.to_dict(),
            recording=_recording_json(recording),
            error_category=None if state == "completed" else f"summary_{state}",
            now=instant,
        )
        return self.store.get_job(job.event_key)
