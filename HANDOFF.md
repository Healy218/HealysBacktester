# Handoff — October 5, 2026 — Joined diagnostic schema

## Focus and completed result

Continued fresh Alpaca-only ETFE with actual 0–5 DTE including qualifying 0DTE.
Completed **ETFE-2.joined-schema** within its bounded diagnostic scope.
[Review](docs/reviews/2026-10-05-etfe-joined-schema.md),
[machine receipt](docs/reviews/2026-10-05-etfe-joined-schema.json).

- Joined all 221 registered values plus 221 masks for every one of the original
  458,133 pilot events across nine ticker/timeframe scopes.
- Kept per-variant MA overrides, original event/target identities and lineage.
  Matrix, reasons, modeled availability and row metadata are separate Parquets.
- Independent natural-key audit reconciles all 101,247,393 value cells and every
  mask, reason, clock, original event field and row/source link exactly.
- 59,917,288 values are finite; 41,330,105 missing. Missingness includes structural
  parameters, insufficient history and unresolved inputs; no imputation.
- Every one of 96 chunks passed changed-batch-boundary checks. Actual one-chunk
  stop/resume preserved five files and wrote the remaining 95 chunks.
- 173 focused ETFE tests passed, including 16 new join guard/recovery tests.
- Join compute 35.15s, peak RSS 1.00 GiB, root 193.14 MB. No new capture,
  execution simulation, labels, training or deployment.

## Evidence boundary and stopping point

All outputs remain diagnostic and unadmitted. Each row has 75–100 missing
fields; schema completeness does not establish complete historical inputs.
Seven option-context and eleven dated contract/sector fields remain missing.
Selected contract and actual DTE are unknown; acquisition candidates/target DTE
never substitute for historical selections. Modeled clocks do not prove dated
provider publication. Raw stock values still need dated action reconstruction.

No ETFE process remains running. Usable history remains null. Full-history
feature validation, dataset admission, training and integrated pilot stay open.

## Next work

1. **ETFE.provider-contract / ETFE.history-boundary:** resolve dated actions,
   contract/sector identities, complete option surfaces, session and publication
   evidence. Preserve empty/ambiguous observations and all known minute gaps.
2. **ETFE-1.demand:** finish full phase-B/C signal/feature/holding/roll demand,
   reconciling request/storage budgets before bulk capture.
3. **ETFE-4.pilot:** integrate capture → features → execution → dataset → training
   smoke, with resource/recovery evidence before full builds or freezes.

## Artifacts and constraints

Selected: `nn_meta/validation/etfe-joined-20261005-r0/`.
Plan SHA256: `2395d11076c481cc697cd6848f3682cd18a8866bbbcd9b79b18f37525e08213c`.
PLAN/COMPLETE, 96 chunk receipts, 384 payloads, independent/resume audits and
payload index are local. Evidence ZIP contains 111 metadata/source/audit members
and payload hashes. Market inputs remain 1,249 partitions / 1,955,680 rows.
[State](docs/CURRENT_STATE.md#october-4-etfe-fresh-alpaca-setup),
[commands](docs/reference/ETFE_SETUP.md#joined-diagnostic-schema),
[contract](docs/specs/ETFE_JOINED_SCHEMA_20261005.md).

Source-bound consumers are immutable: change them only in successor studies.
Preserve unrelated dirty work, including DECISIONS/EXPERIMENTS additions.
[Previous handoff](handoff-history/HANDOFF-2026-10-05-before-joined-schema.md).
