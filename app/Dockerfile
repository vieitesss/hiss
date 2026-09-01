# Hiss — Flask issue tracker (teaching image)
# Textbook-readable single-stage build: base, deps, source, non-root, migration+ gunicorn.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dependencies first for layer cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application source (respects .dockerignore)
COPY . .

# Create non-root user and prepare entrypoint
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app \
    && chmod +x ./docker-entrypoint.sh

# hadolint ignore=DL3066
USER appuser

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
