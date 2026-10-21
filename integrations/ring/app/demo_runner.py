"""Explicitly send the checked-in simulated event fixture."""

import json
from pathlib import Path
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
    result = send_event(load_demo_event())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
