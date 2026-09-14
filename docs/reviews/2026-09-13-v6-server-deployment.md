# V6 server deployment — September 13 CDT / September 14 UTC

**September 14 follow-up:** the repaired frozen model is now operating
experimental paper alerts. This review retains the earlier milestone and its
then-open blockers; current deployment evidence and remaining research limits
are in [the activation review](2026-09-14-v6-forward-activation.md) and
[HANDOFF](../../HANDOFF.md). Separate actual-1–9-DTE training is next, not started.

The frozen repaired V6 model is deployed in `/home/mrhea/HealysV6`, separate
from all four working experts. **Live V6 scoring and experimental alerts are
not active**: the complete snapshot producer and portfolio/alert path remain
unfinished. The installed observer reports that dependency as blocked.

The immutable release has 216 hash-bound files. All 40 GBT classifier/EV pairs
reproduced 130 saved historical predictions with zero numerical difference,
locally and on the server. Model config SHA256 remains
`cdacbea1bf6a07e573af46b8d266b1d82b5e3bf736945a06b929e46050fdbd6c`.
No training rule, weight, threshold or historical selection was changed.

Source was deployed through Git in isolated branches. V6 runtime commit
`75854f5`; feed update `b399662`, reconciled with newer production deployment
notes by normal merge `c84edd9`. The main research checkout and its preexisting
untracked artifacts were preserved. No force push or source scp was used.

The existing single OPRA stream now journals raw quote and trade messages,
retaining event/receipt times, conditions and raw msgpack. Its asynchronous
SDK subscription guard, empty-watch idle behavior and stall watchdog remain.
The extra V6 baseline expands the shared stock universe from 443 to 451 names.
At the initial verification there was one process per feed, 795 quote/trade
subscriptions, zero journal errors, no recording suspension and zero new
market receipts during the closed market. This does not establish coverage.
Recording suspends below 10 GiB free disk; its daily contract cap remains 1,000.

`healys-v6-observer.timer` runs every 15 minutes at :06/:21/:36/:51, with one
core and 2.5 GB maximum memory. The 03:01 UTC check completed with systemd
Result=success, exit=0, and application status `blocked/awaiting_live_inputs`.
Host state and selftest are under `nn_meta/live/v6_server/` in the V6 checkout.
That distinction prevents an idle monitor from being reported as model
validation. The prior hourly training watcher remains separate and Telegram-off.

68 targeted feed, operational regression and shared-alert tests passed on
both hosts. 31 local release/forward-recording/replay/pipeline tests passed;
the subsequent calendar guard passed the five release tests. Only relevant
checks were repeated after repairs. No notification or broker order was sent.

Alpaca's condition reference was fetched through the existing account and
saved with its retrieval receipt. Massive's prior reference explicitly maps
209 to OPRA `I`, and Alpaca defines `I` as AUTO. Both references and the mapping
are in `deploy/v6/condition-mapping/`. They establish the condition translation;
provider parity, receipt chronology and complete feed coverage remain separate.

Before the accepted recommendation is fully delivered: connect full-history
causal live features and every selected prior tick window, implement persistent
frozen portfolio allocation/exits/rolls, verify actual bid/ask and decision
chronology, and connect experimental labels/deduplication to the dispatcher.
Do not send current pre-allocation shadow candidates as if they were the
backtested portfolio. Current watch subscriptions originate after other
experts' alerts and cannot establish all V6 preceding windows retroactively.

The separate [short-DTE plan](../specs/V6_SHORT_DTE_EXPERIMENT.md) is saved;
no retraining was launched. Installation and rollback commands are in the
[recording runbook](../specs/V6_SERVER_RECORDING.md). The dashboard's new server
status integration remains pending; its existing training page is unchanged.

Final scheduled-watch verification: the automatic 03:06 UTC pass succeeded;
next scheduled check was 03:21 UTC. At 03:10 UTC there was still one process
per feed and zero raw receipts/errors during the closed market. Local receipt:
`nn_meta/validation/v6-server-setup-20260914/server-verification.json`.
