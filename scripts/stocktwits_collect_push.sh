#!/usr/bin/env bash
# Home-box only: collect StockTwits (residential IP — server is Cloudflare-
# blocked) and push the two StockTwits archives to the server, which merges
# them (archive.append dedupes; the home box is the sole StockTwits writer).
#
# Runs hourly from the home box (systemd timer on Pop!_OS; was Windows Task
# Scheduler under WSL). Repo root is derived from this script's location so the
# same file works from any checkout path.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."

# collect ONLY stocktwits here (edgar/news/reddit run on the server)
FA_SKIP_COLLECTORS=edgar,news,reddit ./venv/bin/python -m fa.collect

# push both StockTwits archives to the server (append-only; rsync creates
# remote dirs; the home box is the sole writer so a straight mirror is safe)
KEY=~/.ssh/id_ed25519
BASE=/home/mrhea/HealysBacktester/fa/archive
for src in stocktwits stocktwits_sentiment; do
  [ -d "fa/archive/$src" ] || continue
  rsync -az -e "ssh -i $KEY -o StrictHostKeyChecking=accept-new" \
    "fa/archive/$src/" "mrhea@62.238.20.66:$BASE/$src/"
done
echo "stocktwits collect+push done $(date -u +%FT%TZ)"
