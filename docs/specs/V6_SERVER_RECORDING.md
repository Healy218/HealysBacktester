# Frozen V6 server recording deployment

The user approved preserving the repaired V6 model and proceeding with a
recording deployment before experimental alerts. The immutable model is
`v6-cash-repair-20260913`, config SHA256
`cdacbea1bf6a07e573af46b8d266b1d82b5e3bf736945a06b929e46050fdbd6c`.

Keep the four production experts in `/home/mrhea/HealysBacktester` on their
existing ops branch. Install the V6 research runtime in the separate Git
checkout `/home/mrhea/HealysV6`. Source and the deployable model are delivered
through Git. Do not scp untracked source into either checkout.

`scripts/package_v6_server.py` verifies the completed training receipts,
copies all 121 model artifacts and the exact trained baseline, relocates
context reference files, and retains the original input manifest. Model
bytes and the historical tick policy remain unchanged. The package contains
130 actual feature rows joined to saved ensemble predictions, including both
EV extremes. Both 40-member heads must replay those predictions within
1e-9 relative / 1e-10 absolute tolerance on the server before installation.
This checks serialization/inference, not live features or achievable returns.

The observer has separate state under `nn_meta/live/v6_server`. Its
`status.json` explicitly distinguishes `blocked`, `failed` and `recorded`.
`healys-v6-observer.timer` checks the frozen release and incoming snapshot
pointer every quarter hour, six minutes after each quarter. One core and
2.5 GB RAM bound its resource use. `selftest.json` records the host replay.
No notification or broker client is called by this runner.

The production feed update preserves the September 9 asynchronous subscription
deadlock fix, idle-watch behavior, stall watchdog and existing latest-quote
store. `NN_META_OPTION_RECORD_TICKS=1` enables raw OPRA quote/trade journaling
on the same connection. `NN_META_ADDITIONAL_STOCK_SPECS` adds the frozen V6
universe to the existing stock stream. Do not start a second competing stream.
Tick recording suspends below 10 GiB free disk; gaps/errors remain explicit.
The daily distinct recorded-contract cap is 1,000. Quote subscriptions and
existing alerts retain their current watch set.

The condition mapping under `deploy/v6/condition-mapping/` is supported by
both provider references: Massive options/trade condition 209 explicitly
maps to OPRA `I`; Alpaca's options condition endpoint defines `I` as AUTO.
It establishes that mapping only. Receipt/SIP timing, capture coverage and
external technical parity are separate evidence requirements.

## Installation

In the Git-deployed V6 checkout, using the existing production Python:

```bash
/home/mrhea/HealysBacktester/venv/bin/python -m scripts.install_v6_observer \
  --production /home/mrhea/HealysBacktester --run
```

After the separate feed change is pulled into production, its
`scripts/configure_v6_capture.py --v6-root /home/mrhea/HealysV6 --run`
backs up the environment with mode 0600, enables the two explicit nonsecret
settings and restarts the two feed processes. The original cron watchdog
commands remain valid. Inspect heartbeat counters, journal errors, process
counts and stock-universe size after startup. A quiet closed market cannot
validate actual receipts.

## Remaining activation requirements

There is **no connected live snapshot producer yet**. An option watch list
populated after prior experts' alerts cannot provide the preceding 15-minute
windows for every new V6 candidate. Do not label a healthy feed heartbeat as
complete capture or model scoring. The observer reports this dependency as
blocked until a real producer supplies sealed snapshots.

Snapshots need the original full technical history extended causally, raw
spot, prior-session surface/context, prior-date contract evidence and every
selected tick window. Preserve all 164 feature definitions. The incoming
pointer is `incoming/latest.json` with `path` and external `sha256`; see
`V6_FOLLOWUP_RUNBOOK.md` for its evidence schema. The recorder verifies model,
history origin, policy, timestamps, full universe and input hashes before
scoring. It does not impute an unavailable tick window.

Before enabling experimental notifications, connect and validate persistent
five-slot/one-symbol allocation, exits/rolls, actual bid/ask observations,
deduplication and the existing shared dispatcher. Shadow candidate selection
alone is before portfolio allocation and must not be presented as the tested
portfolio. The classifier predicts option excess-return success, so do not
label that score a calibrated probability of profit. Experimental alerts
remain disabled until this path is implemented and checked end to end.

Rollback is additive: disable `healys-v6-observer.timer`, restore the backed-up
feed environment, and restart those feed processes. Preserve journals and
the V6 release. Existing expert source, model selections, alert floors and
cron cadence are not changed by the recording deployment.
