#!/usr/bin/env bash
# Full expanded v6 freeze. Preview by default; --run executes after all gates.
# Supply a named campaign, repaired candidate, and the sealed TV13/tick input
# manifest plus its separately recorded SHA256. Explicit comparison deferral:
# NN_META_V6_PARITY_POLICY=deferred, with the matching unverified contract.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
: "${NN_META_CAMPAIGN:?Set a new expanded v6 campaign name}"
: "${NN_META_DATA_CANDIDATE:?Set the sealed corrected data candidate}"
: "${NN_META_V6_INPUTS:?Set the sealed TV13 and option tick input manifest}"
: "${NN_META_V6_INPUTS_SHA256:?Set its separately recorded SHA256}"
export NN_META_V6_EXPANDED=1
exec bash scripts/run_research_local.sh --campaign "$NN_META_CAMPAIGN" --pool v6 --stage freeze "$@"
