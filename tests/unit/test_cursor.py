"""Tests for demo_video_maker.cursor."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from demo_video_maker.cursor import (
    _create_cursor_png,
    _hex_to_rgba,
    apply_cursors_to_manifest,
    overlay_cursor_on_frame,
    save_cursor_png,
)
from demo_video_maker.models import CursorConfig, Manifest, StepResult


class TestHexToRgba:
    """Tests for hex color conversion."""

    def test_basic_color(self) -> None:
        assert _hex_to_rgba("#ff0000", alpha=255) == b"\xff\x00\x00\xff"

    def test_with_alpha(self) -> None:
        assert _hex_to_rgba("#3b82f6", alpha=153) == b"\x3b\x82\xf6\x99"

    def test_strips_hash(self) -> None:
        assert _hex_to_rgba("ef4444", alpha=217) == b"\xef\x44\x44\xd9"


class TestCreateCursorPng:
    """Tests for cursor PNG generation."""

    def test_normal_cursor_is_valid_png(self) -> None:
        config = CursorConfig(color="#ff0000", size=48)
        data = _create_cursor_png(config, clicked=False)

        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(data) > 100

    def test_clicked_cursor_is_larger(self) -> None:
        config = CursorConfig(size=48, click_ring_size=80)
        normal = _create_cursor_png(config, clicked=False)
        clicked = _create_cursor_png(config, clicked=True)

        # Clicked image encodes more pixels (80x80 vs 48x48)
        assert len(clicked) > len(normal)

    def test_produces_rgba_pixels(self) -> None:
        config = CursorConfig(color="#ff0000", size=20)
        data = _create_cursor_png(config, clicked=False)

        # Verify IHDR chunk declares RGBA (color type 6)
        # IHDR starts at byte 16 (after 8-byte sig + 4-byte length + 4-byte type)
        # color type is at offset 25 (16 + 8 width + 1 bit depth)
        assert data[25] == 6


class TestSaveCursorPng:
    """Tests for saving cursor PNGs to disk."""

    def test_creates_both_files(self, tmp_path: Path) -> None:
        config = CursorConfig()
        normal, clicked = save_cursor_png(config, tmp_path)

        assert normal.exists()
        assert clicked.exists()
        assert normal.name == "cursor.png"
        assert clicked.name == "cursor_click.png"
        # Verify they are valid PNGs
        assert normal.read_bytes()[:4] == b"\x89PNG"
        assert clicked.read_bytes()[:4] == b"\x89PNG"


class TestOverlayCursorOnFrame:
    """Tests for cursor frame overlay."""

    @patch("demo_video_maker.cursor.subprocess.run")
    def test_calls_ffmpeg_with_centered_position(
        self, mock_run: MagicMock, tmp_path: Path,
    ) -> None:
        frame = tmp_path / "frame.png"
        cursor = tmp_path / "cursor.png"
        output = tmp_path / "output.png"

        overlay_cursor_on_frame(frame, output, cursor, (200, 300), cursor_size=80)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ffmpeg"
        filter_arg = cmd[cmd.index("-filter_complex") + 1]
        # Position should be offset by half cursor size: 200-40=160, 300-40=260
        assert "overlay=160:260" in filter_arg


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
    @patch("demo_video_maker.cursor.save_cursor_png")
    def test_applies_to_steps_with_click_position(
        self, mock_save: MagicMock, mock_overlay: MagicMock, tmp_path: Path,
    ) -> None:
        mock_save.return_value = (tmp_path / "n.png", tmp_path / "c.png")
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
        # Verify cursor_size was passed
        call_kwargs = mock_overlay.call_args
        assert call_kwargs[0][4] == config.click_ring_size
        assert result.steps[1].frame_path == "f1.png"
