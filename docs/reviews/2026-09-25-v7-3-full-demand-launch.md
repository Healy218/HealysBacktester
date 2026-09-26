# V7-3 full entry-demand launch — September 25, 2026

The user directed starting the next stage. The proposal catalog is already
frozen; the next operation is full entry-feature option demand, followed by
request union and targeted option-path capture. No proposal refreeze, training,
or broker change was launched.

## Full-scope storage forecast

The new read-only `scripts/forecast_v7_entry_demand.py` inspected all 591
securities and their 1,773 stores. It checked saved batch receipts/content and
counted unique symbol/decision-clock/right identities in bounded column reads.
It retained each signal timeframe separately, then deduplicated selection
identities across timeframes. The census finished in 76.5 seconds:

- 793,394,264 admitted proposals.
- 27,576,105 distinct timeframe feature decisions.
- 20,345,211 distinct contract-selection decisions.
- 101,726,055 target-selection identities (five per decision).
- At most 275,761,050 feature links (two tick kinds per target/timeframe).

The observed chain gives a conservative request bound of 122,916,244. For each
security, the bound uses the maximum number of distinct expiries present in any
nine-day future window, capped at five target identities. The same expiry picks
the same nearest eligible strike for every target at a fixed symbol, clock and
right. Ignoring first-seen, side, strike admissibility and missing prices only
increases the bound. This is a storage-only bound; selection remains causal in
the unchanged production demand code.

Planning allowances are 96 bytes/decision, 256/selection, 384/request plus its
index, another 384/exported request, 224/feature link, and 8 GiB for lineage and
working margin. These yield a **193,449,261,344-byte (193.45 GB) stress forecast**.
They are generous planning assumptions, not formal SQLite byte limits. No
whole-universe volume or ETA was extrapolated from the sparse pilot.

The allocation is **200 GiB (214,748,364,800 bytes)** for this demand stage and
**640 GB total project storage**. The measured pre-launch project footprint was
421.285 GB; baseline plus the full allocation fits within 640 GB. About 344.47 GB
was free at launch, leaving roughly 129.76 GB if the allocation were consumed.
The existing 100 GiB free-space reserve remains mandatory. The scheduler also
uses a conservative free-space floor to catch unrelated disk growth. Reaching
the stage limit, a source mismatch or a worker failure stops new scheduling.
Option captures need their own forecast against actual remaining capacity;
the existing 250 GB acquisition ceiling remains an additional constraint.

Evidence: `nn_meta/validation/v7-3-demand-census-20260925/summary` and
`nn_meta/validation/v7-3-demand-storage-plan-20260925`. The latter seals its
planner source and the per-security expiry/request ceilings.

## Active run

Service: `healys-v7-entry-demand-20260925.service`.
Invocation: `27da05b253cb4f3893d222be3eb1a834`.
Output: `nn_meta/validation/v7-3-scheduler-20260925` (the existing four verified
checkpoints are reused). The full launch has no security selectors.

The user service was observed active/running with four outer workers, one inner
thread, a 400% CPU quota, 14 GiB memory high / 16 GiB memory maximum, no cgroup
swap, nice 10, and IO weight 25. Its allowed socket family is AF_UNIX; it performs
no provider downloads. CPU/memory worker sizing derives from current available
RAM and remains capped at four. A transient user service survives terminal
closure; it is not automatically re-created after reboot.

At the sealed launch follow-up, **130/591 securities** had completed with no
failures and about 2.51 GB of stage output. This is dated progress, not completion
or an ETA. Earlier small jobs are intentionally scheduled first. Monitor the
live output rather than extrapolating that progress into a finish time.
Launch receipt: `nn_meta/validation/v7-3-full-demand-launch-20260925`.

```bash
bash scripts/start_v7_entry_demand.sh \
  --unit healys-v7-entry-demand-20260925 \
  --completion nn_meta/validation/v7-2-completion-20260925 \
  --output nn_meta/validation/v7-3-scheduler-20260925 \
  --storage-plan nn_meta/validation/v7-3-demand-storage-plan-20260925
```

The launcher verifies the sealed storage plan and runs the unchanged scheduler
in planning mode before submitting the service. While the unit remains loaded,
use `systemctl --user status healys-v7-entry-demand-20260925.service` for status.
Inspect `progress.json`, `controller.log`, and `logs/<security_id>.log` beneath
the output. After investigating any failure, restarting that loaded service
reuses completed checkpoints. After reboot, rerun the launcher. Incomplete
security directories remain counted evidence; no automatic deletion occurs.

## Validation and next gate

Two new census tests cover cross-batch variant deduplication, preservation of
symbol/right identities, empty demand and rejection of invalid clocks, schema
or row counts. The full suite passed **2,407 tests and 18 subtests**, with 20
warnings, in 112.47 seconds. The launcher also passed Bash syntax validation;
its actual launch and effective resource properties were checked.

When all demand checkpoints seal, independently reconcile the full request
union. Then resolve dated option hours and standard reference records and
cover entry fills, minute marks, exits, rolls and stock-delivery paths. This
service builds only pre-decision feature demand and does not start capture or
training automatically. V7-3 and training readiness remain open.
