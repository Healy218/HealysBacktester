import { test, expect } from "@playwright/test";
import { initializeApp } from "firebase-admin/app";
import { getAuth } from "firebase-admin/auth";
import { getFirestore } from "firebase-admin/firestore";
process.env.FIREBASE_AUTH_EMULATOR_HOST = "127.0.0.1:9099";
process.env.FIRESTORE_EMULATOR_HOST = "127.0.0.1:8080";
const app = initializeApp({ projectId: "demo-healylabs" });
const db = getFirestore(app);
const now = new Date().toISOString();
const server = {
  schemaVersion: 1,
  source: "server",
  observedAt: now,
  market: "open",
  scanners: [],
  feeds: [],
  signals: [],
  positions: [],
  queueCounts: { sent: 7, pending: 2 },
  queueAvailable: true,
  positionsAvailable: true,
  openPositionCount: 1,
  scope: "Emulator test records",
  issues: [],
};
const home = {
  schemaVersion: 1,
  source: "home",
  observedAt: now,
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
};
test.beforeAll(async () => {
  for (const uid of ["owner-browser", "stranger-browser"]) {
    await getAuth(app).createUser({
      uid,
      email: `${uid}@example.test`,
      password: "emulator-password-only",
      emailVerified: true,
    });
  }
  await db.doc("access/owner-browser").set({ enabled: true });
  await db.doc("dashboard/server").set({ payload: JSON.stringify(server) });
  await db.doc("dashboard/home").set({ payload: JSON.stringify(home) });
});
async function login(page: any, email: string) {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("emulator-password-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}
test("approved login reads server summaries, revocation clears them, signout hides workspace", async ({
  page,
}) => {
  await login(page, "owner-browser@example.test");
  await expect(
    page
      .locator(".metric")
      .filter({ hasText: "Alerts sent" })
      .locator("strong"),
  ).toHaveText("7");
  await db.doc("access/owner-browser").set({ enabled: false });
  await page.getByLabel("Refresh data").click();
  await expect(
    page
      .locator(".metric")
      .filter({ hasText: "Alerts sent" })
      .locator("strong"),
  ).toHaveText("—");
  await page.getByLabel("Sign out").click();
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("navigation")).toHaveCount(0);
});
test("authenticated stranger cannot read private summaries", async ({
  page,
}) => {
  await login(page, "stranger-browser@example.test");
  await expect(
    page
      .locator(".metric")
      .filter({ hasText: "Alerts sent" })
      .locator("strong"),
  ).toHaveText("—");
  await page.locator("summary").click();
  await expect(
    page.getByText("Server: access denied.", { exact: false }),
  ).toBeVisible();
});
