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
  PuzzleRequest,
  SolveResponse,
  TileInput,
} from "../types/api";

// ---------------------------------------------------------------------------
// Phase 5: seen-puzzle tracking (localStorage persistence)
// Phase 6: last puzzle metadata (chain depth + uniqueness for stats badge)
// ---------------------------------------------------------------------------

interface PuzzleMeta {
  chainDepth: number;
  isUnique: boolean;
  difficulty: string;
}

const _SEEN_KEY = "rummikub_seen_puzzles";
const _SEEN_MAX = 500;

function _loadSeenIds(): string[] {
  try {
    const raw = localStorage.getItem(_SEEN_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return []; // localStorage unavailable (SSR / private browsing)
  }
}

function _persistSeenIds(ids: string[]): void {
  try {
    localStorage.setItem(_SEEN_KEY, JSON.stringify(ids));
  } catch {
    // ignore write failures (storage quota, private browsing)
  }
}

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

  // Phase 5: accumulated IDs of puzzles already seen (persisted in localStorage)
  seenPuzzleIds: string[];

  // Phase 6: metadata from the most recently loaded puzzle
  lastPuzzleMeta: PuzzleMeta | null;

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
  loadPuzzle: (request: PuzzleRequest, signal?: AbortSignal) => Promise<void>;

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
  seenPuzzleIds: [] as string[], // Phase 5: reset() clears in-memory list (localStorage retained)
  lastPuzzleMeta: null as PuzzleMeta | null,
};

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useGameStore = create<GameState>((set, get) => ({
  ...initialState,
  // Phase 5: hydrate seenPuzzleIds from localStorage on first store creation.
  seenPuzzleIds: _loadSeenIds(),

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

  loadPuzzle: async (request, signal) => {
    // Guard against concurrent calls (e.g. rapid double-click before re-render).
    if (get().isPuzzleLoading) return;
    set({ isPuzzleLoading: true, error: null, solution: null });
    try {
      // Phase 5: inject seen_ids so the pool avoids sending duplicate puzzles.
      const currentSeen = get().seenPuzzleIds;
      const enrichedRequest: PuzzleRequest = {
        ...request,
        ...(currentSeen.length > 0 ? { seen_ids: currentSeen } : {}),
      };
      const puzzle = await fetchPuzzle(enrichedRequest, signal);

      // Phase 5: accumulate the returned puzzle_id (non-empty = drawn from pool).
      let updatedSeen = currentSeen;
      if (puzzle.puzzle_id) {
        updatedSeen = [...currentSeen, puzzle.puzzle_id].slice(-_SEEN_MAX);
        _persistSeenIds(updatedSeen);
      }

      set({
        boardSets: puzzle.board_sets,
        rack: puzzle.rack,
        isPuzzleLoading: false,
        isFirstTurn: false,
        isBuildingSet: false,
        seenPuzzleIds: updatedSeen,
        lastPuzzleMeta: {           // Phase 6: expose metadata for stats badge
          chainDepth: puzzle.chain_depth ?? 0,
          isUnique: puzzle.is_unique ?? false,
          difficulty: puzzle.difficulty,
        },
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
