# Private Firebase dashboard

Requested: affordable personal dashboard accessible on desktop and iPhone.
Selected: React/TypeScript/Vite, Firebase Spark Auth/Firestore, Capacitor iOS.
Keep existing Hetzner scanners/feeds and home research/FA infrastructure.

The publisher reads SQLite with URI `mode=ro` and `query_only`, feed heartbeat
JSON, bounded log tails, immutable FA snapshot hashes, and a specifically named
campaign progress receipt. It imports no live scanner or notifier modules.
It replaces just `dashboard/server` or `dashboard/home` once per minute. The
payload is unindexed JSON text, bounded below Firestore's document limit.
Browser reads are allowlisted by verified Auth UID; listing and writes denied.
Access rules were tested in the local demo emulator, including revocation.

Five pages and common navigation are implemented. Source interpretation:
- `sent` is recorded queue delivery, not scanner log `delivered` (which is queued).
- Today's counts refer to Chicago candidate cohorts. No exact send timestamps
  are available; the UI never invents them. Detail is limited to latest 100.
- Completion log prints use the preceding UTC timestamp as an approximation.
- Missing sources and future timestamps are not healthy. Capture time does not
  replace last observed source activity. Session status follows captured calendar.
- `exit_due` is active until closed. Net realized P&L requires recorded fills
  and all applicable fees; quotes are separate and retain their observation time.
- FA is experimental and immutable. Zero matured labels gives no performance
  claim. Artifact presence in Research is progress, not promotion evidence.

Live read-only capture at 15:49 UTC September 11 validated all four scanners,
two feeds, 100 bounded candidates and the position adapter without errors. Home
capture validated the 300-symbol FA snapshot and existing campaign receipt.
Captured data remains local, ignored, and absent from production bundles.

Verification: 4 frontend +7 Python +4 security-rule +2 login-browser +4 responsive
browser tests passed; TypeScript/Vite production build and Capacitor iOS sync
passed. Read-only systemd template verification passed. Production npm audit
reported zero vulnerabilities; 11 moderate advisories remain in dev tooling.
The missing-project predeploy guard was verified to refuse deployment.

Remaining: Firebase owner/project configuration, cloud rules/site deployment,
publisher credentials/activation, real end-to-end cloud readback, and Mac/Xcode
signing/device validation. No paid services or notifications were activated.
Setup and exact commands are in `dashboard/README.md`.
