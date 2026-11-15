"""Google Veo adapter (image-guided video generation).

NOTE: this adapter was written against the google-genai SDK but has not been run against the
live API (no key was available when it was written). Model names and the reference-image
options change between Veo releases, so set VEO_MODEL to the model your key can use.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from .. import config
from .base import SceneRequest, SceneResult, VideoAdapter

POLL_SECONDS = 10
TIMEOUT_SECONDS = 900


def _mime(path: Path) -> str:
    return "image/png" if path.suffix.lower() == ".png" else "image/jpeg"


class VeoAdapter(VideoAdapter):
    name = "veo"

    def is_available(self) -> tuple[bool, str]:
        if not os.environ.get("GEMINI_API_KEY"):
            return False, "GEMINI_API_KEY is not set"
        try:
            import google.genai  # noqa: F401
        except Exception:
            return False, "google-genai is not installed (pip install google-genai)"
        return True, "ok"

    def generate(self, req: SceneRequest) -> SceneResult:
        ok, why = self.is_available()
        if not ok:
            return SceneResult(False, adapter=self.name, error=why)

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        refs = [Path(p) for p in req.reference_images if Path(p).exists()]

        cfg_kwargs = dict(aspect_ratio=req.aspect_ratio, number_of_videos=1)
        if req.duration:
            cfg_kwargs["duration_seconds"] = int(round(req.duration))
        negative = req.extra.get("negative_prompt")
        if negative:
            cfg_kwargs["negative_prompt"] = negative

        # Newer Veo models accept several reference images (identity lock for two people).
        # If this SDK/model does not know the option we fall back to one start frame.
        used_refs = "none"
        image_arg = None
        ref_cls = getattr(types, "VideoGenerationReferenceImage", None)
        if refs and ref_cls is not None and req.extra.get("use_reference_images", True):
            try:
                cfg_kwargs["reference_images"] = [
                    ref_cls(
                        image=types.Image(image_bytes=p.read_bytes(), mime_type=_mime(p)),
                        reference_type="ASSET",
                    )
                    for p in refs[:3]
                ]
                used_refs = f"reference_images x{len(refs[:3])}"
            except Exception as e:  # pragma: no cover - SDK dependent
                cfg_kwargs.pop("reference_images", None)
                used_refs = f"reference_images failed: {e}"
        if "reference_images" not in cfg_kwargs and refs:
            image_arg = types.Image(image_bytes=refs[0].read_bytes(), mime_type=_mime(refs[0]))
            used_refs = "start frame (first reference only)"

        try:
            op = client.models.generate_videos(
                model=req.extra.get("model", config.VEO_MODEL),
                prompt=req.prompt,
                image=image_arg,
                config=types.GenerateVideosConfig(**cfg_kwargs),
            )
            t0 = time.time()
            while not op.done:
                if time.time() - t0 > TIMEOUT_SECONDS:
                    return SceneResult(False, adapter=self.name, error="Veo timed out")
                time.sleep(POLL_SECONDS)
                op = client.operations.get(op)
            videos = getattr(op.response, "generated_videos", None) if op.response else None
            if not videos:
                return SceneResult(False, adapter=self.name, error="Veo returned no video (possibly blocked by a safety filter)")
            video = videos[0].video
            client.files.download(file=video)
            out = Path(req.out_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = out.with_name(out.stem + ".part.mp4")
            video.save(str(tmp))
            os.replace(tmp, out)
            return SceneResult(True, str(out), self.name, meta={"references": used_refs})
        except Exception as e:  # network / quota / SDK errors
            return SceneResult(False, adapter=self.name, error=f"{type(e).__name__}: {e}")
