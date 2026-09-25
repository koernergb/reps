import { defineConfig } from "@playwright/test";

// Runs against an already-running stack (make dev + make sandbox-build):
//   E2E_BASE_URL=http://127.0.0.1:3000 pnpm --filter @reps/web e2e
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:3000",
    channel: process.env.E2E_CHANNEL ?? "chrome",
    headless: true,
    viewport: { width: 1440, height: 900 },
    screenshot: "only-on-failure",
  },
});
