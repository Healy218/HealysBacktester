# Healy's Backtester

An options meta-labeling research pipeline and a vectorbt strategy-sweep dashboard. Mechanical strategies propose trades; neural and tree models score them; evaluation compares costed portfolio results with frozen baselines. Live components send alerts and maintain paper records; they do not place broker orders.

## Current status

The September 5 adversarial audit found causal, accounting, data-integrity and operational defects in the earlier results. See [current handoff](HANDOFF.md), [repair status](docs/reviews/2026-09-05-remediation.md), and the [original audit](docs/reviews/2026-09-05-adversarial-audit.md). Historical experiment verdicts are preserved as history and must be rerun on corrected artifacts before reuse as evidence.

The corrected feature/build contract is `2026-09-05-causal-v2`. Existing unversioned freezes, rows, marks and verified bundles are not interchangeable with it. Rebuild and validate upstream artifacts before training or promotion. This checkout does not establish the state of deployed services.

## Components

| Path | Purpose |
|---|---|
| `main.py`, `backtests/` | Dash dashboard and equity/option strategy runners |
| `signals/`, `indicators/`, `portfolio/` | Parameter grids, causal signals, vectorbt simulation |
| `scanner/` | Monitor configurations saved from dashboard results |
| `models/`, `sentiment/` | Legacy neural experiments and headline sentiment strategy |
| `nn_meta/` | Frozen proposals, option labels/marks, model evaluation and finalization |
| `nn_meta/live/` | Independent alert experts, durable outbox, paper ledger and digest |
| `nn_meta/spx0/` | Intraday SPX options research |
| `nn_options_signal/` | Separate earlier daily-options experiment |
| `v3/`, `options/data/` | Historical underlying/option data and cache providers |
| `fa/` | Archived attention/news/filing evidence, monthly discovery and forward tracking |
| `tests/` | Offline tests, including adversarial regressions |

`NN_META_POOL` selects both strategy families and artifact locations: `v2` is the default, `v3` is the legacy TV pool, `v31` is the at-scale pool used for v4 research, and `v5`/`v6` use the PIT membership archive. v6 adds families and weekly DTE variants; it shares v5's raw cache and window, with separate generated artifacts. Reuse requires matching current provenance and complete rows/marks.

## Local use

Use Python 3.12 in a project virtual environment with `requirements.txt`; install pytest separately for tests. Credentials belong in `.env`, never source control. Equity loaders use Alpaca and local caches; no Yahoo fallback is implemented. Read [data sources](data/DATA_SOURCES.md) for boundaries.

```bash
./venv/bin/python main.py
./venv/bin/python -m pytest tests/ -q
```

The dashboard runs on loopback port 8050. Configure experiments in `config/settings.py`; options pipeline configuration is in `nn_meta/config.py`. Use each module's `--help` before running a build: historical cache availability, chosen pool and causal contract matter.

## Documentation

Start with [CLAUDE.md](CLAUDE.md) for the documentation map. [TODO.md](TODO.md) contains current work, [ROADMAP.md](ROADMAP.md) separates active goals from historical milestones, and [DOCUMENTATION.md](DOCUMENTATION.md) records durable conventions and operational traps. Specs are under `docs/specs/`; dated decisions and experiment results remain in `docs/DECISIONS.md` and `docs/EXPERIMENTS.md`.
