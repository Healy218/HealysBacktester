# September 5 audit integration into main

The audit fixes are integrated with the latest user/Claude pipeline work. The newer notes are the documentation base; audit migration requirements are added without discarding the Massive Advanced, Alpaca Algo Trader Plus, streamed-feed, v7, or outstanding alert-format decisions.

## Source snapshots and preservation

- Audited base: `f98ed265db3ce3faf4ba7abf8e6604671e3a1c90`.
- Completed audit repairs: `79d3b58` ([remediation report](2026-09-05-remediation.md)).
- Newer main and `codex/v4-causal-validation`: `9351d01ee487299ae208393cfad021da0330950b`.
- Before integration, tracked Markdown and changed/untracked source files in both checkouts were archived with SHA-256 manifests under `/tmp/healys-premerge-20260905T234729Z`. The existing primary-checkout v6 shards were included; raw caches, trained bundles, and live state were not regenerated.
- The original incident log, real-time spec, and latest historical handoff remain intact. The latest TODO and HANDOFF content is preserved with prominent current-contract instructions. Git history also retains every incoming note at the source snapshot above.

## Integration behavior

The combined code retains streamed current-session bars, fresh REST fallback, vendor aliases, and parallel detection. Audit safeguards cover both detection modes, including closed/fresh data, durable notification replay, serialized state, and isolated previews. The final scan window accommodates the documented staggered closing passes through 16:03 ET. Today's REST requests use midnight-to-now timestamp bounds with cache reads/writes disabled; historical cache reads exclude today's rows. Streamed elapsed buckets require all 15 minute timestamps, and a missing bucket anywhere in the current session triggers REST fallback. This deliberately uses REST for sparse/no-trade minute intervals too; it does not infer that missing stream minutes had zero volume.

The old v6 freeze/reuse instructions are historical: preserve the paused shards, then create new freezes and derived artifacts under `2026-09-05-causal-v2`. Existing model files are preserved but default loaders reject stale contracts. A source merge does not establish compatibility with deployed bundles.

## Validation and next work

The final combined suite passed **642 tests and 18 subtests**, with zero failures/skips and 10 dependency warnings, in 23.74 seconds. Command:

```bash
PYTHONDONTWRITEBYTECODE=1 NUMBA_CACHE_DIR=/tmp/healys-review-numba MPLCONFIGDIR=/tmp/healys-review-mpl /home/healy/Coding/HealysBacktester/venv/bin/python -m pytest tests/ -q -p no:cacheprovider
```

`bash -n` passed for all five changed operational shell scripts. `git diff --check` passed. All nine incoming Markdown documents were checked against `9351d01`: complete original text remains, except the user-directed working-branch change and removal of one trailing space. HANDOFF/TODO also have byte-exact pre-merge snapshots. EXPERIMENTS, REALTIME_SPEC, and the previous full-day handoff remain byte-identical. Primary-checkout source notes and untracked v6 shards still matched their pre-merge hashes before switching checkouts.

No deployment, market-provider call, training, cloud workload, or historical rebuild is part of this merge. Local tests do not establish deployed-feed parity; retain the full-session parity gate in REALTIME_SPEC.

Work proceeds from `/home/healy/Coding/HealysBacktester` on `main`. Next, inventory and implement the requested TradingView indicators/strategies with source attribution, explicit mechanical signal rules, and causal validation; reconcile their data needs with the preserved v7 real-time contract before scheduling corrected rebuilds. TradingView implementation remains paused during this integration.
