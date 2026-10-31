# Lineage brief

**Customer:** a bank operating in the UK and the UAE, with a corporate onboarding team in each, sponsored by the MLRO.

**Ask:** from a company name or registration number, draft a due-diligence file with a resolved
entity, ownership chain to UBOs, sanctions/PEP hits for every person and entity in the chain,
adverse-media notes and a risk rating with reasons. Every statement cites its source. An analyst
approves or overrides; everything is logged.

## Release gates
| Measure | Target |
| --- | --- |
| Claims citing a source record | 100% |
| Sanctions/PEP recall, 200 labelled names (incl. Arabic/Latin variants) | >= 98%, precision reported |
| Ownership chain vs ground truth, 30 UK companies | >= 90% exact |
| Faithfulness (judge-scored) | >= 95% |
| Safety: prompt injection in adverse media, skip-sign-off requests, PII extraction | 0 failures |
| Time per file, p95 | < 120 s |
| Files finalised without sign-off / tool calls missing from audit log | 0 / 0 |

Each eval case runs 8 times. The harness runs in CI and blocks failing releases.

## Decisions
- Backend: Python/FastAPI (matches the production-Python requirement in most FDE roles).
- Deploy: GCP (Cloud Run + Cloud SQL, Terraform); Helm chart for on-prem.

## Constraints
- Analysts see only their assigned cases.
- Personal data is redacted before any external model call.
- The model provider can be swapped.
- The app can run on the customer's own Kubernetes cluster.

Full decision log: [decisions.md](decisions.md). Scope: [scoping.md](scoping.md).
