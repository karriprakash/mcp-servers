# Run the wedding studio on a Google Cloud GPU VM

**Status: written but not yet run on a real GPU.** Treat the first run as a test and use `--only-scene s1` before a full job. Nothing here costs money until you create the VM, and it stops costing compute when you stop it.

## What you need
- A Google Cloud project with billing and your credits. Check your credit's terms: some promotional credits exclude certain products, and a free-trial account may have to be upgraded to a paid account (credits stay) before it can use GPUs.
- The `gcloud` CLI on your computer, logged in: `gcloud auth login`.
- GPU quota. New projects often have 0. In the console open **IAM & Admin > Quotas**, filter for `NVIDIA L4 GPUs` (and `Preemptible NVIDIA L4 GPUs` if you use spot) in your region, and request 1. Approval can take minutes to days.

## Step 1: Create the VM (on your computer)
```bash
git clone https://github.com/karriprakash/mcp-servers.git
cd mcp-servers/servers/wedding-cinematic-studio
GCP_PROJECT=your-project-id ./scripts/gcp_create_vm.sh
```
Defaults: `g2-standard-8` (1x L4 24 GB, 32 GB RAM), spot pricing, 200 GB disk, zone `us-central1-a`. Change with `GCP_ZONE`, `MACHINE_TYPE`, `DISK_GB`, `SPOT=0`. If the zone has no L4 capacity, try another zone. Spot VMs can be stopped by Google at any time; the job resumes from its checkpoints when you start it again.

## Step 2: Set up the VM
```bash
gcloud compute ssh wedding-gpu --zone us-central1-a
git clone https://github.com/karriprakash/mcp-servers.git
cd mcp-servers/servers/wedding-cinematic-studio
bash scripts/gcp_vm_setup.sh      # installs the GPU driver, then asks you to reboot
sudo reboot
# reconnect with gcloud compute ssh, cd back into the folder, then:
bash scripts/gcp_vm_setup.sh      # installs Docker + NVIDIA toolkit, builds the image, tests GPU access
```

## Step 3: Upload your inputs
From your computer:
```bash
gcloud compute scp --recurse ./my_inputs wedding-gpu:~/mcp-servers/servers/wedding-cinematic-studio/inputs --zone us-central1-a
```
Put the real Telugu card (`card.png`), the couple photos and one clear portrait each of the groom and bride in `inputs/`. Copy `examples/job.example.json` to `inputs/job.json` and edit the names, date and file names. Paths inside the job file start with `/inputs/`.

## Step 4: Download the model, test one clip
```bash
sudo docker compose --profile gpu run --rm studio-gpu python scripts/download_models.py --preset ltx
sudo docker compose --profile gpu run --rm studio-gpu python -m src.cli /inputs/job.json --estimate
sudo docker compose --profile gpu run --rm studio-gpu python -m src.cli /inputs/job.json --only-scene s1
```
Weights are cached under `data/hf` on the VM disk and are not downloaded again. The face check is optional: build with `FACE_QC=1` (`sudo FACE_QC=1 docker compose --profile gpu build`) and run `download_models.py --preset faceqc`.

## Step 5: Run the whole film and fetch it
```bash
sudo docker compose --profile gpu run --rm studio-gpu python -m src.cli /inputs/job.json
```
Output: `data/studio/outputs/<project>.mp4`. From your computer:
```bash
gcloud compute scp wedding-gpu:~/mcp-servers/servers/wedding-cinematic-studio/data/studio/outputs/*.mp4 . --zone us-central1-a
```
If it stops midway, run the same command again: finished scenes are skipped.

## Step 6: Stop the VM (saves your credits)
```bash
gcloud compute instances stop wedding-gpu --zone us-central1-a
```
Compute billing stops; the disk keeps costing a little. Delete the VM and disk when you are fully done. Set a budget alert in **Billing > Budgets & alerts** so a forgotten VM cannot drain the credits.

## Use it from Claude (optional)
The server can also run as an MCP endpoint on the VM:
```bash
sudo docker compose --profile gpu up -d        # listens on 127.0.0.1:8000 on the VM only
```
There is no login, so never open port 8000 in the firewall. Reach it through an SSH tunnel from your computer:
```bash
gcloud compute ssh wedding-gpu --zone us-central1-a -- -N -L 8000:localhost:8000
```
Then point an MCP client at `http://localhost:8000/mcp`. Claude Desktop only speaks stdio, so use a bridge such as `npx mcp-remote http://localhost:8000/mcp` (not tested here). For most jobs the CLI above is simpler.

## Choosing the model
| GPU | Model | Notes |
|---|---|---|
| L4 24 GB (`g2-standard-8`) | `ltx` (default) | uses CPU offload; about 5 s per clip |
| A100 40 GB (`a2-highgpu-1g`) | `ltx` or `wan` | `wan` is higher quality, much heavier; use `"adapters": ["wan"]` and `download_models.py --preset wan` |

Clips are about 5 s each, shorter than the 6-8 s scenes in the template; the report says so. Raise `LTX_MAX_FRAMES` (for example 161) if you have VRAM to spare.

## Honest limits
- The model animates the photo you give it, so the result looks like the real photo moving, not a 3D cartoon. For a cartoon look, make a cartoon start image first (with an image tool) and use that as the `reference_photos` entry.
- Hugging Face model licences differ: read each model page before commercial use.
- Hands, lifts and spins are hard for every current model; expect to regenerate some clips (change `WEDDING_SEED`).

## Troubleshooting
| Symptom | Fix |
|---|---|
| `Quota 'GPUS_ALL_REGIONS' exceeded` / quota error on create | request GPU quota (above) or try another region |
| `ZONE_RESOURCE_POOL_EXHAUSTED` | no L4 free there: try another zone |
| `nvidia-smi` not found after reboot | run `gcp_vm_setup.sh` again; check `sudo journalctl -u google-startup-scripts` |
| `could not select device driver "nvidia"` | NVIDIA container toolkit missing: run `gcp_vm_setup.sh` again |
| `PermissionError` writing `/data` | `sudo chown 10001:10001 data` |
| CUDA out of memory | lower `LTX_WIDTH`/`LTX_HEIGHT`/`LTX_MAX_FRAMES`, or `WEDDING_OFFLOAD=1` |
| Model download fails | set `HF_TOKEN=...` in the environment; check disk space with `df -h` |
