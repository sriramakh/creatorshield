#!/usr/bin/env bash
# Browser E2E for connected accounts against the FAKE platform server.
# Temporarily restarts the API + worker with test overrides (fake Instagram /
# Google endpoints, mock AI, throwaway encryption key), runs Playwright, then
# restores the normal stack. No real platform or paid API is called.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOGS="$ROOT/var/logs"; PIDS="$ROOT/var/pids"; mkdir -p "$LOGS" "$PIDS"
FAKE=http://127.0.0.1:8099

stop_app() {
  for n in api worker; do
    [ -f "$PIDS/$n.pid" ] && kill "$(cat "$PIDS/$n.pid")" 2>/dev/null; rm -f "$PIDS/$n.pid"
  done
  sleep 1
}

cd "$ROOT/backend"
FAKE_CDN_BASE="$FAKE/cdn" nohup .venv/bin/uvicorn tests.fake_platforms:app --host 127.0.0.1 --port 8099 \
  >"$LOGS/fake_platforms.log" 2>&1 &
FAKE_PID=$!

stop_app
export AI_PROVIDER=mock \
  TOKEN_ENCRYPTION_KEY="$(.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
  INSTAGRAM_APP_ID=e2e-ig INSTAGRAM_APP_SECRET=e2e-ig-secret \
  INSTAGRAM_OAUTH_URL="$FAKE/oauth/authorize" INSTAGRAM_TOKEN_URL="$FAKE/oauth/access_token" \
  INSTAGRAM_GRAPH_URL="$FAKE" \
  GOOGLE_CLIENT_ID=e2e-google GOOGLE_CLIENT_SECRET=e2e-google-secret \
  GOOGLE_AUTH_URL="$FAKE/o/oauth2/v2/auth" GOOGLE_TOKEN_URL="$FAKE/token" \
  GOOGLE_REVOKE_URL="$FAKE/revoke" YOUTUBE_API_URL="$FAKE/youtube/v3" \
  YOUTUBE_CAPTIONS_SCOPE=true IMPORT_MEDIA_HOSTS='["127.0.0.1"]'
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 >"$LOGS/api-e2e.log" 2>&1 & echo $! >"$PIDS/api.pid"
nohup .venv/bin/python -m app.worker >"$LOGS/worker-e2e.log" 2>&1 & echo $! >"$PIDS/worker.pid"
for _ in $(seq 1 30); do curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1 && curl -fsS "$FAKE/docs" >/dev/null 2>&1 && break; sleep 1; done

cd "$ROOT/frontend"
E2E_FAKE_PLATFORMS=1 npx playwright test e2e/import-from-account.spec.ts
STATUS=$?

# Remove E2E data (connections made with the throwaway key, imported analyses).
cd "$ROOT/backend"
.venv/bin/python - <<'EOF'
from sqlalchemy import select
from app.db import get_sessionmaker
from app.jobs import delete_analysis
from app.models import Analysis, PlatformConnection
with get_sessionmaker()() as db:
    for a in db.scalars(select(Analysis).where(Analysis.source != "upload")).all():
        delete_analysis(db, a)
    for c in db.scalars(select(PlatformConnection)).all():
        db.delete(c)
    db.commit()
EOF

kill $FAKE_PID 2>/dev/null
unset AI_PROVIDER TOKEN_ENCRYPTION_KEY INSTAGRAM_APP_ID INSTAGRAM_APP_SECRET INSTAGRAM_OAUTH_URL \
  INSTAGRAM_TOKEN_URL INSTAGRAM_GRAPH_URL GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET GOOGLE_AUTH_URL \
  GOOGLE_TOKEN_URL GOOGLE_REVOKE_URL YOUTUBE_API_URL YOUTUBE_CAPTIONS_SCOPE IMPORT_MEDIA_HOSTS
stop_app
"$ROOT/scripts/dev.sh" >/dev/null && echo "• normal stack restored"
exit $STATUS
