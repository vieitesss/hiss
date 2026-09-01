# Configuración del repositorio

## Integración continua

El repositorio tiene un único workflow de GitHub Actions,
`.github/workflows/ci.yml`. Se ejecuta en las pull requests y en los pushes a
`main`. Todos los jobs usan runners hospedados por GitHub (`ubuntu-latest`).
Una ejecución completa normal debería terminar en menos de tres minutos; si
tarda más, trátalo como una regresión — un pipeline lento es un mal artefacto
docente.

El workflow detecta primero las áreas modificadas y después ejecuta sólo las
comprobaciones relevantes:

- El lint de Python usa Ruff 0.9.10 (`ruff check app cli` y
  `ruff format --check app cli`).
- `lint-docker` ejecuta Hadolint contra `app/Dockerfile`.
- `test-app` aplica las migraciones de Alembic y ejecuta los tests de Flask
  contra un contenedor de servicio efímero `postgres:17-alpine`.
- `test-cli` ejecuta los tests del CLI sin contenedor de servicio.
- `build` ejecuta `docker build -f app/Dockerfile app/` después de los tests de
  la aplicación. Sólo valida la imagen: no hace login en ningún registro, no
  publica ninguna imagen ni despliega nada.

El job `changes` usa filtros de rutas. Un cambio en la aplicación ejecuta sus
comprobaciones y la construcción de la imagen; un cambio sólo en el CLI ejecuta
el lint de Python y los tests del CLI, pero se salta los tests de la
aplicación, el lint del Dockerfile y la construcción de la imagen. Los cambios
en archivos compartidos como `pytest.ini`, `ruff.toml` o el propio workflow
ejecutan ambas suites de tests. Un cambio que sólo toca documentación puede
dejar jobs de paquetes saltados; GitHub informa de los jobs requeridos
saltados como exitosos, así que esto no elude una comprobación fallida en un
cambio relevante.

## Proteger `main`

La protección de rama es deliberadamente un ajuste manual del repositorio en
GitHub, no un paso más de automatización. Después de que la primera ejecución
del workflow haga disponibles las comprobaciones:

1. Abre **Settings → Branches** (o **Rules → Rulesets**) en el repositorio.
2. Añade una regla para `main` y exige pull requests antes de fusionar.
3. Exige que las comprobaciones de estado pasen antes de fusionar. Selecciona
   las que aparecen como `CI / Detect changes`, `CI / Lint Python`,
   `CI / Lint Dockerfile`, `CI / Test app`, `CI / Test CLI` y
   `CI / Build app image`.
4. Guarda la regla. Mantenla activada también para administradores si el
   repositorio se usa como la puerta de fusión de la lección de CI/CD.

Una comprobación requerida en rojo bloquea el merge; una en verde (o saltada
por el filtro de rutas) es el permiso para continuar. Los runners
autoalojados quedan reservados para el trabajo de despliegue.

## Revisar una ejecución

El worker no hace push desde el checkout local. Después de que el orquestador
haga push de la rama, localiza y observa la ejecución real con comandos
acotados:

```sh
gh run list --workflow ci.yml --limit 5
gh run watch <run-id> --exit-status
gh run view <run-id> --log-failed
```

También puedes usar `gh workflow view ci.yml` una vez que el workflow existe
en GitHub. Deliberadamente no hay puerta de actionlint, ni de cobertura, ni
job de mypy, ni publicación de imagen, ni despliegue en este workflow.

## Entrega continua

Tres workflows de CD despliegan cada artefacto aceptado en tu propia máquina,
y un cuarto permite hacer rollback. Todos los despliegues se ejecutan en un
runner `[self-hosted]` que debe tener Docker Compose y `curl`/`jq`
disponibles; `linux` no forma parte de la etiqueta del runner, así que los
runners en macOS también funcionan.

| Disparador | Workflow | Tag de imagen | Environment | Puerta |
| --- | --- | --- | --- | --- |
| `push` a `main` | `cd-dev.yml` | `GITHUB_SHA` de 8 caracteres | `dev` (`:8001`) | automático |
| `push` de tag `X.Y.Z-snapshot` | `cd-staging.yml` | `X.Y.Z-snapshot` | `staging` (`:8002`) | automático |
| `push` de tag `X.Y.Z` | `cd-prod.yml` | `X.Y.Z` | `prod` (`:8003`) | aprobación del Environment |

Los tags no deben llevar una `v` inicial y `pull_request` nunca despliega —
cada workflow de despliegue comenta este invariante de seguridad en su
cabecera. Las construcciones usan `app/Dockerfile` y publican en
`ghcr.io/vieitesss/hiss:<tag>` a través del workflow reutilizable
`.github/workflows/_build-push.yml` (`workflow_call` con entrada `tag`,
permiso `packages: write`, login con `GITHUB_TOKEN`). Los despliegues ejecutan
`POSTGRES_PASSWORD=${{ secrets.POSTGRES_PASSWORD }} IMAGE_TAG=<tag>
APP_VERSION=<tag> docker compose -f deploy/compose.yml --env-file
deploy/<env>.env -p hiss-<env> pull && up -d` y después un job de humo hace
curl a `/healthz` y `/readyz`, y comprueba que `/version`
(`{"version": "<tag>"}`) coincide con el tag desplegado.

### Mutabilidad de los tags

- `X.Y.Z-snapshot` es un **tag móvil** — puedes borrarlo y volver a subirlo
  mientras endureces una release. La contrapartida es que el historial de
  staging no es estrictamente inmutable.
- `X.Y.Z` es **inmutable** una vez subido; nunca lo muevas ni lo vuelvas a
  subir.

### Prerrequisitos

1. **Runner autoalojado** registrado con la etiqueta `self-hosted` en la
   máquina que ejecutará los tres Environments (requiere Docker Engine +
   Compose v2).
2. **GitHub Environments** `dev`, `staging` y `prod` creados en el
   repositorio; cada uno guarda un secreto `POSTGRES_PASSWORD` (nunca
   versionado). `prod` tiene un revisor requerido (tú) para que el job de
   despliegue pause a la espera de aprobación — la distinción entre
   Continuous Delivery y Continuous Deployment.
3. **Paquete GHCR `ghcr.io/vieitesss/hiss` configurado como público** para
   que el runner pueda hacer `pull` sin credenciales adicionales; los pushes
   usan el `GITHUB_TOKEN` del workflow con `packages: write`.

### Rollback

`rollback.yml` sólo se dispara con `workflow_dispatch` (no construye nada) —
redespliega cualquier tag anterior en cualquier Environment. Los rollbacks a
prod siguen requiriendo la aprobación del Environment `prod`.

- **Interfaz web:** Actions → Rollback → Run workflow → elige `environment`
  (`dev` | `staging` | `prod`) y `tag`.
- **CLI:**

```sh
gh workflow run rollback.yml -f environment=prod -f tag=0.1.0
# o para staging:
gh workflow run rollback.yml -f environment=staging -f tag=0.1.0-snapshot
gh run list --workflow rollback.yml --limit 5
gh run view <run-id> --log-failed
```

> TODO: la ceremonia completa de release, la checklist de promoción y el
> runbook de rollback vivirán en `docs/release-process.md` (issue #7). Esta
> sección es sólo un puntero de descubrimiento hasta que ese documento exista.
