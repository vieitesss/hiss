# Lección — Refactor de workflows duplicados a workflow reutilizable

> **Orientado al profesor — teacher-only.** Plan de clase para el profesor. Los estudiantes pueden
> leerlo después, pero la actividad está diseñada para ser guiada en aula.
> Requiere haber visto `docs/pipeline.md` y `docs/setup.md`.

Esta lección convierte un defecto intencional en aprendizaje. El tag
`workflows-duplicated` contiene los tres workflows de CD con `build` y
`push` duplicados inline; `main` los extrae a un workflow reutilizable
`_build-push.yml`. El alumno comprueba el tag, inspecciona el diff y
discute por qué `workflow_call` es la abstracción correcta.

## Objetivo

Que el alumno distinga duplicación accidental de abstracción útil y entienda
`workflow_call` con `inputs`, `secrets: inherit` y `permissions`.

## Prerrequisitos

- Repo clonado con acceso a `origin` y tags: `git fetch --tags`.
- Haber leído `docs/pipeline.md` § `_build-push.yml` y § `cd-dev.yml`.
- Conocer `docker/build-push-action@v6` y `docker/login-action@v3` a nivel
  de lectura — no es necesario ejecutarlos en clase.

## Material

- Tag `workflows-duplicated` (commit `963d38e`): `cd: duplicated first-pass
  delivery workflows and manual rollback`.
- `main` actual con `_build-push.yml`.

## Guion (45–60 min)

### 0. Contexto (5 min)

El repo entregó CD por primera vez con tres ficheros idénticos salvo el
trigger y el Environment. Funcionaba, pero cada cambio de `login` o
`build-push` había que repetirlo tres veces. La deuda técnica se etiquetó
adrede para enseñar el refactor.

Pregunta de apertura: ¿dónde está la duplicación y por qué duele?

### 1. Inspeccionar el tag (10 min)

```sh
git fetch --tags
git tag --list | grep workflows-duplicated
git show workflows-duplicated --stat
```

Debe mostrar:

```
.github/workflows/cd-dev.yml     |  99 +++++++++++++++++++
.github/workflows/cd-prod.yml    | 101 ++++++++++++++++++++
.github/workflows/cd-staging.yml | 101 ++++++++++++++++++++
.github/workflows/rollback.yml   |  99 +++++++++++++++++++++
```

Sin `_build-push.yml`.

Ver un workflow duplicado:

```sh
git show workflows-duplicated:.github/workflows/cd-dev.yml
```

Snippet relevante (antes del refactor):

```yaml
  build:
    name: Build and push dev image
    needs: prepare
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - name: Check out repository
        uses: actions/checkout@v4
      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Build and push image
        uses: docker/build-push-action@v6
        with:
          context: ./app
          file: ./app/Dockerfile
          push: true
          tags: ghcr.io/vieitesss/hiss:${{ needs.prepare.outputs.tag }}
```

Hacer lo mismo con `cd-staging.yml` y `cd-prod.yml` — son idénticos salvo
el nombre del job y el tag de entrada.

```sh
git show workflows-duplicated:.github/workflows/cd-staging.yml | grep -A5 "Build and push"
git show workflows-duplicated:.github/workflows/cd-prod.yml | grep -A5 "Build and push"
```

Alternativa sin `git show` (útil si el alumno prefiere checkout):

```sh
git checkout workflows-duplicated -- .github/workflows/cd-dev.yml
cat .github/workflows/cd-dev.yml | sed -n '/Build and push/,/tags:/p'
git checkout main -- .github/workflows/cd-dev.yml  # restaurar
```

### 2. Diff al `main` actual (15 min)

```sh
git diff workflows-duplicated..main -- .github/workflows/_build-push.yml
git diff workflows-duplicated..main -- .github/workflows/cd-dev.yml
git diff workflows-duplicated..main -- .github/workflows/cd-staging.yml
git diff workflows-duplicated..main -- .github/workflows/cd-prod.yml
```

**`_build-push.yml` — fichero nuevo:**

```yaml
name: Reusable build and push
on:
  workflow_call:
    inputs:
      tag: { description: Image tag to publish, required: true, type: string }
permissions:
  contents: read
  packages: write
jobs:
  build:
    name: Build and push ${{ inputs.tag }}
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v7
      - uses: docker/login-action@v3
        with: { registry: ghcr.io, username: ${{ github.actor }}, password: ${{ secrets.GITHUB_TOKEN }} }
      - uses: docker/build-push-action@v6
        with: { context: ./app, file: ./app/Dockerfile, push: true, tags: ghcr.io/vieitesss/hiss:${{ inputs.tag }} }
```

**`cd-dev.yml` — antes vs después (diff resumido):**

```diff
   build:
     name: Build and push dev image
     needs: prepare
-    runs-on: ubuntu-latest
-    timeout-minutes: 10
-    steps:
-      - name: Check out repository
-        uses: actions/checkout@v4
-      - name: Log in to GHCR
-        uses: docker/login-action@v3
-      - name: Build and push image
-        uses: docker/build-push-action@v6
+    uses: ./.github/workflows/_build-push.yml
+    with: { tag: ${{ needs.prepare.outputs.tag }} }
+    secrets: inherit
+    permissions: { contents: read, packages: write }
```

El diff también muestra `checkout@v4` → `checkout@v7` — cambio menor de
mantenimiento, no parte del refactor conceptual. Señalarlo para que no
distraiga.

Hacer el mismo `git diff` para `cd-staging.yml` y `cd-prod.yml`; el patrón
es idéntico.

### 3. Discusión guiada (15 min)

1. **¿Por qué `workflow_call` y no una `action` compuesta?**
   `workflow_call` reutiliza un workflow completo con `jobs`; una action
   compuesta encapsula `steps`. Aquí necesitamos un job con `permissions` y
   `runs-on` propios — `workflow_call` es la herramienta correcta.

2. **¿Por qué `inputs.tag` y no `github.ref_name` directo?**
   Porque `_build-push.yml` no sabe si viene de `SHA8`, `snapshot` o `X.Y.Z`
   — el caller decide. Desacopla trigger de empaquetado.

3. **¿Qué hace `secrets: inherit`?**
   Propaga `GITHUB_TOKEN` con `packages: write` sin enumerar cada secreto.
   Sin `inherit`, el `docker/login-action` fallaría con `unauthorized`.
   Discutir alternativa `secrets: { GITHUB_TOKEN: ... }` y por qué `inherit`
   es más simple aquí pero menos granular.

4. **¿Por qué `permissions: contents: read, packages: write` dos veces?**
   Una a nivel de workflow reutilizable, otra a nivel de caller que lo
   invoca — GitHub exige declarar permisos en ambos.

5. **¿Cuándo no abstraer?**
   Si cada CD necesitase `build` distinto (por ejemplo `dev` con `--target
   dev`), la abstracción prematura complicaría. Aquí los tres builds son
   idénticos — abstraer reduce 60 líneas duplicadas y un punto de fallo.

6. **¿Qué queda duplicado a propósito?**
   `prepare` (cálculo de tag distinto: `SHA8` vs `ref_name`) y `deploy`/
   `smoke-test` (Environment y puerto distintos). No todo debe generalizarse.

### 4. Cierre y tarea (5 min)

- Tarea: proponer un siguiente refactor — por ejemplo extraer `deploy` a
  workflow reutilizable con `inputs: environment, tag, port`. Debatir si
  merece la pena o si la duplicación de `deploy` es accidental pero estable.
- Referencia: `docs/pipeline.md:### _build-push.yml` y `fdab845 cd: extract
  reusable build-push workflow from CD callers` (mensaje de commit).

## Comandos de referencia para el alumno

```sh
git fetch --tags
git show workflows-duplicated:.github/workflows/cd-dev.yml | less
git diff workflows-duplicated..main -- .github/workflows/_build-push.yml
git diff workflows-duplicated..main -- .github/workflows/cd-dev.yml
git log --oneline workflows-duplicated..main | cat
# restaurar si se hizo checkout del tag:
git checkout main -- .github/workflows/
```

## Notas para el profesor

- No ejecutar workflows en clase — la inspección es estática. Si quieres
  demo en vivo, empuja un commit vacío a `main` y observa `cd-dev.yml` en
  **Actions**.
- El tag `workflows-duplicated` se creó adrede para esta lección; no lo
  borres. Si se pierde, recrearlo desde `963d38e`.
- Tiempo: si la clase es de 90 min, añade ejercicio práctico: el alumno
  crea una rama, revierte el refactor (copia el `build` inline) y abre PR
  para ver `ci.yml` verde pero diff mayor.
