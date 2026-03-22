import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  // Fail the CI build if test.only is accidentally left in source.
  forbidOnly: !!process.env.CI,
  // Retry once on CI to handle transient flakiness; no retries locally.
  retries: process.env.CI ? 1 : 0,
  // Single worker in CI to keep resource usage predictable.
  workers: process.env.CI ? 1 : undefined,
  reporter: [["html", { open: "never" }]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000",
    // Capture a trace on the first retry so failures are diagnosable.
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile-chrome",
      use: { ...devices["Pixel 5"] },    // 393×851 — mid-range Android phone
    },
    {
      name: "mobile-safari",
      // Use Chromium engine with iPhone SE viewport/UA — WebKit is not installed
      // in CI (only chromium is in the install step). Chromium with mobile
      // emulation still validates layout, touch targets, and mobile UA behaviour.
      use: { ...devices["iPhone SE"], browserName: "chromium" },
    },
  ],
  // Playwright will start the Next.js dev server automatically.
  // The backend must already be running on NEXT_PUBLIC_API_URL (default :8000).
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    // Re-use an already-running server in local development to save time.
    reuseExistingServer: !process.env.CI,
    env: {
      NEXT_PUBLIC_API_URL:
        process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
    },
  },
});
