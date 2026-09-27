import { z } from "zod";
// Payloads published by DraftKings-Scripts `python -m dfs.site` to the
// Firestore documents dfs/latest and dfs/history (separate from the stock
// dashboard/* documents).
const time = z.string().datetime({ offset: true });
const num = z.number().finite().nullable();
const lineupPlayer = z.object({
  slot: z.string(),
  name: z.string(),
  team: z.string(),
  position: z.string(),
  salary: z.number(),
  proj: num,
  id: z.string().nullable(),
});
const lineup = z.object({
  strategy: z.string(),
  rank: z.number().int(),
  salary: z.number(),
  proj: num,
  objective: num,
  actual: num,
  status: z.string(),
  players: z.array(lineupPlayer),
});
const boardRow = z.object({
  id: z.string().nullable(),
  name: z.string(),
  position: z.string(),
  team: z.string(),
  opponent: z.string().nullable(),
  salary: z.number(),
  proj: num,
  ceiling: num,
  boomC: num,
  boomD: num,
  value: num,
  depth: z.string().nullable(),
  excluded: z.string().nullable(),
  status: z.string().nullable(),
  method: z.string().nullable(),
});
const trackRow = z.object({
  week: z.number().int(),
  source: z.string(),
  runId: z.string().nullable(),
  file: z.string(),
  proj: num,
  actual: num,
  status: z.string(),
});
const udLeg = z.object({
  name: z.string(),
  side: z.string(),
  line: z.number(),
  stat: z.string(),
  p: z.number(),
  src: z.string(),
  mult: z.number(),
});
const underdog = z.object({
  tiles: z.record(z.string(), z.number()),
  frontier: z.array(
    z.object({
      rank: z.number(),
      k: z.number(),
      mult: z.number(),
      p: z.number(),
      legs: z.array(udLeg),
    }),
  ),
  td_gaps: z.array(
    z.object({
      name: z.string(),
      display_mult: z.number(),
      ud: z.number(),
      books: z.number(),
      blend: z.number(),
    }),
  ),
  edges: z.array(
    z.object({
      name: z.string(),
      stat: z.string(),
      line: z.number(),
      side: z.string(),
      p: z.number(),
      q50: z.number(),
    }),
  ),
  scatter: z.array(z.unknown()),
  trackingRun: z.string().nullable(),
  results: z.array(
    z.object({
      week: z.number().int(),
      picks: z.number().optional(),
      hitRate: num.optional(),
      predicted: num.optional(),
      entries: num.optional(),
      settled: num.optional(),
      entriesHit: num.optional(),
      expectedHits: num.optional(),
    }),
  ),
});
export const sportsLatestSchema = z.object({
  source: z.literal("dfs"),
  schemaVersion: z.literal(1),
  observedAt: time,
  season: z.number().int(),
  week: z.number().int(),
  run: z
    .object({
      runId: z.string(),
      createdAt: z.string(),
      slate: z.string(),
      maxPerTeam: z.number().nullable(),
      minUnique: z.number().nullable(),
    })
    .nullable(),
  lineups: z.array(lineup),
  board: z.array(boardRow),
  track: z.array(trackRow),
  underdog,
  issues: z.array(z.string()),
});
export const sportsHistorySchema = z.object({
  source: z.literal("dfs-history"),
  schemaVersion: z.literal(1),
  observedAt: time,
  season: z.number().int(),
  week: z.number().int(),
  players: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      position: z.string(),
      team: z.string(),
      // [season, week, DK points]
      games: z.array(z.tuple([z.number(), z.number(), z.number()])),
    }),
  ),
});
export type SportsLatest = z.infer<typeof sportsLatestSchema>;
export type SportsHistory = z.infer<typeof sportsHistorySchema>;
export type Lineup = z.infer<typeof lineup>;
export type BoardRow = z.infer<typeof boardRow>;
export type HistoryPlayer = SportsHistory["players"][number];

export const STRATEGIES: Record<string, string> = {
  A: "Mean model",
  B: "Shrunk ceiling",
  C: "Boom score",
  D: "Role-aware boom",
};

/** Exponential moving average with pandas' span convention (adjust=true). */
export function ema(values: number[], span: number): number[] {
  const alpha = 2 / (span + 1);
  let num = 0,
    den = 0;
  return values.map((v) => {
    num = v + (1 - alpha) * num;
    den = 1 + (1 - alpha) * den;
    return num / den;
  });
}

export function lineupsByStrategy(lineups: Lineup[]): [string, Lineup[]][] {
  const groups = new Map<string, Lineup[]>();
  for (const l of [...lineups].sort(
    (a, b) => a.strategy.localeCompare(b.strategy) || a.rank - b.rank,
  ))
    groups.set(l.strategy, [...(groups.get(l.strategy) ?? []), l]);
  return [...groups.entries()];
}

export type BoardFilter = {
  query: string;
  position: string;
  showExcluded: boolean;
};
export type BoardSort = keyof Pick<
  BoardRow,
  "proj" | "salary" | "value" | "boomC" | "boomD" | "ceiling"
>;
export function filterBoard(
  rows: BoardRow[],
  f: BoardFilter,
  sort: BoardSort,
): BoardRow[] {
  const q = f.query.trim().toLowerCase();
  return rows
    .filter(
      (r) =>
        (f.showExcluded || !r.excluded) &&
        (f.position === "ALL" || r.position === f.position) &&
        (!q || r.name.toLowerCase().includes(q) || r.team.toLowerCase() === q),
    )
    .sort((a, b) => (b[sort] ?? -Infinity) - (a[sort] ?? -Infinity));
}

/** Per-source track record: settled lineup count and mean projected/actual. */
export function trackSummary(rows: SportsLatest["track"]) {
  const by = new Map<string, { n: number; proj: number; actual: number }>();
  for (const r of rows) {
    if (r.status !== "settled" || r.actual === null || r.proj === null)
      continue;
    const s = by.get(r.source) ?? { n: 0, proj: 0, actual: 0 };
    s.n += 1;
    s.proj += r.proj;
    s.actual += r.actual;
    by.set(r.source, s);
  }
  return [...by.entries()]
    .map(([source, s]) => ({
      source,
      lineups: s.n,
      proj: s.proj / s.n,
      actual: s.actual / s.n,
    }))
    .sort((a, b) => b.actual - a.actual);
}

/** Search players like tickers: name prefix/substring or exact team. */
export function searchPlayers(
  players: HistoryPlayer[],
  query: string,
  limit = 8,
): HistoryPlayer[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const starts = (p: HistoryPlayer) =>
    p.name
      .toLowerCase()
      .split(" ")
      .some((w) => w.startsWith(q));
  return players
    .filter(
      (p) => p.name.toLowerCase().includes(q) || p.team.toLowerCase() === q,
    )
    .sort((a, b) => Number(starts(b)) - Number(starts(a)))
    .slice(0, limit);
}
