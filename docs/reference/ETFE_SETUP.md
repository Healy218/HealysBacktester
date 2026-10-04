# ETFE setup and integrity commands

Use the [ETFE specification](../specs/ETFE.md) for scope and
[CURRENT_STATE](../CURRENT_STATE.md#october-3-etfe-setup) for the selected root.
These commands prepare or inspect a new expert; none launches training.
The [first-run sequence](../../ROADMAP.md#etfe-first-run-sequence) and
[acceptance contract](../specs/ETFE_FIRST_RUN.md) define the remaining work.
Dataset-build, training, finalizer and expert-replay commands will be documented
only after their ETFE consumers exist and have passed their gates; do not
substitute V7 launch commands or infer launch permission from setup success.

From `/home/healy/Coding/HealysBacktester`, verify the selected setup:

```bash
./venv/bin/python scripts/verify_etfe_vwap.py --setup nn_meta/validation/etfe-setup-20261003-vwap-r1
```

For an intentional new preparation revision, use a fresh output name:

```bash
NN_META_POOL=etfe ./venv/bin/python scripts/prepare_etfe_vwap.py --predecessor nn_meta/validation/etfe-setup-20261003-r0 --output nn_meta/validation/etfe-setup-YYYYMMDD-vwap-rN
```

The launcher rejects unrelated inherited campaign/research selectors. It uses
the registered parameter grids but neither invokes old planners nor imports
V7 model/checkpoint/data artifacts. Do not edit a saved plan or overwrite its
output to bypass a mismatch. Keep prior source snapshots and probe evidence.

The [VWAP amendment](../specs/ETFE_VWAP_20261003.md) owns the selected pricing
semantics. `vwap_reference.reference_from_bar` consumes only provenance-checked
1Min option bars; it does not select contracts, simulate fills or admit data.
Verify the unchanged midpoint predecessor separately with
`./venv/bin/python scripts/verify_etfe_setup.py --setup nn_meta/validation/etfe-setup-20261003-r0`.
The old `prepare_etfe.py` and probes remain historical v1 consumers; do not use
them to regenerate a VWAP plan or bind new observations to its v2 scope.

Provider diagnostics require root `.env` data credentials `ALPACA_API_KEY` and
`ALPACA_API_SECRET`, and paper metadata credentials `ALPACA_PAPER_API_KEY` and
`ALPACA_PAPER_API_SECRET`. Only these values are read; other `.env` selectors
are not exported into the runtime. Never print or commit credentials.

The live diagnostic results already exist under the predecessor. Do not repeat
unsupported historical-quote requests. The following are historical v1 command
references only; a VWAP acquisition consumer must bind the v2 plan and its own
source/receipts before new capture:

```bash
./venv/bin/python scripts/probe_etfe_alpaca.py --plan nn_meta/validation/etfe-setup-YYYYMMDD-rN/plan.json --output nn_meta/validation/etfe-setup-YYYYMMDD-rN/probe-rN
./venv/bin/python scripts/probe_etfe_history_boundary.py --setup nn_meta/validation/etfe-setup-YYYYMMDD-rN --output nn_meta/validation/etfe-setup-YYYYMMDD-rN/probe-boundary-rN
```

Check HTTP results, transport errors, pagination and raw receipts. A 404 is not
empty-but-complete history; an early trade sample is not a provider-global floor;
today's expired-contract response is not a historical point-in-time catalogue.
`PREPARED.json` is not admission: ready-for-build/training stays false until the
ETFE gates have actual input, execution, feature and resource evidence.

## ETFE-0 contract verification

Run `./venv/bin/python scripts/verify_etfe_contract.py` to verify the versioned
[declarations](../specs/ETFE_CONTRACT_20261003.md), source snapshot and boundary
receipts. The portable evidence ZIP permits verification without local ignored
validation directories. Success verifies definitions only; H1/R1/R2/P1 remain
open and readiness remains false. The new bounded `probe_etfe_contract_boundary.py`
is a v2-bound diagnostic consumer; its ten live results are already retained.
