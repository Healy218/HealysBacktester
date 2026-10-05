# ETFE action process-date tail — October 5, 2026

The fresh action capture returned 33 dividends, but its process-date filter ends
October 2. The bounded October event probe contains September SPY/QQQ dividends
with October process dates. Therefore that query interval cannot enumerate all
actions effective inside the fixed price window. The earlier root remains valid
for its declared process-date scope and remains immutable; no completed gate is
reopened or relabeled.

Extend only reference discovery with three fresh all-type/all-quality Alpaca
corporate-action queries, one per ETF, process dates October 3–December 31, 2026.
This 90-day tail is an explicit bounded search, not proof of completeness or a
change to the October 2 market-price cutoff. Capture may include future-effective
actions; retain them and mark window membership separately. Never treat current
capture as a historical publication or admit an action merely from its ex-date.

Use isolated `alpaca-fresh-actions-tail-20261005-r0`. Bind every retained parent
file (excluding the writer lock), sources and exact requests in PLAN. Reuse the
verified immutable HTTP/shape/page-chain functions without altering their source.
One serial GET per second, max 32 requests/15 minutes, 8 MiB response, 128 MiB root,
existing disk/RAM reserves. Failed requests remain uncommitted and stop the run;
resume retries later after persisted provider cooldown. No automatic retries in
this extension. Preserve all raw occurrences and never overwrite committed pages.

Inspect the already captured event stream without further downloads. Parse only
complete blank-line-delimited SSE blocks; retain a capped trailing fragment as
unparsed bytes. Require mutation ID, aware emission clock, action and object.
Check clocks against requested bounds. Keep all complete ETF insert/update/delete
observations with source-body hashes and block ordinals; unrelated events count
only toward probe scope. Count repeated event IDs without silent deduplication.
An emission time on a later update is not the original announcement time. Neither
the January welcome-only response nor the capped October replay proves absence
or complete historical coverage. Do not connect these receipts to feature clocks.

Exit: all three tail page chains terminal; exact tail occurrences and ETF event
lineage retained, independent raw/inspection reconciliation, and tests for partial
blocks, multiline SSE, duplicate IDs, timestamp/schema drift and tail boundaries.
Report in-window/outside-window actions and cross-reference native IDs between
REST tail and mutations. Dated adjustment admission remains unresolved. Broader
mutation acquisition requires measured volume and a separate bounded plan.
