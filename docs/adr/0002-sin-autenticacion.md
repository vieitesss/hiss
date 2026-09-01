# ADR 0002: Sin autenticación — API abierta por alcance docente

> Decisión deliberada: sin auth = alcance docente recortado para un curso de CD.

- **Estado:** Aceptado
- **Fecha:** 2025-09-01
- **Decisores:** Equipo docente, mantenedores del repo

## Contexto

Hiss es un gestor de issues mínimo para enseñar CI/CD, no un producto
multiusuario. Cada despliegue (`hiss-dev:8001`, `hiss-staging:8002`,
`hiss-prod:8003`) corre en `localhost` del estudiante con su propio
`pgdata` aislado por `COMPOSE_PROJECT_NAME`. No hay usuarios, roles,
sesiones ni datos sensibles: el repo se usa en clase, en red local, por
una sola persona a la vez.

Añadir autenticación desviaría el foco del módulo 5168 (pipelines,
environments, estrategias de despliegue, migraciones) hacia gestión de
identidad, hashing de contraseñas, JWT/sesiones, middleware y tests de
seguridad — todo valioso pero fuera del temario y con coste de
mantenimiento que oscurece las lecciones de CD.

## Decisión

No implementar autenticación ni gestión de usuarios. La API
(`app/app/api/projects.py`, `issues.py`, `labels.py`, `comments.py`) y la
SPA (`app/app/static/`) son abiertas en la red de Compose; cualquier
cliente con acceso a `http://localhost:8001` (o `8002`/`8003`) puede leer
y escribir.

Esta decisión se documenta para que ningún contribuidor la "arregle" por
sorpresa.

## Alternativas consideradas y rechazadas

| Alternativa | Por qué se rechazó |
| --- | --- |
| **Autenticación completa** (registro/login, `Flask-Login` o JWT, `User` en `app/app/models.py`, guardas en cada endpoint) | Duplica fuera de alcance: requiere modelo `users`, migraciones, hash `bcrypt`, manejo de sesiones/refresh, recuperación de contraseña, y tests de auth. El curso no evalúa auth; evaluaría el pipeline haciendo más difícil ver el flujo `push` → `build` → `deploy`. |
| **API tokens** (cabecera `Authorization: Bearer <token>` por Environment) | Más ligero que usuarios, pero aún exige generación, almacenamiento y rotación de tokens, inyección vía `secrets.API_TOKEN` y lógica de validación en cada `api/*.py`. Añade una variable por Environment sin aportar lección de CD distinta a la que ya enseña `POSTGRES_PASSWORD`. |

## Consecuencias

**Positivas:**

- Código mínimo y legible: `app/app/api/` sin decoradores de auth, tests
  sin fixtures de usuario, migraciones sin `users`.
- El alumno se concentra en `ci.yml`, `cd-*.yml`, `deploy/compose.yml`,
  `FEATURE_LABEL_FILTERING` y `0002_create_labels_issue_labels.py`.
- `rollback.yml` y `switch.sh` no necesitan credenciales de app.

**Negativas / obligaciones:**

- **API abierta:** cualquiera con acceso a `localhost:8001` puede crear o
  borrar issues. No exponer `hiss-prod:8003` a internet ni a redes no
  confiables; el repo está pensado para `localhost`.
- **Sin auditoría por usuario:** `Comment` y `Issue` no guardan `author`.
  Si se necesita trazabilidad, habrá que migrar el esquema.
- Alcance recortado: si hiss se publica como servicio real, esta ADR debe
  revertirse — revisar `CONTEXT.md` (términos `Project`/`Issue`/`Label`) y
  diseñar auth antes de exponer un host público.

**Reversibilidad:** decisión reversible. Para añadir auth, crear rama con
`users` + JWT, proteger `api/*` y añadir `AUTH_TOKEN` a
`deploy/*.env`/`secrets`; el pipeline no cambia, solo la app. Mantener
esta ADR como recordatorio de por qué se optó por no hacerlo.

## Referencias

- `app/app/api/` — endpoints sin guarda de auth
- `app/app/models.py` — sin modelo `User`
- `CONTEXT.md` — glosario (`Project`, `Issue`, `Label`, `Comment`)
- `deploy/compose.yml` — sin `AUTH_TOKEN`, solo `POSTGRES_PASSWORD` y `FEATURE_LABEL_FILTERING`
- `docs/secrets-and-config.md` — qué es secreto y qué no
