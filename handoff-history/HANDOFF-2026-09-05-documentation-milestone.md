# Handoff — TradingView implementation and readiness work

Documentation milestone, September 5, 2026 (Chicago). [TODO](TODO.md) holds
active tasks; [ROADMAP](ROADMAP.md) holds phase gates. The user authorized
starting all six workstreams with multiple agents: reconcile docs, finish
TradingView, prepare the campaign, rebuild/compare after dependencies,
verify operations, and advance execution/broader research.

## Verified local state

- Work on `main` in `/home/healy/Coding/HealysBacktester`. Audit integration
  is `d7d7816` (repair commit `79d3b58`). All 51 findings and four additional
  concerns have corrective code. The planning rerun passed **642 tests and
  18 subtests**, 10 warnings, in approximately 35.9 seconds.
- Contract: `2026-09-05-causal-v2`. Local v5 spec/manifest and sampled v6
  shard lack it; preserved artifacts are ineligible for current default
  loaders or resumed corrected builds.
- Untracked `nn_meta/artifacts_v6/` holds historical shards. The previous
  campaign stopped at 211/441; do not resume/merge them or reuse pre-audit
  v5 rows for the corrected campaign.
- Read-path optimization, PBO/EV/watchlists, PIT, Keltner/BBW scaffolding and
  weekly-DTE plumbing are implemented. v6 retains v5's window; the archive
  audit identified fifteen weekly names.

## This milestone

[TRADINGVIEW_EXPANSION](docs/specs/TRADINGVIEW_EXPANSION.md) and the
[complete snapshot](docs/specs/tradingview-boost-snapshot-2026-09-05.json)
record all 42 general pages (1,000 unique recent scripts) and 32 Editors'
Picks pages (758 scripts), ranked by exact boost count. The selected ten
plus three are distinct; all detail pages label them open source.

Use the literal supplied-page scope while the optional all-time clarification
is unanswered. Source pinning, licenses, mechanical rules and causal/Pine
parity are implementation work, not completed by listing research.
Keltner/BBW semantics remain part of validation.

Source/signal agents are active; the coordinator is preparing campaign/artifact
readiness and a read-only operational review. This handoff records the docs
milestone only. It does not establish completed ports, corrected model builds,
server verification or deployment. The coordinator will reconcile actual
results before the session closes.

TODO/ROADMAP now separate completed foundations from remaining work.
DOCUMENTATION's environment, provider, read-path and ops instructions are
reconciled, with old text archived. The previous HANDOFF is preserved
byte-for-byte in
[before-tradingview-selection](handoff-history/HANDOFF-2026-09-05-before-tradingview-selection.md).

## Next actions and boundaries

1. Pin sources/rules for all thirteen selections; implement in dependency order.
   Admit families only after Pine/causal/data parity. Footprint modes lacking
   a historical/live twin stay pending.
2. Preserve history, establish coverage/gaps and fresh paths/full corrected
   launchers. After integration/preflight, refreeze, build rows/marks/PIT,
   evaluate and finalize with matching fingerprints and valid time boundaries.
3. Finish actual server inspection and full-session checks. Last deployment
   notes report four experts, SIP/OPRA feeds and :01/:02/:03 staggering;
   these are historical observations. September 8, 2026 is Tuesday.
4. Prepare resolver/quotes and a concrete alert preview. Shared alert-format
   go/no-go remains in force. Quote-verified accounting and Alpaca paper
   execution depend on offline semantics and sizing/exits/reconciliation.
5. Advance deeper data/PIT/surfaces for v7/SPX0 and prospective FA automation.
   The contaminated August FA monthly contributes no clean prospective
   cohort toward the three-monthly gate.

## Operational facts to preserve

- Massive Advanced and Alpaca Algo Trader Plus landed; deep history is no
  longer blocked on those purchases. Quote files were observed at 85–140
  GB/day: use targeted timestamp-bounded REST.
- Current-session bars come from complete healthy stream buckets or forced
  current REST; cached history stops at yesterday. Check closed-bar
  timestamps, not process/pass counts.
- Use bracketed process patterns (`pgrep -f "[f]eeds."`) everywhere. Plain
  patterns previously matched watchdog shells and concealed a dead stream.
- Default loaders reject stale bundles. Prepare regenerated verified models
  with compatible source before rollout; retained models remain historical.
- Server source delivery is git pull via its deploy key. Stage/diff cron
  changes and preserve backups; server notes report no sudo.
- Avoid notifier side effects in read-only work. Use isolated dry runs and
  inspect code/logs before calling heartbeat/digest entrypoints.
- Global proposal-freeze evaluation is conditional and restricted to later
  validation/test. Preserve prior results/refusals and gate-selection history;
  fresh forward evidence is still required.

References: [remediation](docs/reviews/2026-09-05-remediation.md),
[integration](docs/reviews/2026-09-05-main-integration.md),
[full-day history](handoff-history/HANDOFF-2026-09-05-wipe-restore-v5-ladder-feeds.md),
[REALTIME_SPEC](docs/specs/REALTIME_SPEC.md).
