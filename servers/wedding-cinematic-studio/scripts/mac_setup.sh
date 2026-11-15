#!/usr/bin/env bash
# Mac with Apple silicon: run natively (Docker on macOS cannot use the Apple GPU).
# Run from servers/wedding-cinematic-studio:   bash scripts/mac_setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
  echo "This script is for Apple silicon Macs. Detected: $(uname -s) $(uname -m)" >&2
  exit 1
fi
command -v brew >/dev/null 2>&1 || { echo "Install Homebrew first: https://brew.sh" >&2; exit 1; }

brew install ffmpeg python@3.11
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt -r requirements-gpu.txt

python - <<'PY'
import torch
print("torch", torch.__version__, "| Apple GPU (MPS) available:", torch.backends.mps.is_available())
PY

cat <<MSG

Done. Every new terminal:  cd $(pwd) && source .venv/bin/activate
Recommended Mac settings (put in your shell profile):
  export PYTORCH_ENABLE_MPS_FALLBACK=1
  export LTX_WIDTH=384 LTX_HEIGHT=640 LTX_MAX_FRAMES=49
Then:
  python scripts/download_models.py --preset ltx
  python -m src.cli examples/job.example.json --estimate
MSG
