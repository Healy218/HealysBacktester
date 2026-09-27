# FA Roadmap — causal fundamental-attention context bars

## Purpose

Build a point-in-time FA layer that produces a causal, per-security context bar
aligned to the project's price and options bars. The FA layer may become an
auxiliary trading signal, a regime/context score, or a learned embedding for
future model generations. It is not a replacement price series and it is not
admitted to live or V7 training until it passes its own evidence gates.

This work can proceed while the V7 catalog compiles. FA work must remain
isolated from the active V7 run, its artifacts, its resource budget and its
source contracts.

## Starting point

- Collectors exist for Reddit, StockTwits, news and EDGAR.
- Archive, entity resolution, attention scoring, ranking and forward tracking
  are implemented in `fa/`.
- The fundamental overlay remains a scaffold.
- The home/dashboard state has a fresh 300-symbol feature snapshot and 2,998
  unique news items.
- The current evaluation has only 120 labeled rows and reports
  `insufficient-purged-history`; this is exploratory evidence, not a model
  verdict.
- The August 2026 ranking is contaminated by the pre-capture-time-correction
  path and remains historical only.
- The roadmap previously required immutable captures/PIT maintenance,
  automation/digest/overlays, and three clean forward-tracked monthlies.
- The former roadmap also retained prospective FA/PIT cohorts and overlays,
  FA automation, and a future stacked blend behind validated FA evidence.
- `TODO.md` contains no direct FA work items; its active queue is the gated V7
  sequence. FA must not become an implicit V7 prerequisite.

## Phases and gates

### FA-0 — Freeze the contract and audit the current data

Document the intended grain, source availability timestamps, ticker identity
rules, timezone policy, retention, feature schemas, label horizons and resource
limits. Profile every current source for freshness, duplicates, missingness,
entity-resolution coverage, date continuity and join loss. Produce a dated
baseline report and preserve the current artifacts unchanged.

Gate: the current data limitations are quantified and every required field has
an explicit treatment.

### FA-1 — Make collection and archives durable

Run collectors on a bounded schedule with immutable raw captures, manifests,
hashes, provider-response receipts and restart-safe checkpoints. Keep source
and capture time separate. Enforce idempotent writes, stable event IDs and
source-specific failure reporting. Maintain the PIT alias/entity map as a
versioned artifact rather than silently rewriting history.

Gate: a fresh capture can be replayed byte-for-byte and its availability
boundary is inspectable.

### FA-2 — Build causal FA context bars

Convert events into per-security bars at the supported 5/15/30-minute signal
cadences, with daily features where intraday data is not justified. Include
attention velocity, sentiment, news, filings, insider activity, options-flow
and liquidity/crowding features as sources become available. Use as-of joins,
explicit freshness/age fields and documented decay; never forward-fill across
an unavailable boundary or use provider publication data that was not known at
the decision time.

Gate: causal prefix tests, duplicate/grain checks, as-of join tests and
batch/incremental equivalence all pass.

### FA-3 — Establish labels and evaluation

Define forward labels separately from features: direction, excess return,
volatility or event-impact labels at named horizons. Use chronological folds,
purging and embargo. Report coverage, class balance, effective sample size,
source ablations and baseline comparisons. Accumulate prospective monthlies;
the contaminated August cohort cannot count toward the clean set.

Gate: enough clean purged history exists for a stable evaluation, with at
least three clean forward-tracked monthlies and no unexplained leakage or join
loss.

### FA-4 — Train and validate the first FA model

Start with boring baselines: source-only rules, regularized linear/logistic
models and a simple tree model. Compare against price/options-only baselines.
Calibrate outputs and test stability across symbols, regimes, source subsets
and horizons. The first useful output may be a probability, expected return,
regime score or compact embedding; choose based on incremental evidence rather
than model novelty.

Gate: FA adds robust out-of-sample value after costs and purging, survives
feature/source ablations, and has a frozen artifact, manifest and reproducible
inference path.

### FA-5 — Integrate as a future model sidecar

Expose a versioned FA bar/score contract that future V7+ or V8 feature builders
can join without changing the live V5/V6 policy. Run shadow/offline integration
first. Compare price/options-only, FA-only and combined models. Keep the FA
artifact alongside existing experts with its own state, ledger and promotion
decision.

Gate: exact point-in-time joins, offline/near-live parity, resource feasibility,
forward evidence and an explicit promotion decision.

### FA-6 — Optional panel admission and ongoing maintenance

Only after FA-5 may it feed a stacked blend, training-universe graduation or
live alert panel. Continue immutable capture, monthly cohort tracking,
drift/freshness checks, artifact retention and rollback support.

## Long-term acceptance criteria

- All source events have source time, capture time, availability treatment and
  stable provenance.
- FA bars have a declared grain, causal as-of semantics and explicit age/decay.
- Historical and incremental builds agree for the same cutoff.
- Labels and folds are chronological, purged and independently reproducible.
- The model beats a boring price/options baseline on clean out-of-sample data,
  after costs, or is explicitly rejected.
- Three clean forward-tracked monthlies exist before any graduation claim.
- No FA result changes V7 or live operation without a separate reviewed gate.

## Parallel-work boundary

Safe while V7 compiles: documentation, profiling existing FA artifacts,
collector contract work, small bounded tests, archive manifests and isolated
FA pilots. Not safe without explicit coordination: bulk acquisition that
competes for the V7 disk reserve, changing shared data contracts, altering V7
launchers, or admitting FA features into V7 training.

