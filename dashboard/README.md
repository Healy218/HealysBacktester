# HealyLabs Observatory

Private React + Firebase dashboard, with a Capacitor iOS project. Development
lives on `ops/firebase-dashboard-20260911`, separate from the source-pinned
research build. No scanner, position, ranking or notification state is mutated.

## What works

- Overview: last completed scanner pass, feed heartbeats, alert queue totals,
  active taken positions (including exit-due positions), publisher freshness.
- Signals: today's Chicago candidate cohorts, expert/status/search filters,
  bounded latest-100 ledger and source inspection. Queue `sent` is delivery
  evidence; scanner `delivered` is only queued. Exact send time is unavailable.
- Positions: recorded entry/sale accounting, partial sales, unknown fees,
  observed bid/ask with timestamps, monitor errors and recorded exit guidance.
- Research: one explicitly configured campaign progress receipt, artifact
  presence, automation receipts. Presence never implies passing evaluation.
- FA: immutable snapshot coverage, ticker search, provider sentiment, revenue
  growth, short interest, float and forward evaluation status.

## Local development

Node 24 LTS is recommended (Firebase CLI's static server supports Node 20/22/24).

```sh
cd dashboard
npm ci
npm run dev
```

Without configuration the login page explains that Firebase is pending. During
local development, **Open local snapshot** reads a user-selected JSON file into
memory; it is labeled captured data. The feature is compiled out of production.
No private data is placed in `public`, `src` or the JavaScript bundle.

```sh
/path/to/venv/bin/python publisher/collect.py home \
  --root /home/healy/Coding/HealysAutomation \
  --progress /home/healy/Coding/HealysBacktester/logs/v6-progress/v6-local-20260906/latest.json \
  --output private/home.json
```

The optional `scripts/capture-server-preview.py` makes a read-only SSH capture
using existing SSH access; it executes the adapter in memory and installs no
server source. Combine captures as `{"server": <server document>, "home": <home
document>}` in `private/preview.json`. The entire private directory is ignored.

## Firebase Spark setup (pending owner project/access)

1. Create a **separate Firebase Spark project** without linking billing. Do not
   reuse the research Google Cloud project or enable paid App Hosting/Storage.
2. Add a web app. Copy the public web config into `.env.local` using `.env.example`.
   Firebase web API keys are public identifiers; service credentials are not.
3. Create Firestore **Standard edition**, Native mode, `(default)` database,
   choosing the desired region. Enable Email/Password authentication.
4. Create your login user in Firebase Auth. Sign in and use the verification
   email button, then sign out/in to refresh the verified token.
5. In Firestore Console create `access/YOUR_AUTH_UID` with `enabled: true`.
   Use the real Firebase Auth UID, not an email. All other users are denied.
6. Deploy **rules and indexes first**, then the configured site:

```sh
npx firebase login
npx firebase deploy --project YOUR_PROJECT_ID --only firestore:rules,firestore:indexes
npx firebase deploy --project YOUR_PROJECT_ID --only hosting
```

The hosting predeploy validates configuration and builds the production app.
No Cloud Functions are used. Firestore rules allow verified, allowlisted users
only two exact document reads; browser writes, collection listing, and access
self-grants are denied. Firebase Auth signup alone grants no data access.

## Summary publishers

Install/run from a dedicated git checkout on each host, never patch the pinned
research checkout or merge its source into the production scanner branch.
`collect.py` uses only standard Python for server data; home FA reads require
pandas/pyarrow. Publishing uses `google-auth` and `requests` already available
in the existing environment. No provider API credentials are read.

Use a dedicated service account in the new Firebase project with the minimum
Firestore write permissions needed (for example `roles/datastore.user`). IAM
server credentials bypass Firestore rules: store them mode 600 outside the repo,
never under a VITE variable. This role is project-wide; keep this project private
and separate from other applications. The publishers write only
`dashboard/server` and `dashboard/home`, replacing one document per minute.

```sh
/path/to/venv/bin/python publisher/publish.py server \
  --root /path/to/HealysBacktester --project YOUR_PROJECT_ID \
  --state ~/.local/state/healylabs-dashboard
# Prints a dry-run report. Add --publish only after project/rules are verified.
```

`deploy/` provides resource-limited user systemd templates and environment
examples. Create the state directory, populate the per-host environment file,
install templates under `~/.config/systemd/user/`, and enable the appropriate
`healys-dashboard-publisher@server.timer` or `@home.timer` after one verified run.
These timers have NOT been installed or activated by this implementation.
User lingering is needed for publishers to continue after logout.

Two documents/minute total is 2,880 writes/day. Visible clients fetch two docs
once/minute (up to 2,880 data reads/day per continuously open client, plus access
rule reads). Background tabs pause polling. The 750 KB application document
limit, one-minute writer lock/rate limit, unindexed payload and bounded histories
control costs. Firestore free quotas are not a substitute for measuring actual
bandwidth and aggregate usage. No managed backup, TTL or paid features required;
the dashboard summaries can be regenerated from authoritative host records.

## iPhone

The native project is in `ios/App/App.xcodeproj`. On a **Mac with Xcode**, after
configuring Firebase:

```sh
npm ci
npm run ios:sync
npx cap open ios
```

Select your Apple development team and a unique bundle identifier, then build
and install on your iPhone. Linux can generate/sync the project but cannot
compile, sign or install the native app. Capacitor uses bundled web assets;
there is no development-server URL or cleartext override in the native config.
Push notifications/APNs, Face ID and TestFlight distribution are future work;
this version is a read-only dashboard, not a notification delivery service.

## Validation

```sh
npm run build
npm test
/path/to/venv/bin/python -m pytest publisher/test_collect.py -q
# Java 21+ required; emulator uses demo-healylabs, not a live cloud project:
npm run test:rules
# Install Playwright Chromium once, then:
npm run test:browser
```

Browser tests cover desktop and iPhone-sized Chromium, navigation, filtering,
evidence inspection, invalid imports, and page overflow. This does not establish
actual Safari/WKWebView or signed-device acceptance. The tests optionally use
ignored private captures; otherwise they exercise honest empty states.

Additional end-to-end login test: `npm run test:auth-browser` (Java and Chromium
required). It signs into local Auth/Firestore emulators, reads authorized data,
revokes access, checks that the next refresh clears private data, and verifies
that an authenticated stranger cannot read either summary.
`node scripts/verify-build.mjs` checks the production bundle excludes local
preview controls and captured private position identifiers.
