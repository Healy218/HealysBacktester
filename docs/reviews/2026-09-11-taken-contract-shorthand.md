# Register the actual option contract from a Taken reply

User replied with `/taken 1 9/16 72C @ 1.03` after tapping Taken on an alert
for TQQQ September 16 71C. The previous parser rejected the shorthand and the
button-created position remained the alerted 71C with no quantity or premium.

The parser now accepts quantity + M/D[/YYYY or /YY] + strike/right + optional
premium. Replies inherit the exact original alert identity; standalone commands
must include its Trade ID. The ticker comes from that alert. Yearless dates use
the current UTC year, never roll silently to next year. Dates, strike precision,
quantity, premium, underlying, call/put direction and expiration are validated.
Full OCC override syntax remains supported.

An open Taken-button placeholder with no quantity, premium, fees, sales or exit
notice can now have its contract corrected by an explicit override. Its frozen
strategy/stop context and trade ID are preserved, monitor checks are invalidated,
and the confirmation displays the corrected contract and submitted fill. Filled,
closed, fee-bearing, sold and exit-marked positions cannot be reassigned. The
original alert remains immutable, with command audit and retry idempotency intact.

102 focused tests passed locally across Taken parsing, accounting, fees, exit
monitoring and session recovery. Regressions cover the exact command, reply vs
explicit ID, years, decimal strikes, malformed input, same-side validation,
placeholder correction and protection of nonplaceholder entries.

Production record inspected read-only: trade 00EA905144FB, TQQQ260916C00071000,
quantity/premium absent; failed command response cached at update 710008726.
The previously rejected update will not be replayed automatically. After deployment
user can resend `/taken 00EA905144FB 1 9/16 72C @ 1.03` as a new standalone message.
No live position or Telegram message was changed/sent by the local tests.

Deployed 2cf23a9 through fast-forward Git pull on September 11. All 102
focused tests also passed on Hetzner. Existing minute dispatcher loads the
updated parser on its next run. Live position is still awaiting the user’s
new command; do not claim the 72C has been recorded without readback.
