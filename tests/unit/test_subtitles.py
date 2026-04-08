"""Tests for demo_video_maker.subtitles."""

from __future__ import annotations

from pathlib import Path

from demo_video_maker.models import Manifest, StepResult
from demo_video_maker.subtitles import (
    _format_srt_time,
    _format_vtt_time,
    generate_srt,
    generate_vtt,
)


class TestFormatSrtTime:
    """Tests for SRT timestamp formatting."""

    def test_zero(self) -> None:
        assert _format_srt_time(0.0) == "00:00:00,000"

    def test_seconds_and_millis(self) -> None:
        assert _format_srt_time(5.5) == "00:00:05,500"

    def test_minutes(self) -> None:
        assert _format_srt_time(125.25) == "00:02:05,250"

    def test_hours(self) -> None:
        assert _format_srt_time(3661.0) == "01:01:01,000"


class TestFormatVttTime:
    """Tests for VTT timestamp formatting."""

    def test_zero(self) -> None:
        assert _format_vtt_time(0.0) == "00:00:00.000"

    def test_uses_dot_separator(self) -> None:
        result = _format_vtt_time(5.5)
        assert "." in result
        assert "," not in result


class TestGenerateSrt:
    """Tests for SRT file generation."""

    def test_generates_srt_with_narration(self, tmp_path: Path) -> None:
        manifest = Manifest(
            title="Test",
            steps=[
                StepResult(index=0, frame_path="f0.png", narration="Hello", duration=2.0),
                StepResult(index=1, frame_path="f1.png", narration="World", duration=3.0),
            ],
        )
        output = tmp_path / "test.srt"
        result = generate_srt(manifest, output)

        assert result == output
        content = output.read_text()
        assert "1\n" in content
        assert "Hello" in content
        assert "2\n" in content
        assert "World" in content
        assert "00:00:00,000 --> 00:00:02,000" in content
        assert "00:00:02,000 --> 00:00:05,000" in content

    def test_skips_steps_without_narration(self, tmp_path: Path) -> None:
        manifest = Manifest(
            title="Test",
            steps=[
                StepResult(index=0, frame_path="f0.png", narration="", duration=2.0),
                StepResult(index=1, frame_path="f1.png", narration="Only this", duration=3.0),
            ],
        )
        output = tmp_path / "test.srt"
        generate_srt(manifest, output)

        content = output.read_text()
        assert "Only this" in content
        # Should be subtitle index 1, not 2 (skipped empty)
        assert content.startswith("1\n")

    def test_empty_manifest(self, tmp_path: Path) -> None:
        manifest = Manifest(title="Empty", steps=[])
        output = tmp_path / "test.srt"
        generate_srt(manifest, output)
        assert output.read_text() == ""


class TestGenerateVtt:
    """Tests for VTT file generation."""

    def test_starts_with_webvtt_header(self, tmp_path: Path) -> None:
        manifest = Manifest(
            title="Test",
            steps=[
                StepResult(index=0, frame_path="f0.png", narration="Hi", duration=2.0),
            ],
        )
        output = tmp_path / "test.vtt"
        generate_vtt(manifest, output)

        content = output.read_text()
        assert content.startswith("WEBVTT\n")

    def test_uses_dot_separator(self, tmp_path: Path) -> None:
        manifest = Manifest(
            title="Test",
            steps=[
                StepResult(index=0, frame_path="f0.png", narration="Hi", duration=2.0),
            ],
        )
        output = tmp_path / "test.vtt"
        generate_vtt(manifest, output)

        content = output.read_text()
        assert "00:00:00.000 --> 00:00:02.000" in content
