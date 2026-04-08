"""SRT and VTT subtitle generation from manifest narration."""

from __future__ import annotations

from pathlib import Path

from demo_video_maker.models import Manifest


def _format_srt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp (HH:MM:SS,mmm).

    Args:
        seconds: Time in seconds.

    Returns:
        Formatted SRT timestamp string.
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_vtt_time(seconds: float) -> str:
    """Format seconds as VTT timestamp (HH:MM:SS.mmm).

    Args:
        seconds: Time in seconds.

    Returns:
        Formatted VTT timestamp string.
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def generate_srt(manifest: Manifest, output_path: Path) -> Path:
    """Generate SRT subtitle file from manifest narration.

    Args:
        manifest: Recording manifest with step narrations.
        output_path: Path to write the SRT file.

    Returns:
        Path to the created SRT file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    cumulative = 0.0
    subtitle_index = 1

    for step in manifest.steps:
        start = cumulative
        end = cumulative + step.duration
        cumulative = end

        if not step.narration:
            continue

        lines.append(str(subtitle_index))
        lines.append(f"{_format_srt_time(start)} --> {_format_srt_time(end)}")
        lines.append(step.narration)
        lines.append("")
        subtitle_index += 1

    output_path.write_text("\n".join(lines))
    return output_path


def generate_vtt(manifest: Manifest, output_path: Path) -> Path:
    """Generate WebVTT subtitle file from manifest narration.

    Args:
        manifest: Recording manifest with step narrations.
        output_path: Path to write the VTT file.

    Returns:
        Path to the created VTT file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = ["WEBVTT", ""]
    cumulative = 0.0
    subtitle_index = 1

    for step in manifest.steps:
        start = cumulative
        end = cumulative + step.duration
        cumulative = end

        if not step.narration:
            continue

        lines.append(str(subtitle_index))
        lines.append(f"{_format_vtt_time(start)} --> {_format_vtt_time(end)}")
        lines.append(step.narration)
        lines.append("")
        subtitle_index += 1

    output_path.write_text("\n".join(lines))
    return output_path
