# Lineage

[![CI](https://github.com/deavgprime/lineage/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/deavgprime/lineage/actions/workflows/ci.yml)
[![Licence](https://img.shields.io/badge/licence-Apache--2.0-blue.svg)](LICENSE)

Due-diligence drafting for corporate onboarding at a national bank in the UAE.
Given a company name or registration number, Lineage drafts a cited KYC file: the resolved entity,
the ownership chain to ultimate beneficial owners, sanctions and PEP hits, adverse media, and a risk
rating. An analyst approves or overrides it, and every step is logged.

Status: pre-alpha. The design is settled and the repository is set up. The code is being built in the
order shown in the [delivery plan](#delivery-plan).

Stack: Python 3.12 with FastAPI, a Next.js console, Postgres with pgvector, deployed on GCP (Cloud Run
and Cloud SQL, defined in Terraform). Data comes from OpenSanctions, UK Companies House and GLEIF.

Documents: [brief](docs/brief.md), [scope](docs/scoping.md), [decisions](docs/decisions.md),
[testing plan](docs/testing.md), [contributing](CONTRIBUTING.md).

## System architecture

Every model call is redacted first; every step is traced and audited. The agent core is the only
component that calls models, always through redaction.

![System architecture](docs/images/1-architecture.png)

## Agent run

Only an analyst can make a file final; uncited drafts never reach them.

![Agent run: request to approved file](docs/images/2-agent-run.png)

## Security and audit

Three controls a bank will test: access, data egress and tamper evidence.

![Access control, data egress and tamper evidence](docs/images/3-security-audit.png)

## Evals and CI/CD

A release that misses any eval gate never reaches production. Prompt changes go through the same gate as code.

![Pull request to production](docs/images/4-ci-cd.png)

## Deployment

The demo runs on GCP: Cloud Run services, Cloud SQL for PostgreSQL, Secret Manager, all defined in
Terraform. The same container images run as an in-house install for a bank; only the values file changes.

![Cloud demo on GCP and bank install on Kubernetes](docs/images/5-deployment-gcp.png)

### AWS equivalent

Kept for reference, since a customer may run on AWS. The mapping is one to one: Cloud Run becomes
ECS Fargate, Cloud SQL becomes RDS, Secret Manager becomes AWS Secrets Manager, Terraform becomes CDK.

![The same deployment on AWS](docs/images/6-deployment-aws.png)

## Delivery plan

About 12 hours a week from 2 November 2026; live URL on 20 December.

![Weekly delivery plan](docs/images/7-delivery-plan.png)

## Repository layout

```
apps/api/          FastAPI service
apps/console/      Next.js analyst console
packages/agent/    plan-and-execute core and tools
packages/evals/    datasets, harness, release gates
packages/mcp/      MCP server over the same tools
ingest/            bulk loaders for the three data sources
infra/terraform/   GCP infrastructure
infra/helm/        chart for installs on Kubernetes
docs/              brief, scope, decisions, testing plan
tests/             repository and cross-package tests
```

## Contributing

Work happens on short topic branches into `develop`, and `main` holds released code. Commits and pull
request titles follow Conventional Commits. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

Apache-2.0, see [LICENSE](LICENSE). The data sources keep their own terms. OpenSanctions bulk data is
licensed CC BY-NC.
