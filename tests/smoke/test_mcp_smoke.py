"""Smoke tests for the demo-video-maker MCP server.

Fast sanity checks: imports, registrations, basic function signatures.
These tests must complete in <2 seconds with zero external dependencies.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

smoke = pytest.mark.smoke


@pytest.fixture(scope="module")
def mcp_instance() -> FastMCP:  # type: ignore[type-arg]
    """Import and return the FastMCP instance once for the whole module."""
    from demo_video_maker.mcp_server import mcp

    return mcp


# ---------------------------------------------------------------------------
# Import checks
# ---------------------------------------------------------------------------


class TestImports:
    """Verify the module and all its symbols import cleanly."""

    @smoke
    def test_mcp_server_module_imports(self) -> None:
        """The mcp_server module imports without errors."""
        from demo_video_maker import mcp_server  # noqa: F811

        assert mcp_server is not None

    @smoke
    def test_mcp_instance_exists(self, mcp_instance: FastMCP) -> None:  # type: ignore[type-arg]
        """The module exports a FastMCP instance named 'mcp'."""
        from mcp.server.fastmcp import FastMCP as _FastMCP

        assert isinstance(mcp_instance, _FastMCP)

    @smoke
    def test_main_function_exists(self) -> None:
        """The module exports a main() entry point."""
        from demo_video_maker.mcp_server import main

        assert callable(main)


# ---------------------------------------------------------------------------
# Server configuration
# ---------------------------------------------------------------------------


class TestServerConfiguration:
    """Verify server metadata and configuration."""

    @smoke
    def test_server_name(self, mcp_instance: FastMCP) -> None:  # type: ignore[type-arg]
        """Server is named 'demo-video-maker'."""
        assert mcp_instance.name == "demo-video-maker"

    @smoke
    def test_server_has_instructions(self, mcp_instance: FastMCP) -> None:  # type: ignore[type-arg]
        """Server has non-empty instructions."""
        assert mcp_instance.instructions


# ---------------------------------------------------------------------------
# Tool registrations
# ---------------------------------------------------------------------------


class TestToolRegistrations:
    """Verify all expected tools are registered."""

    @smoke
    def test_tool_count(self, mcp_instance: FastMCP) -> None:  # type: ignore[type-arg]
        """Server has exactly 10 registered tools."""
        tools = mcp_instance._tool_manager._tools
        assert len(tools) == 10

    @smoke
    def test_pipeline_tools_registered(self, mcp_instance: FastMCP) -> None:  # type: ignore[type-arg]
        """All 4 pipeline tools are registered."""
        tools = set(mcp_instance._tool_manager._tools.keys())
        expected = {
            "record_demo",
            "capture_screenshots",
            "narrate_manifest",
            "stitch_video",
        }
        assert expected <= tools

    @smoke
    def test_query_tools_registered(self, mcp_instance: FastMCP) -> None:  # type: ignore[type-arg]
        """All 4 query tools are registered."""
        tools = set(mcp_instance._tool_manager._tools.keys())
        expected = {
            "list_scenarios",
            "validate_scenario",
            "list_builds",
            "get_manifest",
        }
        assert expected <= tools

    @smoke
    def test_utility_tools_registered(self, mcp_instance: FastMCP) -> None:  # type: ignore[type-arg]
        """Both utility tools are registered."""
        tools = set(mcp_instance._tool_manager._tools.keys())
        expected = {"list_tts_voices", "get_scenario_details"}
        assert expected <= tools


# ---------------------------------------------------------------------------
# Resource registrations
# ---------------------------------------------------------------------------


class TestResourceRegistrations:
    """Verify resource templates are registered."""

    @smoke
    def test_scenario_resource_registered(self, mcp_instance: FastMCP) -> None:  # type: ignore[type-arg]
        """scenario:// resource template exists."""
        templates = mcp_instance._resource_manager._templates
        assert any("scenario" in str(uri) for uri in templates)

    @smoke
    def test_manifest_resource_registered(self, mcp_instance: FastMCP) -> None:  # type: ignore[type-arg]
        """manifest:// resource template exists."""
        templates = mcp_instance._resource_manager._templates
        assert any("manifest" in str(uri) for uri in templates)

    @smoke
    def test_build_video_resource_registered(self, mcp_instance: FastMCP) -> None:  # type: ignore[type-arg]
        """build:// video resource template exists."""
        templates = mcp_instance._resource_manager._templates
        assert any("build" in str(uri) for uri in templates)


# ---------------------------------------------------------------------------
# Prompt registrations
# ---------------------------------------------------------------------------


class TestPromptRegistrations:
    """Verify prompts are registered."""

    @smoke
    def test_create_scenario_prompt_registered(self, mcp_instance: FastMCP) -> None:  # type: ignore[type-arg]
        """create_scenario prompt exists."""
        prompts = mcp_instance._prompt_manager._prompts
        assert "create_scenario" in prompts

    @smoke
    def test_debug_build_prompt_registered(self, mcp_instance: FastMCP) -> None:  # type: ignore[type-arg]
        """debug_build prompt exists."""
        prompts = mcp_instance._prompt_manager._prompts
        assert "debug_build" in prompts


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    """Verify helper functions are importable and have correct signatures."""

    @smoke
    def test_build_tts_backend_importable(self) -> None:
        """_build_tts_backend can be imported."""
        from demo_video_maker.mcp_server import _build_tts_backend

        assert callable(_build_tts_backend)

    @smoke
    def test_resolve_work_dir_importable(self) -> None:
        """_resolve_work_dir can be imported."""
        from demo_video_maker.mcp_server import _resolve_work_dir

        assert callable(_resolve_work_dir)

    @smoke
    def test_collect_extras_importable(self) -> None:
        """_collect_extras can be imported."""
        from demo_video_maker.mcp_server import _collect_extras

        assert callable(_collect_extras)

    @smoke
    def test_build_tts_backend_returns_kokoro(self) -> None:
        """_build_tts_backend('kokoro', None) returns a KokoroTTS instance."""
        from demo_video_maker.mcp_server import _build_tts_backend
        from demo_video_maker.narrator import KokoroTTS

        backend = _build_tts_backend("kokoro", None)
        assert isinstance(backend, KokoroTTS)

    @smoke
    def test_build_tts_backend_returns_silent(self) -> None:
        """_build_tts_backend('silent', None) returns a SilentBackend."""
        from demo_video_maker.mcp_server import _build_tts_backend
        from demo_video_maker.narrator import SilentBackend

        backend = _build_tts_backend("silent", None)
        assert isinstance(backend, SilentBackend)

    @smoke
    def test_resolve_work_dir_with_explicit_path(self) -> None:
        """_resolve_work_dir with explicit work_dir returns that path."""
        from demo_video_maker.mcp_server import _resolve_work_dir

        result = _resolve_work_dir("/some/scenario.yaml", "/tmp/mywork")  # noqa: S108
        assert result == Path("/tmp/mywork")  # noqa: S108

    @smoke
    def test_resolve_work_dir_defaults_from_scenario(self) -> None:
        """_resolve_work_dir without work_dir derives from scenario name."""
        from demo_video_maker.mcp_server import _resolve_work_dir

        result = _resolve_work_dir("/path/to/my_demo.yaml", None)
        assert result == Path(".demo_build/my_demo")
