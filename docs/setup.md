# Repository setup

## Continuous integration

The repository has one GitHub Actions workflow, `.github/workflows/ci.yml`. It
runs for pull requests and for pushes to `main`. Every job uses GitHub-hosted
`ubuntu-latest` runners. A normal full run should complete in roughly under
three minutes; if it grows past that, treat it as a regression — a slow
pipeline is a bad teaching artifact.

The workflow first detects changed areas, then runs the relevant checks:

- Python linting uses Ruff 0.9.10 (`ruff check app cli` and
  `ruff format --check app cli`).
- `lint-docker` runs Hadolint against `app/Dockerfile`.
- `test-app` applies the Alembic migrations and runs the Flask tests against an
  ephemeral `postgres:17-alpine` service container.
- `test-cli` runs the CLI tests without a service container.
- `build` runs `docker build -f app/Dockerfile app/` after the app tests. It
  validates the image only: it does not log in to a registry, push an image, or
  deploy anything.

The `changes` job uses path filters. An app change runs the app checks and an
app image build; a CLI-only change runs the Python lint and CLI tests but skips
app tests, Dockerfile lint, and the image build. Changes to shared files such
as `pytest.ini`, `ruff.toml`, or the workflow run both test suites. A docs-only
change can leave package jobs skipped; GitHub reports skipped required jobs as
successful, so this does not bypass a failing check on a relevant change.

## Protecting `main`

Branch protection is intentionally a manual GitHub repository setting, not
another automation step. After the first workflow run makes the checks
available:

1. Open **Settings → Branches** (or **Rules → Rulesets**) in the repository.
2. Add a rule/ruleset for `main` and require pull requests before merging.
3. Require status checks to pass before merging. Select the checks shown as
   `CI / Detect changes`, `CI / Lint Python`, `CI / Lint Dockerfile`,
   `CI / Test app`, `CI / Test CLI`, and `CI / Build app image`.
4. Save the rule. Keep the rule enabled for administrators if the repository is
   being used as the CI/CD lesson's merge gate.

A red required check blocks the merge; a green (or path-filtered skipped)
check is the permission to proceed. Self-hosted runners remain reserved for
deployment work in the later deployment specification.

## Checking a run

The worker does not push from the local checkout. After the orchestrator pushes
the branch, find and watch the real run with bounded commands:

```sh
gh run list --workflow ci.yml --limit 5
gh run watch <run-id> --exit-status
gh run view <run-id> --log-failed
```

`gh workflow view ci.yml` can also be used after the workflow exists on GitHub.
There is deliberately no actionlint gate, coverage gate, mypy job, image
publication, or deployment job in this workflow.

## Continuous delivery

Three CD workflows deploy every accepted artifact to your own machine and a
fourth lets you roll back. All deploys run on a `[self-hosted]` runner that
must have Docker Compose and `curl`/`jq` available; `linux` is not part of
the runner label so macOS runners work as well.

| Trigger | Workflow | Image tag | Environment | Gate |
| --- | --- | --- | --- | --- |
| `push` to `main` | `cd-dev.yml` | 8-char `GITHUB_SHA` | `dev` (`:8001`) | auto |
| `push` tag `X.Y.Z-snapshot` | `cd-staging.yml` | `X.Y.Z-snapshot` | `staging` (`:8002`) | auto |
| `push` tag `X.Y.Z` | `cd-prod.yml` | `X.Y.Z` | `prod` (`:8003`) | Environment approval |

Tags must not include a leading `v` and `pull_request` never deploys — each
deploy workflow comments this safety invariant at the top. Builds use
`app/Dockerfile` and push to `ghcr.io/vieitesss/hiss:<tag>` via the reusable
`.github/workflows/_build-push.yml` (`workflow_call` input `tag`,
`packages: write`, `GITHUB_TOKEN` login). Deploys run
`POSTGRES_PASSWORD=${{ secrets.POSTGRES_PASSWORD }} IMAGE_TAG=<tag>
APP_VERSION=<tag> docker compose -f deploy/compose.yml --env-file
deploy/<env>.env -p hiss-<env> pull && up -d` and then a smoke job curls
`/healthz`, `/readyz`, and asserts `/version` (`{"version": "<tag>"}`) equals
the deployed tag.

### Tag mutability

- `X.Y.Z-snapshot` is a **moving tag** — you may delete and re-push it while
hardening a release. The trade-off is that staging history is not strictly
immutable.
- `X.Y.Z` is **immutable** once pushed; never move or re-push it.

### Prerequisites

1. **Self-hosted runner** registered with label `self-hosted` on the host that
   will run the three Environments (Docker Engine + Compose v2 required).
2. **GitHub Environments** `dev`, `staging`, `prod` created for the repo; each
holds a secret `POSTGRES_PASSWORD` (never committed). `prod` has a required
   reviewer (you) so the deploy job pauses for approval — the
   Continuous Delivery vs Deployment distinction.
3. **GHCR package `ghcr.io/vieitesss/hiss` set to public** so the runner can
   `pull` without extra credentials; pushes use the workflow's
   `GITHUB_TOKEN` with `packages: write`.

### Rollback

`rollback.yml` is `workflow_dispatch`-only (no build) — it redeploys any
previous tag to any Environment. Prod rollbacks still require the `prod`
Environment approval.

- **UI:** Actions → Rollback → Run workflow → choose `environment` (`dev` |
  `staging` | `prod`) and `tag`.
- **CLI:**

```sh
gh workflow run rollback.yml -f environment=prod -f tag=0.1.0
# or for staging:
gh workflow run rollback.yml -f environment=staging -f tag=0.1.0-snapshot
gh run list --workflow rollback.yml --limit 5
gh run view <run-id> --log-failed
```

> TODO: the full release ceremony, promotion checklist, and rollback runbook
> will live in `docs/release-process.md` (issue #7). This section is only a
discovery pointer until that doc lands.
