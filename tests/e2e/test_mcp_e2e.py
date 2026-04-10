"""End-to-end tests for the demo-video-maker MCP server.

Tests the full MCP protocol flow: client <-> server over stdio transport.
Each test starts a **fresh** server connection inline (no shared fixture)
to avoid anyio task-group teardown issues with pytest-asyncio.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path("/home/uge/demo-video-maker")

SERVER_PARAMS = StdioServerParameters(
    command="pixi",
    args=["run", "python", "-m", "demo_video_maker.mcp_server"],
    cwd=str(PROJECT_ROOT),
)

EXPECTED_TOOLS: set[str] = {
    "record_demo",
    "capture_screenshots",
    "narrate_manifest",
    "stitch_video",
    "list_scenarios",
    "validate_scenario",
    "list_builds",
    "get_manifest",
    "list_tts_voices",
    "get_scenario_details",
}

EXPECTED_RESOURCE_PREFIXES: set[str] = {"scenario://", "manifest://", "build://"}

EXPECTED_PROMPTS: set[str] = {"create_scenario", "debug_build"}

pytestmark = [pytest.mark.e2e]


# ---------------------------------------------------------------------------
# Protocol tests
# ---------------------------------------------------------------------------


class TestServerProtocol:
    """Verify basic MCP protocol handshake and discovery."""

    async def test_server_initializes_successfully(self) -> None:
        """Connect, initialize, verify server name."""
        async with stdio_client(SERVER_PARAMS) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                result = await session.initialize()
                assert result.serverInfo.name == "demo-video-maker"

    async def test_server_lists_all_tools(self) -> None:
        """All 10 registered tools must be present."""
        async with stdio_client(SERVER_PARAMS) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                await session.initialize()
                result = await session.list_tools()
                tool_names = {t.name for t in result.tools}
                missing = EXPECTED_TOOLS - tool_names
                assert not missing, f"Missing tools: {missing}"

    async def test_server_lists_resource_templates(self) -> None:
        """Resource templates for scenario://, manifest://, build:// must exist."""
        async with stdio_client(SERVER_PARAMS) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                await session.initialize()
                result = await session.list_resource_templates()
                uri_templates = {rt.uriTemplate for rt in result.resourceTemplates}
                for prefix in EXPECTED_RESOURCE_PREFIXES:
                    assert any(prefix in uri for uri in uri_templates), (
                        f"No template matching '{prefix}' in {uri_templates}"
                    )

    async def test_server_lists_prompts(self) -> None:
        """Both prompts must be registered."""
        async with stdio_client(SERVER_PARAMS) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                await session.initialize()
                result = await session.list_prompts()
                prompt_names = {p.name for p in result.prompts}
                missing = EXPECTED_PROMPTS - prompt_names
                assert not missing, f"Missing prompts: {missing}"


# ---------------------------------------------------------------------------
# Tool call tests — read-only tools
# ---------------------------------------------------------------------------


class TestToolCalls:
    """Call read-only tools via the MCP protocol and verify responses."""

    async def test_call_list_tts_voices_returns_backends(self) -> None:
        """list_tts_voices with no filter must return all four backends."""
        async with stdio_client(SERVER_PARAMS) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                await session.initialize()
                result = await session.call_tool("list_tts_voices", arguments={})
                assert not result.isError, f"Error: {result.content}"

                text = result.content[0].text  # type: ignore[union-attr]
                payload = json.loads(text)
                assert "backends" in payload
                backend_names = set(payload["backends"].keys())
                expected = {"kokoro", "openai", "edge", "silent"}
                assert expected.issubset(backend_names), (
                    f"Missing: {expected - backend_names}"
                )

    async def test_call_list_tts_voices_filters_by_backend(self) -> None:
        """list_tts_voices with backend='kokoro' returns only kokoro."""
        async with stdio_client(SERVER_PARAMS) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                await session.initialize()
                result = await session.call_tool(
                    "list_tts_voices", arguments={"backend": "kokoro"},
                )
                assert not result.isError
                text = result.content[0].text  # type: ignore[union-attr]
                payload = json.loads(text)
                assert "backends" in payload
                assert set(payload["backends"].keys()) == {"kokoro"}

    async def test_call_validate_scenario_with_valid_file(
        self, tmp_path: Path,
    ) -> None:
        """validate_scenario returns valid=true for a well-formed YAML."""
        scenario_data = {
            "title": "E2E Test",
            "base_url": "http://localhost:8080",
            "steps": [{"action": "navigate", "url": "/", "narration": "Hello."}],
        }
        scenario_file = tmp_path / "valid_scenario.yaml"
        scenario_file.write_text(yaml.dump(scenario_data))

        async with stdio_client(SERVER_PARAMS) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                await session.initialize()
                result = await session.call_tool(
                    "validate_scenario",
                    arguments={"scenario_file": str(scenario_file)},
                )
                assert not result.isError, f"Error: {result.content}"
                text = result.content[0].text  # type: ignore[union-attr]
                payload = json.loads(text)
                assert payload["valid"] is True

    async def test_call_validate_scenario_with_invalid_file(self) -> None:
        """validate_scenario with nonexistent path returns error or valid=false."""
        async with stdio_client(SERVER_PARAMS) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                await session.initialize()
                result = await session.call_tool(
                    "validate_scenario",
                    arguments={"scenario_file": "/nonexistent/scenario.yaml"},
                )
                if result.isError:
                    return
                text = result.content[0].text  # type: ignore[union-attr]
                payload = json.loads(text)
                assert payload.get("valid") is False or "error" in payload

    async def test_call_list_scenarios_with_existing_dir(self) -> None:
        """list_scenarios with scenarios/examples/ finds YAML files."""
        scenarios_dir = str(PROJECT_ROOT / "scenarios" / "examples")
        async with stdio_client(SERVER_PARAMS) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                await session.initialize()
                result = await session.call_tool(
                    "list_scenarios",
                    arguments={"scenarios_dir": scenarios_dir},
                )
                assert not result.isError, f"Error: {result.content}"
                text = result.content[0].text  # type: ignore[union-attr]
                payload = json.loads(text)
                assert "scenarios" in payload
                assert len(payload["scenarios"]) > 0

    async def test_call_get_manifest_with_existing_manifest(self) -> None:
        """get_manifest with a real manifest.json returns parsed data."""
        # Find any existing manifest
        demo_build = PROJECT_ROOT / ".demo_build"
        if not demo_build.exists():
            pytest.skip("No .demo_build/ directory available")

        manifest_files = list(demo_build.rglob("manifest.json"))
        if not manifest_files:
            pytest.skip("No manifest.json found in .demo_build/")

        manifest_path = str(manifest_files[0])
        async with stdio_client(SERVER_PARAMS) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                await session.initialize()
                result = await session.call_tool(
                    "get_manifest",
                    arguments={"manifest_file": manifest_path},
                )
                assert not result.isError, f"Error: {result.content}"
                text = result.content[0].text  # type: ignore[union-attr]
                payload = json.loads(text)
                assert "title" in payload
                assert "steps" in payload

    async def test_call_list_builds_with_existing_builds(self) -> None:
        """list_builds finds existing build directories."""
        builds_dir = str(PROJECT_ROOT / ".demo_build")
        if not Path(builds_dir).exists():
            pytest.skip("No .demo_build/ directory available")

        async with stdio_client(SERVER_PARAMS) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                await session.initialize()
                result = await session.call_tool(
                    "list_builds",
                    arguments={"work_dir": builds_dir},
                )
                assert not result.isError, f"Error: {result.content}"
                text = result.content[0].text  # type: ignore[union-attr]
                payload = json.loads(text)
                assert "builds" in payload
                assert len(payload["builds"]) > 0


# ---------------------------------------------------------------------------
# Prompt tests
# ---------------------------------------------------------------------------


class TestPrompts:
    """Verify prompt retrieval via the MCP protocol."""

    async def test_get_create_scenario_prompt(self) -> None:
        """create_scenario prompt returns content with app_name."""
        async with stdio_client(SERVER_PARAMS) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                await session.initialize()
                result = await session.get_prompt(
                    "create_scenario",
                    arguments={
                        "app_name": "My Test App",
                        "base_url": "http://localhost:3000",
                    },
                )
                assert result.messages
                content_text = result.messages[0].content.text  # type: ignore[union-attr]
                assert "My Test App" in content_text

    async def test_get_debug_build_prompt(self) -> None:
        """debug_build prompt returns non-empty content."""
        # Find an existing manifest for realistic prompt
        demo_build = PROJECT_ROOT / ".demo_build"
        manifest_files = list(demo_build.rglob("manifest.json")) if demo_build.exists() else []
        manifest_file = str(manifest_files[0]) if manifest_files else "/nonexistent/manifest.json"

        async with stdio_client(SERVER_PARAMS) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                await session.initialize()
                result = await session.get_prompt(
                    "debug_build",
                    arguments={"manifest_file": manifest_file},
                )
                assert result.messages
                content_text = result.messages[0].content.text  # type: ignore[union-attr]
                assert len(content_text) > 0
