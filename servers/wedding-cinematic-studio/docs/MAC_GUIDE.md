# Run the wedding studio on your Apple laptop

**Status: written but not yet run on a Mac.** I am assuming "Apple Neo" means an Apple-silicon (M-series) Mac; check with `uname -m` (it should print `arm64`).

## The important fact about Docker on a Mac
Docker Desktop on macOS runs Linux in a virtual machine and **cannot use the Apple GPU**. So:
- **GPU run (recommended): native Python**, using Apple's Metal GPU through PyTorch (MPS).
- **Docker run: the light image only** (card reveal, stitching, QC, and the Veo API). No local AI models inside Docker on a Mac.

## Option A: native, with the Apple GPU
Needs 16 GB or more of memory (unified memory is shared with the GPU). Free about 40 GB of disk.
```bash
git clone https://github.com/karriprakash/mcp-servers.git
cd mcp-servers/servers/wedding-cinematic-studio
bash scripts/mac_setup.sh
```
It installs ffmpeg (Homebrew), makes a virtual environment and installs the packages. Then, in the same terminal:
```bash
source .venv/bin/activate
export PYTORCH_ENABLE_MPS_FALLBACK=1 LTX_WIDTH=384 LTX_HEIGHT=640 LTX_MAX_FRAMES=49
python scripts/download_models.py --preset ltx
python -m src.cli examples/job.example.json --estimate      # shows it found the Apple GPU
```
Copy `examples/job.example.json` to `job.json`, put your photos and card in `inputs/`, change the paths in `job.json` to `inputs/...`, and try one clip first:
```bash
python -m src.cli job.json --only-scene s1
python -m src.cli job.json            # the whole film, resumes if interrupted
```
Output: `~/.wedding_studio/outputs/<project>.mp4`.

Expect it to be slow (minutes per clip, possibly much more) and clips to be short and low resolution. Some operations may not be supported on MPS; the fallback setting sends those to the CPU. If a clip fails or looks bad, use the Google Cloud GPU VM (`docs/GCP_GPU_GUIDE.md`) for the AI clips and finish on your Mac.

## Option B: Docker (light image, no local AI models)
Install Docker Desktop, then:
```bash
cd mcp-servers/servers/wedding-cinematic-studio
mkdir -p data inputs
docker compose --profile cpu build
docker compose --profile cpu run --rm studio-cpu python -m src.cli /inputs/job.json --estimate
```
This is useful with a Veo API key (`export GEMINI_API_KEY=...`, `"adapters": ["veo"]`), or to composite your real card over clips made elsewhere (for example in Gemini or ChatGPT) and stitch them with music.

## Use it from Claude Desktop (native option)
Add to Claude Desktop's MCP config:
```json
{"mcpServers": {"wedding-studio": {
  "command": "/path/to/mcp-servers/servers/wedding-cinematic-studio/.venv/bin/python",
  "args": ["-m", "src.server"],
  "cwd": "/path/to/mcp-servers/servers/wedding-cinematic-studio",
  "env": {"PYTORCH_ENABLE_MPS_FALLBACK": "1", "LTX_WIDTH": "384", "LTX_HEIGHT": "640", "LTX_MAX_FRAMES": "49"}
}}}
```
Restart Claude Desktop. The `hardware_check` and `adapter_status` tools show what it found.

## Troubleshooting
| Symptom | Fix |
|---|---|
| `MPS available: False` | you are not on Apple silicon, or macOS is old: update macOS and reinstall torch |
| `not implemented for 'MPS'` | `export PYTORCH_ENABLE_MPS_FALLBACK=1` |
| Out of memory / Mac freezes | lower `LTX_WIDTH`, `LTX_HEIGHT`, `LTX_MAX_FRAMES`; close other apps |
| `ffmpeg not found` | `brew install ffmpeg` |
