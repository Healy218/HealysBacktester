# V7-2 catalog audit preparation — 2026-09-23

The full 591-security 5/15/30 compact catalog is still being built. Nothing in
this note is a 7-2 completion verdict or permission to start 7-3.

`scripts/audit_v7_catalog.py` is a read-only, two-mode verifier. Live
preflight samples sealed feature/proposal stores and checks the exact 2,817
registered variants per timeframe, source and input declarations, receipt
bindings, compact mode, proposal filter, research-only status, and the
221-column downstream schema. Its `--full` mode checks all 1,773 expected
stores, rejects missing/unknown stores, deep-opens each proposal store, and
enforces the 100 GiB free-space reserve. Run full mode only after the builder
seals; then separately inspect worker/restart/resource receipts and scope
before changing the 7-2 gate. The audit deliberately reports
`ready_for_7_3=false` even after a technical pass.

Live preflight sampled one completed store with no errors while 848 proposal
stores were present; 925 were not yet complete. The report is outside the
active catalog at
`logs/v7-progress/v7-2-full-catalog-20260922-rebuild-5-15-30/preflight-catalog-audit.json`.
`scripts/sample_v7_catalog_resources.py` appends read-only JSONL samples in
that same log directory. A later sample found 291 complete securities and 881
proposal stores, 82.25°C CPU, 12.36 GB current / 19.96 GB peak cgroup memory,
400.52 GB free disk, and no cgroup CPU throttling. This is point-in-time
operational evidence, not a thermal safety or completion guarantee. Neither
tool writes to the active catalog.

After the build seals, run the following from the repository root and review
the report alongside the builder's final and recovery receipts:

```text
./venv/bin/python scripts/audit_v7_catalog.py \
  --output nn_meta/validation/v7-2-full-catalog-20260922-rebuild-5-15-30 \
  --history nn_meta/validation/v7-security-history-20260918-7-2-current \
  --full \
  --report logs/v7-progress/v7-2-full-catalog-20260922-rebuild-5-15-30/postseal-catalog-audit.json
```
