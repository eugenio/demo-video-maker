"""Tests for demo_video_maker.gif."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from demo_video_maker.gif import generate_gif
from demo_video_maker.models import Manifest, StepResult


class TestGenerateGif:
    """Tests for GIF generation."""

    @patch("demo_video_maker.gif.subprocess.run")
    def test_calls_ffmpeg_twice(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Two-pass pipeline: palettegen + paletteuse."""
        manifest = Manifest(
            title="Test",
            steps=[
                StepResult(index=0, frame_path="step_000.png", duration=2.0),
                StepResult(index=1, frame_path="step_001.png", duration=3.0),
            ],
        )
        output = tmp_path / "out.gif"
        generate_gif(manifest, output)

        assert mock_run.call_count == 2
        # Pass 1: palettegen
        cmd1 = mock_run.call_args_list[0][0][0]
        assert "palettegen" in " ".join(cmd1)
        # Pass 2: paletteuse
        cmd2 = mock_run.call_args_list[1][0][0]
        assert "paletteuse" in " ".join(cmd2)

    @patch("demo_video_maker.gif.subprocess.run")
    def test_creates_concat_file(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Verify concat demuxer file is written with frame paths and durations."""
        manifest = Manifest(
            title="Test",
            steps=[
                StepResult(index=0, frame_path="step_000.png", duration=2.0),
            ],
        )
        output = tmp_path / "out.gif"
        generate_gif(manifest, output)

        concat_file = tmp_path / ".gif_work" / "gif_concat.txt"
        assert concat_file.exists()
        content = concat_file.read_text()
        assert "step_000.png" in content
        assert "duration 2.0" in content

    @patch("demo_video_maker.gif.subprocess.run")
    def test_custom_width(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Verify custom width is passed to ffmpeg scale filter."""
        manifest = Manifest(
            title="Test",
            steps=[StepResult(index=0, frame_path="f.png", duration=1.0)],
        )
        generate_gif(manifest, tmp_path / "out.gif", width=320)

        cmd2 = mock_run.call_args_list[1][0][0]
        assert "scale=320" in " ".join(cmd2)
