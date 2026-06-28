# Terraform equivalent of infra/bootstrap.sh for ATLAS Plane C on GCP.
#
# Provisions Artifact Registry, two GCS buckets, a runtime service account, the
# nvidia-api-key secret (value supplied out-of-band or left empty), and two Cloud Run
# services (api + web) in asia-south1 (Mumbai). Images must already be pushed to Artifact
# Registry (by cloudbuild.yaml or bootstrap.sh) — Terraform references them by tag.
#
# No secret is required to PLAN/APPLY the non-secret resources; the NVIDIA key is read by
# the API only at runtime via the secret mount.
#
#   terraform init
#   terraform apply -var project_id=YOUR_PROJECT

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }
}

variable "project_id" {
  type        = string
  description = "GCP project id."
}

variable "region" {
  type    = string
  default = "asia-south1" # Mumbai
}

variable "repo" {
  type    = string
  default = "indiaruns"
}

variable "image_tag" {
  type    = string
  default = "latest"
}

variable "nvidia_api_key" {
  type        = string
  default     = ""
  sensitive   = true
  description = "Optional. If empty, the secret is created with no usable version and the API runs deterministic."
}

variable "nvidia_model" {
  type        = string
  default     = ""
  description = "Optional model id for the hosted NVIDIA endpoint used by the web app's route handlers. If empty, the web app degrades to deterministic output even when a key is present."
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  ar_host  = "${var.region}-docker.pkg.dev"
  img_base = "${local.ar_host}/${var.project_id}/${var.repo}"
}

# --- APIs ------------------------------------------------------------------------------
resource "google_project_service" "svc" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
    "iamcredentials.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# --- Artifact Registry -----------------------------------------------------------------
resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = var.repo
  format        = "DOCKER"
  description   = "ATLAS images"
  depends_on    = [google_project_service.svc]
}

# --- GCS buckets -----------------------------------------------------------------------
resource "google_storage_bucket" "artifacts" {
  name                        = "${var.project_id}-artifacts"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false
}

resource "google_storage_bucket" "data" {
  name                        = "${var.project_id}-data"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false
}

# --- Runtime service account -----------------------------------------------------------
resource "google_service_account" "runtime" {
  account_id   = "atlas-run"
  display_name = "ATLAS Cloud Run runtime"
}

# --- Secret Manager: nvidia-api-key ----------------------------------------------------
resource "google_secret_manager_secret" "nvidia" {
  secret_id = "nvidia-api-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.svc]
}

# Only create a version when a key is actually supplied.
resource "google_secret_manager_secret_version" "nvidia" {
  count       = var.nvidia_api_key == "" ? 0 : 1
  secret      = google_secret_manager_secret.nvidia.id
  secret_data = var.nvidia_api_key
}

resource "google_secret_manager_secret_iam_member" "nvidia_access" {
  secret_id = google_secret_manager_secret.nvidia.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

# --- Cloud Run: API --------------------------------------------------------------------
resource "google_cloud_run_v2_service" "api" {
  name     = "indiaruns-api"
  location = var.region

  template {
    service_account = google_service_account.runtime.email
    scaling {
      min_instance_count = 0
      max_instance_count = 4
    }
    containers {
      image = "${local.img_base}/api:${var.image_tag}"
      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }
      ports {
        container_port = 8080
      }
      # Mount the key only when a version exists; otherwise the API runs deterministic.
      dynamic "env" {
        for_each = var.nvidia_api_key == "" ? [] : [1]
        content {
          name = "NVIDIA_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.nvidia.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }
  depends_on = [google_secret_manager_secret_iam_member.nvidia_access]
}

resource "google_cloud_run_v2_service_iam_member" "api_public" {
  name     = google_cloud_run_v2_service.api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# --- Cloud Run: web --------------------------------------------------------------------
resource "google_cloud_run_v2_service" "web" {
  name     = "indiaruns-web"
  location = var.region

  template {
    service_account = google_service_account.runtime.email
    scaling {
      min_instance_count = 0
      max_instance_count = 4
    }
    containers {
      image = "${local.img_base}/web:${var.image_tag}"
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
      ports {
        container_port = 8080
      }
      env {
        name  = "API_URL"
        value = google_cloud_run_v2_service.api.uri
      }
      # The public web UI's live features are Next.js route handlers that run ON the web
      # service, so the NVIDIA key must be visible here too — otherwise the web app stays
      # deterministic even when a key is supplied. Mounted only when a version exists.
      dynamic "env" {
        for_each = var.nvidia_api_key == "" ? [] : [1]
        content {
          name = "NVIDIA_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.nvidia.secret_id
              version = "latest"
            }
          }
        }
      }
      dynamic "env" {
        for_each = var.nvidia_model == "" ? [] : [1]
        content {
          name  = "NVIDIA_MODEL"
          value = var.nvidia_model
        }
      }
    }
  }
  depends_on = [google_secret_manager_secret_iam_member.nvidia_access]
}

resource "google_cloud_run_v2_service_iam_member" "web_public" {
  name     = google_cloud_run_v2_service.web.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# --- Outputs ---------------------------------------------------------------------------
output "api_url" {
  value = google_cloud_run_v2_service.api.uri
}

output "web_url" {
  value = google_cloud_run_v2_service.web.uri
}

output "artifact_registry" {
  value = local.img_base
}
