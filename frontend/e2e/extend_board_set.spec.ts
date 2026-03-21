import { test, expect } from "@playwright/test";

test("solver extends an existing board run with a rack tile", async ({
  page,
}) => {
  // Arrange — add a board run [red 4, 5, 6]
  await page.goto("/");

  await page.getByRole("button", { name: /add set/i }).click();
  await page.getByRole("button", { name: /^red 4/i }).click();
  await page.getByRole("button", { name: /^red 5/i }).click();
  await page.getByRole("button", { name: /^red 6/i }).click();
  await page.getByRole("button", { name: /add to board/i }).click();

  // Add red 7 to the rack
  await page.getByRole("button", { name: /^red 7/i }).click();

  // Act
  await page.getByRole("button", { name: "Solve" }).click();

  // Assert — an extend move referencing set 1 is shown
  await expect(page.getByText(/extend/i)).toBeVisible({ timeout: 5_000 });
  await expect(page.getByText(/set 1/i)).toBeVisible();
});
