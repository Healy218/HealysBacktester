# ETFE setup and capture commands

Use the [current-state index](../CURRENT_STATE.md#october-4-etfe-fresh-alpaca-setup)
for selected roots, the [scope](../specs/ETFE_SCOPE_0DTE_20261004.json),
[0DTE amendment](../specs/ETFE_0DTE_NORMALIZATION_20261004.md) and
[fresh collection contract](../specs/ETFE_FRESH_ACQUISITION_20261003.md) for policy.
The [roadmap sequence](../../ROADMAP.md#etfe-first-run-sequence) owns ordering.
No command here deploys a model or starts training.

## Current setup

From the repository root, inspect the selected v4 setup:

```bash
./venv/bin/python scripts/prepare_etfe_0dte.py verify --root nn_meta/validation/etfe-setup-20261004-0dte-r0
```

For an intentional successor preparation, use `prepare` with a fresh direct
`nn_meta/validation/etfe-*` root. Saved plans/source snapshots are immutable.
The v4 scope retains strategy specifications but imports no old market data,
features, labels or models. New entry/roll consumers must apply
`purchase_policy_v2.check_purchase / expiry_entry_gate` at the actual timezone-aware attempt and obey
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
eligibility; same-day samples may be eligible under v4 only after signal, dated expiry and
all other entry guards pass. A raw sample itself is not an eligible trade.
`iter_records` retains exact native fields and a per-page occurrence identity.
Typed normalization is implemented below; full option/context coverage remains separate.

Only root `.env` Alpaca pairs are loaded: data `ALPACA_API_KEY` /
`ALPACA_API_SECRET`, discovery `ALPACA_PAPER_API_KEY` /
`ALPACA_PAPER_API_SECRET`. No unrelated selectors are exported. Never print or
commit credentials. This transport uses serial rate limiting; future parallel
build workers must use the shared autosizer and measured memory budget.

## Preserved earlier evidence

The v1 midpoint and v2 VWAP preparations remain historical consumers. Verify
with their own `verify_etfe_setup.py` / `verify_etfe_vwap.py` commands when needed;
do not regenerate old plans or relabel their data as the current scope. The VWAP reference
component remains valid as a reference, not a complete execution model.

`./venv/bin/python scripts/verify_etfe_contract.py` verifies the original four
component declarations and portable source evidence. Its H1/R1/R2/P1 output
reports that historical revision, not the current collection authorization.
Apply the fresh-acquisition and DTE successors for current work. Historical
option quotes remain unsupported; do not repeat their diagnostics.

## Normalization and expanded acquisition

`expand_etfe_alpaca.py` prepares/executes source-bound calendar, remaining-stock,
discovery and option-stratum work. Use existing selected roots from CURRENT_STATE
for resume; do not prepare duplicate stock months. The source-bound capture plan
keeps per-invocation and root budgets; a budget stop must be resumed explicitly.
Current expansion roots completed, so there is no unfinished background job.

`normalize_etfe.py prepare --root ... --calendar ... --input ...` accepts one or
more complete fresh capture roots and creates a new `normalized-*` output.
`run --root ...` writes/checks typed partitions; `--max-partitions` permits a
bounded interruption. A complete-root run verifies committed inputs/outputs and
writes only a new run report. Sources/calendars and captured page hashes must
match. Do not change a saved normalization plan or silently overwrite Parquet.

```bash
./venv/bin/python scripts/audit_etfe_normalized.py --root nn_meta/data_cache_etfe/normalized-20261004-main-r0 --output /tmp/etfe-normalized-audit-new.json
```

The independent audit requires a fresh output path and reconciles every raw row
occurrence with normalized raw JSON in order, as well as counts/hashes/quality.
Parquet files are found through `partitions/*.json`, not filename guessing.
Keep all occurrences; filter only under an explicit downstream admission policy.
Inspect `stock_session_coverage` for expected/observed/missing minutes. VOO's
recorded gaps remain gaps, and stock-session labels do not define option hours.

## Demand inventory and January coverage

`scripts/etfe_demand.py inventory` requires `--calendar`, `--setup`, repeatable
`--input` fresh capture roots, and a new `nn_meta/validation/etfe-demand-*` root.
It factors all civil expiry/status edges over the collected calendar. `DEMAND.json`
binds the mathematical catalog and every reuse link; it explicitly lists later
signal, holding, reference and history frontiers instead of counting them as zero.

`discovery --inventory ... --root ...` prepares the bounded January expiry grid.
`boundary` and `surfaces` additionally require the full discovery and selected
reuse roots via `--input`. They verify the complete discovery grid before
enumerating every returned symbol, batch at most 100, and record symbol/window
edges plus reused capture links. Use `run` to resume the selected source-bound
root and `report` once complete to create immutable `COVERAGE.json`.

Honor the [study's total ceilings](../specs/ETFE_DEMAND_20261004.md) and the
[active-time successor](../specs/ETFE_DEMAND_CONTINUATION_20261004.md), not
just each invocation's 128-request cap. Plans and reports distinguish absent
symbols from no trading and first observed timestamps from usable history.
Full-day data can serve multiple downstream purposes; its download does not
establish complete historical listings or admit a context surface. Normalization
and independent reconciliation use the same commands as above.


## Causal component pilot

`scripts/pilot_etfe_causal.py prepare --root nn_meta/validation/etfe-causal-...`
creates a new source/input/package-bound component plan. `run --root ...` executes
nine serial ticker/timeframe scopes; `--max-scopes 1` provides a bounded stop.
Resume verifies completed scope hashes and skips their computation. `verify`
checks plan, source snapshots, package versions and bound input receipts.
Use the selected completed root from CURRENT_STATE; do not repeat the study
without a relevant change. Source edits require a new successor root.

`scripts/audit_etfe_causal.py --root ...` requires COMPLETE and creates immutable
GLOBAL_DEMAND and INDEPENDENT_AUDIT once. It independently checks candidate ranking,
event counts, feature masks, logical membership, physical unions and overlapping
raw request chains. An audit rerun needs a new evidence destination/workflow;
it does not overwrite the previous receipt. Transport coverage is not evidence
of a valid no-trade minute or historical contract eligibility.

The fifteen `raw__` fields are unadjusted engineering diagnostics, with explicit
missing masks. New adapters consume the frozen ETFE catalog and pure mathematical
kernels, never old runtime selectors or market/feature/model artifacts. Option
acquisition candidates remain separate from dated selection and entry approval.
This command performs no capture, execution, dataset freeze or model training.


## Bounded pilot trade capture

`scripts/capture_etfe_trade_demand.py prepare --root ... --pilot ...` binds the
completed pilot's audited GLOBAL_DEMAND, source code and measured trade-density
preflight. The selected study is deliberately limited to 225 intervals / 103
queries; a changed demand inventory requires a new study definition and root.
`run --root ... [--request-budget N]` applies cumulative study limits in addition
to the underlying capture caps; `verify` is read-only, and `report` publishes
COVERAGE once after every page chain terminates. Use the wrapper so cumulative
request/active-time/invocation ceilings are checked. Credentials stay in `.env`.

Normalize the completed raw root using the existing normalize/audit commands.
Then `scripts/audit_etfe_trade_windows.py --raw ... --normalized ...` publishes
DEMANDED_MINUTES.parquet and DEMAND_AUDIT once. It checks exact half-open request
membership and retains every demanded minute, including unresolved absence.
Do not overwrite these outputs or edit the pilot's original GLOBAL_DEMAND to
relabel old evidence. The successor demand audit records transport closure.
The minute census is diagnostic, not an admitted model feature table.


## Option trade/bar feature component

`scripts/pilot_etfe_option_features.py prepare --root nn_meta/validation/etfe-option-features-...`
binds the ten-field registry, selected fresh inputs, source snapshots and package
versions. `run --root ... [--max-scopes 1]` computes nine serial scopes, preserving
existing scope hashes on resume. `verify --root ...` is read-only. The selected
completed successor is listed in CURRENT_STATE; do not repeat it without cause.

Each scope has a diagnostic window table and an ordinal-to-window link table.
The original event Parquet owns the variant/direction/target fields and is bound
by hash. A null window ID preserves a missing acquisition candidate. Every row
keeps model-feature admission false, including rows with all ten finite values.

`scripts/audit_etfe_option_features.py --root ...` independently recomputes all
real-window values/masks/reasons and membership, then writes INDEPENDENT_AUDIT
once. Its real-data assertions are deliberately limited to this pilot's actual
condition/ID/availability observations; synthetic tests cover other cases.
Rejected roots remain immutable, including their original source snapshots and
rejection receipts. A changed consumer requires a new root, not altered receipts.


## Thirteen-source TV feature component

`scripts/pilot_etfe_tv_features.py prepare --root nn_meta/validation/etfe-tv-features-...`
binds the 96 registered formulas, thirteen parameter scopes, explicit readiness
predicates, fresh inputs, numerical source snapshots and package versions.
`run --root ... [--max-scopes 1]` computes serial ticker/timeframe scopes; a scope
limit exits with status 2 to indicate deliberate incompleteness. Resume validates
existing receipt/payload hashes. `verify --root ...` is read-only. Invoke all
commands with `./venv/bin/python`. The selected completed root is in CURRENT_STATE.

Each scope retains diagnostic values/masks/reasons, required native columns and
original-event-ordinal links. Full-prefix recurrence starts at the fixed January
origin; observation slicing never resets indicator history or calendar anchors.
The legacy acceleration environment flag must not select alternative kernels.

`scripts/audit_etfe_tv_features.py --root ...` independently recomputes scalar
projections, ATR, prerequisite decisions and logical membership and writes
INDEPENDENT_AUDIT once. It does not independently reimplement native kernels or
prove exported Pine parity. All outputs remain unadmitted diagnostics. Completed
studies are immutable; source changes require successor roots and fresh evidence.


## Remaining feature components

`scripts/pilot_etfe_remaining_features.py prepare --root nn_meta/validation/etfe-remaining-features-...`
binds fresh predecessors, the ETFE catalog, original registry and versioned
numeric-Setup/DTE binding amendment. Run with `./venv/bin/python`.
`run --root ... [--max-scopes 1]` preserves shared and completed scope files;
the scope limit returns status 2 for deliberate incompleteness. `verify` is
read-only. Do not repeat completed studies without a relevant change.

SHARED points to the 77-field variant table, daily context and daily input audit
source. Each scope has signal diagnostics, original-event-ordinal links and
compressed full-prefix native signal positions. Target replicas share the same
signal ordinal. Missing dated contract/sector fields are explicit in every link.
The per-signal MA fields override the shared 10/30 projections for MA variants.

`scripts/audit_etfe_remaining_features.py --root ...` checks static values,
scalar daily rolling calculations, age/MA projections and every membership.
`scripts/audit_etfe_remaining_daily_inputs.py --root ...` separately reconciles
daily closes and missingness to original minute grids, retaining its own source
snapshot/hash. Both create immutable receipts once. Seven daily option-context
formulas have synthetic complete-surface checks; current real values are missing
pending dated coverage/terms evidence. These outputs do not admit a model schema.


## Joined diagnostic schema

`scripts/pilot_etfe_joined.py prepare --root nn_meta/validation/etfe-joined-...`
binds all four verified component roots, their receipts/payloads, the registry,
binding amendment, join/audit source and package versions. Invoke with
`./venv/bin/python`. `run --root ... [--max-chunks 1]` uses bounded 5,000-row
chunks and returns status 2 for deliberate incompleteness. Resume verifies all
committed file hashes; `verify --root ...` is read-only. Selected root and
completed evidence live in CURRENT_STATE; do not repeat completed runs casually.

Each chunk receipt commits four Parquets: 221 float64 values followed by 221
uint8 masks in `matrix`, field-level `reasons`, modeled nanosecond `availability`
(-1 for missing values), and original identity/provenance in `rows`. The container
is explicitly diagnostic despite canonical matrix names. Selected contract stays
null; acquisition candidates never establish eligibility. Variant MA overrides
come from the remaining component; target replicas preserve distinct row IDs.

`scripts/audit_etfe_joined.py --root ...` independently aligns sources by natural
keys and checks every value/mask/reason/clock and logical row against predecessors.
It writes INDEPENDENT_AUDIT once and does not recompute native indicators.
Run-time changed-batch-boundary checks and a recorded one-chunk stop/resume supply
separate recovery evidence. Model admission remains false. Source-bound consumers
and existing study roots are immutable; changes require a successor study.


## Fresh corporate-action evidence

Use `./venv/bin/python scripts/capture_etfe_actions.py` with `prepare`, `run`,
`normalize` or read-only `verify`, and a direct
`nn_meta/data_cache_etfe/alpaca-fresh-actions-*` root. `run --request-budget 1`
supports deliberate interruption; status 2 means incomplete/stopped. It captures
all-type/all-quality SPY/QQQ/VOO action pages and two finite route probes. Native
REST fields and exact raw JSON survive normalization; historical availability
remains unknown. `scripts/audit_etfe_actions.py --root ...` writes an independent
raw-occurrence audit once. Selected completed roots live in CURRENT_STATE.

The fixed price window must not be used as an effective-date completeness claim
for the REST process-date filter. The source-bound
`scripts/extend_etfe_action_evidence.py` successor captures the October 3–December
31 process-date tail in a separate root, without requesting later prices. Commands
are `prepare`, `run`, `inspect`, and read-only `verify`; `run` preserves failed
attempts and stops for explicit retry after any provider cooldown. Tail roots
must be named `alpaca-fresh-actions-tail-*` and retain every native occurrence.

`inspect` parses already-captured SSE blocks, preserves emitted timestamps,
insert/update/delete kinds and ETF lineage, and reports unparsed trailing bytes.
`scripts/audit_etfe_action_tail.py --root ...` independently reconciles REST
occurrences and complete SSE events with a line-oriented parser. No original
publication time or revision history is inferred from a later mutation. Empty
or capped probes stay incomplete evidence. Do not repeat completed captures;
expanded replay requires its own measured request/storage plan.

### Bounded historical action replay

Use `./venv/bin/python scripts/replay_etfe_actions_v2.py` with `prepare`, `run`,
`reconcile` or read-only `verify`; selected root is in CURRENT_STATE. The original
unsuffixed consumer belongs to rejected r0 and must stay immutable. R1 uses four
fixed UTC control days and the documented cash-dividend event-type filter.
`run --request-budget 4` exercises an actual stop on the first capped September
page. Resume verifies all committed pages and starts from the beginning of the
last complete event's second. Preserve overlaps, compare repeated IDs exactly,
and retain partial trailing blocks in raw bodies. Never advance one nanosecond
past an event to avoid duplicates: equal-time events could be skipped.

The earlier precise restart returned events before its submillisecond cursor.
Whole-second overlap addresses that observation while retaining strict bounds.
Repeated zero-progress pages, conflicting IDs or exhausted byte/time budgets stop
the study. EOF is a transport fact; retention/history coverage stays separate.
`scripts/audit_etfe_action_replay_v2.py --root ...` independently reconciles every
event and ETF link and compares witnesses with all 35 selected REST actions.
Completed receipts are immutable. Do not rerun controls without a specific new
question or source/implementation change.

## Bounded synthetic option execution

Selected root: `nn_meta/validation/etfe-execution-components-20261005-r0/`.
This study consumes synthetic dated fixtures only; it does not admit market
paths or emit labels. [Component boundary](../specs/ETFE_EXECUTION_COMPONENTS_20261005.md),
[hand reconciliation](../reviews/2026-10-05-etfe-execution-components.md).

```bash
./venv/bin/python scripts/pilot_etfe_execution.py audit --root nn_meta/validation/etfe-execution-components-20261005-r0
```

The recorded run used `run --stop-after 2`, then `run` in a separate process.
Resume checks source and checkpoint hashes and preserves earlier files. The
audit replays every prefix and independently reconciles cash, quantity, fees,
slippage, cent rounding and shared bar capacity using Decimal arithmetic.
Unknown settlement dates retain receivables; unsupported expiry/roll/physical
paths remain unresolved. The caller owns complete observation scheduling.
Any bound-source behavioral change requires a successor module/study root;
do not overwrite this evidence or retrofit real-data admission into it.

## Bounded synthetic expiry and delivery

Selected root: `nn_meta/validation/etfe-expiry-components-20261005-r0/`.
The new continuation verifies an unchanged option-prefix snapshot and binds
separate synthetic terms, official references, quotes and settlement calendars.
[Scope](../specs/ETFE_EXPIRY_COMPONENTS_20261005.md),
[four hand cases](../reviews/2026-10-05-etfe-expiry-components.md).

```bash
./venv/bin/python scripts/pilot_etfe_expiry.py audit --root nn_meta/validation/etfe-expiry-components-20261005-r0
```

The recorded run used `run --max-steps 2`, then `run` in a new process. It
restored exercise reservations before delivery and completed all four cases.
Thirteen immutable checkpoint/hash pairs reconcile against uninterrupted replay;
an independent Decimal audit checks cash, shares, fees, capacities and dates.
Ordinary entries after continuation and full observation scheduling remain
separate. Real source admission, labels and training stay false. Preserve source
snapshots and use successor modules/roots for behavior changes.

## Bounded shared scheduler and stress matrix

Selected root: `nn_meta/validation/etfe-integration-components-20261005-r0/`.
[Contract](../specs/ETFE_INTEGRATION_COMPONENTS_20261005.md),
[evidence and limits](../reviews/2026-10-05-etfe-integration-components.md).

```bash
./venv/bin/python scripts/pilot_etfe_integration.py audit --root nn_meta/validation/etfe-integration-components-20261005-r0
```

The recorded `run --max-events 20` stopped within the first ordinary path;
`run` in a new process resumed and completed six tapes × 27 finite profiles.
All 162 reports/states and the saved prefix reconcile against fresh replay.
Independent Decimal checks cover cash, shares/contracts, costs, participation,
reservations and the complete 189-path census. Three stressed paths require
additional quote/exercise observations; no missing outcome is discarded.

The scheduler generates all required clocks inside each declared synthetic
interval, including settlement and stock latency. Short fixture ends stay open;
only a completed fixed-end tape may censor. Model targets remain null. This is
not real input admission, isolated scientific labels or full-history resource
validation. Snapshot tape/source/cursor identities are mandatory; uncommitted
payloads recover a missing hash receipt only after deterministic replay.
Future changes use new source versions and study roots.
