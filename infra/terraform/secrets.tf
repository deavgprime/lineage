locals {
  database_host = google_sql_database_instance.main.private_ip_address
}

resource "random_password" "session" {
  length  = 48
  special = false
}

resource "random_password" "keycloak_admin" {
  length  = 32
  special = false
}

# Demonstration users get random passwords here, never the local test ones.
resource "random_password" "demo_user" {
  for_each = toset(local.demo_users)
  length   = 20
  special  = false
}

resource "google_secret_manager_secret" "secret" {
  for_each   = toset(["database-url", "keycloak-db-password", "keycloak-admin-password", "session-secret", "realm", "anthropic-api-key"])
  secret_id  = "${var.name}-${each.key}"
  depends_on = [google_project_service.required]

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
}

resource "google_secret_manager_secret_version" "value" {
  for_each = {
    "database-url"            = "postgresql://lineage:${random_password.db["lineage"].result}@${local.database_host}:5432/lineage?sslmode=require"
    "keycloak-db-password"    = random_password.db["keycloak"].result
    "keycloak-admin-password" = random_password.keycloak_admin.result
    "session-secret"          = random_password.session.result
    "realm"                   = local.realm
  }
  secret      = google_secret_manager_secret.secret[each.key].id
  secret_data = each.value
}

# The Anthropic API key is added by hand when drafting = "api", so it never sits in Terraform state.
