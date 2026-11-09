#!/usr/bin/env bash
# Stop CreatorShield processes. Pass --all to also stop PostgreSQL and Redis.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIDS="$ROOT/var/pids"

for name in frontend worker api; do
  f="$PIDS/$name.pid"
  if [ -f "$f" ] && kill -0 "$(cat "$f")" 2>/dev/null; then
    pkill -TERM -P "$(cat "$f")" 2>/dev/null
    kill -TERM "$(cat "$f")" 2>/dev/null && echo "• stopped $name"
  fi
  rm -f "$f"
done

if [ "${1:-}" = "--all" ]; then
  redis-cli shutdown nosave >/dev/null 2>&1 && echo "• stopped Redis"
  "$(brew --prefix postgresql@17)/bin/pg_ctl" -D "$(brew --prefix)/var/postgresql@17" stop -m fast >/dev/null 2>&1 \
    && echo "• stopped PostgreSQL"
fi
