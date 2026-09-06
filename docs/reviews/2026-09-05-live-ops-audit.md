# Live, discovery, and operations adversarial audit — 2026-09-05

> Remediated in the review checkout. See [the repair report](2026-09-05-remediation.md) for current dispositions and validation. Findings below refer to the original audited commit.

Reviewed snapshot: `f98ed265db3ce3faf4ba7abf8e6604671e3a1c90`. Read-only review; no production commands, remote calls, notifications, or source changes. Synthetic reproductions used the existing interpreter with bytecode disabled and temporary files. The coordinating reviewer runs the full test suite separately.

## Findings

### LO-01 — P1: the cloud spend guard abandons live fleets on API errors

`scripts/cloud_budget_guard.sh:63-74` converts every failed `gcloud batch jobs describe` into `GONE`, then counts that as terminal. A temporary network/authentication/control-plane failure affecting all watched jobs immediately exits the guard successfully and reports that fleets finished; the running VMs can continue billing. Separately, lines 83-87 ignore failed cancellation commands and announce `CANCELLED` unconditionally before exiting. Neither an observation failure nor a cancellation request proves billing stopped. Preserve unknown jobs as active, retry/alert, and verify terminal state after cancellation. Static control-flow proof; no cloud calls made.

### LO-02 — P1: cloud checkpoint publication can permanently omit mark streams

`deploy/gcp/task.sh:419-420` uploads `meta_rows` before `meta_marks`, while lines 412-414 skip a symbol whenever its row file exists. Preemption or a failed marks upload between these commands leaves a committed-looking row with no marks; all retries then skip the symbol. This contradicts the local worker's comment claiming both paths commit marks before rows. Publish each symbol's marks first, rows last, and validate the pair before skipping. This is a crash-window finding, not a claim that the currently committed dataset has this defect.

### LO-03 — P1: local v5 publishing failures are reported as successful builds

`scripts/run_build_v5_local.sh:49-52` does not check either upload's exit code; `build_one` returns the final successful `echo`. A failed marks upload can therefore be followed by a successful row upload, triggering LO-02's permanent skip condition. A failed row upload still prints `published`. At lines 57-63, the outer script also ignores a failed xargs pipeline and prints `LOCAL-BUILD-DONE` with exit 0 (`set -uo pipefail`, without error propagation). Even the initial spec download at line 31 can fail and leave an old spec in use. Require successful inputs/uploads and aggregate worker failures before declaring completion.

### LO-04 — P1: FA historical rankings consume information after their declared cutoff

`fa/ranker.py:61,68,86` uses Reddit creation/news publication timestamps instead of archived capture `ts_utc`, and line 98 passes the entire archive to scoring before cutoff filtering. Content first collected after an as-of date can therefore enter that historical ranking. `fa/scores.py:58-78` additionally maps each full day's count to midnight, making later same-day observations visible at the start of that day. **Committed evidence:** `fa/artifacts/top10_2026-08.json` declares `2026-08-24T00:00:00`, but B's evidence contains `stocktwits:2026-08-24 18:05:12.319329+00:00:B`. Synthetic August-created mentions all captured September 5 also produced an August 31 ranking. Filter capture times before aggregation and make the daily cutoff convention explicit; published time and first-observed time are different fields.

### LO-05 — P2: scanner dry runs consume real alert/digest state

`nn_meta/live/v4_scan.py:437-439,454-461` changes only the notifier for `--dry-run`; it uses the normal state directory. `ConsoleNotifier.send` returns true (`notifier.py:31-34`), so scan/digest paths acknowledge pending production outbox entries as delivered, mark signals seen, open paper positions, and mark digest rows consumed. A later real invocation cannot recover the notifications printed only to the terminal. The legacy path has the same state mutation (`run_live.py:84-87`). Use isolated ephemeral state or suppress all durable mutations and outbox replay during previews.

### LO-06 — P2: legacy experts permanently lose failed notifications

`nn_meta/live/scanner.py:219-221` saves alert deduplication before returning signals; `run_live.py:92-96` then sends and ignores the boolean result. A failed Telegram/Pushover request or a crash between scan and send permanently suppresses that signal on retry and prints it as alerted. The v4/v5 outbox fix does not cover the still-deployed legacy v3/v31 path. Reuse the durable outbox and count actual delivery separately.

### LO-07 — P2: fresh means newest cached bar, not recent market data

`nn_meta/live/scanner.py:92-99,111-117` only removes forming bars and compares the proposal against the last returned timestamp. `v4_scan.py:113-118,245-247` uses the same rule. An old cached feed with a proposal on its final bar qualifies as fresh, including a previous session's signal at the next opening scan. There is no maximum age/session check. Furthermore, `scanner.py:84` excludes 16:00 ET, so a 15:45 bar is never actionable at its close; its first eligible scan can be the following session at 09:30. Fail stale feeds explicitly, and schedule a final closed-bar pass with an explicit session policy. This is distinct from the documented stale daily IV/beta inputs.

### LO-08 — P2: atomic state files still lose writes across overlapping processes

`nn_meta/live/state.py:55-67,77-92` loads whole-file snapshots and replaces the file on each mutation without a lock or reload. `v4_scan.scan_pass` and `digest_pass` share the v4 outbox, and scan invocations are cron-driven without an in-code process lock. Two overlapping processes can both enqueue/send the same key or overwrite each other's unrelated pending entries; the watchlist and ledger have the same snapshot pattern. Reproduced with two `AlertState` objects created before either write: A marks key A, B marks key B, reloading loses A. Atomic replacement prevents torn JSON, not lost updates. Lock the whole transaction/pass or use transactional storage.

### LO-09 — P2: the append-only FA archive is overwritten non-atomically

`fa/archive.py:38` rewrites the existing monthly parquet directly. An interrupted write (power loss, disk full, killed collector) can destroy all previously archived observations for that source/month; subsequent runs then fail reading it. This is particularly material for historical Reddit/news rows that cannot be reconstructed reliably. Use same-directory temporary output and atomic replacement, plus serialization if multiple writers are possible. This is a concrete unsafe-write path; no destructive crash simulation was run.

### LO-10 — P2: month boundaries bypass collector deduplication

`fa/archive.py:27-36` partitions by capture month and only deduplicates inside that partition. The same Reddit post/comment, news URL, or EDGAR filing captured January 31 and again February 1 is appended twice. The ranking loader concatenates every partition and `attention_velocity` counts rows rather than unique evidence, inflating old-day counts and changing subsequent z-scores. Reproduced: appending identical `post_id=p1` across those capture dates returns `+1` both times. Preserve first-capture identity across partitions or deduplicate globally downstream as well.

### LO-11 — P2: the forward-return tracker CLI crashes on ordinary frozen rankings

`fa/tracker.py:107` passes timezone-aware `pd.Timestamp.utcnow().normalize()` into `forward_returns`; line 62 preserves its timezone while loaded ranking dates are naive. The comparison at line 76 raises `TypeError: Cannot compare tz-naive and tz-aware timestamps` before price loading. Reproduced with a normal August 31 naive ranking date and September 5 UTC as-of date. Existing tests only pass naive as-of values. Normalize both sides to the declared UTC representation.

### LO-12 — P2: news corroboration silently drops all but the first ticker

`fa/ranker.py:82-86` turns comma-separated provider tags into `'$AAPL,MSFT,NVDA'`. The resolver recognizes cashtags, so only AAPL survives when aliases do not happen to rescue the remaining tags. Reproduced directly: `resolve('$AAPL,MSFT,NVDA', {}, valid_tickers=[...]) == ['AAPL']`. This biases source counts and excludes legitimately corroborated candidates from monthly rankings. Split ticker lists and resolve every symbol explicitly.

### LO-13 — P2: graduation borrows returns from a different ranking cohort

`fa/universe_loop.py:71-74` selects the latest return per ticker and joins it to probation-qualified rankings by ticker alone. A repeated monthly pick can therefore pass probation using a different, much younger winning cohort. Reproduced: January AAA loses 20%, August AAA gains 10%, both measured August 31; on September 1, the January cohort qualifies using August's +10% return. Key returns by `(ticker, ranking_date)` and apply probation to that same cohort.

### LO-14 — P2: trending's cashtags bypass its advertised liquidity universe

`fa/trending.py:57-60` restricts bare tickers to `BARE_OK` but accepts every explicit cashtag; `build_report` applies only the mention floor. Repeating an arbitrary `$LOL`/illiquid ticker four times gets it into daily candidates despite the module's documented liquidity filter. Intersect all resolved tickers with the supported universe before counting/ranking. This affects the daily trending report; the monthly ranker's separate valid-ticker filter is present.

### LO-15 — P2: local v6 launcher reports completion when workers fail

`scripts/run_freeze_v6_local.sh:39-40` calls `wait "${pids[@]}"` and then unconditionally echoes `LOCAL-FREEZE-DONE`; it does not enable errexit or accumulate child statuses. Bash returns only the last listed child's status for this wait invocation, and the final echo masks that status anyway. A worker crash/OOM can leave a partial shard set while the launcher exits 0. Check every child and return nonzero on any failure. No active v6 job was touched.

## Additional limitations and verified boundaries

- `watchlist.hit_stats` filters by entry date (`nn_meta/live/watchlist.py:138-141`) while outcomes resolve after up to seven days. For DTE >=7, the advertised 7-day scoreboard includes essentially only the just-matured entry-day cohort, rather than seven days of resolved outcomes. Choose a resolution-date window or explicitly label a matured entry cohort before using this to tune thresholds.
- FA `monthly_rank` averages all historical score rows at/before the cutoff (`fa/universe_loop.py:31-37`), without a monthly/trailing ranking window. This may preserve stale winners and counts old social/news appearances as corroboration. Treat as a metric-definition decision requiring clarification, not a proven implementation failure against an explicit window.
- The daily stocktwits sentiment stream archives snapshot counts, not unique message IDs; hourly overlapping message windows are summed later. This is a snapshot-weighted sentiment statistic, not a unique-message vote count. Its interpretation should be explicit.
- The intended live DD-brake/sizing deferral, paper-only alerts, stale daily surface/beta caveat, and unused fundamental overlay stub are known scope limitations, not presented as newly discovered regressions.
- Verified in source: v4/v5 state filenames/default bundle locations are separate; renamed ticker fetching is shared with legacy; v4 enqueue precedes ledger and dedupe; heartbeat persists baselines only after a successful notifier result, isolates unreadable expert logs, and handles counter resets; cloud build uses pipefail and submission checks the image manifest; StockTwits synchronization pulls before pushing. These prior fixes do not resolve the distinct findings above.
- The synthetic tests inspected cover happy-path live dedupe, v4 failed-send replay, scorer fallback, monthly source-family filtering, and basic as-of exclusion. They do not exercise the CLI timezone mismatch, capture-vs-publication cutoff, overlapping state snapshots, cross-month duplicate identity, or cloud publication failure windows.

## Coverage

Read `nn_meta/live/*.py`, `fa/*.py`, `fa/collectors/*.py`, FA alias/frozen-ranking JSON, `deploy/gcp/*` shell/container/dependency configuration, `deploy/systemd/*` units/timers, `.github/workflows/ci.yml`, `requirements.txt`, `.gitignore`, `.dockerignore`, operational launchers/watchers in `scripts/*.sh`, job descriptors and autosizing helper, and operational Python scripts (`build_spx0_underlying`, `build_universe_daily`, `extract_index_1m`, `rank_universe`, `sort_universe`, `spx0_stage0_audit`, `wf_prewarm`, `zram_reclaim_stress`). Markdown-first reading was completed by the coordinating reviewer before delegation; relevant prior audit findings were cross-checked. Legacy backtest scripts and policy/strategy research code belong to the coordinating/other reviewer scopes. Deployment semantics were reviewed statically; installed server cron/systemd/cloud resources were not inspected or changed.
