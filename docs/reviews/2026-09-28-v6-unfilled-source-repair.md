# V6 never-filled source reconciliation — September 28, 2026

The absence of orders after PDD was partly a scanner failure. ANF's source
projection remained open after its broker entry was blocked by a stale quote
and then missed its five-minute submission deadline. It required a fresh option
mark on each scan; unavailable marks triggered the global unresolved-monitoring
guard before new signals could be evaluated. Alpaca held no ANF position.

## Deployed repair

Scanner v4 reconciles the authenticated broker account before each frozen scan.
An initial simulated projection is archived only after its entry window expires,
with no broker holding and no pending, uncertain or ever-filled related order.
The original row moves transactionally to `broker_unfilled_sources`; source
events and the order journal remain. No close, return or equity change is invented.
Pending orders and partial fills retain their protections. Rolled positions need
their own lifecycle reconciliation and are not retired by this rule.

Deployment at **14:21:22 Central** archived ANF's never-filled projection with
zero actual holdings or pending orders. The pre-change database, manifest and
unit are preserved under the paper state's
`runtime-revisions/scanner-v4-20260928/`. Original model and source hashes remain.
New adapter sources are additive manifest bindings, committed as `eb8bbae`.

- Launcher: `scripts/run_v6_alpaca_scanner_v4.sh` (same autosized eight-worker
  ceiling and 12-GiB service cap).
- Policy: `archive-expired-never-filled-source-v1`.
- Current paper-manifest SHA:
  `55296139aa80f9042f1b9d4cefffec39789ff65989873bccd511b6b04749334e`.
- Deployment receipt:
  `nn_meta/validation/v6-scanner-source-repair-20260928/deployment.json`.
- Live per-pass evidence: paper state's `scanner-source-reconciliation.json`,
  `scanner-dispatch-status.json`, `status.json` and `broker-status.json`.

Forty-eight focused reconciliation, order, runtime and launcher tests passed;
the subsequent v4 autosizing regression also passed (three launcher cases).
Shell/systemd checks passed.

The **14:30 scheduled scan completed in 254.253 seconds**: 444 symbols had
current bars, five did not; 53 fresh signals across 49 symbols, 274 candidate
rows and zero detection errors. Five selections yielded two simulated entries
(IONQ and CRM) and three unfilled simulations. At 14:34:30, the independent
broker poll submitted both entries and received two distinct `pending_new`
Alpaca order IDs. This verifies restored detection, scoring and independent
submission; pending is not a fill. Preserved evidence:
`nn_meta/validation/v6-scanner-source-repair-20260928/prospective-scan/`.

## Mode boundary

Research simulation uses hypothetical fills and labels independent of broker
participation. Broker paper trading uses actual Alpaca orders, fills, balances
and holdings. An unfilled attempt is an execution outcome, not a reason to stop
future signal detection. Current v4 repairs the expired initial-entry coupling;
it is not a complete replacement of the frozen scanner's simulated portfolio
with a broker-native lifecycle. Do not claim full mode separation from this fix.
