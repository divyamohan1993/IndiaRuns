# ATLAS — GCP Deployment (Plane C)

Production deployment of the ATLAS live product (api + web) to **Google Cloud Run** in
**`asia-south1` (Mumbai)**. This is **optional** and **credential-gated** — it is never
required to build images, run tests, reproduce the ranker, or evaluate the submission.

> **Hard rule:** no secret is needed to BUILD any image. The NVIDIA key is stored in
> Secret Manager and read by the API **only at runtime**. With no key, the API still
> serves every artifact endpoint and the live endpoints degrade to a deterministic,
> fact-grounded brain.

## What gets created

| Resource | Name | Notes |
|---|---|---|
| Artifact Registry (Docker) | `indiaruns` | holds `api` + `web` images |
| Cloud Run service | `indiaruns-api` | 1 vCPU / 1 GiB, scale-to-zero, public |
| Cloud Run service | `indiaruns-web` | 1 vCPU / 512 MiB, scale-to-zero, public |
| GCS bucket | `<project>-artifacts` | optional artifact / build-log store |
| GCS bucket | `<project>-data` | optional raw-data store |
| Service Account | `atlas-run@…` | Cloud Run runtime identity |
| Secret Manager | `nvidia-api-key` | mounted into the API only; may be empty |

## Prerequisites (operator supplies their own creds)

- `gcloud` CLI authenticated (`gcloud auth login`) with Owner/Editor on a project, or
- Terraform >= 1.5 with application-default credentials (`gcloud auth application-default login`).
- A billing-enabled GCP project. **No NVIDIA key is required.**

## Option A — `bootstrap.sh` (idempotent gcloud, recommended)

```bash
# minimal: enables APIs, creates registry/buckets/SA/secret, builds+pushes, deploys.
PROJECT_ID=your-project ./infra/bootstrap.sh

# with the live LLM enabled:
PROJECT_ID=your-project NVIDIA_API_KEY=nvapi-xxxxx ./infra/bootstrap.sh
```

Every step is create-or-skip, so re-running is safe. It prints the final `web` and `api`
URLs. Images are built by Cloud Build, so a local Docker daemon is not required.

## Option B — Terraform

```bash
cd infra
terraform init
# Images must exist in Artifact Registry first (run cloudbuild.yaml or bootstrap's build
# steps, or `gcloud builds submit -f docker/Dockerfile.api ...`).
terraform apply -var project_id=your-project              # deterministic API
terraform apply -var project_id=your-project -var nvidia_api_key=nvapi-xxxxx  # live API
```

`outputs`: `api_url`, `web_url`, `artifact_registry`.

## Option C — CI-driven deploy on tag `v*` (no long-lived JSON key)

`cloudbuild.yaml` + `.github/workflows/deploy.yml` deploy via **Workload Identity
Federation** when:

1. the repo variable `GCP_ENABLED == 'true'`, and
2. WIF + repo variables are configured (see below).

This avoids storing any service-account JSON key in GitHub.

### One-time WIF setup

```bash
PROJECT_ID=your-project
POOL=github-pool
PROVIDER=github-provider
REPO=owner/IndiaRuns                 # your GitHub repo

gcloud iam workload-identity-pools create "$POOL" \
  --project="$PROJECT_ID" --location=global --display-name="GitHub pool"

gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" \
  --project="$PROJECT_ID" --location=global --workload-identity-pool="$POOL" \
  --display-name="GitHub provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='$REPO'" \
  --issuer-uri="https://token.actions.githubusercontent.com"

# Let the GitHub repo impersonate the deploy SA:
DEPLOY_SA=atlas-deploy@$PROJECT_ID.iam.gserviceaccount.com
gcloud iam service-accounts create atlas-deploy --project="$PROJECT_ID" || true
PROJECT_NUM=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
gcloud iam service-accounts add-iam-policy-binding "$DEPLOY_SA" \
  --project="$PROJECT_ID" --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUM/locations/global/workloadIdentityPools/$POOL/attribute.repository/$REPO"
# Grant the deploy SA: run.admin, artifactregistry.writer, cloudbuild.builds.editor, iam.serviceAccountUser.
```

Then set in **GitHub → Settings**:

- **Variables:** `GCP_ENABLED=true`, `GCP_PROJECT_ID`, `GCP_REGION=asia-south1`,
  `GCP_WIF_PROVIDER=projects/$PROJECT_NUM/locations/global/workloadIdentityPools/github-pool/providers/github-provider`,
  `GCP_DEPLOY_SA=atlas-deploy@<project>.iam.gserviceaccount.com`.

Pushing a tag `v*` then builds + pushes + deploys. Without `GCP_ENABLED=true` the deploy
workflow **skips cleanly** — PRs and the main CI never need any cloud credentials.

## Teardown

```bash
gcloud run services delete indiaruns-api indiaruns-web --region=asia-south1 --quiet
# or: cd infra && terraform destroy -var project_id=your-project
```
