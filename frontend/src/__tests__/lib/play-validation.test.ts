import { describe, it, expect } from "vitest";
import { validateTileGroup } from "../../lib/play-validation";
import type { PlacedTile } from "../../types/play";
import type { TileInput } from "../../types/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const placed = (tile: TileInput): PlacedTile => ({ tile, source: "board" });

const red = (n: number): PlacedTile => placed({ color: "red", number: n, joker: false });
const blue = (n: number): PlacedTile => placed({ color: "blue", number: n, joker: false });
const black = (n: number): PlacedTile => placed({ color: "black", number: n, joker: false });
const yellow = (n: number): PlacedTile => placed({ color: "yellow", number: n, joker: false });
const joker = (): PlacedTile => placed({ joker: true });

// ---------------------------------------------------------------------------
// Runs
// ---------------------------------------------------------------------------

describe("validateTileGroup — runs", () => {
  it("happy path: 3 same-color consecutive tiles → valid run", () => {
    const result = validateTileGroup([red(5), red(6), red(7)]);
    expect(result.isValid).toBe(true);
    expect(result.type).toBe("run");
  });

  it("run with joker filling a single gap → valid", () => {
    const result = validateTileGroup([red(5), joker(), red(7)]);
    expect(result.isValid).toBe(true);
    expect(result.type).toBe("run");
  });

  it("run of 13 tiles (max valid length) → valid", () => {
    const tiles = Array.from({ length: 13 }, (_, i) => red(i + 1));
    const result = validateTileGroup(tiles);
    expect(result.isValid).toBe(true);
  });

  it("mixed colors → invalid with runMixedColors reason", () => {
    const result = validateTileGroup([red(5), blue(6), red(7)]);
    expect(result.isValid).toBe(false);
    expect(result.reason).toBe("play.validation.runMixedColors");
  });

  it("duplicate numbers in same color → invalid with runDuplicateNumbers reason", () => {
    const result = validateTileGroup([red(5), red(5), red(6)]);
    expect(result.isValid).toBe(false);
    expect(result.reason).toBe("play.validation.runDuplicateNumbers");
  });

  it("gap too large for available jokers → invalid with runGapsTooLarge reason", () => {
    // Gap of 2 between 5 and 8, only 1 joker
    const result = validateTileGroup([red(5), joker(), red(8)]);
    expect(result.isValid).toBe(false);
    expect(result.reason).toBe("play.validation.runGapsTooLarge");
  });

  it("14 tiles → invalid with runTooLong reason", () => {
    const tiles = Array.from({ length: 14 }, (_, i) => red(i + 1));
    const result = validateTileGroup(tiles);
    expect(result.isValid).toBe(false);
    expect(result.reason).toBe("play.validation.runTooLong");
  });

  it("tiles in wrong order (6, 8, 7) → invalid with runNotOrdered reason", () => {
    const result = validateTileGroup([red(6), red(8), red(7)]);
    expect(result.isValid).toBe(false);
    expect(result.reason).toBe("play.validation.runNotOrdered");
  });
});

// ---------------------------------------------------------------------------
// Groups
// ---------------------------------------------------------------------------

describe("validateTileGroup — groups", () => {
  it("happy path: 3 same-number different-color tiles → valid group", () => {
    const result = validateTileGroup([red(8), blue(8), black(8)]);
    expect(result.isValid).toBe(true);
    expect(result.type).toBe("group");
  });

  it("group of 4 tiles → valid", () => {
    const result = validateTileGroup([red(8), blue(8), black(8), yellow(8)]);
    expect(result.isValid).toBe(true);
    expect(result.type).toBe("group");
  });

  it("group with joker replacing one color → valid", () => {
    const result = validateTileGroup([red(8), blue(8), joker()]);
    expect(result.isValid).toBe(true);
    expect(result.type).toBe("group");
  });

  it("duplicate color in group → invalid with groupDuplicateColors reason", () => {
    const result = validateTileGroup([red(8), red(8), blue(8)]);
    expect(result.isValid).toBe(false);
    expect(result.reason).toBe("play.validation.groupDuplicateColors");
  });

  it("mixed numbers AND mixed colors → invalid (heuristic returns run reason)", () => {
    // [red(8), blue(9), black(8)] fails both run (mixed colors) and group
    // (mixed numbers). Since numbers aren't all equal the heuristic treats
    // this as a run attempt and returns the run reason.
    const result = validateTileGroup([red(8), blue(9), black(8)]);
    expect(result.isValid).toBe(false);
    expect(result.type).toBeNull();
    expect(result.reason).toBe("play.validation.runMixedColors");
  });

  it("5 tiles → invalid with groupTooLarge reason", () => {
    const result = validateTileGroup([
      red(8), blue(8), black(8), yellow(8), joker(),
    ]);
    expect(result.isValid).toBe(false);
    expect(result.reason).toBe("play.validation.groupTooLarge");
  });
});

// ---------------------------------------------------------------------------
// Incomplete (fewer than 3 tiles)
// ---------------------------------------------------------------------------

describe("validateTileGroup — incomplete", () => {
  it("2 tiles → isValid false, type null, NO reason property", () => {
    const result = validateTileGroup([red(5), red(6)]);
    expect(result.isValid).toBe(false);
    expect(result.type).toBeNull();
    expect(result.reason).toBeUndefined();
  });

  it("1 tile → isValid false, type null, NO reason property", () => {
    const result = validateTileGroup([red(5)]);
    expect(result.isValid).toBe(false);
    expect(result.type).toBeNull();
    expect(result.reason).toBeUndefined();
  });

  it("0 tiles → isValid false, type null, NO reason property", () => {
    const result = validateTileGroup([]);
    expect(result.isValid).toBe(false);
    expect(result.type).toBeNull();
    expect(result.reason).toBeUndefined();
  });
});
