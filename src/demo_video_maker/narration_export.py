"""Narration timing JSON export (DemoSmith-compatible format)."""

from __future__ import annotations

import json
from pathlib import Path

from demo_video_maker.models import Manifest


def export_narration_json(manifest: Manifest, output_path: Path) -> Path:
    """Export narration timing data as a structured JSON file.

    Produces a format compatible with DemoSmith's narration.json,
    enabling interoperability with external TTS and subtitle tools.

    Args:
        manifest: Recording manifest with narration and timing data.
        output_path: Path to write the narration JSON file.

    Returns:
        Path to the created JSON file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    segments: list[dict[str, object]] = []
    cumulative_ms = 0

    for step in manifest.steps:
        start_ms = cumulative_ms
        duration_ms = int(step.duration * 1000)
        end_ms = start_ms + duration_ms
        cumulative_ms = end_ms

        if not step.narration:
            continue

        segments.append({
            "stepId": step.index + 1,
            "startMs": start_ms,
            "endMs": end_ms,
            "durationMs": duration_ms,
            "text": step.narration,
        })

    data = {
        "title": manifest.title,
        "totalDurationMs": cumulative_ms,
        "segments": segments,
    }

    output_path.write_text(json.dumps(data, indent=2))
    return output_path
