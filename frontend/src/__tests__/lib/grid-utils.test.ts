import { describe, it, expect } from "vitest";
import {
  puzzleToGrid,
  detectSets,
  checkSolved,
  validateTileConservation,
  insertTileIntoRow,
  compactGrid,
} from "../../lib/grid-utils";
import {
  cellKey,
  GRID_MIN_ROWS,
  GRID_MAX_ROWS,
  GRID_WORKSPACE_ROWS,
  GRID_COLS,
} from "../../types/play";
import type { PlacedTile, DetectedSet } from "../../types/play";
import type { PuzzleResponse, TileInput } from "../../types/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const redTile = (n: number): TileInput => ({ color: "red", number: n, joker: false });
const blueTile = (n: number): TileInput => ({ color: "blue", number: n, joker: false });

const makePuzzle = (
  boardSets: { tiles: TileInput[] }[],
  rack: TileInput[] = [],
): PuzzleResponse => ({
  board_sets: boardSets.map((s) => ({ type: "run", tiles: s.tiles })),
  rack,
  difficulty: "easy",
  tile_count: 0,
  disruption_score: 0,
  chain_depth: 0,
  is_unique: false,
  puzzle_id: "",
});

const boardPlaced = (tile: TileInput): PlacedTile => ({ tile, source: "board" });
const rackPlaced = (tile: TileInput): PlacedTile => ({ tile, source: "rack" });

const validSetResult: DetectedSet["validation"] = { isValid: true, type: "run" };

// ---------------------------------------------------------------------------
// puzzleToGrid
// ---------------------------------------------------------------------------

describe("puzzleToGrid", () => {
  it("happy path: maps single board set tiles to row 0", () => {
    const puzzle = makePuzzle([{ tiles: [redTile(5), redTile(6), redTile(7)] }]);
    const { grid } = puzzleToGrid(puzzle);
    expect(grid.get(cellKey(0, 0))?.tile.number).toBe(5);
    expect(grid.get(cellKey(0, 1))?.tile.number).toBe(6);
    expect(grid.get(cellKey(0, 2))?.tile.number).toBe(7);
  });

  it("maps multiple board sets to consecutive rows", () => {
    const puzzle = makePuzzle([
      { tiles: [redTile(1), redTile(2), redTile(3)] },
      { tiles: [blueTile(4), blueTile(5), blueTile(6)] },
    ]);
    const { grid } = puzzleToGrid(puzzle);
    expect(grid.get(cellKey(0, 0))?.tile.color).toBe("red");
    expect(grid.get(cellKey(1, 0))?.tile.color).toBe("blue");
  });

  it("all board tiles have source 'board'", () => {
    const puzzle = makePuzzle([{ tiles: [redTile(5), redTile(6), redTile(7)] }]);
    const { grid } = puzzleToGrid(puzzle);
    for (const placed of grid.values()) {
      expect(placed.source).toBe("board");
    }
  });

  it("rack tiles are returned unchanged in the rack array", () => {
    const rack = [redTile(8), blueTile(9)];
    const puzzle = makePuzzle([], rack);
    const result = puzzleToGrid(puzzle);
    expect(result.rack).toEqual(rack);
    expect(result.rack).not.toBe(rack); // new array (spread)
  });

  it("workspace rows are appended below content rows", () => {
    const puzzle = makePuzzle([{ tiles: [redTile(1), redTile(2), redTile(3)] }]);
    const { rows } = puzzleToGrid(puzzle);
    // 1 board set + 3 workspace rows = 4, but min is 6
    expect(rows).toBe(GRID_MIN_ROWS);
  });

  it("row count respects GRID_MIN_ROWS when puzzle is small", () => {
    const { rows } = puzzleToGrid(makePuzzle([]));
    expect(rows).toBe(GRID_MIN_ROWS);
  });

  it("row count is capped at GRID_MAX_ROWS for very large puzzles", () => {
    // Create a puzzle with GRID_MAX_ROWS many sets
    const sets = Array.from({ length: GRID_MAX_ROWS + 5 }, () => ({
      tiles: [redTile(1), redTile(2), redTile(3)],
    }));
    const { rows } = puzzleToGrid(makePuzzle(sets));
    expect(rows).toBe(GRID_MAX_ROWS);
  });

  it("cellKey format is 'row:col'", () => {
    expect(cellKey(3, 7)).toBe("3:7");
    expect(cellKey(0, 0)).toBe("0:0");
    expect(cellKey(23, 15)).toBe("23:15");
  });
});

// ---------------------------------------------------------------------------
// detectSets
// ---------------------------------------------------------------------------

describe("detectSets", () => {
  it("happy path: finds one contiguous set in a row", () => {
    const grid = new Map([
      [cellKey(0, 0), boardPlaced(redTile(5))],
      [cellKey(0, 1), boardPlaced(redTile(6))],
      [cellKey(0, 2), boardPlaced(redTile(7))],
    ]);
    const sets = detectSets(grid, 1, GRID_COLS);
    expect(sets).toHaveLength(1);
    expect(sets[0].row).toBe(0);
    expect(sets[0].startCol).toBe(0);
    expect(sets[0].tiles).toHaveLength(3);
  });

  it("splits at empty-cell gap into two separate sets", () => {
    const grid = new Map([
      [cellKey(0, 0), boardPlaced(redTile(1))],
      [cellKey(0, 1), boardPlaced(redTile(2))],
      [cellKey(0, 3), boardPlaced(redTile(4))], // gap at col 2
      [cellKey(0, 4), boardPlaced(redTile(5))],
      [cellKey(0, 5), boardPlaced(redTile(6))],
    ]);
    const sets = detectSets(grid, 1, GRID_COLS);
    expect(sets).toHaveLength(2);
    expect(sets[0].startCol).toBe(0);
    expect(sets[0].tiles).toHaveLength(2);
    expect(sets[1].startCol).toBe(3);
    expect(sets[1].tiles).toHaveLength(3);
  });

  it("empty row produces no sets", () => {
    const sets = detectSets(new Map(), 3, GRID_COLS);
    expect(sets).toHaveLength(0);
  });

  it("tiles in two rows are detected independently", () => {
    const grid = new Map([
      [cellKey(0, 0), boardPlaced(redTile(1))],
      [cellKey(0, 1), boardPlaced(redTile(2))],
      [cellKey(0, 2), boardPlaced(redTile(3))],
      [cellKey(1, 0), boardPlaced(blueTile(4))],
      [cellKey(1, 1), boardPlaced(blueTile(5))],
      [cellKey(1, 2), boardPlaced(blueTile(6))],
    ]);
    const sets = detectSets(grid, 2, GRID_COLS);
    expect(sets).toHaveLength(2);
    expect(sets[0].row).toBe(0);
    expect(sets[1].row).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// checkSolved
// ---------------------------------------------------------------------------

describe("checkSolved", () => {
  it("happy path: empty rack + all valid sets + ≥3 tiles each → true", () => {
    const grid = new Map([
      [cellKey(0, 0), boardPlaced(redTile(5))],
      [cellKey(0, 1), boardPlaced(redTile(6))],
      [cellKey(0, 2), boardPlaced(redTile(7))],
    ]);
    const sets = detectSets(grid, 1, GRID_COLS);
    expect(checkSolved(grid, [], sets)).toBe(true);
  });

  it("returns false when rack is not empty", () => {
    const grid = new Map([
      [cellKey(0, 0), boardPlaced(redTile(5))],
      [cellKey(0, 1), boardPlaced(redTile(6))],
      [cellKey(0, 2), boardPlaced(redTile(7))],
    ]);
    const sets = detectSets(grid, 1, GRID_COLS);
    expect(checkSolved(grid, [redTile(8)], sets)).toBe(false);
  });

  it("returns false when a set is invalid", () => {
    // Two tiles with same color but non-consecutive → invalid run
    const grid = new Map([
      [cellKey(0, 0), boardPlaced(redTile(1))],
      [cellKey(0, 1), boardPlaced(redTile(2))],
      [cellKey(0, 2), boardPlaced(blueTile(3))], // color break
    ]);
    const sets = detectSets(grid, 1, GRID_COLS);
    expect(checkSolved(grid, [], sets)).toBe(false);
  });

  it("returns false when a set has fewer than 3 tiles", () => {
    const grid = new Map([
      [cellKey(0, 0), boardPlaced(redTile(5))],
      [cellKey(0, 1), boardPlaced(redTile(6))],
    ]);
    const sets = detectSets(grid, 1, GRID_COLS);
    expect(checkSolved(grid, [], sets)).toBe(false);
  });

  it("returns false when there are no detected sets", () => {
    expect(checkSolved(new Map(), [], [])).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// validateTileConservation
// ---------------------------------------------------------------------------

describe("validateTileConservation", () => {
  it("happy path: grid + rack contain exactly the puzzle tiles", () => {
    const puzzle = makePuzzle(
      [{ tiles: [redTile(1), redTile(2)] }],
      [redTile(3)],
    );
    const { grid, rack } = puzzleToGrid(puzzle);
    expect(validateTileConservation(puzzle, grid, rack)).toBe(true);
  });

  it("returns false when a tile is missing", () => {
    const puzzle = makePuzzle([{ tiles: [redTile(1), redTile(2)] }], [redTile(3)]);
    const { grid } = puzzleToGrid(puzzle);
    expect(validateTileConservation(puzzle, grid, [])).toBe(false);
  });

  it("returns false when an extra tile is present", () => {
    const puzzle = makePuzzle([{ tiles: [redTile(1)] }], []);
    const { grid, rack } = puzzleToGrid(puzzle);
    rack.push(redTile(99)); // extra tile
    expect(validateTileConservation(puzzle, grid, rack)).toBe(false);
  });

  it("correctly handles duplicate tiles (two copies of same tile)", () => {
    // Puzzle has two red 5s: one on board, one in rack
    const puzzle = makePuzzle([{ tiles: [redTile(5)] }], [redTile(5)]);
    const { grid, rack } = puzzleToGrid(puzzle);
    expect(validateTileConservation(puzzle, grid, rack)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// insertTileIntoRow — Phase 5 scaffold
// ---------------------------------------------------------------------------

describe("insertTileIntoRow — Phase 5", () => {
  it.todo("shifts tiles rightward from insertCol");
  it.todo("returns unchanged grid when row is full at the right edge");
});

// ---------------------------------------------------------------------------
// compactGrid — Phase 5 scaffold
// ---------------------------------------------------------------------------

describe("compactGrid — Phase 5", () => {
  it.todo("removes empty rows");
  it.todo("slides sets left (removes leading column gaps)");
  it.todo("preserves gaps between sets in the same row");
  it.todo("adds workspace rows below content after compact");
  it.todo("caps final row count at GRID_MAX_ROWS");
});
