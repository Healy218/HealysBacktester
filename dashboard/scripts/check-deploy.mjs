import { loadEnv } from "vite";
const e = loadEnv("production", process.cwd(), "VITE_");
for (const k of [
  "FIREBASE_API_KEY",
  "FIREBASE_AUTH_DOMAIN",
  "FIREBASE_PROJECT_ID",
  "FIREBASE_APP_ID",
]) {
  if (!e["VITE_" + k]) throw new Error(`Configure VITE_${k} before deploying.`);
}
if (
  e.VITE_FIREBASE_EMULATORS === "true" ||
  e.VITE_FIREBASE_PROJECT_ID.startsWith("demo-")
)
  throw new Error("Production must use the intended live Firebase project.");
if (
  process.env.GCLOUD_PROJECT &&
  process.env.GCLOUD_PROJECT !== e.VITE_FIREBASE_PROJECT_ID
)
  throw new Error("Firebase deploy target does not match web configuration.");
console.log("Production config checked for " + e.VITE_FIREBASE_PROJECT_ID);
