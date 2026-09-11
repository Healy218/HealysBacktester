# Firebase dashboard implementation — September 11, 2026

User selected Firebase for the private React dashboard and an iPhone app.
Implemented on `ops/firebase-dashboard-20260911` in a separate worktree. Main
research source and production scanners remain untouched. Do not merge this
branch into the active source-pinned campaign or the older production branch.

Dashboard source/runbook: `dashboard/README.md`. Five pages: Overview, Signals,
Positions, Research, FA. Firebase Auth + exact-document Firestore reads; verified
UID allowlist, all client writes denied. One-minute, read-only Python summary
publishers for server/home. Actual server and home captures were validated;
private captures/screenshots are ignored and excluded from production assets.
Includes bounded candidate records, candidate-cohort rather than send-time
counts, queued-vs-sent separation, stale markers, exit-due positions counted
active, missing fee/P&L preservation, and explicit campaign binding.

Firebase project ID, public web config, owner email/UID and server publisher
credentials are not supplied. An async question was asked; no answer received.
No Firebase project created, no billing enabled, no cloud deployment, no summary
timers activated, no notifications sent. The production predeploy guard correctly
refuses missing Firebase configuration. Finish concrete setup from README once
owner supplies the project/access details. Prepare/deploy rules before site/data.

Capacitor iOS project generated and synced successfully. It needs Mac/Xcode,
owner signing team, Firebase configuration and physical-device acceptance.
Push/APNs and TestFlight distribution are not implemented in this first version.

Validation: production TypeScript/Vite build; four frontend tests; seven Python
adapter/accounting tests; four Firebase emulator rule tests; two end-to-end
Auth/Firestore browser tests; four desktop/iPhone-sized Chromium UI tests.
Publisher systemd templates verified without installation. Production dependency
audit: zero vulnerabilities; Firebase development tooling reports 11 moderate
advisories. Node 24 is recommended; local checks ran Node 26 with a Firebase
CLI static-server engine warning. Native Safari/WKWebView not yet tested.

Earlier FA work remains deployed independently in HealysAutomation; see the
archived handoff and that runtime's README/review documents. PTON sale status
must be read from current broker/position evidence, never inferred here.
