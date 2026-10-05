# Handoff — October 5, 2026 — Remaining feature components

## Focus and completed result

Continued fresh Alpaca-only ETFE with actual 0–5 DTE including qualifying 0DTE.
Completed **ETFE-2.remaining-components** within its real/synthetic evidence scope.
[Review](docs/reviews/2026-10-05-etfe-remaining-features.md),
[machine receipt](docs/reviews/2026-10-05-etfe-remaining-features.json).

- Implemented the remaining 100 fields; all 221 registered component names
  reconcile. Full joined schema and input admission remain separate.
- 77 static fields for all 8,451 catalog variants; all 25,353 ticker combinations
  replayed. 152,711 signals preserve every one of 458,133 original event links.
- Signal age uses the full January 2 prefix: 35,378 signals have a preceding
  signal before January 18. Target replicas do not advance the age counter.
- Added per-event MA fast/slow overrides and 2,073 daily-context rows spanning
  all 691 stock sessions. Next-open availability and calendar gaps preserved.
- Ten VOO days have invalid closes from twelve missing minutes. Daily table:
  5,588 finite raw-stock values, 15,142 missing cells, no forward-fill.
- Corrected two previously unimplemented Setup numeric formulas in a versioned
  binding amendment. Existing registry and completed artifacts remain unchanged.
- Independent static/daily/signal/MA/missingness/membership and minute-to-daily
  audits pass. All-variant prefix/batch checks and 157 focused tests pass.
- Actual one-scope stop/resume preserved nine completed files; compute 51.32s,
  peak RSS 1.29 GiB, root 18.25 MB. No downloads, simulation or training.

## Evidence boundary and stopping point

Seven daily option-context formulas have synthetic complete-surface evidence;
all real values remain missing pending dated complete catalog/capture/terms.
Actual selected-contract DTE/moneyness and nine dated sector fields also remain
missing on every pilot link. API tests cover evidence clocks and 0/5 DTE bounds.
Acquisition candidates and today's expired listings are not dated selections.
Raw stock context still needs dated action reconstruction before admission.

No ETFE process remains running. Usable history remains null; no dataset/model
freeze, model-ready feature schema, training verdict or deployment is implied.

## Next work

1. **ETFE-2.joined-schema:** join verified components in the 221-value/221-mask
   order, apply per-variant MA overrides, and verify all original row identities,
   availability clocks, missing reasons, links and provenance. Keep unadmitted.
2. Resolve dated actions/contract/sector/surface/session/publication evidence.
   Preserve explicit absence, the three option trade-without-bar cases, and
   ambiguous equal-time order; do not repair gaps with synthetic observations.
3. Finish full phase-B/C demand and integrated ETFE-4 capture/features/execution/
   dataset/training smoke and resource/recovery checks before bulk work/freezes.

## Artifacts and constraints

Selected: `nn_meta/validation/etfe-remaining-features-20261005-r0/`.
Plan SHA256: `8fe1d85439c8458cbe86d166f6b70ec23be4f4a5baca66cd2e04b94885445145`.
SHARED, nine scopes, independent/raw-daily/resume receipts and payload index are
local. Evidence ZIP: 69 metadata/source members, hashes for 21 Parquets and nine
compressed native-position payloads. Market inputs remain 1,249 partitions /
1,955,680 rows. [State](docs/CURRENT_STATE.md#october-4-etfe-fresh-alpaca-setup),
[commands](docs/reference/ETFE_SETUP.md#remaining-feature-components),
[binding amendment](docs/specs/ETFE_FEATURE_BINDINGS_20261005.json).

Source-bound consumers are immutable: change them only in successor studies.
Preserve unrelated dirty work, including DECISIONS/EXPERIMENTS additions.
[Previous handoff](handoff-history/HANDOFF-2026-10-05-before-remaining-features.md).
