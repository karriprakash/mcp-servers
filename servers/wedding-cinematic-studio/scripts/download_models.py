#!/usr/bin/env python3
"""Download model weights into the local cache so jobs do not stall (or re-download) later.

    python scripts/download_models.py --list
    python scripts/download_models.py --preset ltx
    python scripts/download_models.py --preset ltx --preset faceqc
    python scripts/download_models.py --preset wan --dry-run

Weights are NOT stored in GitHub (they are tens of GB). They go to the Hugging Face cache
(HF_HOME, default ~/.cache/huggingface; /data/hf in the Docker image). Set HF_TOKEN if a model needs it.
Read each model's licence on its Hugging Face page before commercial use."""
from __future__ import annotations

import argparse
import os
import sys

PRESETS = {
    "ltx": {
        "repo": "Lightricks/LTX-Video",
        "allow": ["model_index.json", "scheduler/*", "text_encoder/*", "tokenizer/*", "transformer/*", "vae/*"],
        "size": "large (roughly 10-20 GB)",
        "note": "default local model; 16 GB+ GPU, or Apple silicon at low resolution",
    },
    "wan": {
        "repo": "Wan-AI/Wan2.1-I2V-14B-480P-Diffusers",
        "allow": None,
        "size": "very large (tens of GB)",
        "note": "higher quality; 40 GB+ GPU and 64 GB+ RAM recommended",
    },
    "faceqc": {
        "repo": None,
        "allow": None,
        "size": "small (a few hundred MB)",
        "note": "insightface buffalo_l face models for the identity check (needs insightface installed)",
    },
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preset", action="append", choices=sorted(PRESETS), help="repeat for several")
    ap.add_argument("--list", action="store_true", help="show presets and exit")
    ap.add_argument("--dry-run", action="store_true", help="show what would be downloaded")
    a = ap.parse_args(argv)

    if a.list or not a.preset:
        for k, v in PRESETS.items():
            print(f"{k:7} {v['repo'] or 'insightface buffalo_l':45} {v['size']:32} {v['note']}")
        return 0

    for name in a.preset:
        p = PRESETS[name]
        print(f"== {name}: {p['repo'] or 'insightface buffalo_l'} ({p['size']})")
        if a.dry_run:
            continue
        if name == "faceqc":
            try:
                from insightface.app import FaceAnalysis
            except ImportError:
                print("insightface is not installed: pip install insightface onnxruntime", file=sys.stderr)
                return 1
            FaceAnalysis(name="buffalo_l")
            continue
        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            print("huggingface_hub is not installed: pip install -r requirements-gpu.txt", file=sys.stderr)
            return 1
        path = snapshot_download(p["repo"], allow_patterns=p["allow"], token=os.environ.get("HF_TOKEN") or None)
        print(f"   cached at {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
