"""CLI entry point for demo-video-maker."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import click

from demo_video_maker.cursor import apply_cursors_to_manifest
from demo_video_maker.gif import generate_gif
from demo_video_maker.models import CursorConfig, Manifest, OutputConfig, Scenario
from demo_video_maker.narration_export import export_narration_json
from demo_video_maker.narrator import (
    EdgeTTS,
    KokoroTTS,
    OpenAITTS,
    SilentBackend,
    generate_narration,
)
from demo_video_maker.recorder import record_scenario
from demo_video_maker.stitcher import stitch_video
from demo_video_maker.subtitles import generate_srt, generate_vtt
from demo_video_maker.tutorial import generate_html_tutorial

logger = logging.getLogger(__name__)


def _generate_extras(
    manifest: Manifest,
    output_dir: Path,
    config: OutputConfig,
) -> None:
    """Generate all configured extra outputs (subtitles, GIF, tutorial, etc.).

    Args:
        manifest: Recording manifest with frames and narration.
        output_dir: Directory to write extra output files.
        config: Output configuration flags.
    """
    if config.subtitles_srt:
        path = generate_srt(manifest, output_dir / "subtitles.srt")
        click.echo(f"  SRT subtitles: {path}")

    if config.subtitles_vtt:
        path = generate_vtt(manifest, output_dir / "subtitles.vtt")
        click.echo(f"  VTT subtitles: {path}")

    if config.gif:
        path = generate_gif(manifest, output_dir / "preview.gif")
        click.echo(f"  GIF preview: {path}")

    if config.html_tutorial:
        path = generate_html_tutorial(manifest, output_dir / "tutorial.html")
        click.echo(f"  HTML tutorial: {path}")

    if config.narration_json:
        path = export_narration_json(manifest, output_dir / "narration.json")
        click.echo(f"  Narration JSON: {path}")


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging")
def cli(*, verbose: bool) -> None:
    """Automated webapp demo video recorder."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


@cli.command()
@click.argument("scenario_file", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), default="demo.mp4")
@click.option("--base-url", default=None, help="Override scenario base_url")
@click.option("--tts", type=click.Choice(["kokoro", "openai", "edge", "silent"]), default="kokoro")
@click.option("--voice", default=None, help="TTS voice name")
@click.option("--headed", is_flag=True, help="Show browser window during recording")
@click.option("--work-dir", type=click.Path(path_type=Path), default=None)
@click.option("--gif", is_flag=True, help="Also generate GIF preview")
@click.option("--html", is_flag=True, help="Also generate HTML tutorial")
@click.option("--cursor/--no-cursor", default=True, help="Enable cursor overlay on click steps")
def record(
    scenario_file: Path,
    output: Path,
    base_url: str | None,
    tts: str,
    voice: str | None,
    *,
    headed: bool,
    work_dir: Path | None,
    gif: bool,
    html: bool,
    cursor: bool,
) -> None:
    """Record a demo video from a YAML scenario file."""
    if work_dir is None:
        work_dir = Path(".demo_build") / scenario_file.stem

    scenario = Scenario.from_yaml(scenario_file)
    click.echo(f"Loaded scenario: {scenario.title} ({len(scenario.steps)} steps)")

    # 1. Record browser session
    click.echo("Recording browser session...")
    manifest = asyncio.run(
        record_scenario(
            scenario,
            work_dir,
            base_url_override=base_url,
            headless=not headed,
        )
    )

    # 2. Apply cursor overlays
    if cursor:
        cursor_config = CursorConfig()
        manifest = apply_cursors_to_manifest(manifest, cursor_config, work_dir / "cursors")

    # 3. Generate narration
    backend_map = {
        "kokoro": lambda: KokoroTTS(voice=voice or "af_heart"),
        "openai": lambda: OpenAITTS(voice=voice or scenario.voice),
        "edge": lambda: EdgeTTS(voice=voice or "en-US-AvaMultilingualNeural"),
        "silent": lambda: SilentBackend(),
    }
    backend = backend_map[tts]()
    click.echo(f"Generating narration ({tts} backend)...")
    manifest = generate_narration(manifest, work_dir / "audio", backend=backend)

    # 4. Stitch final video
    click.echo("Stitching video...")
    stitch_video(manifest, output, work_dir=work_dir)
    click.echo(f"Video saved to {output}")

    # 5. Generate extras
    output_config = OutputConfig(gif=gif, html_tutorial=html)
    click.echo("Generating extras...")
    _generate_extras(manifest, output.parent, output_config)

    click.echo("Done!")


@cli.command()
@click.argument("scenario_file", type=click.Path(exists=True, path_type=Path))
@click.option("--base-url", default=None, help="Override scenario base_url")
@click.option("--headed", is_flag=True, help="Show browser window")
@click.option("--work-dir", type=click.Path(path_type=Path), default=None)
def capture(
    scenario_file: Path,
    base_url: str | None,
    *,
    headed: bool,
    work_dir: Path | None,
) -> None:
    """Capture screenshots only (no TTS or video stitching)."""
    if work_dir is None:
        work_dir = Path(".demo_build") / scenario_file.stem

    scenario = Scenario.from_yaml(scenario_file)
    click.echo(f"Capturing: {scenario.title} ({len(scenario.steps)} steps)")

    manifest = asyncio.run(
        record_scenario(
            scenario,
            work_dir,
            base_url_override=base_url,
            headless=not headed,
        )
    )
    click.echo(f"Captured {len(manifest.steps)} frames to {work_dir}")


@cli.command()
@click.argument("manifest_file", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), default="demo.mp4")
@click.option("--tts", type=click.Choice(["kokoro", "openai", "edge", "silent"]), default="kokoro")
@click.option("--voice", default=None, help="TTS voice name")
@click.option("--gif", is_flag=True, help="Also generate GIF preview")
@click.option("--html", is_flag=True, help="Also generate HTML tutorial")
def narrate(
    manifest_file: Path,
    output: Path,
    tts: str,
    voice: str | None,
    *,
    gif: bool,
    html: bool,
) -> None:
    """Add narration to existing screenshots and produce video."""
    manifest = Manifest.load(manifest_file)
    work_dir = manifest_file.parent

    backend_map = {
        "kokoro": lambda: KokoroTTS(voice=voice or "af_heart"),
        "openai": lambda: OpenAITTS(voice=voice or "onyx"),
        "edge": lambda: EdgeTTS(voice=voice or "en-US-AvaMultilingualNeural"),
        "silent": lambda: SilentBackend(),
    }
    backend = backend_map[tts]()
    click.echo(f"Generating narration ({tts})...")
    manifest = generate_narration(manifest, work_dir / "audio", backend=backend)

    click.echo("Stitching video...")
    stitch_video(manifest, output, work_dir=work_dir)
    click.echo(f"Video saved to {output}")

    output_config = OutputConfig(gif=gif, html_tutorial=html)
    click.echo("Generating extras...")
    _generate_extras(manifest, output.parent, output_config)

    click.echo("Done!")


def main() -> None:
    """Entry point."""
    cli()


if __name__ == "__main__":
    main()
