import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests/auth-browser",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:5174" },
  webServer: {
    command: "npm run dev -- --port 5174",
    url: "http://127.0.0.1:5174",
    env: {
      VITE_FIREBASE_API_KEY: "fake-api-key",
      VITE_FIREBASE_AUTH_DOMAIN: "demo-healylabs.firebaseapp.com",
      VITE_FIREBASE_PROJECT_ID: "demo-healylabs",
      VITE_FIREBASE_APP_ID: "demo-app",
      VITE_FIREBASE_EMULATORS: "true",
    },
  },
});
