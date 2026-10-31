# Testing plan

This is the plan for how Lineage is tested and what must pass before code moves between branches.
It applies to every change. The release gates for model behaviour live in [brief.md](brief.md).

## Test levels

| Level | What it checks | Needs | Marker | Runs |
| --- | --- | --- | --- | --- |
| Unit | One function or class, no I/O | Nothing | `unit` | Every push and PR |
| Integration | Postgres queries, row-level security, the audit log, tool wrappers against recorded API responses | Postgres in a container | `integration` | Every PR |
| Contract | Our parsers against saved responses from OpenSanctions, Companies House and GLEIF | Saved fixtures | `integration` | Every PR |
| Eval | Model behaviour on labelled data, 8 runs per case | Model access | `eval` | Every PR that touches `packages/` or prompts, and nightly |
| Safety | Prompt injection, skipped sign-off, personal data extraction | Model access | `eval` | Same as eval |
| End to end | Console to API to agent to database on a seeded case | Docker Compose | none | Before a release |
| Performance | p95 time per file under 120 seconds | Model access | `eval` | Nightly and before a release |

Tests are chosen from the cheapest level that can catch the fault. A bug in parsing is a unit test, not an eval.

## Rules

1. Every bug fix starts with a failing test that reproduces it.
2. Every new behaviour comes with tests in the same pull request.
3. Unit tests make no network calls and need no database. They run in under a minute in total.
4. External APIs are never called in CI except by the nightly job. Everything else uses saved fixtures
   kept under `tests/fixtures/` with a note of where and when each was captured.
5. No real personal data in the repository. Fixtures use public records or invented people.
6. Tests are deterministic. Time, randomness and ordering are controlled, and model calls in unit
   tests use a stub.
7. A flaky test is fixed or removed within two working days. Until then it is skipped with a link to its
   issue and never retried silently.

## Coverage

Coverage is measured for `packages/` and `apps/api/` once they hold code.

- Line coverage must stay at or above 85 percent overall.
- Changed lines must be covered at 90 percent or more.
- Coverage is a guard against untested code and not a target. A test that asserts nothing does not count.

## Release gates (model behaviour)

| Measure | Target |
| --- | --- |
| Claims citing a source record | 100% |
| Sanctions and PEP recall on 200 labelled names | At least 98% |
| Ownership chain on 30 UK companies | At least 90% exact |
| Faithfulness, judge scored | At least 95% |
| Safety failures | 0 |
| p95 time per file | Under 120 seconds |
| Files finalised without analyst sign-off | 0 |
| Tool calls missing from the audit log | 0 |

Every eval case runs 8 times. A gate passes only if the result holds across all runs. Scores are posted
on the pull request and recorded in `packages/evals/baselines/`. A prompt change is treated as a code
change and goes through the same gates.

## Where tests run

| Stage | Checks |
| --- | --- |
| Local, before commit | Pre-commit hooks: formatting, lint, commit message format, no em-dashes |
| Pull request into `develop` | Pre-commit, lint, type check, unit and integration tests on Python 3.12 and 3.13, eval harness when relevant |
| Pull request into `main` | Everything above, plus end to end tests |
| Nightly | Full eval suite, performance, contract tests against the live APIs |

All required checks are summarised by one job named `CI gate`, which is the status the branch rules
require. See [CONTRIBUTING.md](../CONTRIBUTING.md) for the branch rules.

## Commands

```bash
uv sync --frozen
uv run pytest -m unit
uv run pytest -m integration
uv run ruff check . && uv run ruff format --check .
uv run mypy tests
```

## Test data

| Dataset | Size | Owner | Location |
| --- | --- | --- | --- |
| Labelled screening names | 200 | `packages/evals` | `packages/evals/datasets/screening.jsonl` |
| Ownership ground truth | 30 UK companies | `packages/evals` | `packages/evals/datasets/ownership.jsonl` |
| Adverse media with injected instructions | To be set | `packages/evals` | `packages/evals/datasets/safety.jsonl` |

Datasets are versioned with the code. A change to a label is reviewed like a change to code, because it
moves the baseline.
