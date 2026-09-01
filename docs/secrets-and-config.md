# Secretos y configuración

Este documento explica cómo hiss separa configuración y secretos
siguiendo el principio 12-factor, qué ficheros están versionados y
cuáles nunca deben versionarse, y cómo la Feature Flag permite cambiar
comportamiento por Environment sin reconstruir la imagen.

## Principio 12-factor

La app no lee ficheros de configuración por entorno. Toda configuración
entra por variables de entorno en tiempo de ejecución. La clase
`app/app/config.py` centraliza la lectura:

```python
# app/app/config.py
class Config:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    APP_VERSION: str = os.getenv("APP_VERSION", "dev")
    FEATURE_LABEL_FILTERING: bool = _parse_feature_flag(
        os.getenv("FEATURE_LABEL_FILTERING", "true")
    )
    SQLALCHEMY_DATABASE_URI: str = _to_psycopg_uri(DATABASE_URL or "sqlite:///:memory:")
```

`create_app` relee el entorno en cada llamada para que los tests puedan
mutar flags sin recargar el proceso. Los valores por defecto permiten
arrancar sin entorno completo (`sqlite:///:memory:` para tests,
`APP_VERSION=dev`).

## `deploy/*.env` — configuración versionada no secreta

Tres ficheros idénticos en estructura, distintos solo en cuatro valores.
Están en Git y se pueden auditar:

| Variable | `deploy/dev.env` | `deploy/staging.env` | `deploy/prod.env` |
| --- | --- | --- | --- |
| `COMPOSE_PROJECT_NAME` | `hiss-dev` | `hiss-staging` | `hiss-prod` |
| `IMAGE` | `ghcr.io/vieitesss/hiss` | `ghcr.io/vieitesss/hiss` | `ghcr.io/vieitesss/hiss` |
| `IMAGE_TAG` | `edge` | `0.1.0-snapshot` | `0.1.0` |
| `APP_VERSION` | `edge` | `0.1.0-snapshot` | `0.1.0` |
| `APP_PORT` | `8001` | `8002` | `8003` |
| `FEATURE_LABEL_FILTERING` | `true` | `true` | `false` |
| `POSTGRES_DB` | `hiss` | `hiss` | `hiss` |
| `POSTGRES_USER` | `postgres` | `postgres` | `postgres` |

Todos declaran:

```
# Hiss — Environment config (committed, non-secret)
# DB password is injected at deploy time — never committed.
```

`IMAGE` es parametrizable: puedes sobreescribirlo en el shell para
validar otro registro sin editar el repo:

```sh
IMAGE=ghcr.io/otro/hiss docker compose -f deploy/compose.yml --env-file deploy/dev.env -p hiss-dev config | grep image:
```

`IMAGE_TAG` y `APP_VERSION` siguen al tag desplegado (`DEPLOY_TAG` en los
workflows). En `dev` el valor real es `GITHUB_SHA::8`, no `edge` — `edge`
es solo placeholder del fichero.

Comprueba que ningún `.env` contiene secretos:

```sh
grep -r POSTGRES_PASSWORD deploy/*.env || echo "ok: ningún secreto versionado"
cat deploy/dev.env
cat deploy/staging.env
cat deploy/prod.env
```

## `POSTGRES_PASSWORD` — secreto nunca versionado

`POSTGRES_PASSWORD` se declara en `deploy/compose.yml` con validación
estricta:

```yaml
services:
  db:
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?must be set}
  app:
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:?must be set}@db:5432/${POSTGRES_DB:-hiss}
```

Si falta, Compose falla en seco en lugar de arrancar con una contraseña
por defecto. La base de datos nunca publica `5432` en el host — solo es
accesible como `db:5432` dentro de la red de Compose.

### En local

Inyecta la contraseña desde el entorno del proceso:

```sh
export POSTGRES_PASSWORD='elige-un-secreto-local'
docker compose --env-file deploy/dev.env -p hiss-dev up -d
docker compose --env-file deploy/dev.env -p hiss-dev ps

# También puede invocarse con -f explícito
docker compose -f deploy/compose.yml --env-file deploy/staging.env -p hiss-staging up -d
docker compose -f deploy/compose.yml --env-file deploy/prod.env -p hiss-prod up -d

# Verificación de que el secreto llegó al contenedor
docker compose --env-file deploy/dev.env -p hiss-dev exec db env | grep POSTGRES_PASSWORD
curl --fail http://localhost:8001/readyz | jq .  # hace SELECT 1 real con la contraseña
```

Para detener sin borrar datos:

```sh
docker compose --env-file deploy/dev.env -p hiss-dev down      # mantiene pgdata
docker compose --env-file deploy/dev.env -p hiss-dev down -v   # borra volumen de ese Environment
```

### En CI/CD

Cada `cd-*.yml` y `rollback.yml` inyecta el secreto desde el GitHub
Environment:

```yaml
deploy:
  runs-on: [self-hosted]
  environment: dev
  env:
    DEPLOY_TAG: ${{ needs.prepare.outputs.tag }}
    POSTGRES_PASSWORD: ${{ secrets.POSTGRES_PASSWORD }}
  steps:
    - run: |
        POSTGRES_PASSWORD="$POSTGRES_PASSWORD" IMAGE_TAG="$DEPLOY_TAG" APP_VERSION="$DEPLOY_TAG" \
          docker compose -f deploy/compose.yml --env-file deploy/dev.env -p hiss-dev pull
        POSTGRES_PASSWORD="$POSTGRES_PASSWORD" IMAGE_TAG="$DEPLOY_TAG" APP_VERSION="$DEPLOY_TAG" \
          docker compose -f deploy/compose.yml --env-file deploy/dev.env -p hiss-dev up -d
```

Configura el secreto por Environment en **Settings → Environments → dev/staging/prod →
Environment secrets → POSTGRES_PASSWORD** (ver `docs/setup.md`). `prod`
además tiene `Required reviewers` — el despliegue pausa hasta aprobación.

El secreto nunca se escribe en `deploy/*.env` ni en logs. Si `GHCR` fuese
privado, también haría falta `docker/login-action`, pero el paquete es
público (`ghcr.io/vieitesss/hiss` en **Packages → Visibility → Public**) y
el `pull` es anónimo.

## Feature Flag — `FEATURE_LABEL_FILTERING`

Una variable de entorno que activa o desactiva el filtrado por etiqueta
sin cambiar la imagen.

| Environment | `FEATURE_LABEL_FILTERING` | Efecto |
| --- | --- | --- |
| `dev` | `true` | filtrado por `?label=bug` activo |
| `staging` | `true` | igual que `dev` — pruebas de la feature |
| `prod` | `false` | filtrado deshabilitado — `GET /projects/:key/issues?label=...` devuelve `400` |

Lectura en `app/app/config.py`:

```python
def _parse_feature_flag(value: str | None) -> bool:
    if value is None:
        return True
    lower = value.strip().lower()
    if lower in ("true", "1", "yes", "on"):
        return True
    if lower in ("false", "0", "no", "off"):
        return False
    return True  # fallback conservador
```

Pruebas en `app/tests/test_probes_version_flag.py`:

- `test_label_filter_when_flag_on_returns_filtered` — con flag `true` filtra por label.
- `test_label_filter_when_flag_off_returns_400` — con `FEATURE_LABEL_FILTERING=false` la query `?label=bug` devuelve `400` con mensaje `disabled` o `flag`.

Para probar localmente:

```sh
# Con filtrado activo (dev/staging)
export POSTGRES_PASSWORD='elige-un-secreto-local'
docker compose --env-file deploy/dev.env -p hiss-dev up -d
curl -s http://localhost:8001/api/v1/projects/PRJ/issues?label=bug | jq .

# Con filtrado desactivo (prod)
docker compose --env-file deploy/prod.env -p hiss-prod up -d
curl -s http://localhost:8003/api/v1/projects/PRJ/issues?label=bug | jq .
# → {"message":"label filtering disabled"}  (400)

# Sobrescribir sin editar .env
FEATURE_LABEL_FILTERING=false docker compose --env-file deploy/dev.env -p hiss-dev up -d
```

La flag demuestra el patrón 12-factor: el mismo artefacto
(`ghcr.io/vieitesss/hiss:<tag>`) se comporta distinto según el entorno que
lo ejecuta.

## Resumen de verificación

```sh
# Ningún secreto en ficheros versionados
grep -rn POSTGRES_PASSWORD deploy/*.env && echo "ERROR" || echo "ok"

# Config por Environment visible y parametrizable
cat deploy/dev.env | grep -E "IMAGE|APP_PORT|FEATURE_LABEL_FILTERING"
cat deploy/prod.env | grep -E "IMAGE|APP_PORT|FEATURE_LABEL_FILTERING"
IMAGE=example.invalid/x docker compose -f deploy/compose.yml --env-file deploy/dev.env config | grep example.invalid

# Compose valida presencia del secreto
POSTGRES_PASSWORD=dummy docker compose --env-file deploy/dev.env -p hiss-dev config -q && echo "config ok"
# Sin contraseña debe fallar
POSTGRES_PASSWORD= docker compose --env-file deploy/dev.env -p hiss-dev config && echo "debe fallar" || echo "falla como debe"

# Feature flag en código y tests
grep -n FEATURE_LABEL_FILTERING app/app/config.py
grep -n FEATURE_LABEL_FILTERING app/tests/test_probes_version_flag.py
grep -n FEATURE_LABEL_FILTERING deploy/*.env

# Despliegue con secreto inyectado
export POSTGRES_PASSWORD='elige-un-secreto-local'
docker compose -f deploy/compose.yml --env-file deploy/dev.env -p hiss-dev up -d
curl --fail http://localhost:8001/healthz | jq .
curl --fail http://localhost:8001/readyz  | jq .
curl --fail http://localhost:8001/version | jq .
```

Ver también `docs/release-process.md` para cómo ese mismo mecanismo se usa
durante promociones y rollbacks, y `deploy/compose.yml` para la definición
canónica de servicios.
