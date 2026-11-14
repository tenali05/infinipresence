#!/usr/bin/env bash
# Creates the infiniPresence test VM on Google Cloud.
# The VM stops itself MAX_RUN after every start (Compute Engine max-run-duration),
# so you only pay for running hours plus the disk and the reserved IP.
#   PROJECT=infinipresence ADMIN_PASSWORD=... ./deploy/create-vm.sh
set -euo pipefail
PROJECT="${PROJECT:?set PROJECT to the GCP project id}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:?set ADMIN_PASSWORD for the Administrator login}"
ZONE="${ZONE:-europe-west2-b}"         # London
REGION="${ZONE%-*}"
NAME="${NAME:-infinipresence-test}"
MACHINE="${MACHINE:-e2-standard-2}"    # 2 vCPU, 8 GB RAM
MAX_RUN="${MAX_RUN:-4h}"
BRANCH="${BRANCH:-main}"               # git branch the VM deploys and follows

gcloud compute addresses describe "$NAME-ip" --project "$PROJECT" --region "$REGION" >/dev/null 2>&1 \
  || gcloud compute addresses create "$NAME-ip" --project "$PROJECT" --region "$REGION"
IP=$(gcloud compute addresses describe "$NAME-ip" --project "$PROJECT" --region "$REGION" --format='value(address)')

gcloud compute firewall-rules describe allow-http-https --project "$PROJECT" >/dev/null 2>&1 \
  || gcloud compute firewall-rules create allow-http-https --project "$PROJECT" \
       --allow tcp:80,tcp:443 --target-tags http-server,https-server

gcloud compute instances create "$NAME" --project "$PROJECT" --zone "$ZONE" \
  --machine-type "$MACHINE" --image-family debian-12 --image-project debian-cloud \
  --boot-disk-size 40GB --boot-disk-type pd-balanced --address "$IP" \
  --tags http-server,https-server \
  --max-run-duration "$MAX_RUN" --instance-termination-action STOP \
  --metadata "app-branch=$BRANCH,admin-password=$ADMIN_PASSWORD" \
  --metadata-from-file startup-script="$(dirname "$0")/startup.sh"

echo "VM $NAME created. Site: https://$(echo "$IP" | tr . -).sslip.io (first boot takes ~30 min)."
