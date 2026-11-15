from __future__ import annotations

from .base import SceneRequest, SceneResult, VideoAdapter
from .local_compositor import LocalCompositorAdapter
from .ltx import LTXAdapter
from .veo import VeoAdapter
from .wan import WanAdapter

_REGISTRY: dict[str, type[VideoAdapter]] = {
    "veo": VeoAdapter,        # Google API (paid key), no GPU needed
    "ltx": LTXAdapter,        # local model, 16 GB+ GPU or Apple MPS (slow)
    "wan": WanAdapter,        # local model, 40 GB+ GPU recommended
    "local": LocalCompositorAdapter,  # card reveal compositor, no AI
}


def get_adapter(name: str) -> VideoAdapter:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown adapter '{name}'. Available: {sorted(_REGISTRY)}")
    return _REGISTRY[name]()


def adapter_status() -> dict[str, dict]:
    out = {}
    for name, cls in _REGISTRY.items():
        ok, why = cls().is_available()
        out[name] = {"available": ok, "detail": why}
    return out


__all__ = ["SceneRequest", "SceneResult", "VideoAdapter", "get_adapter", "adapter_status"]
