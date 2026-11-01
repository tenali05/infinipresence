#!/usr/bin/env bash
# Creates the infiniPresence test VM on Google Cloud.
# The VM stops itself MAX_RUN after every start (Compute Engine max-run-duration),
# so you only pay for running hours plus the disk.
set -euo pipefail
PROJECT="${PROJECT:?set PROJECT to the GCP project id}"
ZONE="${ZONE:-europe-west2-b}"         # London
NAME="${NAME:-infinipresence-test}"
MACHINE="${MACHINE:-e2-standard-2}"    # 2 vCPU, 8 GB RAM
MAX_RUN="${MAX_RUN:-4h}"

gcloud compute addresses create "$NAME-ip" --project "$PROJECT" --region "${ZONE%-*}" 2>/dev/null || true
IP=$(gcloud compute addresses describe "$NAME-ip" --project "$PROJECT" --region "${ZONE%-*}" --format='value(address)')

gcloud compute instances create "$NAME" --project "$PROJECT" --zone "$ZONE" \
  --machine-type "$MACHINE" --image-family debian-12 --image-project debian-cloud \
  --boot-disk-size 40GB --boot-disk-type pd-balanced --address "$IP" \
  --tags http-server,https-server \
  --max-run-duration "$MAX_RUN" --instance-termination-action STOP \
  --metadata-from-file startup-script="$(dirname "$0")/startup.sh"

gcloud compute firewall-rules create allow-http-https --project "$PROJECT" \
  --allow tcp:80,tcp:443 --target-tags http-server,https-server 2>/dev/null || true

echo "VM $NAME created. Site will be at https://$(echo "$IP" | tr . -).sslip.io once the first boot finishes (~20-30 min)."
