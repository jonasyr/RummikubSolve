/**
 * Zustand store for Play Mode — isolated from the solver store (game.ts).
 *
 * Phase 0: loadPuzzle, setInteractionMode, toggleValidation, reset implemented.
 * Phase 2: tapCell, tapRackTile, returnToRack, undo, redo implemented.
 * Phase 3: commit, revert implemented.
 */
import { create } from "zustand";

import { fetchPuzzle } from "../lib/api";
import { recordTelemetryEvent, toTelemetryTile } from "../lib/telemetry";
import { puzzleToGrid, detectSets, checkSolved, validateTileConservation } from "../lib/grid-utils";
import type {
  CellKey,
  DetectedSet,
  PlacedTile,
  PlaySnapshot,
  TileSelection,
} from "../types/play";
import { cellKey, GRID_COLS, GRID_MIN_ROWS, GRID_MAX_ROWS, GRID_WORKSPACE_ROWS, UNDO_MAX } from "../types/play";
import type { PuzzleRequest, PuzzleResponse, TileInput } from "../types/api";

// ---------------------------------------------------------------------------
// CommitResult
// ---------------------------------------------------------------------------

export type CommitResult =
  | { ok: true }
  | { ok: false; reason: "invalid_sets" | "incomplete_sets" | "tile_conservation" };

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
  lastMeaningfulActionAt: number | null;
  undoCount: number;
  redoCount: number;
  commitCount: number;
  revertCount: number;
  moveCount: number;
  stuckMoments: number;
  telemetrySolvedSent: boolean;
  attemptId: string | null;
  calibrationContext: { batchName: string; batchRunId: string; batchIndex: number } | null;

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
  setCalibrationContext: (context: { batchName: string; batchRunId: string; batchIndex: number } | null) => void;
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
  lastMeaningfulActionAt: null as number | null,
  undoCount: 0,
  redoCount: 0,
  commitCount: 0,
  revertCount: 0,
  moveCount: 0,
  stuckMoments: 0,
  telemetrySolvedSent: false,
  attemptId: null as string | null,
  calibrationContext: null as { batchName: string; batchRunId: string; batchIndex: number } | null,
};

// ---------------------------------------------------------------------------
// Private helpers (not exported — only used inside the store)
// ---------------------------------------------------------------------------

function computeGridRows(grid: Map<CellKey, PlacedTile>): number {
  let lastUsedRow = -1;
  for (const key of grid.keys()) {
    const row = parseInt(key.split(":")[0]);
    if (row > lastUsedRow) lastUsedRow = row;
  }
  const neededRows = lastUsedRow + GRID_WORKSPACE_ROWS + 1;
  return Math.max(GRID_MIN_ROWS, Math.min(neededRows, GRID_MAX_ROWS));
}

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

  const now = Date.now();
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
    gridRows: Math.max(state.gridRows, computeGridRows(newGrid)), // only grow, never shrink
    moveCount: state.moveCount + 1,
    stuckMoments:
      state.stuckMoments +
      (state.lastMeaningfulActionAt !== null && now - state.lastMeaningfulActionAt > 30_000 ? 1 : 0),
    solveStartTime: state.solveStartTime ?? now, // Start timer on first placement
    solveEndTime: solved ? now : null,
    lastMeaningfulActionAt: now,
  };
}

function maybeRecordSolved(state: PlayState): void {
  if (
    !state.puzzle ||
    !state.isSolved ||
    state.telemetrySolvedSent ||
    state.solveStartTime === null ||
    state.solveEndTime === null
  ) {
    return;
  }

  void recordTelemetryEvent("puzzle_solved", state.puzzle, {
    attempt_id: state.attemptId ?? "",
    batch_name: state.calibrationContext?.batchName,
    batch_run_id: state.calibrationContext?.batchRunId,
    batch_index: state.calibrationContext?.batchIndex,
    elapsed_ms: Math.max(0, state.solveEndTime - state.solveStartTime),
    move_count: state.moveCount,
    undo_count: state.undoCount,
    redo_count: state.redoCount,
    commit_count: state.commitCount,
    revert_count: state.revertCount,
    tiles_placed: state.puzzle.tile_count,
    tiles_remaining: 0,
    stuck_moments: state.stuckMoments,
  });
}

function makeAttemptId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `attempt-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
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
        lastMeaningfulActionAt: null,
        undoCount: 0,
        redoCount: 0,
        commitCount: 0,
        revertCount: 0,
        moveCount: 0,
        stuckMoments: 0,
        telemetrySolvedSent: false,
        attemptId: makeAttemptId(),
      });
      const nextState = get();
      void recordTelemetryEvent("puzzle_loaded", puzzle, {
        attempt_id: nextState.attemptId ?? "",
        batch_name: nextState.calibrationContext?.batchName,
        batch_index: nextState.calibrationContext?.batchIndex,
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
    (set((state) => {
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
      const next = placeTile(state, row, col);
      if (state.puzzle && Object.keys(next).length > 0) {
        if (state.selectedTile.source === "rack") {
          const tile = state.rack[state.selectedTile.index];
          if (tile) {
            void recordTelemetryEvent("tile_placed", state.puzzle, {
              attempt_id: state.attemptId ?? "",
              batch_name: state.calibrationContext?.batchName,
              batch_index: state.calibrationContext?.batchIndex,
              tile: toTelemetryTile(tile),
              to_row: row,
              to_col: col,
            });
          }
        } else {
          const sourceTile = state.grid.get(cellKey(state.selectedTile.row, state.selectedTile.col));
          if (sourceTile) {
            void recordTelemetryEvent("tile_moved", state.puzzle, {
              attempt_id: state.attemptId ?? "",
              batch_name: state.calibrationContext?.batchName,
              batch_index: state.calibrationContext?.batchIndex,
              tile: toTelemetryTile(sourceTile.tile),
              from_row: state.selectedTile.row,
              from_col: state.selectedTile.col,
              to_row: row,
              to_col: col,
            });
          }
        }
      }
      return next;
    }), (() => {
      const state = get();
      if (state.isSolved && !state.telemetrySolvedSent) {
        set({ telemetrySolvedSent: true });
        maybeRecordSolved(state);
      }
    })()),

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
      const now = Date.now();

      void (state.puzzle &&
        recordTelemetryEvent("tile_returned_to_rack", state.puzzle, {
          attempt_id: state.attemptId ?? "",
          batch_name: state.calibrationContext?.batchName,
          batch_index: state.calibrationContext?.batchIndex,
          tile: toTelemetryTile(placed.tile),
        }));

      return {
        grid: newGrid,
        rack: newRack,
        selectedTile: null,
        detectedSets: detected,
        isSolved: false,            // Rack non-empty → cannot be solved
        past: [...state.past, snapshot].slice(-UNDO_MAX),
        future: [],                 // New action clears redo stack
        moveCount: state.moveCount + 1,
        stuckMoments:
          state.stuckMoments +
          (state.lastMeaningfulActionAt !== null && now - state.lastMeaningfulActionAt > 30_000 ? 1 : 0),
        lastMeaningfulActionAt: now,
      };
    }),

  undo: () =>
    (set((state) => {
      if (state.past.length === 0) return {};
      void (state.puzzle && recordTelemetryEvent("undo_pressed", state.puzzle, {
        attempt_id: state.attemptId ?? "",
        batch_name: state.calibrationContext?.batchName,
        batch_index: state.calibrationContext?.batchIndex,
      }));
      const snapshot = state.past[state.past.length - 1];
      const futureSS = takeSnapshot(state);
      const detected = detectSets(snapshot.cells, state.gridRows, state.gridCols);
      const now = Date.now();
      return {
        grid: snapshot.cells,
        rack: snapshot.rack,
        detectedSets: detected,
        isSolved: checkSolved(snapshot.cells, snapshot.rack, detected),
        past: state.past.slice(0, -1),
        future: [...state.future, futureSS],
        undoCount: state.undoCount + 1,
        stuckMoments:
          state.stuckMoments +
          (state.lastMeaningfulActionAt !== null && now - state.lastMeaningfulActionAt > 30_000 ? 1 : 0),
        lastMeaningfulActionAt: now,
        selectedTile: null,         // Always clear selection on undo
      };
    }), (() => {
      const state = get();
      if (state.isSolved && !state.telemetrySolvedSent) {
        set({ telemetrySolvedSent: true });
        maybeRecordSolved(state);
      }
    })()),

  redo: () =>
    (set((state) => {
      if (state.future.length === 0) return {};
      const snapshot = state.future[state.future.length - 1];
      const pastSS = takeSnapshot(state);
      const detected = detectSets(snapshot.cells, state.gridRows, state.gridCols);
      const now = Date.now();
      return {
        grid: snapshot.cells,
        rack: snapshot.rack,
        detectedSets: detected,
        isSolved: checkSolved(snapshot.cells, snapshot.rack, detected),
        past: [...state.past, pastSS],
        future: state.future.slice(0, -1),
        redoCount: state.redoCount + 1,
        stuckMoments:
          state.stuckMoments +
          (state.lastMeaningfulActionAt !== null && now - state.lastMeaningfulActionAt > 30_000 ? 1 : 0),
        lastMeaningfulActionAt: now,
        selectedTile: null,         // Always clear selection on redo
      };
    }), (() => {
      const state = get();
      if (state.isSolved && !state.telemetrySolvedSent) {
        set({ telemetrySolvedSent: true });
        maybeRecordSolved(state);
      }
    })()),

  commit: () => {
    const state = get();

    // Gate 0: tile conservation — only checked when a puzzle is loaded
    // Defensive guard: ensures no tiles were lost or duplicated by store logic bugs.
    if (
      state.puzzle &&
      !validateTileConservation(state.puzzle, state.grid, state.rack)
    ) {
      return { ok: false as const, reason: "tile_conservation" as const };
    }

    // Gate 1: no set of ≥3 tiles that fails validation
    const hasInvalid = state.detectedSets.some(
      (ds) => ds.tiles.length >= 3 && !ds.validation.isValid,
    );
    if (hasInvalid) return { ok: false as const, reason: "invalid_sets" as const };

    // Gate 2: no orphan groups of 1 or 2 tiles
    const hasIncomplete = state.detectedSets.some(
      (ds) => ds.tiles.length > 0 && ds.tiles.length < 3,
    );
    if (hasIncomplete) return { ok: false as const, reason: "incomplete_sets" as const };

    // All gates passed — advance the committed snapshot and clear undo history
    set({
      committedSnapshot: takeSnapshot(state),
      past: [],
      future: [],
      commitCount: state.commitCount + 1,
      stuckMoments:
        state.stuckMoments +
        (state.lastMeaningfulActionAt !== null && Date.now() - state.lastMeaningfulActionAt > 30_000 ? 1 : 0),
      lastMeaningfulActionAt: Date.now(),
      selectedTile: null,
    });

    const nextState = get();
    if (nextState.isSolved && !nextState.telemetrySolvedSent) {
      set({ telemetrySolvedSent: true });
      maybeRecordSolved(nextState);
    }

    return { ok: true as const };
  },

  revert: () =>
    set((state) => {
      const snap = state.committedSnapshot;
      const detected = detectSets(snap.cells, state.gridRows, state.gridCols);
      const now = Date.now();
      return {
        grid: new Map(snap.cells),
        rack: [...snap.rack],
        detectedSets: detected,
        isSolved: checkSolved(snap.cells, snap.rack, detected),
        past: [],
        future: [],
        revertCount: state.revertCount + 1,
        stuckMoments:
          state.stuckMoments +
          (state.lastMeaningfulActionAt !== null && now - state.lastMeaningfulActionAt > 30_000 ? 1 : 0),
        lastMeaningfulActionAt: now,
        selectedTile: null,
        gridRows: computeGridRows(snap.cells), // recompute from snapshot (may shrink)
      };
    }),

  setInteractionMode: (mode) => {
    try {
      localStorage.setItem("play:interactionMode", mode);
    } catch {
      // localStorage unavailable (SSR or restricted environment)
    }
    set({ interactionMode: mode });
  },
  setCalibrationContext: (context) => set({ calibrationContext: context }),
  toggleValidation: () => set((s) => ({ showValidation: !s.showValidation })),
  reset: () => set(initialState),
}));

// ---------------------------------------------------------------------------
// Exported helpers for internal use by Phase 2 implementation
// ---------------------------------------------------------------------------

export { cellKey, GRID_COLS, UNDO_MAX };
export type { PlayState };
