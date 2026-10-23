from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import pytest
import requests

from integrations.ring.app.ring_client import (
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
from integrations.ring.app.processing import InMemoryProcessingStore, process_event
from integrations.ring.app.ranking import ImportanceRules, rank_importance
from integrations.ring.app.summaries import SummaryStatus, metadata_summary, summarize_event
from integrations.ring.app.pipeline_worker import SQLiteSummaryWorker
from integrations.ring.app.sqlite_pipeline import SQLitePipelineStore
from integrations.ring.app.synthetic_fixture import SyntheticFixtureInspector, make_color_card_video
from integrations.ring.app.vision_provider import (
    OpenAIFrameSummaryProvider,
    SampledFrame,
    VisionProviderConfigurationError,
    VisionProviderTemporaryError,
    create_configured_provider,
)


SYNTHETIC_TEST_MP4 = make_color_card_video()


EVENT = {
    "source": "ring",
    "external_event_id": "req-1",
    "event_type": "motion",
    "occurred_at": "2026-10-20T10:00:00Z",
    "device_id": "device-1",
    "metadata": {"ring_event_id": "evt-1", "timestamp": 1792490400000, "component_ids": ["1"]},
}


class FakeResponse:
    def __init__(self, status=200, headers=None, chunks=None):
        self.status_code = status
        self.chunks = chunks if chunks is not None else (SYNTHETIC_TEST_MP4,)
        self.headers = headers or {"Content-Type": "video/mp4", "Content-Length": str(sum(map(len, self.chunks)))}
        self.closed = False

    def iter_content(self, chunk_size):
        yield from self.chunks

    def close(self):
        self.closed = True


class FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("post", url, kwargs))
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        self.calls.append(("get", url, kwargs))
        return self.responses.pop(0)


def past_event():
    return EVENT | {
        "occurred_at": "2020-01-01T00:00:00.123Z",
        "metadata": EVENT["metadata"] | {"timestamp": 1577836800123},
    }


def client(transport, **kwargs):
    return RingVideoClient(
        "test-access-token", hardware_id="550e8400-e29b-41d4-a716-446655440000", transport=transport,
        clock=lambda: datetime(2026, 10, 23, tzinfo=timezone.utc),
        **kwargs,
    )


def test_ring_video_post_matches_documented_body_and_returns_bounded_mp4():
    transport = FakeTransport(FakeResponse(headers={
        "Content-Type": "video/mp4", "Content-Length": "8",
        "X-Media-Timestamp": "1577836800000", "X-Media-Length": "25000",
    }))
    recording = client(transport).download_event_video(past_event(), duration_ms=30_000, component_id="1")
    method, url, kwargs = transport.calls[0]
    assert method == "post"
    assert url == "https://api.amazonvision.com/v1/devices/device-1/media/video/download"
    assert kwargs["json"] == {"timestamp": 1577836800123, "duration": 30_000, "components": [{"component_id": "1"}]}
    assert kwargs["headers"]["Authorization"] == "Bearer test-access-token"
    assert kwargs["headers"]["User-Agent"] == "AccessAble/0.1"
    assert kwargs["headers"]["Hardware_Id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert kwargs["allow_redirects"] is False
    assert recording.media_bytes == SYNTHETIC_TEST_MP4
    assert recording.status == RecordingStatus.AVAILABLE
    assert recording.actual_duration_ms == 25_000
    assert recording.recording_id is None


def test_rejects_too_large_response_and_bad_event_type():
    oversized = FakeResponse(chunks=(b"1234", b"5678"))
    with pytest.raises(RecordingResponseError, match="size limit"):
        client(FakeTransport(oversized), max_bytes=5).download_event_video(past_event())
    with pytest.raises(RecordingUnavailableError, match="no documented recording"):
        client(FakeTransport()).download_event_video(EVENT | {"event_type": "device_offline"})
    with pytest.raises(RecordingResponseError, match="invalid MP4"):
        client(FakeTransport(FakeResponse(chunks=(b"not-an-mp4-container",)))).download_event_video(past_event())


def test_auth_failure_is_typed_and_errors_do_not_leak_token():
    transport = FakeTransport(FakeResponse(status=403))
    token = "private-test-token"
    with pytest.raises(RecordingAuthorizationError) as error:
        RingVideoClient(token, hardware_id="550e8400-e29b-41d4-a716-446655440000", transport=transport, clock=lambda: datetime(2026, 10, 23, tzinfo=timezone.utc)).download_event_video(past_event())
    assert token not in str(error.value)


def test_http_timeout_is_bounded_and_sanitized():
    class TimeoutTransport(FakeTransport):
        def post(self, url, **kwargs):
            self.calls.append(("post", url, kwargs))
            raise requests.Timeout("private signed URL should not escape")

    transport = TimeoutTransport()
    with pytest.raises(RecordingNetworkError) as error:
        client(transport, max_attempts=2, backoff_seconds=0, sleep=lambda _: None).download_event_video(past_event())
    assert len(transport.calls) == 2
    assert "private signed URL" not in str(error.value)


def test_media_not_found_is_typed_without_inventing_expiration():
    with pytest.raises(RecordingUnavailableError) as error:
        client(FakeTransport(FakeResponse(status=416))).download_event_video(past_event())
    assert error.value.status == RecordingStatus.NOT_FOUND

    recent = EVENT | {"occurred_at": "2026-10-22T23:59:00Z", "metadata": {}}
    with pytest.raises(RecordingUnavailableError) as recent_error:
        client(FakeTransport(FakeResponse(status=416))).download_event_video(recent, duration_ms=1000)
    assert recent_error.value.status == RecordingStatus.NOT_FOUND
    assert recent_error.value.retryable is True

    with pytest.raises(RecordingUnavailableError) as device_error:
        client(FakeTransport(FakeResponse(status=404))).download_event_video(past_event())
    assert device_error.value.status == RecordingStatus.DEVICE_NOT_FOUND

    with pytest.raises(RecordingUnavailableError) as corrupt_error:
        client(FakeTransport(FakeResponse(status=422))).download_event_video(past_event())
    assert corrupt_error.value.status == RecordingStatus.CORRUPT


def test_future_clip_is_not_requested_and_not_ready_is_distinct():
    transport = FakeTransport()
    future_event = EVENT | {"occurred_at": "2026-10-23T00:00:00Z", "metadata": {}}
    with pytest.raises(RecordingUnavailableError, match="range has not ended"):
        client(transport).download_event_video(future_event)
    assert not transport.calls
    recently_ended = EVENT | {"occurred_at": "2026-10-22T23:59:57Z", "metadata": {}}
    with pytest.raises(RecordingUnavailableError, match="processing delay"):
        client(transport).download_event_video(recently_ended, duration_ms=1000)
    assert not transport.calls
    with pytest.raises(RecordingUnavailableError) as error:
        client(FakeTransport(FakeResponse(status=425))).download_event_video(past_event())
    assert error.value.status == RecordingStatus.NOT_READY


def test_transient_server_error_retries_with_cap(monkeypatch):
    first = FakeResponse(status=503)
    success = FakeResponse()
    transport = FakeTransport(first, success)
    sleeps = []
    monkeypatch.setattr("integrations.ring.app.ring_client.random.uniform", lambda *_: 0)
    result = client(transport, max_attempts=2, backoff_seconds=0.1, sleep=sleeps.append).download_event_video(past_event())
    assert result.media_bytes == SYNTHETIC_TEST_MP4
    assert len(transport.calls) == 2 and sleeps == [0.1]


def test_ring_429_respects_retry_after_and_defers_long_wait_to_job_queue():
    sleeps = []
    transport = FakeTransport(FakeResponse(status=429, headers={"Retry-After": "1"}), FakeResponse())
    result = client(transport, max_attempts=2, sleep=sleeps.append).download_event_video(past_event())
    assert result.status == RecordingStatus.AVAILABLE
    assert sleeps == [1.0]

    transport = FakeTransport(FakeResponse(status=429, headers={"Retry-After": "60"}))
    with pytest.raises(RecordingRateLimitedError) as error:
        client(transport, max_attempts=3).download_event_video(past_event())
    assert error.value.retry_after_seconds == 60
    assert len(transport.calls) == 1


def test_redirect_requires_https_allowlist_and_never_forwards_bearer_token():
    location = "https://media.example.test/signed?secret=not-logged"
    transport = FakeTransport(FakeResponse(status=303, headers={"Location": location}), FakeResponse())
    with pytest.raises(UnsafeRecordingRedirect):
        client(transport).download_event_video(past_event())
    assert len(transport.calls) == 1

    transport = FakeTransport(
        FakeResponse(status=303, headers={"Location": location}),
        FakeResponse(headers={"Content-Type": "video/mp4", "Content-Length": str(len(SYNTHETIC_TEST_MP4))}, chunks=(SYNTHETIC_TEST_MP4,)),
    )
    rec = client(transport, allowed_redirect_hosts={"media.example.test"}).download_event_video(past_event())
    method, _, kwargs = transport.calls[1]
    assert method == "get" and "headers" not in kwargs
    assert rec.media_bytes == SYNTHETIC_TEST_MP4


def test_metadata_summary_does_not_claim_video_observations():
    result = metadata_summary(EVENT).to_dict()
    assert result["evidence_type"] == "event_metadata"
    assert result["observed_actions"] == []
    assert "No video was supplied" in result["limitations"][0]
    assert "Motion detected" in result["summary"]


def test_synthetic_video_is_passed_to_explicit_mock_provider():
    seen = []

    class Provider:
        def summarize_video(self, video_bytes, event_context):
            seen.append((video_bytes, event_context["external_event_id"]))
            return {"summary": "A synthetic test provider received bytes.", "observed_actions": ["test fixture supplied"], "uncertainties": [], "confidence": 0.2, "limitations": []}

    result = summarize_event(EVENT, video_bytes=b"synthetic-video-bytes", provider=Provider())
    assert seen == [(b"synthetic-video-bytes", "req-1")]
    assert result.evidence_type == "video" and result.recording_available is True
    assert result.confidence == 0.2


def test_video_without_provider_is_explicitly_unavailable_and_malformed_provider_rejected():
    result = summarize_event(EVENT, video_bytes=b"synthetic-video")
    assert result.status == SummaryStatus.UNAVAILABLE
    assert result.evidence_type == "event_metadata"

    class BadProvider:
        def summarize_video(self, *args):
            return {"summary": "bad", "observed_actions": "not-a-list"}

    with pytest.raises(ValueError, match="malformed"):
        summarize_event(EVENT, video_bytes=b"synthetic-video", provider=BadProvider())


def test_provider_error_is_failure_without_video_description():
    class BrokenProvider:
        def summarize_video(self, *args):
            raise RuntimeError("should not be exposed")

    result = summarize_event(EVENT, video_bytes=b"synthetic", provider=BrokenProvider())
    assert result.status == SummaryStatus.FAILED
    assert result.evidence_type == "event_metadata"
    assert "should not be exposed" not in str(result.to_dict())


def test_importance_has_configurable_transparent_repetition_and_missing_metadata():
    recent = [
        EVENT | {
            "external_event_id": f"req-{index}",
            "occurred_at": "2026-10-20T09:55:00Z",
        }
        for index in range(6)
    ]
    rules = ImportanceRules(event_points={"motion": 15}, repeat_points=3, max_repeat_points=6)
    ranked = rank_importance(EVENT, recent_events=recent, rules=rules)
    assert ranked["importance_score"] == 21
    assert ranked["repeat_count"] == 5 and ranked["repeat_points"] == 6
    assert ranked["confidence"] == "metadata_based"
    missing = rank_importance({"event_type": "motion"})
    assert missing["confidence"] == "metadata_only"
    assert missing["importance_score"] == 20


def test_processing_is_idempotent_and_preserves_event_if_retrieval_fails():
    store = InMemoryProcessingStore()
    calls = []

    class FailingRecording:
        def get_video(self, event):
            calls.append(event["external_event_id"])
            raise RuntimeError("private transport detail")

    first = process_event(EVENT, store=store, recording_source=FailingRecording())
    second = process_event(EVENT, store=store, recording_source=FailingRecording())
    assert first.status == SummaryStatus.COMPLETED
    assert first.event == EVENT
    assert first.summary.evidence_type == "event_metadata"
    assert "retrieval failed" in first.summary.limitations[-1]
    assert calls == ["req-1"]
    assert second == first


def test_sqlite_pipeline_deduplicates_concurrently_and_recovers_queued_job_after_restart(tmp_path):
    database = tmp_path / "pipeline.sqlite3"
    store = SQLitePipelineStore(database)
    now = datetime(2026, 10, 23, tzinfo=timezone.utc)
    event = EVENT | {"occurred_at": "2026-10-22T10:00:00Z"}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: store.enqueue(event, now=now), range(16)))
    assert sum(created for _, created in results) == 1
    assert all(key == "ring:req-1" for key, _ in results)
    store.close()

    fixture = make_color_card_video()

    class Retriever:
        calls = 0
        components = []

        def download_event_video(self, event, *, duration_ms, component_id=None):
            self.calls += 1
            self.components.append(component_id)
            return RecordingMetadata(
                external_event_id=event["external_event_id"],
                device_id=event["device_id"],
                recording_id=None,
                started_at=datetime.fromisoformat(event["occurred_at"].replace("Z", "+00:00")),
                requested_duration_ms=duration_ms,
                actual_duration_ms=1000,
                status=RecordingStatus.AVAILABLE,
                mime_type="video/mp4",
                retrieved_at=now,
                media_bytes=fixture,
                component_id=component_id,
            )

    retriever = Retriever()
    provider = SyntheticFixtureInspector()
    restarted_store = SQLitePipelineStore(database)
    worker = SQLiteSummaryWorker(
        restarted_store,
        recording_retriever=retriever,
        summary_provider=provider,
        recording_duration_ms=1000,
    )
    completed = worker.run_once("worker-after-restart", now=now)
    assert completed["status"] == "completed"
    assert completed["summary"]["provider_name"] == "synthetic_fixture_inspector"
    assert "red, blue, then green" in completed["summary"]["summary"]
    assert completed["summary"]["evidence_type"] == "video"
    assert retriever.calls == 1
    assert retriever.components == ["1"]

    timeline = restarted_store.list_timeline(date.fromisoformat("2026-10-22"), sort="importance")
    assert len(timeline["items"]) == 1
    assert timeline["items"][0]["status"] == "completed"
    assert timeline["items"][0]["summary"]["provider_name"] == provider.provider_name
    assert timeline["items"][0]["recording"]["bytes_persisted"] is False
    assert timeline["items"][0]["recording"]["component_id"] == "1"
    assert worker.run_once("worker-again", now=now) is None


def test_sqlite_pipeline_retries_transient_recording_failure_with_bounded_attempts(tmp_path):
    store = SQLitePipelineStore(tmp_path / "retry.sqlite3")
    event = EVENT | {"occurred_at": "2026-10-22T10:00:00Z"}
    now = datetime(2026, 10, 23, tzinfo=timezone.utc)
    store.enqueue(event, now=now)

    class FailingRetriever:
        calls = 0

        def download_event_video(self, event, *, duration_ms, component_id=None):
            self.calls += 1
            raise RecordingNetworkError("private URL must not persist")

    retriever = FailingRetriever()
    worker = SQLiteSummaryWorker(
        store,
        recording_retriever=retriever,
        summary_provider=None,
        max_attempts=2,
        retry_delay_seconds=10,
    )
    first = worker.run_once("bounded-worker", now=now)
    assert first["status"] == "pending" and first["attempt_count"] == 1
    assert "private URL" not in str(first)
    second = worker.run_once("bounded-worker", now=now + timedelta(seconds=11))
    assert second["status"] == "failed" and second["attempt_count"] == 2
    assert retriever.calls == 2
    assert worker.run_once("bounded-worker", now=now + timedelta(days=1)) is None


def test_provider_failure_persists_no_visual_description_and_no_media(tmp_path):
    store = SQLitePipelineStore(tmp_path / "provider-error.sqlite3")
    event = EVENT | {"occurred_at": "2026-10-22T10:00:00Z"}
    now = datetime(2026, 10, 23, tzinfo=timezone.utc)
    store.enqueue(event, now=now)
    fixture = make_color_card_video()

    class Retriever:
        def download_event_video(self, event, *, duration_ms, component_id=None):
            return RecordingMetadata(
                external_event_id=event["external_event_id"], device_id=event["device_id"], recording_id=None,
                started_at=now, requested_duration_ms=duration_ms, actual_duration_ms=1000,
                status=RecordingStatus.AVAILABLE, mime_type="video/mp4", retrieved_at=now, media_bytes=fixture,
            )

    class BrokenProvider:
        def summarize_video(self, video_bytes, event_context):
            raise RuntimeError("do not persist provider response details")

    result = SQLiteSummaryWorker(
        store, recording_retriever=Retriever(), summary_provider=BrokenProvider(),
    ).run_once("provider-failure", now=now)
    assert result["status"] == "failed"
    assert result["summary"]["evidence_type"] == "event_metadata"
    assert result["summary"]["observed_actions"] == []
    assert result["recording"]["bytes_persisted"] is False
    assert "do not persist" not in str(result)


def test_transient_provider_failure_is_retried_and_bounded(tmp_path):
    store = SQLitePipelineStore(tmp_path / "provider-retry.sqlite3")
    event = EVENT | {"occurred_at": "2026-10-22T10:00:00Z"}
    now = datetime(2026, 10, 23, tzinfo=timezone.utc)
    store.enqueue(event, now=now)
    fixture = make_color_card_video()

    class Retriever:
        def download_event_video(self, event, *, duration_ms, component_id=None):
            return RecordingMetadata(
                external_event_id=event["external_event_id"], device_id=event["device_id"], recording_id=None,
                started_at=now, requested_duration_ms=duration_ms, actual_duration_ms=1000,
                status=RecordingStatus.AVAILABLE, mime_type="video/mp4", retrieved_at=now, media_bytes=fixture,
            )

    class TransientThenSuccess:
        calls = 0

        def summarize_video(self, video_bytes, event_context):
            self.calls += 1
            if self.calls == 1:
                raise VisionProviderTemporaryError("transient details stay private")
            return SyntheticFixtureInspector().summarize_video(video_bytes, event_context)

    provider = TransientThenSuccess()
    worker = SQLiteSummaryWorker(
        store, recording_retriever=Retriever(), summary_provider=provider,
        max_attempts=2, retry_delay_seconds=5,
    )
    first = worker.run_once("provider-retry", now=now)
    assert first["status"] == "pending" and first["attempt_count"] == 1
    assert first["summary"] is None and "transient details" not in str(first)
    second = worker.run_once("provider-retry", now=now + timedelta(seconds=6))
    assert second["status"] == "completed" and second["attempt_count"] == 2
    assert provider.calls == 2


def test_worker_does_not_guess_between_multiple_ring_camera_components(tmp_path):
    store = SQLitePipelineStore(tmp_path / "multi-component.sqlite3")
    event = EVENT | {
        "occurred_at": "2026-10-22T10:00:00Z",
        "metadata": {"component_ids": ["1", "2"]},
    }
    now = datetime(2026, 10, 23, tzinfo=timezone.utc)
    store.enqueue(event, now=now)

    class MustNotRetrieve:
        calls = 0

        def download_event_video(self, event, **kwargs):
            self.calls += 1
            raise AssertionError("worker must not choose one camera module")

    retriever = MustNotRetrieve()
    result = SQLiteSummaryWorker(
        store, recording_retriever=retriever, summary_provider=None,
    ).run_once("multi-component", now=now)
    assert result["status"] == "unavailable"
    assert result["error_category"] == "recording_unsupported"
    assert retriever.calls == 0


def test_openai_frame_adapter_sends_ordered_bounded_images_and_validates_response():
    class Sampler:
        def sample(self, video_bytes, duration_ms):
            assert video_bytes.startswith(b"\x00\x00\x00\x18ftyp")
            assert duration_ms == 3000
            return [
                SampledFrame(timestamp, "image/jpeg", b"\xff\xd8\xff\xe0synthetic-jpeg")
                for timestamp in (750, 1500, 2250)
            ]

    class Response:
        status_code = 200

        def json(self):
            return {
                "status": "completed",
                "output": [{"type": "message", "content": [{
                    "type": "output_text",
                    "text": '{"summary":"Synthetic adapter test.","observed_actions":[],"uncertainties":[],"confidence":0.5,"limitations":[]}',
                }]}],
            }

    class Transport:
        calls = []

        def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return Response()

    transport = Transport()
    provider = OpenAIFrameSummaryProvider(
        "offline-test-key", enabled=True, sampler=Sampler(), transport=transport,
    )
    result = provider.summarize_video(b"\x00\x00\x00\x18ftypfake-bounded-fixture", {
        "recording_duration_ms": 3000, "event_type": "motion", "occurred_at": "2026-10-22T10:00:00Z",
    })
    url, kwargs = transport.calls[0]
    assert url == "https://api.openai.com/v1/responses"
    assert kwargs["json"]["model"] == "gpt-6-luna"
    assert kwargs["json"]["store"] is False
    assert kwargs["allow_redirects"] is False
    sent = kwargs["json"]["input"][0]["content"]
    assert [part["type"] for part in sent].count("input_image") == 3
    assert "750, 1500, 2250" in sent[0]["text"]
    assert result["provider_name"] == "openai" and result["model_id"] == "gpt-6-luna"


def test_openai_provider_is_off_by_default_and_requires_explicit_credentials():
    assert create_configured_provider({}) is None
    with pytest.raises(VisionProviderConfigurationError, match="OPENAI_API_KEY"):
        create_configured_provider({"RING_AI_ENABLED": "true"})
    with pytest.raises(VisionProviderConfigurationError, match="integer"):
        create_configured_provider({
            "RING_AI_ENABLED": "true", "OPENAI_API_KEY": "offline-test-key",
            "RING_FRAME_SAMPLE_COUNT": "many",
        })
