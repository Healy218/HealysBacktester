# ETFE setup and capture commands

Use the [current-state index](../CURRENT_STATE.md#october-4-etfe-fresh-alpaca-setup)
for selected roots, the [scope](../specs/ETFE_SCOPE_ALPACA_20261004.json),
[five-DTE amendment](../specs/ETFE_DTE_20261004.md) and
[fresh collection contract](../specs/ETFE_FRESH_ACQUISITION_20261003.md) for policy.
The [roadmap sequence](../../ROADMAP.md#etfe-first-run-sequence) owns ordering.
No command here deploys a model or starts training.

## Current setup

From the repository root, inspect the selected v3 setup:

```bash
./venv/bin/python scripts/prepare_etfe_current.py verify --root nn_meta/validation/etfe-setup-20261004-alpaca-r0
```

For an intentional successor preparation, use `prepare` with a fresh direct
`nn_meta/validation/etfe-*` root. Saved plans/source snapshots are immutable.
The v3 scope retains strategy specifications but imports no old market data,
features, labels or models. New entry/roll consumers must apply
`purchase_policy.check_purchase` at the actual timezone-aware attempt and obey
all other price/cash/identity/session guards; DTE eligibility alone is not a fill.

## Fresh raw acquisition

The CLI supports `prepare-bootstrap`, `prepare-options --parent ...`, `run`
and `audit`, with `--root` required. Roots must be direct children of
`nn_meta/data_cache_etfe/` named `alpaca-fresh-*`. Preparation requires a fresh
root. `run` resumes an existing source-bound plan and never overwrites a page.

```bash
./venv/bin/python scripts/acquire_etfe_alpaca.py audit --root nn_meta/data_cache_etfe/alpaca-fresh-20261004-options-r0
```

Use `run` on that selected root only when unfinished work is intended; completed
partitions issue no new requests. `--request-budget` can reduce the plan's hard
ceiling for controlled interruption. Nonzero exit means incomplete capture or a
stop condition; inspect unique `runs/*.json` and failed `attempts/*/receipt.json`.
Do not count request-budget exhaustion, HTTP errors or pending tokens as empty
history. Preserve orphan attempts after interruption; only hash-verified page
pointers are committed. A source change requires a successor root, not in-place
rebinding. Respect persisted provider wait deadlines before resumption.

`prepare-options` consumes only the fresh stock/discovery parent to select a
fixed transport sample. It does not implement full demand or historical chain
eligibility; same-day samples may be fetched but are not eligible purchases.
`iter_records` retains exact native fields and a per-page occurrence identity.
Typed normalization and full coverage are separate consumers still to implement.

Only root `.env` Alpaca pairs are loaded: data `ALPACA_API_KEY` /
`ALPACA_API_SECRET`, discovery `ALPACA_PAPER_API_KEY` /
`ALPACA_PAPER_API_SECRET`. No unrelated selectors are exported. Never print or
commit credentials. This transport uses serial rate limiting; future parallel
build workers must use the shared autosizer and measured memory budget.

## Preserved earlier evidence

The v1 midpoint and v2 VWAP preparations remain historical consumers. Verify
with their own `verify_etfe_setup.py` / `verify_etfe_vwap.py` commands when needed;
do not regenerate old plans or relabel their data as v3. The VWAP reference
component remains valid as a reference, not a complete execution model.

`./venv/bin/python scripts/verify_etfe_contract.py` verifies the original four
component declarations and portable source evidence. Its H1/R1/R2/P1 output
reports that historical revision, not the current collection authorization.
Apply the fresh-acquisition and DTE successors for current work. Historical
option quotes remain unsupported; do not repeat their diagnostics.
