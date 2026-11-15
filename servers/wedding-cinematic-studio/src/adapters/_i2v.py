"""Shared base for local image-to-video models run through Hugging Face diffusers.

The couple's photo is the first frame, so identity comes from the photo itself (no face swapping).
Subclasses supply the model loading and the pipeline call. NOT yet run on real GPU hardware:
treat the first run on a new machine as a test (use `--only-scene` in the CLI)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from . import hw
from .base import SceneRequest, SceneResult, VideoAdapter


class DiffusersI2VAdapter(VideoAdapter):
    default_model = ""
    model_env = ""
    fps = 24
    frame_step = 8            # frame count must be frame_step * k + 1
    default_max_frames = 121
    default_steps = 40
    min_vram_gb = 16
    default_size = {"9:16": (480, 704), "16:9": (704, 480), "1:1": (512, 512)}  # (width, height)
    _pipes: dict = {}

    # ---- pure helpers (no torch needed, unit-tested) ----------------------------------------
    @property
    def model_id(self) -> str:
        return os.environ.get(self.model_env, self.default_model)

    def _env(self, key: str, default):
        return type(default)(os.environ.get(f"{self.name.upper()}_{key}", default))

    def size_for(self, aspect: str) -> tuple[int, int]:
        w, h = self._env("WIDTH", 0), self._env("HEIGHT", 0)
        if w and h:
            return w, h
        return self.default_size.get(aspect, self.default_size["9:16"])

    def frames_for(self, duration: float) -> int:
        cap = self._env("MAX_FRAMES", self.default_max_frames)
        want = max(1, round(duration * self.fps))
        k = max(1, round((want - 1) / self.frame_step))
        kmax = max(1, (cap - 1) // self.frame_step)
        return self.frame_step * min(k, kmax) + 1

    # ---- availability -----------------------------------------------------------------------
    def is_available(self) -> tuple[bool, str]:
        device, info = hw.detect_device()
        if device == "none":
            return False, "torch not installed (pip install -r requirements-gpu.txt)"
        try:
            import diffusers  # noqa: F401
        except ImportError:
            return False, "diffusers not installed (pip install -r requirements-gpu.txt)"
        if device == "cpu" and not os.environ.get("WEDDING_ALLOW_CPU"):
            return False, "no GPU found (CUDA or Apple MPS); set WEDDING_ALLOW_CPU=1 to force a very slow CPU run"
        if device == "cuda" and (info.get("vram_gb") or 0) < self.min_vram_gb:
            return False, f"needs about {self.min_vram_gb} GB VRAM, found {info.get('vram_gb')} GB"
        return True, f"{device} {info}"

    # ---- to be provided by subclasses -------------------------------------------------------
    def _load(self, device: str):
        raise NotImplementedError

    def _call(self, pipe, image, req: SceneRequest, width: int, height: int, frames: int, steps: int, generator):
        raise NotImplementedError

    # ---- generation -------------------------------------------------------------------------
    @staticmethod
    def _place(pipe, device: str, offload_default: bool) -> None:
        """Put the pipeline on the device, using CPU offload when VRAM is tight."""
        offload = os.environ.get("WEDDING_OFFLOAD", "auto")
        if device == "cuda" and (offload == "1" or (offload == "auto" and offload_default)):
            pipe.enable_model_cpu_offload()
        else:
            pipe.to(device)

    def _get_pipe(self, device: str):
        key = (self.name, self.model_id, device)
        if key not in self._pipes:
            self._pipes[key] = self._load(device)
        return self._pipes[key]

    def generate(self, req: SceneRequest) -> SceneResult:
        start = req.extra.get("start_image") or (req.reference_images[0] if req.reference_images else None)
        if not start:
            return SceneResult(False, adapter=self.name, error="this model needs a start photo: pass reference_photos")
        ok, why = self.is_available()
        if not ok:
            return SceneResult(False, adapter=self.name, error=why)
        try:
            import torch
            from diffusers.utils import export_to_video
            from PIL import Image, ImageOps

            device, _ = hw.detect_device()
            width, height = self.size_for(req.aspect_ratio)
            frames = self.frames_for(req.duration)
            steps = self._env("STEPS", self.default_steps)
            image = ImageOps.fit(Image.open(start).convert("RGB"), (width, height), Image.LANCZOS, centering=(0.5, 0.4))
            gen = torch.Generator("cpu").manual_seed(int(os.environ.get("WEDDING_SEED", "42")))

            pipe = self._get_pipe(device)
            out_frames = self._call(pipe, image, req, width, height, frames, steps, gen)

            out = Path(req.out_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            raw = out.with_name(out.stem + ".raw.mp4")
            part = out.with_name(out.stem + ".part.mp4")
            export_to_video(out_frames, str(raw), fps=self.fps)
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-c:v", "libx264", "-crf", "18",
                 "-preset", "veryfast", "-pix_fmt", "yuv420p", "-an", str(part)], check=True)
            part.replace(out)
            raw.unlink(missing_ok=True)
            seconds = round(frames / self.fps, 2)
            meta = {"model": self.model_id, "device": device, "size": f"{width}x{height}", "frames": frames,
                    "steps": steps, "seconds": seconds}
            if seconds + 0.5 < req.duration:
                meta["note"] = f"clip is {seconds}s, shorter than the {req.duration}s requested (raise {self.name.upper()}_MAX_FRAMES if VRAM allows)"
            return SceneResult(True, str(out), self.name, meta=meta)
        except Exception as e:  # report, never crash the job
            msg = f"{type(e).__name__}: {e}"
            if "out of memory" in msg.lower():
                msg += f" | lower {self.name.upper()}_WIDTH/HEIGHT/MAX_FRAMES or set WEDDING_OFFLOAD=1"
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            return SceneResult(False, adapter=self.name, error=msg)
