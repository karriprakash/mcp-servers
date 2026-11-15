"""Hardware detection shared by the local-model adapters. Imports torch lazily so the rest of the
server works on machines without it."""
from __future__ import annotations

import os


def _ram_gb() -> float | None:
    try:
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1)
    except (ValueError, OSError, AttributeError):
        return None


def detect_device() -> tuple[str, dict]:
    """Return (device, info). device is 'cuda', 'mps', 'cpu' or 'none' (torch not installed)."""
    try:
        import torch
    except ImportError:
        return "none", {"reason": "torch is not installed", "ram_gb": _ram_gb()}
    if torch.cuda.is_available():
        p = torch.cuda.get_device_properties(0)
        return "cuda", {"name": p.name, "vram_gb": round(p.total_memory / 2**30, 1), "ram_gb": _ram_gb()}
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        # Apple silicon: GPU memory is the unified system memory
        return "mps", {"name": "Apple Metal (MPS)", "vram_gb": None, "ram_gb": _ram_gb()}
    return "cpu", {"ram_gb": _ram_gb()}


def recommend(device: str, info: dict) -> str:
    """One-line advice on which adapter to use on this machine."""
    if device == "cuda":
        vram = info.get("vram_gb") or 0
        if vram >= 40:
            return "ltx (fast) or wan (higher quality, heavy): enough VRAM for both"
        if vram >= 16:
            return "ltx: fits with CPU offload. wan 14B is very slow here; prefer a 40 GB+ GPU for it"
        return "GPU is below 16 GB: use lower LTX_WIDTH/LTX_HEIGHT/LTX_MAX_FRAMES, or use the veo API"
    if device == "mps":
        return "ltx at low resolution (set LTX_WIDTH=384 LTX_HEIGHT=640 LTX_MAX_FRAMES=49); expect it to be slow. Needs 16 GB+ unified memory"
    if device == "cpu":
        return "no GPU: use the veo API for AI clips; local compositor/stitching still work"
    return "install torch (requirements-gpu.txt) to use local models, or use the veo API"
