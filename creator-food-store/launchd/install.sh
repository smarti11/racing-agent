#!/bin/bash
# Install LaunchAgent so GoodCart comes back after a Mac mini reboot.
#
# Usage (on the Mac mini, from creator-food-store/):
#   ./scripts/mac-mini-setup.sh     # first time: install, seed, build
#   ./launchd/install.sh            # register + start web on port 3000
#   ./launchd/install.sh --port 3001
#   ./launchd/uninstall.sh          # stop + remove
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.smarti11.goodcart.web"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
PORT="${PORT:-3000}"
RUN_WEB="${ROOT}/scripts/run-web.sh"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="${2:?--port requires a value}"
      shift 2
      ;;
    --port=*)
      PORT="${1#*=}"
      shift
      ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

chmod +x "$RUN_WEB" "${ROOT}/scripts/"*.sh "${ROOT}/launchd/"*.sh 2>/dev/null || true

if [[ ! -d "${ROOT}/apps/web/.next" ]]; then
  echo "No production build found." >&2
  echo "Run first:  ./scripts/mac-mini-setup.sh" >&2
  exit 1
fi

mkdir -p "$AGENTS_DIR" "${ROOT}/logs"

PLIST="${AGENTS_DIR}/${LABEL}.plist"
PATH_VALUE="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${HOME}/.local/share/pnpm"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${RUN_WEB}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${ROOT}/logs/${LABEL}.out.log</string>
  <key>StandardErrorPath</key>
  <string>${ROOT}/logs/${LABEL}.err.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>${PATH_VALUE}</string>
    <key>PORT</key>
    <string>${PORT}</string>
    <key>DATABASE_URL</key>
    <string>file:${ROOT}/packages/db/prisma/dev.db</string>
    <key>HOME</key>
    <string>${HOME}</string>
  </dict>
</dict>
</plist>
EOF

UID_NUM="$(id -u)"
launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/${UID_NUM}" "$PLIST"
launchctl enable "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
launchctl kickstart -k "gui/${UID_NUM}/${LABEL}" 2>/dev/null || launchctl load "$PLIST"

echo "Installed + started ${LABEL}"
echo
echo "Check:"
echo "  launchctl print gui/\$(id -u)/${LABEL} | head"
echo "  lsof -nP -iTCP:${PORT} -sTCP:LISTEN"
echo "  curl -s -o /dev/null -w '%{http_code}\\n' http://127.0.0.1:${PORT}/"
echo
echo "Logs:"
echo "  tail -f ${ROOT}/logs/${LABEL}.out.log"
echo "  tail -f ${ROOT}/logs/${LABEL}.err.log"
echo
echo "Open: http://127.0.0.1:${PORT}/"
echo "  /@grocerygirl  /discover"
echo
echo "Public URL (optional): ./scripts/tunnel.sh"
