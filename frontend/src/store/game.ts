/**
 * Global Zustand store for the RummikubSolve application.
 *
 * Holds:
 *  - User input: board sets and rack tiles the user has entered
 *  - Rule settings: first-turn toggle, etc.
 *  - Async state: loading flag, solve result, error message
 *
 * Actions are synchronous state mutations; async operations (API calls)
 * are handled by hooks/services that call these actions.
 */
import { create } from "zustand";

import { fetchPuzzle } from "../lib/api";
import type {
  BoardSetInput,
  Difficulty,
  SolveResponse,
  TileInput,
} from "../types/api";

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

interface GameState {
  // Input
  boardSets: BoardSetInput[];
  rack: TileInput[];
  isFirstTurn: boolean;

  // Async
  isLoading: boolean;
  isPuzzleLoading: boolean;
  solution: SolveResponse | null;
  error: string | null;

  // UI state
  isBuildingSet: boolean;

  // Actions — board
  addBoardSet: (set: BoardSetInput) => void;
  removeBoardSet: (index: number) => void;
  updateBoardSet: (index: number, set: BoardSetInput) => void;

  // Actions — rack
  addRackTile: (tile: TileInput) => void;
  removeRackTile: (index: number) => void;

  // Actions — settings
  setIsFirstTurn: (value: boolean) => void;

  // Actions — async state
  setLoading: (loading: boolean) => void;
  setSolution: (solution: SolveResponse | null) => void;
  setError: (error: string | null) => void;

  // Actions — UI state
  setIsBuildingSet: (v: boolean) => void;

  // Actions — puzzle
  loadPuzzle: (difficulty: Difficulty, signal?: AbortSignal) => Promise<void>;

  // Actions — reset
  reset: () => void;
}

// ---------------------------------------------------------------------------
// Initial state (extracted so reset() can reuse it)
// ---------------------------------------------------------------------------

const initialState = {
  boardSets: [] as BoardSetInput[],
  rack: [] as TileInput[],
  isFirstTurn: false,
  isLoading: false,
  isPuzzleLoading: false,
  solution: null as SolveResponse | null,
  error: null as string | null,
  isBuildingSet: false,
};

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useGameStore = create<GameState>((set, get) => ({
  ...initialState,

  addBoardSet: (s) =>
    set((state) => ({ boardSets: [...state.boardSets, s] })),

  removeBoardSet: (i) =>
    set((state) => ({
      boardSets: state.boardSets.filter((_, idx) => idx !== i),
    })),

  updateBoardSet: (i, s) =>
    set((state) => ({
      boardSets: state.boardSets.map((existing, idx) =>
        idx === i ? s : existing
      ),
    })),

  addRackTile: (t) =>
    set((state) => ({ rack: [...state.rack, t] })),

  removeRackTile: (i) =>
    set((state) => ({ rack: state.rack.filter((_, idx) => idx !== i) })),

  setIsFirstTurn: (value) => set({ isFirstTurn: value }),

  setLoading: (isLoading) => set({ isLoading }),
  setSolution: (solution) => set({ solution }),
  setError: (error) => set({ error }),

  setIsBuildingSet: (v) => set({ isBuildingSet: v }),

  loadPuzzle: async (difficulty, signal) => {
    // Guard against concurrent calls (e.g. rapid double-click before re-render).
    if (get().isPuzzleLoading) return;
    set({ isPuzzleLoading: true, error: null, solution: null });
    try {
      const puzzle = await fetchPuzzle({ difficulty }, signal);
      set({
        boardSets: puzzle.board_sets,
        rack: puzzle.rack,
        isPuzzleLoading: false,
        isFirstTurn: false,
        isBuildingSet: false,
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

  reset: () => set(initialState),
}));
