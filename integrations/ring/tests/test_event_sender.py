import requests
import pytest

from integrations.ring.app import event_sender


class FakeResponse:
    def __init__(self, payload=None, error=None):
        self.payload = payload or {}
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.payload


def test_send_event_posts_to_configured_api_and_returns_json(monkeypatch):
    calls = []
    payload = {"id": 7, "source": "demo"}
    monkeypatch.setenv("ACCESSABLE_API_URL", "http://localhost:8000/")
    monkeypatch.setattr(
        event_sender.requests,
        "post",
        lambda *args, **kwargs: (calls.append((args, kwargs)) or FakeResponse(payload)),
    )

    result = event_sender.send_event({"source": "demo"})

    assert result == payload
    assert calls[0][0][0] == "http://localhost:8000/api/v1/events"
    assert calls[0][1]["json"] == {"source": "demo"}
    assert calls[0][1]["timeout"] == 10


def test_send_event_propagates_http_errors(monkeypatch):
    monkeypatch.setenv("ACCESSABLE_API_URL", "http://localhost:8000")
    error = requests.HTTPError("bad response")
    monkeypatch.setattr(
        event_sender.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(error=error),
    )

    with pytest.raises(requests.HTTPError, match="bad response"):
        event_sender.send_event({"source": "demo"})


def test_send_event_propagates_connection_failures(monkeypatch):
    monkeypatch.setenv("ACCESSABLE_API_URL", "http://localhost:8000")

    def fail(*args, **kwargs):
        raise requests.ConnectionError("server unavailable")

    monkeypatch.setattr(event_sender.requests, "post", fail)
    with pytest.raises(requests.ConnectionError, match="server unavailable"):
        event_sender.send_event({"source": "demo"})


def test_send_event_requires_api_url(monkeypatch):
    monkeypatch.delenv("ACCESSABLE_API_URL", raising=False)
    with pytest.raises(RuntimeError, match="ACCESSABLE_API_URL"):
        event_sender.send_event({"source": "demo"})
