#!/usr/bin/env bash
# Idempotent GCP bootstrap for ATLAS Plane C (api + web on Cloud Run, Mumbai).
#
# Run by an operator with THEIR OWN gcloud credentials. No secret is needed to BUILD any
# image; the NVIDIA key is stored in Secret Manager and read only at API runtime. Every
# step is safe to re-run (create-or-skip / --quiet).
#
# Usage:
#   PROJECT_ID=your-project ./infra/bootstrap.sh
#   # optional: REGION=asia-south1 NVIDIA_API_KEY=nvapi-... ./infra/bootstrap.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-CHANGE_ME_PROJECT}"
REGION="${REGION:-asia-south1}"          # Mumbai
REPO="${REPO:-indiaruns}"
AR_HOST="${REGION}-docker.pkg.dev"
IMG_BASE="${AR_HOST}/${PROJECT_ID}/${REPO}"
API_SVC="${API_SVC:-indiaruns-api}"
WEB_SVC="${WEB_SVC:-indiaruns-web}"
BUCKET_ART="${BUCKET_ART:-gs://${PROJECT_ID}-artifacts}"
BUCKET_DATA="${BUCKET_DATA:-gs://${PROJECT_ID}-data}"
SECRET_NAME="${SECRET_NAME:-nvidia-api-key}"
RUNTIME_SA="${RUNTIME_SA:-atlas-run@${PROJECT_ID}.iam.gserviceaccount.com}"

if [[ "${PROJECT_ID}" == "CHANGE_ME_PROJECT" ]]; then
  echo "ERROR: set PROJECT_ID (e.g. PROJECT_ID=my-proj ./infra/bootstrap.sh)" >&2
  exit 2
fi

echo ">> Project: ${PROJECT_ID}  Region: ${REGION}"
gcloud config set project "${PROJECT_ID}" >/dev/null

echo ">> Enabling APIs (idempotent)…"
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  iamcredentials.googleapis.com \
  --quiet

echo ">> Artifact Registry repo…"
gcloud artifacts repositories describe "${REPO}" --location="${REGION}" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "${REPO}" \
    --repository-format=docker --location="${REGION}" \
    --description="ATLAS images" --quiet

echo ">> GCS buckets…"
gcloud storage buckets describe "${BUCKET_ART}" >/dev/null 2>&1 || \
  gcloud storage buckets create "${BUCKET_ART}" --location="${REGION}" --uniform-bucket-level-access
gcloud storage buckets describe "${BUCKET_DATA}" >/dev/null 2>&1 || \
  gcloud storage buckets create "${BUCKET_DATA}" --location="${REGION}" --uniform-bucket-level-access

echo ">> Runtime service account…"
gcloud iam service-accounts describe "${RUNTIME_SA}" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "atlas-run" \
    --display-name="ATLAS Cloud Run runtime" --quiet

echo ">> Secret Manager: ${SECRET_NAME} (created empty if absent)…"
if ! gcloud secrets describe "${SECRET_NAME}" >/dev/null 2>&1; then
  gcloud secrets create "${SECRET_NAME}" --replication-policy="automatic" --quiet
fi
if [[ -n "${NVIDIA_API_KEY:-}" ]]; then
  printf '%s' "${NVIDIA_API_KEY}" | gcloud secrets versions add "${SECRET_NAME}" --data-file=- --quiet
  echo "   added a new secret version from \$NVIDIA_API_KEY"
else
  echo "   no \$NVIDIA_API_KEY provided — secret left empty (API runs in deterministic mode)"
fi
gcloud secrets add-iam-policy-binding "${SECRET_NAME}" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/secretmanager.secretAccessor" --quiet >/dev/null

echo ">> Build + push images via Cloud Build (no local Docker needed)…"
gcloud builds submit --tag "${IMG_BASE}/api:latest"  --gcs-log-dir="${BUCKET_ART}/cloudbuild" \
  --config=/dev/stdin <<EOF || gcloud builds submit . -f docker/Dockerfile.api  -t "${IMG_BASE}/api:latest"
steps:
- name: gcr.io/cloud-builders/docker
  args: ['build','-f','docker/Dockerfile.api','-t','${IMG_BASE}/api:latest','.']
images: ['${IMG_BASE}/api:latest']
EOF
gcloud builds submit . --config=/dev/stdin <<EOF
steps:
- name: gcr.io/cloud-builders/docker
  args: ['build','-f','docker/Dockerfile.web','-t','${IMG_BASE}/web:latest','.']
images: ['${IMG_BASE}/web:latest']
EOF

echo ">> Deploy API (key from Secret Manager; deterministic if empty)…"
gcloud run deploy "${API_SVC}" \
  --image="${IMG_BASE}/api:latest" \
  --region="${REGION}" --platform=managed \
  --service-account="${RUNTIME_SA}" \
  --cpu=1 --memory=1Gi --min-instances=0 --max-instances=4 \
  --allow-unauthenticated \
  --set-secrets="NVIDIA_API_KEY=${SECRET_NAME}:latest" \
  --quiet

API_URL="$(gcloud run services describe "${API_SVC}" --region="${REGION}" --format='value(status.url)')"
echo "   API_URL=${API_URL}"

echo ">> Deploy web (its Next.js /api/* route handlers need the NVIDIA key to go live)…"
# The public web UI's live features run as Next.js route handlers ON the web service, so the
# NVIDIA key must be mounted here too — otherwise the web app stays deterministic even when a
# key is supplied. NVIDIA_MODEL (optional) selects the hosted model the web routes call.
WEB_ENV_VARS="API_URL=${API_URL}"
if [[ -n "${NVIDIA_MODEL:-}" ]]; then
  WEB_ENV_VARS="${WEB_ENV_VARS},NVIDIA_MODEL=${NVIDIA_MODEL}"
fi
gcloud run deploy "${WEB_SVC}" \
  --image="${IMG_BASE}/web:latest" \
  --region="${REGION}" --platform=managed \
  --service-account="${RUNTIME_SA}" \
  --cpu=1 --memory=512Mi --min-instances=0 --max-instances=4 \
  --allow-unauthenticated \
  --set-env-vars="${WEB_ENV_VARS}" \
  --set-secrets="NVIDIA_API_KEY=${SECRET_NAME}:latest" \
  --quiet

WEB_URL="$(gcloud run services describe "${WEB_SVC}" --region="${REGION}" --format='value(status.url)')"
echo ""
echo "==================================================================="
echo " ATLAS deployed."
echo "   web : ${WEB_URL}"
echo "   api : ${API_URL}   (health: ${API_URL}/api/health)"
echo "==================================================================="
