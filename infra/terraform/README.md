# GCP deployment

One environment of Lineage on Google Cloud:

- Cloud Run services for the API, the console and Keycloak, plus a Cloud Run job for ingestion that
  Cloud Scheduler starts each morning.
- Cloud SQL Postgres 17 with pgvector, on a private IP only, with encrypted connections, backups,
  point-in-time recovery, pgaudit and session logging.
- Secret Manager for every password and key, Artifact Registry for the images, and one service
  account per service with access to its own secrets only.
- A private network with flow logs. Cloud Run reaches the database through direct VPC egress.

The deployment drafts from fixtures by default (`drafting = "fixture"`), because live drafting needs
an Anthropic API key. With `drafting = "api"`, add the key to the `lineage-anthropic-api-key` secret
by hand, so it never sits in Terraform state.

The realm reuses the local roles, groups and scopes, with the console's real address, no password
grant and random passwords for the demonstration users (`terraform output -json demo_passwords`).

## Use

```bash
gcloud auth application-default login
cp terraform.tfvars.example terraform.tfvars    # set project_id and image_tag
terraform init
terraform plan
```

Push the images to the `registry` output before applying. CI checks this directory with
`terraform fmt`, `validate`, TFLint and the Trivy config scan, and never applies it.
