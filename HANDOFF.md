# Dashboard handoff

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

Earlier implementation details: `docs/reviews/2026-09-11-firebase-dashboard.md`.

Timer follow-up: switched to 60 seconds after prior completion (plus up to
5 seconds jitter) to avoid calendar coalescing hitting the 55-second rate guard.
Corrected home timer completed successfully at 18:06 UTC; live schema and
anonymous-denial checks still pass. Server timer source is 0595ea7.
