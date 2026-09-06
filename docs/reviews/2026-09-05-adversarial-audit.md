# Adversarial code audit — 2026-09-05

> Remediated in the review checkout. See [the repair report](2026-09-05-remediation.md) for current dispositions and validation. Findings below refer to the original audited commit.

Reviewed commit: `f98ed265db3ce3faf4ba7abf8e6604671e3a1c90`.

## Assessment

**The passing test suite does not establish that the reported strategy performance is reliable.** The review found **51 main findings: 17 P1 and 34 P2**, plus four smaller or qualified implementation concerns in the evaluation report and the documentation/measurement limitations below. Several defects directly affect active research/live paths: future-informed Elliott signals, globally optimized baselines inside purported nested evaluation, discarded entry-bar losses, omitted roll costs, unfunded ledger entries, order-dependent option labels, and destructive daily cache compaction. These need correction and affected artifacts need rebuilding before the corresponding performance/eligibility results can be trusted.

P1 denotes a high-priority correctness, data-loss, or operational-control issue; P2 denotes a material defect under the documented trigger. This is a repair priority assessment, not evidence that every production artifact is affected. Synthetic results demonstrate mechanisms; no historical production P&L was recomputed. Legacy dashboard, daily-options, FA and SPX0 findings are explicitly scoped in the detailed reports.

## Review method and validation

The review began with the Markdown documentation and historical decisions, then split into three specialist agents covering data/execution, evaluation/accounting, and live/operations. The coordinating reviewer covered the core backtester and integrated the results. The initial documentation pass covered 54 files; final tracked-file inventory reconciled 58 Markdown files, including four hidden project-manager memory files. These extra memory files were checked during consolidation. Their old bug claims were not accepted as current defects without checking source.

- Complete existing suite: **517 passed, 6 skipped, 18 subtests passed, 10 warnings**, in 28.60 seconds. Command: `PYTHONDONTWRITEBYTECODE=1 NUMBA_CACHE_DIR=/tmp/healys-review-numba /home/healy/Coding/HealysBacktester/venv/bin/python -m pytest tests/ -q -p no:cacheprovider`.
- The data reviewer additionally ran 152 relevant existing tests successfully. These overlap the full suite; they are not 152 additional unique tests.
- Isolated synthetic checks reproduced cache deletion, DTE sweep-order changes, incomplete reuse, PIT rerun failure, future SPX0 selection/fills, retroactive Elliott signals, first-bar drawdown loss, endpoint inconsistency, leverage, omitted roll costs, future-exit selection, and several scanner/FA defects. Static findings identify the precise failure path and are labeled accordingly.
- Preserved scripts: [core reproductions](repros/root_audit_repro.py), [data reproductions](repros/data_audit_repro.py), [evaluation reproductions](repros/evaluation_audit.py). Run from the repository root with project dependencies, `PYTHONPATH=.`, bytecode disabled, and temporary cache directories. Scripts expose current behavior; they are not fixed-behavior regression tests.
- Source, configuration, deployment scripts, tests and text/JSON artifacts were inspected. Full binary model weights, absent production parquet caches, deployed cron/cloud state, real provider availability, and every UI/grid permutation were outside executable coverage. This is a broad adversarial source audit, not an exhaustive proof of correctness.
- Only review reports and reproduction scripts were added. No source fixes, commits, pushes, cloud jobs, broker actions, or external notifications were performed.

## Repair sequence

1. **Preserve data and make failures visible:** repair compaction (D1), budget guard (LO-01), rows/marks publication and reuse (LO-02/03, D5), and worker exit handling (LO-15). Confirm recoverable copies before any production compaction rerun.
2. **Restore causal inputs:** correct Elliott confirmation (CORE-01), baseline-fold boundaries (E01), DTE cache coverage (D2), PIT defaults/update/reuse (D3/4/6), and SPX0 timing (D7/8). Rebuild affected upstream artifacts, not just downstream models.
3. **Repair the acceptance ledger:** separate entry/open/close events (E02), enforce cash (E03), account for every roll fill (E04), reconcile/hash marks (E05/E14). Rerun candidate and baseline gates on the same corrected inputs.
4. **Align live behavior and durability:** address feature mismatch (CORE-13), dry-run state, legacy delivery failures, feed freshness and overlapping state updates (LO-05 through LO-08).
5. **Repair remaining scoped research/UI/FA findings**, then add regression tests using the reproduced triggers and refresh operational documentation. The detailed reports give a fix direction for each item.

## Complete main finding index

Each linked report contains exact source locations, trigger, consequence, evidence status, and proposed correction. Multiple findings may contribute to one failure: D5 and LO-02/03 are separate reuse/publication causes of missing marks; E05 and E14 are distinct validation/provenance gaps. The count is not a count of independent production incidents.

### Core backtester and signal parity

[Detailed report](2026-09-05-core-audit.md)

| ID | Priority | Finding |
|---|---|---|
| CORE-01 | P1 | Elliott signals use future-confirmed pivots before confirmation |
| CORE-02 | P2 | legacy sentiment aggregation timestamps future news at the bucket start |
| CORE-03 | P2 | ranking reintroduces parameter sets it explicitly excluded |
| CORE-04 | P2 | chunked ranking can crown the wrong per-metric winner |
| CORE-05 | P2 | signal combination invents nonexistent parameter pairs |
| CORE-06 | P2 | saved scanner RSI/MACD calculations differ from backtested indicators |
| CORE-07 | P2 | the legacy intraday scanner requests a window ending at midnight |
| CORE-08 | P2 | saving Volume Breakout produces an unusable scanner configuration |
| CORE-09 | P2 | scanner saves use current controls rather than the selected result's configuration |
| CORE-10 | P2 | legacy neural training labels cross the train/test boundary |
| CORE-11 | P2 | walk-forward evaluation discards valid pre-window indicator history |
| CORE-12 | P2 | OHLCV cleaning backfills earlier missing prices with future observations |
| CORE-13 | P2 | live v4/v5 moneyness is fixed at zero despite varying training values |

### Data, execution, PIT and SPX0

[Detailed report](2026-09-05-data-audit.md)

| ID | Priority | Finding |
|---|---|---|
| D1 | P1 | daily-bar compaction deletes legitimate history across flat-file partitions |
| D2 | P1 | shared option-bar cache changes labels depending on DTE sweep order |
| D3 | P1 | v6 assembly disables point-in-time membership by default |
| D4 | P1 | weekly expansion is lost when the re-frozen winner stays unchanged |
| D5 | P2 | marks-required builds accept rows without their mark stream |
| D6 | P1 | successful PIT freeze writes an output that breaks the next update |
| D7 | P1 | SPX0 credit-vertical selection uses future session prints |
| D8 | P1 | SPX0 close-triggered stops execute inside the bar that revealed the trigger |

### Evaluation, accounting and models

[Detailed report](2026-09-05-evaluation-audit.md)

| ID | Priority | Finding |
|---|---|---|
| E01 | P1 | “Nested” v4 evaluation does not nest the frozen proposal strategy |
| E02 | P1 | Entry-bar close marks are silently discarded |
| E03 | P1 | The cash ledger permits unfunded entries and leverage |
| E04 | P1 | Rolls lose all intermediate execution costs in Option B |
| E05 | P2 | Mark sidecars are not reconciled with the execution outcome |
| E06 | P1 | Daily options selection looks ahead to exit-data availability |
| E07 | P2 | Daily options “purged” splits do not inspect label exits |
| E08 | P2 | The daily drawdown metric forgets initial capital |
| E09 | P2 | Legacy walk-forward training labels can cross the OOS boundary |
| E10 | P2 | Walk-forward resume silently reuses a different experiment |
| E11 | P2 | Isotonic calibration depends on ordering of tied scores |
| E12 | P2 | Volatility feature availability is one minute early |
| E13 | P2 | Regime diagnostic bins read future OOS distributions |
| E14 | P2 | The artifact manifest does not identify the mark stream that determined eligibility |
| E15 | P2 | Every candidate repeatedly validates and sorts the full mark universe |

### Live operations and discovery

[Detailed report](2026-09-05-live-ops-audit.md)

| ID | Priority | Finding |
|---|---|---|
| LO-01 | P1 | the cloud spend guard abandons live fleets on API errors |
| LO-02 | P1 | cloud checkpoint publication can permanently omit mark streams |
| LO-03 | P1 | local v5 publishing failures are reported as successful builds |
| LO-04 | P1 | FA historical rankings consume information after their declared cutoff |
| LO-05 | P2 | scanner dry runs consume real alert/digest state |
| LO-06 | P2 | legacy experts permanently lose failed notifications |
| LO-07 | P2 | fresh means newest cached bar, not recent market data |
| LO-08 | P2 | atomic state files still lose writes across overlapping processes |
| LO-09 | P2 | the append-only FA archive is overwritten non-atomically |
| LO-10 | P2 | month boundaries bypass collector deduplication |
| LO-11 | P2 | the forward-return tracker CLI crashes on ordinary frozen rankings |
| LO-12 | P2 | news corroboration silently drops all but the first ticker |
| LO-13 | P2 | graduation borrows returns from a different ranking cohort |
| LO-14 | P2 | trending's cashtags bypass its advertised liquidity universe |
| LO-15 | P2 | local v6 launcher reports completion when workers fail |

## Additional implementation concerns

The [evaluation report](2026-09-05-evaluation-audit.md#additional-concerns-and-smaller-defects) also identifies a crash window between final-bundle renames (P2), incomplete verification-envelope requirements (P2), an omitted fold remainder (P3), and legitimate zero baseline returns treated as missing (P3). These are separate from the 51 main findings.

## Documentation and methodological findings

1. **Current operational state is spread across contradictory documents.** `HANDOFF.md` has recent updates above older state summaries; `ROADMAP.md`, `TODO.md`, and `README.md` still contain completed/obsolete PIT, cloud and v4 milestones. A new operator cannot safely infer current deployed experts, validated datasets, or next steps from any arbitrary summary. Put a dated authoritative status and explicit supersession links in the entry-point documents; keep historical handoffs as history.
2. **Technical reference material describes superseded implementations.** `DOCUMENTATION.md`, `data/DATA_SOURCES.md`, `v3/README.md`, `fa/README.md`, and hidden project-manager memory contain obsolete paths, stubs, provider/fallback descriptions, test counts or model bugs. Current source already implements some claimed missing model APIs and LSTM support. These stale statements are documentation defects, not additional open code defects. `nn_meta/live/v4_scan.py` also claims feature parity more strongly than its actual moneyness construction supports (CORE-13).
3. **Cost-control prose overstates guarantees.** The GCP feasibility/runbook material's four-hour/budget assurances do not match documented longer workloads and cannot be upheld by the current fail-open spend guard. State assumptions, billed-resource termination verification and unknown-state handling explicitly; an alert budget is not a hard spend cap.
4. **Research gate changes must remain visible in performance claims.** The September 4 change to return divided by `max(drawdown, .05)` versus baseline ex-top3 is documented and intentional, so it is not reported as an unauthorized code change. However, adopting criteria after seeing refusal results is another research selection decision. Preserve the full experiment history and use genuinely untouched/forward evidence for the next effectiveness claim. This is separate from the implementation leakage in E01.
5. **Some reports have stronger temporal/statistical labels than their definitions support.** E14 identifies stale gate wording; LO-04 shows as-of evidence after a declared cutoff. The live watchlist's seven-day scoreboard is based on entry cohorts rather than seven days of resolved outcomes; FA monthly ranking averages historical score rows without a stated trailing window; StockTwits archives overlapping snapshots rather than unique-message votes. These need explicit metric definitions before comparisons or threshold tuning.

Accepted limitations were not counted as new bugs: known historical cache holes/rename continuity, deliberate shared v5/v6 date windows, paper/alert-only execution, the documented realized-close EV brake choice, deferred live sizing/DD enforcement, and stale daily surface/beta caveats. Earlier fixes were checked where relevant and are acknowledged in the specialist reports.
