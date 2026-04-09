import { test, expect } from "@playwright/test";

// ---------------------------------------------------------------------------
// Mock puzzle fixture — backend NOT required; all tests use page.route()
// ---------------------------------------------------------------------------

const MOCK_PUZZLE = {
  board_sets: [
    {
      type: "run",
      tiles: [
        { color: "red", number: 5, joker: false },
        { color: "red", number: 6, joker: false },
        { color: "red", number: 7, joker: false },
      ],
    },
    {
      type: "run",
      tiles: [
        { color: "blue", number: 1, joker: false },
        { color: "blue", number: 2, joker: false },
        { color: "blue", number: 3, joker: false },
      ],
    },
  ],
  rack: [
    { color: "black", number: 10, joker: false },
    { color: "yellow", number: 8, joker: false },
  ],
  difficulty: "easy",
  tile_count: 8,
  disruption_score: 1,
  chain_depth: 1,
  is_unique: true,
  puzzle_id: "phase2-test-001",
};

// ---------------------------------------------------------------------------
// Specs
// ---------------------------------------------------------------------------

test.describe("Play page — Phase 2 tap interaction", () => {
  // Each test routes the API and loads the puzzle individually so that
  // page.route() is registered before page.goto().

  test("selecting a rack tile shows blue selection ring", async ({ page }) => {
    await page.route("**/api/puzzle", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PUZZLE),
      }),
    );
    await page.goto("/en/play");
    await page.getByRole("button", { name: /get puzzle/i }).click();
    await expect(page.locator("[data-slot-cell]").first()).toBeVisible({
      timeout: 5_000,
    });

    const rackButtons = page.locator(".play-rack-scroll button");
    await rackButtons.first().dispatchEvent("click");
    await expect(rackButtons.first()).toHaveClass(/ring-blue-500/);
  });

  test("clicking same rack tile twice deselects it", async ({ page }) => {
    await page.route("**/api/puzzle", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PUZZLE),
      }),
    );
    await page.goto("/en/play");
    await page.getByRole("button", { name: /get puzzle/i }).click();
    await expect(page.locator("[data-slot-cell]").first()).toBeVisible({
      timeout: 5_000,
    });

    const rackButtons = page.locator(".play-rack-scroll button");
    await rackButtons.first().dispatchEvent("click");
    await rackButtons.first().dispatchEvent("click");
    await expect(rackButtons.first()).not.toHaveClass(/ring-blue-500/);
  });

  test("placing a rack tile on an empty cell removes it from rack", async ({
    page,
  }) => {
    await page.route("**/api/puzzle", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PUZZLE),
      }),
    );
    await page.goto("/en/play");
    await page.getByRole("button", { name: /get puzzle/i }).click();
    await expect(page.locator("[data-slot-cell]").first()).toBeVisible({
      timeout: 5_000,
    });

    // Select first rack tile (black 10), place on empty row 2
    await page.locator(".play-rack-scroll button").first().dispatchEvent("click");
    await page.locator("[data-slot-cell][data-row='2'][data-col='0']").click();
    await expect(page.getByText("1 tile")).toBeVisible();
  });

  test("clicking a grid tile selects it (pick up)", async ({ page }) => {
    await page.route("**/api/puzzle", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PUZZLE),
      }),
    );
    await page.goto("/en/play");
    await page.getByRole("button", { name: /get puzzle/i }).click();
    await expect(page.locator("[data-slot-cell]").first()).toBeVisible({
      timeout: 5_000,
    });

    // Red 5 is at row 0, col 0
    await page.locator("[data-slot-cell][data-row='0'][data-col='0']").click();
    await expect(
      page.locator("[data-slot-cell][data-row='0'][data-col='0']"),
    ).toHaveClass(/ring-blue-500/);
  });

  test("moving a grid tile to an empty cell", async ({ page }) => {
    await page.route("**/api/puzzle", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PUZZLE),
      }),
    );
    await page.goto("/en/play");
    await page.getByRole("button", { name: /get puzzle/i }).click();
    await expect(page.locator("[data-slot-cell]").first()).toBeVisible({
      timeout: 5_000,
    });

    // Pick up red 5 from (0,0), drop on empty cell (2,0)
    await page.locator("[data-slot-cell][data-row='0'][data-col='0']").click();
    await page.locator("[data-slot-cell][data-row='2'][data-col='0']").click();
    // Original cell must now be empty
    await expect(
      page.locator("[data-slot-cell][data-row='0'][data-col='0']"),
    ).toHaveText("");
    // Target cell must be occupied
    await expect(
      page.locator("[data-slot-cell][data-row='2'][data-col='0']"),
    ).not.toHaveText("");
  });

  test("undo restores a placed rack tile back to rack", async ({ page }) => {
    await page.route("**/api/puzzle", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PUZZLE),
      }),
    );
    await page.goto("/en/play");
    await page.getByRole("button", { name: /get puzzle/i }).click();
    await expect(page.locator("[data-slot-cell]").first()).toBeVisible({
      timeout: 5_000,
    });

    // Place rack tile 0 on (2,0)
    await page.locator(".play-rack-scroll button").first().dispatchEvent("click");
    await page.locator("[data-slot-cell][data-row='2'][data-col='0']").click();
    await expect(page.getByText("1 tile")).toBeVisible();

    // Undo
    await page.getByRole("button", { name: /undo/i }).click();
    await expect(page.getByText("2 tiles")).toBeVisible();
    await expect(
      page.locator("[data-slot-cell][data-row='2'][data-col='0']"),
    ).toHaveText("");
  });

  test("return-to-rack button appears for rack-source tile and returns it", async ({
    page,
  }) => {
    await page.route("**/api/puzzle", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(MOCK_PUZZLE),
      }),
    );
    await page.goto("/en/play");
    await page.getByRole("button", { name: /get puzzle/i }).click();
    await expect(page.locator("[data-slot-cell]").first()).toBeVisible({
      timeout: 5_000,
    });

    // Place rack tile 0 on (2,0), then pick it up from the grid
    await page.locator(".play-rack-scroll button").first().dispatchEvent("click");
    await page.locator("[data-slot-cell][data-row='2'][data-col='0']").click();
    await page.locator("[data-slot-cell][data-row='2'][data-col='0']").click(); // pick up

    // Return to rack button must now be visible
    const returnBtn = page.getByRole("button", { name: /return to rack/i });
    await expect(returnBtn).toBeVisible();
    await returnBtn.click();

    // Rack back to 2 tiles, cell empty
    await expect(page.getByText("2 tiles")).toBeVisible();
    await expect(
      page.locator("[data-slot-cell][data-row='2'][data-col='0']"),
    ).toHaveText("");
  });
});
