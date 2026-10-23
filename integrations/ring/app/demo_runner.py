"""Explicitly send the checked-in simulated event fixture."""

import json
import argparse
import os
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

from .event_sender import send_event
from .normalizer import normalize_event

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "sample_events.json"


def load_demo_event() -> dict[str, Any]:
    """Load and normalize the sample fixture, preserving its demo marker."""
    with FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
        raw_event = json.load(fixture_file)

    # The fixture notice is descriptive; ensure the actual API metadata marks
    # the payload as simulated even if the fixture is later edited.
    metadata = dict(raw_event.get("metadata") or {})
    metadata["is_simulated"] = True
    raw_event["metadata"] = metadata
    return normalize_event(raw_event, source="demo")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send one clearly marked synthetic AccessAble demo event.")
    parser.add_argument("--allow-remote", action="store_true", help="Allow sending to a non-local backend explicitly")
    args = parser.parse_args()
    base_url = os.getenv("ACCESSABLE_API_URL", "")
    if not base_url:
        parser.error("ACCESSABLE_API_URL is required")
    parsed = urlparse(base_url)
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        parser.error("ACCESSABLE_API_URL must be an HTTP(S) backend origin")
    if parsed.hostname not in local_hosts and not args.allow_remote:
        parser.error("Remote backend blocked; pass --allow-remote only when intentionally targeting a non-production test backend")
    try:
        result = send_event(load_demo_event())
    except Exception as exc:
        print(f"Synthetic demo delivery failed: {exc}")
        raise SystemExit(1) from None
    print("Synthetic demo event delivered; this is not a genuine Ring detection.")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
