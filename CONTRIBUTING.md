# Contributing to Lineage

This guide covers how work moves from an idea to a release. The rules are enforced by branch
rules and CI, so a pull request that breaks them cannot be merged.

## Branches

| Branch | Purpose | Who updates it |
| --- | --- | --- |
| `main` | Released code. Every commit on it is deployable and every release is tagged `vX.Y.Z`. | Pull requests from `develop`, `release/*` or `hotfix/*` only |
| `develop` | Integration branch. The next release is built here. | Pull requests from topic branches |
| `<type>/<description>` | One change, for example `feat/screening-tool` or `fix/audit-hash-order`. | The author |
| `release/<version>` | Optional stabilisation of a release, for example `release/0.2.0`. | Fixes only, no new features |
| `hotfix/<description>` | An urgent fix to what is on `main`. Merged to `main`, then back to `develop`. | The author |

Nobody pushes to `main` or `develop` directly. Topic branches are short lived, branch from `develop`
and are deleted after merge.

Branch names use lowercase letters, digits, `.`, `_` and `-`. The `<type>` is one of the commit types
below.

## Commits

Commits follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

| Type | Use for |
| --- | --- |
| `feat` | A new capability |
| `fix` | A bug fix |
| `perf` | A performance change |
| `refactor` | A change that alters neither behaviour nor performance |
| `docs` | Documentation only |
| `test` | Adding or correcting tests |
| `build` | Dependencies and packaging |
| `ci` | Workflows and automation |
| `chore` | Anything else that does not touch the product |
| `revert` | Undoing an earlier commit |
| `style` | Formatting only |

Scopes: `api`, `console`, `agent`, `evals`, `mcp`, `ingest`, `infra`, `docs`, `deps`, `ci`, `release`.

The pull request title is the line that appears in the changelog, so write it as the outcome for a
user or maintainer: `fix(ingest): registry lookups no longer fail on company numbers with leading zeros`,
not `fix: update parser`. Pick the type deliberately, because `feat` and `fix` decide the next version.

Rules for the message:

- The subject is in the imperative mood, starts with a lowercase letter, has no full stop and is at
  most 72 characters. Write "add audit log", not "added audit log".
- The body says why the change is needed. The diff already says what changed.
- Mark a breaking change with `!` after the type, for example `feat(api)!:`, and add a
  `BREAKING CHANGE:` paragraph in the footer.
- Reference issues in the footer: `Closes #12`.
- Each commit is one logical step that builds and passes tests on its own.

## Pull requests

1. Branch from `develop`.
2. Make small commits and push.
3. Open a pull request into `develop`. The title is a Conventional Commit, because the pull request
   is squash-merged and the title becomes the commit message.
4. Fill in the template. Link the issue.
5. Wait for the required checks and a review from a code owner.
6. Squash and merge. The branch is deleted.

Keep pull requests under about 400 changed lines where possible. Split larger work into a
sequence of pull requests that each leave `develop` working.

### Merge methods

| Into | Method | Reason |
| --- | --- | --- |
| `develop` | Squash | One commit per change, a linear history |
| `main` | Merge commit | Keeps the individual commits and marks each release |

### Required checks

| Check | What it verifies |
| --- | --- |
| `CI gate` | Pre-commit, lint, type check and tests on Python 3.12 and 3.13 |
| `Lint PR title` | The title is a valid Conventional Commit |
| `Branch policy` | The source branch is allowed for the target branch |

Branches must be up to date with their target before merging. The repository owner can bypass the
review requirement on a pull request, because a single maintainer cannot approve their own work. The
checks cannot be bypassed.

## Releases

1. Open a pull request from `develop` (or a `release/x.y.z` branch) into `main`.
2. Merge it with a merge commit once all checks pass.
3. Tag the merge commit `vX.Y.Z` and publish a GitHub release with notes grouped by commit type.
4. Versions follow [Semantic Versioning](https://semver.org/). Before 1.0.0, a breaking change raises
   the minor version.

A hotfix branches from `main`, is merged into `main` through a pull request, tagged as a patch release
and then merged back into `develop`.

## Testing

Read the [testing plan](docs/testing.md). In short: every bug fix starts with a failing test, every
new behaviour ships with tests, and model behaviour is measured by the eval harness against the
release gates in the [brief](docs/brief.md).

## Local setup

Requires Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
uv run pytest -m "not eval"
```

The hooks check formatting, lint, the commit message format and the writing rules below.

## Writing rules

These apply to code comments, documentation, commit messages and pull request text.

- Plain, specific sentences. Say what the thing does and why.
- No em-dashes. Use a full stop, a comma or a colon.
- No filler or marketing words, for example "robust", "seamless", "leverage" or "cutting-edge".
- Spell it "arbiter", not "arbitrator".
- Documentation describes what is true now. Planned work lives in issues and milestones.
- Do not commit anything you could not explain line by line, whoever or whatever wrote it.

## Security

Do not report vulnerabilities in public issues. See [SECURITY.md](SECURITY.md).
