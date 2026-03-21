import { test, expect } from "@playwright/test";

test("adds a board set and sees it rendered in the board section", async ({
  page,
}) => {
  // Arrange
  await page.goto("/");

  // Act — open the set builder
  await page.getByRole("button", { name: /add set/i }).click();

  // Scope tile clicks to the board section builder (avoids ambiguity with the
  // always-visible rack TileGridPicker which has the same tile buttons).
  const boardSection = page.locator("section").filter({ hasText: /Board Sets/i });
  await boardSection.getByRole("button", { name: /^red 4/i }).click();
  await boardSection.getByRole("button", { name: /^red 5/i }).click();
  await boardSection.getByRole("button", { name: /^red 6/i }).click();

  // Confirm the set
  await page.getByRole("button", { name: /add to board/i }).click();

  // Assert — board section now shows the lowercase "run" type label on the set row
  // (distinct from the "Run" heading in the RulesPanel).
  await expect(boardSection.getByText("run", { exact: true })).toBeVisible();
  // The three tiles should be listed inside the board section
  await expect(boardSection.getByText("4")).toBeVisible();
  await expect(boardSection.getByText("5")).toBeVisible();
  await expect(boardSection.getByText("6")).toBeVisible();
});
