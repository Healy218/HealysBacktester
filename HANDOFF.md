# Handoff — October 6, 2026 — ETFE exact windows and acquisition tranche

## Focus and result

Continued the first-run sequence after full discovery. Built full collected-history
signal/context and factored option feature/entry windows, independently checked
decision clocks and bounds, rechecked all VOO gaps, resolved QQQ's payable date
retrospectively from an issuer source, and began exact-window option capture.
User-selected scope remains SPY/QQQ/VOO, fresh Alpaca, 0–5 DTE entries/rolls,
1–45 DTE daily context, and October 2, 2026 market end.

- Context: 137,080 batches / 13,609,133 memberships. Signal: 180 checkpoints /
  25,353 variants; 4,311,060 decision clocks / 151,005,384 logical links.
- Known-candidate union: 2,857 bar / 3,446 trade intervals; pending snapshot:
  2,678 / 3,221 after reuse. Realized holding paths: zero pending dated
  selection and execution receipts.
- Density pilot: 24 windows, 513 bars, 8,409 trades, two empty trade windows;
  duration-rank selected and not representative. Twelve VOO SIP rechecks omitted
  the missing minute each; recursive suffix stays unresolved. Invesco gives
  QQQ's March 18, 2024 payable date as April 30 retrospectively; availability
  before that event remains unknown.
- Exact-option plan: 3,036 jobs (1,369 bars / 1,667 trades). Four 128-GET runs
  completed 512 bar jobs; 512 normalized partitions / 27,073 occurrences pass
  independent raw-to-Parquet audit. No full-plan trade job has run. No process
  remains active.

## Next actions

1. Resume `alpaca-fresh-exact-options-20261006-r0` in 128-GET tranches under the
   512 MiB root, 100 GiB / 20% reserve, 1-second pacing and per-run limits.
   Remaining: 857 bar / 1,667 trade jobs, plus pagination. Normalize in
   128-partition increments; at completion run the full occurrence audit and
   reconcile capture against the exact physical union.
3. Keep the VOO gaps, dated terms/action issues and January 18 observed option
   boundary explicit. Derive holding windows only from dated eligible selections
   and actual execution receipts. Do not treat the current window envelope as a
   realized path or a full strategy demand/resource admission.
4. Continue ETFE-0 dated-input admission and ETFE-1 path demand; ETFE-4.pilot,
   freeze, build, training and evaluation remain later sequence gates.

## Selected artifacts

Review and compact evidence: `docs/reviews/2026-10-06-etfe-window-demand.md`,
`.json`, and `-evidence.zip`.

Signal/context: `nn_meta/validation/etfe-window-demand-20261006-r0/`, plan
`d6b9c26dcb8bc0dbd448b3224c665429275b8ecd2ef9e37d67ff7279923816ed`.
Exact windows: `nn_meta/validation/etfe-exact-windows-20261006-r0/`, plan
`d4a1edb79c46c043e273d494b52768d3b960aac7aec594655cfa0b61b8f16bc3`.
Gap/density check: `nn_meta/data_cache_etfe/alpaca-fresh-window-checks-20261006-r0/`.
Full exact-option capture: `nn_meta/data_cache_etfe/alpaca-fresh-exact-options-20261006-r0/`,
plan `422da8d5b5419ce2f1bf119fde720804d1d5a69552f7e8be551bbd041e9f8aea`.
Typed tranche: `nn_meta/data_cache_etfe/normalized-20261006-exact-options-r0/`,
plan `a7c14a96876c88dd47127130a4534fd7b58e2747dd1cdf64effa15e4e180788c`.
QQQ reference: `nn_meta/data_cache_etfe/issuer-fresh-invesco-20261006-r0/`.

Capture audit at the stopping point: 512/1,369 option-bar jobs terminal;
0/1,667 trade jobs terminal in this full-window plan; 2,524 jobs remain.
All 512 terminal jobs normalize with raw occurrence order preserved. Artifacts
stay under their isolated ignored roots; review ZIP and manifest bind their
hashes. No historical eligibility, ETFE-0 closure, real execution or training
is implied. Preserve unrelated dirty V6/V7 work.

[Previous handoff](handoff-history/HANDOFF-2026-10-06-before-window-demand.md).
