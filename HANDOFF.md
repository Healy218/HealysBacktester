# Actual exit fills and reconciliation implemented

September 10, 2026. User chose the first waiting-for-build task: actual fills,
partial exits, fees, realized P/L and broker reconciliation. Implemented only
in ops/server-alert-readiness-20260906; not deployed. Home campaign untouched.
Production remains at the previously recorded d2708d6; not rechecked here.

Commands, schema, limitations, read-only normalized broker JSON workflow and
rollback precautions: docs/reviews/2026-09-10-trade-accounting.md.
Existing /sold ID still closes without inventing a fill. Partial sales leave
remaining contracts tracked. Net P/L requires actual entry and sale fees.
SQLite migrations preserve existing positions; command events retain fee edits.
Broker reconciliation requires supplied records; no actual broker comparison
or production mutation was performed. No private holdings were read.

Validation: full ops suite passed 689 tests and 18 subtests. The final
broker-reference immutability / oversized sale-ID guard then passed the
22-test accounting suite. git diff --check passed. Existing dependency
warnings only.
Tasks 2–4 remain unstarted, pending the user's assessment of this change.
