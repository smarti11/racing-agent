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

# Prefer absolute SQLite path so launchd cwd quirks don't break the DB
export DATABASE_URL="${DATABASE_URL:-file:${DB_PATH}}"
export PORT

# Resolve pnpm / node for launchd (minimal PATH)
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${HOME}/.local/share/pnpm:${PATH}"

if command -v pnpm >/dev/null 2>&1; then
  exec pnpm --filter web start -- --port "$PORT"
fi

# Fallback: next binary from node_modules
NEXT_BIN="${ROOT}/node_modules/.bin/next"
if [[ -x "$NEXT_BIN" ]]; then
  cd "$WEB"
  exec "$NEXT_BIN" start --port "$PORT"
fi

echo "pnpm/next not found. Install Node 20+ and run ./scripts/mac-mini-setup.sh" >&2
exit 1
