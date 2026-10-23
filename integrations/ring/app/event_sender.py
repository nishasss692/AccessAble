"""Send normalized events to the AccessAble API."""

import os
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import requests


class EventSendError(RuntimeError):
    """Sanitized event delivery failure with retryability information."""

    def __init__(self, message: str, *, retryable: bool, status_code: int | None = None,
                 retry_after_seconds: float | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def send_event(
    event: dict[str, Any], *, timeout: float = 10, max_attempts: int = 3,
    backoff_seconds: float = 0.25, max_retry_after_seconds: float = 30.0,
) -> dict[str, Any]:
    """POST one event to ``/api/v1/events`` on ``ACCESSABLE_API_URL``.

    ACCESSABLE_API_URL is the backend origin, for example
    ``http://localhost:8000``. Transient failures are retried with a bounded
    policy; terminal failures use sanitized ``EventSendError`` values.
    """
    base_url = os.getenv("ACCESSABLE_API_URL")
    if not base_url:
        raise RuntimeError("ACCESSABLE_API_URL is not configured")

    if not isinstance(max_attempts, int) or max_attempts < 1 or max_attempts > 5:
        raise ValueError("max_attempts must be between 1 and 5")
    url = f"{base_url.rstrip('/')}/api/v1/events"
    for attempt in range(max_attempts):
        try:
            response = requests.post(url, json=event, timeout=timeout, allow_redirects=False)
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt + 1 == max_attempts:
                raise EventSendError("AccessAble backend is unavailable", retryable=True) from None
            time.sleep(backoff_seconds * (2 ** attempt) + random.uniform(0, backoff_seconds * 0.1))
            continue
        if response.status_code == 429:
            retry_after = _retry_after_seconds(response.headers.get("Retry-After"))
            if attempt + 1 == max_attempts or (retry_after is not None and retry_after > max_retry_after_seconds):
                raise EventSendError("AccessAble backend rate limited event delivery", retryable=True,
                                     status_code=429, retry_after_seconds=retry_after)
            delay = retry_after if retry_after is not None else backoff_seconds * (2 ** attempt)
            delay = min(delay, max_retry_after_seconds)
            time.sleep(delay + (random.uniform(0, min(backoff_seconds * 0.1, 0.5)) if retry_after is None else 0))
            continue
        if response.status_code >= 500:
            if attempt + 1 == max_attempts:
                raise EventSendError("AccessAble backend returned a server error", retryable=True, status_code=response.status_code)
            time.sleep(backoff_seconds * (2 ** attempt) + random.uniform(0, backoff_seconds * 0.1))
            continue
        if response.status_code >= 400:
            raise EventSendError("AccessAble backend rejected the event", retryable=False, status_code=response.status_code)
        try:
            payload = response.json()
        except ValueError:
            raise EventSendError("AccessAble backend returned an invalid response", retryable=False, status_code=response.status_code) from None
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("event"), dict)
            or not isinstance(payload.get("is_duplicate"), bool)
        ):
            raise EventSendError("AccessAble backend returned an unexpected response", retryable=False, status_code=response.status_code)
        return payload
    raise EventSendError("AccessAble backend is unavailable", retryable=True)
