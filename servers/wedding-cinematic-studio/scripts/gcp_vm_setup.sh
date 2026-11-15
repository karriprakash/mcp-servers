#!/usr/bin/env bash
# Run ON the Google Cloud VM (Ubuntu 22.04 with an NVIDIA GPU). Safe to run twice:
# the first run installs the GPU driver and asks you to reboot; the second run installs Docker and builds.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v nvidia-smi >/dev/null 2>&1 || ! nvidia-smi >/dev/null 2>&1; then
  echo "== Installing the NVIDIA driver (Google's installer)"
  sudo apt-get update && sudo apt-get install -y python3 curl
  curl -fsSL https://storage.googleapis.com/compute-gpu-installation-us/installer/latest/cuda_installer.pyz -o /tmp/cuda_installer.pyz
  sudo python3 /tmp/cuda_installer.pyz install_driver
  echo
  echo "Driver installed. Reboot now, then run this script again:  sudo reboot"
  exit 0
fi
nvidia-smi

if ! command -v docker >/dev/null 2>&1; then
  echo "== Installing Docker"
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

if ! dpkg -s nvidia-container-toolkit >/dev/null 2>&1; then
  echo "== Installing the NVIDIA container toolkit"
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
  sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
  sudo nvidia-ctk runtime configure --runtime=docker
  sudo systemctl restart docker
fi

mkdir -p data inputs
sudo chown 10001:10001 data

echo "== Building the GPU image (first time takes a few minutes)"
sudo docker compose --profile gpu build

echo "== Checking Docker can see the GPU"
sudo docker run --rm --gpus all pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime python -c "import torch;print('cuda:',torch.cuda.is_available(),torch.cuda.get_device_name(0))"

cat <<MSG

Ready. Next steps (see docs/GCP_GPU_GUIDE.md):
  1. Copy your photos and card into ./inputs   (from your computer: gcloud compute scp --recurse ./my_photos wedding-gpu:~/mcp-servers/servers/wedding-cinematic-studio/inputs)
  2. Download the model:   sudo docker compose --profile gpu run --rm studio-gpu python scripts/download_models.py --preset ltx
  3. Try one clip:         sudo docker compose --profile gpu run --rm studio-gpu python -m src.cli /inputs/job.json --only-scene s1
MSG
