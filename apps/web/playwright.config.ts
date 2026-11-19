import { defineConfig } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
const root = path.resolve("../..");
fs.mkdirSync(path.join(root, "artifacts/databases"), { recursive: true });
const database =
  "sqlite:///" + path.join(root, "artifacts/databases/e2e-test.db").replaceAll("\\", "/");
export default defineConfig({
  testDir: "./e2e",
  outputDir: "../../artifacts/browser",
  timeout: 180000,
  expect: { timeout: 15000 },
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:5174",
    viewport: { width: 390, height: 844 },
    trace: "retain-on-failure",
    channel: "chromium",
    launchOptions: { timeout: 120000 },
  },
  webServer: [
    {
      command: "node scripts/e2e-api.mjs",
      cwd: root,
      url: "http://127.0.0.1:8000/health/live",
      timeout: 120000,
      reuseExistingServer: false,
      env: {
        DATABASE_URL: database,
        APP_ENV: "test",
        LLM_PROVIDER: "mock",
        AUDIO_PROVIDER: "mock",
        REQUESTS_PER_MINUTE: "10000",
      },
    },
    {
      command: "node node_modules/vite/bin/vite.js --port 5174 --strictPort",
      url: "http://127.0.0.1:5174",
      timeout: 120000,
      reuseExistingServer: false,
    },
  ],
});
