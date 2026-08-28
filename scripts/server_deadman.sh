#!/usr/bin/env bash
# Home-box dead-man for the Hetzner server (built after the 2026-08-27/28
# outage: a payment lock null-routed the server's IP Thursday 13:32Z and
# nobody noticed until Friday afternoon — two missed noon heartbeats were
# the only signal, and "no message" reads as "quiet market" by design).
#
# Hourly (systemd timer): probe SSH; on failure, page via Telegram from THIS
# box (the server can't page about its own network being dead — that is the
# whole point of a dead-man). State file prevents re-paging every hour for
# one incident: page on the FIRST failure after >=2 consecutive misses, then
# again every 12h while down, and once on recovery.
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."

HOST=mrhea@62.238.20.66
KEY=~/.ssh/id_ed25519
STATE=/tmp/healys_server_deadman.state   # "<consecutive_misses> <last_page_epoch>"
NOW=$(date +%s)
{ read -r MISSES LAST_PAGE < "$STATE"; } 2>/dev/null || { MISSES=0; LAST_PAGE=0; }

page() {
  ./venv/bin/python - "$1" <<'PY'
import sys
# Explicit path: find_dotenv() frame-walks and asserts when run from stdin.
try:
    from dotenv import load_dotenv; load_dotenv(".env")
except ImportError:
    pass
from nn_meta.live.notifier import get_notifier
get_notifier().send(sys.argv[1], title="Server dead-man")
PY
}

if ssh -i "$KEY" -o ConnectTimeout=15 -o BatchMode=yes "$HOST" true 2>/dev/null; then
  if [ "$MISSES" -ge 2 ]; then
    page "✅ Hetzner server reachable again after ${MISSES} failed hourly checks."
  fi
  echo "0 0" > "$STATE"
  echo "$(date -u +%FT%TZ) ok"
else
  MISSES=$((MISSES + 1))
  # First page at 2 consecutive misses (~2h, rides out reboots/blips);
  # re-page every 12h while the outage continues.
  if { [ "$MISSES" -eq 2 ]; } || { [ "$MISSES" -gt 2 ] && [ $((NOW - LAST_PAGE)) -ge 43200 ]; }; then
    page "🚨 Hetzner server UNREACHABLE for ${MISSES} consecutive hourly checks (SSH 62.238.20.66). Scanners/digests are likely dark — check console.hetzner.cloud."
    LAST_PAGE=$NOW
  fi
  echo "$MISSES $LAST_PAGE" > "$STATE"
  echo "$(date -u +%FT%TZ) MISS $MISSES"
fi
