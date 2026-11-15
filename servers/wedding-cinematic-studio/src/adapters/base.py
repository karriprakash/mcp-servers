"""Common interface for every video provider."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SceneRequest:
    scene_id: str
    prompt: str
    out_path: str
    duration: float = 6.0
    aspect_ratio: str = "9:16"
    reference_images: list[str] = field(default_factory=list)
    # provider-specific options, e.g. card_png / base_video for the local compositor
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SceneResult:
    ok: bool
    path: str | None = None
    adapter: str = ""
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class VideoAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def is_available(self) -> tuple[bool, str]:
        """Return (usable, reason). Must not make network calls."""

    @abstractmethod
    def generate(self, req: SceneRequest) -> SceneResult:
        """Render one scene to req.out_path."""
