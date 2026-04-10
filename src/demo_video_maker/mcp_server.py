"""MCP server exposing demo-video-maker as tools, resources, and prompts."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from demo_video_maker.cursor import apply_cursors_to_manifest
from demo_video_maker.gif import generate_gif
from demo_video_maker.models import (
    ActionType,
    CursorConfig,
    Manifest,
    Scenario,
    Step,
)
from demo_video_maker.narration_export import export_narration_json
from demo_video_maker.narrator import (
    EdgeTTS,
    KokoroTTS,
    OpenAITTS,
    SilentBackend,
    TTSBackend,
    generate_narration,
    pre_generate_audio,
)
from demo_video_maker.recorder import record_scenario
from demo_video_maker.stitcher import stitch_video as _stitch_video_impl
from demo_video_maker.subtitles import generate_srt, generate_vtt
from demo_video_maker.tutorial import generate_html_tutorial

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "demo-video-maker",
    instructions="Automated webapp demo video recorder: Playwright + TTS + FFmpeg",
)

# ---------------------------------------------------------------------------
# Known TTS voices (hardcoded reference data)
# ---------------------------------------------------------------------------
_TTS_VOICES: dict[str, dict[str, Any]] = {
    "kokoro": {
        "default": "af_heart",
        "voices": [
            "af_heart",
            "af_alloy",
            "af_aoede",
            "af_bella",
            "af_jessica",
            "af_kore",
            "af_nicole",
            "af_nova",
            "af_river",
            "af_sarah",
            "af_sky",
            "am_adam",
            "am_echo",
            "am_eric",
            "am_fenrir",
            "am_liam",
            "am_michael",
            "am_onyx",
            "am_puck",
            "am_santa",
            "bf_emma",
            "bf_isabella",
            "bm_george",
            "bm_lewis",
            "bm_daniel",
            "if_sara",
            "im_nicola",
        ],
    },
    "openai": {
        "default": "onyx",
        "voices": [
            "alloy",
            "ash",
            "ballad",
            "coral",
            "echo",
            "fable",
            "nova",
            "onyx",
            "sage",
            "shimmer",
        ],
    },
    "edge": {
        "default": "en-US-AvaMultilingualNeural",
        "voices": [
            "en-US-AvaMultilingualNeural",
            "en-US-AndrewMultilingualNeural",
            "en-US-EmmaMultilingualNeural",
            "en-US-BrianMultilingualNeural",
            "en-US-JennyNeural",
            "en-US-GuyNeural",
            "en-US-AriaNeural",
            "en-US-DavisNeural",
            "en-US-JaneNeural",
            "en-US-JasonNeural",
            "en-US-SaraNeural",
            "en-US-TonyNeural",
            "en-US-NancyNeural",
            "en-GB-SoniaNeural",
            "en-GB-RyanNeural",
        ],
    },
    "silent": {
        "default": "silent",
        "voices": ["silent"],
    },
}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_tts_backend(
    tts: str,
    voice: str | None,
    scenario_voice: str = "onyx",
) -> TTSBackend:
    """Build a TTS backend instance from name and optional voice override.

    Args:
        tts: Backend name ("kokoro", "openai", "edge", "silent").
        voice: Explicit voice override, or None for backend default.
        scenario_voice: Voice defined in the scenario (used as OpenAI fallback).

    Returns:
        Configured TTSBackend instance.

    Raises:
        ValueError: If the backend name is not recognized.
    """
    backends: dict[str, Any] = {
        "kokoro": lambda: KokoroTTS(voice=voice or "af_heart"),
        "openai": lambda: OpenAITTS(voice=voice or scenario_voice),
        "edge": lambda: EdgeTTS(voice=voice or "en-US-AvaMultilingualNeural"),
        "silent": lambda: SilentBackend(),
    }
    factory = backends.get(tts)
    if factory is None:
        msg = f"Unknown TTS backend: {tts!r}. Choose from: {', '.join(backends)}"
        raise ValueError(msg)
    return factory()  # type: ignore[no-any-return]


def _collect_extras(
    manifest: Manifest,
    output_dir: Path,
    *,
    gif: bool,
    html: bool,
) -> list[str]:
    """Generate optional extra output files and return their paths.

    Args:
        manifest: Recording manifest with frames and narration.
        output_dir: Directory to write extra output files.
        gif: Whether to generate an animated GIF preview.
        html: Whether to generate an HTML tutorial.

    Returns:
        List of absolute paths to generated extra files.
    """
    extras: list[str] = []

    srt_path = generate_srt(manifest, output_dir / "subtitles.srt")
    extras.append(str(srt_path))

    vtt_path = generate_vtt(manifest, output_dir / "subtitles.vtt")
    extras.append(str(vtt_path))

    narration_path = export_narration_json(manifest, output_dir / "narration.json")
    extras.append(str(narration_path))

    if gif:
        gif_path = generate_gif(manifest, output_dir / "preview.gif")
        extras.append(str(gif_path))

    if html:
        html_path = generate_html_tutorial(manifest, output_dir / "tutorial.html")
        extras.append(str(html_path))

    return extras


def _resolve_work_dir(
    scenario_file: str | None,
    work_dir: str | None,
) -> Path:
    """Determine the working directory for build artifacts.

    Args:
        scenario_file: Path to the scenario YAML (used to derive a default).
        work_dir: Explicit work directory override, or None for auto.

    Returns:
        Resolved working directory path.
    """
    if work_dir is not None:
        return Path(work_dir)
    if scenario_file is not None:
        return Path(".demo_build") / Path(scenario_file).stem
    return Path(".demo_build") / "default"


# ---------------------------------------------------------------------------
# Pipeline tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="record_demo",
    description=(
        "Full pipeline: load scenario, record browser, generate narration, stitch video."
    ),
)
async def record_demo(
    scenario_file: str,
    output: str = "demo.mp4",
    base_url: str | None = None,
    tts: str = "kokoro",
    voice: str | None = None,
    mode: str = "clip",
    headed: bool = False,  # noqa: FBT001, FBT002
    work_dir: str | None = None,
    gif: bool = False,  # noqa: FBT001, FBT002
    html: bool = False,  # noqa: FBT001, FBT002
    cursor: bool = True,  # noqa: FBT001, FBT002
    gap: float = 0.8,
) -> dict[str, Any]:
    """Record a full demo video from a YAML scenario file.

    Replicates the CLI ``record`` command: loads the scenario, records
    the browser session, generates TTS narration, stitches the final
    video, and optionally produces GIF/HTML extras.

    Args:
        scenario_file: Path to the YAML scenario file.
        output: Output video file path.
        base_url: Override the scenario's base_url.
        tts: TTS backend name (kokoro, openai, edge, silent).
        voice: TTS voice name override.
        mode: Recording mode ("clip" for live video, "screenshot" for frames).
        headed: Show browser window during recording.
        work_dir: Working directory for build artifacts.
        gif: Also generate an animated GIF preview.
        html: Also generate an HTML tutorial page.
        cursor: Enable cursor overlay on click steps (screenshot mode).
        gap: Seconds of pause after narration ends before next step (clip mode).

    Returns:
        Dict with status, output paths, and extras list, or error details.
    """
    try:
        resolved_work = _resolve_work_dir(scenario_file, work_dir)
        output_path = Path(output)

        scenario = await asyncio.to_thread(Scenario.from_yaml, Path(scenario_file))
        backend = _build_tts_backend(tts, voice, scenario.voice)

        use_clips = mode == "clip"

        # In clip mode: pre-generate audio so recording pauses match narration
        pre_audio: dict[int, tuple[str, float]] = {}
        if use_clips:
            steps_as_objects: list[object] = list(scenario.steps)
            pre_audio = await asyncio.to_thread(
                pre_generate_audio,
                steps_as_objects,
                resolved_work / "audio",
                backend,
            )

        # 1. Record browser session
        manifest = await record_scenario(
            scenario,
            resolved_work,
            base_url_override=base_url,
            headless=not headed,
            video_clips=use_clips,
            audio_durations=(
                {k: v[1] for k, v in pre_audio.items()} if pre_audio else None
            ),
        )

        # 2. Cursor overlays (screenshot mode only)
        if cursor and not use_clips:
            cursor_config = CursorConfig()
            manifest = await asyncio.to_thread(
                apply_cursors_to_manifest,
                manifest,
                cursor_config,
                resolved_work / "cursors",
            )

        # 3. Attach narration
        if use_clips:
            for step in manifest.steps:
                if step.index in pre_audio:
                    step.audio_path = pre_audio[step.index][0]
        else:
            manifest = await asyncio.to_thread(
                generate_narration,
                manifest,
                resolved_work / "audio",
                backend=backend,
            )

        # Save manifest with audio paths
        await asyncio.to_thread(manifest.save, resolved_work / "manifest.json")

        # 4. Stitch final video
        await asyncio.to_thread(
            _stitch_video_impl,
            manifest,
            output_path,
            work_dir=resolved_work,
            transition_gap=gap,
        )

        # 5. Generate extras
        extras = await asyncio.to_thread(
            _collect_extras,
            manifest,
            output_path.parent,
            gif=gif,
            html=html,
        )

        return {
            "status": "ok",
            "video": str(output_path),
            "manifest": str(resolved_work / "manifest.json"),
            "extras": extras,
        }
    except Exception as exc:
        logger.exception("record_demo failed")
        return {"error": str(exc)}


@mcp.tool(
    name="capture_screenshots",
    description="Capture screenshots from a scenario without narration or stitching.",
)
async def capture_screenshots(
    scenario_file: str,
    base_url: str | None = None,
    headed: bool = False,  # noqa: FBT001, FBT002
    work_dir: str | None = None,
) -> dict[str, Any]:
    """Capture browser screenshots for every step in a scenario.

    Runs the browser automation without TTS or video stitching.
    Produces a manifest and screenshot frames only.

    Args:
        scenario_file: Path to the YAML scenario file.
        base_url: Override the scenario's base_url.
        headed: Show browser window during capture.
        work_dir: Working directory for build artifacts.

    Returns:
        Dict with status, manifest path, frames directory, and frame count.
    """
    try:
        resolved_work = _resolve_work_dir(scenario_file, work_dir)
        scenario = await asyncio.to_thread(Scenario.from_yaml, Path(scenario_file))

        manifest = await record_scenario(
            scenario,
            resolved_work,
            base_url_override=base_url,
            headless=not headed,
        )

        frames_dir = resolved_work / "frames"
        return {
            "status": "ok",
            "manifest": str(resolved_work / "manifest.json"),
            "frames_dir": str(frames_dir),
            "frame_count": len(manifest.steps),
        }
    except Exception as exc:
        logger.exception("capture_screenshots failed")
        return {"error": str(exc)}


@mcp.tool(
    name="narrate_manifest",
    description="Add TTS narration to an existing manifest and produce a video.",
)
async def narrate_manifest(
    manifest_file: str,
    output: str = "demo.mp4",
    tts: str = "kokoro",
    voice: str | None = None,
    gif: bool = False,  # noqa: FBT001, FBT002
    html: bool = False,  # noqa: FBT001, FBT002
) -> dict[str, Any]:
    """Generate narration for an existing manifest and stitch the final video.

    Corresponds to the CLI ``narrate`` command. Loads a previously
    captured manifest, synthesizes TTS audio, then stitches and exports.

    Args:
        manifest_file: Path to the manifest JSON file.
        output: Output video file path.
        tts: TTS backend name (kokoro, openai, edge, silent).
        voice: TTS voice name override.
        gif: Also generate an animated GIF preview.
        html: Also generate an HTML tutorial page.

    Returns:
        Dict with status, video path, and extras list, or error details.
    """
    try:
        manifest_path = Path(manifest_file)
        output_path = Path(output)
        work_dir_path = manifest_path.parent

        manifest = await asyncio.to_thread(Manifest.load, manifest_path)
        backend = _build_tts_backend(tts, voice)

        manifest = await asyncio.to_thread(
            generate_narration,
            manifest,
            work_dir_path / "audio",
            backend=backend,
        )

        await asyncio.to_thread(
            _stitch_video_impl,
            manifest,
            output_path,
            work_dir=work_dir_path,
        )

        extras = await asyncio.to_thread(
            _collect_extras,
            manifest,
            output_path.parent,
            gif=gif,
            html=html,
        )

        return {
            "status": "ok",
            "video": str(output_path),
            "extras": extras,
        }
    except Exception as exc:
        logger.exception("narrate_manifest failed")
        return {"error": str(exc)}


@mcp.tool(
    name="stitch_video",
    description="Re-stitch video from a manifest without regenerating narration.",
)
async def stitch_video_tool(
    manifest_file: str,
    output: str = "demo.mp4",
    gif: bool = False,  # noqa: FBT001, FBT002
    html: bool = False,  # noqa: FBT001, FBT002
    gap: float = 0.8,
) -> dict[str, Any]:
    """Stitch a final video from an existing manifest.

    Use after manually editing step durations or audio offsets in the
    manifest JSON to fix audio-video sync issues.

    Args:
        manifest_file: Path to the manifest JSON file.
        output: Output video file path.
        gif: Also generate an animated GIF preview.
        html: Also generate an HTML tutorial page.
        gap: Seconds of pause after narration before next step (clip mode).

    Returns:
        Dict with status, video path, and extras list, or error details.
    """
    try:
        manifest_path = Path(manifest_file)
        output_path = Path(output)
        work_dir_path = manifest_path.parent

        manifest = await asyncio.to_thread(Manifest.load, manifest_path)

        await asyncio.to_thread(
            _stitch_video_impl,
            manifest,
            output_path,
            work_dir=work_dir_path,
            transition_gap=gap,
        )

        extras = await asyncio.to_thread(
            _collect_extras,
            manifest,
            output_path.parent,
            gif=gif,
            html=html,
        )

        return {
            "status": "ok",
            "video": str(output_path),
            "extras": extras,
        }
    except Exception as exc:
        logger.exception("stitch_video failed")
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Query tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="list_scenarios",
    description="List available scenario YAML files in a directory.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def list_scenarios(
    scenarios_dir: str = "scenarios",
) -> dict[str, Any]:
    """Scan a directory for YAML scenario files and return metadata.

    Args:
        scenarios_dir: Directory to scan for .yaml/.yml scenario files.

    Returns:
        Dict with a list of scenario summaries (name, path, title, step count).
    """
    try:
        base = Path(scenarios_dir)
        if not base.is_dir():
            return {"scenarios": []}

        scenarios: list[dict[str, Any]] = []
        for ext in ("*.yaml", "*.yml"):
            for yaml_path in sorted(base.glob(ext)):
                try:
                    scenario = Scenario.from_yaml(yaml_path)
                    scenarios.append({
                        "name": yaml_path.stem,
                        "path": str(yaml_path),
                        "title": scenario.title,
                        "step_count": len(scenario.steps),
                    })
                except Exception:  # noqa: BLE001
                    logger.debug("Skipping invalid scenario: %s", yaml_path)

        return {"scenarios": scenarios}
    except Exception as exc:
        logger.exception("list_scenarios failed")
        return {"error": str(exc)}


@mcp.tool(
    name="validate_scenario",
    description="Validate a YAML scenario file and report any errors.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def validate_scenario(
    scenario_file: str,
) -> dict[str, Any]:
    """Parse and validate a YAML scenario file.

    Checks that the file is valid YAML, conforms to the Scenario schema,
    and reports any Pydantic validation errors.

    Args:
        scenario_file: Path to the YAML scenario file.

    Returns:
        Dict with validity status, error list, and parsed scenario data.
    """
    errors: list[str] = []
    try:
        scenario = Scenario.from_yaml(Path(scenario_file))
        return {
            "valid": True,
            "errors": [],
            "scenario": json.loads(scenario.model_dump_json()),
        }
    except FileNotFoundError:
        errors.append(f"File not found: {scenario_file}")
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))

    return {"valid": False, "errors": errors, "scenario": None}


@mcp.tool(
    name="list_builds",
    description="List existing build directories with manifests.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def list_builds(
    work_dir: str = ".demo_build",
) -> dict[str, Any]:
    """Enumerate build directories that contain a manifest.json.

    Args:
        work_dir: Root build directory to scan.

    Returns:
        Dict with a list of build summaries.
    """
    try:
        base = Path(work_dir)
        if not base.is_dir():
            return {"builds": []}

        builds: list[dict[str, Any]] = []
        for manifest_path in sorted(base.glob("*/manifest.json")):
            try:
                manifest = Manifest.load(manifest_path)
                build_dir = manifest_path.parent
                has_video = bool(list(build_dir.glob("*.mp4"))) or any(
                    s.video_path is not None for s in manifest.steps
                )
                has_audio = any(
                    s.audio_path is not None for s in manifest.steps
                )
                builds.append({
                    "name": build_dir.name,
                    "manifest_path": str(manifest_path),
                    "has_video": has_video,
                    "has_audio": has_audio,
                    "step_count": len(manifest.steps),
                    "title": manifest.title,
                })
            except Exception:  # noqa: BLE001
                logger.debug("Skipping invalid manifest: %s", manifest_path)

        return {"builds": builds}
    except Exception as exc:
        logger.exception("list_builds failed")
        return {"error": str(exc)}


@mcp.tool(
    name="get_manifest",
    description="Read and return the contents of a manifest JSON file.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def get_manifest(
    manifest_file: str,
) -> dict[str, Any]:
    """Load a manifest file and return it as a dictionary.

    Args:
        manifest_file: Path to the manifest JSON file.

    Returns:
        Manifest data as a dictionary.
    """
    try:
        manifest = Manifest.load(Path(manifest_file))
        return json.loads(manifest.model_dump_json())  # type: ignore[no-any-return]
    except Exception as exc:
        logger.exception("get_manifest failed")
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Utility tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="list_tts_voices",
    description="List available TTS voices for each backend.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def list_tts_voices(
    backend: str | None = None,
) -> dict[str, Any]:
    """Return available TTS voices, optionally filtered by backend.

    Args:
        backend: Filter to a specific backend name, or None for all.

    Returns:
        Dict mapping backend names to their default voice and voice list.
    """
    if backend is not None:
        if backend not in _TTS_VOICES:
            return {
                "error": (
                    f"Unknown backend: {backend!r}. "
                    f"Choose from: {', '.join(_TTS_VOICES)}"
                ),
            }
        return {"backends": {backend: _TTS_VOICES[backend]}}
    return {"backends": _TTS_VOICES}


@mcp.tool(
    name="get_scenario_details",
    description="Load a scenario YAML file and return its full contents as structured data.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def get_scenario_details(
    scenario_file: str,
) -> dict[str, Any]:
    """Parse a scenario file and return the complete scenario as a dict.

    Args:
        scenario_file: Path to the YAML scenario file.

    Returns:
        Full scenario data as a dictionary.
    """
    try:
        scenario = Scenario.from_yaml(Path(scenario_file))
        return json.loads(scenario.model_dump_json())  # type: ignore[no-any-return]
    except Exception as exc:
        logger.exception("get_scenario_details failed")
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource(
    "scenario://{path}",
    name="scenario",
    description="Read a scenario YAML file by path.",
    mime_type="text/yaml",
)
async def read_scenario_resource(path: str) -> str:
    """Return the raw YAML content of a scenario file.

    Args:
        path: Filesystem path to the scenario YAML file.

    Returns:
        YAML file contents as a string.
    """
    return Path(path).read_text()


@mcp.resource(
    "manifest://{build_name}",
    name="manifest",
    description="Read a build manifest JSON from .demo_build/{build_name}/manifest.json.",
    mime_type="application/json",
)
async def read_manifest_resource(build_name: str) -> str:
    """Return the JSON content of a build's manifest file.

    Args:
        build_name: Name of the build directory under .demo_build/.

    Returns:
        Manifest JSON as a string.
    """
    manifest_path = Path(".demo_build") / build_name / "manifest.json"
    return manifest_path.read_text()


@mcp.resource(
    "build://{build_name}/video",
    name="build_video",
    description="Get the absolute path to a build's output MP4 video file.",
    mime_type="text/plain",
)
async def read_build_video_resource(build_name: str) -> str:
    """Return the absolute path to the first MP4 file in a build directory.

    Args:
        build_name: Name of the build directory under .demo_build/.

    Returns:
        Absolute path to the MP4 file as a string.

    Raises:
        FileNotFoundError: If no MP4 file is found in the build directory.
    """
    build_dir = Path(".demo_build") / build_name
    mp4_files = sorted(build_dir.glob("*.mp4"))
    if not mp4_files:
        msg = f"No MP4 video found for build {build_name!r}"
        raise FileNotFoundError(msg)
    return str(mp4_files[0].resolve())


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


@mcp.prompt(
    name="create_scenario",
    description="Generate a YAML scenario template for a web application demo.",
)
async def create_scenario_prompt(
    app_name: str,
    base_url: str,
) -> str:
    """Build a user message with a YAML scenario template and field reference.

    Args:
        app_name: Name of the web application being demoed.
        base_url: Base URL where the application is running.

    Returns:
        Formatted prompt text with YAML template and available actions/fields.
    """
    action_list = ", ".join(a.value for a in ActionType)

    step_fields: list[str] = []
    for name, field_info in Step.model_fields.items():
        annotation = field_info.annotation
        default = field_info.default
        step_fields.append(f"  - {name}: {annotation} (default: {default!r})")
    step_fields_text = "\n".join(step_fields)

    return (
        f"I need to create a demo video scenario for **{app_name}** "
        f"running at `{base_url}`.\n\n"
        "Please help me write a YAML scenario file. Here is the template "
        "and reference:\n\n"
        "```yaml\n"
        f'title: "{app_name} Demo"\n'
        f'base_url: "{base_url}"\n'
        "resolution: [1920, 1080]\n"
        "pause_between_steps: 1.5\n"
        'transition: "fade"\n'
        'voice: "onyx"\n'
        'tts_model: "tts-1-hd"\n'
        "steps:\n"
        "  - action: navigate\n"
        '    url: "/"\n'
        f'    narration: "Welcome to {app_name}."\n'
        "\n"
        "  - action: click\n"
        '    selector: "#login-button"\n'
        '    narration: "Click the login button to get started."\n'
        '    highlight: "#login-button"\n'
        "\n"
        "  - action: type\n"
        '    selector: "#username"\n'
        '    text: "demo@example.com"\n'
        '    narration: "Enter the demo credentials."\n'
        "\n"
        "  - action: wait\n"
        "    wait_seconds: 2.0\n"
        '    narration: "The page loads."\n'
        "\n"
        "  - action: screenshot\n"
        '    narration: "Here is the dashboard view."\n'
        "```\n\n"
        "### Available actions\n"
        f"{action_list}\n\n"
        "### Step fields\n"
        f"{step_fields_text}\n\n"
        "### Tips\n"
        "- Use `narration` on every step for the TTS voiceover.\n"
        "- Use `highlight` with a CSS selector to draw a blue outline "
        "around an element.\n"
        "- Use `wait_for` with a CSS selector to wait for an element "
        "before capturing.\n"
        "- Use `duration_override` (seconds) to hold a step longer than "
        "the default pause.\n"
        "- The `selector` field accepts any CSS selector.\n\n"
        "Please generate the complete scenario YAML for the described "
        "application flow."
    )


@mcp.prompt(
    name="debug_build",
    description="Analyze a build manifest to diagnose issues.",
)
async def debug_build_prompt(
    manifest_file: str,
) -> str:
    """Build a user message with the manifest JSON for debugging analysis.

    Args:
        manifest_file: Path to the manifest JSON file.

    Returns:
        Formatted prompt text with embedded manifest data for analysis.
    """
    manifest_path = Path(manifest_file)
    try:
        raw = manifest_path.read_text()
        data = json.loads(raw)
        pretty = json.dumps(data, indent=2)
    except Exception as exc:  # noqa: BLE001
        return f"Failed to load manifest from {manifest_file}: {exc}"

    step_count = len(data.get("steps", []))
    has_audio = any(s.get("audio_path") for s in data.get("steps", []))
    has_video = any(s.get("video_path") for s in data.get("steps", []))

    return (
        "Please analyze this demo-video-maker build manifest and help me "
        "diagnose any issues.\n\n"
        f"**Manifest file:** `{manifest_file}`\n"
        f"**Steps:** {step_count}\n"
        f"**Has audio:** {has_audio}\n"
        f"**Has video clips:** {has_video}\n\n"
        f"```json\n{pretty}\n```\n\n"
        "Things to check:\n"
        "1. Are all frame_path files likely to exist?\n"
        "2. Are audio_path files present for steps with narration text?\n"
        "3. Are step durations reasonable (not too short for narration)?\n"
        "4. Are audio_offset values monotonically increasing?\n"
        "5. Is the click_position set for click action steps?\n"
        "6. Any steps with empty narration that should have text?\n\n"
        "Please provide your analysis and any recommended fixes."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MCP server with stdio transport."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
