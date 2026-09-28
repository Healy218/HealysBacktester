# Documentation — environment, conventions, traps and operations

This file owns durable operating knowledge. Use [AGENTS](AGENTS.md) for project
instructions, [ROADMAP](ROADMAP.md) for direction, [TODO](TODO.md) for selected
work and [CURRENT_STATE](docs/CURRENT_STATE.md) for exact current artifacts,
runtimes and dated observations. Do not add running-job status blocks here.

## Environment

- Work on `main` in the shared research checkout. Research, the frozen V6
  checkout, FA automation and the Hetzner deployment are separate surfaces;
  their selected paths and purposes are in CURRENT_STATE.
- Use `./venv/bin/python` explicitly. The project environment is Python 3.12;
  the system Python is not the project interpreter. Install runtime packages
  from the project requirements; pytest is installed separately.
- The full regression command is `./venv/bin/python -m pytest tests/ -q`.
  Record actual results in the relevant dated review, not a permanent test-count
  floor in instructions. Documentation-only edits need document checks.
- Root `.env` is untracked private configuration. Do not print secrets. Dedicated
  Alpaca paper credentials are separate from other data/operational credentials.
- `NN_META_POOL` selects both the pool and artifact namespace in `nn_meta/config.py`.
  Campaign/release manifests can additionally bind input roots and hashes.
  Use the selected launcher's environment; never infer a pool from directory age.
- The home box is the replacement Ryzen machine with 32 GB RAM; the old faulty
  i5 hardware is retired. Do not revive its old cloud-only or RAM restrictions.
  Current job limits and authorized storage policy are owned by CURRENT_STATE.
- Rootless gcloud is installed under `~/google-cloud-sdk`; shell configuration
  supplies PATH. Cloud work still needs an explicit, measured campaign budget.

## Conventions

- Derive repo roots in scripts and use the shared autosizing helper. Measure
  memory for the workload; old worker counts and RSS observations are not new
  allocations. Do not count swap as reliable capacity for large numeric arrays.
- Publish persistent artifacts atomically, bind their provenance and keep
  completion receipts separate from partial output. A filename is not proof
  of completion. Preserve interrupted evidence and reuse valid checkpoints.
- Worktree changes, commits, deployments, launches and successful outcomes are
  distinct events. Record which actually happened.
- Keep code/model/source versions separate from observation time. Do not rename
  old artifacts or change hashes to make a newer consumer accept them.
- Keep projected/simulated prices and returns separate from broker fills and
  balances. A passed inference run is not a scored outcome or trading edge.
- Logs and health locations are launcher-specific. Inspect the selected
  launcher/installed unit and its recorded job identity before interpreting logs.
- Statistical or storage forecasts are estimates, not guarantees. State the
  workload, observation interval, units and exclusions when reporting them.

## Traps

Read the relevant entries before treating a script or cache as broken.

- **Bind watchers to submitted IDs.** Never select the newest job/image from a
  listing. Process-name matching can match the watcher itself; anchor exact
  commands and use appropriate bracket patterns. Evidence means actual receipts,
  task state and outputs, not merely a process name or an exit banner.
- **Do not assume shell syntax.** Use arrays/explicit arguments and inspect each
  command's exit result. A wrong shell or partial command execution can resemble
  provider or permission failure.
- **A missing minute may be a quiet minute.** Live aggregation uses reference
  symbols to establish stream health. Do not require a traded bar for every
  symbol in every minute or erase the existing reference-symbol distinction.
- **Calendar-aware freshness matters.** After weekends/holidays, compare with the
  expected closed session bar. Do not replace this with a wall-clock age rule.
- **Do not deadlock the stream's own loop.** alpaca-py public subscription helpers
  can block when called from inside that loop; preserve the loop-aware send path
  and stall guard. Historical incident detail is in the archived notes below.
- **Logrotate permissions are intentional.** Deployment chmod protects against
  group-writable configuration. Shell source fragments in `scripts/jobs.d/`
  need not be executable; actual launchers do need their intended mode.
- **Job marker absence means never launched here.** Do not turn a missing local
  marker into a request to launch every archived job after a fresh checkout.
- **Compare dataset builds by signal identity.** Use `nn_meta.dataset_diff` and
  the declared signal keys; sorting duplicate rows or joining on changed option
  contracts can invent differences or hide the change being measured.
- **Choose representative verification inputs.** A symbol unaffected by a cache
  defect cannot validate its repair. Old pilot sizes/timings do not describe
  the full present workload.
- **Historical year-end holes were a real dated finding.** Earlier underlying
  requests used an exclusive midnight end. Check the selected current input's
  coverage receipt before assuming it still has that hole or recapturing data.
- **Capture time is not publication time.** Historical FA rankings cannot use
  content first collected after their cutoff. Monthly cohorts, raw collection
  days and eligible forward-label dates are different measurements.
- **Partial provider failure semantics can be deliberate.** Reddit listing
  failures are aggregated by the collector; do not treat a single handled
  401/403 as global success or global failure without the collector receipt.
- **Provider entitlements and local completeness differ.** A listed object or
  successful sample query is not proof of complete local history. Historical
  entitlement probes are dated evidence, not permanent product specifications.
- **Frozen runtime recovery is explicit.** Kernel/platform changes can trip
  source-bound manifests. Use an approved, evidenced recovery consumer; never
  relabel the original runtime or globally disable its checks.
- **MRHA locators are meaningful.** A verified archived loose tree is not missing
  data. For active packed captures, keep local logical directories/receipts and
  payload-file symlinks; whole-directory symlinks change discovery behavior.
  Verify the drive identity and preserve external payloads used by local receipts.
- **Clean page cache is not the same as working buffers.** Preserve the deployed
  V7 memory-pressure calculation; do not restore a cache-blind guard because
  total cgroup memory alone appears high. Current policy is in the state index.
- **Quota accounting includes pending and external data.** An old local-only
  reinitializer can miss external partials or overwrite the authorized limit.
  Use the selected campaign's accounting; do not infer limits from old reviews.
- **Obsolete checker fields do not reopen completed work.** Resolve the checker
  against accepted contracts and receipts. Distinguish intermediate readiness
  flags from the completed deliverable they do not measure.

## Research and artifact procedures

| Topic | Durable reference |
| --- | --- |
| V7 scope, availability and accepted amendments | [Specification](docs/specs/MULTITIMEFRAME_RESEARCH.md); selected inputs in CURRENT_STATE |
| TradingView author/version/licensing and causal parity | [Expansion specification](docs/specs/TRADINGVIEW_EXPANSION.md), [historical/live contract](docs/specs/REALTIME_SPEC.md) |
| September audit migration boundaries | [Remediation](docs/reviews/2026-09-05-remediation.md); preserve original historical verdicts |
| Kernel-change demand recovery | [Bounded recovery evidence](docs/reviews/2026-09-25-v7-3-crash-recovery.md) |
| Packed option capture and exact reader coverage | [Packing review](docs/reviews/2026-09-27-v7-joined-packed-capture.md); historical allocation figures there are superseded by CURRENT_STATE |
| Exact reference blackouts and retained outcomes | [Blackout review](docs/reviews/2026-09-27-v7-contract-reference-blackouts.md) |
| Dated hours and execution frontier | [Hours/path review](docs/reviews/2026-09-27-v7-dated-hours-and-execution-paths.md) |
| External archive recovery | [Storage migration](docs/reviews/2026-09-26-authorized-storage-reclamation.md); use the verified external RESTORE instructions and hashes |
| FA contracts and evaluation distinctions | [FA context](docs/reference/FA_CONTEXT.md) |

Technical requirements stay attached to their declared artifact scope. Later
amendments must name the contract they change; a historical narrative must not
silently override a current freeze. Keep labels separate from features, purge
by information/label availability and preserve predeclared comparisons.

## Operations and recovery

- **Server deployment:** use the deploy-key `git pull` workflow, never `scp`.
  Verify the specific checkout/revision and installed units. A main-branch push
  does not prove that the server has deployed it.
- **V6 paper:** use the [activation runbook](docs/reviews/2026-09-27-v6-alpaca-activation.md)
  for service controls and recovery. A provider price-vintage error requires a
  new validated input snapshot; a same-date refresh may simply reuse the existing
  snapshot. Preserve the vintage guard and original artifacts. See the
  [September 28 repair](docs/reviews/2026-09-28-v6-paper-readiness.md).
  Do not rerun activation, reset its timestamp,
  erase the broker journal or import old simulator positions. Actual subsequent
  state lives under the pointers in CURRENT_STATE.
- **Incubator:** the selected V6-only purpose is continual research/training,
  independent of paper-trade selection. Append immutable candidate features and
  matured simulated labels; an end-of-window mark is not a completed label.
  Prediction replay is historical machinery, not a model update. New freezes
  preserve their parents; research acceptance does not deploy a model. See the
  [current contract](docs/specs/AI_INCUBATOR.md).
- **FA:** the automation checkout owns deployed collection/evaluation receipts.
  Local skipped collectors may be covered by server/archive transfer; check the
  complete configured route. Daily capture does not imply a new monthly cohort.
- **Long-running work:** distinguish persistent installed units from transient
  services and the optional reboot dispatcher. Inspect actual installation
  before claiming restart coverage. Keep home auto-suspend disabled while jobs
  require continuous operation; do not change settings from historical advice.
- **Cloud:** bind exact image/job IDs; account for actual parallelism, billing,
  memory packing, retries and scratch I/O. Capacity exhaustion is different
  from quota exhaustion. Prior instance prices and throughput are dated evidence.
- **Monitors/dashboards:** show artifact/account identity, observation time and
  actual schema-valid evidence. An old simulator projection must not appear as
  a new paper account's fill/P&L record.

## Detailed historical notes

The [full pre-consolidation notes](handoff-history/docs-2026-09-27-before-consolidation/DOCUMENTATION.md)
retain all earlier implementation details, billing lessons, source/identity
cases, legacy bundle layouts and old deployment recipes. Their dates and
original text are preserved. Consult them for a specific historical mechanism;
verify applicability against current pointers/contracts before executing any
command. They are not an additional current task list or resource policy.
