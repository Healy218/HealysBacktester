# Four-process resume, paper dashboard, and new research preparation

Updated September 14 Central / September 15 UTC, 2026.

## Campaign state

The existing `v6-short-dte-20260914-now` scope was resumed using a separately
bound execution wrapper: four workers, two threads each, 24 GiB memory cap,
800% CPU, 4 GiB available-memory reserve and the existing overnight cutoff.
Original frozen numerical code and the 20 completed symbol receipts were
preserved. AMDL completed, bringing the preserved total to 21/449.

After the user selected one-minute signals/execution and then the full
1/5/15/30-minute signal universe, the main service was stopped and its timer
disabled. Status at 2026-09-15T04:02:05Z is `paused`, reason `Service stopped`.
The read-only progress timer remains available. Do not resume this old
15-minute experiment as the new version. Session-chat updates remain stopped
from the user's earlier pause; do not rebind them to an unrelated thread.

Implementation: `scripts/resume_v6_short_dte.py`, watcher integration, and
`tests/test_v6_parallel_resume.py`. Copied launch code and resource plan are
under the old campaign's `v6/execution/parallel-4/` directory.

## Dashboard and evidence implementation

Source changes were installed into `/home/healy/Coding/HealyLabsDashboard`.
The V6 Paper tab shows the read-only paper ledger, active/closed positions,
realized contribution, exits/rolls, cycles, quote validation and operating
history. Search/filter and scoped export are included. Open positions have
no invented current valuation; realized contribution is not total portfolio
return. Relay export is distinct from server-confirmed notification delivery.

The collector validates status schemas, queries the original SQLite ledger
read-only and can append deduplicated operating samples and quote records to
a separate evidence journal. Samples cannot guarantee capturing every brief
failure. Quote receipt metadata is reported without claiming full raw-byte
verification. Existing rolled-position history has incomplete entry-quote
history; collection cannot reconstruct evidence that was not recorded.

Main-repository copies: `integrations/dashboard/v6_forward.py`,
`integrations/dashboard/v6-forward.patch`, and
`tests/test_v6_forward_dashboard.py`. No private ledger data is bundled.

**Source installed; hosting not deployed and continuous evidence collection
not activated.** The home publisher needs:

```
V6_FORWARD_ROOT=/home/healy/Coding/HealysV6/nn_meta/live/v6_server
V6_FORWARD_EVIDENCE=/home/healy/.local/state/healylabs-dashboard/v6-forward-evidence.sqlite3
```

The server collector needs normal source deployment for actual delivery
counts. Missing counts appear unavailable. Existing authentication/rules
are unchanged. No new Telegram messages were sent as tests.

Validation: nine frontend tests, production build and two Chrome browser
tests (desktop and phone, using `/usr/bin/google-chrome-stable`) passed.
Filtering/export, overflow and JavaScript errors were checked; screenshots
were inspected. Python collector tests also passed. No browser installation
was needed; the user's cancellation of the bundled download was respected.

## New version preparation

See [new research scope](../specs/MULTITIMEFRAME_RESEARCH.md). Original dates
remain unchanged. The deterministic inventory enumerates 2,817 registered
parameter combinations per timeframe and 5,059,332 ticker/timeframe/parameter
combinations before directions, DTEs and events. It is explicitly a draft,
not an implemented vectorized signal engine or launch gate.

GCS listing found 2,761 symbol/year objects, 5.33 GiB, 2017–2026. Exact-name
matches to the 449-symbol scope are 220/221/221 in 2024/2025/2026. Contents,
aliases, listing dates and complete minute coverage remain unverified.
Evidence is preserved in `nn_meta/validation/multitimeframe-preparation-20260915/`.
Execution-quote coverage is also incomplete/unverified for the new universe.

Validation after catalog implementation: **1,618 tests and 18 subtests passed**
in the repository suite (69.70 seconds, 18 dependency warnings). No new
minute campaign was frozen, built or trained. Existing broad-DTE paper
services and deployed model were not replaced.
