import { test, expect } from "@playwright/test";

test("loads an easy puzzle and solves it", async ({ page }) => {
  await page.goto("/en/");

  // Expand the Practice Puzzle panel.
  await page.getByRole("group").filter({ hasText: "Practice Puzzle" }).click();
  // Fallback: click the summary element directly.
  await page.locator("details summary").filter({ hasText: "Practice Puzzle" }).click();

  // Select "Easy" difficulty.
  await page.getByRole("button", { name: "Easy" }).click();

  // Click "Get Puzzle".
  await page.getByRole("button", { name: /Get Puzzle/i }).click();

  // Wait for the puzzle to load — rack should have at least 1 tile visible.
  await expect(page.locator("[data-testid='rack-tile'], .rack-tile, [aria-label*='Remove tile']").first()).toBeVisible({
    timeout: 10_000,
  });

  // Click Solve.
  await page.getByRole("button", { name: "Solve" }).click();

  // Solution summary should appear.
  await expect(page.getByText(/tile[s]? placed/i)).toBeVisible({ timeout: 10_000 });
});
