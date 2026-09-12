import { z } from "zod";
import { trainingSchema } from "./trainingModel";
const timestamp = z.string().datetime({ offset: true });
const optionalTime = timestamp.nullable();
const number = z.number().finite().nullable();
const scanner = z.object({
  id: z.string(),
  observedAt: optionalTime,
  lastCompletionAt: optionalTime,
  scanned: number,
  queued: number,
  errors: number,
  filtered: number,
  note: z.string(),
  source: z.string(),
});
const feed = z.object({
  id: z.string(),
  observedAt: optionalTime,
  state: z.string(),
  count: number,
  lastBar: optionalTime,
  source: z.string(),
});
const signal = z.object({
  id: z.string(),
  symbol: z.string(),
  side: z.string(),
  expert: z.string(),
  score: number,
  status: z.string(),
  candidateAt: optionalTime,
  strategy: z.string(),
  source: z.string(),
});
const position = z.object({
  id: z.string(),
  symbol: z.string(),
  contract: z.string(),
  status: z.string(),
  quantity: number,
  remaining: number,
  entry: number,
  realizedGross: number,
  realizedNet: number,
  bid: number,
  ask: number,
  quoteAt: optionalTime,
  takenAt: optionalTime,
  checkedAt: optionalTime,
  exitNotice: z.string().nullable(),
  monitorError: z.string().nullable(),
});
const job = z.object({
  id: z.string(),
  state: z.string(),
  observedAt: optionalTime,
  source: z.string(),
});
export const serverSchema = z.object({
  schemaVersion: z.literal(1),
  source: z.literal("server"),
  observedAt: timestamp,
  market: z.enum(["open", "closed", "unknown"]),
  scanners: z.array(scanner).max(10),
  feeds: z.array(feed).max(10),
  signals: z.array(signal).max(100),
  positions: z.array(position).max(100),
  queueCounts: z.record(z.string(), z.number()),
  queueAvailable: z.boolean(),
  positionsAvailable: z.boolean(),
  openPositionCount: number,
  scope: z.string(),
  issues: z.array(z.string()),
});
const faRow = z.object({
  ticker: z.string(),
  sentiment: number,
  newsCount: number,
  revenueGrowth: number,
  shortInterest: number,
  floatPercent: number,
});
export const homeSchema = z.object({
  training: trainingSchema.nullable().optional(),
  schemaVersion: z.literal(1),
  source: z.literal("home"),
  observedAt: timestamp,
  jobs: z.array(job).max(100),
  fa: z.object({
    cutoff: optionalTime,
    symbols: number,
    uniqueNews: number,
    coverage: z.record(z.string(), z.number()),
    rows: z.array(faRow).max(400),
    evaluationStatus: z.string(),
    labeledRows: number,
  }),
  research: z
    .object({
      campaign: z.string(),
      observedAt: optionalTime,
      counts: z.record(z.string(), z.number()),
      totalSymbols: number,
      stages: z.array(z.string()),
      evidence: z.record(z.string(), z.boolean()),
    })
    .nullable(),
  issues: z.array(z.string()),
});
export type ServerData = z.infer<typeof serverSchema>;
export type HomeData = z.infer<typeof homeSchema>;
export type Signal = ServerData["signals"][number];
export function ageSeconds(
  value: string | null | undefined,
  now = Date.now(),
): number | null {
  if (!value) return null;
  const age = (now - Date.parse(value)) / 1000;
  return Number.isFinite(age) && age >= -30 ? Math.max(0, age) : null;
}
export function fresh(
  value: string | null | undefined,
  seconds: number,
  now = Date.now(),
) {
  const age = ageSeconds(value, now);
  return age !== null && age <= seconds;
}
export function displayNumber(value: number | null | undefined, digits = 0) {
  return value == null
    ? "—"
    : value.toLocaleString("en-US", { maximumFractionDigits: digits });
}
export function filteredSignals(
  rows: Signal[],
  query: string,
  expert: string,
  status: string,
) {
  const q = query.trim().toLowerCase();
  return rows.filter(
    (r) =>
      (expert === "all" || r.expert === expert) &&
      (status === "all" || r.status === status) &&
      (!q ||
        [r.symbol, r.id, r.strategy].some((v) => v.toLowerCase().includes(q))),
  );
}
export function scannerState(
  scanner: ServerData["scanners"][number],
  market: ServerData["market"],
  now = Date.now(),
) {
  if (!scanner.lastCompletionAt) return "unknown";
  if (market === "unknown") return "unknown";
  if (market === "closed") return "off session";
  return fresh(scanner.lastCompletionAt, 25 * 60, now) ? "reporting" : "stale";
}
