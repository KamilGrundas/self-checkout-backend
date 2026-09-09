# Backend repository instructions

FastAPI/SQLModel code is in `app/`, API tests in `tests/`, and Alembic
migrations in `app/alembic/versions`. Start at the workspace root when
available and read the applicable parent instructions; do not copy host-local
policy into this repository.

Preserve existing changes and work on `main`. Do not create task branches or
pull requests in the standard workflow. Commit, push, deployment, and migration
against a live database require separate explicit approval. Never rewrite an
applied migration; add a new migration when schema evolution is needed.

Run `bash scripts/lint.sh` and the relevant test command when dependencies are
available. Build validation uses the Dockerfile. Integration validation uses a
locally selected environment and is not assumed by repository checks.

Configuration uses generic database, S3-compatible storage, OIDC, and
OpenAI-compatible vision inference contracts. Do not add host names, provider
brands, concrete origins, or runtime-specific assumptions. Browser image URLs
use the configured `BACKEND_PUBLIC_URL`, not internal S3 DNS names.
