# HealyLabs engineering goals — year-end 2026

Established September 10, 2026. **Target: reach 7/10 or higher in every
assessment area and overall by December 31, 2026.** Scores should follow
measured results and demonstrated reliability, not feature count or deadlines.

Continue the current [ROADMAP](ROADMAP.md) and [TODO](TODO.md): their corrected
research, operational readiness, and execution work move us toward this goal.
This document supplies the long-term scorecard; it does not replace their
priorities, bypass promotion gates, or change the active v6 campaign.

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

## Notes to carry forward

Strengths include frozen inputs, provenance checks, point-in-time controls,
purged temporal validation, baseline comparisons, persistent live state,
retries, and useful regression tests. Newly deployed Taken tracking, exit
watching, and broker fee estimates need operational history to establish their
reliability; implementation and passing tests are only the starting evidence.

The central weakness is the gap between intended and demonstrated behavior.
Recent work clarified exit semantics, connected option quotes to alerts,
added actual taken-position tracking, and distinguished open simulator marks
from real exits. Earlier audits found material correctness issues. Repairs
must be followed by rebuilt artifacts and fresh evaluation; old performance
claims do not become valid simply because the code was fixed. See the
[audit remediation record](docs/reviews/2026-09-05-remediation.md).

The highest-value improvements identified in the assessment are:

1. Complete corrected v6 evaluation and state the boundaries of proposal
   selection, training folds, and holdouts.
2. Reconcile tracked positions, actual fills, fees, and exits against brokerage
   records, without substituting quotes or simulated fills for actual fills.
3. Demonstrate sustained operation and recovery from realistic failures.
4. Consolidate research and production contracts so fewer assumptions live
   only in scripts, branches, or handoffs.
5. Gather sufficient forward evidence for calibration and net performance
   across market conditions.

## First checkpoint — after one week running v6

**Reassess after v6 has actually been running for a week and more existing
TODOs have been completed.** The clock starts with the operational v6 run,
not the beginning of its freeze/build or the date this document was written.
Operational start is **September 14, 2026**, in experimental paper-alert mode,
with current quotes and no broker orders. First review is due on or after
**September 21**, once more current TODOs are complete. See the
[activation review](docs/reviews/2026-09-14-v6-forward-activation.md).

At that checkpoint:

- Update each score with linked test, incident, deployment, and evaluation
  evidence; identify what remains unknown.
- Review feed freshness, alert delivery, taken-position/exit behavior,
  recoveries, and manual interventions during the week.
- Compare tracked positions and fee estimates with available broker records.
- Review corrected v6 results and forward sample size. Treat the first week
  as an operational checkpoint, not proof of durable profitability.
- Map remaining gaps to the current TODOs and agree on the next priorities.

Continue the existing plan until this review; do not start a separate broad
rewrite solely to improve these ratings. Define measurable acceptance checks
for remaining gaps at the checkpoint, then reassess at major milestones and
at the December 31 year-end review.

## Review log

| Review | Status | Evidence / next action |
|---|---|---|
| September 10 baseline | Recorded | Scores and rationale above; main and isolated production branches represent different stages of the system. |
| First week running v6 | Started September 14, experimental paper; review on/after September 21 | Preserve incident/delivery/portfolio evidence, complete more TODOs, then reassess. Initial deployment is not a score increase. |
| December 31, 2026 | Target | ≥7 in every area and overall, supported by evidence; record any shortfalls honestly. |
