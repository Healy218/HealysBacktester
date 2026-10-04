# ETFE phase-A demand and January coverage expansion

Continue fresh Alpaca acquisition under the current 0–5 DTE scope. This revision
enumerates the complete **calendar-level** phase-A demand over the collected
January 2024–October 2, 2026 window. It does not claim an admitted research start,
complete historical listings, strategy proposals, or phase-B/C holding demand.

For each Alpaca stock-calendar session and each of SPY/QQQ/VOO, enumerate all
calendar expiry dates at 0–5 DTE for purchase discovery and 1–45 DTE for context.
Use the union, including weekends, holidays and expirations beyond the fixed
last observation date. Do not filter expirations through the stock calendar.
Request both current statuses, both rights and all strikes; current fields remain
discovery-only. Bind mathematical catalog identities, feature/execution contracts,
the current scope and calendar. There is no new context ticker: SPY supplies it.
Inventory every session/expiry/status edge and factor identical physical queries
by route and parameters, independent of their purpose labels.

Completed fresh queries may satisfy identical transport demands only after their
page chains verify. Record their plan/job IDs; do not relabel their historical
purpose or treat discovery as dated eligibility. Conditional weekly targets still
need dated listing evidence. Preserve all twenty families and all timeframes.
Phase-B signal/feature/trade windows, phase-C holding/roll/stock-quote paths,
dated action/terms/session evidence and pre-January history remain unresolved
frontiers, not zero demand. Exact final request/storage estimates await them.

## Bounded continuation

1. Discover every calendar expiry January 1–March 4, 2024 for all three ETFs,
   both statuses, reusing verified exact fresh queries. This covers January 18/19
   surfaces to 45 DTE and earlier expiry discovery, without invented OCC symbols.
2. Request January 1–17 option minute bars for every returned symbol from that
   discovery inventory, in batches of at most 100. This diagnoses earlier
   observations within that inventory only; longer expiries and pre-January
   observations remain outside this test. No trade-history floor is inferred.
3. Request full civil-day January 18/19 bars for every returned 0–45 DTE symbol.
   Distinguish context (1–45) and purchase-discovery (0–5) purposes. Exclude
   contract/day pairs already covered by a verified identical full-day request,
   retaining links to those captures. Fetch every page; don't select strikes by
   closing premium or outcomes. Final eligible surfaces require dated references.
4. Normalize each completed new plan and independently reconcile every raw row.
   Report absent symbols and first observations per symbol/ticker/date; an empty
   response is unresolved absence, not proof of no trading or a provider floor.

The physical request floor is known after discovery; pagination is estimated
using earlier measured bars per returned symbol and bytes per row, with a
390-row regular-minute scenario and explicit additional-hours uncertainty.
This is a bounded transport study, not the integrated ETFE-4.pilot.

Use the existing immutable raw engine: 128 GETs and 30 minutes per invocation,
512 MiB per raw root, 32 MiB per page, serial 60 GET/minute, existing RAM/disk
reserves and no worker pool. At most four invocations each for discovery,
boundary bars and daily bars: 1,536 GETs total, and a one-hour wall-clock ceiling
from the first network attempt. Stop on exhausted ceilings and report unfinished
work; no automatic uncapped campaign. Normalization retains its 2 GiB/root,
5,000-row batches and two-hour ceiling. Up to three new normalized roots; check
actual disk reserves before each run. No model training, freeze or deployment.

Alpaca documents explicit expiry filters and current-status defaults on its
[contracts route](https://docs.alpaca.markets/us/reference/get-options-contracts).
Its [bars route](https://docs.alpaca.markets/us/reference/optionbars) limits requests
to 100 symbols, sorts by symbol then time, and requires following continuation
tokens even after short pages. These details were checked October 4, 2026;
the existing 1,000-record discovery page size remains conservative.
