import { expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import {
  trainingSchema,
  trainingPercent,
  reportMarkdown,
} from "../src/trainingModel";
import { homeSchema } from "../src/model";
import { trainingFixture } from "./training.fixture";
it("preserves missing metrics and zero values with fractional percent units", () => {
  const data = trainingSchema.parse(trainingFixture());
  expect(data.versions[0].folds[0].drawdown).toBeNull();
  expect(data.versions[0].folds[0].trades).toBe(0);
  expect(trainingPercent(null)).toBe("—");
  expect(trainingPercent(0)).toBe("0.0%");
  expect(trainingPercent(0.123)).toBe("+12.3%");
  const md = reportMarkdown(data.versions[0]);
  expect(md).toContain("+12.3%");
  expect(md).toContain("Marked ledger / base costs");
  expect(md).toContain("SHA-256");
  expect(md).toContain("Different windows");
});
it("rejects invalid metric values and source identities", () => {
  const data = trainingFixture();
  data.versions[0].folds[0].returnValue = Infinity;
  expect(trainingSchema.safeParse(data).success).toBe(false);
  data.versions[0].folds[0].returnValue = 0.1;
  data.versions[0].sources[0].sha256 = "bad";
  expect(trainingSchema.safeParse(data).success).toBe(false);
});
it("accepts the real collector capture when supplied, while remaining backward compatible", () => {
  if (!existsSync("private/training-preview.json")) return;
  const raw = JSON.parse(readFileSync("private/training-preview.json", "utf8"));
  const parsed = homeSchema.safeParse(raw.home);
  expect(parsed.error?.message).toBeUndefined();
  expect(parsed.success).toBe(true);
  delete raw.home.training;
  expect(homeSchema.safeParse(raw.home).success).toBe(true);
});
