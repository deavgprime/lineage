# Taking Lineage into a bank

This is how a forward-deployed engineer takes Lineage from a first meeting with a bank's financial
crime team to a signed-off pilot and a handover. It assumes the bank's question is the one Lineage
answers: can corporate onboarding files be drafted faster without weakening the evidence behind
them?

## 1. Discovery (week 1)

Meet the MLRO, two or three onboarding analysts, the head of financial crime technology and someone
from information security. Watch an analyst build a real file before proposing anything.

Questions to answer:

- **Volume and pain.** How many corporate files a month, by jurisdiction? How long does one take,
  and where does the time go: registry lookups, screening triage, writing the narrative, rework
  after QA?
- **Policy.** Which written procedure do analysts follow? Who owns it, and how often does it change?
  What does QA reject most often?
- **Screening.** Which lists and which screening vendor? How are alerts cleared today, and where is
  the clearance recorded?
- **Decisions.** Who signs off which ratings? Is there a second sign-off for high risk? What must
  the file show a regulator?
- **Systems.** Where do files live today: a case management tool, a CRM, shared drives? What
  identity provider, what Kubernetes or cloud estate, what logging and SIEM?
- **Constraints.** Data residency per jurisdiction, approved model providers, whether data may
  leave the bank's network, and the change approval process for a new system.

Output: a one-page problem statement with today's time per file and QA rejection rate. These are
the baseline the pilot is measured against.

## 2. Configure the jurisdiction pack (weeks 2 to 3)

A pack is configuration, not code (decision 10). For each jurisdiction in scope:

| Setting | Where | Bank input |
| --- | --- | --- |
| Sanctions lists | `ingest/lineage_ingest/packs.py` | The lists the bank screens against, mapped to OpenSanctions datasets, or the bank's own vendor feed |
| PEP scope | Same file | Which countries' PEPs count for this pack |
| Registry | Agent plan per pack | Companies House for the UK; GLEIF and analyst-supplied documents where no open registry exists |
| Policy corpus | `policies/` and `lineage_ingest.policy` | The bank's own KYC procedure, plus any regulation the bank is licensed to store (decision 0004) |
| Roles and packs | The identity provider | Which analysts, MLROs and auditors belong to which pack (decision 0003) |
| Rating rules | `lineage_agent.agent` | Confirm the minimum ratings from strong matches (decision 0002) match the bank's risk methodology |

Load the bank's policy, then re-run the policy eval with twenty or so questions the bank's QA team
writes, with the paragraphs that answer them. Their questions, not ours, set the bar.

## 3. Security review (weeks 2 to 4, in parallel)

Bring the evidence, not a slide. Each control below is already in the repository and can be shown
working:

| Control the bank will ask about | Evidence |
| --- | --- |
| Personal data never reaches the model | Redaction in `lineage_agent.redaction` and `lineage_agent.pii`; the redaction eval in CI; the safety eval |
| Model output cannot invent facts | Every claim quotes its source and is checked in code; citation and faithfulness results in the README |
| Prompt injection in adverse media | 320 safety runs with no failure; flagged instructions shown to the analyst |
| Only assigned analysts see a case | Postgres row-level security plus API checks; integration and browser tests |
| No file is final without people | Sign-off rules enforced by the database (migration 0005); four-eyes on high risk |
| Tamper-evident record | Hash-chained audit log; `python -m lineage_db.audit`; exports checkable with plain Python |
| Supply chain | Pinned actions and images, Dependabot, secret, dependency and image scanning, SBOM and provenance on images |
| Observability without data leakage | Traces carry ids, counts and timings only; tested |
| Deployment hardening | Helm chart: non-root, read-only filesystem, no capabilities, network policy; Terraform: private database, flow logs, pgaudit |

The full mapping to UK and UAE rules and standards is in [security.md](security.md). Agree with the
bank which items are theirs: penetration testing, model provider due diligence, DPIA sign-off and
data residency choices.

## 4. Pilot (weeks 4 to 8)

- **Scope.** One jurisdiction, one team of three to five analysts, new corporate onboarding only.
  Lineage drafts; analysts review, edit through overrides, and sign off as today. Nothing changes in
  who decides.
- **Shadow first.** For two weeks, analysts build files the usual way and compare with Lineage's
  draft for the same company. Disagreements go to a shared log, and each one is a test case.
- **Then assist.** Analysts start from the draft. QA reviews every pilot file as normal.
- **Weekly review** with the MLRO: measures below, the disagreement log, and any safety flag.

Success measures, agreed before the pilot starts:

| Measure | Target | Source |
| --- | --- | --- |
| Analyst time per file | At least 40% lower than the discovery baseline | Case timestamps |
| QA rejection rate | No higher than the baseline | QA records |
| Claims citing a source | 100% | Citation check on every draft |
| Strong sanctions or PEP matches missed | 0 | Comparison with the bank's screening vendor |
| Files finalised without sign-off | 0 | Database rule and audit log |
| Personal data sent to the model | 0 | Redaction leak check and audit |
| p95 time to a draft | Under 120 seconds | Traces |

## 5. Handover (weeks 8 to 10)

- The bank's platform team runs the Helm chart in its own cluster, from its own image mirror, with
  its own secrets and identity provider ([deployment guide](deployment.md)).
- The bank's financial crime team owns the policy corpus and the labelled eval sets. Changing either
  is a reviewed change that re-runs the evals, the same as a code change.
- The MLRO owns the rating rules and the sign-off rules.
- Releases are cut through a reviewed release pull request and a version tag. Every release runs the
  full test suite and publishes scanned images with an SBOM.
- Agree the run book: daily ingestion, audit chain check, key rotation, and who is called when the
  model provider is unavailable. Drafting stops, and analysts work as they did before.

## What to watch for

- **Scope creep into decisions.** Lineage drafts and cites. If a stakeholder asks it to approve or
  reject customers, the answer is no: sign-off stays with named people.
- **Policy drift.** If the bank's procedure changes and the corpus does not, answers will cite an
  outdated rule. Make the corpus part of the policy change process.
- **Screening disagreements.** Weak matches are alerts, not ratings. If the bank's methodology
  differs, change the rule and the test together, and record the decision.
