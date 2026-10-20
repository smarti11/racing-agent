#!/bin/bash
# Stop and remove the GoodCart LaunchAgent.
#
# Usage:
#   ./launchd/uninstall.sh
#
set -euo pipefail

LABEL="com.smarti11.goodcart.web"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
PLIST="${AGENTS_DIR}/${LABEL}.plist"
UID_NUM="$(id -u)"

launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
launchctl unload "$PLIST" 2>/dev/null || true

if [[ -f "$PLIST" ]]; then
  rm -f "$PLIST"
  echo "Removed $PLIST"
else
  echo "No plist at $PLIST (already uninstalled?)"
fi

echo "Stopped ${LABEL}"
echo "Verify port free:  lsof -nP -iTCP:3000 -sTCP:LISTEN"
