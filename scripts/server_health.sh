#!/usr/bin/env bash
# Read-only health snapshot of the Hetzner server's three live experts.
#
# WHY A WRAPPER AND NOT A BARE SSH: a Claude Code permission rule matches on a
# command PREFIX, and everything after the host in an ssh invocation is one
# opaque argument the wildcard swallows — so an allow rule for
# `ssh ... mrhea@<host> *` grants writes just as readily as reads. Pinning the
# remote command here, in a file, is what makes "read-only" actually true; the
# allow rule then names this script rather than ssh.
#
# Keep every remote command in REMOTE non-mutating. Anything that writes,
# deploys, or restarts belongs in the deploy runbook (DOCUMENTATION.md), which
# is a deliberate, prompted action — not this.
#
# Repo root is derived from this script's location so the same file works from
# any checkout path.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."

KEY=~/.ssh/id_ed25519
HOST=mrhea@62.238.20.66
BASE=/home/mrhea/HealysBacktester

# The remote command is a fixed heredoc, never built from arguments — this
# script takes no arguments precisely so nothing can be injected into it.
read -r -d '' REMOTE <<REMOTE_EOF || true
set -u
cd "$BASE" || exit 1

echo "=== host ==="
date -u '+%Y-%m-%dT%H:%M:%SZ  uptime:'
uptime

echo
echo "=== cron lines (the three experts) ==="
crontab -l 2>/dev/null | grep -E 'v3_scan|v4_scan|scan' || echo "(no scan lines found)"

echo
echo "=== log freshness ==="
for f in logs/*cron*.log; do
  [ -e "\$f" ] || continue
  printf '%s  %s  %s bytes\n' "\$f" "\$(date -u -r "\$f" '+%Y-%m-%dT%H:%M:%SZ')" "\$(stat -c %s "\$f")"
done

echo
echo "=== rate limiting (429s / throttling) per log ==="
for f in logs/*cron*.log; do
  [ -e "\$f" ] || continue
  n=\$(grep -ciE 'http.?429|status.?(code)?.?429|error.?429|429 client|too many requests|rate.?limit|throttl' "\$f" 2>/dev/null || true)
  printf '%s: %s\n' "\$f" "\${n:-0}"
done

echo
echo "=== most recent 429 lines (shape + when) ==="
for f in logs/v4_cron.log logs/v31_cron.log logs/live_cron.log; do
  [ -e "\$f" ] || continue
  echo "--- \$f ---"
  grep -iE 'http.?429|status.?(code)?.?429|error.?429|429 client|too many requests|rate.?limit|throttl' "\$f" 2>/dev/null | tail -n 3 || true
done

echo
echo "=== errors / tracebacks per log ==="
for f in logs/*cron*.log; do
  [ -e "\$f" ] || continue
  n=\$(grep -ciE 'traceback|error|exception' "\$f" 2>/dev/null || true)
  printf '%s: %s\n' "\$f" "\${n:-0}"
done

echo
echo "=== most recent error lines (shape check — counts alone lie) ==="
for f in logs/v4_cron.log logs/v31_cron.log logs/heartbeat_cron.log logs/fa_cron.log; do
  [ -e "\$f" ] || continue
  echo "--- \$f ---"
  grep -iE 'traceback|error|exception' "\$f" 2>/dev/null | tail -n 3 || true
done

echo
echo "=== last 15 lines, v4 expert ==="
tail -n 15 logs/v4_cron.log 2>/dev/null || echo "(no v4_cron.log)"
REMOTE_EOF

exec ssh -i "$KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 \
  "$HOST" "$REMOTE"
