#!/usr/bin/env bash
# Full expanded v6 freeze. Preview by default; --run executes after all gates.
# Supply a named campaign, repaired candidate, and the reviewed TV13/tick input
# manifest plus its separately recorded SHA256.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
: "${NN_META_CAMPAIGN:?Set a new expanded v6 campaign name}"
: "${NN_META_DATA_CANDIDATE:?Set the sealed corrected data candidate}"
: "${NN_META_V6_INPUTS:?Set the reviewed TV13 and option tick input manifest}"
: "${NN_META_V6_INPUTS_SHA256:?Set its separately recorded SHA256}"
export NN_META_V6_EXPANDED=1
exec bash scripts/run_research_local.sh --campaign "$NN_META_CAMPAIGN" --pool v6 --stage freeze "$@"
