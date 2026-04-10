"""Animated cursor overlay for screenshot frames.

Renders cursor PNG images and composites them onto screenshot frames
using ffmpeg. Uses PNG (not SVG) for universal ffmpeg compatibility.
"""

from __future__ import annotations

import logging
import struct
import zlib
from pathlib import Path

import subprocess

from demo_video_maker.models import CursorConfig, Manifest

logger = logging.getLogger(__name__)


def _create_cursor_png(config: CursorConfig, *, clicked: bool = False) -> bytes:
    """Create a cursor image as a minimal PNG with alpha channel.

    Draws a filled circle (cursor dot) and optionally an outer ring
    (click effect) using pure Python — no Pillow or Cairo needed.

    Args:
        config: Cursor appearance configuration.
        clicked: Whether to render the click ring effect.

    Returns:
        PNG file contents as bytes.
    """
    size = config.click_ring_size if clicked else config.size
    half = size / 2
    dot_r = config.size / 2
    ring_r = (config.click_ring_size / 2) - 2 if clicked else 0
    ring_w = 4

    dot_color = _hex_to_rgba(config.color, alpha=217)  # 0.85 opacity
    ring_color = _hex_to_rgba(config.click_ring_color, alpha=153)  # 0.6 opacity

    # Build RGBA pixel rows with filter byte
    raw_rows = bytearray()
    for py in range(size):
        raw_rows.append(0)  # PNG filter: None
        for px in range(size):
            dx = px + 0.5 - half
            dy = py + 0.5 - half
            dist = (dx * dx + dy * dy) ** 0.5

            if dist <= dot_r:
                raw_rows.extend(dot_color)
            elif clicked and abs(dist - ring_r) <= ring_w / 2:
                raw_rows.extend(ring_color)
            else:
                raw_rows.extend(b"\x00\x00\x00\x00")

    return _encode_png(size, size, raw_rows)


def _hex_to_rgba(hex_color: str, *, alpha: int = 255) -> bytes:
    """Convert a hex color string to RGBA bytes.

    Args:
        hex_color: Color string like '#ef4444'.
        alpha: Alpha value 0-255.

    Returns:
        4 bytes (R, G, B, A).
    """
    h = hex_color.lstrip("#")
    return bytes([int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha])


def _encode_png(width: int, height: int, raw_rows: bytes | bytearray) -> bytes:
    """Encode raw RGBA pixel data as a minimal PNG file.

    Args:
        width: Image width in pixels.
        height: Image height in pixels.
        raw_rows: RGBA pixel data with per-row filter bytes.

    Returns:
        Complete PNG file as bytes.
    """

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        """Wrap data in a PNG chunk with length, type, and CRC32."""
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(bytes(raw_rows))) + _chunk(b"IEND", b"")


def save_cursor_png(config: CursorConfig, output_dir: Path) -> tuple[Path, Path]:
    """Save cursor PNG files (normal and clicked) to disk.

    Args:
        config: Cursor appearance configuration.
        output_dir: Directory to write PNG files.

    Returns:
        Tuple of (normal_cursor_path, clicked_cursor_path).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    normal_path = output_dir / "cursor.png"
    normal_path.write_bytes(_create_cursor_png(config, clicked=False))

    clicked_path = output_dir / "cursor_click.png"
    clicked_path.write_bytes(_create_cursor_png(config, clicked=True))

    return normal_path, clicked_path


def overlay_cursor_on_frame(
    frame_path: Path,
    output_path: Path,
    cursor_png: Path,
    position: tuple[int, int],
    cursor_size: int,
) -> Path:
    """Composite a cursor PNG onto a screenshot frame using ffmpeg.

    The cursor is centered on the given position coordinates.

    Args:
        frame_path: Path to the source screenshot PNG.
        output_path: Path to write the composited PNG.
        cursor_png: Path to the cursor PNG file.
        position: (x, y) coordinates for the cursor center.
        cursor_size: Size of the cursor image (for centering offset).

    Returns:
        Path to the composited frame.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    x, y = position
    half = cursor_size // 2

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(frame_path),
            "-i", str(cursor_png),
            "-filter_complex",
            f"[0:v][1:v]overlay={x - half}:{y - half}",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )
    return output_path


def apply_cursors_to_manifest(
    manifest: Manifest,
    config: CursorConfig,
    output_dir: Path,
) -> Manifest:
    """Apply cursor overlays to all frames in a manifest that have click positions.

    Args:
        manifest: Recording manifest with frames and optional click positions.
        config: Cursor appearance configuration.
        output_dir: Directory to write cursor-overlaid frames.

    Returns:
        Updated manifest with frame paths pointing to cursor-overlaid frames.
    """
    if not config.enabled:
        return manifest

    output_dir.mkdir(parents=True, exist_ok=True)
    normal_png, clicked_png = save_cursor_png(config, output_dir / "cursors")

    for step in manifest.steps:
        if step.click_position is None:
            continue

        frame_path = Path(step.frame_path)
        overlaid_path = output_dir / f"cursor_step_{step.index:03d}.png"

        overlay_cursor_on_frame(
            frame_path, overlaid_path, clicked_png, step.click_position, config.click_ring_size,
        )
        step.frame_path = str(overlaid_path)
        logger.info("Cursor overlay applied to step %d", step.index)

    return manifest
