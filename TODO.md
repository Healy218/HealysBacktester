# Current work — audit remediation

The user authorized fixing all findings from the [September 5 audit](docs/reviews/2026-09-05-adversarial-audit.md). Prior campaign tasks are preserved in [the pre-repair task list](handoff-history/TODO-2026-09-05-before-audit-fixes.md).

- [x] Implement core causal signal, ranking, scanner-save, and preprocessing repairs.
- [x] Add core adversarial regression tests and pass targeted checks.
- [x] Complete data/execution/PIT/SPX0 repairs and regression tests.
- [x] Complete evaluation/accounting/provenance repairs and regression tests.
- [x] Complete live/FA/operational repairs and regression tests.
- [x] Run the integrated test suite, inspect cross-component changes, and record final coverage.
- [ ] Rebuild and validate affected production artifacts in a separately provisioned campaign. Existing corrected-code checks do not recompute past performance.

Current implementation status and validation are tracked in [the remediation report](docs/reviews/2026-09-05-remediation.md). No cloud campaign or deployment is part of this local repair session.

Final local validation: **615 tests passed**, no failures/skips, plus shell syntax and whitespace checks. All 51 main findings and four additional code concerns have repairs; deployment/artifact revalidation is the remaining operational boundary.
