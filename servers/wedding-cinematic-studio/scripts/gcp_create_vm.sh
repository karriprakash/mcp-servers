#!/usr/bin/env bash
# Create a GPU VM on Google Cloud. Run this on YOUR computer (needs the gcloud CLI, logged in).
#   GCP_PROJECT=my-project ./scripts/gcp_create_vm.sh
# Defaults: 1x NVIDIA L4 (24 GB), spot pricing, 200 GB disk. For the big Wan model use
#   MACHINE_TYPE=a2-highgpu-1g (1x A100 40 GB) and a zone that has it.
set -euo pipefail

PROJECT="${GCP_PROJECT:?set GCP_PROJECT to your Google Cloud project id}"
ZONE="${GCP_ZONE:-us-central1-a}"
NAME="${VM_NAME:-wedding-gpu}"
MACHINE="${MACHINE_TYPE:-g2-standard-8}"   # g2 = L4 GPU included; 8 vCPU, 32 GB RAM
DISK_GB="${DISK_GB:-200}"
SPOT="${SPOT:-1}"                           # 1 = cheaper, but Google can stop the VM; jobs resume from checkpoints

PRICING=()
if [ "$SPOT" = "1" ]; then
  PRICING=(--provisioning-model=SPOT --instance-termination-action=STOP)
fi

gcloud compute instances create "$NAME" \
  --project="$PROJECT" --zone="$ZONE" \
  --machine-type="$MACHINE" \
  --image-family=ubuntu-2204-lts --image-project=ubuntu-os-cloud \
  --boot-disk-size="${DISK_GB}GB" --boot-disk-type=pd-balanced \
  --maintenance-policy=TERMINATE \
  "${PRICING[@]}"

cat <<MSG

VM '$NAME' created. Next:
  gcloud compute ssh $NAME --zone $ZONE --project $PROJECT
  # then on the VM:
  git clone https://github.com/karriprakash/mcp-servers.git
  cd mcp-servers/servers/wedding-cinematic-studio
  bash scripts/gcp_vm_setup.sh        # installs driver + Docker; run it again after the reboot it asks for

When you are done for the day, stop the VM so compute billing stops (the disk still costs a little):
  gcloud compute instances stop $NAME --zone $ZONE --project $PROJECT
MSG
