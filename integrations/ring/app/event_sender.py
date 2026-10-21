"""Send normalized events to the AccessAble API."""

import os
from typing import Any

import requests


def send_event(event: dict[str, Any], *, timeout: float = 10) -> dict[str, Any]:
    """POST one event to ``/api/v1/events`` on ``ACCESSABLE_API_URL``.

    ACCESSABLE_API_URL is the backend origin, for example
    ``http://localhost:8000``. HTTP and connection errors from requests are
    allowed to propagate to the caller.
    """
    base_url = os.getenv("ACCESSABLE_API_URL")
    if not base_url:
        raise RuntimeError("ACCESSABLE_API_URL is not configured")

    response = requests.post(
        f"{base_url.rstrip('/')}/api/v1/events",
        json=event,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()
