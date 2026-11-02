# One service account per service, each with only what it needs.
resource "google_service_account" "service" {
  for_each     = toset(["api", "console", "keycloak", "ingest", "scheduler"])
  account_id   = "${var.name}-${each.key}"
  display_name = "Lineage ${each.key}"
}

resource "google_project_iam_member" "sql_client" {
  for_each = toset(["api", "keycloak", "ingest"])
  project  = var.project_id
  role     = "roles/cloudsql.client"
  member   = google_service_account.service[each.key].member
}

locals {
  secret_access = {
    "api-database-url"                 = ["api", "database-url"]
    "ingest-database-url"              = ["ingest", "database-url"]
    "api-anthropic-api-key"            = ["api", "anthropic-api-key"]
    "console-session-secret"           = ["console", "session-secret"]
    "keycloak-keycloak-db-password"    = ["keycloak", "keycloak-db-password"]
    "keycloak-keycloak-admin-password" = ["keycloak", "keycloak-admin-password"]
    "keycloak-realm"                   = ["keycloak", "realm"]
  }
}

resource "google_secret_manager_secret_iam_member" "access" {
  for_each  = local.secret_access
  secret_id = google_secret_manager_secret.secret[each.value[1]].id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.service[each.value[0]].member
}

resource "google_artifact_registry_repository_iam_member" "pull" {
  for_each   = toset(["api", "console", "keycloak", "ingest"])
  repository = google_artifact_registry_repository.images.name
  location   = var.region
  role       = "roles/artifactregistry.reader"
  member     = google_service_account.service[each.key].member
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_runs_ingest" {
  name     = google_cloud_run_v2_job.ingest.name
  location = var.region
  role     = "roles/run.invoker"
  member   = google_service_account.service["scheduler"].member
}
