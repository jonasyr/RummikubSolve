/**
 * Zustand store for Play Mode — isolated from the solver store (game.ts).
 *
 * Phase 0: loadPuzzle, setInteractionMode, toggleValidation, reset implemented.
 * Phase 2: tapCell, tapRackTile, returnToRack, undo, redo implemented.
 * Phase 3: commit, revert implemented.
 */
import { create } from "zustand";

import { fetchPuzzle } from "../lib/api";
import { puzzleToGrid, detectSets, checkSolved } from "../lib/grid-utils";
import type {
  CellKey,
  DetectedSet,
  PlacedTile,
  PlaySnapshot,
  TileSelection,
} from "../types/play";
import { cellKey, GRID_COLS, UNDO_MAX } from "../types/play";
import type { PuzzleRequest, PuzzleResponse, TileInput } from "../types/api";

// ---------------------------------------------------------------------------
// CommitResult
// ---------------------------------------------------------------------------

export type CommitResult =
  | { ok: true }
  | { ok: false; reason: "invalid_sets" | "incomplete_sets" };

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

interface PlayState {
  // ── Puzzle ──────────────────────────────────────────────────────────────
  puzzle: PuzzleResponse | null;

  // ── Grid ────────────────────────────────────────────────────────────────
  grid: Map<CellKey, PlacedTile>;
  gridRows: number;
  gridCols: number;

  // ── Rack ────────────────────────────────────────────────────────────────
  rack: TileInput[];

  // ── Derived (recomputed on every grid mutation) ──────────────────────────
  detectedSets: DetectedSet[];
  isSolved: boolean;

  // ── Undo / Redo ──────────────────────────────────────────────────────────
  past: PlaySnapshot[];
  future: PlaySnapshot[];

  // ── Turn sandbox ─────────────────────────────────────────────────────────
  committedSnapshot: PlaySnapshot;

  // ── UI state ─────────────────────────────────────────────────────────────
  selectedTile: TileSelection;
  interactionMode: "tap" | "drag";
  showValidation: boolean;
  isPuzzleLoading: boolean;
  error: string | null;
  solveStartTime: number | null;
  solveEndTime: number | null;

  // ── Actions ──────────────────────────────────────────────────────────────
  loadPuzzle: (req: PuzzleRequest, signal?: AbortSignal) => Promise<void>;
  tapCell: (row: number, col: number) => void;
  tapRackTile: (index: number) => void;
  returnToRack: () => void;
  undo: () => void;
  redo: () => void;
  commit: () => CommitResult;
  revert: () => void;
  setInteractionMode: (mode: "tap" | "drag") => void;
  toggleValidation: () => void;
  reset: () => void;
}

// ---------------------------------------------------------------------------
// Initial state (extracted so reset() can reuse it)
// ---------------------------------------------------------------------------

const emptySnapshot: PlaySnapshot = { cells: new Map(), rack: [] };

const initialState = {
  puzzle: null as PuzzleResponse | null,
  grid: new Map<CellKey, PlacedTile>(),
  gridRows: 6,
  gridCols: GRID_COLS,
  rack: [] as TileInput[],
  detectedSets: [] as DetectedSet[],
  isSolved: false,
  past: [] as PlaySnapshot[],
  future: [] as PlaySnapshot[],
  committedSnapshot: emptySnapshot,
  selectedTile: null as TileSelection,
  interactionMode: "tap" as const,
  showValidation: true,
  isPuzzleLoading: false,
  error: null as string | null,
  solveStartTime: null as number | null,
  solveEndTime: null as number | null,
};

// ---------------------------------------------------------------------------
// Private helpers (not exported — only used inside the store)
// ---------------------------------------------------------------------------

function takeSnapshot(state: {
  grid: Map<CellKey, PlacedTile>;
  rack: TileInput[];
}): PlaySnapshot {
  return {
    cells: new Map(state.grid),
    rack: [...state.rack],
  };
}

function placeTile(
  state: PlayState,
  targetRow: number,
  targetCol: number,
): Partial<PlayState> {
  const sel = state.selectedTile!;
  const targetKey = cellKey(targetRow, targetCol);

  // Guard: target cell must be empty (guaranteed by tapCell logic, but defensive)
  if (state.grid.has(targetKey)) return {};

  const snapshot = takeSnapshot(state);
  const newGrid = new Map(state.grid);
  let newRack = [...state.rack];

  if (sel.source === "rack") {
    const tile = state.rack[sel.index];
    if (!tile) return {};                    // Safety guard: index out of bounds
    newGrid.set(targetKey, { tile, source: "rack" });
    newRack = newRack.filter((_, i) => i !== sel.index);
  } else {
    // Moving an existing grid tile — preserve PlacedTile.source intact
    const srcKey = cellKey(sel.row, sel.col);
    const srcTile = state.grid.get(srcKey);
    if (!srcTile) return {};                 // Safety guard: tile vanished
    newGrid.delete(srcKey);
    newGrid.set(targetKey, srcTile);
  }

  const detected = detectSets(newGrid, state.gridRows, state.gridCols);
  const solved = checkSolved(newGrid, newRack, detected);

  return {
    grid: newGrid,
    rack: newRack,
    selectedTile: null,
    detectedSets: detected,
    isSolved: solved,
    past: [...state.past, snapshot].slice(-UNDO_MAX),
    future: [],                              // New action always clears redo stack
    solveStartTime: state.solveStartTime ?? Date.now(), // Start timer on first placement
    solveEndTime: solved ? Date.now() : null,
  };
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const usePlayStore = create<PlayState>((set, get) => ({
  ...initialState,

  loadPuzzle: async (request, signal) => {
    // Guard against concurrent calls (e.g. rapid double-click before re-render).
    if (get().isPuzzleLoading) return;
    set({ isPuzzleLoading: true, error: null });
    try {
      const puzzle = await fetchPuzzle(request, signal);
      const { grid, rack, rows } = puzzleToGrid(puzzle);
      const detected = detectSets(grid, rows, GRID_COLS);
      const snapshot: PlaySnapshot = { cells: new Map(grid), rack: [...rack] };
      set({
        puzzle,
        grid,
        gridRows: rows,
        rack,
        detectedSets: detected,
        isSolved: false,
        past: [],
        future: [],
        committedSnapshot: snapshot,
        selectedTile: null,
        isPuzzleLoading: false,
        solveStartTime: null,
        solveEndTime: null,
      });
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        set({ isPuzzleLoading: false });
        return;
      }
      set({
        isPuzzleLoading: false,
        error: err instanceof Error ? err.message : "Unknown error",
      });
    }
  },

  tapRackTile: (index) =>
    set((state) => {
      // Toggle: tapping the already-selected rack tile deselects it
      if (
        state.selectedTile?.source === "rack" &&
        state.selectedTile.index === index
      ) {
        return { selectedTile: null };
      }
      return { selectedTile: { source: "rack", index } };
    }),

  tapCell: (row, col) =>
    set((state) => {
      const key = cellKey(row, col);
      const existing = state.grid.get(key);

      // ── No selection active ──────────────────────────────────────
      if (!state.selectedTile) {
        if (existing) {
          return { selectedTile: { source: "grid", row, col } };
        }
        return {}; // Tapped empty cell with no selection — nothing to do
      }

      // ── Selection active, tapped an occupied cell ────────────────
      if (existing) {
        // Tapping the same cell that is already selected → deselect
        if (
          state.selectedTile.source === "grid" &&
          state.selectedTile.row === row &&
          state.selectedTile.col === col
        ) {
          return { selectedTile: null };
        }
        // Tapped a different occupied cell → switch selection to it
        return { selectedTile: { source: "grid", row, col } };
      }

      // ── Selection active, tapped an empty cell → PLACE the tile ──
      return placeTile(state, row, col);
    }),

  returnToRack: () =>
    set((state) => {
      if (!state.selectedTile || state.selectedTile.source !== "grid") return {};

      const { row, col } = state.selectedTile;
      const key = cellKey(row, col);
      const placed = state.grid.get(key);
      if (!placed) return {};

      // RULE: board-source tiles are permanently locked to the grid
      if (placed.source === "board") return {};

      const snapshot = takeSnapshot(state);
      const newGrid = new Map(state.grid);
      newGrid.delete(key);
      const newRack = [...state.rack, placed.tile];
      const detected = detectSets(newGrid, state.gridRows, state.gridCols);

      return {
        grid: newGrid,
        rack: newRack,
        selectedTile: null,
        detectedSets: detected,
        isSolved: false,            // Rack non-empty → cannot be solved
        past: [...state.past, snapshot].slice(-UNDO_MAX),
        future: [],                 // New action clears redo stack
      };
    }),

  undo: () =>
    set((state) => {
      if (state.past.length === 0) return {};
      const snapshot = state.past[state.past.length - 1];
      const futureSS = takeSnapshot(state);
      const detected = detectSets(snapshot.cells, state.gridRows, state.gridCols);
      return {
        grid: snapshot.cells,
        rack: snapshot.rack,
        detectedSets: detected,
        isSolved: checkSolved(snapshot.cells, snapshot.rack, detected),
        past: state.past.slice(0, -1),
        future: [...state.future, futureSS],
        selectedTile: null,         // Always clear selection on undo
      };
    }),

  redo: () =>
    set((state) => {
      if (state.future.length === 0) return {};
      const snapshot = state.future[state.future.length - 1];
      const pastSS = takeSnapshot(state);
      const detected = detectSets(snapshot.cells, state.gridRows, state.gridCols);
      return {
        grid: snapshot.cells,
        rack: snapshot.rack,
        detectedSets: detected,
        isSolved: checkSolved(snapshot.cells, snapshot.rack, detected),
        past: [...state.past, pastSS],
        future: state.future.slice(0, -1),
        selectedTile: null,         // Always clear selection on redo
      };
    }),

  // Phase 3 — stub replaced in Phase 3 implementation
  commit: () => ({ ok: false, reason: "invalid_sets" } as const),
  revert: () => {},

  setInteractionMode: (mode) => set({ interactionMode: mode }),
  toggleValidation: () => set((s) => ({ showValidation: !s.showValidation })),
  reset: () => set(initialState),
}));

// ---------------------------------------------------------------------------
// Exported helpers for internal use by Phase 2 implementation
// ---------------------------------------------------------------------------

export { cellKey, GRID_COLS, UNDO_MAX };
export type { PlayState };
