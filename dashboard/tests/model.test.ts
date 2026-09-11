import { expect, it } from "vitest";
import { fresh, ageSeconds, filteredSignals, serverSchema } from "../src/model";
it("rejects unknown or future freshness and preserves actual stale observations", () => {
  const now = Date.parse("2026-09-11T15:00:00Z");
  expect(fresh(null, 180, now)).toBe(false);
  expect(fresh("2026-09-11T16:00:00Z", 180, now)).toBe(false);
  expect(fresh("2026-09-11T14:59:00Z", 180, now)).toBe(true);
  expect(ageSeconds("bad", now)).toBe(null);
});
it("intersects signal filters without changing source rows", () => {
  const rows = [
    {
      id: "1",
      symbol: "PTON",
      side: "BUY PUT",
      expert: "v4",
      score: 0.6,
      status: "sent",
      candidateAt: null,
      strategy: "ma",
      source: "test",
    },
    {
      id: "2",
      symbol: "PTON",
      side: "BUY PUT",
      expert: "v5",
      score: 0.7,
      status: "pending",
      candidateAt: null,
      strategy: "ma",
      source: "test",
    },
  ];
  expect(filteredSignals(rows, "pton", "v4", "sent")).toEqual([rows[0]]);
  expect(filteredSignals(rows, "pton", "v4", "pending")).toEqual([]);
  expect(rows).toHaveLength(2);
});
it("rejects incompatible documents instead of rendering fabricated defaults", () => {
  expect(serverSchema.safeParse({ schemaVersion: 2 }).success).toBe(false);
});

it('accepts the captured server adapter document without coercing missing data', async () => {
  const { readFileSync, existsSync } = await import('node:fs');
  if (!existsSync('private/preview.json')) return;
  const raw = JSON.parse(readFileSync('private/preview.json', 'utf8'));
  if (raw.server) expect(serverSchema.safeParse(raw.server).success).toBe(true);
});
