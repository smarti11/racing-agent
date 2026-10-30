#!/bin/bash
# Start GoodCart Next.js in production mode (port 3000 by default).
# Used by LaunchAgent and for manual runs.
#
# Usage:
#   ./scripts/run-web.sh
#   PORT=3001 ./scripts/run-web.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB="${ROOT}/apps/web"
PORT="${PORT:-3000}"
DB_PATH="${ROOT}/packages/db/prisma/dev.db"

cd "$ROOT"

if [[ ! -d "${WEB}/.next" ]]; then
  echo "No production build found. Run ./scripts/mac-mini-setup.sh first." >&2
  exit 1
fi

if [[ ! -f "${WEB}/.env" ]]; then
  echo "Missing ${WEB}/.env — run ./scripts/mac-mini-setup.sh first." >&2
  exit 1
fi

export DATABASE_URL="${DATABASE_URL:-file:${DB_PATH}}"
export PORT

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${HOME}/.local/share/pnpm:${PATH}"

# Bind 0.0.0.0 so Tailscale / LAN phones can reach the Mini (not just localhost).
# Use `exec next` (not `pnpm start -- --port`) — pnpm was forwarding "--" as a path.
cd "$WEB"
HOST="${HOST:-0.0.0.0}"
NEXT_BIN="${ROOT}/node_modules/.bin/next"
if [[ -x "$NEXT_BIN" ]]; then
  exec "$NEXT_BIN" start -H "$HOST" -p "$PORT"
fi

if command -v pnpm >/dev/null 2>&1; then
  exec pnpm exec next start -H "$HOST" -p "$PORT"
fi

echo "next binary not found. Run ./scripts/mac-mini-setup.sh" >&2
exit 1
