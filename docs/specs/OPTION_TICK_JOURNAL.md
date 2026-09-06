# Optional OPRA tick journal

The existing option stream continues to maintain QuoteStore. Explicitly enable
raw quote **and trade** recording with:

```sh
./venv/bin/python -m nn_meta.live.feeds.option_stream --record-ticks
```

`--contracts A,B` selects a fixed OCC contract set; otherwise the process reads
`nn_meta/live/feeds/data/option_watch.json`. `--tick-contract-limit N` limits the
distinct recorded contracts per UTC receipt day (1–1000, default 1000), and
`--tick-root PATH` changes the default journal directory
`nn_meta/live/feeds/data/option_ticks/`. This is an opt-in recorder; installation
does not enable it in a deployed service.

The quote subscription and QuoteStore continue to cover the watch set, capped at
1000 contracts. Trade subscriptions cover the journal's admitted watch subset.
Daily admissions survive watch changes and restarts: removing a contract does
not recover its daily slot. The heartbeat reports refusals. The budget resets
at UTC midnight; the subscription refresh can delay newly eligible trades by
up to 30 seconds. Such gaps are not filled or certified complete.

Each UTC receipt-day directory contains append-only `quotes.jsonl`,
`trades.jsonl`, `contracts.jsonl` admissions, and `control.jsonl` lifecycle and
subscription observations. The journal takes an exclusive writer lock, appends
without replacing data, and fsyncs admission records before recording their
ticks. Tick files are fsynced with the five-second QuoteStore flush and on
shutdown. A partial final line refuses further appends to that file; preserve
the incomplete capture for explicit repair rather than silently truncating it.

The recorder uses the Alpaca SDK's raw message mode. The installed SDK otherwise
converts msgpack timestamps to microsecond Python datetimes and drops unknown
fields during model construction. Every journal tick preserves the decoded
message through `raw_msgpack_b64` and its SHA-256. These bytes are a lossless
msgpack reserialization of the decoded message, not the original websocket
packet. They preserve unknown fields and provider condition codes. The
normalized view keeps event nanoseconds, handler-entry wall-clock receipt
nanoseconds (`available_at_ns`), and monotonic receipt time. Handler entry occurs
after SDK decoding and dispatch; it is not network packet arrival.

Alpaca documents `t` as a timestamp, without exposing a separate SIP clock.
`sip_timestamp` is a compatibility alias of `event_timestamp_ns`, explicitly
labelled `alpaca_t_no_separate_sip_clock_asserted`. This does not establish
timestamp equivalence with Massive. Provider event precision cannot exceed the
source message. Receipt-before-event clock skew remains visible and is never
clamped. The journal's `journal_sequence` and `capture_id` identify local appends;
they are not vendor sequence numbers. Duplicate-looking trades are preserved.

Conditions use the `alpaca_opra_string` namespace. A string condition is one code,
including a string with multiple characters; it is never split into characters
or translated to Massive's integer codes. Missing conditions remain unknown.
The documented stream has no separate correction-message field; normalized
`correction=0` has `correction_available=false` when absent, and the raw message
remains available for a future provider-specific correction policy.

Heartbeats expose actual quote/trade receipt times, successful QuoteStore
updates, appended and fsynced journal counts, normalization failures, and journal
errors separately. Recording failures do not prevent independent QuoteStore
updates. An open connection, lifecycle event, or recent heartbeat is not proof
of tick receipt or continuous capture. Every status remains
`coverage_complete=false`, and normalized ticks have `model_admission=false`.
Use explicit provider and coverage validation before passing a capture to
research feature windows; do not infer missing quote order from local append
sequence without a separately declared adapter policy.

Validation: `tests/test_option_tick_journal.py` and
`tests/test_option_stream_ticks.py` cover precision/raw round trips, duplicate
trades, contract bounds/restart/rotation, partial tails, stream subscriptions,
visible disk failures, and quiet-connection status. These are deterministic
tests with a fake stream, not evidence of a deployed live OPRA capture.

Primary wire-format reference:
[Alpaca real-time option data](https://docs.alpaca.markets/us/docs/real-time-option-data).
