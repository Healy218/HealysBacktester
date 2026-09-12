# Training library — September 12, 2026

The private Firebase dashboard now has a Training page with Compare, V2, V3,
V3.1, V4, V5 and V6 views. Each version includes its summary, individual
out-of-sample folds, available validation/calibration diagnostics, source
reports and a downloadable Markdown summary. There is no combined return or
cross-generation ranking: the windows, universes and accounting differ.

V2/V3 use their retained reports; V3's misleading legacy document heading is
explained using the EXPERIMENTS mapping. V3.1/V4 use preserved history because
the ignored original reports are absent locally. V4's August EV run and July
shared-simulation run remain separate. V5 uses the original walk-forward
report, not the later threshold sweep. All V2–V5 results are labeled pre-audit
history; old gate verdicts do not waive the September corrections.

V6 follows the explicit `TRAINING_CAMPAIGN` under `TRAINING_ROOT`. It never
selects the newest directory or reads the multi-GB parent scope. Small stage
receipts bind the evaluation report, manifest and final ensemble configuration
by SHA-256 before publishing their metrics. The final validation tail is
labeled selection/revalidation, not new held-out evidence. The observer does
not reload or independently rehash all model weights every minute.

The publisher distinguishes running work without seed children, completed
training, an explicit final gate refusal and an operational failure. A seed
count of 40/40 alone does not establish completion. The same current observation
drives both Research and Training, replacing the stale old build snapshot.
No Telegram summary or new scheduling service is introduced.

The existing home publisher supplies the library inside the authenticated
`dashboard/home` payload. Schema additions are optional for rolling deployment.
Source text and metrics are never bundled into public JavaScript. Markdown
source rendering uses React text nodes only; it executes no HTML and loads no
remote source resources. Access revocation clears the report and download
control with the rest of the private home document.

Validation: 16 publisher tests, 7 frontend unit tests, 8 desktop/phone browser
checks, production TypeScript/Vite build and private-evidence bundle scan.
Browser checks cover all versions, comparison, source expansion, download,
missing/zero metrics, inert source HTML and page overflow. Local Firebase
emulator login/revocation checks also cover the Training view.

Configuration in the existing home environment:

```ini
TRAINING_ROOT=/home/healy/Coding/HealysBacktester
TRAINING_CAMPAIGN=v6-train-20260912r2
PROGRESS_RECEIPT=/home/healy/Coding/HealysBacktester/logs/v6-progress/v6-train-20260912r2/latest.json
```

The timer continues its existing roughly one-minute cadence. Completion is
picked up automatically, including the final validation table and gate log.
The v6 research sources remain pinned and untouched by this dashboard branch.
