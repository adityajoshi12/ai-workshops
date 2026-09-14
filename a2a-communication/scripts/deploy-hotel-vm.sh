#!/usr/bin/env bash
# Deploys hotel-search-agent to a Container-Optimized OS VM on Compute Engine.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-gde-workspace}"
ZONE="${ZONE:-asia-south1-a}"
INSTANCE_NAME="${INSTANCE_NAME:-hotel-search-agent-vm}"
IMAGE_TAG="gcr.io/${PROJECT_ID}/hotel-search-agent"

echo "==> Building and pushing container image: ${IMAGE_TAG}..."
gcloud builds submit --project="${PROJECT_ID}" \
  --tag="${IMAGE_TAG}" \
  --machine-type=e2-highcpu-8 \
  "$(cd "$(dirname "${BASH_SOURCE[0]}")/../hotel-search-agent" && pwd)"

echo "==> Ensuring firewall rule for port 8080 exists..."
if ! gcloud compute firewall-rules describe allow-hotel-agent-8080 --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud compute firewall-rules create allow-hotel-agent-8080 \
    --project="${PROJECT_ID}" \
    --allow=tcp:8080 \
    --target-tags=http-server \
    --source-ranges=0.0.0.0/0
fi

echo "==> Checking if instance ${INSTANCE_NAME} exists..."
if gcloud compute instances describe "${INSTANCE_NAME}" --project="${PROJECT_ID}" --zone="${ZONE}" >/dev/null 2>&1; then
  echo "Instance ${INSTANCE_NAME} already exists. Recreating to apply fresh image and startup script..."
  gcloud compute instances delete "${INSTANCE_NAME}" --project="${PROJECT_ID}" --zone="${ZONE}" --quiet
fi

echo "==> Creating Compute Engine VM with Container-Optimized OS..."
gcloud compute instances create "${INSTANCE_NAME}" \
  --project="${PROJECT_ID}" \
  --zone="${ZONE}" \
  --machine-type=e2-small \
  --image-family=cos-stable \
  --image-project=cos-cloud \
  --scopes=cloud-platform \
  --tags=http-server \
  --metadata=startup-script='#!/bin/bash
set -ex
export HOME=/var/lib/docker
mkdir -p /var/lib/docker
docker-credential-gcr configure-docker --registries=gcr.io
VM_IP=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip")
docker pull gcr.io/'"${PROJECT_ID}"'/hotel-search-agent
docker run -d --restart=always \
  --name=hotel-search-agent \
  -p 8080:8080 \
  -e GOOGLE_CLOUD_PROJECT='"${PROJECT_ID}"' \
  -e GOOGLE_CLOUD_LOCATION=global \
  -e APP_URL=http://${VM_IP}:8080 \
  gcr.io/'"${PROJECT_ID}"'/hotel-search-agent'

echo "==> Fetching VM external IP..."
VM_IP=$(gcloud compute instances describe "${INSTANCE_NAME}" \
  --project="${PROJECT_ID}" \
  --zone="${ZONE}" \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "=========================================================="
echo " hotel-search-agent deployed successfully!"
echo " VM External IP: ${VM_IP}"
echo " HOTEL_AGENT_URL: http://${VM_IP}:8080"
echo " Agent Card: http://${VM_IP}:8080/a2a/app/.well-known/agent-card.json"
echo "=========================================================="
