#! /usr/bin/env bash

set -e
set -x

export PYTHONPATH="/app/backend${PYTHONPATH:+:$PYTHONPATH}"

# Run migrations
alembic upgrade head

# Create initial data in DB
python -m app.initial_data
