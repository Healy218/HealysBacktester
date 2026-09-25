# Handoff — 2026-09-25 — V7-2 catalog sealed, daily context due

Read `TODO.md` first. The previous handoff is archived at
`handoff-history/HANDOFF-2026-09-25-before-alpaca-bridge-and-v7-audit.md`.
Main is the operational branch. The worktree contains extensive pre-existing
unrelated edits; stage only owned changes. Do not restart the V7-2 proposal
catalog or alter its frozen stores. V7-1 is complete; 7-2 remains open for
full-scope daily context. V7-3 has not started.

## V7-2 catalog verdict and remaining daily scope

The catalog controller exited successfully at 10:11:59 CDT with 591/591
securities and 1,773/1,773 compact 5/15/30 feature/proposal stores. The deep
audit opened every store and verified declarations, source and input bindings,
compact epoch and proposal batch receipts, 8,451 variants per security, the
221-column row schema, 4,314 admitted action/coverage events, and 344.75 GB
free disk versus the 100 GiB floor. All 415 reused securities reverified under
their exact action/receipt manifest. Ten additional securities built under an
old builder hash passed current-loader replay on all three timeframes. No
frozen receipt was edited. The maximum parsed worker RSS was 2,846,392 KiB;
four outer workers and one inner thread were configured. The final review is
`docs/reviews/2026-09-25-v7-2-deep-audit.md`; local validation reports include
`nn_meta/validation/v7-2-final-deep-gate-20260925.json`.

The catalog subgate passes. The **full 7-2 item does not**: its 591-security
joined daily/market context with next-session availability and warmup
missingness is absent. Existing stock-daily and surface components each cover
339,640 eligible sessions; the dated sector component maps the same sessions,
including 22,079 explicit unknown-sector sessions. The daily-context builder
has only a 300-day SPY pilot. Build and audit the full joined daily context
before marking 7-2 complete or starting V7-3. Do not treat proposal stores
as training or trading readiness.

## Alpaca paper bridge

The fresh account remains distinct from the old V6 simulator. The new bridge
is `integrations/alpaca_paper/v6_bridge.py` and its guarded CLI is
`scripts/run_v6_alpaca_bridge.py`. It uses structured future V6 positions and
leg-close events, stable client order IDs, a private SQLite intent/observation
journal, real paper-account reconciliation, fresh OPRA quote validation,
provider-mark limit preference (fresh midpoint fallback), whole-contract
buying-power sizing, and broker fill records. A lost POST response blocks
blind retries. The CLI creates `TradingClient(..., paper=True)` only and
requires a manifest opt-in for `--submit`.

A read-only real-account preview succeeded and saw zero scanner events. The
fresh state still has no portfolio DB; `scanner_enabled=false` and
`order_submission_enabled=false` in its restart manifest. **No Alpaca order
has been submitted.** Next: run the fresh V6 scanner prospectively, preview
genuine new structured events, test broker lifecycle reconciliation against
those events, then consider enabling paper submission. The old simulator's four
positions must never be backfilled. The account-only monitor timer continues.
Broker P/L remains separate from Stonks' simulator projection. Multi-roll
positions currently block for review; open/partial/uncertain broker orders
also block further actions. Finish lifecycle handling before activation.

Focused bridge tests passed; the full suite passed 2,399 tests, 18 subtests
and 20 warnings after the final append-only observation change. Commit
`75e2374` contains the initial bridge and audit tools, pushed to main.
Subsequent script/journal/doc changes need a focused commit and push.

## Other live work

The read-only V5/V6 incubator after-close timer is enabled and its September 25
scheduled run still needs confirmation. Massive Options Advanced decision is
due October 2; V6's frozen feature path still uses Massive and historical
Alpaca OPRA coverage/feature parity remain unproved. Preserve one more month
if replacement evidence is incomplete. Prior operational details are in the
archived handoff and `TODO.md`.
