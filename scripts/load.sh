#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    echo "No .env file. Run scripts/init-env.sh first." >&2
    exit 1
fi
set -a
. ./.env
set +a

venv=loader/.venv
if ! "$venv/bin/python" -c 'import jsm_loader' 2>/dev/null; then
    echo "First run: installing the loader. This takes about a minute."
    python3 -m venv "$venv"
    "$venv/bin/python" -m pip install --quiet --upgrade pip
    "$venv/bin/python" -m pip install --quiet ./loader
fi

PGHOST=127.0.0.1 \
    PGPORT=${DB_PORT:-5433} \
    PGDATABASE=${POSTGRES_DB:?Set POSTGRES_DB in .env} \
    PGUSER=${POSTGRES_USER:?Set POSTGRES_USER in .env} \
    PGPASSWORD=${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env} \
    ANALYST_USER=${ANALYST_USER:?Set ANALYST_USER in .env} \
    ANALYST_PASSWORD=${ANALYST_PASSWORD:?Set ANALYST_PASSWORD in .env} \
    SOURCE_DIR=data/source \
    exec "$venv/bin/python" -m jsm_loader
