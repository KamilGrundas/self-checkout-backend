# Self-Checkout Backend

FastAPI backend for the self-checkout platform.

This service is part of a larger setup:
- Client: `https://github.com/KamilGrundas/self-checkout-client`
- ML service: `https://github.com/KamilGrundas/self-checkout-ml`
- Infrastructure: `https://github.com/KamilGrundas/self-checkout-infra`

## Responsibilities

- product catalog,
- checkout counters,
- persistent checkout sessions,
- cart synchronization,
- session payment and closing,
- product image storage integration.

## Stack

- FastAPI
- SQLModel
- PostgreSQL
- Alembic
- Python 3.14.6
- MinIO
- `uv` 0.11.31 for environment and dependency management

## Required Configuration

The backend loads environment variables from `.env`.

Minimal local configuration:

```env
PROJECT_NAME=self-checkout
SECRET_KEY=change-me
FIRST_SUPERUSER=admin@example.com
FIRST_SUPERUSER_PASSWORD=change-me
EMAILS_FROM_EMAIL=info@example.com
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_DB=app
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change-me
FRONTEND_HOST=http://localhost:3000
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=product-images
MINIO_PUBLIC_URL=http://localhost:9000
MINIO_USE_SSL=false
```

## Run Locally

Install Python 3.14.6 and use the pinned interpreter:

```bash
uv python install 3.14.6
uv sync --group dev
source .venv/bin/activate
alembic upgrade head
fastapi run --reload app/main.py
```

Default address:

```text
http://127.0.0.1:8000
```

## Important Endpoints

- `GET /api/v1/utils/health-check/`
- `GET /api/v1/products/`
- `POST /api/v1/checkout-counters/`
- `POST /api/v1/checkout-sessions/connect`
- `PUT /api/v1/checkout-sessions/{id}/cart`
- `POST /api/v1/checkout-sessions/{id}/pay`

## Verification

Quick checks:

```bash
uv run --active --group dev python -m compileall app tests
uv run --active --group dev python -c "from app.main import app; print(len(app.routes))"
```

Full test suite:

```bash
uv run --active --group dev python -m pytest tests/
```
