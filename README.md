# HealyLabs — options research and MLOps lab

HealyLabs develops, evaluates and operates multiple options-trading model
artifacts and specialist researchers. It is an ongoing laboratory: better data,
reproducible experiments, reliable execution and evidence of incremental value
feed the next research cycle. Individual milestones have completion gates;
there is no final model that ends the project.

The shared research path is:

**Point-in-time data → frozen strategy proposals → causal features and labels →
chronological evaluation → frozen model artifacts → continual dataset/model updates →
gated paper/operational admission → measured feedback.**

Researchers share infrastructure but retain their own inputs, state, evidence
and admission decisions. A passing implementation test, a finished model run,
a paper deployment and demonstrated trading performance are distinct results.

## Start here

- [Project instructions](AGENTS.md): working rules and document ownership.
- [Roadmap](ROADMAP.md): the whole lab, dependencies and completed milestones.
- [Current-phase checklist](TODO.md): work selected now.
- [Session handoff](HANDOFF.md): where to resume.
- [Current state and artifact index](docs/CURRENT_STATE.md): exact runtime and
  data locations, with dated observations.
- [Documentation](DOCUMENTATION.md): environment, conventions, traps and runbooks.
- [Maturity scorecard](GOALS.md): assessments supported by recorded evidence.

## Research specifications

- [ETFE — Exchange Traded Funds Expert](docs/specs/ETFE.md): SPY/QQQ/VOO
  independent expert using V7 strategies and timing with 1/5/15-minute signals
  and Alpaca options data. [Setup and verification](docs/reference/ETFE_SETUP.md).
- [V7 research](docs/specs/MULTITIMEFRAME_RESEARCH.md) and
  [V7 archive/restore guide](docs/reference/V7_COLD_ARCHIVE_README.md): predecessor
  contracts and reproducible restoration.

## Components

| Component | Responsibility |
| --- | --- |
| `v3/`, `options/`, data capture tooling | Historical market data, option evidence and execution inputs |
| `signals/`, `indicators/`, `scanner/`, `portfolio/` | Strategy proposals, indicator research and vectorbt equity sweeps |
| `nn_meta/`, `nn_options_signal/` | Feature/dataset construction, model training and chronological evaluation |
| `nn_meta/live/`, `integrations/alpaca_paper/` | Expert operation, paper execution, broker reconciliation and risk checks |
| `incubator/` | Continual research data, model updates, evaluation and immutable candidate freezes |
| `fa/` | Social/news/filing/fundamental collection, discovery and contextual research |
| `scripts/`, `deploy/`, `tests/` | Reproducible operations, scheduling, recovery and verification |

Future specialists, combinations and sizing research follow the dependencies
in the roadmap. Their existence does not make them prerequisites for every
current experiment. Negative results and rejected candidates remain useful
laboratory evidence.

## Evidence and history

[Decisions](docs/DECISIONS.md) retain why choices were made;
[experiments](docs/EXPERIMENTS.md) retain evaluated verdicts.
[Specifications](docs/specs/) describe technical contracts and
[dated reviews](docs/reviews/) explain supporting evidence.
The [documentation snapshot](handoff-history/docs-2026-09-27-before-consolidation/ARCHIVE.md)
preserves the previous onboarding text, including historical layer-1 examples.
Historical command examples require checking against the current environment
and selected task before use.
