#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
exec ./venv/bin/python -m scripts.run_v6_next_stage --stage evaluate "$@"
