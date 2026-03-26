import { test, expect } from "@playwright/test";
// eslint-disable-next-line @typescript-eslint/no-require-imports
const { version } = require("../package.json") as { version: string };

test.describe("PWA / iOS Home Screen", () => {
  test("apple-touch-icon is served as a PNG", async ({ request }) => {
    const response = await request.get("/apple-touch-icon.png");
    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toContain("image/png");
  });

  test("HTML head has apple-touch-icon link pointing to /apple-touch-icon.png", async ({
    page,
  }) => {
    await page.goto("/");
    const link = page.locator('link[rel="apple-touch-icon"]');
    await expect(link).toHaveCount(1);
    await expect(link).toHaveAttribute("href", "/apple-touch-icon.png");
  });

  test('HTML head has apple-mobile-web-app-title set to "RummiSolve"', async ({
    page,
  }) => {
    await page.goto("/");
    const meta = page.locator('meta[name="apple-mobile-web-app-title"]');
    await expect(meta).toHaveCount(1);
    await expect(meta).toHaveAttribute("content", "RummiSolve");
  });

  test("version footer is visible and matches package.json version", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page.getByRole("contentinfo")).toContainText(`v${version}`);
  });
});
