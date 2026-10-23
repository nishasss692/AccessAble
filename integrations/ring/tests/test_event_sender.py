import requests
import pytest

from integrations.ring.app import event_sender


class FakeResponse:
    def __init__(self, status_code=201, payload=None, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.payload = payload or {"event": {"id": 1}, "is_duplicate": False}

    def json(self):
        return self.payload


def test_send_event_posts_to_configured_api(monkeypatch):
    calls = []
    monkeypatch.setenv("ACCESSABLE_API_URL", "http://localhost:8000/")
    monkeypatch.setattr(event_sender.requests, "post", lambda *a, **kw: calls.append((a, kw)) or FakeResponse())
    assert event_sender.send_event({"source": "demo"}) == {"event": {"id": 1}, "is_duplicate": False}
    assert calls[0][0][0] == "http://localhost:8000/api/v1/events"
    assert calls[0][1]["timeout"] == 10
    assert calls[0][1]["allow_redirects"] is False


def test_4xx_is_permanent_and_sanitized(monkeypatch):
    monkeypatch.setenv("ACCESSABLE_API_URL", "http://localhost:8000")
    monkeypatch.setattr(event_sender.requests, "post", lambda *a, **kw: FakeResponse(422))
    with pytest.raises(event_sender.EventSendError) as err:
        event_sender.send_event({"source": "demo"})
    assert not err.value.retryable
    assert err.value.status_code == 422


@pytest.mark.parametrize("failure", [requests.Timeout, requests.ConnectionError])
def test_transport_failure_retries_bounded_with_same_id(monkeypatch, failure):
    monkeypatch.setenv("ACCESSABLE_API_URL", "http://localhost:8000")
    seen = []
    sleeps = []
    def post(_url, *, json, timeout, allow_redirects):
        seen.append(json["external_event_id"])
        if len(seen) < 3:
            raise failure("may contain private URL detail")
        return FakeResponse()
    monkeypatch.setattr(event_sender.requests, "post", post)
    monkeypatch.setattr(event_sender.time, "sleep", sleeps.append)
    monkeypatch.setattr(event_sender.random, "uniform", lambda *_: 0)
    event_sender.send_event({"external_event_id": "stable-id"}, backoff_seconds=0.1)
    assert seen == ["stable-id"] * 3
    assert sleeps == [0.1, 0.2]


def test_5xx_retries_then_returns_retryable_sanitized_error(monkeypatch):
    monkeypatch.setenv("ACCESSABLE_API_URL", "http://localhost:8000")
    calls = []
    monkeypatch.setattr(event_sender.requests, "post", lambda *a, **kw: calls.append(1) or FakeResponse(503))
    monkeypatch.setattr(event_sender.time, "sleep", lambda _: None)
    monkeypatch.setattr(event_sender.random, "uniform", lambda *_: 0)
    with pytest.raises(event_sender.EventSendError) as err:
        event_sender.send_event({"external_event_id": "same"}, max_attempts=3)
    assert err.value.retryable and err.value.status_code == 503
    assert len(calls) == 3


def test_429_respects_retry_after_and_retries_same_event(monkeypatch):
    monkeypatch.setenv("ACCESSABLE_API_URL", "http://localhost:8000")
    calls, sleeps = [], []
    responses = [FakeResponse(429, headers={"Retry-After": "2"}), FakeResponse()]
    monkeypatch.setattr(event_sender.requests, "post", lambda *_a, **_kw: calls.append(1) or responses.pop(0))
    monkeypatch.setattr(event_sender.time, "sleep", sleeps.append)
    result = event_sender.send_event({"external_event_id": "same"}, max_attempts=2)
    assert result["is_duplicate"] is False
    assert len(calls) == 2 and sleeps == [2.0]


def test_excessive_retry_after_returns_retryable_without_early_retry(monkeypatch):
    monkeypatch.setenv("ACCESSABLE_API_URL", "http://localhost:8000")
    calls = []
    monkeypatch.setattr(event_sender.requests, "post", lambda *_a, **_kw: calls.append(1) or FakeResponse(429, headers={"Retry-After": "60"}))
    with pytest.raises(event_sender.EventSendError) as err:
        event_sender.send_event({"external_event_id": "same"}, max_retry_after_seconds=30)
    assert err.value.retryable and err.value.retry_after_seconds == 60
    assert calls == [1]


def test_send_event_requires_url(monkeypatch):
    monkeypatch.delenv("ACCESSABLE_API_URL", raising=False)
    with pytest.raises(RuntimeError, match="ACCESSABLE_API_URL"):
        event_sender.send_event({"source": "demo"})


def test_duplicate_response_is_validated_and_returned(monkeypatch):
    monkeypatch.setenv("ACCESSABLE_API_URL", "http://localhost:8000")
    duplicate = {"event": {"id": 12}, "is_duplicate": True}
    monkeypatch.setattr(event_sender.requests, "post", lambda *a, **kw: FakeResponse(200, duplicate))
    assert event_sender.send_event({"external_event_id": "same"}) == duplicate


def test_unexpected_success_response_is_permanent_error(monkeypatch):
    monkeypatch.setenv("ACCESSABLE_API_URL", "http://localhost:8000")
    monkeypatch.setattr(event_sender.requests, "post", lambda *a, **kw: FakeResponse(201, {"ok": True}))
    with pytest.raises(event_sender.EventSendError, match="unexpected response"):
        event_sender.send_event({"source": "demo"})
