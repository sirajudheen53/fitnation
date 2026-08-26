# Backend Dockerfile — FBOS Django API (Cloud Run / GCP)
# Single-stage build for reliability on Cloud Run.
# Runtime deps compiled on the fly (psycopg) so gunicorn + Django are
# always present in the final image at a known location.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.cloudrun \
    PIP_NO_CACHE_DIR=1

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

# Collect static (production) — best-effort so a missing setting doesn't fail the build
RUN python manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 8000

# Health check endpoint for Cloud Run (uses Django's own liveness)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health/', timeout=3).status==200 else 1)"

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
