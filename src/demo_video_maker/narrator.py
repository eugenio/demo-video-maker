"""TTS narration generation with pluggable backends."""

from __future__ import annotations

import logging
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from demo_video_maker.models import Manifest

logger = logging.getLogger(__name__)


class TTSBackend(ABC):
    """Abstract base for TTS backends."""

    @abstractmethod
    def synthesize(self, text: str, output_path: Path) -> None:
        """Synthesize speech from text and write to file.

        Args:
            text: Text to synthesize.
            output_path: Path to write the audio file.
        """


class OpenAITTS(TTSBackend):
    """OpenAI TTS backend (requires OPENAI_API_KEY)."""

    def __init__(self, model: str = "tts-1-hd", voice: str = "onyx") -> None:
        """Initialize OpenAI TTS with model and voice selection.

        Args:
            model: OpenAI TTS model name.
            voice: Voice identifier for speech synthesis.
        """
        self.model = model
        self.voice = voice

    def synthesize(self, text: str, output_path: Path) -> None:
        """Synthesize speech using OpenAI's TTS API.

        Args:
            text: Text to synthesize.
            output_path: Path to write the MP3 file.
        """
        from openai import OpenAI

        client = OpenAI()
        response = client.audio.speech.create(
            model=self.model,
            voice=self.voice,
            input=text,
        )
        response.stream_to_file(str(output_path))


class EdgeTTS(TTSBackend):
    """Microsoft Edge TTS backend (free, no API key needed)."""

    def __init__(self, voice: str = "en-US-GuyNeural") -> None:
        """Initialize Edge TTS with voice selection.

        Args:
            voice: Microsoft Edge TTS voice name.
        """
        self.voice = voice

    def synthesize(self, text: str, output_path: Path) -> None:
        """Synthesize speech using edge-tts CLI.

        Args:
            text: Text to synthesize.
            output_path: Path to write the MP3 file.
        """
        subprocess.run(
            ["edge-tts", "--voice", self.voice, "--text", text, "--write-media", str(output_path)],
            check=True,
            capture_output=True,
        )


class SilentBackend(TTSBackend):
    """Generate silence — used when TTS is skipped."""

    def synthesize(self, text: str, output_path: Path) -> None:
        """Generate a silent audio file matching approximate speech duration.

        Args:
            text: Text (used to estimate duration).
            output_path: Path to write the silent audio file.
        """
        # ~150 words per minute, estimate duration from word count
        words = len(text.split())
        duration = max(2.0, words / 2.5)
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                "-t", str(duration),
                "-q:a", "9",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )


def get_audio_duration(audio_path: Path) -> float:
    """Get duration of an audio file in seconds using ffprobe.

    Args:
        audio_path: Path to the audio file.

    Returns:
        Duration in seconds.
    """
    import json

    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", str(audio_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


def generate_narration(
    manifest: Manifest,
    output_dir: Path,
    *,
    backend: TTSBackend | None = None,
) -> Manifest:
    """Generate narration audio for each step in the manifest.

    Args:
        manifest: Recording manifest with step narrations.
        output_dir: Directory to write audio files into.
        backend: TTS backend to use. Defaults to OpenAITTS.

    Returns:
        Updated manifest with audio paths and adjusted durations.
    """
    if backend is None:
        backend = OpenAITTS()

    output_dir.mkdir(parents=True, exist_ok=True)

    for step in manifest.steps:
        if not step.narration:
            continue

        audio_path = output_dir / f"step_{step.index:03d}.mp3"
        logger.info("Generating narration for step %d...", step.index)
        backend.synthesize(step.narration, audio_path)

        step.audio_path = str(audio_path)
        duration = get_audio_duration(audio_path)
        step.duration = max(step.duration, duration + 0.5)

    return manifest
