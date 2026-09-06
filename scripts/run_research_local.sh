#!/usr/bin/env bash
# Preview explicit stages of an isolated home-box research campaign.
# Add --run only after source/data admission and the printed plan are ready.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
. scripts/lib/autosize.sh
export PYTHONDONTWRITEBYTECODE=1
export RESEARCH_WORKERS_DEFAULT
RESEARCH_WORKERS_DEFAULT=$(autosize_workers 5000)
exec ./venv/bin/python -m scripts.research_local "$@"
