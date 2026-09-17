# Handoff — option-risk repair deployed; V7 build next

Updated September 17, 2026. Main; no subagents. Goal active and incomplete.
No training launched. No downloads or build jobs live. Preserve unrelated dirty
V6 work. Main code and isolated runtime branch have separate commits.

## Latest user execution rules — now implemented

Always `(bid+ask)/2` for simulated option fills and marks, with existing 0.15%
per-side costs separate. Stop on option midpoint loss from the current purchased
leg entry midpoint: V6 7.5%, V7 12.5%. No generic 5% underlying loss stop for
held positions. Actual strategy sell signals remain, with frozen conflict rules.
ITM options still open on expiration day close 15 minutes before the dated option
class regular close. User confirmed the timing; do not ask again.

A valid stop/ITM trigger quote also supplies the paper sale midpoint. No second
quote request or broker fill proof. Missing/invalid quotes are explicit gaps,
not synthetic prices; next observations may exit beyond the threshold. V7 keeps
actual quote timestamp separate from execution/observation time. Costs do not
trigger the stop. Supplied midpoint/last cannot override bid/ask average.
Existing OTM rolls and unresolved physical-expiry fallback remain in scope.

Review: docs/reviews/2026-09-16-option-premium-risk.md.

## V6 deployed and verified

Runtime `/home/healy/Coding/HealysV6` is at
`d252c5190c3ca261136966ffe43432b160adfc84`, pushed isolated branch
`ops/v6-option-risk-20260916`. Candidate `/tmp/healys-v6-option-risk-20260916`
contains an untracked venv symlink; do not commit it. Main V6 source/tests are
mostly untracked preexisting work; never blanket-stage or revert them.

Deployment via Git pull stopped the forward timer, waited for any active pass,
held `.forward.lock`, required zero open positions, backed up SQLite/activation,
verified all source/evidence hashes, installed the guarded amendment and risk
units, then resumed the forward timer. All 13 closed records and full logical
ledger stayed identical; realized equity 0.6867286044611687. No reset or broker
orders. New risk service returned success/0; risk timer active (every minute at
:10 within regular sessions); existing forward/relay timers remain.

Activation SHA `d7ce5e3ebbcc58ddb894564b113cc35c210d0d35f4558123944f8cacf8c02f34`.
Evidence `nn_meta/validation/v6-option-risk-20260916` retains copied/live ledger
snapshots, exact audit/deployment scripts, source comparison, test logs/XML,
review and actual activation, unit files/verification and command/status logs.
Final follow-up evidence is under `roll-guard/`: expiry-roll decisions also bind
to the checked leg, preventing a stale OTM classification from rolling its
concurrent replacement. Original stop/pricing deployment was d415733; follow-up
d252c51 changed only the two guarded callers plus one regression. Both timers
were paused, both locks held, ledger backed up/preserved, and risk service passed.
Candidate full suite: 1,609 tests +18 subtests,16 warnings, 70.24s. Service test was
with an empty book; no live stopped-position outcome has yet been observed.

`monitor_option_position` uses a transactional expected-leg check so a quote
from before a concurrent roll cannot close the new contract. SQLite prevents
repeat sales, and alert-spool exports have a shared lock. Minute worker avoids
heavy feature/model recomputation. Alpaca SIP stock midpoint is used only for
expiry ITM classification. Held strategy signal conflicts were compared against
all 16 signal combinations in vectorbt for both directions.

Frozen V6 entry calculations remain unchanged: the original virtual simulator
still computes its frozen entry features; actual held exits use strategy signals
plus premium-risk checks. AST comparison proves unchanged entry calculation code
excluding only held-exit logic and a descriptive context field. Do not globally
disable its frozen simulator stop, which would silently change model inputs.

## V7 active scope and current evidence

Current execution-aware manifest:
`docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json`.
Policy `docs/specs/V7_OPTION_RISK_20260916.json` binds arithmetic pricing, 12.5%
premium stop, 15-minute ITM expiry and original quote/execution clock separation.
`scripts/v7_readiness.py` defaults to this manifest. Raw-only producers retain
the original `V7_ACTIVE_INPUTS_20220315.json` default: its bytes and producer
scripts are bound by existing stock/history/action receipts. Both manifests have
identical non-execution data scope; readiness verifies that against the retained
predecessor hash. Do not mutate/relabel the predecessor or rebuild raw stock data
merely because an execution rule changed. Rebuild affected proposals/paths/labels.

Current `nn_meta/validation/v7-readiness-20260916-option-risk.json`: three
input/membership/coverage checks pass; all eight substantive stage gates remain
missing. Assembly now requires full-universe midpoint/option-stop/ITM-expiry
proof too. No full readiness, resource/no-swap or training claim.

Main final bound-state suite: 1,957 tests +18 subtests, 18 warnings, 102.97s.
Logs/XML copied into the evidence directory as main-bound-tests.log/xml.
All process handles in this turn completed; no test/build/download job remains.

Real current AAPL input consumer verified 15,600 raw minutes, 40 routed sessions,
18 compiled actions and 33,877 parent input bindings, without downloads:
source `nn_meta/data_v7/start-20220315`, history
`nn_meta/validation/v7-security-history-20260916`, actions
`nn_meta/validation/v7-compiled-cash-actions-20260916`, security BBG000B9XRY4,
March15–May10,2022. Producer-default edits initially invalidated the captured
stock builder hash; restored those unchanged raw defaults and the load passed.

## Next: compact proposals, PIT filtering and full feature/label integration

No broad reference/news/issuer acquisition.250 GB is a ceiling, never a target.
Use captured inputs to finish actual build consumers and demand. Prior successful
all-variant feature/proposal milestone was main 66b2078, review
`docs/reviews/2026-09-16-v7-proposal-build.md`. Stores compute each action epoch
once, pack four full-variant boolean signal channels, checkpoint bounded simulator
batches, and resume with source/runtime/input/catalog/content verification.

Historical AAPL four-timeframe output
`nn_meta/validation/v7-proposal-build-20260916r2`: 11,268 variants, 757,465
proposals, 887,697,704 bytes. Resume preserved all 736 receipts. Those counts use
the superseded generic stock-stop proposal policy; do not relabel/reuse as new
training labels. Verification `v7-proposal-build-verification-20260916` retains
receipt 5aabbe6a7c23f43dc3f0315e3366562f74750a015562252ede44674192c916ff.
JSONL is too verbose to scale; next convert batch proposal output to typed compact
storage with lossless factorization and bounded reads, test exact reconstruction
and resume, then run the current-policy real four-timeframe integration.

`nn_meta/v7/proposal_store.py::build_proposals` still writes JSONL and repeats
variant parameters/timestamps/static fields. `tests/test_v7_proposal_store.py`
contains exact simulator/routing/resume parity checks. Preserve proposal IDs,
entry/exit clocks, censored state, bars-since-signal, dated stock aliases and all
variants including zero-signal variants. Apply PIT entry eligibility, join all
222 daily/sector/technical/TV/tick columns, derive selected-contract quote demand,
replay new risk/physical labels and shared portfolios, and wire bounded folds to
the full predeclared training runner. Finish lifecycle/action/physical exceptions
using retained evidence before targeted missing-input capture. Full-history
resource/recovery/V6-coexistence gates remain required.

## Fixed scope and preserved data

March15,2022–September14,2026 inclusive; cold start March15, no March8–14 active
price inputs. All 20 families,2,817 variants×four 1/5/15/30m timeframes;222 columns,
13 TV scopes,10 tick features. Actual 1–9 DTE purchases, targets 1/2/4/5/7; five shared
slots, 10% equity premium and one symbol across timeframes. Max four outer workers,
one inner thread,100 GiB disk reserve and 250 GB acquisition ceiling. Alpaca-only
stock prices/quotes; Massive options. No OTC: entire BBBY/FRC/REV/SI excluded,
without replacement or reranking; explicit ex-post study restriction.

Chronological folds 2024H2, 2025H1/H2; final Jan 1–Sep 14, 2026, 10-session embargo
through full settlement horizon. Funded physical delivery/observed Alpaca stock
liquidation remains unresolved where funding, deliverables or dated references
are missing; no free financing or invented intrinsic-value sale.

Daily raw `v7-stock-daily-20260916-midpoint` and surfaces
`v7-surfaces-20260916-midpoint` retain full 339,640 eligible rows; security history
591 IDs × 1,129 sessions = 667,239 rows, 339,454/339,640 eligible identity matches,
186 unresolved. Compiled cash actions 19 reviewed events (18 AAPL + DVN); 10,340 provider
records unresolved. Preserve identity alias FISV/FI June 7, 2023 and original
retained evidence; do not restart open-ended collection. Detailed prior data,
artifacts and remaining exception context are in the archived handoff below.

Archived predecessor: handoff-history/HANDOFF-2026-09-16-before-option-premium-risk.md.

## Latest stock-coverage question

User asked whether all necessary minute bars are present, then acknowledged the
remaining work. Answered: broad collection is in place, not yet fully verified.
339,581/339,640 required ticker/session combinations contain minute bars;59zero
sessions have recorded merger/successor/halt explanations.186identity matches
remain unresolved and can include existing prices. These are session-presence
counts, not proof of every expected minute. Both source receipts were reverified;
exact per-ticker counts are in
`nn_meta/validation/v7-stock-coverage-answer-20260916.json`. Do not say all bars
are complete or imply training is ready from these counts.
