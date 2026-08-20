# HANDOFF — state for the next session

Written 2026-08-20 ~01:15 CDT (06:15 UTC). Protocol: `CLAUDE.md`.
Previous handoff (stale-dataset evidence, panic forensics, pilot verification):
`handoff-history/HANDOFF-2026-08-19-stale-dataset-and-panic-loop.md` — read it
for the *why* behind the rebuild; this file is the *where we are*.

User went to bed 2026-08-20 ~01:15 CDT leaving the box running, with Claude
Remote Control deliberately switched ON to test whether it correlates with the
crashes. It almost certainly does not — see "the box" below.

## THE REBUILD IS RUNNING ON-DEMAND — `marks-build-d64ca9b-010138`

Live-verified at 01:10 CDT: state RUNNING, 5 tasks RUNNING / 11 PENDING, task
logs fresh, **57/118 shards** in `out/meta_rows/` and `out/meta_marks/`
(identical symbol sets). 27 of those 57 are the 08-17 originals that were
never stale; 30 are rebuilt.

| Setting | Value | Why |
|---|---|---|
| `provisioningModel` | **STANDARD** (was SPOT) | every failure in the previous job was exit 50001, Spot preemption |
| `taskCount`/`parallelism` | **16 / 8** | halves each slice (~7 symbols, not ~15) to stop exit 50005; 8 is the quota ceiling |
| `IMAGE_TAG` | pinned **`d64ca9b`** | HEAD is 5 commits ahead; an unpinned submit would bake a different code version into half the shards |
| `maxRunDuration` | 43200s (12h) | was 6h, and attempts were timing out |
| `maxRetryCount` | 3 | unchanged |

**Predecessor `marks-build-d64ca9b-161349` was CANCELLED**, not deleted, so its
failure record survives in `jobs list`. It could never have finished: tasks 0,
4 and 7 had exhausted all four attempts. Two distinct failure modes were eating
attempts — Spot preemption (**exit 50001**) *and* the 6h runtime cap (**exit
50005**, hit by tasks 1, 3, 4, 5, 6). Moving to on-demand fixes only the first;
the 16-way split is what addresses the second. Cancelling cost only in-flight
symbols: 57/118 was preserved across the cancel, verified after.

**Quota reality — `CPUS_ALL_REGIONS = 32`, and it is GLOBAL.** Free trials
cannot raise it. 8 x e2-standard-4 = 32 vCPU is exactly the ceiling, so 16-wide
parallelism is impossible no matter how many shards are requested; the extra
shards queue as a second wave. Do not be misled by the *regional* `CPUS = 200`
quota — it is real and not the binding constraint. Verify with
`gcloud compute project-info describe --project=healys-batch`, not
`regions describe`.

NEXT after 118/118, unchanged from the last handoff:
assemble → verify the assembled dataset against stage-0 (the 13 differing
columns must collapse to zero) → both evaluate runs → only then consider
deploy. Assemble command, as printed by submit.sh:
`TASK_MODE=assemble PROJECT=healys-batch BUCKET=gs://healys-backtester IMAGE_TAG=d64ca9b bash deploy/gcp/submit.sh 1`
**Do not run assemble before all 16 build tasks SUCCEED.**

Still true and still important: do **NOT** delete
`gs://healys-backtester/out/archive-2026-08-19-stale-cache/` until the new
dataset is verified — it is the evidence for the comparison.

Open questions the clean data does NOT resolve (check them explicitly after the
evaluate runs): fold 3 maxDD 25.0% → 53.4%, and the INVERTED `prem_spot`
leakage finding.

## The box: swap + earlyoom landed; the hardware is still the problem

Added 2026-08-20. Two separate failure modes were untangled this session.

**1. Claude Code sessions vanishing "with a blinking prompt" are CRASHES.**
Not timeouts, not logouts, not herdr. Three coredumps on 08-19 — SIGABRT on
main, SIGSEGV on JSC's `HeapHelper`, SIGSEGV `SEGV_MAPERR` on mimalloc's
`mi-scavenger` — each matching a herdr `agent changed ... agent=None` log line
to the second. **All three faulted in allocator/GC threads with the system
under no memory pressure**, which is the userspace face of this box's proven
single-bit corruption, not a Claude Code bug. Diagnose with `coredumpctl`.
Ruled out and verified healthy: herdr (zero errors), its SessionStart hook
(65 ms against a 10 s budget), all 15 MCP servers (<2.4 s), the network (20 ms,
0% loss on ethernet — the `iwlwifi` "Timeout" lines are correctable PCIe noise
on a `wlan0` that is DOWN).

**2. A REAL OOM kill, separate from the above.** 08-19 20:40, kernel OOM-killer
took a `claude` process at 9.7 GB RSS / 24 GB virtual. The box had 15 GB RAM
and **zram-only swap** — 15.5 GB of compressed swap living in that same RAM, so
no real headroom.

Fixed, verified live:
- **`/swap/swapfile`, 16 GB**, in a nested `/swap` btrfs subvolume so snapper
  (config `root`, plus snap-pac on every pacman txn) can still snapshot `@` —
  btrfs snapshots are not recursive, so the nested subvolume is skipped.
  Created with `btrfs filesystem mkswapfile -s 16g -U clear`, which sets NOCOW
  and disables compression by construction. Persisted at `/etc/fstab` line 17.
  **No `pri=`**, so it takes priority −2, below zram's 100: zram stays the fast
  first tier and the disk file is pure overflow. Confirmed working — zram had
  absorbed 3.6 GB while the disk file sat at 0 B. Total swap 15 GB → **31 GB**.
- **earlyoom 1.9.0**, enabled and active. Caveat: it is running the *stock*
  `--avoid '(^|/)(init|systemd|Xorg|sshd)$'`. A tuned config that also protects
  `konsole|herdr|fish|plasmashell|kwin_wayland` — so a runaway `claude` is the
  victim and the pane survives for `claude --continue` — was staged but NOT
  installed. Second caveat: earlyoom fires only when mem avail AND swap free
  are both under threshold, and with 31 GB of swap that second condition will
  rarely be true. It is a backstop, not a fast trigger.

**None of this fixes the hardware.** The panic loop is unchanged and the
DIMM bisect from the previous handoff is still the highest-value action: at the
observed MTBF an hour of survival on a single stick is already a real signal.
The 22:16 reboot on 08-19 was a deliberate user power-cycle (no pstore record),
not a crash — do not count it. The 21:11 one WAS real (fresh pstore record,
kwin_wayland GPF just before).

**Trap for the next session — `sudo` chains silently truncate.** Four separate
attempts at a multi-step `sudo a && sudo b && sudo c` ran only the FIRST
command; the sudo journal proves it each time. Wrap privileged multi-step work
in a single `sudo bash -c "..."` instead. Related: the `!` prefix runs **bash**,
not the user's fish, so `; and` chaining is a syntax error there.

## Watcher

Re-armed 01:36 CDT on `marks-build-d64ca9b-010138`, every 30 min, emitting
shard count + task-state breakdown + the most recent `[NN-META-DS]` symbol line,
and loud on any terminal state. That last field matters: symbols publish only on
completion and each takes ~1-2h, so a flat shard count is normal and the symbol
line is what distinguishes "working" from "stalled". **Monitors die with the
session** — if the box crashes, re-arm it; the Batch job is unaffected. Nothing
on GCP depends on this box staying up.

The first watcher (01:05) reported `UNREACHABLE` twice. That was a bug in the
watcher, NOT the job — see the new zsh word-splitting trap in
`DOCUMENTATION.md`. The job was RUNNING and healthy throughout; `describe`
answered in 1.75s when called directly.

## Unchanged standing warnings

- **Do NOT run the ledger re-runs or `v4_finalize` on this box** while the
  hardware is unresolved — corruption is silent and would produce a wrong
  artifact with no error. Run them on GCP Batch, as the marks build does.
- **The Docker image BAKES the repo** (`COPY . /app`), so code changes need a
  rebuild and an image tag is a frozen commit. This is why `IMAGE_TAG` is
  pinned above.
- **Verification doctrine**: never report the cloud build's state from this
  file or from memory — verify live, all three legs: job state + createTime,
  fresh task-log lines, advancing bucket count.
- Suite: `./venv/bin/python -m pytest tests/ -q` (390). Not re-run this
  session — nothing in the repo was changed by it except documentation.
