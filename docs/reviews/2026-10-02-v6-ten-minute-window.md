# V6 paper ten-minute entry window — October 2, 2026

User explicitly changed V6's broker entry deadline from five to ten minutes.
Installed at 10:36:02 Central. Broker polls subsequently completed under the new
manifest. The 10:45 and 11:00 scans subsequently completed in 247.372s and
251.968s with successful held monitoring and no detection errors.
This is an execution timing change, not a model deployment or quote-age change.

Scanner v11 / resilient consumer v2 use a versioned allocation override based on
frozen ForwardPortfolio.allocate, changing all three entry cutoffs to ten minutes
from the original signal close. Features, ranking, sizing and other portfolio
methods still come from the verified frozen checkout. Source-leg capture preserves
that original signal timestamp. Broker runtime v6 / bridge v5 admit entries through
600 seconds, including first intent after a crash. Source reconciler v4 preserves
unfilled projections until the same window expires. Existing admitted ladders
retain their separate 300-second maximum and fixed 30/30/60-second step waits.
Fresh quotes must still satisfy the unchanged 30-second SIP rule.

Held-monitor retries retain their 120-second budget, with the signal-close cap
moved to +570 seconds. Scanner subprocess/service timeouts are 630/660 seconds;
allocation still rejects a decision or quote past +600 seconds. No old event is
redated, no old frozen file is edited, and no direct order is submitted by the
installer. The independently scheduled broker owns actual paper orders.

101 focused tests passed, including 600-second inclusive/601-second rejected
boundaries, quote arrival after the deadline, original signal chronology,
crash-before-intent recovery, stale quotes, source retention and existing ladder
behavior. New subclass imports successfully from the actual frozen checkout.
The first test run exposed a missing source-capture trigger in the test fixture;
the fixture now installs the production trigger before checking event chronology.

Installer: scripts/install_v6_ten_minute_v1.py. Source hashes remain append-only in
the selected paper manifest; previous manifest/unit snapshots preserved under
runtime-revisions/ten-minute-v1-20261002 in the paper state. Installed drop-ins:
healys-v6-alpaca-scanner.service.d/99-ten-minute-v11.conf and
healys-v6-alpaca-orders.service.d/99-ten-minute-v6.conf.
Both timers were restored after a lock-protected consumer drain.
Evidence: nn_meta/validation/v6-ten-minute-20261002-r0/{deployment,verification}.json.

Current manifest SHA: e6d33229e249ffd4a0ba0f116cf73434b16fb97c91e834f71ad250c424f31c06.
Prospective quote reliability remains an observation task; a wider admission
window does not guarantee quotes or fills. V7 remains paused for optimization.
