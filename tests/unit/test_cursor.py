"""Tests for demo_video_maker.cursor."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from demo_video_maker.cursor import (
    _create_cursor_svg,
    apply_cursors_to_manifest,
    overlay_cursor_on_frame,
    save_cursor_svg,
)
from demo_video_maker.models import CursorConfig, Manifest, StepResult


class TestCreateCursorSvg:
    """Tests for cursor SVG generation."""

    def test_normal_cursor(self) -> None:
        config = CursorConfig(color="#ff0000", size=20)
        svg = _create_cursor_svg(config, clicked=False)

        assert "<svg" in svg
        assert "</svg>" in svg
        assert "#ff0000" in svg

    def test_clicked_cursor_has_ring(self) -> None:
        config = CursorConfig(click_ring_color="#0000ff", click_ring_size=40)
        svg = _create_cursor_svg(config, clicked=True)

        assert "#0000ff" in svg
        assert "stroke" in svg


class TestSaveCursorSvg:
    """Tests for saving cursor SVGs to disk."""

    def test_creates_both_files(self, tmp_path: Path) -> None:
        config = CursorConfig()
        normal, clicked = save_cursor_svg(config, tmp_path)

        assert normal.exists()
        assert clicked.exists()
        assert normal.name == "cursor.svg"
        assert clicked.name == "cursor_click.svg"


class TestOverlayCursorOnFrame:
    """Tests for cursor frame overlay."""

    @patch("demo_video_maker.cursor.subprocess.run")
    def test_calls_ffmpeg(self, mock_run: MagicMock, tmp_path: Path) -> None:
        frame = tmp_path / "frame.png"
        cursor = tmp_path / "cursor.svg"
        output = tmp_path / "output.png"

        overlay_cursor_on_frame(frame, output, cursor, (100, 200))

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ffmpeg"
        assert "overlay=100:200" in cmd[cmd.index("-filter_complex") + 1]


class TestApplyCursorsToManifest:
    """Tests for applying cursors to a manifest."""

    def test_skips_when_disabled(self) -> None:
        config = CursorConfig(enabled=False)
        manifest = Manifest(
            title="Test",
            steps=[
                StepResult(index=0, frame_path="f.png", click_position=(100, 200)),
            ],
        )
        result = apply_cursors_to_manifest(manifest, config, Path("out"))
        assert result.steps[0].frame_path == "f.png"

    @patch("demo_video_maker.cursor.overlay_cursor_on_frame")
    @patch("demo_video_maker.cursor.save_cursor_svg")
    def test_applies_to_steps_with_click_position(
        self, mock_save: MagicMock, mock_overlay: MagicMock, tmp_path: Path
    ) -> None:
        mock_save.return_value = (tmp_path / "n.svg", tmp_path / "c.svg")
        mock_overlay.return_value = tmp_path / "out.png"

        config = CursorConfig()
        manifest = Manifest(
            title="Test",
            steps=[
                StepResult(index=0, frame_path="f0.png", click_position=(50, 75)),
                StepResult(index=1, frame_path="f1.png", click_position=None),
            ],
        )
        result = apply_cursors_to_manifest(manifest, config, tmp_path)

        mock_overlay.assert_called_once()
        assert result.steps[1].frame_path == "f1.png"
