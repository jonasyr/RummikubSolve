import { test, expect } from "@playwright/test";

test("loads an easy puzzle and solves it", async ({ page }) => {
  await page.goto("/");

  // Expand the Practice Puzzle panel by clicking its summary.
  await page.locator("summary", { hasText: "Practice Puzzle" }).click();

  // Select "Easy" difficulty (buttons are now visible inside the open panel).
  await page.getByRole("button", { name: "Easy" }).click();

  // Click "Get Puzzle" and wait for tiles to populate the rack.
  await page.getByRole("button", { name: /Get Puzzle/i }).click();
  await expect(
    page.locator("[aria-label*='Remove tile']").first(),
  ).toBeVisible({ timeout: 10_000 });

  // Solve the loaded puzzle.
  await page.getByRole("button", { name: "Solve" }).click();
  await expect(page.getByText(/tile[s]? placed/i)).toBeVisible({
    timeout: 10_000,
  });
});
