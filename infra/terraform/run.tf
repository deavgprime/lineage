data "google_project" "current" {}

# Cloud Run gives each service a fixed address from its name and the project number, so the
# services can refer to each other without waiting for one another.
locals {
  urls = {
    for s in ["api", "console", "keycloak"] :
    s => "https://${var.name}-${s}-${data.google_project.current.number}.${var.region}.run.app"
  }
  issuer = "${local.urls.keycloak}/realms/lineage"

  vpc_access = {
    network    = google_compute_network.main.id
    subnetwork = google_compute_subnetwork.run.id
  }
}

resource "google_cloud_run_v2_service" "api" {
  name                = "${var.name}-api"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.service["api"].email

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = local.vpc_access.network
        subnetwork = local.vpc_access.subnetwork
      }
    }

    containers {
      image = "${local.registry}/api:${var.image_tag}"

      ports {
        container_port = 8000
      }

      resources {
        limits = { cpu = "1", memory = "2Gi" }
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.secret["database-url"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "OIDC_ISSUER"
        value = local.issuer
      }
      env {
        name  = "LINEAGE_RUNNER"
        value = var.drafting == "fixture" ? "fixture" : "live"
      }
      env {
        name  = "LINEAGE_ENV"
        value = var.drafting == "fixture" ? "demo" : "production"
      }
      env {
        name  = "LINEAGE_MODEL"
        value = "api"
      }
      dynamic "env" {
        for_each = var.drafting == "api" ? [1] : []
        content {
          name = "ANTHROPIC_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.secret["anthropic-api-key"].secret_id
              version = "latest"
            }
          }
        }
      }

      startup_probe {
        http_get {
          path = "/health/ready"
        }
        initial_delay_seconds = 5
        period_seconds        = 5
        failure_threshold     = 24
      }
    }
  }

  depends_on = [google_project_service.required, google_secret_manager_secret_iam_member.access, google_secret_manager_secret_version.value]
}

resource "google_cloud_run_v2_service" "console" {
  name                = "${var.name}-console"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.service["console"].email

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = "${local.registry}/console:${var.image_tag}"

      ports {
        container_port = 3000
      }

      resources {
        limits = { cpu = "1", memory = "512Mi" }
      }

      env {
        name  = "OIDC_ISSUER"
        value = local.issuer
      }
      env {
        name  = "OIDC_CLIENT_ID"
        value = "lineage-console"
      }
      env {
        name  = "APP_URL"
        value = local.urls.console
      }
      env {
        name  = "LINEAGE_API_URL"
        value = local.urls.api
      }
      env {
        name  = "LINEAGE_API_AUDIENCE"
        value = local.urls.api
      }
      env {
        name = "SESSION_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.secret["session-secret"].secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [google_project_service.required, google_secret_manager_secret_iam_member.access, google_secret_manager_secret_version.value]
}

resource "google_cloud_run_v2_service" "keycloak" {
  name                = "${var.name}-keycloak"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.service["keycloak"].email

    # Keycloak takes about 30 seconds to start, so one instance stays warm rather than every
    # sign-in after a quiet spell waiting for it.
    scaling {
      min_instance_count = 1
      max_instance_count = 1
    }

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = local.vpc_access.network
        subnetwork = local.vpc_access.subnetwork
      }
    }

    volumes {
      name = "realm"
      secret {
        secret = google_secret_manager_secret.secret["realm"].secret_id
        items {
          version = "latest"
          path    = "lineage-realm.json"
        }
      }
    }

    containers {
      image = "${local.registry}/keycloak:${var.image_tag}"
      args  = ["start", "--import-realm", "--http-enabled=true", "--proxy-headers=xforwarded", "--health-enabled=true", "--cache=local", "--features-disabled=admin"]

      resources {
        limits = { cpu = "1", memory = "1Gi" }
      }

      volume_mounts {
        name       = "realm"
        mount_path = "/opt/keycloak/data/import"
      }

      env {
        name  = "KC_DB"
        value = "postgres"
      }
      env {
        name  = "KC_DB_URL"
        value = "jdbc:postgresql://${local.database_host}:5432/keycloak?sslmode=require"
      }
      env {
        name  = "KC_DB_USERNAME"
        value = "keycloak"
      }
      env {
        name = "KC_DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.secret["keycloak-db-password"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "KC_HOSTNAME"
        value = local.urls.keycloak
      }
      env {
        name  = "KC_BOOTSTRAP_ADMIN_USERNAME"
        value = "admin"
      }
      env {
        name = "KC_BOOTSTRAP_ADMIN_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.secret["keycloak-admin-password"].secret_id
            version = "latest"
          }
        }
      }

      ports {
        container_port = 8080
      }

      # Ready only once Keycloak says so on its management port. The HTTP port opens earlier and
      # answers 503 while Keycloak is still starting.
      startup_probe {
        http_get {
          path = "/health/ready"
          port = 9000
        }
        initial_delay_seconds = 10
        period_seconds        = 10
        failure_threshold     = 30
      }
    }
  }

  depends_on = [google_project_service.required, google_secret_manager_secret_iam_member.access, google_secret_manager_secret_version.value]
}

# The console and the sign-in page are public. The admin console is switched off in Keycloak, so
# the public service serves sign-in only.
resource "google_cloud_run_v2_service_iam_member" "public" {
  for_each = {
    console  = google_cloud_run_v2_service.console.name
    keycloak = google_cloud_run_v2_service.keycloak.name
  }
  name     = each.value
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# The API is not public. Cloud Run admits only the console's service account, which proves itself
# with a Google ID token in X-Serverless-Authorization, leaving Authorization for the user's token.
resource "google_cloud_run_v2_service_iam_member" "console_calls_api" {
  name     = google_cloud_run_v2_service.api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = google_service_account.service["console"].member
}
