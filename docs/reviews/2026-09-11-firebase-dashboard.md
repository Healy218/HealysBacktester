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

## Live Firebase deployment — September 11, 2026

Supersedes earlier cloud-setup-pending notes. Project `stonks-22367`, owner
`mrhealy115@gmail.com`; Hosting is live at https://stonks-22367.web.app.
Registered web app `1:290920029883:web:1b443e4c821b96a6a2539e`; public config
is in ignored `dashboard/.env.local`. Standard Native Firestore `(default)`
is in `us-central1`, deletion protection enabled, billing disabled. Private
rules and payload index exemptions deployed before Hosting.

Home and server publishers deployed in separate checkouts and Python environments.
Both first publications succeeded with no source issues; live documents passed
frontend schemas; unauthenticated reads returned 403. Timers running about once per minute
`healys-dashboard-publisher@home.timer` (home) and `@server.timer` (Hetzner)
are enabled. User lingering is enabled on both hosts. Service credentials are
mode 600 in each user's `.config/healylabs-dashboard`, never committed.
Dedicated dashboard-home/dashboard-server service accounts have datastore.user
on this separate project. This role bypasses Firestore client rules.

Python runtime: each host's `~/.local/share/healylabs-dashboard/venv`.
Home source `/home/healy/Coding/HealysAutomation`; server source
`/home/mrhea/HealysBacktester`. Server publisher code is a detached Git worktree
at `/home/mrhea/HealyLabsDashboard` (0595ea7). Home code is this checkout.
Campaign progress is pinned to `logs/v6-progress/v6-local-20260906/latest.json`
in the home research repo. Source-pinned build and production scanner code
were not changed. Existing trading environments were not modified.

Live browser check: HTTP 200, sign-in visible, preview import absent, zero
JavaScript errors. Production build/privacy check and configured iOS sync passed.
Native signing/device acceptance and push notifications remain outstanding.

**Access still pending:** Firebase Authentication returns CONFIGURATION_NOT_FOUND.
User has been asked to open Authentication in Firebase Console, click Get started,
enable Email/Password, and add their email with a privately chosen password.
Once done, inspect the real Firebase Auth UID, create `access/{uid}` enabled=true,
and have the user verify their email via the dashboard and sign in again.
Never mark an email verified administratively just to bypass this check.
No Auth user/access grant or signed-in live browser acceptance has happened yet.

Timer acceptance caught calendar coalescing placing two home runs within the
55-second publication guard. Timer now uses OnUnitInactiveSec=60s plus up to
5 seconds jitter, so each run waits a full minute after the previous completion.

## Owner access granted — September 11, 2026, 19:18 UTC

Supersedes the Authentication-initialization-pending notes above. Email/password
authentication is enabled. Looked up the user by the exact owner email
mrhealy115@gmail.com and enabled access for UID `6PNmN6SAEsclHtmEXKS5Mma3IZw1`.
Grant readback succeeded. Firebase reports emailVerified=false; verification
was not overridden and no email was sent by automation. User must sign in,
press Send verification email, follow the link, then sign out/in.
Home/server documents refreshed at 19:18 UTC, passed frontend schemas with no
source issues, and anonymous reads returned 403. Signed-in owner acceptance
is pending the user's email verification; administrative readback is not
evidence of successful browser access.
