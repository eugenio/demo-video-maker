"""Tests for demo_video_maker.models."""

from __future__ import annotations

from pathlib import Path

from demo_video_maker.models import ActionType, Manifest, Scenario, Step, StepResult


class TestStep:
    """Tests for the Step model."""

    def test_minimal_step(self) -> None:
        step = Step(action=ActionType.NAVIGATE, url="/test")
        assert step.action == ActionType.NAVIGATE
        assert step.url == "/test"
        assert step.narration == ""
        assert step.highlight is None

    def test_full_step(self) -> None:
        step = Step(
            action=ActionType.CLICK,
            selector=".btn",
            narration="Click the button.",
            highlight=".btn",
            wait_for=".result",
        )
        assert step.selector == ".btn"
        assert step.narration == "Click the button."


class TestScenario:
    """Tests for the Scenario model."""

    def test_defaults(self) -> None:
        scenario = Scenario(title="Test", steps=[])
        assert scenario.resolution == (1920, 1080)
        assert scenario.pause_between_steps == 1.5
        assert scenario.voice == "onyx"

    def test_from_yaml(self, tmp_path: Path) -> None:
        yaml_content = (
            "title: Test Scenario\n"
            "base_url: http://localhost:3000\n"
            "steps:\n"
            "  - action: navigate\n"
            "    url: /\n"
            "    narration: Hello\n"
        )
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        scenario = Scenario.from_yaml(yaml_file)
        assert scenario.title == "Test Scenario"
        assert scenario.base_url == "http://localhost:3000"
        assert len(scenario.steps) == 1
        assert scenario.steps[0].action == ActionType.NAVIGATE


class TestManifest:
    """Tests for the Manifest model."""

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        manifest = Manifest(
            title="Test",
            steps=[
                StepResult(index=0, frame_path="frame.png", narration="Hi", duration=2.0),
            ],
        )
        manifest_path = tmp_path / "manifest.json"
        manifest.save(manifest_path)

        loaded = Manifest.load(manifest_path)
        assert loaded.title == "Test"
        assert len(loaded.steps) == 1
        assert loaded.steps[0].narration == "Hi"

    def test_empty_manifest(self, tmp_path: Path) -> None:
        manifest = Manifest(title="Empty", steps=[])
        manifest_path = tmp_path / "manifest.json"
        manifest.save(manifest_path)

        loaded = Manifest.load(manifest_path)
        assert loaded.steps == []
