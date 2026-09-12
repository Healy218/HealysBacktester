import { expect, test } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import { trainingFixture } from "../training.fixture";
const baseHome = {
  schemaVersion: 1,
  source: "home",
  observedAt: new Date().toISOString(),
  jobs: [],
  research: null,
  issues: [],
  fa: {
    cutoff: null,
    symbols: null,
    uniqueNews: null,
    coverage: {},
    rows: [],
    evaluationStatus: "unavailable",
    labeledRows: null,
  },
};
const captured = existsSync("private/training-preview.json")
  ? JSON.parse(readFileSync("private/training-preview.json", "utf8"))
  : { home: { ...baseHome, training: trainingFixture() } };
test("training generations, comparison, sources and download work without page overflow", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByLabel("Open local snapshot").setInputFiles({
    name: "training.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(captured)),
  });
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("button", { name: "Training", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Every generation, on record." }),
  ).toBeVisible();
  await page.screenshot({
    path: `private/${info.project.name}-training.png`,
    fullPage: false,
  });
  const generations = page.getByRole("navigation", {
    name: "Training generations",
  });
  for (const label of ["Compare", "V2", "V3", "V3.1", "V4", "V5", "V6"]) {
    await generations
      .getByRole("button", {
        name: new RegExp(`^${label.replace(".", "\\.")}(?:$|\\s)`),
      })
      .click();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await expect(
      page.getByRole("region", { name: "Out-of-sample comparison" }),
    ).toBeVisible();
  }
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download summary" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("v6-training-summary.md");
  await page.locator(".training-sources summary").first().click();
  await expect(page.getByText(/SHA-256 ·/).first()).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await generations.getByRole("button", { name: /^Compare$/ }).click();
  await page.screenshot({
    path: `private/${info.project.name}-training-compare.png`,
    fullPage: false,
  });
  expect(errors).toEqual([]);
});
test("terminal seed count is not completion and source HTML stays inert", async ({
  page,
}) => {
  const external: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("invalid.example")) external.push(request.url());
  });
  await page.goto("/");
  await page.getByLabel("Open local snapshot").setInputFiles({
    name: "training.json",
    mimeType: "application/json",
    buffer: Buffer.from(
      JSON.stringify({ home: { ...baseHome, training: trainingFixture() } }),
    ),
  });
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("button", { name: "Training", exact: true })
    .click();
  await expect(page.locator(".training-seeds .tag")).toHaveText("Training");
  await expect(
    page.getByText("0 seed workers at capture", { exact: false }),
  ).toBeVisible();
  await page.locator(".training-sources summary").click();
  await expect(page.locator(".training-source-text img")).toHaveCount(0);
  expect(external).toEqual([]);
});
