"""Data models for demo scenarios."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel


class ActionType(StrEnum):
    """Supported browser actions."""

    NAVIGATE = "navigate"
    CLICK = "click"
    SCROLL = "scroll"
    TYPE = "type"
    HOVER = "hover"
    WAIT = "wait"
    SCREENSHOT = "screenshot"


class Step(BaseModel):
    """A single demo step."""

    action: ActionType
    url: str | None = None
    selector: str | None = None
    text: str | None = None
    distance: int = 0
    narration: str = ""
    highlight: str | None = None
    wait_for: str | None = None
    wait_seconds: float = 0.0
    duration_override: float | None = None


class Scenario(BaseModel):
    """A complete demo scenario."""

    title: str
    base_url: str = "http://localhost:8080"
    resolution: tuple[int, int] = (1920, 1080)
    pause_between_steps: float = 1.5
    transition: str = "fade"
    voice: str = "onyx"
    tts_model: str = "tts-1-hd"
    steps: list[Step]

    @classmethod
    def from_yaml(cls, path: Path) -> Scenario:
        """Load a scenario from a YAML file.

        Args:
            path: Path to the YAML scenario file.

        Returns:
            Parsed Scenario instance.
        """
        data = yaml.safe_load(path.read_text())
        return cls(**data)


class CursorConfig(BaseModel):
    """Configuration for animated cursor overlay."""

    enabled: bool = True
    color: str = "#ef4444"
    size: int = 48
    click_ring_color: str = "#3b82f6"
    click_ring_size: int = 80
    trail: bool = True


class OutputConfig(BaseModel):
    """Configuration for which outputs to generate."""

    video: bool = True
    gif: bool = False
    subtitles_srt: bool = True
    subtitles_vtt: bool = True
    html_tutorial: bool = False
    narration_json: bool = True


class StepResult(BaseModel):
    """Result of recording a single step."""

    index: int
    frame_path: str
    video_path: str | None = None
    narration: str = ""
    audio_path: str | None = None
    duration: float = 2.0
    click_position: tuple[int, int] | None = None


class Manifest(BaseModel):
    """Recording manifest tying frames to audio."""

    title: str
    steps: list[StepResult]

    def save(self, path: Path) -> None:
        """Write manifest to JSON file.

        Args:
            path: Output path for the manifest JSON.
        """
        path.write_text(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, path: Path) -> Manifest:
        """Load manifest from JSON file.

        Args:
            path: Path to the manifest JSON file.

        Returns:
            Parsed Manifest instance.
        """
        return cls.model_validate_json(path.read_text())
