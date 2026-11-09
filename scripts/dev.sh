#!/usr/bin/env bash
# Start CreatorShield AI locally (native processes - lighter than Docker on a 16 GB Mac).
#
#   scripts/dev.sh          start Postgres, Redis, API, worker, frontend
#   scripts/stop.sh         stop API, worker, frontend (and optionally the DB/Redis)
#
# Postgres/Redis are started for this session only; they do not auto-start at login.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOGS="$ROOT/var/logs"
PIDS="$ROOT/var/pids"
mkdir -p "$LOGS" "$PIDS"

PG_PREFIX="$(brew --prefix postgresql@17)"
PG_DATA="$(brew --prefix)/var/postgresql@17"

if ! pg_isready -q; then
  echo "• starting PostgreSQL"
  "$PG_PREFIX/bin/pg_ctl" -D "$PG_DATA" -l "$LOGS/postgres.log" -w start >/dev/null
fi
if ! redis-cli ping >/dev/null 2>&1; then
  echo "• starting Redis"
  redis-server --daemonize yes --logfile "$LOGS/redis.log" --dir "$ROOT/var" >/dev/null
fi

[ -f "$ROOT/backend/.env" ] || { cp "$ROOT/.env.example" "$ROOT/backend/.env"; echo "• created backend/.env from .env.example"; }
if ! grep -qE '^TOKEN_ENCRYPTION_KEY=.+' "$ROOT/backend/.env"; then
  KEY="$("$ROOT/backend/.venv/bin/python" -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
  grep -q '^TOKEN_ENCRYPTION_KEY=' "$ROOT/backend/.env" \
    && sed -i '' "s|^TOKEN_ENCRYPTION_KEY=.*|TOKEN_ENCRYPTION_KEY=$KEY|" "$ROOT/backend/.env" \
    || printf '\nTOKEN_ENCRYPTION_KEY=%s\n' "$KEY" >> "$ROOT/backend/.env"
  chmod 600 "$ROOT/backend/.env"
  echo "• generated TOKEN_ENCRYPTION_KEY in backend/.env (keep it; changing it invalidates stored connections)"
fi
[ -f "$ROOT/frontend/.env.local" ] || echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > "$ROOT/frontend/.env.local"

cd "$ROOT/backend"
echo "• applying database migrations"
.venv/bin/alembic upgrade head >/dev/null

start() { # name, logfile, command...
  local name=$1 log=$2; shift 2
  if [ -f "$PIDS/$name.pid" ] && kill -0 "$(cat "$PIDS/$name.pid")" 2>/dev/null; then
    echo "• $name already running (pid $(cat "$PIDS/$name.pid"))"; return
  fi
  nohup "$@" >"$LOGS/$log" 2>&1 &
  echo $! >"$PIDS/$name.pid"
  echo "• started $name (pid $!, log var/logs/$log)"
}

start api api.log .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
start worker worker.log .venv/bin/python -m app.worker
cd "$ROOT/frontend"
start frontend frontend.log npm run dev -- --hostname 127.0.0.1 --port 3000

echo "• waiting for services"
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1 && curl -fsS -o /dev/null http://127.0.0.1:3000/ 2>/dev/null; then
    echo
    echo "CreatorShield AI is running:  http://localhost:3000"
    echo "API docs:                      http://localhost:8000/docs"
    exit 0
  fi
  sleep 1
done
echo "Services did not become healthy in 60s - check var/logs/*.log" >&2
exit 1
