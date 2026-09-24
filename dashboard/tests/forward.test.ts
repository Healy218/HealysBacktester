import { expect, it } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { forwardFixture } from "./forward.fixture";
import { forwardSchema, filterPositions, recentBrokerTrades, realizedPnlSeries, type BrokerTrade } from "../src/forwardModel";
it("validates a real paper capture and preserves missing current valuations", () => {
  const data = forwardSchema.parse(
    existsSync("private/forward-preview.json")
      ? JSON.parse(readFileSync("private/forward-preview.json", "utf8")).home
          .v6Forward
      : forwardFixture(),
  );
  expect(
    data.positions
      .filter((p) => p.state !== "closed")
      .every((p) => p.realizedReturn === null && p.unrealizedReturn === null),
  ).toBe(true);
  expect(filterPositions(data.positions, "all", "")).toEqual(data.positions);
  const symbol = data.positions[0].symbol;
  expect(
    filterPositions(data.positions, "all", symbol).every(
      (p) => p.symbol === symbol,
    ),
  ).toBe(true);
  expect(filterPositions(data.positions, "all", "no-such-symbol")).toEqual([]);
});
it("rejects invented current paper valuations", () => {
  const value = forwardFixture();
  expect(
    forwardSchema.safeParse({
      ...value,
      positions: [{ ...value.positions[0], unrealizedReturn: 0 }],
    }).success,
  ).toBe(false);
});
it("sorts broker trades by latest activity and charts only dated realized P/L", () => {
  const trade = (key: string, opened_at: string, closed_at: string | null, pnl: number | null): BrokerTrade => ({
    key, symbol: key, contract: key, strategy: "ma", state: closed_at ? "closed" : "open",
    allocation_usd: 100, entry_price_net: 1, quote_bid: null, quote_ask: null,
    quote_received_at: null, mark_price_net: null, realized_pnl_usd: pnl,
    unrealized_pnl_usd: null, opened_at, closed_at, entry_ts: opened_at,
    exit_reason: null, return_factor: null,
  });
  const rows = [
    trade("older-close", "2026-09-01T10:00:00Z", "2026-09-03T10:00:00Z", 25),
    trade("new-open", "2026-09-05T10:00:00Z", null, null),
    trade("recent-close", "2026-09-02T10:00:00Z", "2026-09-04T10:00:00Z", -10),
  ];
  expect(recentBrokerTrades(rows).map((row) => row.key)).toEqual(["new-open", "recent-close", "older-close"]);
  expect(realizedPnlSeries(rows).map((point) => point.pnl)).toEqual([0, 25, 15]);
  expect(realizedPnlSeries(rows).map((point) => point.at)).toEqual([
    Date.parse("2026-09-01T10:00:00Z"),
    Date.parse("2026-09-03T10:00:00Z"),
    Date.parse("2026-09-04T10:00:00Z"),
  ]);
});
