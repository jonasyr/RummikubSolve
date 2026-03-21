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

  // Add red 7 to the rack via the rack section picker
  const rackSection = page.locator("section").filter({ hasText: /Your Rack/i });
  await rackSection.getByRole("button", { name: /^red 7/i }).click();

  // Act
  await page.getByRole("button", { name: "Solve" }).click();

  // Assert — an extend move referencing set 1 is shown
  await expect(page.getByText(/extend/i)).toBeVisible({ timeout: 5_000 });
  await expect(page.getByText(/set 1/i)).toBeVisible();
});
