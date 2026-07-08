# fa/collectors — Stage 0: dumb-by-design raw collectors (fetch, timestamp,
# append). Deploy early on the live-alert server; see FA_SPEC.md.
#
# Contract every collector honors:
#   collect() -> int   # rows appended to ARCHIVE/<source>/<yyyy-mm>.parquet
# Rows carry at minimum: ts_utc, source, raw payload fields. No analysis here.
