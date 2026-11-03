# Deploying and running Lineage

Lineage ships as two images, `api` and `console`, published with each release to
`ghcr.io/deavgprime/lineage`. There are two ways to run them:

- **GCP**, for a demonstration or a bank on Google Cloud, with the Terraform in `infra/terraform`.
- **The bank's own Kubernetes cluster**, with the Helm chart in `infra/helm/lineage`.

Both need the same four things around the images: Postgres 17 with pgvector, an OpenID Connect
provider, a few secrets, and a way to reach a model.

## What every deployment needs

| Need | GCP (Terraform) | Bank cluster (Helm) |
| --- | --- | --- |
| Postgres 17 with `vector`, `pg_trgm` and `pgcrypto` | Cloud SQL, created | The bank's own, given as `DATABASE_URL` |
| OpenID Connect provider with the lineage realm's roles, groups and scopes | Keycloak on Cloud Run, created, realm imported | The bank's own, configured from `infra/keycloak/lineage-realm.json` |
| Secrets | Secret Manager, created | A Kubernetes Secret the bank creates |
| Images | Pushed to the project's Artifact Registry | Pulled from GitHub Packages or the bank's mirror |
| Model | Fixture drafting by default, or an Anthropic API key | An Anthropic API key, or fixture drafting for a demonstration |

## Settings

| Variable | Used by | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | API, jobs | Postgres connection string, with `sslmode=require` outside a laptop |
| `OIDC_ISSUER` | API, console | The realm's issuer, as browsers and tokens see it |
| `OIDC_JWKS_URL` | API | Where to fetch signing keys, if not under the issuer |
| `OIDC_BACKCHANNEL_URL` | Console | Where the console server reaches the provider, if not the issuer. HTTPS unless the issuer is localhost |
| `OIDC_CLIENT_ID` | Console | `lineage-console` |
| `APP_URL` | Console | The console's public address, for sign-in redirects |
| `LINEAGE_API_URL` | Console | Where the console server reaches the API |
| `SESSION_SECRET` | Console | At least 32 random characters. Encrypts the session cookie |
| `LINEAGE_RUNNER` | API | `fixture` drafts canned files for demonstrations and tests. Anything else drafts live |
| `LINEAGE_MODEL` | API | `api` uses the Anthropic API. Unset uses Claude Code on a signed-in machine |
| `ANTHROPIC_API_KEY` | API | Needed for live drafting and policy answers through the API |
| `LINEAGE_MODELS` | API, jobs | A writable directory for the local embedding and reranking models |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | API | Where to send traces. Empty turns tracing off |
| `OTEL_EXPORTER_OTLP_HEADERS` | API | Headers for that endpoint, such as Langfuse's keys |

## Model access

Drafting and policy answers use Claude Opus 5.5 at medium effort. A deployment reaches it in one of
two ways:

- **An Anthropic API key**, with `LINEAGE_MODEL=api`. The key is a secret: on GCP it is added to the
  `lineage-anthropic-api-key` secret by hand, so it never sits in Terraform state.
- **Fixtures**, with `LINEAGE_RUNNER=fixture`. Files are drafted from canned, fully cited content
  with no model call. This is for demonstrations and tests only, and the API logs a warning when it
  is on.

Embeddings and reranking for policy questions run locally on CPU, downloaded once into
`LINEAGE_MODELS`. Nothing about a policy question leaves the deployment except the final answer
request to Claude, after redaction.

## Deploying on GCP

```bash
gcloud auth application-default login
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars        # project_id, image_tag, drafting
terraform init
terraform apply -target=google_project_service.required -target=google_artifact_registry_repository.images
```

Push the images to the `registry` output, including Keycloak, since Cloud Run pulls from Artifact
Registry:

```bash
REG=$(terraform output -raw registry); TAG=0.7.0
for image in api console; do
  docker pull ghcr.io/deavgprime/lineage/$image:$TAG
  docker tag ghcr.io/deavgprime/lineage/$image:$TAG $REG/$image:$TAG && docker push $REG/$image:$TAG
done
docker pull quay.io/keycloak/keycloak:26.8.0
docker tag quay.io/keycloak/keycloak:26.8.0 $REG/keycloak:$TAG && docker push $REG/keycloak:$TAG
```

Then apply the rest, load the data once, and read the addresses and demonstration passwords:

```bash
terraform apply
gcloud run jobs execute lineage-ingest --region europe-west2 --wait
terraform output urls
terraform output -json demo_passwords
```

To remove everything, set `deletion_protection = false`, apply, then `terraform destroy`.

## Installing on a bank's cluster

```bash
kubectl create secret generic lineage \
  --from-literal=DATABASE_URL='postgresql://lineage:...@db.bank.internal:5432/lineage?sslmode=require' \
  --from-literal=SESSION_SECRET="$(openssl rand -base64 32)" \
  --from-literal=ANTHROPIC_API_KEY='...'

helm install lineage oci://ghcr.io/deavgprime/lineage/charts/lineage --version 0.7.0 \
  --set oidc.issuer=https://sso.bank.example/realms/lineage \
  --set consoleUrl=https://lineage.bank.example \
  --set existingSecret=lineage

kubectl create job --from=cronjob/lineage-ingest lineage-ingest-first
```

Migrations run as a hook before every install and upgrade. Expose the console through the bank's
ingress, and allow that ingress in `networkPolicy.ingressFrom`. The API is reachable only from the
console.

## Operating it

**First load and refresh.** The ingestion job applies migrations, loads the pinned sanctions and PEP
lists, and loads the policy corpus. It runs daily. A reload of unchanged data writes nothing.
Changing the pinned list version is a code change, reviewed like any other.

**Backups.** On GCP, Cloud SQL keeps daily backups with point-in-time recovery. On a bank's
cluster, the bank's database backups cover everything: Lineage keeps all state in Postgres.

**Rotating keys and passwords.**

- Session secret: change `SESSION_SECRET` and restart the console. Everyone signs in again.
- Database password: change it in Postgres and in the secret, then restart the API and console.
- Anthropic key: add a new secret version and restart the API.
- Signing keys are the identity provider's, and the API fetches them as they change.

**Checking the audit log.** Every case, tool call, model call, redaction, sign-off and policy
question is a row in a hash chain. To check the whole chain:

```bash
DATABASE_URL=... python -m lineage_db.audit
```

An MLRO or auditor can export one case's trail from the API (`GET /cases/{id}/audit/export`) and
check it anywhere with plain Python: `python3 scripts/verify_audit_export.py export.json`.

**Traces.** With `OTEL_EXPORTER_OTLP_ENDPOINT` set, each request, agent step and model call is
traced with ids, counts and timings only, never personal data.

## The same deployment on AWS

| GCP | AWS |
| --- | --- |
| Cloud Run services | ECS on Fargate services behind an Application Load Balancer |
| Cloud Run job and Cloud Scheduler | ECS scheduled task through EventBridge Scheduler |
| Cloud SQL for PostgreSQL 17, private IP | RDS for PostgreSQL 17 in private subnets |
| Secret Manager | Secrets Manager |
| Artifact Registry | ECR |
| VPC with direct VPC egress and flow logs | VPC with private subnets and flow logs |
| One service account per service | One task role per service |
| Terraform `google` provider | Terraform `aws` provider, or CDK |
