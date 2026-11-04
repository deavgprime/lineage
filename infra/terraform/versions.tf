terraform {
  required_version = ">= 1.16.0"

  # State holds every generated password, so it lives in the encrypted, versioned bucket made by
  # bootstrap/, never on a laptop. The bucket is given at init:
  #   terraform init -backend-config="bucket=<state bucket>"
  backend "gcs" {
    prefix = "lineage"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "8.7.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "3.9.1"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
