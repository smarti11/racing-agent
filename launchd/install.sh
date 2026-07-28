#!/bin/bash
# Install LaunchAgents so racing-agent sidecars (and optionally the agent)
# come back after a Mac mini reboot.
#
# Usage (on the Mac mini):
#   cd ~/agents/racing-agent
#   ./launchd/install.sh            # scratch + dashboard only
#   ./launchd/install.sh --with-agent
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL_PREFIX="com.smarti11.racing-agent"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
PYTHON="${ROOT}/venv/bin/python3"
WITH_AGENT=0

for arg in "$@"; do
  case "$arg" in
    --with-agent) WITH_AGENT=1 ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown arg: $arg" >&2
      exit 1
      ;;
  esac
done

if [[ ! -x "$PYTHON" ]]; then
  echo "Missing venv python at $PYTHON — create/activate venv first." >&2
  exit 1
fi

mkdir -p "$AGENTS_DIR" "${ROOT}/logs"

write_plist() {
  local label="$1"
  local prog="$2"
  shift 2
  local plist="${AGENTS_DIR}/${label}.plist"
  local args_xml=""
  local a
  for a in "$@"; do
    args_xml+="    <string>${a}</string>
"
  done

  cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${prog}</string>
${args_xml}  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${ROOT}/logs/${label}.out.log</string>
  <key>StandardErrorPath</key>
  <string>${ROOT}/logs/${label}.err.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/usr/local/bin:/usr/bin:/bin:${ROOT}/venv/bin</string>
  </dict>
</dict>
</plist>
EOF

  launchctl bootout "gui/$(id -u)/${label}" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$plist"
  launchctl enable "gui/$(id -u)/${label}" 2>/dev/null || true
  launchctl kickstart -k "gui/$(id -u)/${label}" 2>/dev/null || launchctl load "$plist"
  echo "Installed + started ${label}"
}

write_plist "${LABEL_PREFIX}.scratch" "$PYTHON" "${ROOT}/scratch_server.py"
write_plist "${LABEL_PREFIX}.dashboard" /bin/bash "${ROOT}/serve_dashboard.sh"

if [[ "$WITH_AGENT" -eq 1 ]]; then
  write_plist "${LABEL_PREFIX}.agent" "$PYTHON" "${ROOT}/racing_agent.py"
fi

echo
echo "Done. After reboot these should come back automatically."
echo "Check:"
echo "  launchctl print gui/\$(id -u)/${LABEL_PREFIX}.scratch | head"
echo "  lsof -nP -iTCP:8081 -sTCP:LISTEN"
echo "  lsof -nP -iTCP:8082 -sTCP:LISTEN"
