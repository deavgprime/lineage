# Decision log

Source: Plan and architecture, 31 Oct 2026 (PDF). Project renamed from Sentinel to Lineage.

## Agreed

| # | Decision | Reason |
| --- | --- | --- |
| 1 | Name: Lineage | "Sentinel" collides with Microsoft Sentinel and a KYB product named Sentinel Compliance Platform |
| 2 | Backend: Python 3.12, FastAPI, Pydantic; plan-and-execute loop written by hand | 71% of roles ask for production Python |
| 3 | Demo deploys on GCP: Cloud Run, Cloud SQL (Postgres + pgvector), Secret Manager, Terraform | The VM and gcloud project are already on GCP. Images in Artifact Registry; ingestion as a Cloud Scheduler job. AWS (ECS Fargate, RDS, Secrets Manager, CDK) kept as a reference mapping in the README |
| 4 | Bank install: same images, Helm chart on Kubernetes | Constraint: runs on the customer's own cluster |
| 5 | Retrieval: pgvector with Postgres full-text search, reranked by a local open model (was Cohere Rerank, changed by 0004) | One database to secure and audit, and no extra supplier. See [0004](decisions/0004-policy-corpus.md) |
| 6 | Access and privacy: Keycloak OIDC, Postgres row-level security, Presidio | Analysts see only assigned cases |
| 7 | Tracing: OpenTelemetry, exported over OTLP to Langfuse or the bank's collector; Jaeger for local viewing | One open standard, so the bank picks the backend. Spans carry no personal data |
| 8 | CI/CD: GitHub Actions (test, eval gate, build, deploy) | |
| 9 | Not adding: Temporal, LangChain, LlamaIndex, a separate vector database | Weight without payoff at about 12 hours a week |
| 10 | Customer: a bank operating in the UK and the UAE. Jurisdiction is configuration (lists, registry source, policy corpus) with a UK pack and a UAE pack | One agent core serves both teams, and a new jurisdiction is a new pack |
| 11 | Redaction happens only between the agent core and an external model. Known entities from tool results are replaced first, then Presidio catches the rest | Tools need real names, models must not see them. See [0001](decisions/0001-redaction.md) |
| 12 | Strong screening matches set a minimum rating in code: sanctions means high, PEP means at least medium. Weak matches are alerts for the analyst and do not change the rating | Ratings should follow facts, not unreviewed fuzzy matches. See [0002](decisions/0002-risk-rating.md) |
| 13 | Roles are analyst, MLRO and auditor, each limited to their packs. Analysts see only their assigned cases. Files drafted or rated high, or lowered at sign-off, need a second sign-off by a different MLRO, and only sign-off can make a file final. Enforced in the API and by Postgres row-level security | Need to know, senior approval for high risk, and no single layer to trust. See [0003](decisions/0003-access-model.md) |
| 14 | The policy corpus holds only what may be stored and quoted: the bank's own UK and UAE KYC policies and the Money Laundering Regulations 2017 under the Open Government Licence. FCA, JMLSG and CBUAE texts are referred to, not stored | Licences. See [0004](decisions/0004-policy-corpus.md) |

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

- Companies House covers UK companies only, and no open UAE registry exists. The 30 ground-truth
  companies are UK, UAE ownership cases rely on GLEIF parent links and analyst-supplied documents, and
  that limit is stated wherever results are reported.
- Data residency differs by jurisdiction. The regions for each pack are the bank's decision.
- OpenSanctions bulk data is CC BY-NC: fine for a portfolio demo, not for a commercial offering.
