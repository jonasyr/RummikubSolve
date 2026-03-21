import { test, expect } from "@playwright/test";

test("solver extends an existing board run with a rack tile", async ({
  page,
}) => {
  // Arrange — add a board run [red 4, 5, 6]
  await page.goto("/");

  await page.getByRole("button", { name: /add set/i }).click();

  // Scope tile clicks to the board section builder (avoids ambiguity with the
  // always-visible rack TileGridPicker which has the same tile buttons).
  const boardSection = page.locator("section").filter({ hasText: /Board Sets/i });
  await boardSection.getByRole("button", { name: /^red 4/i }).click();
  await boardSection.getByRole("button", { name: /^red 5/i }).click();
  await boardSection.getByRole("button", { name: /^red 6/i }).click();
  await page.getByRole("button", { name: /add to board/i }).click();

  // Board builder is now closed — only the rack TileGridPicker is visible,
  // so a page-level locator is unambiguous.
  await page.getByRole("button", { name: /^red 7/i }).click();

  // Act
  await page.getByRole("button", { name: "Solve" }).click();

  // Assert — solver places 1 tile and describes the extend move
  await expect(page.getByText("1 tile placed")).toBeVisible({ timeout: 8_000 });
  await expect(page.getByText(/Add Red 7 to set 1/i)).toBeVisible();
});
