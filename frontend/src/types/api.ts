/**
 * TypeScript mirror of backend/api/models.py
 *
 * Keep in sync with the Pydantic models whenever the API schema changes.
 * These types are used by the Zustand store and all API call sites.
 */

// ---------------------------------------------------------------------------
// Shared primitives
// ---------------------------------------------------------------------------

export type TileColor = "blue" | "red" | "black" | "yellow";

// ---------------------------------------------------------------------------
// Request types  (frontend → backend)
// ---------------------------------------------------------------------------

export interface TileInput {
  color?: TileColor;
  number?: number;
  joker?: boolean;
}

export interface BoardSetInput {
  type: "run" | "group";
  tiles: TileInput[];
}

export interface RulesInput {
  initial_meld_threshold?: number;
  is_first_turn?: boolean;
  allow_wrap_runs?: boolean;
}

export interface SolveRequest {
  board: BoardSetInput[];
  rack: TileInput[];
  rules?: RulesInput;
}

// ---------------------------------------------------------------------------
// Response types  (backend → frontend)
// ---------------------------------------------------------------------------

export interface TileOutput {
  color: TileColor | null;
  number: number | null;
  joker: boolean;
  copy_id: number;
}

export interface BoardSetOutput {
  type: "run" | "group";
  tiles: TileOutput[];
  /** 0-based indices of tiles in this set that came from the rack */
  new_tile_indices: number[];
  /** True when the set is identical to an existing board set (no tiles added/removed) */
  is_unchanged?: boolean;
}

export interface MoveOutput {
  action: string;
  description: string;
  set_index: number | null;
}

export type Difficulty = "easy" | "medium" | "hard" | "expert" | "nightmare" | "custom";

export interface PuzzleRequest {
  difficulty?: Difficulty;
  seed?: number;
  /** Only used when difficulty == "custom". Range 1–5, default 3. */
  sets_to_remove?: number;
  /** Phase 5: IDs of puzzles already seen; prevents duplicates when drawing from pool. */
  seen_ids?: string[];
}

export interface PuzzleResponse {
  board_sets: BoardSetInput[];
  rack: TileInput[];
  difficulty: Difficulty;
  tile_count: number;
  disruption_score: number; // was missing from TS mirror (backend returns it since v0.22.0)
  chain_depth: number;      // Phase 3: longest rearrangement chain depth
  is_unique: boolean;       // Phase 3: solution uniqueness verified for Expert/Nightmare
  /** Phase 5: UUID for pool-drawn puzzles; empty string for live-generated. */
  puzzle_id: string;
}

export type SolveStatus = "solved" | "no_solution";

export interface SolveResponse {
  status: SolveStatus;
  tiles_placed: number;
  tiles_remaining: number;
  solve_time_ms: number;
  is_optimal: boolean;
  is_first_turn: boolean;
  new_board: BoardSetOutput[];
  remaining_rack: TileOutput[];
  moves: MoveOutput[];
}
