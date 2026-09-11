import { readFileSync } from "node:fs";
import { afterAll, beforeAll, it } from "vitest";
import {
  initializeTestEnvironment,
  assertFails,
  assertSucceeds,
  type RulesTestEnvironment,
} from "@firebase/rules-unit-testing";
import { doc, getDoc, setDoc, collection, getDocs } from "firebase/firestore";
let env: RulesTestEnvironment;
beforeAll(async () => {
  env = await initializeTestEnvironment({
    projectId: "demo-healylabs",
    firestore: {
      host: "127.0.0.1",
      port: 8080,
      rules: readFileSync("firestore.rules", "utf8"),
    },
  });
  await env.withSecurityRulesDisabled(async (c) => {
    await setDoc(doc(c.firestore(), "access/owner"), { enabled: true });
    await setDoc(doc(c.firestore(), "dashboard/server"), {
      payload: "private",
    });
    await setDoc(doc(c.firestore(), "dashboard/home"), { payload: "private" });
  });
});
afterAll(async () => {
  await env?.cleanup();
});
it("allows only an approved verified user to read the two summaries", async () => {
  const db = env
    .authenticatedContext("owner", { email_verified: true })
    .firestore();
  await assertSucceeds(getDoc(doc(db, "dashboard/server")));
  await assertSucceeds(getDoc(doc(db, "dashboard/home")));
  await assertFails(getDocs(collection(db, "dashboard")));
});
it("denies signed-out, unapproved and unverified users", async () => {
  for (const db of [
    env.unauthenticatedContext().firestore(),
    env.authenticatedContext("stranger", { email_verified: true }).firestore(),
    env.authenticatedContext("owner", { email_verified: false }).firestore(),
  ])
    await assertFails(getDoc(doc(db, "dashboard/server")));
});
it("denies all client writes including self-granting access", async () => {
  const db = env
    .authenticatedContext("owner", { email_verified: true })
    .firestore();
  await assertFails(
    setDoc(doc(db, "dashboard/server"), { payload: "tampered" }),
  );
  await assertFails(setDoc(doc(db, "access/owner"), { enabled: true }));
  await assertFails(getDoc(doc(db, "access/owner")));
});
it("revocation takes effect on the next server read", async () => {
  await env.withSecurityRulesDisabled(async (c) => {
    await setDoc(doc(c.firestore(), "access/revoked"), { enabled: false });
  });
  await assertFails(
    getDoc(
      doc(
        env
          .authenticatedContext("revoked", { email_verified: true })
          .firestore(),
        "dashboard/server",
      ),
    ),
  );
});
