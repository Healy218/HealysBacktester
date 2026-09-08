# Post-freeze v6 launchers prepared at the halfway checkpoint

Campaign v6-local-20260906. Preparation only: no build, evaluation or final
training was started. Existing running freeze controller and causal sources
remain unchanged. Saved previews: campaign preparation post-freeze-launchers.json.

Preview each stage from the repository root:

```bash
bash scripts/run_build_v6_local.sh --campaign v6-local-20260906
bash scripts/run_evaluate_v6_local.sh --campaign v6-local-20260906
bash scripts/run_finalize_v6_local.sh --campaign v6-local-20260906
```

Add --run only when launching the chosen stage. Build executes per-symbol rows
and marks followed by assembly. Evaluate executes the existing evaluator;
finalize executes existing gated final model selection/training. Each wrapper
requires its predecessor's successful receipt and required artifacts. Full freeze
must have returned zero, recorded freeze_completed=true, and produced the merged
baseline. Finalization is still subject to the original model admission gates.
The underlying research launcher retains coverage checks, full source/raw/input
fingerprints, campaign lock and per-stage validation. No fold gates are bypassed.

The evaluator is requested to construct three folds. Existing code removes folds
whose validation starts within the global proposal optimization window; this is
conditional evaluation, not three independent fold-local strategy freezes. The
actual eligible fold count depends on the assembled dataset and is not promised
to be three. Zero eligible folds causes refusal.

Resource sizing occurs at execution, not while the freeze is using the box:
maximum four slots, 5 GiB allowance per slot plus 4 GiB available-memory reserve,
two physical cores excluded from affinity. Insufficient headroom causes refusal.
Numerical inner threads are bounded. This is admission sizing, not a hard RAM cap.
Results and logs: nn_meta/campaigns/v6-local-20260906/v6/runs/next-stage/.
Wrapper lock prevents duplicate downstream admissions; separate explicit commands
avoid automatically moving from build into training.

Validation: all three previews ran against the sealed input digest; unit tests
verify absent/failed predecessors and missing datasets cannot launch later stages.
Full main regression: 1452 tests and 18 subtests passed.
