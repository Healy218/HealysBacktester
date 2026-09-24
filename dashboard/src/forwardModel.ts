import { z } from "zod";
const time = z.string().datetime({ offset: true }).nullable();
const number = z.number().finite().nullable();
const counts = z.record(z.string(), z.number().int().nonnegative());
export const deliverySchema = z.object({
  observedAt: time,
  counts,
  oldestPendingAt: time,
});
export const forwardSchema = z.object({
  schemaVersion: z.literal(1),
  observedAt: time,
  modelSha256: z.string().nullable(),
  status: z.string(),
  phase: z.string(),
  checkedAt: time,
  nextSession: z.string().nullable(),
  dataThrough: z.string().nullable(),
  elapsedSeconds: number,
  counts,
  totalPositions: z.number(),
  cycles: z.number(),
  lastCycleAt: time,
  realizedContribution: number,
  totalRolls: z.number(),
  outbox: counts,
  relay: z.object({ status: z.string(), at: time, events: number }),
  positions: z
    .array(
      z.object({
        id: z.string(),
        symbol: z.string(),
        contract: z.string(),
        state: z.string(),
        strategy: z.string(),
        openedAt: time,
        allocation: number,
        entryAsk: number,
        entryQuoteAt: time,
        rolls: z.number(),
        realizedReturn: number,
        unrealizedReturn: z.null(),
        triggerReason: z.string().nullable(),
      }),
    )
    .max(100),
  events: z
    .array(
      z.object({
        id: z.string(),
        at: time,
        kind: z.string(),
        contract: z.string(),
        reason: z.string(),
        triggerAt: time,
        quoteReceivedAt: time,
        quoteAgeSeconds: number,
        bid: number,
        legReturn: number,
      }),
    )
    .max(100),
  recentCycles: z
    .array(
      z.object({
        bar: z.string(),
        at: time,
        selected: z.number(),
        opened: z.number(),
        unfilled: z.number(),
      }),
    )
    .max(100),
  quoteCoverage: z.object({
    observed: z.number(),
    valid: z.number(),
    withReceipts: z.number(),
  }),
  history: z
    .object({
      samples: z.number(),
      firstObservedAt: time,
      failedPassesObserved: z.number(),
      uniqueQuotes: z.number(),
      recent: z
        .array(z.object({ at: time, status: z.string(), phase: z.string() }))
        .max(30),
    })
    .nullable(),
  issues: z.array(z.string()),
  limitations: z.array(z.string()),
});
const brokerTradeSchema = z.object({
  key: z.string(),
  symbol: z.string(),
  contract: z.string(),
  strategy: z.string(),
  state: z.enum(["closed", "open"]),
  allocation_usd: z.number().finite(),
  entry_price_net: z.number().finite().nullable(),
  quote_bid: z.number().finite().nullable(),
  quote_ask: z.number().finite().nullable(),
  quote_received_at: time,
  mark_price_net: z.number().finite().nullable(),
  realized_pnl_usd: z.number().finite().nullable(),
  unrealized_pnl_usd: z.number().finite().nullable(),
  opened_at: time,
  closed_at: time,
  entry_ts: time,
  exit_reason: z.string().nullable(),
  return_factor: z.number().finite().nullable(),
});
export const brokerSchema = z.object({
  schema: z.literal("v6-broker-ledger-v1"),
  summary: z.object({
    broker_orders: z.literal(false),
    snapshot_at: z.string().datetime({ offset: true }),
    starting_capital_usd: z.number().finite(),
    closed_trades: z.number().int().nonnegative(),
    open_trades: z.number().int().nonnegative(),
    marked_open_trades: z.number().int().nonnegative(),
    unmarked_open_trades: z.number().int().nonnegative(),
    complete_open_mark: z.boolean(),
    realized_pnl_usd: z.number().finite(),
    unrealized_pnl_usd: z.number().finite().nullable(),
    unrealized_pnl_usd_marked: z.number().finite().nullable(),
    total_pnl_usd: z.number().finite().nullable(),
    total_pnl_usd_marked: z.number().finite().nullable(),
    equity_usd: z.number().finite().nullable(),
    equity_usd_marked: z.number().finite().nullable(),
    pricing: z.string(),
    research_ledger_unchanged: z.literal(true),
  }),
  trades: z.array(brokerTradeSchema).max(100),
});
export type ForwardData = z.infer<typeof forwardSchema>;
export type DeliveryData = z.infer<typeof deliverySchema>;
export type BrokerData = z.infer<typeof brokerSchema>;
export type BrokerTrade = BrokerData["trades"][number];

// A closed trade is realized at its close time. Open marks are a current
// snapshot and cannot be backfilled into a historical P/L series.
export function recentBrokerTrades(trades: BrokerTrade[]): BrokerTrade[] {
  return [...trades].sort((a, b) => {
    const aAt = Date.parse(a.closed_at ?? a.opened_at ?? "") || 0;
    const bAt = Date.parse(b.closed_at ?? b.opened_at ?? "") || 0;
    return bAt - aAt || a.key.localeCompare(b.key);
  });
}

export function realizedPnlSeries(trades: BrokerTrade[]) {
  const opened = trades.map((t) => Date.parse(t.opened_at ?? "")).filter(Number.isFinite);
  const closes = trades
    .filter((t) => t.state === "closed" && t.realized_pnl_usd !== null)
    .map((t) => ({ at: Date.parse(t.closed_at ?? ""), pnl: t.realized_pnl_usd! }))
    .filter((point) => Number.isFinite(point.at))
    .sort((a, b) => a.at - b.at);
  if (!closes.length) return [];
  const start = Math.min(...opened, closes[0].at);
  let running = 0;
  return [{ at: start, pnl: 0 }, ...closes.map((point) => ({
    at: point.at,
    pnl: (running += point.pnl),
  }))];
}
export function filterPositions(
  rows: ForwardData["positions"],
  state: string,
  query: string,
) {
  return rows.filter(
    (p) =>
      (state === "all" ||
        (state === "active" ? p.state !== "closed" : p.state === state)) &&
      `${p.symbol} ${p.contract} ${p.strategy}`
        .toLowerCase()
        .includes(query.trim().toLowerCase()),
  );
}
