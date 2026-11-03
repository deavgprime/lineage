# Security and compliance

Lineage is built for a regulated bank. This page lists what is protected, how, and which standards the
design follows. It states plainly what exists today and what is planned.

Nothing here is a certification. Lineage has not been audited or attested against any standard. A bank
that adopts it runs its own assessment, and several items below can only be confirmed by that bank.

## Data handled

| Data | Class | Handling |
| --- | --- | --- |
| Sanctions, PEP, company registry and LEI records | Public | Loaded from open sources, with the source and load date stored |
| Cases, drafted files, analyst decisions | Confidential | Row-level security, only assigned analysts, encrypted at rest and in transit |
| Analyst identities | Personal | Held by the sign-in provider, referenced by ID in the audit log |
| Model prompts and responses | Confidential, may contain personal data | Redacted before any external call, or sent only to a self-hosted model |
| Audit log | Integrity critical | Append only and hash chained |

Lineage does not process cardholder data, account numbers or transaction data.

## Standards

Status values: **Designed** means the architecture and tests are shaped for it. **Planned** means it is
scheduled and not yet built. **Not applicable** explains why. **Bank to confirm** needs the bank's
legal or compliance team.

| Standard | Relevance | How Lineage addresses it | Status |
| --- | --- | --- | --- |
| PCI DSS v4.0.1 | Applies to systems that store, process or transmit cardholder data | Lineage handles none, so the standard does not apply. A redaction rule and an eval case will check that card numbers are never forwarded. A deployment that did handle card data would put that environment in scope | Not applicable |
| ISO/IEC 27001:2022 | Information security management | Access control, logging, secure development, supplier and change management follow the Annex A themes. Certification belongs to an organisation, not a codebase | Designed |
| SOC 2 (security, confidentiality, processing integrity) | Assurance report for service providers | Controls below map to these criteria. No attestation exists | Designed |
| NIST SP 800-218 (SSDF) | Secure software development | Reviewed pull requests, pinned dependencies, secret, dependency, image and workflow scanning, tests as a merge gate | Partly in place |
| OWASP ASVS and OWASP Top 10 for LLM applications | Application and model security | Prompt injection, excessive agency, insecure output handling and data leakage each have a control and a test | Planned |
| NIST AI RMF and ISO/IEC 42001 | Governance of AI systems | Human sign-off, measured release gates, full logging and documented limits | Designed |
| Model risk management (PRA SS1/23 in the UK, and SR 11-7 style practice) | Validation and monitoring of models | Evals with fixed datasets and eight runs per case, baselines recorded, drift visible in tracing | Designed |
| UK GDPR and Data Protection Act 2018 | Personal data protection in the UK | Data minimisation, redaction, purpose limits and retention. Lawful basis and the data protection impact assessment are the bank's | Bank to confirm |
| UK Money Laundering Regulations 2017, JMLSG guidance, FCA Financial Crime Guide | The UK rules the product serves: due diligence, PEPs, beneficial ownership, record keeping | Ownership tracing from the people with significant control register, cited evidence, retention and audit traceability | Designed |
| UK Sanctions List (FCDO) | The list a UK bank must screen against | Screened directly, with the UN, EU and US lists | Designed |
| FCA and PRA operational resilience, SM&CR | Outsourcing, resilience and named accountability | Human sign-off keeps the decision with the accountable person. Resilience testing is the bank's | Bank to confirm |
| NCSC Cloud Security Principles | UK baseline for cloud services | Mapped to the controls below | Designed |
| UAE Federal Decree-Law No. 45 of 2021 (PDPL) | Personal data protection in the UAE | Data minimisation, redaction, purpose limits and retention rules. Lawful basis and cross-border transfer rules are the bank's | Bank to confirm |
| DIFC Data Protection Law 2020, ADGM Data Protection Regulations 2021 | Data protection if the bank is licensed there | Same controls as above | Bank to confirm |
| CBUAE AML/CFT guidance, Decree Law No. 10 of 2025, FATF Recommendations 10, 11, 24 and 25, Wolfsberg CDD principles | The business rules the product serves: customer due diligence, beneficial ownership, record keeping | Ownership tracing through layers, cited evidence, retention and audit traceability | Designed |
| UAE Information Assurance Regulation | National security baseline | Mapped to the controls below once the bank states which entities fall in scope | Bank to confirm |
| GDPR, EU AI Act, DORA | Only if deployed for EU entities | Not assessed | Not assessed |

## Threats and controls

| Threat | Control | Status |
| --- | --- | --- |
| An analyst sees a case that is not theirs | OIDC sign-in, roles, Postgres row-level security as well as API checks. See [decision 0003](decisions/0003-access-model.md) | Sign-in and row-level security in place |
| Text in adverse media tells the agent to change behaviour | Fetched text is treated as data, tools come from a fixed list, no tool can finalise a file, and a safety eval must show zero failures | Planned |
| A file is finalised without an analyst | Only the analyst role can set the final state, enforced in the database and covered by a test | Planned |
| Personal data reaches an external model | Redaction before every external call, a self-hosted option, and an egress allow-list | Planned |
| The audit log is edited | Each row stores the hash of the previous row, the application role cannot update or delete, and a job verifies the chain | Planned |
| A claim has no support | Structured claims with source ID and quote, and a check that the quote exists in the cited record | Planned |
| Secrets leak | Keys in Secret Manager, none in the repository, secret scanning in pre-commit and CI | In place for scanning |
| A dependency or action is compromised | Actions pinned to commit SHAs, lockfile, a 7 day Dependabot cooldown, workflow auditing, pinned base images, an SBOM and build provenance for images | Partly in place |
| A workflow is abused to run attacker code | Least privilege permissions, no pull request text in scripts, no persisted credentials, all checked by tests | In place |
| Source data is stale or altered | Checksums and load dates stored, shown in every file | Planned |
| Cost or load abuse | Rate limits and a budget per case | Planned |

## Secure development in this repository

- `main` and `develop` are protected. Changes arrive by pull request with required checks and a code
  owner review.
- Commits and titles follow a fixed format, so every change is traceable to a reason.
- Pre-commit and CI run secret scanning (gitleaks), workflow auditing (zizmor), linting, type checks
  and tests.
- A security workflow runs inside `CI gate` on every pull request and push, and on its own every
  Monday so new advisories against unchanged code still show up. It checks:
  - every commit in the history for secrets (gitleaks), and the current files with a second
    scanner (Trivy)
  - every package in the lock file against the PyPI advisory database (pip-audit)
  - the API image for fixable high and critical vulnerabilities, and the Dockerfile and compose
    files for insecure configuration (Trivy)
  - the Python code with ruff's security rules. Each reviewed exception carries its reason next to
    it, and no code relies on `assert` for checks.
- Scanner images are pinned by digest, like the actions.
- Traces leave the bank's audit boundary for a tracing tool, so they carry steps, counts, timings
  and case ids only. Agent spans pass through an allowlist of attributes. Request spans drop query
  strings, headers and client IP addresses, and health checks are not traced. Tests run a file with
  a name, a passport and an address in its inputs and check none of them reaches a span.
- The audit log is a hash chain. `python -m lineage_db.audit` checks every row and link in the
  whole log, and CI runs it after the integration tests. An MLRO or auditor can export a case's trail
  as JSON from `GET /cases/{id}/audit/export`, and `scripts/verify_audit_export.py` checks it with
  nothing but Python. Each export is itself recorded in the trail.
- Tests fail the build if a workflow uses an action that is not pinned to a commit SHA, lacks a
  permissions block or a timeout, or interpolates pull request text into a script.
- Dependabot proposes updates weekly with a cooldown.
- Vulnerabilities are reported privately, see [SECURITY.md](../SECURITY.md).

## Operations (targets for the first deployment)

- TLS everywhere, encryption at rest, customer-managed keys where the bank requires them.
- Backups with a tested restore.
- Retention set by the bank, with at least five years after the relationship ends, as the UK
  Money Laundering Regulations 2017 and FATF Recommendation 11 require.
- Centralised logs and alerts, and an incident process with named owners.
- Fix targets: critical vulnerabilities in 7 days, high in 30 days.

## Before a bank uses this in production

- An independent penetration test and a data protection impact assessment.
- The bank's vendor and model risk reviews.
- A commercial licence for OpenSanctions data. The free bulk data is licensed for non-commercial use
  only, which is why this repository uses it for evaluation and demonstration.
- A decision on where models run and which providers are approved.
