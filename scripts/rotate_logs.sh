#!/usr/bin/env bash
# Rotate the scanner logs as the service user (no sudo on the server).
# logrotate refuses a config that is group/world-writable, and the server's
# umask checks files out as 664, so fix the mode before every run.
set -euo pipefail
cd "$(dirname "$0")/.."
CONF=deploy/logrotate/healys.conf
STATE="${HOME}/.logrotate.healys.state"
chmod 644 "$CONF"
mkdir -p logs
echo "=== logrotate $(date -u +%FT%TZ) ==="
/usr/sbin/logrotate -s "$STATE" "$CONF"
