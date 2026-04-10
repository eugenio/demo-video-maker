"""Unit tests for the demo-video-maker MCP server."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from demo_video_maker.mcp_server import (
    _build_tts_backend,
    _collect_extras,
    _resolve_work_dir,
    capture_screenshots,
    create_scenario_prompt,
    debug_build_prompt,
    get_manifest,
    get_scenario_details,
    list_builds,
    list_scenarios,
    list_tts_voices,
    narrate_manifest,
    read_build_video_resource,
    read_manifest_resource,
    read_scenario_resource,
    record_demo,
    stitch_video_tool,
    validate_scenario,
)
from demo_video_maker.models import Manifest, StepResult
from demo_video_maker.narrator import EdgeTTS, KokoroTTS, OpenAITTS, SilentBackend

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_scenario(
    path: Path,
    title: str = "Test Scenario",
    steps: int = 2,
) -> Path:
    """Create a minimal scenario YAML file.

    Args:
        path: File path to write.
        title: Scenario title.
        steps: Number of navigate steps to include.

    Returns:
        Path to the written file.
    """
    data: dict[str, Any] = {
        "title": title,
        "base_url": "http://localhost:8080",
        "steps": [
            {"action": "navigate", "url": f"/page{i}", "narration": f"Step {i}"}
            for i in range(steps)
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data))
    return path


def _write_manifest(
    path: Path,
    title: str = "Test Build",
    steps: int = 3,
    *,
    with_audio: bool = False,
) -> Path:
    """Create a minimal manifest JSON file.

    Args:
        path: File path to write.
        title: Manifest title.
        steps: Number of step results.
        with_audio: Whether to include audio_path on even steps.

    Returns:
        Path to the written file.
    """
    step_results = [
        StepResult(
            index=i,
            frame_path=f"frames/step_{i:03d}.png",
            narration=f"Narration {i}" if i % 2 == 0 else "",
            duration=2.0,
            audio_path=f"audio/step_{i:03d}.mp3" if with_audio and i % 2 == 0 else None,
        )
        for i in range(steps)
    ]
    manifest = Manifest(title=title, steps=step_results)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest.save(path)
    return path


# ---------------------------------------------------------------------------
# TestHelpers
# ---------------------------------------------------------------------------


class TestHelpers:
    """Unit tests for helper functions."""

    def test_build_tts_backend_kokoro(self) -> None:
        """Kokoro backend is returned for 'kokoro' key."""
        backend = _build_tts_backend("kokoro", None)
        assert isinstance(backend, KokoroTTS)
        assert backend.voice == "af_heart"

    def test_build_tts_backend_openai(self) -> None:
        """OpenAI backend is returned for 'openai' key."""
        backend = _build_tts_backend("openai", None)
        assert isinstance(backend, OpenAITTS)
        assert backend.voice == "onyx"

    def test_build_tts_backend_edge(self) -> None:
        """Edge backend is returned with default voice."""
        backend = _build_tts_backend("edge", None)
        assert isinstance(backend, EdgeTTS)
        assert backend.voice == "en-US-AvaMultilingualNeural"

    def test_build_tts_backend_silent(self) -> None:
        """Silent backend is returned for 'silent' key."""
        backend = _build_tts_backend("silent", None)
        assert isinstance(backend, SilentBackend)

    def test_build_tts_backend_invalid_raises(self) -> None:
        """Unknown backend name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown TTS backend"):
            _build_tts_backend("nonexistent", None)

    def test_build_tts_backend_kokoro_with_custom_voice(self) -> None:
        """Custom voice is forwarded to the Kokoro backend."""
        backend = _build_tts_backend("kokoro", "am_michael")
        assert isinstance(backend, KokoroTTS)
        assert backend.voice == "am_michael"

    def test_build_tts_backend_openai_scenario_voice(self) -> None:
        """OpenAI backend uses scenario_voice as fallback when voice is None."""
        backend = _build_tts_backend("openai", None, scenario_voice="nova")
        assert isinstance(backend, OpenAITTS)
        assert backend.voice == "nova"

    def test_resolve_work_dir_from_scenario(self) -> None:
        """Work dir is derived from the scenario file stem."""
        result = _resolve_work_dir("scenarios/my_demo.yaml", None)
        assert result == Path(".demo_build") / "my_demo"

    def test_resolve_work_dir_explicit(self) -> None:
        """Explicit work_dir takes precedence."""
        result = _resolve_work_dir("s.yaml", "/tmp/custom")  # noqa: S108
        assert result == Path("/tmp/custom")  # noqa: S108

    def test_resolve_work_dir_default(self) -> None:
        """Falls back to .demo_build/default when no hints given."""
        result = _resolve_work_dir(None, None)
        assert result == Path(".demo_build") / "default"

    @patch("demo_video_maker.mcp_server.generate_srt", return_value=Path("/out/subtitles.srt"))
    @patch("demo_video_maker.mcp_server.generate_vtt", return_value=Path("/out/subtitles.vtt"))
    @patch(
        "demo_video_maker.mcp_server.export_narration_json",
        return_value=Path("/out/narration.json"),
    )
    def test_collect_extras_generates_default_files(
        self,
        mock_narr: MagicMock,
        mock_vtt: MagicMock,
        mock_srt: MagicMock,
    ) -> None:
        """Default extras include SRT, VTT, and narration JSON."""
        manifest = Manifest(title="T", steps=[])
        extras = _collect_extras(manifest, Path("/out"), gif=False, html=False)
        assert len(extras) == 3
        assert "/out/subtitles.srt" in extras
        assert "/out/subtitles.vtt" in extras
        assert "/out/narration.json" in extras

    @patch("demo_video_maker.mcp_server.generate_srt", return_value=Path("/o/s.srt"))
    @patch("demo_video_maker.mcp_server.generate_vtt", return_value=Path("/o/s.vtt"))
    @patch("demo_video_maker.mcp_server.export_narration_json", return_value=Path("/o/n.json"))
    @patch("demo_video_maker.mcp_server.generate_gif", return_value=Path("/o/preview.gif"))
    @patch(
        "demo_video_maker.mcp_server.generate_html_tutorial",
        return_value=Path("/o/tutorial.html"),
    )
    def test_collect_extras_generates_gif_and_html_when_flags_set(
        self,
        mock_html: MagicMock,
        mock_gif: MagicMock,
        mock_narr: MagicMock,
        mock_vtt: MagicMock,
        mock_srt: MagicMock,
    ) -> None:
        """GIF and HTML are added to extras when flags are True."""
        manifest = Manifest(title="T", steps=[])
        extras = _collect_extras(manifest, Path("/o"), gif=True, html=True)
        assert len(extras) == 5
        mock_gif.assert_called_once()
        mock_html.assert_called_once()


# ---------------------------------------------------------------------------
# TestRecordDemo
# ---------------------------------------------------------------------------


class TestRecordDemo:
    """Unit tests for record_demo tool."""

    async def test_record_demo_returns_video_path_when_successful(
        self,
        tmp_path: Path,
    ) -> None:
        """Successful recording returns status ok with video path."""
        scenario_file = _write_scenario(tmp_path / "s.yaml")
        manifest = Manifest(
            title="Test",
            steps=[StepResult(index=0, frame_path="f.png", narration="Hi")],
        )

        with (
            patch("demo_video_maker.mcp_server.asyncio.to_thread") as mock_to_thread,
            patch("demo_video_maker.mcp_server.Scenario") as mock_scenario_cls,
            patch(
                "demo_video_maker.mcp_server.record_scenario",
                new_callable=AsyncMock,
                return_value=manifest,
            ),
        ):
            mock_scenario = MagicMock()
            mock_scenario.steps = []
            mock_scenario.voice = "onyx"
            mock_scenario_cls.from_yaml.return_value = mock_scenario
            # screenshot mode + cursor=True (default):
            # 1. Scenario.from_yaml -> scenario
            # 2. apply_cursors_to_manifest -> manifest
            # 3. generate_narration -> manifest
            # 4. manifest.save -> None
            # 5. _stitch_video_impl -> None
            # 6. _collect_extras -> []
            mock_to_thread.side_effect = [
                mock_scenario,   # Scenario.from_yaml
                manifest,        # apply_cursors_to_manifest
                manifest,        # generate_narration
                None,            # manifest.save
                None,            # _stitch_video_impl
                [],              # _collect_extras
            ]

            result = await record_demo(
                scenario_file=str(scenario_file),
                mode="screenshot",
            )

        assert result["status"] == "ok"
        assert result["video"] == "demo.mp4"
        assert "manifest" in result

    async def test_record_demo_returns_error_when_scenario_not_found(self) -> None:
        """Missing scenario file returns error dict."""
        result = await record_demo(
            scenario_file="/nonexistent/scenario.yaml",
        )

        assert "error" in result

    async def test_record_demo_uses_correct_tts_backend(
        self,
        tmp_path: Path,
    ) -> None:
        """Clip mode calls pre_generate_audio with the chosen backend."""
        scenario_file = _write_scenario(tmp_path / "s.yaml")
        manifest = Manifest(
            title="Test",
            steps=[StepResult(index=0, frame_path="f.png", narration="Hi")],
        )

        with (
            patch("demo_video_maker.mcp_server.asyncio.to_thread") as mock_to_thread,
            patch("demo_video_maker.mcp_server.Scenario") as mock_scenario_cls,
            patch(
                "demo_video_maker.mcp_server.record_scenario",
                new_callable=AsyncMock,
                return_value=manifest,
            ),
        ):
            mock_scenario = MagicMock()
            mock_scenario.steps = []
            mock_scenario.voice = "onyx"
            mock_scenario_cls.from_yaml.return_value = mock_scenario
            mock_to_thread.side_effect = [
                mock_scenario,   # Scenario.from_yaml
                {},              # pre_generate_audio
                None,            # manifest.save
                None,            # _stitch_video_impl
                [],              # _collect_extras
            ]

            await record_demo(
                scenario_file=str(scenario_file),
                tts="edge",
                mode="clip",
            )

        # The second to_thread call is pre_generate_audio
        pre_call = mock_to_thread.call_args_list[1]
        backend_arg = pre_call[0][3]  # pre_generate_audio(steps, dir, backend)
        assert isinstance(backend_arg, EdgeTTS)

    async def test_record_demo_defaults_work_dir_to_demo_build(
        self,
        tmp_path: Path,
    ) -> None:
        """Work dir defaults to .demo_build/<stem> when not specified."""
        scenario_file = _write_scenario(tmp_path / "my_app.yaml")
        manifest = Manifest(
            title="Test",
            steps=[StepResult(index=0, frame_path="f.png")],
        )

        with (
            patch("demo_video_maker.mcp_server.asyncio.to_thread") as mock_to_thread,
            patch("demo_video_maker.mcp_server.Scenario") as mock_scenario_cls,
            patch(
                "demo_video_maker.mcp_server.record_scenario",
                new_callable=AsyncMock,
                return_value=manifest,
            ),
        ):
            mock_scenario = MagicMock()
            mock_scenario.steps = []
            mock_scenario.voice = "onyx"
            mock_scenario_cls.from_yaml.return_value = mock_scenario
            mock_to_thread.side_effect = [
                mock_scenario, manifest, manifest, None, None, [],
            ]

            result = await record_demo(
                scenario_file=str(scenario_file),
                mode="screenshot",
            )

        assert result["status"] == "ok"
        assert "my_app" in result["manifest"]

    async def test_record_demo_generates_extras_when_flags_set(
        self,
        tmp_path: Path,
    ) -> None:
        """GIF and HTML flags are forwarded to _collect_extras."""
        scenario_file = _write_scenario(tmp_path / "s.yaml")
        manifest = Manifest(
            title="Test",
            steps=[StepResult(index=0, frame_path="f.png")],
        )

        with (
            patch("demo_video_maker.mcp_server.asyncio.to_thread") as mock_to_thread,
            patch("demo_video_maker.mcp_server.Scenario") as mock_scenario_cls,
            patch(
                "demo_video_maker.mcp_server.record_scenario",
                new_callable=AsyncMock,
                return_value=manifest,
            ),
        ):
            mock_scenario = MagicMock()
            mock_scenario.steps = []
            mock_scenario.voice = "onyx"
            mock_scenario_cls.from_yaml.return_value = mock_scenario
            # screenshot mode + cursor=True:
            # Scenario.from_yaml, apply_cursors, generate_narration,
            # manifest.save, _stitch_video_impl, _collect_extras
            mock_to_thread.side_effect = [
                mock_scenario, manifest, manifest, None, None, ["a.srt", "a.gif"],
            ]

            await record_demo(
                scenario_file=str(scenario_file),
                mode="screenshot",
                gif=True,
                html=True,
            )

        # The _collect_extras call is the 6th to_thread call (index 5)
        extras_call = mock_to_thread.call_args_list[5]
        assert extras_call[1]["gif"] is True
        assert extras_call[1]["html"] is True


# ---------------------------------------------------------------------------
# TestCaptureScreenshots
# ---------------------------------------------------------------------------


class TestCaptureScreenshots:
    """Unit tests for capture_screenshots tool."""

    async def test_capture_returns_frame_count(self, tmp_path: Path) -> None:
        """Successful capture returns frame count matching manifest steps."""
        scenario_file = _write_scenario(tmp_path / "s.yaml", steps=4)
        manifest = Manifest(
            title="Test",
            steps=[StepResult(index=i, frame_path=f"f{i}.png") for i in range(4)],
        )

        with (
            patch("demo_video_maker.mcp_server.asyncio.to_thread") as mock_to_thread,
            patch(
                "demo_video_maker.mcp_server.record_scenario",
                new_callable=AsyncMock,
                return_value=manifest,
            ),
        ):
            mock_to_thread.return_value = MagicMock()  # Scenario.from_yaml

            result = await capture_screenshots(
                scenario_file=str(scenario_file),
            )

        assert result["status"] == "ok"
        assert result["frame_count"] == 4

    async def test_capture_returns_error_when_file_missing(self) -> None:
        """Missing scenario file returns error dict."""
        result = await capture_screenshots(
            scenario_file="/no/such/file.yaml",
        )

        assert "error" in result


# ---------------------------------------------------------------------------
# TestNarrateManifest
# ---------------------------------------------------------------------------


class TestNarrateManifest:
    """Unit tests for narrate_manifest tool."""

    async def test_narrate_produces_video(self, tmp_path: Path) -> None:
        """Narrate produces a video and returns ok status."""
        manifest_path = _write_manifest(tmp_path / "build" / "manifest.json")
        narrated = Manifest(
            title="T",
            steps=[StepResult(index=0, frame_path="f.png", audio_path="a.mp3")],
        )

        with patch("demo_video_maker.mcp_server.asyncio.to_thread") as mock_to_thread:
            mock_to_thread.side_effect = [
                Manifest.load(manifest_path),  # Manifest.load
                narrated,                       # generate_narration
                None,                           # _stitch_video_impl
                [],                             # _collect_extras
            ]

            result = await narrate_manifest(
                manifest_file=str(manifest_path),
            )

        assert result["status"] == "ok"
        assert result["video"] == "demo.mp4"

    async def test_narrate_returns_error_on_invalid_manifest(self) -> None:
        """Missing manifest returns error dict."""
        result = await narrate_manifest(
            manifest_file="/missing/manifest.json",
        )

        assert "error" in result


# ---------------------------------------------------------------------------
# TestStitchVideo
# ---------------------------------------------------------------------------


class TestStitchVideo:
    """Unit tests for stitch_video_tool."""

    async def test_stitch_returns_video_path(self, tmp_path: Path) -> None:
        """Stitch returns the output video path."""
        manifest_path = _write_manifest(tmp_path / "build" / "manifest.json")

        with patch("demo_video_maker.mcp_server.asyncio.to_thread") as mock_to_thread:
            mock_to_thread.side_effect = [
                Manifest.load(manifest_path),  # Manifest.load
                None,                           # _stitch_video_impl
                [],                             # _collect_extras
            ]

            result = await stitch_video_tool(
                manifest_file=str(manifest_path),
            )

        assert result["status"] == "ok"
        assert result["video"] == "demo.mp4"

    async def test_stitch_with_custom_gap(self, tmp_path: Path) -> None:
        """Custom gap is forwarded to _stitch_video_impl."""
        manifest_path = _write_manifest(tmp_path / "build" / "manifest.json")

        with patch("demo_video_maker.mcp_server.asyncio.to_thread") as mock_to_thread:
            mock_to_thread.side_effect = [
                Manifest.load(manifest_path),
                None,
                [],
            ]

            await stitch_video_tool(
                manifest_file=str(manifest_path),
                gap=1.5,
            )

        # The second call is _stitch_video_impl
        stitch_call = mock_to_thread.call_args_list[1]
        assert stitch_call[1]["transition_gap"] == 1.5

    async def test_stitch_returns_error_on_missing_manifest(self) -> None:
        """Missing manifest returns error dict."""
        result = await stitch_video_tool(
            manifest_file="/no/manifest.json",
        )

        assert "error" in result


# ---------------------------------------------------------------------------
# TestListScenarios
# ---------------------------------------------------------------------------


class TestListScenarios:
    """Unit tests for list_scenarios tool."""

    async def test_list_scenarios_finds_yaml_files(self, tmp_path: Path) -> None:
        """YAML files in the directory are discovered."""
        sd = tmp_path / "scenarios"
        _write_scenario(sd / "demo1.yaml", title="Demo One", steps=3)
        _write_scenario(sd / "demo2.yaml", title="Demo Two", steps=1)

        result = await list_scenarios(scenarios_dir=str(sd))

        names = [s["name"] for s in result["scenarios"]]
        assert "demo1" in names
        assert "demo2" in names

    async def test_list_scenarios_returns_empty_when_dir_missing(self) -> None:
        """Non-existent directory returns empty list."""
        result = await list_scenarios(scenarios_dir="/nonexistent/dir")

        assert result["scenarios"] == []

    async def test_list_scenarios_includes_title_and_step_count(
        self,
        tmp_path: Path,
    ) -> None:
        """Each scenario entry contains title and step_count."""
        sd = tmp_path / "scenarios"
        _write_scenario(sd / "app.yaml", title="My App", steps=5)

        result = await list_scenarios(scenarios_dir=str(sd))

        entry = result["scenarios"][0]
        assert entry["title"] == "My App"
        assert entry["step_count"] == 5
        assert entry["path"] == str(sd / "app.yaml")

    async def test_list_scenarios_skips_invalid_yaml(self, tmp_path: Path) -> None:
        """Invalid YAML files are silently skipped."""
        sd = tmp_path / "scenarios"
        sd.mkdir(parents=True)
        (sd / "bad.yaml").write_text("not: valid: yaml: [[[")
        _write_scenario(sd / "good.yaml", title="Good")

        result = await list_scenarios(scenarios_dir=str(sd))

        names = [s["name"] for s in result["scenarios"]]
        assert "good" in names
        assert "bad" not in names


# ---------------------------------------------------------------------------
# TestValidateScenario
# ---------------------------------------------------------------------------


class TestValidateScenario:
    """Unit tests for validate_scenario tool."""

    async def test_valid_scenario_returns_true(self, tmp_path: Path) -> None:
        """Well-formed scenario file passes validation."""
        sf = _write_scenario(tmp_path / "ok.yaml")

        result = await validate_scenario(scenario_file=str(sf))

        assert result["valid"] is True
        assert result["errors"] == []
        assert result["scenario"]["title"] == "Test Scenario"

    async def test_invalid_yaml_returns_errors(self, tmp_path: Path) -> None:
        """Invalid YAML content returns validation errors."""
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("title: Missing steps\n")

        result = await validate_scenario(scenario_file=str(bad_file))

        assert result["valid"] is False
        assert len(result["errors"]) > 0

    async def test_missing_file_returns_error(self) -> None:
        """Non-existent file returns invalid with file-not-found error."""
        result = await validate_scenario(scenario_file="/nope.yaml")

        assert result["valid"] is False
        assert any(
            "not found" in e.lower() or "no such file" in e.lower()
            for e in result["errors"]
        )


# ---------------------------------------------------------------------------
# TestListBuilds
# ---------------------------------------------------------------------------


class TestListBuilds:
    """Unit tests for list_builds tool."""

    async def test_list_builds_finds_manifests(self, tmp_path: Path) -> None:
        """Build directories with manifests are discovered."""
        _write_manifest(tmp_path / "build_a" / "manifest.json", title="Build A")
        _write_manifest(tmp_path / "build_b" / "manifest.json", title="Build B")

        result = await list_builds(work_dir=str(tmp_path))

        names = [b["name"] for b in result["builds"]]
        assert "build_a" in names
        assert "build_b" in names

    async def test_list_builds_returns_empty_when_dir_missing(self) -> None:
        """Non-existent work_dir returns empty list."""
        result = await list_builds(work_dir="/nonexistent")

        assert result["builds"] == []

    async def test_list_builds_detects_video_and_audio(self, tmp_path: Path) -> None:
        """Build metadata includes has_video and has_audio flags."""
        build_dir = tmp_path / "my_build"
        _write_manifest(
            build_dir / "manifest.json",
            title="AV Build",
            with_audio=True,
        )
        # Create a dummy video file
        (build_dir / "demo.mp4").write_bytes(b"\x00")

        result = await list_builds(work_dir=str(tmp_path))

        build = result["builds"][0]
        assert build["has_video"] is True
        assert build["has_audio"] is True

    async def test_list_builds_no_video_no_audio(self, tmp_path: Path) -> None:
        """Build without video or audio reports False for both."""
        _write_manifest(
            tmp_path / "empty_build" / "manifest.json",
            title="Plain",
            with_audio=False,
        )

        result = await list_builds(work_dir=str(tmp_path))

        build = result["builds"][0]
        assert build["has_video"] is False
        assert build["has_audio"] is False


# ---------------------------------------------------------------------------
# TestGetManifest
# ---------------------------------------------------------------------------


class TestGetManifest:
    """Unit tests for get_manifest tool."""

    async def test_returns_manifest_dict(self, tmp_path: Path) -> None:
        """Existing manifest is returned as a dict."""
        manifest_path = _write_manifest(
            tmp_path / "build" / "manifest.json",
            title="My Build",
            steps=2,
        )

        result = await get_manifest(manifest_file=str(manifest_path))

        assert result["title"] == "My Build"
        assert len(result["steps"]) == 2

    async def test_returns_error_when_file_missing(self) -> None:
        """Missing file returns error dict."""
        result = await get_manifest(manifest_file="/no/manifest.json")

        assert "error" in result


# ---------------------------------------------------------------------------
# TestListTtsVoices
# ---------------------------------------------------------------------------


class TestListTtsVoices:
    """Unit tests for list_tts_voices tool."""

    async def test_returns_all_backends(self) -> None:
        """No filter returns all four backend groups."""
        result = await list_tts_voices()

        backends = result["backends"]
        assert "kokoro" in backends
        assert "openai" in backends
        assert "edge" in backends
        assert "silent" in backends

    async def test_filters_by_backend(self) -> None:
        """Specifying a backend returns only that one."""
        result = await list_tts_voices(backend="openai")

        assert list(result["backends"].keys()) == ["openai"]
        assert "onyx" in result["backends"]["openai"]["voices"]

    async def test_unknown_backend_returns_error(self) -> None:
        """Unknown backend name returns error dict."""
        result = await list_tts_voices(backend="imaginary")

        assert "error" in result

    async def test_each_backend_has_default_voice(self) -> None:
        """Every backend entry includes a default voice key."""
        result = await list_tts_voices()

        for name, info in result["backends"].items():
            assert "default" in info, f"Backend {name!r} missing 'default' key"
            assert "voices" in info, f"Backend {name!r} missing 'voices' key"


# ---------------------------------------------------------------------------
# TestGetScenarioDetails
# ---------------------------------------------------------------------------


class TestGetScenarioDetails:
    """Unit tests for get_scenario_details tool."""

    async def test_returns_full_scenario_dict(self, tmp_path: Path) -> None:
        """Valid scenario returns its full model dump."""
        sf = _write_scenario(tmp_path / "app.yaml", title="Full Detail", steps=3)

        result = await get_scenario_details(scenario_file=str(sf))

        assert result["title"] == "Full Detail"
        assert len(result["steps"]) == 3
        assert result["base_url"] == "http://localhost:8080"

    async def test_returns_error_for_invalid_file(self) -> None:
        """Non-existent scenario returns error."""
        result = await get_scenario_details(scenario_file="/missing.yaml")

        assert "error" in result

    async def test_returns_error_for_malformed_yaml(self, tmp_path: Path) -> None:
        """Malformed YAML returns error dict."""
        bad = tmp_path / "bad.yaml"
        bad.write_text("not: valid: yaml: [[[")

        result = await get_scenario_details(scenario_file=str(bad))

        assert "error" in result


# ---------------------------------------------------------------------------
# TestResources
# ---------------------------------------------------------------------------


class TestResources:
    """Unit tests for MCP resources."""

    async def test_scenario_resource_returns_yaml(self, tmp_path: Path) -> None:
        """scenario:// resource returns raw YAML text."""
        sf = _write_scenario(tmp_path / "demo.yaml", title="Resource Test")

        text = await read_scenario_resource(str(sf))

        assert "Resource Test" in text

    async def test_manifest_resource_returns_json(self, tmp_path: Path) -> None:
        """manifest:// resource returns manifest JSON."""
        build_dir = tmp_path / ".demo_build" / "test_build"
        _write_manifest(build_dir / "manifest.json", title="Manifest Resource")

        old_cwd = os.getcwd()
        os.chdir(str(tmp_path))
        try:
            text = await read_manifest_resource("test_build")
        finally:
            os.chdir(old_cwd)

        data = json.loads(text)
        assert data["title"] == "Manifest Resource"

    async def test_build_video_resource_returns_path(self, tmp_path: Path) -> None:
        """build:// video resource returns an absolute path string."""
        build_dir = tmp_path / ".demo_build" / "my_build"
        build_dir.mkdir(parents=True)
        (build_dir / "demo.mp4").write_bytes(b"\x00")

        old_cwd = os.getcwd()
        os.chdir(str(tmp_path))
        try:
            result = await read_build_video_resource("my_build")
        finally:
            os.chdir(old_cwd)

        assert "my_build" in result
        assert "demo.mp4" in result

    async def test_build_video_resource_raises_when_no_mp4(self, tmp_path: Path) -> None:
        """build:// video resource raises when no MP4 exists."""
        build_dir = tmp_path / ".demo_build" / "empty_build"
        build_dir.mkdir(parents=True)

        old_cwd = os.getcwd()
        os.chdir(str(tmp_path))
        try:
            with pytest.raises(FileNotFoundError, match="No MP4"):
                await read_build_video_resource("empty_build")
        finally:
            os.chdir(old_cwd)


# ---------------------------------------------------------------------------
# TestPrompts
# ---------------------------------------------------------------------------


class TestPrompts:
    """Unit tests for MCP prompts."""

    async def test_create_scenario_prompt_contains_app_name(self) -> None:
        """create_scenario returns prompt text containing the app name."""
        text = await create_scenario_prompt("MyApp", "http://localhost:3000")

        assert isinstance(text, str)
        assert "MyApp" in text
        assert "http://localhost:3000" in text

    async def test_create_scenario_prompt_includes_actions(self) -> None:
        """create_scenario includes available action types."""
        text = await create_scenario_prompt("TestApp", "http://test.local")

        assert "navigate" in text
        assert "click" in text
        assert "scroll" in text

    async def test_create_scenario_prompt_includes_step_fields(self) -> None:
        """create_scenario includes step field reference."""
        text = await create_scenario_prompt("TestApp", "http://test.local")

        assert "selector" in text
        assert "narration" in text

    async def test_debug_build_prompt_with_existing_manifest(
        self,
        tmp_path: Path,
    ) -> None:
        """debug_build includes manifest contents when file exists."""
        mf = _write_manifest(tmp_path / "manifest.json", title="Debug Me")

        text = await debug_build_prompt(str(mf))

        assert isinstance(text, str)
        assert "Debug Me" in text
        assert "manifest" in text.lower()

    async def test_debug_build_prompt_with_missing_manifest(self) -> None:
        """debug_build returns an error message for missing file."""
        text = await debug_build_prompt("/nonexistent/manifest.json")

        assert isinstance(text, str)
        assert "failed" in text.lower() or "error" in text.lower()

    async def test_debug_build_prompt_includes_analysis_checklist(
        self,
        tmp_path: Path,
    ) -> None:
        """debug_build prompt includes diagnostic checklist items."""
        mf = _write_manifest(tmp_path / "m.json", title="Check")

        text = await debug_build_prompt(str(mf))

        assert "frame_path" in text or "audio_path" in text
        assert "duration" in text.lower()
