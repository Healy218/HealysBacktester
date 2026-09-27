import { expect, it } from "vitest";
import {
  ema,
  filterBoard,
  lineupsByStrategy,
  searchPlayers,
  sportsHistorySchema,
  sportsLatestSchema,
  trackSummary,
  type BoardRow,
} from "../src/sportsModel";

const row = (o: Partial<BoardRow>): BoardRow => ({
  id: "p",
  name: "Player",
  position: "WR",
  team: "KC",
  opponent: "MIA",
  salary: 5000,
  proj: 10,
  ceiling: 12,
  boomC: 5,
  boomD: 4,
  value: 2,
  depth: "starter",
  excluded: "",
  status: null,
  method: "production_model",
  ...o,
});

it("matches pandas ewm(span, adjust=True)", () => {
  // pandas: pd.Series([10, 20, 30]).ewm(span=3).mean() -> 10, 16.667, 24.286
  const out = ema([10, 20, 30], 3);
  expect(out[0]).toBeCloseTo(10, 3);
  expect(out[1]).toBeCloseTo(16.667, 3);
  expect(out[2]).toBeCloseTo(24.286, 3);
});

it("hides depth-gate exclusions unless asked, and sorts nulls last", () => {
  const rows = [
    row({ name: "A", proj: 5, boomC: null }),
    row({ name: "B", proj: 9, excluded: "backup_qb", position: "QB" }),
    row({ name: "C", proj: 7, boomC: 3 }),
  ];
  const base = { query: "", position: "ALL", showExcluded: false };
  expect(filterBoard(rows, base, "proj").map((r) => r.name)).toEqual([
    "C",
    "A",
  ]);
  expect(
    filterBoard(rows, { ...base, showExcluded: true }, "proj").map(
      (r) => r.name,
    ),
  ).toEqual(["B", "C", "A"]);
  expect(filterBoard(rows, base, "boomC").map((r) => r.name)).toEqual([
    "C",
    "A",
  ]);
  expect(filterBoard(rows, { ...base, query: "kc" }, "proj")).toHaveLength(2);
});

it("groups lineups by strategy in rank order and summarizes settled results", () => {
  const lu = (strategy: string, rank: number) => ({
    strategy,
    rank,
    salary: 50000,
    proj: 150,
    objective: 150,
    actual: null,
    status: "pending",
    players: [],
  });
  const groups = lineupsByStrategy([lu("C", 2), lu("A", 1), lu("C", 1)]);
  expect(groups.map(([s, ls]) => [s, ls.map((l) => l.rank)])).toEqual([
    ["A", [1]],
    ["C", [1, 2]],
  ]);
  const track = [
    {
      week: 1,
      source: "stratA",
      runId: "r",
      file: "f1",
      proj: 150,
      actual: 120,
      status: "settled",
    },
    {
      week: 1,
      source: "stratA",
      runId: "r",
      file: "f2",
      proj: 150,
      actual: 140,
      status: "settled",
    },
    {
      week: 2,
      source: "stratA",
      runId: "r",
      file: "f3",
      proj: 150,
      actual: null,
      status: "pending",
    },
  ];
  expect(trackSummary(track)).toEqual([
    { source: "stratA", lineups: 2, proj: 150, actual: 130 },
  ]);
});

it("searches players like tickers, word-prefix matches first", () => {
  const p = (name: string, team: string) => ({
    id: name,
    name,
    position: "WR",
    team,
    games: [] as [number, number, number][],
  });
  const players = [
    p("Travis Kelce", "KC"),
    p("Kelcey Other", "NYJ"),
    p("Rashee Rice", "KC"),
  ];
  expect(searchPlayers(players, "kel").map((x) => x.name)).toEqual([
    "Travis Kelce",
    "Kelcey Other",
  ]);
  expect(searchPlayers(players, "kc")).toHaveLength(2);
  expect(searchPlayers(players, " ")).toEqual([]);
});

it("validates the published document shapes", () => {
  const latest = {
    source: "dfs",
    schemaVersion: 1,
    observedAt: "2026-09-27T03:40:00+00:00",
    season: 2026,
    week: 3,
    run: null,
    lineups: [],
    board: [row({})],
    track: [],
    underdog: {
      tiles: {},
      frontier: [],
      td_gaps: [],
      edges: [],
      scatter: [],
      trackingRun: null,
      results: [{ week: 1, picks: 425, hitRate: 0.485, predicted: 0.551 }],
    },
    issues: [],
  };
  expect(sportsLatestSchema.parse(latest).week).toBe(3);
  expect(() =>
    sportsLatestSchema.parse({ ...latest, source: "home" }),
  ).toThrow();
  const history = {
    source: "dfs-history",
    schemaVersion: 1,
    observedAt: "2026-09-27T03:40:00+00:00",
    season: 2026,
    week: 3,
    players: [
      {
        id: "x",
        name: "X",
        position: "QB",
        team: "KC",
        games: [[2026, 1, 22.7]],
      },
    ],
  };
  expect(sportsHistorySchema.parse(history).players[0].games[0][2]).toBe(22.7);
});
