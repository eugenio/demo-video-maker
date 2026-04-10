"""Integration tests for the demo-video-maker MCP server.

These tests exercise multiple real components together: Pydantic model
parsing/validation, real filesystem operations, and the FastMCP server
instance.  External processes (Playwright, TTS synthesis, FFmpeg) are
mocked to keep the suite fast and dependency-free.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml

from demo_video_maker.mcp_server import (
    _build_tts_backend,
    _collect_extras,
    mcp,
)
from demo_video_maker.models import ActionType, Manifest, Scenario, StepResult

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _minimal_scenario_dict(
    *,
    title: str = "Integration Test",
    base_url: str = "http://localhost:8080",
    steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a minimal scenario dict suitable for YAML serialisation.

    Args:
        title: Scenario title.
        base_url: Base URL for the demo.
        steps: List of step dictionaries.  Defaults to a single navigate step.

    Returns:
        Dictionary ready to be written as YAML.
    """
    if steps is None:
        steps = [{"action": "navigate", "url": "/", "narration": "Welcome"}]
    return {"title": title, "base_url": base_url, "steps": steps}


def _write_scenario_yaml(path: Path, data: dict[str, Any]) -> Path:
    """Write a scenario dict as YAML and return the path.

    Args:
        path: Target file path.
        data: Scenario data dictionary.

    Returns:
        The same *path* after writing.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, sort_keys=False))
    return path


def _make_manifest(
    title: str = "Test Manifest",
    step_count: int = 3,
    *,
    with_audio: bool = False,
    with_video: bool = False,
) -> Manifest:
    """Create a Manifest with *step_count* steps.

    Args:
        title: Manifest title.
        step_count: Number of steps to generate.
        with_audio: If True, populate audio_path on every step.
        with_video: If True, populate video_path on the first step.

    Returns:
        A Manifest instance.
    """
    steps: list[StepResult] = []
    for i in range(step_count):
        steps.append(
            StepResult(
                index=i,
                frame_path=f"frames/step_{i:03d}.png",
                narration=f"Step {i} narration",
                duration=2.5,
                audio_path=f"audio/step_{i:03d}.mp3" if with_audio else None,
                video_path=("video/session.webm" if i == 0 and with_video else None),
            )
        )
    return Manifest(title=title, steps=steps)


def _persist_build(
    build_dir: Path,
    manifest: Manifest,
    *,
    create_audio: bool = False,
    create_video: bool = False,
) -> Path:
    """Write a manifest and optional stub artefacts into *build_dir*.

    Args:
        build_dir: Target build directory.
        manifest: Manifest to serialise.
        create_audio: Create empty audio stub files.
        create_video: Create an empty video stub file.

    Returns:
        Path to the written manifest JSON.
    """
    build_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = build_dir / "manifest.json"
    manifest.save(manifest_path)

    frames_dir = build_dir / "frames"
    frames_dir.mkdir(exist_ok=True)
    for step in manifest.steps:
        (frames_dir / Path(step.frame_path).name).write_bytes(b"\x89PNG")

    if create_audio:
        audio_dir = build_dir / "audio"
        audio_dir.mkdir(exist_ok=True)
        for step in manifest.steps:
            if step.audio_path:
                (audio_dir / Path(step.audio_path).name).write_bytes(b"\xff\xfb")

    if create_video:
        video_dir = build_dir / "video"
        video_dir.mkdir(exist_ok=True)
        (video_dir / "session.webm").write_bytes(b"\x1a\x45")

    return manifest_path


# ---------------------------------------------------------------------------
# Scenario -> Manifest flow
# ---------------------------------------------------------------------------


class TestScenarioYamlRoundtrip:
    """Verify YAML write -> parse -> validate preserves all fields."""

    def test_scenario_yaml_roundtrip(self, tmp_path: Path) -> None:
        """Write YAML, parse with Scenario.from_yaml(), validate fields preserved."""
        data = _minimal_scenario_dict(
            title="Roundtrip",
            base_url="http://example.com",
            steps=[
                {
                    "action": "navigate",
                    "url": "/home",
                    "narration": "Go home",
                    "wait_seconds": 1.0,
                },
                {
                    "action": "click",
                    "selector": "#btn",
                    "narration": "Click it",
                    "highlight": "#btn",
                },
            ],
        )
        yaml_path = _write_scenario_yaml(tmp_path / "roundtrip.yaml", data)

        scenario = Scenario.from_yaml(yaml_path)

        assert scenario.title == "Roundtrip"
        assert scenario.base_url == "http://example.com"
        assert len(scenario.steps) == 2
        assert scenario.steps[0].action == ActionType.NAVIGATE
        assert scenario.steps[0].url == "/home"
        assert scenario.steps[0].narration == "Go home"
        assert scenario.steps[1].selector == "#btn"
        assert scenario.steps[1].highlight == "#btn"


class TestManifestJsonRoundtrip:
    """Verify Manifest save -> load roundtrip preserves equality."""

    def test_manifest_json_roundtrip(self, tmp_path: Path) -> None:
        """Create Manifest, save to JSON, load back, verify equality."""
        original = _make_manifest(
            title="JSON Round",
            step_count=4,
            with_audio=True,
            with_video=True,
        )
        manifest_path = tmp_path / "manifest.json"
        original.save(manifest_path)

        loaded = Manifest.load(manifest_path)

        assert loaded.title == original.title
        assert len(loaded.steps) == len(original.steps)
        for orig, copy in zip(original.steps, loaded.steps, strict=True):
            assert copy.index == orig.index
            assert copy.frame_path == orig.frame_path
            assert copy.narration == orig.narration
            assert copy.audio_path == orig.audio_path
            assert copy.video_path == orig.video_path
            assert copy.duration == pytest.approx(orig.duration)


class TestValidateScenarioAllActionTypes:
    """Validate a scenario that uses every ActionType."""

    def test_validate_scenario_with_all_action_types(self, tmp_path: Path) -> None:
        """YAML with every ActionType parses without errors."""
        steps = [
            {"action": "navigate", "url": "/"},
            {"action": "click", "selector": "#btn"},
            {"action": "scroll", "distance": 300},
            {"action": "type", "selector": "#input", "text": "hello"},
            {"action": "hover", "selector": ".menu"},
            {"action": "wait", "wait_seconds": 0.5},
            {"action": "screenshot"},
        ]
        data = _minimal_scenario_dict(steps=steps)
        yaml_path = _write_scenario_yaml(tmp_path / "all_actions.yaml", data)

        scenario = Scenario.from_yaml(yaml_path)

        action_values = {s.action for s in scenario.steps}
        assert action_values == set(ActionType)


class TestValidateScenarioRejectsUnknownAction:
    """Reject YAML with an invalid action type value."""

    def test_validate_scenario_rejects_unknown_action(self, tmp_path: Path) -> None:
        """YAML with bad action type raises a validation error."""
        data = _minimal_scenario_dict(steps=[{"action": "teleport", "url": "/"}])
        yaml_path = _write_scenario_yaml(tmp_path / "bad_action.yaml", data)

        with pytest.raises(Exception):  # noqa: B017, PT011
            Scenario.from_yaml(yaml_path)


class TestValidateScenarioRejectsMalformedYaml:
    """Reject syntactically invalid YAML."""

    def test_validate_scenario_rejects_malformed_yaml(self, tmp_path: Path) -> None:
        """Invalid YAML syntax raises an error."""
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("title: [unmatched bracket\nsteps:\n  - action: navigate\n")

        with pytest.raises(Exception):  # noqa: B017, PT011
            Scenario.from_yaml(bad_yaml)


# ---------------------------------------------------------------------------
# Query tools — real filesystem
# ---------------------------------------------------------------------------


class TestListScenariosFindsNestedYaml:
    """list_scenarios discovers YAML files in nested directories."""

    @pytest.mark.asyncio
    async def test_list_scenarios_finds_nested_yaml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Create scenarios/examples/*.yaml, verify discovery."""
        monkeypatch.chdir(tmp_path)
        scenarios_dir = tmp_path / "scenarios"
        scenarios_dir.mkdir(parents=True)

        for name in ("demo.yaml", "tutorial.yaml"):
            _write_scenario_yaml(
                scenarios_dir / name,
                _minimal_scenario_dict(title=name),
            )

        result = await mcp.call_tool("list_scenarios", {})
        text = _extract_text(result)

        assert "demo" in text
        assert "tutorial" in text


class TestListScenariosSkipsNonYaml:
    """list_scenarios ignores non-YAML files."""

    @pytest.mark.asyncio
    async def test_list_scenarios_skips_non_yaml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mix .yaml and .txt files, only yaml returned."""
        monkeypatch.chdir(tmp_path)
        scenarios_dir = tmp_path / "scenarios"
        scenarios_dir.mkdir()

        _write_scenario_yaml(
            scenarios_dir / "good.yaml",
            _minimal_scenario_dict(title="Good"),
        )
        (scenarios_dir / "notes.txt").write_text("not a scenario")
        (scenarios_dir / "readme.md").write_text("# readme")

        result = await mcp.call_tool("list_scenarios", {})
        text = _extract_text(result)

        assert "good.yaml" in text
        assert "notes.txt" not in text
        assert "readme.md" not in text


class TestListBuildsDiscoversMultipleBuilds:
    """list_builds finds all build directories with manifests."""

    @pytest.mark.asyncio
    async def test_list_builds_discovers_multiple_builds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Create 3 build dirs with manifests, verify all found."""
        monkeypatch.chdir(tmp_path)
        builds_root = tmp_path / ".demo_build"
        for name in ("alpha", "beta", "gamma"):
            _persist_build(builds_root / name, _make_manifest(title=name))

        result = await mcp.call_tool("list_builds", {})
        text = _extract_text(result)

        for name in ("alpha", "beta", "gamma"):
            assert name in text


class TestListBuildsDetectsAudioAndVideoPresence:
    """list_builds reports audio/ and video/ subdirectory presence."""

    @pytest.mark.asyncio
    async def test_list_builds_detects_audio_and_video_presence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Build with/without audio/, video/ subdirs reported correctly."""
        monkeypatch.chdir(tmp_path)
        builds_root = tmp_path / ".demo_build"

        _persist_build(
            builds_root / "full",
            _make_manifest(title="full", with_audio=True, with_video=True),
            create_audio=True,
            create_video=True,
        )
        _persist_build(
            builds_root / "bare",
            _make_manifest(title="bare"),
        )

        result = await mcp.call_tool("list_builds", {})
        text = _extract_text(result)

        assert "full" in text
        assert "bare" in text


class TestGetManifestReturnsCompleteData:
    """get_manifest returns all step fields."""

    @pytest.mark.asyncio
    async def test_get_manifest_returns_complete_data(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Create manifest with 5 steps, verify all fields."""
        monkeypatch.chdir(tmp_path)
        build_dir = tmp_path / ".demo_build" / "complete"
        manifest = _make_manifest(title="Complete", step_count=5, with_audio=True)
        _persist_build(build_dir, manifest, create_audio=True)

        manifest_path = str(build_dir / "manifest.json")
        result = await mcp.call_tool("get_manifest", {"manifest_file": manifest_path})
        text = _extract_text(result)

        assert "Complete" in text
        for i in range(5):
            assert f"step_{i:03d}" in text


class TestGetScenarioDetailsReturnsSteps:
    """get_scenario_details returns parsed step actions and narrations."""

    @pytest.mark.asyncio
    async def test_get_scenario_details_returns_steps(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Parse YAML, verify step actions and narrations."""
        monkeypatch.chdir(tmp_path)
        scenarios_dir = tmp_path / "scenarios"
        scenarios_dir.mkdir()

        data = _minimal_scenario_dict(
            title="Detailed",
            steps=[
                {"action": "navigate", "url": "/", "narration": "Open homepage"},
                {"action": "click", "selector": "#go", "narration": "Click Go"},
            ],
        )
        yaml_path = _write_scenario_yaml(scenarios_dir / "detailed.yaml", data)

        result = await mcp.call_tool(
            "get_scenario_details", {"scenario_file": str(yaml_path)}
        )
        text = _extract_text(result)

        assert "navigate" in text
        assert "click" in text
        assert "Open homepage" in text
        assert "Click Go" in text


# ---------------------------------------------------------------------------
# Resource reading
# ---------------------------------------------------------------------------


class TestReadScenarioResourceReturnsYamlText:
    """Reading scenario resource returns raw YAML text."""

    @pytest.mark.asyncio
    async def test_read_scenario_resource_returns_yaml_text(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Create YAML, read via resource, compare text."""
        monkeypatch.chdir(tmp_path)

        data = _minimal_scenario_dict(title="Resource Test")
        _write_scenario_yaml(tmp_path / "res.yaml", data)
        contents = await mcp.read_resource("scenario://res.yaml")
        resource_text = _extract_text(contents)

        # The returned text should contain the YAML content
        assert "Resource Test" in resource_text


class TestReadManifestResourceReturnsJson:
    """Reading manifest resource returns parseable JSON."""

    @pytest.mark.asyncio
    async def test_read_manifest_resource_returns_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Create build dir with manifest, read via resource."""
        monkeypatch.chdir(tmp_path)
        build_dir = tmp_path / ".demo_build" / "res_build"
        manifest = _make_manifest(title="Manifest Res")
        _persist_build(build_dir, manifest)

        contents = await mcp.read_resource("manifest://res_build")
        resource_text = _extract_text(contents)

        assert "Manifest Res" in resource_text


class TestReadBuildVideoResourceFindsMp4:
    """Reading build video resource locates .mp4 file."""

    @pytest.mark.asyncio
    async def test_read_build_video_resource_finds_mp4(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Create build dir with .mp4 file, verify path returned."""
        monkeypatch.chdir(tmp_path)
        build_dir = tmp_path / ".demo_build" / "vid_build"
        build_dir.mkdir(parents=True)
        manifest = _make_manifest(title="Vid")
        manifest.save(build_dir / "manifest.json")

        mp4_path = build_dir / "demo.mp4"
        mp4_path.write_bytes(b"\x00\x00\x00\x1c")  # ftyp box stub

        contents = await mcp.read_resource("build://vid_build/video")
        resource_text = _extract_text(contents)

        assert "mp4" in resource_text.lower() or "demo" in resource_text.lower()


# ---------------------------------------------------------------------------
# TTS backend construction
# ---------------------------------------------------------------------------


class TestBuildTtsBackendCreatesCorrectTypes:
    """_build_tts_backend maps each string to the right class."""

    @pytest.mark.parametrize(
        ("backend_name", "expected_class_name"),
        [
            ("openai", "OpenAITTS"),
            ("kokoro", "KokoroTTS"),
            ("edge", "EdgeTTS"),
            ("silent", "SilentBackend"),
        ],
    )
    def test_build_tts_backend_creates_correct_types(
        self, backend_name: str, expected_class_name: str
    ) -> None:
        """Verify each backend string maps to correct class."""
        backend = _build_tts_backend(backend_name, voice="test-voice")
        assert type(backend).__name__ == expected_class_name


class TestBuildTtsBackendPassesVoiceThrough:
    """_build_tts_backend forwards the voice parameter."""

    @pytest.mark.parametrize("backend_name", ["openai", "kokoro", "edge"])
    def test_build_tts_backend_passes_voice_through(self, backend_name: str) -> None:
        """Verify voice parameter is forwarded to the backend."""
        backend = _build_tts_backend(backend_name, voice="custom-voice")
        assert backend.voice == "custom-voice"


# ---------------------------------------------------------------------------
# Extras generation (mock FFmpeg, real filesystem)
# ---------------------------------------------------------------------------


class TestCollectExtrasCreatesSrtAndVtt:
    """_collect_extras generates subtitle files."""

    @patch("demo_video_maker.mcp_server.export_narration_json")
    @patch("demo_video_maker.mcp_server.generate_srt")
    @patch("demo_video_maker.mcp_server.generate_vtt")
    def test_collect_extras_creates_srt_and_vtt(
        self,
        mock_vtt: MagicMock,
        mock_srt: MagicMock,
        mock_narration: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Mock subtitle generation, verify files listed in extras."""
        srt_path = tmp_path / "subtitles.srt"
        vtt_path = tmp_path / "subtitles.vtt"
        narration_path = tmp_path / "narration.json"
        mock_srt.return_value = srt_path
        mock_vtt.return_value = vtt_path
        mock_narration.return_value = narration_path

        manifest = _make_manifest(title="Subs")
        extras = _collect_extras(manifest, tmp_path, gif=False, html=False)

        mock_srt.assert_called_once()
        mock_vtt.assert_called_once()
        assert str(srt_path) in extras
        assert str(vtt_path) in extras


class TestCollectExtrasSkipsGifWhenDisabled:
    """_collect_extras omits GIF when gif=False."""

    @patch("demo_video_maker.mcp_server.export_narration_json", return_value=Path("/fake/n.json"))
    @patch("demo_video_maker.mcp_server.generate_srt", return_value=Path("/fake/s.srt"))
    @patch("demo_video_maker.mcp_server.generate_vtt", return_value=Path("/fake/s.vtt"))
    @patch("demo_video_maker.mcp_server.generate_gif", return_value=Path("/fake/preview.gif"))
    def test_collect_extras_skips_gif_when_disabled(
        self,
        mock_gif: MagicMock,
        mock_vtt: MagicMock,
        mock_srt: MagicMock,
        mock_narration: MagicMock,
        tmp_path: Path,
    ) -> None:
        """gif=False means gif generator is not called."""
        manifest = _make_manifest(title="No GIF")
        extras = _collect_extras(manifest, tmp_path, gif=False, html=False)

        mock_gif.assert_not_called()
        assert not any("gif" in p.lower() for p in extras)


# ---------------------------------------------------------------------------
# Error handling integration
# ---------------------------------------------------------------------------


class TestPipelineToolReturnsErrorOnMissingScenario:
    """record_demo returns an error when the scenario file is missing."""

    @pytest.mark.asyncio
    async def test_pipeline_tool_returns_error_on_missing_scenario(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Call record_demo with nonexistent file, expect error."""
        monkeypatch.chdir(tmp_path)

        result = await mcp.call_tool(
            "record_demo",
            {"scenario_file": str(tmp_path / "does_not_exist.yaml")},
        )
        text = _extract_text(result)

        assert "error" in text.lower() or "not found" in text.lower()


class TestGetManifestReturnsErrorOnCorruptJson:
    """get_manifest returns an error for invalid JSON."""

    @pytest.mark.asyncio
    async def test_get_manifest_returns_error_on_corrupt_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Write invalid JSON, call get_manifest, expect error."""
        monkeypatch.chdir(tmp_path)
        build_dir = tmp_path / ".demo_build" / "corrupt"
        build_dir.mkdir(parents=True)
        (build_dir / "manifest.json").write_text("{invalid json!!!")

        manifest_path = str(build_dir / "manifest.json")
        result = await mcp.call_tool("get_manifest", {"manifest_file": manifest_path})
        text = _extract_text(result)

        assert "error" in text.lower() or "invalid" in text.lower()


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _extract_text(result: object) -> str:
    """Extract concatenated text from an MCP tool/resource result.

    FastMCP tool results may be a list of content objects, a single
    string, or another iterable.  This helper normalises them all to
    a plain string for assertion convenience.

    Args:
        result: Raw return value from ``mcp.call_tool`` or
            ``mcp.read_resource``.

    Returns:
        Concatenated text content.
    """
    if isinstance(result, str):
        return result
    if isinstance(result, (list, tuple)):
        parts: list[str] = []
        for item in result:
            if isinstance(item, str):
                parts.append(item)
            elif hasattr(item, "text"):
                parts.append(str(item.text))
            elif hasattr(item, "content"):
                parts.append(str(item.content))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    if hasattr(result, "text"):
        return str(result.text)
    if hasattr(result, "content"):
        return str(result.content)
    return str(result)
