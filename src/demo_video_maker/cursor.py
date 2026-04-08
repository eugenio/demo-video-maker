"""Animated cursor overlay for screenshot frames.

Draws cursor position and click-effect rings onto screenshot PNGs
using Playwright's page.evaluate to inject SVG overlays before capture.
This module provides post-capture overlay via subprocess calls to ffmpeg
for compositing a cursor image onto frames.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from demo_video_maker.models import CursorConfig, Manifest

logger = logging.getLogger(__name__)


def _create_cursor_svg(config: CursorConfig, *, clicked: bool = False) -> str:
    """Create an SVG cursor image.

    Args:
        config: Cursor appearance configuration.
        clicked: Whether to render the click ring effect.

    Returns:
        SVG markup string.
    """
    size = config.click_ring_size if clicked else config.size
    half = size // 2
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}">',
    ]

    if clicked:
        parts.append(
            f'<circle cx="{half}" cy="{half}" r="{half - 2}" '
            f'fill="none" stroke="{config.click_ring_color}" '
            f'stroke-width="3" opacity="0.6"/>'
        )

    cursor_half = config.size // 2
    cx = half
    cy = half
    parts.append(
        f'<circle cx="{cx}" cy="{cy}" r="{cursor_half // 2}" '
        f'fill="{config.color}" opacity="0.85"/>'
    )
    parts.append("</svg>")
    return "".join(parts)


def save_cursor_svg(config: CursorConfig, output_dir: Path) -> tuple[Path, Path]:
    """Save cursor SVG files (normal and clicked) to disk.

    Args:
        config: Cursor appearance configuration.
        output_dir: Directory to write SVG files.

    Returns:
        Tuple of (normal_cursor_path, clicked_cursor_path).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    normal_path = output_dir / "cursor.svg"
    normal_path.write_text(_create_cursor_svg(config, clicked=False))

    clicked_path = output_dir / "cursor_click.svg"
    clicked_path.write_text(_create_cursor_svg(config, clicked=True))

    return normal_path, clicked_path


def overlay_cursor_on_frame(
    frame_path: Path,
    output_path: Path,
    cursor_svg: Path,
    position: tuple[int, int],
) -> Path:
    """Composite a cursor SVG onto a screenshot frame using ffmpeg.

    Args:
        frame_path: Path to the source screenshot PNG.
        output_path: Path to write the composited PNG.
        cursor_svg: Path to the cursor SVG file.
        position: (x, y) coordinates for the cursor center.

    Returns:
        Path to the composited frame.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    x, y = position

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(frame_path),
            "-i", str(cursor_svg),
            "-filter_complex",
            f"[1:v]scale=-1:-1[cursor];[0:v][cursor]overlay={x}:{y}",
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
    normal_svg, clicked_svg = save_cursor_svg(config, output_dir / "cursors")

    for step in manifest.steps:
        if step.click_position is None:
            continue

        frame_path = Path(step.frame_path)
        overlaid_path = output_dir / f"cursor_step_{step.index:03d}.png"

        cursor_svg = clicked_svg
        overlay_cursor_on_frame(frame_path, overlaid_path, cursor_svg, step.click_position)
        step.frame_path = str(overlaid_path)
        logger.info("Cursor overlay applied to step %d", step.index)

    return manifest
