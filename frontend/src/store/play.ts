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

  // Phase 2 — stubs replaced in Phase 2 implementation
  tapCell: () => {},
  tapRackTile: () => {},
  returnToRack: () => {},
  undo: () => {},
  redo: () => {},

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
