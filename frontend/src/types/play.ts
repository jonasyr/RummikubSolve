import type { TileInput } from "./api";

// ── Grid ──────────────────────────────────────────────────────────────────────

/** A single tile placed on the grid or held in the rack. */
export interface PlacedTile {
  /** The tile data (color, number, joker). */
  tile: TileInput;
  /**
   * Where this tile originated when the puzzle was loaded.
   * "board" = was part of the puzzle's board_sets (cannot return to rack).
   * "rack"  = was part of the puzzle's rack (can return to rack this turn).
   */
  source: "board" | "rack";
}

/** Key format for grid cells: "row:col" */
export type CellKey = `${number}:${number}`;

/** Helper to create a CellKey. */
export function cellKey(row: number, col: number): CellKey {
  return `${row}:${col}`;
}

// ── Set detection ─────────────────────────────────────────────────────────────

export interface DetectedSet {
  row: number;
  startCol: number;
  tiles: PlacedTile[];
  validation: SetValidation;
}

export interface SetValidation {
  isValid: boolean;
  /** null if <3 tiles or invalid */
  type: "run" | "group" | null;
  /** Translation key for the error reason, if invalid and ≥3 tiles */
  reason?: string;
}

// ── Selection ─────────────────────────────────────────────────────────────────

export type TileSelection =
  | { source: "rack"; index: number }
  | { source: "grid"; row: number; col: number }
  | null;

// ── Undo ──────────────────────────────────────────────────────────────────────

export interface PlaySnapshot {
  cells: Map<CellKey, PlacedTile>;
  rack: TileInput[];
}

// ── Drag (used in Phase 4) ────────────────────────────────────────────────────

export type DragStatus = "idle" | "pending" | "dragging";

export interface DragState {
  status: DragStatus;
  pointerId: number | null;
  originSource: TileSelection;
  draggedTile: PlacedTile | null;
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
  snapTarget: { row: number; col: number } | null;
}

// ── Constants ─────────────────────────────────────────────────────────────────

export const GRID_COLS = 16;          // Max run is 13; 16 gives workspace
export const GRID_MIN_ROWS = 6;       // Minimum visible rows
export const GRID_MAX_ROWS = 24;      // Hard cap to prevent unbounded growth
export const GRID_WORKSPACE_ROWS = 3; // Empty rows kept below content
export const UNDO_MAX = 50;           // Snapshot buffer size
export const CELL_SIZE_PX = 48;       // Cell dimensions
export const CELL_GAP_PX = 2;         // Gap between cells
