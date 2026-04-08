"""Tests for demo_video_maker.stitcher."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from demo_video_maker.models import Manifest, StepResult
from demo_video_maker.stitcher import _build_concat_file, stitch_video


class TestBuildConcatFile:
    """Tests for the _build_concat_file helper."""

    def test_creates_concat_file(self, tmp_path: Path) -> None:
        manifest = Manifest(
            title="Test",
            steps=[
                StepResult(index=0, frame_path="step_000.png", duration=2.0),
                StepResult(index=1, frame_path="step_001.png", duration=3.0),
            ],
        )
        concat_path = _build_concat_file(manifest, tmp_path)
        content = concat_path.read_text()

        assert "step_000.png'" in content
        assert "duration 2.0" in content
        assert "step_001.png'" in content
        assert "duration 3.0" in content
        # Last frame repeated — paths are absolute
        assert content.strip().endswith("step_001.png'")

    def test_empty_manifest(self, tmp_path: Path) -> None:
        manifest = Manifest(title="Empty", steps=[])
        concat_path = _build_concat_file(manifest, tmp_path)
        content = concat_path.read_text()
        assert content == ""


class TestStitchVideo:
    """Tests for the stitch_video function."""

    @patch("demo_video_maker.stitcher.subprocess.run")
    @patch("demo_video_maker.stitcher._merge_audio_tracks", return_value=None)
    def test_stitches_video_without_audio(
        self, mock_merge: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        manifest = Manifest(
            title="Test",
            steps=[
                StepResult(index=0, frame_path="step_000.png", duration=2.0),
            ],
        )
        output = tmp_path / "output.mp4"
        stitch_video(manifest, output, work_dir=tmp_path / "work")

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ffmpeg"
        assert str(output) in cmd
