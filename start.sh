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
url="http://127.0.0.1:5084/login"
.venv/bin/python app.py &
app_pid=$!
trap 'kill "$app_pid" 2>/dev/null || true; wait "$app_pid" 2>/dev/null || true' EXIT INT TERM
for _ in $(seq 1 60); do
  if ! kill -0 "$app_pid" 2>/dev/null; then
    wait "$app_pid"
  fi
  if curl --silent --show-error --fail "$url" -o /dev/null 2>/dev/null; then
    if command -v xdg-open >/dev/null 2>&1; then xdg-open "$url" >/dev/null 2>&1 || true; fi
    break
  fi
  sleep 0.5
done
wait "$app_pid"
