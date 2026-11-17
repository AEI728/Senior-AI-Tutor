import { defineConfig } from "@playwright/test";
import path from "node:path";
export default defineConfig({
  testDir: "./live-e2e",
  outputDir: "live-test-results",
  timeout: 180000,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:5173",
    viewport: { width: 390, height: 844 },
    channel: "chromium",
    trace: "retain-on-failure",
    launchOptions: {
      timeout: 120000,
      args: [
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
        "--use-file-for-fake-audio-capture=" +
          path.resolve("../../docs/evals/fixtures/user-command.wav") +
          "%noloop",
      ],
    },
  },
  expect: { timeout: 45000 },
  reporter: "list",
});
