# ETFE setup and integrity commands

Use the [ETFE specification](../specs/ETFE.md) for scope and
[CURRENT_STATE](../CURRENT_STATE.md#october-3-etfe-setup) for the selected root.
These commands prepare or inspect a new expert; none launches training.

From `/home/healy/Coding/HealysBacktester`, verify the selected setup:

```bash
./venv/bin/python scripts/verify_etfe_setup.py --setup nn_meta/validation/etfe-setup-20261003-r0
```

For an intentional new preparation revision, use a fresh output name:

```bash
NN_META_POOL=etfe ./venv/bin/python scripts/prepare_etfe.py --output nn_meta/validation/etfe-setup-YYYYMMDD-rN
```

The launcher rejects unrelated inherited campaign/research selectors. It uses
the registered parameter grids but neither invokes old planners nor imports
V7 model/checkpoint/data artifacts. Do not edit a saved plan or overwrite its
output to bypass a mismatch. Keep prior source snapshots and probe evidence.

Provider diagnostics require root `.env` data credentials `ALPACA_API_KEY` and
`ALPACA_API_SECRET`, and paper metadata credentials `ALPACA_PAPER_API_KEY` and
`ALPACA_PAPER_API_SECRET`. Only these values are read; other `.env` selectors
are not exported into the runtime. Never print or commit credentials.

The selected live results already exist; do not repeat them unless investigating
a change or unresolved question. For a new bounded observation, choose a fresh
`probe-*` child beside the selected `plan.json`:

```bash
./venv/bin/python scripts/probe_etfe_alpaca.py --plan nn_meta/validation/etfe-setup-YYYYMMDD-rN/plan.json --output nn_meta/validation/etfe-setup-YYYYMMDD-rN/probe-rN
./venv/bin/python scripts/probe_etfe_history_boundary.py --setup nn_meta/validation/etfe-setup-YYYYMMDD-rN --output nn_meta/validation/etfe-setup-YYYYMMDD-rN/probe-boundary-rN
```

Check HTTP results, transport errors, pagination and raw receipts. A 404 is not
empty-but-complete history; an early trade sample is not a provider-global floor;
today's expired-contract response is not a historical point-in-time catalogue.
`PREPARED.json` is not admission: ready-for-build/training stays false until the
ETFE gates have actual input, execution, feature and resource evidence.
