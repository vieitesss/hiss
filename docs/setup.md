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
