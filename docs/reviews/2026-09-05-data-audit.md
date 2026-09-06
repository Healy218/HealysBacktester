# Data, execution and dataset audit — 2026-09-05

> Remediated in the review checkout. See [the repair report](2026-09-05-remediation.md) for current dispositions and validation. Findings below refer to the original audited commit.

Reviewed HEAD `f98ed265db3ce3faf4ba7abf8e6604671e3a1c90`. No source fixes or live actions. Reproductions used synthetic data under `/tmp`; this report is the only intentional workspace deliverable. Findings below describe code behavior, not estimates of how many production rows are affected.

## Confirmed findings

### D1 — P1: daily-bar compaction deletes legitimate history across flat-file partitions

**Location:** `nn_meta/download_universe.py:408-409`, deletion/swap at 418-420; producer `v3/derive_contracts.py:93-97`.

Compaction retains only the newest **ticker**, discarding every older row for that ticker. This assumes a newer part contains a complete contract lifetime. The original flat-file producer partitions by batches of 40 **days**, so an ordinary contract can have distinct dates in several parts. Historical contracts not refetched by the recent-life refresh retain that layout. The first automatic compaction after a refresh therefore deletes their earlier dates, then removes the old directory. Lost rows alter surface IV/volume history and may be outside the vendor's rolling entitlement.

**Reproduced:** two parts containing the same contract on January 2 and March 3, with no duplicate `(ticker,date)` keys, become a single March 3 row. Existing tests only exercise overlapping tickers with same-date duplicates or refreshed full lifetimes; they do not cover disjoint date partitions. Deduplicate by `(ticker,date)` with newest values winning, or prove complete-life provenance before replacing an entire ticker.

### D2 — P1: shared option-bar cache changes labels depending on DTE sweep order

**Location:** `options/execution.py:78-86`; shared executor consumers `nn_meta/baseline.py:253-261` and `nn_meta/build_meta_dataset.py:287-293`.

`Execution.bars` caches a provider response by OCC alone, although that response is sliced to the first request's `frm/to`. A short-DTE sweep can first request a June 13 contract on June 9. The next longer-DTE sweep needs that same contract on June 2, but receives the June 9-onward cached slice. The engine silently marks an otherwise fillable early trade unexecuted, or fills it late. Both freeze DTE selection and dataset labels depend on iteration order.

**Reproduced end-to-end:** using the existing test `SyntheticProvider`, June 6/June 13 expirations and June 2/June 9 trades, the first trade at DTE 10 is `executed=True` with a fresh executor but `False` after DTE 1 ran on the shared executor. Cache full contract life or track/extend request coverage.

### D3 — P1: v6 assembly disables point-in-time membership by default

**Location:** `nn_meta/build_meta_dataset.py:598-601`; intended universe contract `nn_meta/config.py:92-100`.

The CLI defaults membership to `config.POOL == "v5"`, while v6 uses the same union of historical PIT memberships and shared raw rows as v5. Standard `NN_META_POOL=v6 ... --assemble` therefore retains symbols outside their valid membership months, including the initial months before any frozen membership exists. The union alone is not a point-in-time universe. This silently invalidates the advertised v6 PIT scope unless an operator explicitly adds `--membership`.

**Reproduced:** invoking the CLI main with pool v6, argv `--assemble`, and a mocked assembly sink records `assemble(membership=False)`. Apply the default to both v5 and v6.

### D4 — P1: weekly expansion is lost when the re-frozen winner stays unchanged

**Location:** `nn_meta/build_meta_dataset.py:441-444`, family early return at 225-239.

Reuse checks only frozen `params` and winning `dte`. Re-freezing a weekly name on `[1,2,4,5,7,10,30,45]` often keeps the same parameters and winner because the parameter sweep is unchanged and the old best DTE can still win. That family is then reused wholesale from v5, skipping its newly required 2/4/7-DTE rows. The identity guard added at HEAD addresses changed winners, but does not establish full-grid identity. Build/freeze specs can consequently claim weekly coverage that the generated family rows do not contain.

**Reproduced:** identical old/new MA winner DTE 5 with v5 rows at `[1,5,10,30,45]` returns those five rows as reusable while weekly mode is enabled. Compare complete grid/window/execution provenance or reuse individual existing variants and build missing variants.

### D5 — P2: marks-required builds accept rows without their mark stream

**Location:** `nn_meta/build_meta_dataset.py:449`, 225-239, 469-472.

`_reusable_rows(..., marks=True)` returns reusable rows with `marks=None` when the earlier pool's mark shard is missing. The family loop then skips execution, so marks are never recovered. Independently, `build_rows` skips an already committed symbol solely because its rows parquet exists, even when `--marks` is newly requested or a non-atomic transport omitted its marks file. This is the same incomplete-checkpoint condition explicitly repaired for **family partials**, but still present at whole-symbol and cross-pool reuse boundaries. Downstream ledger coverage validation may fail later; these paths nevertheless commit/accept a marks-incomplete build rather than repairing it.

**Reproduced:** v5 rows/spec without `meta_marks/SPY.parquet` return rows and `None` for a `marks=True` reuse request. Require corresponding mark coverage before skipping rows when marks are requested.

### D6 — P1: successful PIT freeze writes an output that breaks the next update

**Location:** `nn_meta/universe_pit.py:300-303`, output location 322-326.

`load_daily_rows` reads every parquet under `universe_daily`. `write_membership_parquet` writes `universe_membership.parquet` into that same directory. The next freeze/reconstitution concatenates the membership output with raw daily rows. Membership rows lack `root`, so `_ticker_daily` maps NaN through `root_to_ticker`, whose regex call raises a TypeError. This is a deterministic second-run failure in the documented incremental monthly workflow.

**Reproduced:** compute membership from a small raw monthly fixture, call `write_membership_parquet`, then compute membership from `load_daily_rows` again: `TypeError: expected string or bytes-like object, got 'float'`. Restrict inputs to the monthly filename/schema or keep derived views outside the input directory.

### D7 — P1: SPX0 credit-vertical selection uses future session prints

**Location:** `nn_meta/spx0/contracts.py:127-128`, whole-session grid at 111-116.

`pick_wing` measures strike spacing from the entire day's printed contracts before filtering candidates to prints preceding the decision. Future contracts can change the median strike gap, the target wing, selected contract, margin, width feature and eventual return. The fact that the chosen wing itself has a prior print does not make the grid estimate causal.

**Reproduced prefix-invariance failure:** at 14:00, prior put prints at 5970/5980/5990/6000/6010 and a 6000 short select 5980 for a two-step wing. Adding only 15:00 prints at 5975/5985/5995/6005 changes that same historical selection to 5990. Measure the grid from information available by `at`.

### D8 — P1: SPX0 close-triggered stops execute inside the bar that revealed the trigger

**Location:** `nn_meta/spx0/build_dataset.py:138-144`, call at 424-433; `nn_meta/spx0/fills.py:78-85`.

The stop/target detector reads a start-stamped one-minute bar's **Close**, then returns its start timestamp. `exit_fill` allows `timestamp >= exit_signal_ts`, choosing the triggering minute's Low/High as an exit. That close is not known until the following minute. Worst-print pricing cannot repair this causal violation: an earlier intraminute extreme may be unavailable when the decision is made, and the next minute can gap further. It affects long stop variants (including the active gap-fill seat) and historical naked-short variants.

**Reproduced:** the 14:02 bar closes at 0.4 against a 0.5 stop and is knowable at 14:03; the engine fills at 14:02's Low of 0.3. Advance close-trigger timestamps to the completed-bar time and test next-minute gaps.

## Validation and coverage

The targeted existing suite passed **152 tests**, with two protobuf deprecation warnings:

```text
python -m pytest -q -p no:cacheprovider
  tests/test_execution.py tests/test_hybrid_provider.py
  tests/test_download_universe.py tests/test_universe_pit.py
  tests/test_weekly_expiry_and_reuse.py tests/test_cache_preflight.py
  tests/test_nn_meta_data.py tests/test_nn_meta_baseline.py
  tests/test_v3_flatfiles.py tests/test_v3_underlying.py tests/test_v3_indicators.py
  tests/test_spx0_primitives.py tests/test_spx0_builder.py
  tests/test_spx0_round2.py tests/test_spx0_round3.py
```

Executed with the existing interpreter `/home/healy/Coding/HealysBacktester/venv/bin/python`, `PYTHONDONTWRITEBYTECODE=1`, and `/tmp` Numba/Matplotlib caches. The durable focused reproduction script is `docs/reviews/repros/data_audit_repro.py` (run with `PYTHONPATH=.`); its fixtures write only temporary directories. No provider/network endpoints were called.

Source reviewed: `nn_meta/{baseline,freeze_baseline,build_meta_dataset,config,weekly_expiry,universe_pit,cache_preflight,build_surface,download_universe}.py`; all Python files in `nn_meta/spx0`, `v3`, `options/data`, `options/selection`, plus `options/execution.py`. Technical feature implementation is inside `build_meta_dataset.py`; the assigned `nn_meta/features.py` does not exist. Related tests were examined with emphasis on the execution, reuse, compaction and SPX0 cases above; all listed suites were executed. Read/parsed the committed legacy baseline JSON, three universe-list JSON artifacts, and 21 PIT month JSON files (2024-11 through 2026-07); inspected their shapes, availability timestamps and membership parameters. Large production parquet caches and current v5/v6 generated artifacts are absent from the review checkout, so production prevalence and monetary impact cannot be measured here.

Known/documented limitations not re-reported as fresh defects: legacy bootstrap survivorship, historical Dec 31 cache holes already fixed in crawler code, renamed contract continuity, legacy execution-derived feature schema, baseline sequential accounting, and the accepted v5/v6 shared date windows. The initial family-empty checkpoint writes no marks marker and therefore needlessly rebuilds on marks-enabled resume; this is a minor inefficiency rather than evidence of label corruption. Root owns the Elliott-wave future-swing signal finding; `nn_meta.proposals` calls that generator without a compensating shift.
