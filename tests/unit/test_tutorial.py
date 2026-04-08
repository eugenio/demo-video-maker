"""Tests for demo_video_maker.tutorial."""

from __future__ import annotations

from pathlib import Path

from demo_video_maker.models import Manifest, StepResult
from demo_video_maker.tutorial import generate_html_tutorial


class TestGenerateHtmlTutorial:
    """Tests for HTML tutorial generation."""

    def test_generates_valid_html(self, tmp_path: Path) -> None:
        manifest = Manifest(
            title="Test Demo",
            steps=[
                StepResult(
                    index=0, frame_path="frames/step_000.png",
                    narration="Hello", duration=2.0,
                ),
                StepResult(
                    index=1, frame_path="frames/step_001.png",
                    narration="World", duration=3.0,
                ),
            ],
        )
        output = tmp_path / "tutorial.html"
        result = generate_html_tutorial(manifest, output)

        assert result == output
        content = output.read_text()
        assert "<!DOCTYPE html>" in content
        assert "<title>Test Demo</title>" in content

    def test_contains_step_content(self, tmp_path: Path) -> None:
        manifest = Manifest(
            title="Test",
            steps=[
                StepResult(
                    index=0, frame_path="frames/step_000.png",
                    narration="Click the button", duration=2.0,
                ),
            ],
        )
        output = tmp_path / "tutorial.html"
        generate_html_tutorial(manifest, output)
        content = output.read_text()

        assert "Click the button" in content
        assert 'src="frames/step_000.png"' in content
        assert "1 steps" in content

    def test_escapes_html_in_narration(self, tmp_path: Path) -> None:
        manifest = Manifest(
            title="XSS Test",
            steps=[
                StepResult(
                    index=0,
                    frame_path="f.png",
                    narration='Use <script>alert("xss")</script> tag',
                    duration=2.0,
                ),
            ],
        )
        output = tmp_path / "tutorial.html"
        generate_html_tutorial(manifest, output)
        content = output.read_text()

        assert "<script>alert" not in content
        assert "&lt;script&gt;" in content

    def test_empty_manifest(self, tmp_path: Path) -> None:
        manifest = Manifest(title="Empty", steps=[])
        output = tmp_path / "tutorial.html"
        generate_html_tutorial(manifest, output)
        content = output.read_text()

        assert "0 steps" in content

    def test_has_lightbox(self, tmp_path: Path) -> None:
        manifest = Manifest(
            title="Test",
            steps=[
                StepResult(index=0, frame_path="f.png", narration="Test", duration=2.0),
            ],
        )
        output = tmp_path / "tutorial.html"
        generate_html_tutorial(manifest, output)
        content = output.read_text()

        assert "lightbox" in content
        assert "lightbox-img" in content
