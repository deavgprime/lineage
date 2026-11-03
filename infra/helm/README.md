# Helm chart

Installs Lineage on a bank's own Kubernetes cluster (decision 4). The bank provides Postgres 17 with
pgvector, its identity provider and a Secret named by `existingSecret` holding `DATABASE_URL`,
`SESSION_SECRET` and, for live drafting, `ANTHROPIC_API_KEY`. The chart writes no secrets.

The chart deploys:

- the API and the console
- a migration job that runs before every install and upgrade
- an ingestion CronJob for the pinned lists and the policy corpus

Pods run as numeric non-root users on a read-only root filesystem, with no capabilities, the
runtime's default seccomp profile and no service account token. Network policy denies all ingress
except to the console from `networkPolicy.ingressFrom`, and to the API from the console.

Each release publishes the chart, and the `api` and `console` images it installs, to GitHub Packages.
The images carry an SBOM and build provenance, and are scanned before they are pushed.

```bash
helm install lineage oci://ghcr.io/deavgprime/lineage/charts/lineage --version 0.7.0 \
  --set oidc.issuer=https://sso.bank.example/realms/lineage \
  --set consoleUrl=https://lineage.bank.example \
  --set existingSecret=lineage
```

The values schema refuses an install without an issuer and a console address.
`tests/helm/kind-test.sh` installs the chart on a local kind cluster and checks the migration job,
readiness, and that only the console can reach the API. CI runs it on every pull request.
