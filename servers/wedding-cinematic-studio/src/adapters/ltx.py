"""LTX-Video image-to-video (Lightricks) through diffusers. The default local model: small enough
for a 24 GB GPU (with CPU offload) and the only one here that is plausible on Apple silicon.
Review the model licence on its Hugging Face page before commercial use."""
from __future__ import annotations

from ._i2v import DiffusersI2VAdapter


class LTXAdapter(DiffusersI2VAdapter):
    name = "ltx"
    model_env = "LTX_MODEL"
    default_model = "Lightricks/LTX-Video"
    fps = 24
    frame_step = 8
    default_max_frames = 121      # about 5 s
    default_steps = 40
    min_vram_gb = 16
    default_size = {"9:16": (480, 704), "16:9": (704, 480), "1:1": (512, 512)}

    def _load(self, device: str):
        import torch
        from diffusers import LTXImageToVideoPipeline

        dtype = torch.float32 if device == "cpu" else torch.bfloat16
        pipe = LTXImageToVideoPipeline.from_pretrained(self.model_id, torch_dtype=dtype)
        try:
            pipe.vae.enable_tiling()
        except AttributeError:
            pass
        vram = hw_vram()
        self._place(pipe, device, offload_default=vram is not None and vram < 32)
        return pipe

    def _call(self, pipe, image, req, width, height, frames, steps, generator):
        return pipe(
            image=image,
            prompt=req.prompt,
            negative_prompt=req.extra.get("negative_prompt") or "worst quality, blurry, jittery, distorted, deformed faces, extra fingers, text, watermark",
            width=width, height=height, num_frames=frames, num_inference_steps=steps,
            generator=generator,
        ).frames[0]


def hw_vram():
    from . import hw
    return hw.detect_device()[1].get("vram_gb")
