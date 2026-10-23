"""Opt-in client for Ring's documented historical MP4 download operation.

Nothing in the webhook path calls this client. Callers supply an access token
obtained through an approved account-linking flow; tokens and signed redirect
URLs are never stored on returned recording objects or included in errors.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from enum import Enum
import random
import time
from typing import Any, Callable, Iterable, Protocol
from urllib.parse import quote, urlparse
from uuid import UUID

import requests


RING_API_BASE = "https://api.amazonvision.com"
MAX_DURATION_MS = 15 * 60 * 1000
DEFAULT_MAX_BYTES = 25 * 1024 * 1024


class RecordingStatus(str, Enum):
    AVAILABLE = "available"
    NOT_FOUND = "not_found"
    DEVICE_NOT_FOUND = "device_not_found"
    NOT_READY = "not_ready"
    EXPIRED = "expired"
    INACCESSIBLE = "inaccessible"
    UNSUPPORTED = "unsupported"
    CORRUPT = "corrupt"


@dataclass(frozen=True)
class RecordingMetadata:
    """Safe local descriptor. Does not retain credentials or signed URLs."""

    external_event_id: str
    device_id: str
    recording_id: None
    started_at: datetime
    requested_duration_ms: int
    actual_duration_ms: int | None
    status: RecordingStatus
    mime_type: str | None = None
    retrieved_at: datetime | None = None
    media_bytes: bytes | None = None
    limitation: str | None = None
    component_id: str | None = None


class RecordingError(RuntimeError):
    """Sanitized base error for media retrieval."""


class RecordingAuthorizationError(RecordingError):
    pass


class RecordingUnavailableError(RecordingError):
    def __init__(self, status: RecordingStatus, message: str, *, retryable: bool = False,
                 retry_after_seconds: float | None = None):
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds


class RecordingNetworkError(RecordingError):
    pass


class RecordingRateLimitedError(RecordingError):
    """Ring 429 response with a safe retry delay for durable job scheduling."""

    def __init__(self, retry_after_seconds: float):
        super().__init__("Ring rate limit reached; recording retrieval must be retried later")
        self.retry_after_seconds = retry_after_seconds


class RecordingResponseError(RecordingError):
    pass


class UnsafeRecordingRedirect(RecordingError):
    """Redirect destination is not explicitly permitted by local config."""


class HttpTransport(Protocol):
    def post(self, url: str, **kwargs: Any) -> Any: ...
    def get(self, url: str, **kwargs: Any) -> Any: ...


def _parse_event_time(event: dict[str, Any]) -> datetime:
    metadata = event.get("metadata")
    raw_ring_timestamp = metadata.get("timestamp") if isinstance(metadata, dict) else None
    if isinstance(raw_ring_timestamp, (int, float)) and not isinstance(raw_ring_timestamp, bool):
        if not math.isfinite(raw_ring_timestamp):
            raise ValueError("Event has no valid timestamp")
        try:
            return datetime.fromtimestamp(raw_ring_timestamp / 1000, tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as exc:
            raise ValueError("Event has no valid timestamp") from exc
    raw = event.get("occurred_at")
    if not isinstance(raw, str):
        raise ValueError("Event has no valid timestamp")
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Event has no valid timestamp") from exc
    if value.tzinfo is None:
        raise ValueError("Event timestamp must include a timezone")
    return value.astimezone(timezone.utc)


def _read_limited(response: Any, max_bytes: int) -> bytes:
    declared = response.headers.get("Content-Length")
    if declared is not None:
        try:
            if int(declared) > max_bytes:
                raise RecordingResponseError("Ring recording exceeds the configured size limit")
        except ValueError:
            raise RecordingResponseError("Ring recording has an invalid size header") from None
    chunks: list[bytes] = []
    size = 0
    try:
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            size += len(chunk)
            if size > max_bytes:
                raise RecordingResponseError("Ring recording exceeds the configured size limit")
            chunks.append(chunk)
    except RecordingResponseError:
        raise
    except requests.RequestException:
        raise RecordingNetworkError("Ring recording transfer failed") from None
    return b"".join(chunks)


class RingVideoClient:
    """Download one explicitly requested event-time clip using Ring's API.

    Redirects are followed only when their HTTPS hostname is explicitly listed
    in ``allowed_redirect_hosts``. The pre-signed URL is fetched without the
    Ring bearer token. Ring does not document a stable redirect-host list, so
    the default is to reject redirects until the operator verifies/configures it.
    """

    def __init__(
        self,
        access_token: str,
        *,
        hardware_id: str,
        user_agent: str = "AccessAble/0.1",
        transport: HttpTransport | None = None,
        connect_timeout: float = 3.05,
        read_timeout: float = 20.0,
        max_bytes: int = DEFAULT_MAX_BYTES,
        allowed_redirect_hosts: Iterable[str] = (),
        max_attempts: int = 1,
        backoff_seconds: float = 5.0,
        max_inline_retry_after_seconds: float = 5.0,
        clock: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not isinstance(access_token, str) or not access_token.strip():
            raise ValueError("A Ring access token is required")
        try:
            UUID(hardware_id)
        except (TypeError, ValueError, AttributeError):
            raise ValueError("hardware_id must be a UUID for the authorized user/device pair") from None
        if not isinstance(user_agent, str) or "/" not in user_agent or len(user_agent) > 120:
            raise ValueError("user_agent must identify the application and version")
        if connect_timeout <= 0 or read_timeout <= 0 or max_bytes <= 0:
            raise ValueError("Timeouts and max_bytes must be positive")
        if max_inline_retry_after_seconds < 0:
            raise ValueError("max_inline_retry_after_seconds must not be negative")
        if not isinstance(max_attempts, int) or not 1 <= max_attempts <= 5:
            raise ValueError("max_attempts must be between 1 and 5")
        hosts = {host.lower().rstrip(".") for host in allowed_redirect_hosts}
        if any(not host or "/" in host or ":" in host for host in hosts):
            raise ValueError("Redirect allowlist entries must be hostnames")
        self._access_token = access_token
        self._hardware_id = hardware_id
        self._user_agent = user_agent
        self._transport = transport or requests.Session()
        self._timeout = (connect_timeout, read_timeout)
        self._max_bytes = max_bytes
        self._allowed_redirect_hosts = hosts
        self._max_attempts = max_attempts
        self._backoff_seconds = max(0.0, backoff_seconds)
        self._max_inline_retry_after_seconds = max_inline_retry_after_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._sleep = sleep

    def _backoff_delay(self, attempt: int) -> float:
        base = self._backoff_seconds * (2 ** attempt)
        return base + random.uniform(0.0, base * 0.1)

    def download_event_video(
        self,
        event: dict[str, Any],
        *,
        duration_ms: int = 30_000,
        component_id: str | None = None,
    ) -> RecordingMetadata:
        """Request `[event time, event time + duration)` as MP4.

        This method performs no event-history lookup and does not claim that a
        clip exists. It is intentionally separate from webhook ingestion.
        """
        if not isinstance(event, dict):
            raise ValueError("Event must be an object")
        if event.get("source") != "ring":
            raise RecordingUnavailableError(RecordingStatus.UNSUPPORTED, "Only Ring events can request Ring recordings")
        if event.get("event_type") not in {"motion", "doorbell_press"}:
            raise RecordingUnavailableError(RecordingStatus.UNSUPPORTED, "This Ring event type has no documented recording")
        device_id = event.get("device_id")
        external_id = event.get("external_event_id")
        if not isinstance(device_id, str) or not device_id or not isinstance(external_id, str) or not external_id:
            raise ValueError("Event is missing its Ring device or delivery identifier")
        if not isinstance(duration_ms, int) or isinstance(duration_ms, bool) or not 0 < duration_ms <= MAX_DURATION_MS:
            raise ValueError("duration_ms must be between 1 and 900000")
        if component_id is not None and (not isinstance(component_id, str) or not component_id.strip()):
            raise ValueError("component_id must be a non-empty string")

        started_at = _parse_event_time(event)
        now = self._clock().astimezone(timezone.utc)
        range_ended_at = started_at.timestamp() + duration_ms / 1000
        if now.timestamp() < range_ended_at:
            raise RecordingUnavailableError(RecordingStatus.NOT_READY, "Requested recording range has not ended")
        if now.timestamp() < range_ended_at + 5:
            raise RecordingUnavailableError(RecordingStatus.NOT_READY, "Ring media processing delay has not elapsed")
        body: dict[str, Any] = {
            "timestamp": int(started_at.timestamp() * 1000),
            "duration": duration_ms,
        }
        if component_id is not None:
            body["components"] = [{"component_id": component_id}]
        url = f"{RING_API_BASE}/v1/devices/{quote(device_id, safe='')}/media/video/download"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "User-Agent": self._user_agent,
            "Hardware_Id": self._hardware_id,
        }

        for attempt in range(self._max_attempts):
            try:
                response = self._transport.post(
                    url, json=body, headers=headers, timeout=self._timeout,
                    allow_redirects=False, stream=True,
                )
            except (requests.Timeout, requests.ConnectionError, TimeoutError, OSError):
                if attempt + 1 == self._max_attempts:
                    raise RecordingNetworkError("Ring media service is unavailable") from None
                self._sleep(self._backoff_delay(attempt))
                continue

            try:
                status = response.status_code
                if status in {301, 302, 303, 307, 308}:
                    content, final_headers, final_status = self._fetch_redirect(response)
                    content_type = final_headers.get("Content-Type", "").split(";", 1)[0].lower()
                    if final_status == 206:
                        actual_duration = self._duration_header(final_headers, duration_ms)
                    else:
                        actual_duration = duration_ms
                    media_time = self._timestamp_header(final_headers, started_at)
                elif status in {200, 206}:
                    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
                    if content_type != "video/mp4":
                        raise RecordingResponseError("Ring returned an unsupported media type")
                    content = _read_limited(response, self._max_bytes)
                    actual_duration = self._duration_header(response.headers, duration_ms)
                    media_time = self._timestamp_header(response.headers, started_at)
                elif status in {401, 403}:
                    raise RecordingAuthorizationError("Ring authorization does not permit this recording")
                elif status == 429:
                    raw_retry_after = response.headers.get("Retry-After")
                    try:
                        retry_after = max(0.0, float(raw_retry_after)) if raw_retry_after is not None else max(1.0, self._backoff_seconds * (2 ** attempt))
                    except (TypeError, ValueError):
                        retry_after = max(1.0, self._backoff_seconds * (2 ** attempt))
                    if attempt + 1 == self._max_attempts or retry_after > self._max_inline_retry_after_seconds:
                        raise RecordingRateLimitedError(retry_after)
                    self._sleep(retry_after)
                    continue
                elif status == 404:
                    raise RecordingUnavailableError(RecordingStatus.DEVICE_NOT_FOUND, "Ring device was not found")
                elif status in {416, 425}:
                    now = self._clock().astimezone(timezone.utc)
                    retry_deadline = range_ended_at + 120
                    status_kind = RecordingStatus.NOT_FOUND if status == 416 else RecordingStatus.NOT_READY
                    if now.timestamp() > retry_deadline:
                        message = "No Ring recording exists for the requested time range" if status == 416 else "Ring recording is not ready yet"
                        raise RecordingUnavailableError(status_kind, message)
                    delay = self._backoff_delay(attempt)
                    if now.timestamp() + delay > retry_deadline:
                        message = "No Ring recording exists for the requested time range" if status == 416 else "Ring recording is not ready yet"
                        raise RecordingUnavailableError(status_kind, message)
                    if attempt + 1 == self._max_attempts:
                        message = "No Ring recording exists for the requested time range" if status == 416 else "Ring recording is not ready yet"
                        raise RecordingUnavailableError(
                            status_kind, message, retryable=True, retry_after_seconds=delay,
                        )
                    self._sleep(delay)
                    continue
                elif status == 422:
                    raise RecordingUnavailableError(RecordingStatus.CORRUPT, "Ring marked the recording as corrupt")
                elif status == 400:
                    raise RecordingResponseError("Ring rejected the recording request")
                elif status >= 500:
                    if attempt + 1 == self._max_attempts:
                        raise RecordingNetworkError("Ring media service returned a server error")
                    self._sleep(self._backoff_delay(attempt))
                    continue
                else:
                    raise RecordingResponseError("Ring media service returned an unexpected response")
                if not isinstance(content, bytes) or len(content) < 12 or content[4:8] != b"ftyp":
                    raise RecordingResponseError("Ring returned an invalid MP4 container")
                return RecordingMetadata(
                    external_event_id=external_id,
                    device_id=device_id,
                    recording_id=None,
                    started_at=media_time,
                    requested_duration_ms=duration_ms,
                    actual_duration_ms=actual_duration,
                    status=RecordingStatus.AVAILABLE,
                    mime_type=content_type,
                    retrieved_at=self._clock().astimezone(timezone.utc),
                    media_bytes=content,
                    component_id=component_id,
                )
            finally:
                close = getattr(response, "close", None)
                if callable(close):
                    close()
        raise RecordingNetworkError("Ring media service is unavailable")

    def _fetch_redirect(self, response: Any) -> tuple[bytes, dict[str, Any], int]:
        location = response.headers.get("Location")
        parsed = urlparse(location or "")
        host = (parsed.hostname or "").lower().rstrip(".")
        try:
            port = parsed.port
        except ValueError:
            port = -1
        if (
            parsed.scheme != "https" or not host or host not in self._allowed_redirect_hosts
            or parsed.username is not None or parsed.password is not None
            or port not in {None, 443}
        ):
            raise UnsafeRecordingRedirect("Ring media redirect host is not explicitly allowlisted")
        try:
            redirected = self._transport.get(location, timeout=self._timeout, allow_redirects=False, stream=True)
        except (requests.Timeout, requests.ConnectionError, TimeoutError, OSError):
            raise RecordingNetworkError("Ring recording transfer failed") from None
        try:
            if redirected.status_code in {301, 302, 303, 307, 308}:
                raise UnsafeRecordingRedirect("Nested media redirects are not permitted")
            if redirected.status_code not in {200, 206}:
                raise RecordingResponseError("Ring media redirect could not be retrieved")
            content_type = redirected.headers.get("Content-Type", "").split(";", 1)[0].lower()
            if content_type != "video/mp4":
                raise RecordingResponseError("Ring returned an unsupported media type")
            return _read_limited(redirected, self._max_bytes), dict(redirected.headers), redirected.status_code
        finally:
            close = getattr(redirected, "close", None)
            if callable(close):
                close()

    @staticmethod
    def _duration_header(headers: Any, default: int) -> int:
        raw = headers.get("X-Media-Length")
        if raw is None:
            return default
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise RecordingResponseError("Ring returned invalid media duration metadata") from None
        if value <= 0 or value > default:
            raise RecordingResponseError("Ring returned out-of-range media duration metadata")
        return value

    @staticmethod
    def _timestamp_header(headers: Any, default: datetime) -> datetime:
        raw = headers.get("X-Media-Timestamp")
        if raw is None:
            return default
        try:
            return datetime.fromtimestamp(int(raw) / 1000, tz=timezone.utc)
        except (TypeError, ValueError, OverflowError, OSError):
            raise RecordingResponseError("Ring returned invalid media timestamp metadata") from None
