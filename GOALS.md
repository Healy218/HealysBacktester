# HealyLabs maturity scorecard

This file owns dated assessments, their evidence and remaining uncertainty.
[ROADMAP](ROADMAP.md) owns priorities; [TODO](TODO.md) owns selected work;
[CURRENT_STATE](docs/CURRENT_STATE.md) owns runtime/artifact pointers.
The lab is open-ended. The December 31, 2026 target is a checkpoint, not the
end of the lab or a guaranteed trading outcome.

**Established September 10: aim for at least 7/10 in every assessment area.**
Scores follow demonstrated behavior and evidence, not feature counts, total
tests, elapsed time or deadlines. Documentation consolidation changes no score.

## Starting assessment

The September 10 assessment was approximately **6/10 overall**: a serious
independent quant research platform with early production trading support,
substantially beyond a basic college project, with significant distance to
institutional maturity. “Jane Street grade” is shorthand for institutional
standards; this is not a comparison against access to its private systems.
These are subjective engineering assessments, not certified benchmarks.

| Area | September 10 baseline | Year-end target | Evidence needed for 7 or higher |
|---|---|---|---|
| Research infrastructure | 7/10 | Maintain or improve ≥7 | Completed corrected v6 pipeline; reproducible data/artifact provenance; temporal validation and baseline comparisons; explicit limits on globally selected proposals versus fold-local optimization. |
| Code architecture | 5–6/10 | ≥7 | Clear research/live interfaces and configuration ownership; fewer duplicated generation-specific paths; consistent state and schema contracts; documented, tested migrations. |
| Testing | 7/10 | Maintain or improve ≥7 | Meaningful regression, integration, real-data replay, and failure/recovery coverage; checks for causality, accounting, and offline/live parity. Passing counts alone do not establish correctness. |
| Live operations | 5/10 | ≥7 | Sustained recorded operation; measured freshness and alert delivery; tested disconnect, restart, missing-data, and recovery behavior; repeatable deployments and rollback; fewer manual interventions. |
| Execution and risk controls | 3–4/10 | ≥7 | Reconcile positions, actual fills, fees, and exits with brokerage records; enforce and test portfolio exposure limits and appropriate stop/kill controls; make manual versus automated responsibilities explicit. |
| Evidence of durable trading edge | Unproven | Aim for ≥7 evidence strength | Corrected out-of-sample results plus sufficient forward observations across conditions; assess calibration, net returns, costs, drawdown, outlier dependence, and uncertainty against baselines. |

Trading edge remains **unproven** until the evidence supports a stronger
assessment. A calendar target cannot manufacture profitability or justify
raising a score. One profitable week, sophisticated models, and a large test
suite are not sufficient evidence of a durable edge. Honest negative results
still improve research quality; they do not prove an edge.

## Assessment method

At the user-selected end-of-week review, major operational/research milestones,
and the year-end checkpoint:

- Record the assessment date, observation window and exact model/account/runtime.
- Compare with the dated baseline and link evaluated results, deployment,
  incident and recovery evidence. Distinguish implementation from demonstration.
- Review freshness, delivery, reconciliation, actual broker fills, failure
  handling, interventions and reproducibility within their observed scope.
- Evaluate prediction/performance evidence with baseline comparisons, costs,
  calibration, drawdown, outlier dependence and uncertainty. Do not reinterpret
  historical simulator returns as newly observed broker outcomes.
- Record revised scores only when supported, and preserve prior assessments.
  Put selected follow-up work in the main TODO under its roadmap milestone.

The historical first-week V6 checkpoint began with the September 14 paper-alert
runtime. The September 27 Alpaca activation starts a distinct broker-execution
observation period. Retain the earlier observations without treating them as a
week of Alpaca fills. The original first-week notes remain in the archive below.

## Assessment and evidence log

| Date / checkpoint | Classification | Recorded conclusion |
| --- | --- | --- |
| September 10 | Baseline assessment | Scores above; approximately 6/10 overall, trading edge unproven |
| September 14–22 | Historical operational observations | Experimental V6 simulator/paper alerts and dashboard repairs; no automatic numerical reassessment |
| September 25 | Research evidence milestone | [V7-2 completion](docs/reviews/2026-09-25-v7-2-complete-and-v7-3-start.md) strengthens provenance/causal-validation evidence; numerical scores unchanged |
| September 27 | Operational evidence milestone | [Alpaca startup](docs/reviews/2026-09-27-v6-alpaca-activation.md) verified; sustained operation and actual fills still need observation; numerical scores unchanged |
| Next user-selected end-of-week review | Pending assessment | Use the actual evidence available at review time; do not promise a higher score |
| December 31, 2026 | Target checkpoint | Assess each area honestly against its target and evidence requirements |

[Archived detailed assessment notes](handoff-history/docs-2026-09-27-before-consolidation/GOALS.md)
retain the original rationale and historical continuation wording. They do not
create a separate current work queue.
