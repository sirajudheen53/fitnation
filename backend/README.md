# FBOS Backend

Django + DRF backend for the Fitness Business Operating System.

## Quick Start (Docker Compose)

```bash
# From project root
cp .env.example .env
docker compose up -d
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
```

Backend: http://localhost:8000

## Local Development (without Docker)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set up PostgreSQL and Redis locally or use docker compose for just those:
# docker compose up -d db redis

python manage.py migrate
python manage.py runserver
```

## Settings

| Environment | Settings module              | Use              |
|------------|------------------------------|------------------|
| Dev        | `config.settings.dev`        | Local + compose  |
| Production | `config.settings.prod`       | Staging/Prod     |

## Testing

```bash
cd backend
pytest
# with coverage:
pytest --cov --cov-report=term-missing
```

## Linting

```bash
flake8 .
black --check .
isort --check-only .
```

## Project Structure

```
backend/
├── config/
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py    # shared settings
│   │   ├── dev.py     # dev overrides
│   │   └── prod.py    # production overrides
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── manage.py
├── requirements.txt
└── Dockerfile
```