# Backend repository instructions

FastAPI/SQLModel application. Runtime code is under `app/`, API tests under `tests/`, Alembic migrations under `app/alembic/versions`, and controlled project commands under `scripts/`.

Read `../AGENTS.md` first. Inspect Git with `git -C self-checkout-backend`; never edit directly on `main` or `master`, combine repositories in one commit, or commit `.env`, `.venv`, caches, coverage output, local data, tokens, or object-store credentials. Never rewrite an applied migration; add a new migration and coordinate its deployment explicitly.

Repository checks are `bash scripts/lint.sh` (mypy strict, Ruff lint, Ruff format check) and `bash scripts/tests-start.sh` or `bash scripts/test.sh` when dependencies are ready. Build validation uses the repository Dockerfile. Database-dependent tests, migrations, Docker builds, and integration checks run only on remote dev.

Use `../ops/dev-sync.sh --repo backend --dry-run`, then `../ops/dev-test.sh --repo backend`. Keep commits focused and imperative. Coordinate API/schema changes with admin, client, and ML repositories and document merge order.

The base branch is `main` as recorded in `../repos.yaml`. Create short-lived branches from a freshly fetched `origin/main`, and never implement directly on `main` or `master`. Use Conventional Commits with scopes such as `backend`, `api`, `auth`, `db`, `storage`, or `websocket`.

Definition of Done: mypy, Ruff lint, Ruff formatting, backend tests, image build, Compose configuration, and integrated healthchecks pass on remote dev; API and migration compatibility are documented; tests cover changed behavior; no secret or generated coverage output is committed; and rollback is stated.
