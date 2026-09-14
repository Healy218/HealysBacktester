# Frozen V6 is on the server; live scoring and alerts are still blocked

The user approved the prior recommendation: preserve repaired V6, deploy beside
existing experts, record live decisions, then enable labeled experimental alerts
after checking the full path. Keep a separate actual-short-DTE experiment.
**The deployment infrastructure is installed, but the requested end-to-end
activation is NOT complete. Do not describe V6 as generating live alerts.**

## Installed September 13 CDT / September 14 UTC

- V6 separate server Git checkout: `/home/mrhea/HealysV6`, branch
  `ops/v6-forward-20260914`, runtime commit `75854f5` (model package `86bd788`).
- Production stays `/home/mrhea/HealysBacktester`, branch
  `ops/server-alert-readiness-20260906`. Feed code `b399662`; merged/published
  with the existing deployment notes as `c84edd9`. No existing expert scanner,
  model, threshold, dispatcher membership or cron cadence was changed.
- Frozen release: `deploy/v6/releases/v6-cash-repair-20260913/`, 216 bound files,
  40 GBT members, 164 features, 449 frozen symbols. Model SHA256
  `cdacbea1bf6a07e573af46b8d266b1d82b5e3bf736945a06b929e46050fdbd6c`.
  Release SHA256 `3bc974679fff04044002f833cbb4c9246f63fd4d9370c04985f5f6ca7597764f`.
  Original weights/baseline/tick policy are unchanged; portable context
  references and the original input manifest are retained together.
- Both local and server selftests reproduced **130 actual saved predictions
  exactly**, for both classifier and EV heads. This validates serialization
  and inference, not live features or executable trade returns.
- `healys-v6-observer.timer` is enabled every quarter hour at :06/:21/:36/:51.
  One core, 2.5 GB RAM ceiling. Its state is
  `/home/mrhea/HealysV6/nn_meta/live/v6_server/status.json`; host replay is
  `selftest.json`. At 03:01 UTC the service had Result=success/exit=0 while the
  application truthfully reported `blocked / awaiting_live_inputs`.
- Existing shared OPRA feed now records raw quotes AND trades on its one
  connection, with SDK callback receipt timestamps and preserved raw msgpack.
  795 watched contracts; zero journal errors at startup. The shared SIP stock
  universe expanded from 443 to **451**, covering V6 alongside older experts.
  One process per feed was verified. The closed market had produced zero new
  raw ticks at the verification; do not claim actual capture coverage yet.
- Production feed retains its asynchronous subscription/deadlock fix, idle
  gate and stall watchdog. Recording suspends below 10 GiB free disk, and the
  daily distinct contract admission limit is 1,000. Current watch membership
  is still the existing experts' contracts, not full V6 candidate coverage.
- Provider condition mapping is prepared under `deploy/v6/condition-mapping/`:
  Massive's saved 209 reference explicitly maps to OPRA `I`; Alpaca's live
  condition reference independently defines `I` as AUTO. This does not certify
  receipt/SIP parity, complete capture, or aggressor side.
- Feed installation receipt/0600 environment backup:
  `/home/mrhea/HealysBacktester/nn_meta/live/feeds/data/v6-installations/20260914T025948224730Z/`.
  Observer install receipt:
  `/home/mrhea/HealysV6/nn_meta/live/v6_server/installations/20260914T025821749091Z/`.
- **Alerts remain disabled.** No test Telegram message, V6 notification or
  broker order was sent. The existing hourly TRAINING watcher still follows
  the completed repaired run with Telegram OFF; it is separate from this new
  quarter-hour SERVER observer.

## Work required next to fulfill the accepted recommendation

1. Build/connect the actual sealed live snapshot producer. The existing
   `v6_inputs.py` is a strict consumer, and `seal_v6_live_snapshot.py` seals
   supplied files; neither obtains the complete live inputs automatically.
   The incoming pointer is `nn_meta/live/v6_server/incoming/latest.json` with
   `path` and external `sha256`. The observer is genuinely blocked without it.
2. Preserve original full technical-history origins, extend causal context,
   supply raw prices, prior-session surface/context and prior-date contract
   evidence, and obtain preceding tick windows for ALL selected candidates.
   Existing post-alert watch registration cannot recover a prior 15-minute
   receipt window. A 1,000-contract connection is not evidence of coverage of
   the 449-symbol multi-DTE/call-put universe. Determine a compatible complete
   capture path without inventing missing ticks or silently reducing the
   universe. Reuse Massive data where applicable; V6 training DID use actual
   Massive quotes/trades, with aggregate-bar prices for P&L labels.
3. Connect persistent frozen five-slot/one-symbol allocation and causal
   exits/rolls, then the existing production dispatcher/deduplication. Current
   ShadowStore selects threshold/best-DTE candidates BEFORE portfolio slots;
   those observations are not the 241-position evaluated strategy. Do not
   turn every threshold pass directly into an alert.
4. Verify actual live features, chosen contracts, receipt/quote timestamps,
   ask/bid entry and exit handling, slot decisions and deduplication. Only
   then enable the user-authorized experimental alerts. Do not label the
   classifier's excess-return label as a calibrated profit probability.
5. The separate short-DTE experiment plan is saved, **not launched**:
   `docs/specs/V6_SHORT_DTE_EXPERIMENT.md`. It requires actual expiry 1–9
   calendar days, not merely a short target with the old wide expiry search.

Runbook: `docs/specs/V6_SERVER_RECORDING.md`. Review:
`docs/reviews/2026-09-13-v6-server-deployment.md`.
New targeted verification: 68 feed/legacy ops/alert tests passed locally AND
on server; 31 release/shadow/replay/pipeline tests passed locally. Calendar
follow-up passed the five release tests. Original 1,537-test training repair
verification remains recorded in the archived handoff.

## Workspace and deployment branches

The main checkout stays uncommitted; preexisting `nn_meta/artifacts_v6/` is
untouched and was excluded from the deployment commit. Do not add it.
Isolated local worktrees: `/tmp/healys-v6-forward-deploy` and
`/tmp/healys-v6-feed-deploy`. Feed port edits exist on the latter ops branch;
main's earlier option_stream version lacks the production deadlock fix and
must NOT overwrite the deployed merged feed. Deploy source through Git only.
The new V6 source commit includes the previously uncommitted training repair
and forward-input consumer code because the isolated runtime depends on it.
No new training run was started. Dashboard URL: https://stonks-22367.web.app
The private dashboard still has its existing training integration; the new
server `status.json` has not been added to its publisher UI.

## Retained training and selection audit

Repaired campaign `v6-cash-repair-20260913` completed 19:47 UTC Sep13. GBT,
EV threshold .05, no DD brake; +648.8249% historical portfolio, 12.5673% maxDD,
241 positions, all target DTE 30/45. Matching baseline +90.6059%. The final
May–August tail overlaps previous selection/tests and is not a fresh holdout.
All 32 aggregate execution comparisons matched the independent ledger.
The full readiness inventory still blocks quote/roll evidence, forward
execution, external feature/feed parity and scanner operating review.

The exact selection audit is `docs/reviews/2026-09-13-v6-dte-selection-audit.md`.
Short DTEs WERE trained/scored: 450 sub-10 candidates passed EV, 78 won their
DTE comparison; 43 hit full slots and 35 lost to higher same-bar EV. Among
358 candidates >1,000% net, 356 failed EV and two lost DTE selection. All 37
>200% candidates after DTE selection lost at allocation. No 200% return cap
exists. Magnitude training winsor bound was +350.22%; V4/V5 already had
+358.06%/+373.57%. Do not invent a new return cap or guarantee a 1,000% winner.

Historical raw Massive quote/trade data contributed features (all 241 rows
covered); option aggregate OPEN/CLOSE prices and modeled costs supplied P&L.
The 5-minute-entry revalidation is a limit from signal close to the next option
bar, not measured scanner/network delay. Trade details are preserved in
`nn_meta/validation/v6-trade-review-20260913/selected-trades.csv`.

Previous complete context: `handoff-history/HANDOFF-2026-09-13-before-v6-server-deployment.md`.

Final scheduled-watch verification: the automatic 03:06 UTC pass succeeded;
next scheduled check was 03:21 UTC. At 03:10 UTC there was still one process
per feed and zero raw receipts/errors during the closed market. Local receipt:
`nn_meta/validation/v6-server-setup-20260914/server-verification.json`.
