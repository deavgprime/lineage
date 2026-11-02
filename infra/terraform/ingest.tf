# Migrations, the pinned sanctions and PEP lists, and the policy corpus, loaded by one job that
# Cloud Scheduler runs each morning.
resource "google_cloud_run_v2_job" "ingest" {
  name                = "${var.name}-ingest"
  location            = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.service["ingest"].email
      timeout         = "1800s"
      max_retries     = 1

      vpc_access {
        egress = "PRIVATE_RANGES_ONLY"
        network_interfaces {
          network    = local.vpc_access.network
          subnetwork = local.vpc_access.subnetwork
        }
      }

      containers {
        image   = "${local.registry}/api:${var.image_tag}"
        command = ["sh", "-c"]
        args = [join(" && ", [
          "python -m lineage_db.migrate",
          "python -m lineage_ingest.fetch /tmp/opensanctions",
          "python -m lineage_ingest.opensanctions --sanctions /tmp/opensanctions/sanctions.csv --peps /tmp/opensanctions/peps.csv --version \"$(cat /tmp/opensanctions/version.txt)\"",
          var.drafting == "fixture" ? "python -m lineage_ingest.policy --no-legislation --flat-embeddings" : "python -m lineage_ingest.policy",
        ])]

        resources {
          limits = { cpu = "2", memory = "4Gi" }
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
          name  = "LINEAGE_MODELS"
          value = "/tmp/models"
        }
      }
    }
  }

  depends_on = [google_secret_manager_secret_iam_member.access, google_secret_manager_secret_version.value]
}

resource "google_cloud_scheduler_job" "ingest" {
  name      = "${var.name}-ingest"
  region    = var.region
  schedule  = var.ingest_schedule
  time_zone = "Europe/London"

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.ingest.name}:run"

    oauth_token {
      service_account_email = google_service_account.service["scheduler"].email
    }
  }
}
