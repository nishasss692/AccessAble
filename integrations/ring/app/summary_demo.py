"""Run a durable local pipeline demo with a generated video fixture only."""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
import tempfile
from pathlib import Path

from .normalizer import normalize_event
from .pipeline_worker import SQLiteSummaryWorker
from .ring_client import RecordingMetadata, RecordingNetworkError, RecordingStatus
from .sqlite_pipeline import SQLitePipelineStore
from .synthetic_fixture import SyntheticFixtureInspector, make_color_card_video
from .vision_provider import VisionProviderTemporaryError


class SyntheticRecordingRetriever:
    def __init__(self, video: bytes):
        self.video = video
        self.calls = 0

    def download_event_video(self, event, *, duration_ms):
        self.calls += 1
        return RecordingMetadata(
            external_event_id=event["external_event_id"],
            device_id=event["device_id"],
            recording_id=None,
            started_at=datetime.fromisoformat(event["occurred_at"].replace("Z", "+00:00")),
            requested_duration_ms=duration_ms,
            actual_duration_ms=duration_ms,
            status=RecordingStatus.AVAILABLE,
            mime_type="video/mp4",
            retrieved_at=datetime.now(timezone.utc),
            media_bytes=self.video,
        )


def main() -> None:
    event = normalize_event({
        "event_id": "synthetic-fixture-event-001",
        "type": "motion",
        "timestamp": "2026-10-22T10:00:00.123Z",
        "device_id": "synthetic-test-camera",
        "metadata": {"is_simulated": True},
    })
    fixture = make_color_card_video()
    retriever = SyntheticRecordingRetriever(fixture)
    provider = SyntheticFixtureInspector()
    with tempfile.TemporaryDirectory(prefix="accessable-ring-demo-") as folder:
        database_path = Path(folder) / "ring-demo.sqlite3"
        store = SQLitePipelineStore(database_path)
        event_key, first_created = store.enqueue(event)
        _, duplicate_created = store.enqueue(event)
        store.close()

        # A new store instance simulates a worker process restart with a queued job.
        restarted_store = SQLitePipelineStore(database_path)
        worker = SQLiteSummaryWorker(
            restarted_store,
            recording_retriever=retriever,
            summary_provider=provider,
            recording_duration_ms=1000,
        )
        result = worker.run_once("synthetic-demo-worker")
        timeline = restarted_store.list_timeline(date(2026, 10, 22), sort="importance")

        failure_time = datetime(2026, 10, 23, 0, 0, tzinfo=timezone.utc)
        failed_recording_event = normalize_event({
            "event_id": "synthetic-retrieval-failure-002", "type": "motion",
            "timestamp": "2026-10-22T10:05:00Z", "device_id": "synthetic-test-camera",
            "metadata": {"is_simulated": True},
        })
        restarted_store.enqueue(failed_recording_event, now=failure_time)

        class FailingRetriever:
            calls = 0

            def download_event_video(self, event, *, duration_ms, component_id=None):
                self.calls += 1
                raise RecordingNetworkError("synthetic offline transport failure")

        failing_retriever = FailingRetriever()
        failure_worker = SQLiteSummaryWorker(
            restarted_store, recording_retriever=failing_retriever,
            summary_provider=provider, max_attempts=2, retry_delay_seconds=1,
        )
        retrieval_failure_first = failure_worker.run_once("synthetic-failure-worker", now=failure_time)
        retrieval_failure_final = failure_worker.run_once(
            "synthetic-failure-worker", now=failure_time.replace(second=2),
        )

        failed_provider_event = normalize_event({
            "event_id": "synthetic-provider-failure-003", "type": "motion",
            "timestamp": "2026-10-22T10:10:00Z", "device_id": "synthetic-test-camera",
            "metadata": {"is_simulated": True},
        })
        restarted_store.enqueue(failed_provider_event, now=failure_time)

        class TransientProviderFailure:
            calls = 0

            def summarize_video(self, video_bytes, event_context):
                self.calls += 1
                raise VisionProviderTemporaryError("synthetic transient provider failure")

        transient_provider = TransientProviderFailure()
        provider_failure_worker = SQLiteSummaryWorker(
            restarted_store, recording_retriever=retriever,
            summary_provider=transient_provider, max_attempts=2, retry_delay_seconds=1,
            recording_duration_ms=1000,
        )
        provider_failure_first = provider_failure_worker.run_once("synthetic-provider-worker", now=failure_time)
        provider_failure_final = provider_failure_worker.run_once(
            "synthetic-provider-worker", now=failure_time.replace(second=2),
        )
        print(json.dumps({
            "notice": "SYNTHETIC ONLY: no Ring service, customer footage, or paid AI service was contacted.",
            "event_normalized_and_enqueued": first_created,
            "duplicate_created_new_event_or_job": duplicate_created,
            "worker_restarted_with_queued_job": True,
            "synthetic_mp4_bytes": len(fixture),
            "mock_recording_retrieval_calls": retriever.calls,
            "provider": provider.provider_name,
            "persisted_job": result,
            "local_timeline": timeline,
            "simulated_recording_failure": {
                "first_attempt": {"status": retrieval_failure_first["status"], "attempt_count": retrieval_failure_first["attempt_count"]},
                "final_attempt": {"status": retrieval_failure_final["status"], "attempt_count": retrieval_failure_final["attempt_count"]},
                "calls": failing_retriever.calls,
            },
            "simulated_provider_failure": {
                "first_attempt": {"status": provider_failure_first["status"], "attempt_count": provider_failure_first["attempt_count"]},
                "final_attempt": {"status": provider_failure_final["status"], "attempt_count": provider_failure_final["attempt_count"]},
                "calls": transient_provider.calls,
            },
            "limitations": [
                "The local timeline is SQLite demo output, not the AccessAble backend API.",
                "The frontend does not yet render these integration-local summaries.",
                "The mock inspector decoded only the generated color-card fixture; no Ring video was analyzed.",
            ],
        }, indent=2))
        restarted_store.close()


if __name__ == "__main__":
    main()
