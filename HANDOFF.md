# Handoff — October 6, 2026 — ETFE exact-option capture complete

## Focus and result

Resumed and finished `alpaca-fresh-exact-options-20261006-r0` in 128-GET
tranches (1-second pacing, 512 MiB root and free-space guards), normalizing in
128-partition increments after each tranche. Scope is unchanged: SPY/QQQ/VOO,
fresh Alpaca, 0–5 DTE entries/rolls, 1–45 DTE daily context, October 2, 2026 end.

- Capture: all **3,036 / 3,036** jobs terminal (1,369 bar / 1,667 trade) across
  3,116 committed pages (80 pagination pages). Raw root 221 MB.
- Normalization: 3,036 partitions, **2,275,130 occurrences** (70,354 bars /
  2,204,776 trades), no quality flags; typed root 202 MB.
- Empty windows: 194 bar and 112 trade requests returned zero rows (completed
  responses, not failures).
- New `scripts/audit_etfe_exact_option_capture.py` (full scope; the 512-only
  tranche auditor and its evidence are untouched) writes
  `FULL_CAPTURE_INDEPENDENT_AUDIT.json`. It reconciles every raw page/occurrence
  to Parquet by hash and independently proves the captured windows equal the
  DEMAND pending union minus the density-pilot windows over 754 route/symbol
  pairs (11,899,020 s·symbol captured + 155,400 s·symbol pilot reuse).
- Loop note: both `acquire_etfe_alpaca.py run` and `normalize_etfe.py run` exit 2
  whenever work remains; that is not a failure.

## Next actions

1. Keep the VOO gaps, dated terms/action issues and January 18 observed option
   boundary explicit. Derive holding windows only from dated eligible selections
   and actual execution receipts; this capture covers known-candidate windows,
   not realized paths or full strategy demand/resource admission.
2. Continue ETFE-0 dated-input admission and ETFE-1.path-demand. ETFE-4.pilot,
   freeze, build, training and evaluation remain later sequence gates.
3. Optional: fold the full-capture audit into the window-demand review package
   (`package_etfe_window_review.py`) if a sealed review ZIP is wanted.

## Selected artifacts

Capture: `nn_meta/data_cache_etfe/alpaca-fresh-exact-options-20261006-r0/`,
plan `422da8d5b5419ce2f1bf119fde720804d1d5a69552f7e8be551bbd041e9f8aea`.
Typed: `nn_meta/data_cache_etfe/normalized-20261006-exact-options-r0/`,
plan `a7c14a96876c88dd47127130a4534fd7b58e2747dd1cdf64effa15e4e180788c`,
full audit `FULL_CAPTURE_INDEPENDENT_AUDIT.json`.
Window demand and review: `nn_meta/validation/etfe-exact-windows-20261006-r0/`,
`docs/reviews/2026-10-06-etfe-window-demand.md`.

No historical eligibility, ETFE-0 closure, real execution or training is
implied. Preserve unrelated dirty V6/V7 work.

[Previous handoff](handoff-history/HANDOFF-2026-10-06-before-exact-capture.md).
