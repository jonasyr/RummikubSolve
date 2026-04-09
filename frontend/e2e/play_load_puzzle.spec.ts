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
  puzzle_id: "phase1-test-001",
};

// ---------------------------------------------------------------------------
// Specs
// ---------------------------------------------------------------------------

test.describe("Play page — Phase 1 layout", () => {
  test("happy path: shows load prompt before any puzzle is loaded", async ({
    page,
  }) => {
    await page.goto("/en/play");
    await expect(page.getByText("Load a puzzle to start playing")).toBeVisible();
    // No grid cells rendered yet
    expect(await page.locator("[data-slot-cell]").count()).toBe(0);
  });

  test("loads a puzzle via mocked API and renders grid cells with tile content", async ({
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
    await page.getByRole("button", { name: /easy/i }).click();
    await page.getByRole("button", { name: /get puzzle/i }).click();

    // At least one occupied grid cell should appear
    await expect(page.locator("[data-slot-cell]").first()).toBeVisible({
      timeout: 5_000,
    });
    // Rack counter shows 2 tiles
    await expect(page.getByText("2 tiles")).toBeVisible();
  });

  test("shows all four control buttons", async ({ page }) => {
    await page.goto("/en/play");
    await expect(page.getByRole("button", { name: /undo/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /redo/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /commit/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /revert/i })).toBeVisible();
  });

  test("control buttons meet 44 px minimum touch target height", async ({
    page,
  }) => {
    await page.goto("/en/play");
    const box = await page.getByRole("button", { name: /undo/i }).boundingBox();
    expect(box?.height).toBeGreaterThanOrEqual(44);
  });

  test("board region has play-surface class after puzzle loads", async ({
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
    await expect(page.locator(".play-surface")).toBeVisible();
  });
});
