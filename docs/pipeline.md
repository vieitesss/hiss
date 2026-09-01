# Pipeline

Este documento describe el pipeline completo del repositorio: cómo
se verifica cada cambio, cómo se construye y publica la imagen y cómo
esa misma imagen se despliega en `dev`, `staging` y `prod`. Es la
referencia canónica para RA1 y RA2 — si entiendes este fichero,
entiendes el sistema de entrega.

> Prerrequisito: tener el runner autoalojado y los Environments
> configurados. Ver [`docs/setup.md`](setup.md).

## Vista general

El repo separa claramente verificación y entrega:

- **CI** (`ci.yml`) corre en `ubuntu-latest` hospedado por GitHub y nunca
  despliega. Se ejecuta en `pull_request` y en `push` a `main`.
- **CD** (`cd-dev.yml`, `cd-staging.yml`, `cd-prod.yml`, `rollback.yml`)
  construye la imagen una vez y la despliega en tu máquina vía runner
  `self-hosted`. El workflow reutilizable `_build-push.yml` centraliza el
  `build` y `push`. Ningún `cd-*.yml` despliega si CI no está en verde
  para ese commit: `cd-dev.yml` se dispara con `workflow_run` cuando CI
  termina con éxito en `main`; `cd-staging.yml` y `cd-prod.yml` empiezan
  por un job `ci-gate`.

Toda imagen se publica en `ghcr.io/vieitesss/hiss:<tag>` y se despliega con
el mismo `deploy/compose.yml` cambiando solo `--env-file`. El tag de imagen
y `APP_VERSION` siempre coinciden — el artefacto es inmutable.

## CI — `.github/workflows/ci.yml`

`ci.yml` es el único workflow que responde a `pull_request`. Su objetivo
es dar feedback rápido sin tocar ningún entorno.

```yaml
on:
  pull_request:
  push:
    branches: [main]
```

Propiedades clave:

- `permissions: contents: read, pull-requests: read` — permisos mínimos.
- `concurrency: group: ci-... / cancel-in-progress: para PR` — cancela
  ejecuciones obsoletas de la misma rama.
- Todos los jobs en `ubuntu-latest` con `timeout-minutes` acotado. Una
  ejecución normal termina en menos de tres minutos.

### Jobs

| Job | Cuándo corre | Qué hace |
| --- | --- | --- |
| `changes` | siempre | `dorny/paths-filter@v3` clasifica el diff en `app`, `cli` y `shared` (`pytest.ini`, `ruff.toml`, `.github/workflows/ci.yml`). Exporta `outputs.app/cli/shared`. |
| `lint` | `app`/`cli`/`shared` | `setup-python@v5` con Python 3.13 y caché de `app/requirements.txt` + `cli/requirements.txt`; `pip install ruff==0.9.10`; `ruff check app cli` y `ruff format --check app cli`. |
| `lint-docker` | `app` | `docker run --rm -i hadolint/hadolint:v2.12.0-alpine < app/Dockerfile`. |
| `test-app` | `app`/`shared` | Servicio efímero `postgres:17-alpine` (`POSTGRES_DB=hiss_test`, `healthcheck pg_isready`), `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/hiss_test`, `alembic -c app/alembic.ini upgrade head`, `pytest app/tests`. |
| `test-cli` | `cli`/`shared` | Sin servicio; `pip install -r cli/requirements.txt` + `pip install -e cli`; `pytest cli/tests`. |
| `build` | `app` y `test-app` ok | `docker build -f app/Dockerfile app/` — solo valida que la imagen construye, sin `login` ni `push`. |

El filtro de rutas evita trabajo inútil: un cambio solo en `cli/` no
dispara `test-app` ni `lint-docker`; un cambio solo en documentación deja
jobs saltados que GitHub reporta como éxitos para no bloquear el merge. Los
checks requeridos de `main` incluyen los seis nombres `CI / Detect changes`,
`CI / Lint Python`, `CI / Lint Dockerfile`, `CI / Test app`, `CI / Test CLI`
y `CI / Build app image` (ver `docs/setup.md`).

### Revisar una ejecución de CI

```sh
gh run list --workflow ci.yml --limit 5
gh run watch <run-id> --exit-status
gh run view <run-id> --log-failed
```

## CD — construcción, publicación y despliegue

Tres workflows despliegan automáticamente según el trigger y uno permite
volver atrás manualmente. Todos comparten el mismo patrón:

```
prepare (calcula tag) → build (reutilizable) → deploy (self-hosted) → smoke-test (self-hosted)
```

### Tabla de triggers

| Disparador | Workflow | Tag de imagen | Environment | Puerto | Puerta |
| --- | --- | --- | --- | --- | --- |
| CI en verde tras `push` a `main` | `cd-dev.yml` | `head_sha` truncado a 8 caracteres | `dev` | `8001` | CI debe ser `success` |
| `push` de tag `X.Y.Z-snapshot` | `cd-staging.yml` | `X.Y.Z-snapshot` | `staging` | `8002` | job `ci-gate` + automático |
| `push` de tag `X.Y.Z` | `cd-prod.yml` | `X.Y.Z` | `prod` | `8003` | job `ci-gate` + aprobación de Environment |
| `workflow_dispatch` | `rollback.yml` | tag elegido manualmente | `dev`/`staging`/`prod` | según Environment | aprobación si es `prod` |

Los tags no llevan `v` inicial. `pull_request` nunca despliega — cada
`cd-*.yml` y `rollback.yml` lo declara en su cabecera:

```yaml
# Safety invariant: this workflow deploys only after CI succeeds for an
# owner-controlled push to main. Never add pull_request.
```

### `_build-push.yml` — workflow reutilizable

`.github/workflows/_build-push.yml` es `workflow_call` con input `tag` y
`ref` opcional (SHA a construir; por defecto `github.sha`):

```yaml
on:
  workflow_call:
    inputs:
      tag: { description: Image tag to publish, required: true, type: string }
      ref: { description: Git ref or SHA to check out, required: false, type: string, default: "" }
permissions:
  contents: read
  packages: write
```

Un solo job `build` hace `checkout@v7`, `docker/login-action@v3` con
`registry: ghcr.io` y `GITHUB_TOKEN`, y `docker/build-push-action@v6` con
`context: ./app`, `file: ./app/Dockerfile`, `push: true`,
`tags: ghcr.io/vieitesss/hiss:${{ inputs.tag }}`.

Cada `cd-*.yml` lo invoca así:

```yaml
build:
  needs: prepare
  uses: ./.github/workflows/_build-push.yml
  with: { tag: ${{ needs.prepare.outputs.tag }} }
  secrets: inherit
```

Así se eliminó la duplicación que existía en el tag `workflows-duplicated`
(ver `docs/teacher/workflow-refactor-lesson.md`).

### `cd-dev.yml`, `cd-staging.yml`, `cd-prod.yml`

Los tres comparten estructura. Ejemplo `cd-dev.yml`:

- `prepare` (solo si CI fue `success` en un `push` a `main`): `runs-on: ubuntu-latest`, tag = 8 primeros caracteres de `github.event.workflow_run.head_sha`.
- `build`: reutilizable `_build-push.yml` con `ref` al mismo SHA.
- `deploy`: `runs-on: [self-hosted]`, `environment: dev`, `env: DEPLOY_TAG` y
  `POSTGRES_PASSWORD: ${{ secrets.POSTGRES_PASSWORD }}`, pasos `checkout@v7`,
  `docker compose -f deploy/compose.yml --env-file deploy/dev.env -p hiss-dev pull` y `up -d` con
  `IMAGE_TAG`/`APP_VERSION` inyectados.
- `smoke-test`: `runs-on: [self-hosted]`, `BASE_URL=http://localhost:8001`,
  tres `curl --fail --silent --show-error --max-time 10 --retry 10 --retry-delay 2 --retry-connrefused`
  a `/healthz`, `/readyz` y `/version | jq --exit-status --arg expected \"$DEPLOY_TAG\" '.version == $expected'`.

`cd-dev.yml` se dispara con `on: workflow_run` del workflow `CI`
(`types: [completed]`). Los jobs de `prepare` exigen `conclusion == success`,
`event == push` y `head_branch == main` para que un CI verde de un pull
request no despliegue. `cd-staging.yml` usa `on: push: tags:
'[0-9]+.[0-9]+.[0-9]+-snapshot'` y `RELEASE_TAG: ${{ github.ref_name }}`;
`BASE_URL=http://localhost:8002`. `cd-prod.yml` usa `'[0-9]+.[0-9]+.[0-9]+'`
y `BASE_URL=http://localhost:8003` con `environment: prod` protegido por
revisor. Staging y prod empiezan por `ci-gate`, que consulta el CI de ese
commit y no deja pasar `prepare` hasta `completed:success` (o falla si CI
falló).

### `rollback.yml`

Solo `workflow_dispatch` con inputs `environment` (`dev`/`staging`/`prod`,
`type: choice`) y `tag` (`type: string`). No construye: redespliega un tag
existente. `deploy` elige `env_file`/`project`/`port` con `case`, hace
`pull` y `up -d`; `smoke-test` resuelve `BASE_URL` según el Environment y
repite los tres `curl` + `jq`. Los rollbacks a `prod` también pausan por
aprobación de Environment.

```sh
gh workflow run rollback.yml -f environment=prod -f tag=0.1.0
gh workflow run rollback.yml -f environment=staging -f tag=0.1.0-snapshot
```

## Diagramas

### Flujo por tipo de disparador

```mermaid
flowchart TD
    PR["pull_request / push a main<br/>ci.yml en ubuntu-latest"] --> CHANGES["changes<br/>dorny/paths-filter"]
    CHANGES --> LINT["lint<br/>ruff 0.9.10"]
    CHANGES --> LINTD["lint-docker<br/>hadolint"]
    CHANGES --> TAPP["test-app<br/>postgres:17-alpine efímero"]
    CHANGES --> TCLI["test-cli"]
    TAPP --> BUILD["build<br/>docker build -f app/Dockerfile app/"]

    PUSHMAIN["push a main"] --> CIWAIT["ci.yml debe terminar en success"]
    CIWAIT --> CDDEV["cd-dev.yml via workflow_run<br/>prepare SHA8 → _build-push.yml<br/>→ deploy dev:8001 → smoke-test"]
    TAGSNAP["push tag X.Y.Z-snapshot"] --> CDSTAG["cd-staging.yml<br/>prepare tag → _build-push.yml<br/>→ deploy staging:8002 → smoke-test"]
    TAGREL["push tag X.Y.Z"] --> CDPROD["cd-prod.yml<br/>prepare tag → _build-push.yml<br/>→ deploy prod:8003<br/>gate de aprobación → smoke-test"]
    WD["workflow_dispatch"] --> ROLLBACK["rollback.yml<br/>deploy Environment/tag elegido<br/>→ smoke-test"]

    classDef cd fill:#e1f5fe,stroke:#01579b
    class CDDEV,CDSTAG,CDPROD,ROLLBACK cd
```

### Delivery vs Deployment — el gate de `prod`

```mermaid
sequenceDiagram
    participant D as dev :8001
    participant S as staging :8002
    participant P as prod :8003
    participant R as Revisor

    Note over D,P: push a main + CI verde → dev despliega — Deployment
    D->>D: _build-push SHA8 + pull/up + smoke-test

    Note over D,P: push X.Y.Z-snapshot → staging automático — Deployment
    S->>S: _build-push X.Y.Z-snapshot + pull/up + smoke-test

    Note over D,P: push X.Y.Z → prod queda en espera — Delivery
    P->>R: Environment prod requiere aprobación
    R-->>P: Approve
    P->>P: pull/up X.Y.Z + smoke-test
    Note over D,P: Sin aprobación no hay despliegue — Delivery != Deployment
```

La distinción nace de `environment: prod` con `Required reviewers` en
`Settings → Environments`. `dev` y `staging` practican Continuous
Deployment; `prod` practica Continuous Delivery.

## Smoke tests y probes

Cada despliegue, incluido `rollback.yml`, verifica tres endpoints expuestos
por `app/app/api/probes.py`:

- `GET /healthz` — liveness sin tocar la base de datos, siempre `200` si el
  proceso responde.
- `GET /readyz` — readiness con `SELECT 1` real contra Postgres; `503` si la
  base de datos no es alcanzable.
- `GET /version` — devuelve `{"version": "<APP_VERSION>"}`; el smoke test
  comprueba `jq --exit-status --arg expected \"$DEPLOY_TAG\" '.version == $expected'`
  (forma corta: `jq --arg expected`).

La healthcheck de Compose en `deploy/compose.yml` usa
`python -c 'import urllib.request; urllib.request.urlopen(\"http://localhost:8000/healthz\")'`
(no `curl`, ausente en `python:3.13-slim`) y `depends_on: db: condition: service_healthy`
con `pg_isready`. El observador en el runner hace `curl` desde el host con
`--retry 10 --retry-delay 2 --retry-connrefused` para tolerar el arranque.

```sh
curl --fail http://localhost:8001/healthz | jq .
curl --fail http://localhost:8001/readyz  | jq .
curl --fail http://localhost:8001/version | jq .  # {"version":"<SHA8>"}
curl --fail http://localhost:8002/version | jq .  # {"version":"X.Y.Z-snapshot"}
curl --fail http://localhost:8003/version | jq .  # {"version":"X.Y.Z"}

# Comando exacto del workflow (con reintentos y validación de versión):
curl --fail --silent --show-error --max-time 10 --retry 10 --retry-delay 2 --retry-connrefused "$BASE_URL/healthz"
curl --fail --silent --show-error --max-time 10 --retry 10 --retry-delay 2 --retry-connrefused "$BASE_URL/readyz"
curl --fail --silent --show-error --max-time 10 --retry 10 --retry-delay 2 --retry-connrefused "$BASE_URL/version" \
  | jq --exit-status --arg expected "$DEPLOY_TAG" '.version == $expected' >/dev/null
# forma mínima equivalente: jq --arg expected "$DEPLOY_TAG" '.version == $expected'
```

## Invariantes y convenciones

- `IMAGE=ghcr.io/vieitesss/hiss`, `IMAGE_TAG` y `APP_VERSION` coinciden
  siempre; el despliegue inyecta `POSTGRES_PASSWORD=${{ secrets.POSTGRES_PASSWORD }}` sin
  versionarla.
- `COMPOSE_PROJECT_NAME` (`hiss-dev`/`hiss-staging`/`hiss-prod`) aísla redes,
  volúmenes `pgdata` y contenedores en el mismo host.
- `X.Y.Z-snapshot` es móvil y reescribible; `X.Y.Z` es inmutable.
- `rollback.yml` nunca construye — solo mueve el tag desplegado.

Ver también [`docs/environments.md`](environments.md) para el mapeo de
entornos y [`docs/release-process.md`](release-process.md) para la ceremonia
de promoción.
