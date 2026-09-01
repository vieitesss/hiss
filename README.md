# hiss

Un gestor de issues mínimo y autoalojable (Flask + Postgres + API REST + CLI), construido como material docente para un curso de CI/CD con GitHub Actions y Docker.

> Repo en construcción — ver los issues para el plan de implementación y `CONTEXT.md` para el glosario de dominio.

## Integración continua

GitHub Actions ejecuta los checks de lint, tests y construcción de imagen
descritos en [`docs/setup.md`](docs/setup.md). Configura manualmente la
protección de la rama `main` después de la primera ejecución del workflow para
que un resultado rojo de CI bloquee los merges.

## Despliegue con Docker Compose

La imagen de la aplicación se referencia como `${IMAGE}:${IMAGE_TAG}`. Cada
archivo `deploy/*.env` fija `IMAGE=ghcr.io/vieitesss/hiss` por defecto; puedes
desde el shell sobreescribir `IMAGE` para validar o desplegar otro registro.
El paquete de GHCR debe estar configurado como **público** para que los hosts de
despliegue y los runners puedan hacer pull anónimo sin un token de GitHub. Esto
también significa que cualquiera puede descargar la imagen; la visibilidad
pública no expone las credenciales de Postgres.

Los archivos `deploy/*.env` están versionados y contienen sólo configuración no
secreta. Muestran el mismo artefacto desplegado en cada Environment:

| Environment | Puerto publicado | `IMAGE_TAG` / `APP_VERSION` | `FEATURE_LABEL_FILTERING` | Proyecto Compose |
| --- | ---: | --- | --- | --- |
| dev | 8001 | Edge Build (placeholder `edge`; en un despliegue real, SHA de 8 caracteres) | `true` | `hiss-dev` |
| staging | 8002 | `X.Y.Z-snapshot` | `true` | `hiss-staging` |
| prod | 8003 | `X.Y.Z` | `false` | `hiss-prod` |

En todos los casos `APP_VERSION` sigue a `IMAGE_TAG`; cambiar esta configuración
no cambia la imagen que se despliega. Los nombres `hiss-dev`, `hiss-staging` y
`hiss-prod` permiten que las tres Environments coexistan en el mismo host.

### Credencial de Postgres

`POSTGRES_PASSWORD` **nunca se versiona** ni aparece en los archivos de
Environment. En local, inyéctala desde el entorno del proceso y despliega desde
la raíz del repositorio:

```sh
export POSTGRES_PASSWORD='elige-un-secreto-local'
docker compose --env-file deploy/dev.env -p hiss-dev up -d
```

Para las otras Environments:

```sh
export POSTGRES_PASSWORD='elige-un-secreto-local'
docker compose --env-file deploy/staging.env -p hiss-staging up -d
docker compose --env-file deploy/prod.env -p hiss-prod up -d
```

Los archivos `.env` sólo seleccionan la configuración; si falta la contraseña,
Compose falla en lugar de arrancar con una credencial por defecto. En CI/CD, el
workflow debe inyectar el mismo valor desde el secreto del GitHub Environment,
sin escribirlo en el repositorio ni en `deploy/*.env`.

La definición canónica también puede invocarse explícitamente con
`-f deploy/compose.yml`:

```sh
docker compose -f deploy/compose.yml --env-file deploy/dev.env -p hiss-dev up -d
```

### Red, probes y logs

La base de datos sólo es accesible dentro de la red de Compose mediante el nombre
DNS `db` y el puerto interno 5432; **no se publica 5432 en el host**. Sólo se
publica la aplicación, en 8001 (dev), 8002 (staging) o 8003 (prod), evitando
colisiones con un Postgres local o con el servidor Flask de desarrollo en 8000.

Al iniciar el contenedor de la aplicación, el entrypoint ejecuta
`alembic upgrade head` y después inicia Gunicorn. Compose espera a que Postgres
esté saludable y mantiene probes para liveness, readiness y versión:

```sh
docker compose --env-file deploy/dev.env -p hiss-dev ps
docker compose --env-file deploy/dev.env -p hiss-dev logs -f app

# Desde el host de dev:
curl --fail http://localhost:8001/healthz
curl --fail http://localhost:8001/readyz
curl --fail http://localhost:8001/version
```

Estos comandos (`docker compose ps` y `docker compose logs`) son la
monitorización básica del despliegue. Para detener un Environment sin borrar sus
datos persistentes usa `down`; añade `-v` sólo cuando también quieras eliminar
su volumen de Postgres:

```sh
docker compose --env-file deploy/dev.env -p hiss-dev down
```
