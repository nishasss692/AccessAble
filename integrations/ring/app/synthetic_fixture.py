"""Generated, local-only synthetic MP4 fixture and fixture inspector.

This module is for offline tests and the demo. It does not generate Ring footage
or claim anything about a real scene.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any, Mapping

import av
from PIL import Image


def make_color_card_video() -> bytes:
    """Encode three simple color cards into a tiny, valid synthetic MP4."""
    output = BytesIO()
    with av.open(output, mode="w", format="mp4") as container:
        stream = container.add_stream("libx264", rate=2)
        stream.width = 64
        stream.height = 64
        stream.pix_fmt = "yuv420p"
        for color in ("red", "blue", "green"):
            frame = av.VideoFrame.from_image(Image.new("RGB", (64, 64), color))
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    video = output.getvalue()
    if len(video) < 12 or video[4:8] != b"ftyp":
        raise RuntimeError("Synthetic fixture encoder did not create an MP4")
    return video


class SyntheticFixtureInspector:
    """Mock provider that decodes frames and reports only known test cards."""

    provider_name = "synthetic_fixture_inspector"
    model = "local-test-fixture"

    def summarize_video(self, video_bytes: bytes, event_context: Mapping[str, Any]) -> dict[str, Any]:
        with av.open(BytesIO(video_bytes), mode="r") as container:
            frames = list(container.decode(video=0))
        if len(frames) != 3:
            raise ValueError("Expected exactly three generated fixture frames")
        center_rgb = [frame.to_image().convert("RGB").getpixel((32, 32)) for frame in frames]
        colors = []
        for red, green, blue in center_rgb:
            colors.append(max((("red", red), ("green", green), ("blue", blue)), key=lambda item: item[1])[0])
        if colors != ["red", "blue", "green"]:
            raise ValueError("Generated fixture frames did not match expected color cards")
        return {
            "summary": "Synthetic test clip decoded into red, blue, then green color cards; no real scene was analyzed.",
            "observed_actions": [],
            "uncertainties": ["This is generated test footage and has no real-world event content."],
            "confidence": 1.0,
            "limitations": ["Synthetic fixture only; this is not an AI-generated Ring event summary."],
            "provider_name": self.provider_name,
            "model_id": self.model,
        }
