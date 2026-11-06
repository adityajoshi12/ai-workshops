#!/usr/bin/env bash
# ============================================================================
# One-time Google Cloud Setup for VibeStudio (Agentic Workflow with ADK)
# Enables required GCP APIs, creates a GCS media bucket, and grants Vertex AI
# permissions to the Cloud Run default service account.
# ============================================================================
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "ERROR: No GCP project configured. Run: gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

BUCKET_NAME="${PROJECT_ID}-vibestudio-media"

echo "==> [1/4] Enabling Vertex AI, Cloud Run, Cloud Build, Artifact Registry & Storage APIs in ${PROJECT_ID}..."
gcloud services enable \
  aiplatform.googleapis.com \
  generativelanguage.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  storage.googleapis.com \
  iam.googleapis.com \
  --project="${PROJECT_ID}"

echo "==> [2/4] Creating Cloud Storage bucket gs://${BUCKET_NAME} (${REGION}) for Imagen & Veo outputs..."
if ! gcloud storage buckets describe "gs://${BUCKET_NAME}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${BUCKET_NAME}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --uniform-bucket-level-access
else
  echo "    Bucket gs://${BUCKET_NAME} already exists."
fi

echo "==> [3/4] Uploading VibeStudio enterprise knowledge docs to gs://${BUCKET_NAME}/knowledge/..."
gcloud storage cp vibe_studio_agent/data/*.md "gs://${BUCKET_NAME}/knowledge/" --project="${PROJECT_ID}"

echo "==> [4/4] Granting Vertex AI & Storage roles to Cloud Run runtime service account..."
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for ROLE in roles/aiplatform.user roles/storage.objectAdmin; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="${ROLE}" \
    --quiet >/dev/null
done

echo ""
echo "Setup complete!"
echo "  Project : ${PROJECT_ID}"
echo "  Region  : ${REGION}"
echo "  Bucket  : gs://${BUCKET_NAME}"
