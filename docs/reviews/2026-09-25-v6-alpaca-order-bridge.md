# V6 Alpaca paper order bridge — September 25, 2026

The bridge is implemented in `integrations/alpaca_paper/v6_bridge.py` and
`scripts/run_v6_alpaca_bridge.py`. The CLI uses only the dedicated paper keys,
constructs Alpaca's paper trading client, verifies the prepared account
fingerprint, and reads structured positions and leg-close events from the new
V6 state after its activation timestamp. Historical simulator positions are
rejected. A stable event-derived client order ID and private SQLite journal
record intent before any POST; status and actual fill observations are retained
separately. Broker positions must reconcile to recorded whole-contract fills.
Unknown orders, foreign positions, partial fills, unresolved orders, and
uncertain POST responses block further submission.

Each proposed order checks the active option contract, paper options level,
current options buying power, displayed quote size, SIP quote age of at most
30 seconds, and the five-minute V6 entry window. A valid provider mark is the
limit; otherwise a fresh bid/ask midpoint is used. Last trade is context.
Broker fill price and quantity are stored as broker facts, not merged into the
simulator's midpoint projection. Entries buy to open and exits sell to close,
with DAY limit orders only.

The real account preview completed in read-only mode with zero new scanner
events and zero submitted orders. The fresh scanner state has no portfolio
database yet, and the restart manifest still has both scanner and order
submission disabled. The next operational step is a prospective scanner run
against the fresh state, followed by preview of genuine new structured events.
The bridge's `--submit` path remains gated by explicit manifest opt-in.
Open/partial/uncertain broker orders and multi-roll positions require operator
review before activation; this is a deliberate stop condition, not a synthetic
close or fill. The old V6 simulator and Stonks projection remain separate.

Focused bridge tests cover future-only events, real mark sizing in preview,
paper account fingerprint rejection, and lost-POST idempotency. The full
project suite passed after implementation; see the current handoff for the
final count. No Alpaca paper order was submitted.
