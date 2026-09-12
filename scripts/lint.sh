#!/usr/bin/env bash

set -e
set -x

mypy app
ty check app --exclude app/alembic --ignore unused-type-ignore-comment
ruff check app
ruff format app --check
