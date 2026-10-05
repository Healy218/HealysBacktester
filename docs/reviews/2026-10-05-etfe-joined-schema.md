# ETFE joined diagnostic schema

Completed **ETFE-2.joined-schema** for the bounded January 18–19 pilot:
**458,133 original events, 221 values plus 221 masks, nine ticker/timeframe
scopes**. The registered order, variant MA overrides, missing reasons, modeled
availability and provenance now form one verified diagnostic artifact.
[Contract](../specs/ETFE_JOINED_SCHEMA_20261005.md),
[machine receipt](2026-10-05-etfe-joined-schema.json).

Selected root: `nn_meta/validation/etfe-joined-20261005-r0/`.
Plan SHA256: `2395d11076c481cc697cd6848f3682cd18a8866bbbcd9b79b18f37525e08213c`.
Schema SHA256: `5bfd1b73c85f3e43ce9f76190c12eb0a34e070acb394dbb8513100ba97f42d61`.
All inputs come from the four verified fresh ETFE component studies; their
consumers, frozen artifacts and original registry remain unchanged.

## Output and missingness

Each of 96 chunks commits four separate Parquets: canonical matrix, reasons,
availability and original rows/provenance. All 384 payloads have SHA256 entries.
The matrix contains no clocks, IDs, reasons, outcomes or other metadata columns.
No values were filled, scaled or cast into a model-ready array. Target replicas
retain distinct logical IDs and the original event payload hash.

| Value-cell census | Count |
| --- | ---: |
| Total, excluding masks | 101,247,393 |
| Finite diagnostics | 59,917,288 |
| Explicitly missing | 41,330,105 |

Each row has 75–100 missing fields. This combines structural absence, such as
parameters belonging to other strategy families, with insufficient history and
unresolved market inputs. A complete schema does not mean every field should be
finite. Masks and reasons retain those distinctions, without removing any row.

The eleven dated contract/sector fields and seven option-context fields remain
missing on real data. Selected contract and actual DTE remain unknown; target DTE
and acquisition candidate cannot substitute for historical selection. The approved
0–5 DTE policy, including qualifying 0DTE, is unchanged.

Finite availability clocks are no later than their decision. They preserve the
predecessors' modeled timing, including next-open daily context and a conservative
option-window-end plus one second. They do not establish provider publication
timing or point-in-time availability of final-vintage historical observations.

## Checks and resources

**173 focused ETFE tests pass**, including 16 join tests. The independent auditor
uses natural signal/time/day/window keys instead of the producer's ordinal joins.
It compared every value, mask, reason and clock exactly, checked all original
event fields, and reconciled logical IDs, source links, hashes and missing counts.
It reuses previously audited numerical components; it does not independently
reimplement indicators or establish native Pine parity.

Every actual chunk also passed a second join with changed batch boundaries.
An actual one-chunk stop exited deliberately incomplete, then resume preserved
the committed receipt and four payloads byte-for-byte and wrote the other
95 chunks. Unit tests reject source identity/clock/schema/mask mismatches and
tampered committed payloads.

Join compute across both invocations: **35.15 seconds**; peak RSS
**1,071,894,528 bytes (1.00 GiB)**; completed local root **193,144,184 bytes**.
These measurements exclude the independent audit and do not forecast integrated
execution, full-history building or model fitting. The 2 GiB/30-minute study
limits and disk/RAM reserves were respected.

The [evidence ZIP](2026-10-05-etfe-joined-schema-evidence.zip) contains 111
metadata/source/audit members and the hash index for 384 Parquets. Every ZIP
member was reconciled to its local source; payloads remain in the selected root.
ZIP SHA256: `edb1c16ed9359e2f613e5b87138869645cd087d63713ae1ce6a75562aa8a3aca`.

## Admission boundary and next work

Every model-feature and entry-admission flag remains false. Usable history is
still null. No new downloads, execution simulation, labels, training, deployment
or economic evaluation occurred. This closes the bounded joined-schema task,
not full ETFE-2 feature admission or the integrated ETFE-4 pilot.

Next resolve dated action/contract/sector/surface/session/publication evidence,
then complete full phase-B/C demand and integrated capture/features/execution/
dataset/training smoke and recovery checks before bulk work and freezes.
