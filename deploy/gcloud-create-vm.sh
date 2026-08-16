#!/usr/bin/env bash
# Create the free-tier VM and reserve its IP. Paste into Google Cloud Shell.
#
# Cloud Shell is already authenticated as you, so there is nothing to log into.
# Everything here stays inside Always Free limits: e2-micro, us-central1, and a
# 30GB standard disk (the console's default "balanced" disk is NOT free).

set -euo pipefail

NAME=podcast-cover-dms
ZONE=us-central1-a
REGION=us-central1

echo "==> Project: $(gcloud config get-value project)"

echo "==> Enabling Compute Engine (no-op if already on)"
gcloud services enable compute.googleapis.com --quiet

echo "==> Opening ports 80 and 443"
gcloud compute firewall-rules create allow-http \
    --allow=tcp:80 --target-tags=http-server --quiet 2>/dev/null || echo "    (already exists)"
gcloud compute firewall-rules create allow-https \
    --allow=tcp:443 --target-tags=https-server --quiet 2>/dev/null || echo "    (already exists)"

echo "==> Creating the VM"
gcloud compute instances create "$NAME" \
    --zone="$ZONE" \
    --machine-type=e2-micro \
    --image-family=ubuntu-2404-lts-amd64 \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=30GB \
    --boot-disk-type=pd-standard \
    --tags=http-server,https-server \
    --quiet

IP="$(gcloud compute instances describe "$NAME" --zone="$ZONE" \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')"

echo "==> Reserving $IP so it survives a restart"
gcloud compute addresses create dms-ip \
    --addresses="$IP" --region="$REGION" --quiet 2>/dev/null || echo "    (already reserved)"

cat <<NEXT

────────────────────────────────────────────────────────────
VM is up.

  External IP:  $IP
  Hostname:     $IP.sslip.io

Connect to it:

  gcloud compute ssh $NAME --zone=$ZONE

Then, on the server:

  curl -fsSL https://raw.githubusercontent.com/prodigital97/Podcast-Cover-DMs/claude/podcast-cover-dm-drafts-l133n8/deploy/setup.sh -o setup.sh
  sudo bash setup.sh $IP.sslip.io
────────────────────────────────────────────────────────────
NEXT
