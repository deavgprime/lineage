# The Google APIs this deployment uses, enabled before anything that needs them. They stay enabled
# on destroy, since other work in the project may use them.
resource "google_project_service" "required" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "cloudscheduler.googleapis.com",
    "compute.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
    "iam.googleapis.com",
  ])
  service            = each.key
  disable_on_destroy = false
}
