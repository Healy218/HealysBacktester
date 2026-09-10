# Actual taken-trade accounting

Implemented on the isolated production branch; not yet deployed. The home v6
campaign source and artifacts are unchanged.

## Commands

- `/sold ID 1 @ 1.20 fees .04 ref BROKER_FILL_ID` records a user-reported sale.
  Premium is per share; fees are total dollars for this sale, not per contract.
  Quantity cannot exceed the unsold entry quantity. Zero sale premium is allowed.
  Partial sales retain open/exit-due monitoring; the final sale closes the trade.
- `/sold ID` retains the old manual close shortcut, explicitly leaving sale
  accounting incomplete. Detailed sales can subsequently fill in that history.
- `/entryfees ID .12` supplies or corrects total actual entry fees.
- `/salefees ID SALE_NUMBER .04 ref BROKER_FILL_ID` supplies/corrects sale fees
  and supplies a missing broker reference (existing references stay immutable). Find the sale number with `/trade ID`.
- `/entryprice ID 1.00` supplies a previously missing entry premium, including
  after closure. It cannot overwrite an existing premium.
- `/trade ID` shows sale history, remaining quantity by recorded fills, and
  realized gross/net P/L. `/selllist` shows remaining contracts.

Entry quantity/premium cannot be changed after sales, except supplying a
missing premium or repeating unchanged values. Existing average entry price
represents the original position; scaling into a position is not implemented.
The ledger applies to standard long single-leg options with a 100 multiplier,
consistent with the existing Taken workflow. Adjusted deliverables, exercise,
assignment, and broker-native export adapters are outside this implementation.

Decimal cash calculations allocate total entry fees proportionally to sold
quantity. Missing actual fees keep net P/L unknown; quotes and estimated fee
schedules never populate this realized ledger. Existing fresh-bid estimates
remain labelled estimates and use remaining quantity after partial sales.

SQLite migrations are additive. Commands serialize in the existing immediate
transaction and use a savepoint for rejected operations. Telegram update IDs
are idempotent; supplied broker fill references are unique and reject conflicting
reuse. Without a reference, two distinct updates represent two distinct sales.
Successful mutating command arguments are retained in an append-only event
history, including fee corrections. No position history is copied into git.

## Broker reconciliation

Run with the project's venv Python:

```sh
python scripts/reconcile_taken.py --database /private/queue.sqlite3 --broker-json /private/broker.json
```

The normalized JSON is a list with one object per tracked trade. Example uses
fictional data:

```json
[{
  "trade_id": "EXAMPLE_ID",
  "contract": "SPY351009C00600000",
  "entry_quantity": 3,
  "entry_price": "1.00",
  "entry_fees": "0.12",
  "remaining_quantity": 2,
  "sales": [{"quantity": 1, "premium": "1.20", "fees": "0.04", "broker_ref": "example-fill-1"}]
}]
```

The tool opens SQLite in read-only mode with a consistent read transaction.
It compares contract, entry quantity/price/fees, remaining quantity, and exact
sales by broker reference, premium, quantity and fees. Unknown values or
unreferenced sales prevent a match. Exit code 0 means every supplied record
matched; mismatch or an empty comparison exits 1. This checks only supplied
trades and establishes agreement with supplied records, not independent broker
authentication or account-wide completeness. Actual broker records have not
yet been supplied or compared.

## Deployment and rollback

Before deployment, back up server SQLite using its backup API and record the
source commit. Deploy via git pull on the isolated production branch. Queue
initialization installs additive tables/columns; no existing quantities/fills
are inferred or changed. Validate using a separate temporary queue; do not
invent fills in the real queue. Rollback to the prior code is safe only before
new sales are recorded: old code would display original quantities after a
partial sale. After new sales, preserve the ledger and use a forward fix or
explicit operational reconciliation before rollback.

## Validation

Full ops suite: 689 tests and 18 subtests passed. Final reference/ID guards:
22 accounting tests passed. Coverage includes migration, exact cash flows,
unknown fees, legacy closure backfill, concurrent oversell prevention, update
and reference idempotency, fee audit history, broker mismatches, and a CLI
check that the database bytes are unchanged. git diff --check passed.
