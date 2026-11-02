# Postgres 17 with pgvector, on a private IP, with encrypted connections required.
resource "google_sql_database_instance" "main" {
  name                = var.name
  database_version    = "POSTGRES_17"
  region              = var.region
  deletion_protection = var.deletion_protection
  depends_on          = [google_service_networking_connection.sql]

  settings {
    tier              = var.database_tier
    edition           = "ENTERPRISE"
    availability_type = "ZONAL"
    disk_autoresize   = true

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.main.id
      ssl_mode        = "ENCRYPTED_ONLY"
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }

    # Session, lock and temp-file logging for audit and incident review.
    database_flags {
      name  = "cloudsql.enable_pgaudit"
      value = "on"
    }
    database_flags {
      name  = "log_connections"
      value = "on"
    }
    database_flags {
      name  = "log_disconnections"
      value = "on"
    }
    database_flags {
      name  = "log_lock_waits"
      value = "on"
    }
    database_flags {
      name  = "log_checkpoints"
      value = "on"
    }
    database_flags {
      name  = "log_temp_files"
      value = "0"
    }
  }
}

resource "google_sql_database" "lineage" {
  name     = "lineage"
  instance = google_sql_database_instance.main.name
}

resource "google_sql_database" "keycloak" {
  name     = "keycloak"
  instance = google_sql_database_instance.main.name
}

resource "random_password" "db" {
  for_each = toset(["lineage", "keycloak"])
  length   = 32
  special  = false
}

resource "google_sql_user" "app" {
  for_each = random_password.db
  name     = each.key
  instance = google_sql_database_instance.main.name
  password = each.value.result
}
