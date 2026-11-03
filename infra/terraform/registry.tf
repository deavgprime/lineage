resource "google_artifact_registry_repository" "images" {
  depends_on = [google_project_service.required]

  repository_id = var.name
  location      = var.region
  format        = "DOCKER"
  description   = "Lineage api, console and keycloak images"
}

locals {
  registry = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}
