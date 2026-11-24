#!/bin/bash
# Optional Cloudflare quick tunnel → public HTTPS URL for the Mac mini host.
#
# Usage (while GoodCart is running on PORT):
#   ./scripts/tunnel.sh
#   PORT=3000 ./scripts/tunnel.sh
#
# Installs cloudflared to ~/bin if missing (macOS arm64/amd64).
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-3000}"
BIN_DIR="${HOME}/bin"
CLOUDFLARED="${BIN_DIR}/cloudflared"
LOG="${ROOT}/logs/goodcart-tunnel.log"

mkdir -p "$BIN_DIR" "${ROOT}/logs"

arch="$(uname -m)"
case "$arch" in
  arm64) CF_ARCH="darwin-arm64" ;;
  x86_64) CF_ARCH="darwin-amd64" ;;
  *)
    echo "Unsupported arch: $arch" >&2
    exit 1
    ;;
esac

if [[ ! -x "$CLOUDFLARED" ]]; then
  if command -v cloudflared >/dev/null 2>&1; then
    CLOUDFLARED="$(command -v cloudflared)"
  elif command -v brew >/dev/null 2>&1; then
    echo "==> Installing cloudflared via Homebrew"
    brew install cloudflare/cloudflare/cloudflared
    CLOUDFLARED="$(command -v cloudflared)"
  else
    echo "==> Downloading cloudflared (${CF_ARCH})"
    curl -fsSL \
      "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-${CF_ARCH}" \
      -o "$CLOUDFLARED"
    chmod +x "$CLOUDFLARED"
  fi
fi

if ! curl -sf "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
  echo "Nothing listening on port ${PORT}." >&2
  echo "Start GoodCart first: ./scripts/run-web.sh  (or ./launchd/install.sh)" >&2
  exit 1
fi

echo "==> Tunneling http://127.0.0.1:${PORT} → trycloudflare.com"
echo "    Logs: $LOG"
echo "    Press Ctrl+C to stop."
echo

exec "$CLOUDFLARED" tunnel --url "http://127.0.0.1:${PORT}" 2>&1 | tee "$LOG"
