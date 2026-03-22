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

test("shows error banner when puzzle generation fails (503)", async ({
  page,
}) => {
  // Intercept the /api/puzzle request and return a 503 error.
  await page.route("**/api/puzzle", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Could not generate a puzzle — please try again." }),
    }),
  );

  await page.goto("/");
  await page.locator("summary", { hasText: "Practice Puzzle" }).click();
  await page.getByRole("button", { name: /Get Puzzle/i }).click();

  // An error message should appear in the UI.
  await expect(
    page.getByText(/could not generate a puzzle/i),
  ).toBeVisible({ timeout: 5_000 });

  // The "Get Puzzle" button should be re-enabled after the error.
  await expect(
    page.getByRole("button", { name: /Get Puzzle/i }),
  ).toBeEnabled();
});
