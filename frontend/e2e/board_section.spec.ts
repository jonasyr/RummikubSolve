import { test, expect } from "@playwright/test";

test("adds a board set and sees it rendered in the board section", async ({
  page,
}) => {
  // Arrange
  await page.goto("/");

  // Act — open the set builder and pick three consecutive tiles
  await page.getByRole("button", { name: /add set/i }).click();
  await page.getByRole("button", { name: /^red 4/i }).click();
  await page.getByRole("button", { name: /^red 5/i }).click();
  await page.getByRole("button", { name: /^red 6/i }).click();

  // Confirm the set
  await page.getByRole("button", { name: /add to board/i }).click();

  // Assert — board section now shows a set with the "Run" type label
  await expect(page.getByText(/run/i)).toBeVisible();
  // The three tiles should be listed
  await expect(page.getByText("4")).toBeVisible();
  await expect(page.getByText("5")).toBeVisible();
  await expect(page.getByText("6")).toBeVisible();
});
