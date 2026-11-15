"""Wan 2.1 image-to-video (14B, 480p) through diffusers. Higher quality than LTX but very heavy:
use a 40 GB+ GPU (for example an A100) and 64 GB+ system RAM. Apache-2.0 at the time of writing;
check the model page for current terms."""
from __future__ import annotations

from ._i2v import DiffusersI2VAdapter


class WanAdapter(DiffusersI2VAdapter):
    name = "wan"
    model_env = "WAN_MODEL"
    default_model = "Wan-AI/Wan2.1-I2V-14B-480P-Diffusers"
    fps = 16
    frame_step = 4                # frame count must be 4k + 1
    default_max_frames = 81       # about 5 s at 16 fps
    default_steps = 30
    min_vram_gb = 24
    default_size = {"9:16": (480, 832), "16:9": (832, 480), "1:1": (624, 624)}

    def _load(self, device: str):
        import torch
        from diffusers import AutoencoderKLWan, WanImageToVideoPipeline
        from transformers import CLIPVisionModel

        image_encoder = CLIPVisionModel.from_pretrained(self.model_id, subfolder="image_encoder", torch_dtype=torch.float32)
        vae = AutoencoderKLWan.from_pretrained(self.model_id, subfolder="vae", torch_dtype=torch.float32)
        pipe = WanImageToVideoPipeline.from_pretrained(
            self.model_id, vae=vae, image_encoder=image_encoder, torch_dtype=torch.bfloat16)
        self._place(pipe, device, offload_default=True)   # 14B never fits without offload below ~80 GB
        return pipe

    def _call(self, pipe, image, req, width, height, frames, steps, generator):
        return pipe(
            image=image,
            prompt=req.prompt,
            negative_prompt=req.extra.get("negative_prompt") or "blurry, distorted faces, extra fingers, static, text, watermark",
            height=height, width=width, num_frames=frames, guidance_scale=5.0,
            num_inference_steps=steps, generator=generator,
        ).frames[0]
