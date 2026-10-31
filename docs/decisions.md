# Decision log

Source: Plan and architecture, 31 Oct 2026 (PDF). Project renamed from Sentinel to Lineage.

## Agreed

| # | Decision | Reason |
| --- | --- | --- |
| 1 | Name: Lineage | "Sentinel" collides with Microsoft Sentinel and a KYB product named Sentinel Compliance Platform |
| 2 | Backend: Python 3.12, FastAPI, Pydantic; plan-and-execute loop written by hand | 71% of roles ask for production Python |
| 3 | Demo deploys on GCP: Cloud Run, Cloud SQL (Postgres + pgvector), Secret Manager, Terraform | The VM and gcloud project are already on GCP. Images in Artifact Registry; ingestion as a Cloud Scheduler job. AWS (ECS Fargate, RDS, Secrets Manager, CDK) kept as a reference mapping in the README |
| 4 | Bank install: same images, Helm chart on Kubernetes | Constraint: runs on the customer's own cluster |
| 5 | Retrieval: pgvector + Cohere Rerank | One database to secure and audit |
| 6 | Access and privacy: Keycloak OIDC, Postgres row-level security, Presidio | Analysts see only assigned cases |
| 7 | Tracing: OpenTelemetry, Langfuse, Grafana | |
| 8 | CI/CD: GitHub Actions (test, eval gate, build, deploy) | |
| 9 | Not adding: Temporal, LangChain, LlamaIndex, a separate vector database | Weight without payoff at about 12 hours a week |

## Proposed, awaiting decision

| Area | Change |
| --- | --- |
| Structured outputs | Pydantic schemas for every drafted claim: claim, source ID, quote |
| Model access | Own thin provider interface with native Anthropic and Cohere adapters; LiteLLM only for OpenAI and self-hosted |
| Citation check | After drafting, verify each quoted passage exists in the cited record |
| Agent tooling | Ship the tools as an MCP server plus an installable agent skill |
| Second eval library | Inspect, run once on the same cases, for comparison in the README |
| Safety set | Hand-built Arabic and English adverse-media texts with injected instructions; garak as a supplement |

## Open design risks

- Presidio redaction versus the task: names are the input to screening. Redaction must apply to
  model prompts only, using stable placeholders mapped back after the call, and screening and registry
  tools must run on unredacted data inside the trust boundary.
- Companies House covers UK companies only. The national bank's ownership chains cannot be
  tested on UAE entities with free data; the 30 ground-truth companies are UK.
- OpenSanctions bulk data is CC BY-NC: fine for a portfolio demo, not for a commercial offering.
