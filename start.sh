#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
umask 077
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import flask, psycopg' 2>/dev/null; then
  .venv/bin/pip install -r requirements.txt
fi
mkdir -p .pgsocket
chmod 700 .pgsocket
if [ ! -f .pgdata/PG_VERSION ]; then
  initdb -D "$PWD/.pgdata" --auth-local=trust --auth-host=scram-sha-256 > postgres-init.log
fi
if ! pg_ctl -D "$PWD/.pgdata" status >/dev/null 2>&1; then
  pg_ctl -D "$PWD/.pgdata" -l "$PWD/postgres.log" -o "-p 55438 -k $PWD/.pgsocket -h 127.0.0.1" start
fi
if [ ! -f .env ]; then
  .venv/bin/python setup_local.py
fi
exec .venv/bin/python app.py
