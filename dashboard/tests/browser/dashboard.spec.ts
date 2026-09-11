import { test, expect } from "@playwright/test";
import { readFileSync, existsSync } from "node:fs";
const captured = existsSync("private/preview.json")
  ? JSON.parse(readFileSync("private/preview.json", "utf8"))
  : null;
const empty = {
  home: {
    schemaVersion: 1,
    source: "home",
    observedAt: new Date().toISOString(),
    jobs: [],
    fa: {
      cutoff: null,
      symbols: null,
      uniqueNews: null,
      coverage: {},
      rows: [],
      evaluationStatus: "unavailable",
      labeledRows: null,
    },
    research: null,
    issues: [],
  },
};
test("private setup is explicit and all views work with captured data", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByText("Firebase connection pending")).toBeVisible();
  await page
    .getByLabel("Open local snapshot")
    .setInputFiles({
      name: "snapshot.json",
      mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(captured ?? empty)),
    });
  await expect(page.getByText("Local snapshot preview.")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Your market, in view." }),
  ).toBeVisible();
  await page.screenshot({
    path: `private/${info.project.name}-overview.png`,
    fullPage: true,
  });
  for (const name of ["Signals", "Positions", "Research", "FA"]) {
    await page
      .getByRole("navigation")
      .getByRole("button", { name, exact: true })
      .click();
    await expect(page.locator("h1")).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  }
  await page.getByLabel("Search FA symbols").fill("zzzz-no-symbol");
  await expect(page.getByText("No matching company snapshots.")).toBeVisible();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Signals", exact: true })
    .click();
  await page.getByLabel("Search signals").fill("zzzz-no-symbol");
  if (captured?.server?.signals.length)
    await expect(
      page.getByText("No signals match these filters."),
    ).toBeVisible();
  await page.getByLabel("Search signals").fill("");
  if (captured?.server?.signals.length) {
    await page
      .getByRole("button", { name: /^Inspect / })
      .first()
      .click();
    await expect(
      page.getByRole("dialog", { name: "Signal evidence" }),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
  }
  expect(errors).toEqual([]);
});
test("malformed preview is rejected without private content", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByLabel("Open local snapshot")
    .setInputFiles({
      name: "bad.json",
      mimeType: "application/json",
      buffer: Buffer.from('{"server":{"schemaVersion":2}}'),
    });
  await expect(page.getByRole("alert")).toContainText("not a valid");
  await expect(page.getByRole("navigation")).toHaveCount(0);
});
