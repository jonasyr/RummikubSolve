import type { TileInput, PuzzleResponse } from "../types/api";
import {
  cellKey,
  GRID_COLS,
  GRID_MIN_ROWS,
  GRID_MAX_ROWS,
  GRID_WORKSPACE_ROWS,
} from "../types/play";
import type { CellKey, PlacedTile, DetectedSet } from "../types/play";
import { validateTileGroup } from "./play-validation";

// ── Puzzle → Grid ─────────────────────────────────────────────────────────────

export function puzzleToGrid(puzzle: PuzzleResponse): {
  grid: Map<CellKey, PlacedTile>;
  rack: TileInput[];
  rows: number;
} {
  const grid = new Map<CellKey, PlacedTile>();

  for (let rowIdx = 0; rowIdx < puzzle.board_sets.length; rowIdx++) {
    const set = puzzle.board_sets[rowIdx];
    for (let colIdx = 0; colIdx < set.tiles.length; colIdx++) {
      grid.set(cellKey(rowIdx, colIdx), {
        tile: set.tiles[colIdx],
        source: "board",
      });
    }
  }

  const rows = Math.max(
    GRID_MIN_ROWS,
    Math.min(puzzle.board_sets.length + GRID_WORKSPACE_ROWS, GRID_MAX_ROWS),
  );

  return { grid, rack: [...puzzle.rack], rows };
}

// ── Set detection ─────────────────────────────────────────────────────────────

export function detectSets(
  grid: Map<CellKey, PlacedTile>,
  rows: number,
  cols: number,
): DetectedSet[] {
  const sets: DetectedSet[] = [];

  for (let row = 0; row < rows; row++) {
    let current: PlacedTile[] = [];
    let startCol = 0;

    for (let col = 0; col <= cols; col++) {
      const tile = grid.get(cellKey(row, col));

      if (tile) {
        if (current.length === 0) startCol = col;
        current.push(tile);
      } else if (current.length > 0) {
        sets.push({
          row,
          startCol,
          tiles: [...current],
          validation: validateTileGroup(current),
        });
        current = [];
      }
    }
  }

  return sets;
}

// ── Solved check ──────────────────────────────────────────────────────────────

export function checkSolved(
  grid: Map<CellKey, PlacedTile>,
  rack: TileInput[],
  detectedSets: DetectedSet[],
): boolean {
  // Rack must be empty
  if (rack.length > 0) return false;

  // Must have at least one set
  if (detectedSets.length === 0) return false;

  // Every detected set must be valid with ≥3 tiles
  for (const ds of detectedSets) {
    if (ds.tiles.length < 3) return false;
    if (!ds.validation.isValid) return false;
  }

  return true;
}

// ── Tile conservation ─────────────────────────────────────────────────────────

export function validateTileConservation(
  puzzle: PuzzleResponse,
  grid: Map<CellKey, PlacedTile>,
  rack: TileInput[],
): boolean {
  // Build multiset of all tiles that should exist
  const expected = new Map<string, number>();
  for (const set of puzzle.board_sets) {
    for (const tile of set.tiles) {
      const key = tileIdentityKey(tile);
      expected.set(key, (expected.get(key) ?? 0) + 1);
    }
  }
  for (const tile of puzzle.rack) {
    const key = tileIdentityKey(tile);
    expected.set(key, (expected.get(key) ?? 0) + 1);
  }

  // Build multiset of all tiles currently in play
  const actual = new Map<string, number>();
  for (const placed of grid.values()) {
    const key = tileIdentityKey(placed.tile);
    actual.set(key, (actual.get(key) ?? 0) + 1);
  }
  for (const tile of rack) {
    const key = tileIdentityKey(tile);
    actual.set(key, (actual.get(key) ?? 0) + 1);
  }

  // Compare
  if (expected.size !== actual.size) return false;
  for (const [key, count] of expected) {
    if (actual.get(key) !== count) return false;
  }
  return true;
}

function tileIdentityKey(tile: TileInput): string {
  if (tile.joker) return "joker";
  return `${tile.color}:${tile.number}`;
}

// ── Insert-shift (Phase 5) ────────────────────────────────────────────────────

export function insertTileIntoRow(
  grid: Map<CellKey, PlacedTile>,
  row: number,
  insertCol: number,
  tile: PlacedTile,
  maxCols: number,
): Map<CellKey, PlacedTile> {
  const newGrid = new Map(grid);

  // Find the rightmost occupied cell in this row at or after insertCol
  let rightmost = insertCol;
  for (let c = insertCol; c < maxCols; c++) {
    if (newGrid.has(cellKey(row, c))) rightmost = c;
    else break; // stop at first gap
  }

  // Check if shift would push a tile off the grid
  if (rightmost + 1 >= maxCols && newGrid.has(cellKey(row, rightmost))) {
    // Cannot insert — grid full at this row
    return grid; // return unchanged
  }

  // Shift tiles rightward from rightmost down to insertCol
  for (let c = rightmost; c >= insertCol; c--) {
    const key = cellKey(row, c);
    if (newGrid.has(key)) {
      const t = newGrid.get(key)!;
      newGrid.delete(key);
      newGrid.set(cellKey(row, c + 1), t);
    }
  }

  // Place the new tile
  newGrid.set(cellKey(row, insertCol), tile);
  return newGrid;
}

// ── Auto-compact (Phase 5) ────────────────────────────────────────────────────

export function compactGrid(
  grid: Map<CellKey, PlacedTile>,
  rows: number,
  cols: number,
): { grid: Map<CellKey, PlacedTile>; rows: number } {
  const newGrid = new Map<CellKey, PlacedTile>();
  let newRow = 0;

  for (let row = 0; row < rows; row++) {
    // Collect all tiles in this row
    const rowTiles: { col: number; tile: PlacedTile }[] = [];
    for (let col = 0; col < cols; col++) {
      const t = grid.get(cellKey(row, col));
      if (t) rowTiles.push({ col, tile: t });
    }

    if (rowTiles.length === 0) continue; // skip empty rows

    // Detect set boundaries (gaps in column sequence)
    let newCol = 0;
    let prevCol = -2; // sentinel
    for (const { col, tile } of rowTiles) {
      if (col !== prevCol + 1 && prevCol >= 0) {
        newCol++; // insert one gap cell between sets
      }
      newGrid.set(cellKey(newRow, newCol), tile);
      prevCol = col;
      newCol++;
    }

    newRow++;
  }

  // Add workspace rows
  const finalRows = Math.max(
    GRID_MIN_ROWS,
    Math.min(newRow + GRID_WORKSPACE_ROWS, GRID_MAX_ROWS),
  );

  return { grid: newGrid, rows: finalRows };
}
