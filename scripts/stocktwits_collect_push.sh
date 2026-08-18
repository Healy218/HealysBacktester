#!/usr/bin/env bash
# Home-box only: collect StockTwits (residential IP — server is Cloudflare-
# blocked) and push the two StockTwits archives to the server, which merges
# them (archive.append dedupes; the home box is the sole StockTwits writer).
#
# Runs hourly from the home box (systemd timer; see deploy/systemd/). Repo root
# is derived from this script's location so the same file works from any
# checkout path.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."

KEY=~/.ssh/id_ed25519
HOST=mrhea@62.238.20.66
BASE=/home/mrhea/HealysBacktester/fa/archive
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new"
SOURCES="stocktwits stocktwits_sentiment"

# PULL BEFORE COLLECT — this is the guard, not a convenience.
#
# The push below is a straight file mirror, and the archive is one parquet per
# month (fa/config.py: <source>/<yyyy-mm>.parquet). So "the home box is the
# sole writer, a mirror is safe" holds only while this box still HAS the full
# local history. A reinstall, a fresh clone, or a stray rm breaks that silently
# — the collector then writes a brand-new <yyyy-mm>.parquet containing just
# this run's rows, and rsync happily overwrites the server's month with it.
# That is not hypothetical: on 2026-08-18 the restored box had no fa/archive at
# all, and the first timed run would have replaced 1620 rows with ~30.
#
# Pulling first makes the mirror safe by construction: whatever the server has,
# we have, before append adds to it. --update means the pull only ever fills
# gaps — a file that is newer here (say last hour's push failed) is never
# clobbered by the server's older copy. mkdir -p on the remote first so a
# missing directory cannot be confused with a network failure; then set -e
# makes any real pull failure abort BEFORE we collect or push. Fail closed:
# no pull, no push.
$SSH "$HOST" "mkdir -p $(for s in $SOURCES; do printf '%s ' "$BASE/$s"; done)"
for src in $SOURCES; do
  mkdir -p "fa/archive/$src"
  rsync -az --update -e "$SSH" "$HOST:$BASE/$src/" "fa/archive/$src/"
done

# collect ONLY stocktwits here (edgar/news/reddit run on the server)
FA_SKIP_COLLECTORS=edgar,news,reddit ./venv/bin/python -m fa.collect

# push both StockTwits archives to the server (append-only; rsync creates
# remote dirs; safe because the pull above guarantees local ⊇ remote)
for src in $SOURCES; do
  [ -d "fa/archive/$src" ] || continue
  rsync -az -e "$SSH" "fa/archive/$src/" "$HOST:$BASE/$src/"
done
echo "stocktwits collect+push done $(date -u +%FT%TZ)"
