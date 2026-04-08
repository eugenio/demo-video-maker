"""Tests for demo_video_maker.narrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from demo_video_maker.models import Manifest, StepResult
from demo_video_maker.narrator import EdgeTTS, SilentBackend, generate_narration


class TestSilentBackend:
    """Tests for the SilentBackend TTS backend."""

    @patch("demo_video_maker.narrator.subprocess.run")
    def test_synthesize_calls_ffmpeg(self, mock_run: MagicMock, tmp_path: Path) -> None:
        backend = SilentBackend()
        output = tmp_path / "silence.mp3"
        backend.synthesize("Hello world test", output)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ffmpeg"
        assert str(output) in cmd


class TestEdgeTTS:
    """Tests for the EdgeTTS backend."""

    @patch("demo_video_maker.narrator.subprocess.run")
    def test_synthesize_calls_edge_tts(self, mock_run: MagicMock, tmp_path: Path) -> None:
        backend = EdgeTTS(voice="en-US-AriaNeural")
        output = tmp_path / "speech.mp3"
        backend.synthesize("Test narration", output)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "edge-tts"
        assert "--voice" in cmd
        assert "en-US-AriaNeural" in cmd


class TestGenerateNarration:
    """Tests for the generate_narration function."""

    @patch("demo_video_maker.narrator.get_audio_duration", return_value=3.0)
    def test_generates_audio_for_steps_with_narration(
        self, mock_duration: MagicMock, tmp_path: Path
    ) -> None:
        manifest = Manifest(
            title="Test",
            steps=[
                StepResult(index=0, frame_path="f0.png", narration="Hello", duration=2.0),
                StepResult(index=1, frame_path="f1.png", narration="", duration=2.0),
            ],
        )
        mock_backend = MagicMock()
        result = generate_narration(manifest, tmp_path / "audio", backend=mock_backend)

        # Only step 0 has narration
        mock_backend.synthesize.assert_called_once()
        assert result.steps[0].audio_path is not None
        assert result.steps[1].audio_path is None
        # Duration should be adjusted to audio length + buffer
        assert result.steps[0].duration == 3.5
