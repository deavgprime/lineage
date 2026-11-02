variable "project_id" {
  description = "The GCP project to deploy into."
  type        = string
}

variable "region" {
  description = "Region for every regional resource. London keeps UK pack data in the UK."
  type        = string
  default     = "europe-west2"
}

variable "name" {
  description = "Prefix for resource names."
  type        = string
  default     = "lineage"
}

variable "image_tag" {
  description = "Tag of the api, console and keycloak images in this project's Artifact Registry."
  type        = string
}

variable "drafting" {
  description = "How the API drafts files: fixture (canned, no model) or api (Claude through an Anthropic API key in Secret Manager)."
  type        = string
  default     = "fixture"

  validation {
    condition     = contains(["fixture", "api"], var.drafting)
    error_message = "drafting must be fixture or api."
  }
}

variable "database_tier" {
  description = "Cloud SQL machine tier."
  type        = string
  default     = "db-custom-1-3840"
}

variable "deletion_protection" {
  description = "Protect the database from deletion. Off only for a short-lived demonstration."
  type        = bool
  default     = true
}

variable "ingest_schedule" {
  description = "Cron schedule, in Europe/London time, for reloading lists and the policy corpus."
  type        = string
  default     = "0 5 * * *"
}
