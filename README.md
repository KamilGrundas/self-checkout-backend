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
- checkout-counter camera inventory and per-session settings snapshots,
- superuser-managed scale-autolabel inference settings,
- product image storage integration.

## Stack

- FastAPI
- SQLModel
- PostgreSQL
- Alembic
- Python 3.14.6
- S3-compatible object storage
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
DATABASE_URL=postgresql+psycopg://postgres:change-me@localhost:5432/app
FRONTEND_HOST=http://localhost:3000
BACKEND_PUBLIC_URL=http://localhost:8000
S3_ENDPOINT_URL=http://s3-provider:8080
S3_REGION=us-east-1
S3_ACCESS_KEY_ID=dev-access-key
S3_SECRET_ACCESS_KEY=dev-secret-key
S3_BUCKET=product-images
S3_USE_SSL=false
S3_FORCE_PATH_STYLE=true
S3_VERIFY_TLS=true
S3_CREATE_BUCKETS=true
```

Product image responses use the backend delivery endpoint derived from
`BACKEND_PUBLIC_URL`; browsers never connect directly to internal S3 DNS.
The backend reads each object through the generic S3 client and preserves its
content type.

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
- `PUT /api/v1/checkout-counters/{id}` — superuser counter, mode, language,
  and camera selection; camera identifiers must come from the latest successful
  client report
- `PUT /api/v1/checkout-counters/me/settings` — authenticated counter settings
- `POST /api/v1/checkout-sessions/connect`
- `PUT /api/v1/checkout-sessions/{id}/cart`
- `POST /api/v1/checkout-sessions/{id}/pay`
- `GET /api/v1/system-settings/autolabel` — superuser-only global inference
  configuration
- `PUT /api/v1/system-settings/autolabel` — superuser-only update of endpoint,
  token limit, and connect/read timeouts

The native client includes its current camera inventory when connecting and
reports it again over the checkout-session WebSocket. Failed camera discovery
does not erase the last successful inventory. Each new checkout session stores
a snapshot of the counter's mode, selected cameras, and language; edits made
while a session is active therefore apply to the next session.

Scale-autolabel settings are stored in a singleton database row. Endpoint URLs
accept only HTTP(S), reject embedded credentials and fragments, and deliberately
allow private network addresses for a local VLM. The ML service reads these
settings with the initiating superuser JWT.

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
