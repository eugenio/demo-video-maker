"""Tests for demo_video_maker.narration_export."""

from __future__ import annotations

import json
from pathlib import Path

from demo_video_maker.models import Manifest, StepResult
from demo_video_maker.narration_export import export_narration_json


class TestExportNarrationJson:
    """Tests for narration JSON export."""

    def test_basic_export(self, tmp_path: Path) -> None:
        manifest = Manifest(
            title="Demo",
            steps=[
                StepResult(index=0, frame_path="f0.png", narration="First step", duration=2.0),
                StepResult(index=1, frame_path="f1.png", narration="Second step", duration=3.0),
            ],
        )
        output = tmp_path / "narration.json"
        result = export_narration_json(manifest, output)

        assert result == output
        data = json.loads(output.read_text())
        assert data["title"] == "Demo"
        assert data["totalDurationMs"] == 5000
        assert len(data["segments"]) == 2

    def test_segment_timing(self, tmp_path: Path) -> None:
        manifest = Manifest(
            title="Test",
            steps=[
                StepResult(index=0, frame_path="f0.png", narration="A", duration=2.0),
                StepResult(index=1, frame_path="f1.png", narration="B", duration=3.0),
            ],
        )
        output = tmp_path / "narration.json"
        export_narration_json(manifest, output)
        data = json.loads(output.read_text())

        seg0 = data["segments"][0]
        assert seg0["stepId"] == 1
        assert seg0["startMs"] == 0
        assert seg0["endMs"] == 2000
        assert seg0["durationMs"] == 2000
        assert seg0["text"] == "A"

        seg1 = data["segments"][1]
        assert seg1["stepId"] == 2
        assert seg1["startMs"] == 2000
        assert seg1["endMs"] == 5000

    def test_skips_steps_without_narration(self, tmp_path: Path) -> None:
        manifest = Manifest(
            title="Test",
            steps=[
                StepResult(index=0, frame_path="f0.png", narration="", duration=2.0),
                StepResult(index=1, frame_path="f1.png", narration="Only this", duration=3.0),
            ],
        )
        output = tmp_path / "narration.json"
        export_narration_json(manifest, output)
        data = json.loads(output.read_text())

        assert len(data["segments"]) == 1
        assert data["segments"][0]["text"] == "Only this"
        assert data["totalDurationMs"] == 5000

    def test_empty_manifest(self, tmp_path: Path) -> None:
        manifest = Manifest(title="Empty", steps=[])
        output = tmp_path / "narration.json"
        export_narration_json(manifest, output)
        data = json.loads(output.read_text())

        assert data["segments"] == []
        assert data["totalDurationMs"] == 0
