import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/__tests__/setup.ts"],
    // Exclude Playwright E2E specs — they live in e2e/ and use a different runner.
    exclude: ["**/node_modules/**", "**/e2e/**"],
  },
});
