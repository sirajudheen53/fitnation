# Backend Dockerfile — FBOS Django API (Cloud Run / GCP)
# Single-stage build for reliability on Cloud Run.
# Runtime deps compiled on the fly (psycopg) so gunicorn + Django are
# always present in the final image at a known location.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.cloudrun \
    PIP_NO_CACHE_DIR=1

# Build-time-only settings so collectstatic can import cloudrun settings and
# build the whitenoise manifest. ARGs are visible to RUN steps but are NOT
# persisted into the runtime image — Cloud Run injects the real values as
# service env vars/secrets at deploy time (runtime env unchanged).
# DATABASE_URL only needs to parse (env.db()); storages are lazy and
# collectstatic never opens a DB connection.
ARG DATABASE_URL=postgres://u:p@localhost:5432/d
ARG SECRET_KEY=build-time-only-placeholder-not-used-at-runtime

WORKDIR /app

# Install build + runtime deps (psycopg needs libpq + headers at build time)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (includes gunicorn)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Collect static (production). Must fail the build on error: with
# CompressedManifestStaticFilesStorage, an image without the manifest makes
# every template using {% static %} (admin, DRF browsable API) raise
# ValueError "Missing staticfiles manifest entry" → HTTP 500 at runtime.
RUN python manage.py collectstatic --noinput

# Hard guard: never ship an image without the staticfiles manifest.
# Path is derived from settings so it cannot drift from STATIC_ROOT.
RUN test -f "$(python -c 'import os; from django.conf import settings; print(os.path.join(settings.STATIC_ROOT, "staticfiles.json"))')"

EXPOSE 8000

# Health check endpoint for Cloud Run (uses Django's own liveness)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health/', timeout=3).status==200 else 1)"

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
