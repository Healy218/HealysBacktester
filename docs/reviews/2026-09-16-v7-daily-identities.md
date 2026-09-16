# V7 full-window daily listed-identity acquisition

Month-end masters supported membership selection, but did not supply exact-day
identity evidence for every raw feature-history row. A full daily acquisition
now covers the requested 1,129-session window with five listed-exchange queries
per day: **5,645 shards**. It is still running; this review does not claim complete
capture, a completed full identity panel or training readiness.

`scripts/capture_v7_daily_identities.py` requests only dated listing/reference
metadata from Massive, restricted to ARCX, BATS, XASE, XNAS and XNYS, the five
primary exchanges found for active source symbols in the retained monthly masters.
No stock prices or OTC exchange data are requested. Massive documents `date` as
the historical reference date and `exchange` as the primary exchange MIC filter.
[Official endpoint](https://massive.com/docs/rest/stocks/tickers/all-tickers).

The capture validates every response's exchange, market, locale and active flag;
duplicate symbols, pagination loops and changed origins fail. Missing FIGIs are
retained as unresolved. Provider pagination credentials are stripped, original
returned records are preserved, and each complete shard binds its query and
capture code. A locked acquisition declaration fixes every date/exchange and
code hash. Four spawned workers use one inner thread, the existing 250 GB shared
quota and 100 GiB disk reserve. Completed shards are immutable; failed partials
remain preserved and retries account only for newly written bytes.

`--max-shards` bounds an invocation for access checking without changing the full
declared scope. The successful first invocation captured March 15, 2022 for all
five exchanges: 12,038 listed records over fourteen response pages. The full
invocation then resumed the same declaration for the remaining 5,640 shards.

## Identity join

`scripts/build_v7_identity_panel.py` requires the complete capture summary and
verifies all daily source shards. It joins reference records to every retained
raw daily row, compares all eligible rows against the previously frozen security
IDs, and saves both complete raw-history identities and eligible comparisons.
It will run after acquisition completion; it has not yet run at full scope.

`nn_meta/v7/identity_panel.py` uses exact source dates. The existing OCC-root
punctuation normalization is explicit; collisions stay ambiguous. It distinguishes
absent listed symbols, missing FIGIs and known identities. Continuity breaks at
unknown IDs, changed IDs and missing calendar sessions, including nullable-string
missing values. It does not carry a monthly identity backward or forward. Later
data cannot alter an earlier span. Aliases still require dated stitching; identity
reference does not establish complete action/no-event evidence or original
publication vintage of fundamentals.

Actual first-day validation:
`nn_meta/validation/v7-daily-identity-first-day-20260916`. All **296 eligible
security/date identities** match the dated listed records. The original five
captures and stock summary are hash-bound. This is a first-day integration check,
not evidence about the other 1,128 sessions.

## Live continuation

Capture root: `nn_meta/data_v7/daily-identities-20260916`.
Log: `/tmp/v7-daily-identities-capture.log`. Exact current process handle and
latest verified count are in HANDOFF. Do not restart because a polling interval
expires. Poll the existing handle; the acquisition lock prevents concurrent
writers. Resume only after confirmed termination, with the same code/declaration:

```bash
./venv/bin/python scripts/capture_v7_daily_identities.py \
  --calendar nn_meta/data_v7/start-20220315/calendar.json \
  --output nn_meta/data_v7/daily-identities-20260916 \
  --budget-root nn_meta/data_v7 --workers 4
```

After the complete summary exists and validates:

```bash
./venv/bin/python scripts/build_v7_identity_panel.py \
  --stock-daily nn_meta/validation/v7-stock-daily-20260916-midpoint \
  --identities nn_meta/data_v7/daily-identities-20260916 \
  --output nn_meta/validation/v7-daily-identity-panel-20260916
```

Eleven focused cases cover query restrictions, response validation, cross-page
duplicates, credential stripping, ambiguous symbols, nullable gaps and prefix
stability. Final full-suite evidence is recorded in HANDOFF. V6 source/runtime
unchanged. No training launched; eight substantive readiness stages remain open.
