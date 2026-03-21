import { test, expect } from "@playwright/test";

test("places a valid run from an empty board", async ({ page }) => {
  await page.goto("/");

  // Add Red 10, Red 11, Red 12 via the tile picker.
  // The aria-label starts with "red N" (may include a count suffix after clicking).
  await page.getByRole("button", { name: /^red 10/i }).click();
  await page.getByRole("button", { name: /^red 11/i }).click();
  await page.getByRole("button", { name: /^red 12/i }).click();

  await page.getByRole("button", { name: "Solve" }).click();

  // Solver should place all three tiles optimally.
  await expect(page.getByText("3 tiles placed")).toBeVisible({
    timeout: 5_000,
  });
  await expect(page.getByText("Optimal")).toBeVisible();

  // At least one move instruction should appear (the "create" step).
  await expect(page.getByText("Move instructions")).toBeVisible();
});
