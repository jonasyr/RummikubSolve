import { test, expect } from "@playwright/test";

test("first-turn: places tiles when value meets the threshold", async ({
  page,
}) => {
  await page.goto("/");

  // Enable the first-turn rule.
  await page.getByRole("checkbox", { name: /first turn/i }).check();

  // Red 10 + 11 + 12 = 33 ≥ 30 → should be placed.
  await page.getByRole("button", { name: /^red 10/i }).click();
  await page.getByRole("button", { name: /^red 11/i }).click();
  await page.getByRole("button", { name: /^red 12/i }).click();

  await page.getByRole("button", { name: "Solve" }).click();

  await expect(page.getByText("3 tiles placed")).toBeVisible({
    timeout: 5_000,
  });
});

test("first-turn: no play when rack value is below the threshold", async ({
  page,
}) => {
  await page.goto("/");

  await page.getByRole("checkbox", { name: /first turn/i }).check();

  // Red 4 + 5 + 6 = 15 < 30 → cannot meet the meld threshold.
  await page.getByRole("button", { name: /^red 4/i }).click();
  await page.getByRole("button", { name: /^red 5/i }).click();
  await page.getByRole("button", { name: /^red 6/i }).click();

  await page.getByRole("button", { name: "Solve" }).click();

  await expect(page.getByText(/below the.*threshold/i)).toBeVisible({
    timeout: 5_000,
  });
});
