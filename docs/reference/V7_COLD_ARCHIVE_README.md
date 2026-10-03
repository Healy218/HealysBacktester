# V7 — paused research archive

This folder preserves HealyLabs V7 options-model research so it can resume after
storage and memory constraints are resolved. V7 combines point-in-time stock
identity/actions, causal 5/15/30-minute signals, historical option quotes/trades,
and realistic execution paths to build training examples and evaluate proposed
options decisions. Its accepted research scope is March 15, 2022–September 14,
2026, across 591 securities. It is not a finished trained model or deployed expert.

Identity/actions (gate 7-1) and causal context/proposals (7-2) are complete.
Required option evidence (7-3) is incomplete. Execution integration, full dataset
assembly/folds, resource/recovery validation and training readiness (7-4 through
7-7) remain open. Archiving changes storage, not these scientific verdicts.

## Folder contents and completion

- `data/*.tar.zst`: lossless Zstandard level-22 archives of local V7 raw inputs,
  validation/catalogs/checkpoints, plans, source snapshot and existing external
  V7 payloads. Numbered shards map to source paths in `manifests/plan.json`.
- `manifests/*.verified.json`: each archive's SHA256, full source comparison,
  member counts and eligible local reclamation records.
- `notes/notes.tar.zst`: project documentation and handoff history, including
  V7 reviews, specifications, decisions and the final pre-archive handoff.
  Shared notes are included to preserve the context of mixed V6/V7 sessions.
- `notes/SHA256SUMS`: checksum for the compressed notes.
- `RESTORE.txt`: short restoration reminder.
- `VERIFIED.json`: exists only when every planned data shard has passed checksum,
  complete source comparison and member census.
- `COMPLETE.json`: exists only after the archive run finishes its selected
  reclamation stage. Without it, this is an in-progress/partial archive.
- `LOCAL_CLEANUP_COMPLETE.json`: the independently verified local cleanup subset
  is finished; remaining MRHA compression may still be running.
- `retired.jsonl`: exact local files removed after verification. Small local
  receipts, links, raw inputs, code, shared inputs and external originals remain.

Original MRHA identity: UUID `62C9-C390`, exFAT, mounted at
`/run/media/healy/MRHA`. Do not rename or remove the existing
`HealysBacktester/sealed-v7-payloads-20260929` and
`HealysBacktester/v7-entry-campaign-20260927` trees while local inputs use them.
The copies in this archive preserve these targets for restoration.
Secrets in `.env` and the Python virtual environment are not archived.

## Proper restoration order

1. **Read the notes first.** Choose an empty staging directory on a disk with
   enough room for expanded data (hundreds of GB; consult all manifest source
   byte counts, allow for hardlink/reflink expansion and working space).
   From this `v7` folder, verify and extract notes:

   ```bash
   (cd notes && sha256sum -c SHA256SUMS)
   mkdir -p /path/to/staging/notes
   tar -I zstd -xf notes/notes.tar.zst -C /path/to/staging/notes
   ```

   Read the extracted `HANDOFF.md`, then
   `handoff-history/HANDOFF-2026-10-02-before-v7-cold-archive.md` for the last
   research handoff, followed by `TODO.md`, relevant `ROADMAP.md` gates and
   `docs/CURRENT_STATE.md`. Historical commands are not restart orders.

2. **Verify completeness and hashes before restoring data.** Require
   `VERIFIED.json` and every planned shard/receipt. Run the following from `v7`
   using a trusted Python installation (in the existing checkout use
   `./venv/bin/python` with this script path). This checks each complete archive
   against its saved SHA256; do not proceed on errors:

   ```bash
   python3 manifests/verify_and_list.py
   ```

   The helper prints extraction commands in the order below. It performs no
   extraction, deletion or service restart. `.partial` files are never evidence
   of a complete archive. If incomplete, use the resume procedure below.

3. **Restore source/environment.** The source-snapshot shard holds the working
   project source, requirements and provenance, including uncommitted source
   changes, under the original archive-state path. Extract to staging, then copy
   its `files/` tree into a research checkout. `provenance.json` records the
   original Git commit. Preserve the source snapshot and frozen producers;
   do not replace them with unrelated current code. Recreate a compatible
   environment from the saved requirements and restore credentials separately.
   Keep acquisition/build/training services stopped during restoration.

4. **Restore external payload targets, then local inputs and plans, then all
   validation/catalog/checkpoint shards.** Archives store original paths without
   the leading `/`. Extract each with:

   ```bash
   tar -I zstd -xf data/NNNNN.tar.zst -C /path/to/staging
   ```

   Use the helper's ordered commands and the plan to identify shard numbers.
   Its staging directory must exist. Do not blindly extract over an active
   checkout. The restored staging tree contains `home/healy/Coding/...` and
   `run/media/healy/MRHA/...`. Place those trees at the corresponding original
   locations after reviewing conflicts. Preserve symlinks and permissions.
   Absolute symlinks require the original paths or an explicit, verified remap.
   Restore to a Linux filesystem that supports links; loose extraction onto
   exFAT cannot preserve Linux symlink/hardlink semantics. Existing correct
   external objects may be reused after comparing their checksums.

5. **Validate the checkpoint before research restart.** The selected campaign
   is `nn_meta/validation/v7-required-inputs-20261002-perf-r0/`.
   Preserve its predecessors, `discovery-campaign/revisions/`, wave symlinks,
   SQLite databases and any journals/sidecars exactly. Follow original sealed
   receipts and frozen producer/runtime checks; never relabel a checkpoint to
   bypass a mismatch. Verify referenced raw payloads and all symlink targets.
   Consult source-bound recovery procedures if the machine/environment changed.

6. **Resolve the last blockers, then resume only the selected gate.** At the
   last research handoff, discovery admitted zero workers because the scheduler
   reserved 25,600 MiB for paused V6 work. Historical option capture epoch 00002
   failed with HTTP 403 after Massive options cancellation. More disk space
   alone fixes neither RAM admission nor historical-provider access. Reconcile
   resource policy with the user pause and arrange authorized historical input
   access; do not substitute snapshots, widen exclusions or buy service silently.

   The prior controllers were
   `healys-v7-required-discovery-20260930.service` and
   `healys-v7-required-frontier-20260930.service`, with optimized launcher
   `scripts/finish_v7_optimized_inputs_v1.py`. Consult their archived adoption
   evidence before reconstructing a missing service. Do not run an old launcher
   blindly: validate its selected root, manifest and checkpoint lineage first.
   Observe actual resumed progress. Completed entry capture must not be repeated.
   Finish 7-3 before claiming its closure; then follow 7-4 through 7-7. No model
   promotion or non-V7 campaign resumption is implied.

## If archiving was interrupted

Keep both MRHA and the local sources intact. Mount UUID `62C9-C390` at its
original path; ensure at least 20 GiB external free space and stop V7 writers.
Read the current local receipt:
`nn_meta/validation/v7-cold-archive-20261002-r0/progress.json`.
With the installed source version unchanged, resume the finite plan from the
original checkout using:

```bash
systemctl --user start healys-v7-cold-archive.service
```

If restoring from the source snapshot, first overlay the newer staged archive
runtime saved in the compressed notes under `archive-runtime/` onto `scripts/`
(and the service file onto `deploy/systemd/` if installing it). The original
three-thread launcher remains available as a slower fallback.
If the service is not installed, use
`bash scripts/start_v7_cold_archive_staged.sh` from that checkout. Completed shards are
rehash-verified and reused; incomplete shards are rebuilt. The selected staged-v2
runner compresses local shards into at most 8 GiB of SSD staging while guarding
10 GiB internal free space, then serializes transfers and verification on MRHA.
Oversized and external-source shards stream directly in a later serial phase.
October 3 user direction allows independently verified local files to be
reclaimed while MRHA-only compression continues. Each affected archive and
source file is rehashed before removal; this does not fabricate full completion. The run stops on corruption, changed
sources, insufficient external capacity or other failed checks. Completion is
receipt-owned, never inferred from an idle service or a folder name.


The concurrent cleanup service is `healys-v7-local-reclaim.service`. Its progress
is `early-cleanup-progress.json` beside archive progress. It preserves the original
retirement journal so final cleanup skips files already removed. Reinstall its
runtime from the extracted notes' `archive-runtime/` folder if needed. Inspect the compressor phase
before resuming it: the early pass is for the external-only compression phase.
An `ExecStopPost` hook recovers only a controller stop owned by this cleanup.
Do not delete the journal, intent or owned-stop marker while either service runs.
