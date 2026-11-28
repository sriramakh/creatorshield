#!/usr/bin/env bash
# Browser E2E for connected accounts against the FAKE platform server.
# Temporarily restarts the API + worker with test overrides (fake Instagram /
# Google endpoints, mock AI, throwaway encryption key) on a DEDICATED database and
# storage directory, runs Playwright, then restores the normal stack.
# Your dev database and media are never read or written: the run refuses to start
# if the E2E database is the dev database, and cleanup only touches the E2E ones.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOGS="$ROOT/var/logs"; PIDS="$ROOT/var/pids"; mkdir -p "$LOGS" "$PIDS"
FAKE=http://127.0.0.1:8099
E2E_DB_NAME="${E2E_DB_NAME:-creatorshield_e2e}"
E2E_DATABASE_URL="${E2E_DATABASE_URL:-postgresql+psycopg://creatorshield:creatorshield_dev@localhost:5432/$E2E_DB_NAME}"
E2E_STORAGE_DIR="$ROOT/var/e2e-storage"

db_name() { printf '%s' "${1##*/}" | cut -d'?' -f1; }
DEV_DB_URL="$(grep -E '^DATABASE_URL=' "$ROOT/backend/.env" 2>/dev/null | tail -1 | cut -d= -f2-)"
DEV_DB_URL="${DEV_DB_URL:-postgresql+psycopg://creatorshield:creatorshield_dev@localhost:5432/creatorshield}"
if [ "$(db_name "$E2E_DATABASE_URL")" = "$(db_name "$DEV_DB_URL")" ] || [ "$(db_name "$E2E_DATABASE_URL")" = "creatorshield" ]; then
  echo "Refusing to run: the E2E database ($(db_name "$E2E_DATABASE_URL")) is the dev database." >&2
  exit 2
fi

stop_app() {
  for n in api worker; do
    [ -f "$PIDS/$n.pid" ] && kill "$(cat "$PIDS/$n.pid")" 2>/dev/null; rm -f "$PIDS/$n.pid"
  done
  sleep 1
}

cd "$ROOT/backend"
createdb -O creatorshield "$(db_name "$E2E_DATABASE_URL")" 2>/dev/null || true
rm -rf "$E2E_STORAGE_DIR"; mkdir -p "$E2E_STORAGE_DIR"
if ! DATABASE_URL="$E2E_DATABASE_URL" .venv/bin/alembic upgrade head >/dev/null; then
  echo "Could not migrate the E2E database $E2E_DATABASE_URL" >&2
  exit 1
fi

FAKE_CDN_BASE="$FAKE/cdn" nohup .venv/bin/uvicorn tests.fake_platforms:app --host 127.0.0.1 --port 8099 \
  >"$LOGS/fake_platforms.log" 2>&1 &
FAKE_PID=$!

stop_app
# Exported for the E2E API/worker only; environment variables take precedence over
# backend/.env, so the dev DATABASE_URL and STORAGE_DIR are not used.
export DATABASE_URL="$E2E_DATABASE_URL" STORAGE_DIR="$E2E_STORAGE_DIR" \
  AI_PROVIDER=mock MAINTENANCE_INTERVAL_SECONDS=0 \
  TOKEN_ENCRYPTION_KEY="$(.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
  INSTAGRAM_APP_ID=e2e-ig INSTAGRAM_APP_SECRET=e2e-ig-secret \
  INSTAGRAM_OAUTH_URL="$FAKE/oauth/authorize" INSTAGRAM_TOKEN_URL="$FAKE/oauth/access_token" \
  INSTAGRAM_GRAPH_URL="$FAKE" \
  GOOGLE_CLIENT_ID=e2e-google GOOGLE_CLIENT_SECRET=e2e-google-secret \
  GOOGLE_AUTH_URL="$FAKE/o/oauth2/v2/auth" GOOGLE_TOKEN_URL="$FAKE/token" \
  GOOGLE_REVOKE_URL="$FAKE/revoke" YOUTUBE_API_URL="$FAKE/youtube/v3" \
  YOUTUBE_CAPTIONS_SCOPE=true IMPORT_MEDIA_HOSTS='["127.0.0.1"]' \
  QUEUE_NAME=creatorshield-e2e
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 >"$LOGS/api-e2e.log" 2>&1 & echo $! >"$PIDS/api.pid"
nohup .venv/bin/python -m app.worker >"$LOGS/worker-e2e.log" 2>&1 & echo $! >"$PIDS/worker.pid"
for _ in $(seq 1 30); do curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1 && curl -fsS "$FAKE/docs" >/dev/null 2>&1 && break; sleep 1; done

cd "$ROOT/frontend"
E2E_FAKE_PLATFORMS=1 npx playwright test e2e/import-from-account.spec.ts
STATUS=$?

# Remove only what this run created: the dedicated E2E database's rows and storage.
cd "$ROOT/backend"
stop_app
kill $FAKE_PID 2>/dev/null
.venv/bin/python - <<'EOF'
import os
from app.config import get_settings
from app.db import Base, get_engine
assert get_settings().database_url == os.environ["DATABASE_URL"]
with get_engine().begin() as conn:
    for table in reversed(Base.metadata.sorted_tables):
        if table.name != "alembic_version":
            conn.execute(table.delete())
EOF
rm -rf "$E2E_STORAGE_DIR"

unset DATABASE_URL STORAGE_DIR AI_PROVIDER MAINTENANCE_INTERVAL_SECONDS TOKEN_ENCRYPTION_KEY \
  INSTAGRAM_APP_ID INSTAGRAM_APP_SECRET INSTAGRAM_OAUTH_URL INSTAGRAM_TOKEN_URL INSTAGRAM_GRAPH_URL \
  GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET GOOGLE_AUTH_URL GOOGLE_TOKEN_URL GOOGLE_REVOKE_URL \
  YOUTUBE_API_URL YOUTUBE_CAPTIONS_SCOPE IMPORT_MEDIA_HOSTS QUEUE_NAME
"$ROOT/scripts/dev.sh" >/dev/null && echo "• normal stack restored"
exit $STATUS
