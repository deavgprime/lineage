# The bucket that holds the deployment's Terraform state. Apply this once, with local state, before
# the main configuration. Terraform state contains every generated password, so the bucket is
# versioned, never public, readable only by the people named in state_admins, and encrypted at rest.

terraform {
  required_version = ">= 1.16.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "8.7.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  description = "The GCP project the state bucket belongs to."
  type        = string
}

variable "region" {
  description = "Region for the bucket. Keep it where the deployment's data lives."
  type        = string
  default     = "europe-west2"
}

variable "bucket" {
  description = "Globally unique name for the state bucket."
  type        = string
}

variable "state_admins" {
  description = "Members who may read and write state, such as user:alice@bank.example."
  type        = list(string)
}

resource "google_storage_bucket" "state" {
  name                        = var.bucket
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  # Every write is kept, so a bad apply can be rolled back.
  versioning {
    enabled = true
  }

  # Old versions are pruned after ninety days, keeping the last five.
  lifecycle_rule {
    condition {
      num_newer_versions         = 5
      days_since_noncurrent_time = 90
    }
    action {
      type = "Delete"
    }
  }

  logging {
    log_bucket = google_storage_bucket.access_logs.name
  }
}

# Who read or changed the state, kept apart from the state itself.
resource "google_storage_bucket" "access_logs" {
  name                        = "${var.bucket}-access-logs"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }
}

resource "google_storage_bucket_iam_member" "state_admin" {
  for_each = toset(var.state_admins)
  bucket   = google_storage_bucket.state.name
  role     = "roles/storage.objectAdmin"
  member   = each.value
}

output "bucket" {
  description = "Pass to: terraform init -backend-config=\"bucket=<this>\""
  value       = google_storage_bucket.state.name
}
