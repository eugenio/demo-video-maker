"""Animated GIF preview generation from captured frames."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from demo_video_maker.models import Manifest

logger = logging.getLogger(__name__)


def generate_gif(
    manifest: Manifest,
    output_path: Path,
    *,
    fps: int = 1,
    width: int = 640,
    quality: int = 10,
) -> Path:
    """Generate an animated GIF preview from manifest frames.

    Uses ffmpeg's palettegen/paletteuse pipeline for high-quality GIF output
    with reduced file size.

    Args:
        manifest: Recording manifest with frame paths.
        output_path: Path to write the GIF file.
        fps: Frames per second in the output GIF.
        width: Width of the output GIF (height scales proportionally).
        quality: FFmpeg stats_mode quality (lower = better, 1-30).

    Returns:
        Path to the created GIF file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    work_dir = output_path.parent / ".gif_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Build concat file with per-frame durations
    concat_file = work_dir / "gif_concat.txt"
    with open(concat_file, "w") as f:
        for step in manifest.steps:
            abs_path = Path(step.frame_path).resolve()
            f.write(f"file '{abs_path}'\n")
            f.write(f"duration {step.duration}\n")
        if manifest.steps:
            abs_path = Path(manifest.steps[-1].frame_path).resolve()
            f.write(f"file '{abs_path}'\n")

    palette_path = work_dir / "palette.png"
    scale_filter = f"scale={width}:-1:flags=lanczos"

    # Pass 1: generate palette
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-vf", f"{scale_filter},palettegen=stats_mode=diff",
            str(palette_path),
        ],
        check=True,
        capture_output=True,
    )

    # Pass 2: generate GIF using palette
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-i", str(palette_path),
            "-lavfi", f"{scale_filter} [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=3",
            "-r", str(fps),
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )

    logger.info("GIF created: %s", output_path)
    return output_path
