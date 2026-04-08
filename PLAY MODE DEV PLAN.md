# RummikubSolve — Play Mode: Development Plan

**Version:** 1.0 — Final
**Status:** Ready for development
**Last updated:** 2026-04-05

-----

## Table of Contents

1. [Product Overview](#1-product-overview)
1. [Architecture Decision Record](#2-architecture-decision-record)
1. [Data Model Specification](#3-data-model-specification)
1. [Core Algorithms](#4-core-algorithms)
1. [Phase 0 — Route & State Isolation](#5-phase-0--route--state-isolation)
1. [Phase 1 — Grid Rendering & iPad Layout](#6-phase-1--grid-rendering--ipad-layout)
1. [Phase 2 — Tap-to-Place Interaction](#7-phase-2--tap-to-place-interaction)
1. [Phase 3 — Validation Overlays & Turn Sandbox](#8-phase-3--validation-overlays--turn-sandbox)
1. [Phase 4 — Drag-and-Drop Layer](#9-phase-4--drag-and-drop-layer)
1. [Phase 5 — Board Rearrangement Polish](#10-phase-5--board-rearrangement-polish)
1. [Phase 6 — Completion, Polish & Ship](#11-phase-6--completion-polish--ship)
1. [Bug & Race Condition Register](#12-bug--race-condition-register)
1. [Testing Strategy](#13-testing-strategy)
1. [File Manifest](#14-file-manifest)
1. [i18n Keys](#15-i18n-keys)
1. [Timeline & Dependency Graph](#16-timeline--dependency-graph)
1. [Definition of Done](#17-definition-of-done)

-----

## 1. Product Overview

### What we are building

A new `/play` route where users **manually solve** Rummikub puzzles by placing tiles from their rack onto a 2D grid board. This is a separate mode from the existing solver at `/` — the solver tells you the optimal move; play mode lets you figure it out yourself.

### How it works

1. User loads a puzzle (reuses existing `/api/puzzle` endpoint + `PuzzleControls` component).
1. Puzzle board sets render as rows on a 2D grid. Rack tiles appear in a side/bottom panel.
1. User selects a rack tile (tap or drag), then places it on an empty grid cell.
1. The system detects sets by scanning for horizontally adjacent tiles in each row.
1. Each detected set is validated in real time (green = valid run/group, red = invalid, amber = incomplete).
1. User can rearrange board tiles between cells, undo/redo moves, commit progress, or revert.
1. Puzzle is solved when the rack is empty and every tile on the grid belongs to a valid set of 3+ tiles.

### What we are NOT building

- No backend changes. The existing `/api/puzzle` and `/api/solve` endpoints are sufficient.
- No multiplayer, no real-time sync, no server-side play state.
- No modification to the existing solver mode (`/`). The two modes share only leaf components (`Tile.tsx`, `TileGridPicker.tsx`) and the puzzle API client.

-----

## 2. Architecture Decision Record

### ADR-1: 2D Freeform Grid (not Set-Slot model)

**Decision:** The board is a 2D grid of cells. Any cell can hold one tile. Horizontally adjacent tiles (no gap) form a set. Empty cell = set boundary. Rows are independent.

**Rationale:** Mirrors physical Rummikub. Users can spread tiles out, work on multiple rearrangements simultaneously, slide tiles between groups. Complex puzzles (Expert/Nightmare) require rearranging 5-10+ board sets — a constrained slot model would be clumsy.

**Set detection is trivial:** Scan each row left-to-right, group contiguous tiles, validate each group. ~20 lines of code.

### ADR-2: Tap-to-Place as default, Drag as opt-in

**Decision:** Primary interaction is tap-to-select → tap-to-place. Drag-and-drop is layered on top as a toggleable power-user mode.

**Rationale:** Rummikub’s audience includes families and older adults. Tap is deterministic — no accidental drags, no threshold ambiguity, no stuck tiles. Drag is faster for experienced users but has more failure modes on iPad Safari.

### ADR-3: Immutable snapshots for undo (not command log)

**Decision:** Every mutating action captures a full snapshot of `(grid, rack)` before mutation. Undo restores the previous snapshot. Max 50 snapshots.

**Rationale:** Board state is tiny (~30 tiles × ~20 bytes = ~600 bytes per snapshot, ~30KB total for 50 snapshots). Command replay would require inverse operations for every action, and cascading validation effects make command inversion error-prone. Snapshots are trivially correct.

### ADR-4: Separate route and store (no shared mutable state with solver)

**Decision:** Play mode lives at `/play` with its own Zustand store (`play.ts`). The solver store (`game.ts`) is never imported or modified.

**Rationale:** The two modes have fundamentally different state shapes. Solver mode has `boardSets: BoardSetInput[]` (validated sets). Play mode has `grid: Map<string, PlacedTile>` (individual cells). Mixing them would create coupling bugs.

### ADR-5: Client-side validation only during play

**Decision:** All set validation during play runs in the browser. The backend `/api/solve` is only called optionally after the user solves the puzzle (to compare solutions).

**Rationale:** Validation must run on every tile placement (~60fps during drag). Backend round-trip latency (10-50ms) is too slow. The existing `validateSet()` logic in `BoardSection.tsx` already implements run/group validation in TypeScript — we extract and extend it.

### ADR-6: No copy_id in play mode

**Decision:** Play mode does not track `copy_id`. Tiles are identified by reference identity (their position in the Map), not by `(color, number, copy_id)` tuples.

**Rationale:** `copy_id` exists to let the ILP solver distinguish the two physical copies of identical tiles. In play mode the user is the solver — they see each tile as a distinct object on screen. Reference identity in the `Map<string, PlacedTile>` provides tile uniqueness automatically.

-----

## 3. Data Model Specification

### 3.1 — Core types

Create `frontend/src/types/play.ts`:

```typescript
import type { TileInput, PuzzleResponse } from "./api";

// ── Grid ────────────────────────────────────────────────────────────────

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

// ── Set detection ───────────────────────────────────────────────────────

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

// ── Selection ───────────────────────────────────────────────────────────

export type TileSelection =
  | { source: "rack"; index: number }
  | { source: "grid"; row: number; col: number }
  | null;

// ── Undo ────────────────────────────────────────────────────────────────

export interface PlaySnapshot {
  cells: Map<CellKey, PlacedTile>;
  rack: TileInput[];
}

// ── Drag ────────────────────────────────────────────────────────────────

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
```

### 3.2 — Store shape

Create `frontend/src/store/play.ts`:

```typescript
export interface PlayState {
  // ── Puzzle ──────────────────────────────────────────────────────────
  puzzle: PuzzleResponse | null;

  // ── Grid ────────────────────────────────────────────────────────────
  grid: Map<CellKey, PlacedTile>;
  gridRows: number;  // visible row count (auto-grows)
  gridCols: number;  // fixed at 16

  // ── Rack ────────────────────────────────────────────────────────────
  rack: TileInput[];

  // ── Derived (recomputed on every grid mutation) ─────────────────────
  detectedSets: DetectedSet[];
  isSolved: boolean;

  // ── Undo / Redo ─────────────────────────────────────────────────────
  past: PlaySnapshot[];
  future: PlaySnapshot[];

  // ── Turn sandbox ────────────────────────────────────────────────────
  committedSnapshot: PlaySnapshot;

  // ── UI state ────────────────────────────────────────────────────────
  selectedTile: TileSelection;
  interactionMode: "tap" | "drag";
  showValidation: boolean;
  isPuzzleLoading: boolean;
  error: string | null;
  solveStartTime: number | null;  // Date.now() on first placement
  solveEndTime: number | null;    // Date.now() on completion

  // ── Actions ─────────────────────────────────────────────────────────
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

export type CommitResult =
  | { ok: true }
  | { ok: false; reason: "invalid_sets" | "incomplete_sets" };
```

### 3.3 — Grid constants

```typescript
export const GRID_COLS = 16;           // Max run is 13; 16 gives workspace
export const GRID_MIN_ROWS = 6;       // Minimum visible rows
export const GRID_MAX_ROWS = 24;      // Hard cap to prevent unbounded growth
export const GRID_WORKSPACE_ROWS = 3; // Empty rows kept below content
export const UNDO_MAX = 50;           // Snapshot buffer size
export const CELL_SIZE_PX = 48;       // Cell dimensions
export const CELL_GAP_PX = 2;         // Gap between cells
```

-----

## 4. Core Algorithms

All algorithms go in `frontend/src/lib/grid-utils.ts`.

### 4.1 — Puzzle-to-grid mapping

```typescript
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
```

### 4.2 — Set detection

```typescript
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
```

### 4.3 — Tile group validation

Extract and extend from the existing `validateSet()` in `BoardSection.tsx`. Place in `frontend/src/lib/play-validation.ts`:

```typescript
import type { TileInput, TileColor } from "../types/api";
import type { PlacedTile, SetValidation } from "../types/play";

export function validateTileGroup(placed: PlacedTile[]): SetValidation {
  if (placed.length < 3) {
    return { isValid: false, type: null };
    // NOTE: no reason string for <3 tiles — this is "incomplete", not "invalid"
  }

  const tiles = placed.map((p) => p.tile);
  const runResult = validateAsRun(tiles);
  if (runResult.valid) return { isValid: true, type: "run" };

  const groupResult = validateAsGroup(tiles);
  if (groupResult.valid) return { isValid: true, type: "group" };

  return {
    isValid: false,
    type: null,
    reason: runResult.reason ?? groupResult.reason ?? "play.validation.invalid",
  };
}

// ── Run validation ──────────────────────────────────────────────────────

interface ValidationResult {
  valid: boolean;
  reason?: string;
}

function validateAsRun(tiles: TileInput[]): ValidationResult {
  if (tiles.length > 13) return { valid: false, reason: "play.validation.runTooLong" };

  const jokers = tiles.filter((t) => t.joker);
  const nonJokers = tiles.filter((t) => !t.joker);

  if (nonJokers.length === 0) return { valid: true }; // all jokers, structurally valid

  const colors = new Set(nonJokers.map((t) => t.color));
  if (colors.size > 1) return { valid: false, reason: "play.validation.runMixedColors" };

  const numbers = nonJokers.map((t) => t.number!).sort((a, b) => a - b);
  if (new Set(numbers).size < numbers.length) {
    return { valid: false, reason: "play.validation.runDuplicateNumbers" };
  }

  const nMin = numbers[0];
  const nMax = numbers[numbers.length - 1];
  const gaps = nMax - nMin + 1 - numbers.length;
  if (gaps > jokers.length) {
    return { valid: false, reason: "play.validation.runGapsTooLarge" };
  }

  const total = tiles.length;
  const lo = Math.max(1, nMax - total + 1);
  const hi = Math.min(nMin, 14 - total);
  if (lo > hi) return { valid: false, reason: "play.validation.runOutOfRange" };

  return { valid: true };
}

// ── Group validation ────────────────────────────────────────────────────

function validateAsGroup(tiles: TileInput[]): ValidationResult {
  if (tiles.length > 4) return { valid: false, reason: "play.validation.groupTooLarge" };

  const jokers = tiles.filter((t) => t.joker);
  const nonJokers = tiles.filter((t) => !t.joker);

  if (nonJokers.length === 0) return { valid: true };

  const numbers = new Set(nonJokers.map((t) => t.number));
  if (numbers.size > 1) return { valid: false, reason: "play.validation.groupMixedNumbers" };

  const colors = nonJokers.map((t) => t.color!);
  if (new Set(colors).size < colors.length) {
    return { valid: false, reason: "play.validation.groupDuplicateColors" };
  }

  if (jokers.length > 4 - new Set(colors).size) {
    return { valid: false, reason: "play.validation.groupTooManyJokers" };
  }

  return { valid: true };
}
```

### 4.4 — Completion check

```typescript
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
```

### 4.5 — Tile conservation (commit-time integrity check)

```typescript
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
```

> **⚠ BUG RISK — Tile identity collisions:**
> `tileIdentityKey` collapses both physical copies of a tile (e.g. two Red 5s)
> into the same key. This is intentional for conservation counting (the multiset
> count handles duplicates), but means we cannot distinguish which specific
> copy is which. This is acceptable — play mode does not need copy-level
> tracking (see ADR-6). However, if a puzzle has two identical tiles, the
> conservation check only verifies the COUNT is correct, not that the exact
> same objects are present. This is fine for play mode purposes.

### 4.6 — Insert-shift (for Phase 5)

```typescript
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
      const tile = newGrid.get(key)!;
      newGrid.delete(key);
      newGrid.set(cellKey(row, c + 1), tile);
    }
  }

  // Place the new tile
  newGrid.set(cellKey(row, insertCol), tile);
  return newGrid;
}
```

### 4.7 — Auto-compact (for commit)

```typescript
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
```

-----

## 5. Phase 0 — Route & State Isolation

**Sprint:** 1 (Days 1-2)
**Goal:** `/play` route exists, play store is functional, puzzle loads into grid.

### 5.1 — Tasks

|#  |Task                                                                                  |File                                                |Est|
|---|--------------------------------------------------------------------------------------|----------------------------------------------------|---|
|0.1|Create play route page (minimal shell)                                                |`frontend/src/app/[locale]/play/page.tsx`           |1h |
|0.2|Create play types                                                                     |`frontend/src/types/play.ts`                        |1h |
|0.3|Implement grid-utils (puzzleToGrid, detectSets, checkSolved, validateTileConservation)|`frontend/src/lib/grid-utils.ts`                    |2h |
|0.4|Implement play-validation (validateTileGroup, validateAsRun, validateAsGroup)         |`frontend/src/lib/play-validation.ts`               |2h |
|0.5|Create play store with all state fields and loadPuzzle action                         |`frontend/src/store/play.ts`                        |3h |
|0.6|Wire PuzzleControls to work in play page (reuse component, different store binding)   |`frontend/src/app/[locale]/play/page.tsx`           |1h |
|0.7|Write unit tests for grid-utils                                                       |`frontend/src/__tests__/lib/grid-utils.test.ts`     |2h |
|0.8|Write unit tests for play-validation                                                  |`frontend/src/__tests__/lib/play-validation.test.ts`|1h |
|0.9|Write unit tests for play store                                                       |`frontend/src/__tests__/store/play.test.ts`         |2h |

### 5.2 — Play route page (minimal)

```tsx
// frontend/src/app/[locale]/play/page.tsx
"use client";

import { useTranslations } from "next-intl";
import { usePlayStore } from "../../../store/play";
import PuzzleControls from "../../../components/PuzzleControls";

export default function PlayPage() {
  const t = useTranslations("play");
  const grid = usePlayStore((s) => s.grid);
  const rack = usePlayStore((s) => s.rack);
  const detectedSets = usePlayStore((s) => s.detectedSets);

  return (
    <main className="h-dvh flex flex-col">
      <header className="p-2 border-b">
        <h1 className="text-lg font-bold">{t("title")}</h1>
      </header>
      {/* PuzzleControls needs to call playStore.loadPuzzle instead of gameStore.loadPuzzle.
          Solution: accept a loadPuzzle prop, or create PlayPuzzleControls wrapper. */}
      <div className="flex-1 flex items-center justify-center text-gray-400">
        {grid.size === 0
          ? t("loadPuzzlePrompt")
          : `Grid: ${grid.size} tiles, Rack: ${rack.length} tiles, Sets: ${detectedSets.length}`
        }
      </div>
    </main>
  );
}
```

> **⚠ DESIGN DECISION — PuzzleControls reuse:**
> The existing `PuzzleControls.tsx` is tightly coupled to `useGameStore`. Two options:
> 
> **Option A (Recommended):** Create `PlayPuzzleControls.tsx` that wraps `PuzzleControls`
> and overrides the store binding. This avoids modifying the existing component.
> 
> **Option B:** Refactor `PuzzleControls` to accept `loadPuzzle` as a prop.
> Cleaner long-term but touches the solver’s code path.
> 
> Go with Option A for Phase 0. Refactor to Option B in Phase 6 if desired.

### 5.3 — Play store implementation notes

```typescript
// frontend/src/store/play.ts

import { create } from "zustand";
import { fetchPuzzle } from "../lib/api";
import { puzzleToGrid, detectSets, checkSolved } from "../lib/grid-utils";
import type { PlayState, PlaySnapshot, CellKey, PlacedTile } from "../types/play";
import { cellKey, GRID_COLS, UNDO_MAX } from "../types/play";

const initialState = {
  puzzle: null,
  grid: new Map<CellKey, PlacedTile>(),
  gridRows: 6,
  gridCols: GRID_COLS,
  rack: [],
  detectedSets: [],
  isSolved: false,
  past: [],
  future: [],
  committedSnapshot: { cells: new Map(), rack: [] },
  selectedTile: null,
  interactionMode: "tap" as const,
  showValidation: true,
  isPuzzleLoading: false,
  error: null,
  solveStartTime: null,
  solveEndTime: null,
};

export const usePlayStore = create<PlayState>((set, get) => ({
  ...initialState,

  loadPuzzle: async (request, signal) => {
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

  // Remaining actions implemented in Phase 2
  tapCell: () => {},
  tapRackTile: () => {},
  returnToRack: () => {},
  undo: () => {},
  redo: () => {},
  commit: () => ({ ok: false, reason: "invalid_sets" } as const),
  revert: () => {},
  setInteractionMode: (mode) => set({ interactionMode: mode }),
  toggleValidation: () => set((s) => ({ showValidation: !s.showValidation })),
  reset: () => set(initialState),
}));
```

> **⚠ BUG RISK — Map serialization in Zustand devtools:**
> Zustand devtools use `JSON.stringify` for state snapshots. `Map` objects
> serialize to `{}`. This means devtools will show an empty grid.
> **Mitigation:** Either accept this limitation (Map is correct for runtime)
> or add a custom serializer. Not blocking — devtools are developer-only.

### 5.4 — Tests for Phase 0

**`frontend/src/__tests__/lib/grid-utils.test.ts`** (10 tests):

```
1. puzzleToGrid — maps single board set to row 0
2. puzzleToGrid — maps multiple board sets to consecutive rows
3. puzzleToGrid — sets all board tiles as source "board"
4. puzzleToGrid — creates workspace rows below content
5. puzzleToGrid — caps at GRID_MAX_ROWS
6. detectSets — finds one set for contiguous tiles in a row
7. detectSets — splits at empty cell gap
8. detectSets — finds two sets in same row with gap
9. detectSets — empty row produces no sets
10. detectSets — handles tiles in multiple rows independently
```

**`frontend/src/__tests__/lib/play-validation.test.ts`** (12 tests):

```
1. valid run — 3 same-color consecutive
2. valid run — with joker filling gap
3. invalid run — mixed colors
4. invalid run — duplicate numbers
5. invalid run — gap too large for jokers
6. valid group — 3 same-number different colors
7. valid group — 4 tiles
8. valid group — with joker
9. invalid group — duplicate colors
10. invalid group — mixed numbers
11. invalid group — 5 tiles
12. <3 tiles — returns isValid false, no reason
```

**`frontend/src/__tests__/store/play.test.ts`** (6 tests):

```
1. initial state shape matches expected defaults
2. play store is separate from game store (import both, verify independence)
3. loadPuzzle populates grid from puzzle board_sets
4. loadPuzzle populates rack from puzzle rack
5. loadPuzzle sets committedSnapshot
6. loadPuzzle rejects concurrent calls (isPuzzleLoading guard)
```

### 5.5 — Exit criteria

- [ ] `/play` route renders without errors
- [ ] Loading a puzzle via `loadPuzzle` populates `grid`, `rack`, `detectedSets`
- [ ] All 28 unit tests pass
- [ ] Existing solver tests (104 Vitest + 5 E2E) pass unchanged
- [ ] `game.ts` has zero modifications

-----

## 6. Phase 1 — Grid Rendering & iPad Layout

**Sprint:** 1-2 (Days 3-5)
**Goal:** Visual grid renders on screen. iPad-responsive layout. Touch hardening applied.

### 6.1 — Tasks

|#  |Task                                               |File                                         |Est |
|---|---------------------------------------------------|---------------------------------------------|----|
|1.1|Create PlayLayout (CSS Grid shell)                 |`frontend/src/components/play/PlayLayout.tsx`|2h  |
|1.2|Create ControlBar (undo/redo/commit/revert buttons)|`frontend/src/components/play/ControlBar.tsx`|1h  |
|1.3|Create PlayGrid (2D cell grid rendering)           |`frontend/src/components/play/PlayGrid.tsx`  |3h  |
|1.4|Create GridCell (single cell component)            |`frontend/src/components/play/GridCell.tsx`  |1h  |
|1.5|Create PlayRack (rack panel)                       |`frontend/src/components/play/PlayRack.tsx`  |1h  |
|1.6|Create SetOverlay (validation borders)             |`frontend/src/components/play/SetOverlay.tsx`|1h  |
|1.7|Add touch hardening CSS                            |`frontend/src/app/globals.css`               |0.5h|
|1.8|Wire components into play page                     |`frontend/src/app/[locale]/play/page.tsx`    |1h  |
|1.9|Write component tests                              |`frontend/src/__tests__/components/play/`    |2h  |

### 6.2 — Layout CSS

```css
/* Add to frontend/src/app/globals.css */

/* ── Play mode touch hardening (scoped to play route only) ── */
.play-surface {
  touch-action: none;
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
  -webkit-tap-highlight-color: transparent;
}

.play-rack-scroll {
  touch-action: pan-y;
  -webkit-overflow-scrolling: touch;
}

/* ── Play layout ── */
.play-layout {
  height: 100dvh;
  padding:
    max(8px, env(safe-area-inset-top))
    max(8px, env(safe-area-inset-right))
    max(8px, env(safe-area-inset-bottom))
    max(8px, env(safe-area-inset-left));
  display: grid;
  grid-template-rows: auto 1fr;
  grid-template-areas:
    "controls"
    "main";
  gap: 8px;
}

/* Landscape: board + rack side by side */
@media (min-width: 1024px) {
  .play-layout {
    grid-template-columns: 1fr 200px;
    grid-template-rows: auto 1fr;
    grid-template-areas:
      "controls controls"
      "board    rack";
  }
}

/* Portrait: board on top, rack below */
@media (max-width: 1023px) {
  .play-layout {
    grid-template-rows: auto 1fr auto;
    grid-template-areas:
      "controls"
      "board"
      "rack";
  }
}
```

### 6.3 — PlayGrid component

```tsx
// frontend/src/components/play/PlayGrid.tsx
"use client";

import { useMemo } from "react";
import type { CellKey, PlacedTile, DetectedSet } from "../../types/play";
import { cellKey, CELL_SIZE_PX, CELL_GAP_PX } from "../../types/play";
import GridCell from "./GridCell";
import SetOverlay from "./SetOverlay";

interface Props {
  grid: Map<CellKey, PlacedTile>;
  rows: number;
  cols: number;
  detectedSets: DetectedSet[];
  selectedTile: import("../../types/play").TileSelection;
  showValidation: boolean;
  onCellClick: (row: number, col: number) => void;
}

export default function PlayGrid({
  grid, rows, cols, detectedSets, selectedTile, showValidation, onCellClick,
}: Props) {
  // Lookup: which DetectedSet does each cell belong to?
  const cellSetMap = useMemo(() => {
    const map = new Map<CellKey, DetectedSet>();
    for (const ds of detectedSets) {
      for (let i = 0; i < ds.tiles.length; i++) {
        map.set(cellKey(ds.row, ds.startCol + i), ds);
      }
    }
    return map;
  }, [detectedSets]);

  const cellPx = CELL_SIZE_PX + CELL_GAP_PX;

  return (
    <div className="play-surface overflow-auto relative" style={{ gridArea: "board" }}>
      <div
        className="relative"
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${cols}, ${CELL_SIZE_PX}px)`,
          gridTemplateRows: `repeat(${rows}, ${CELL_SIZE_PX}px)`,
          gap: `${CELL_GAP_PX}px`,
          width: cols * cellPx,
          height: rows * cellPx,
        }}
      >
        {/* Validation overlays (behind cells) */}
        {showValidation &&
          detectedSets.map((ds, i) => (
            <SetOverlay key={`set-${i}`} set={ds} />
          ))}

        {/* Grid cells */}
        {Array.from({ length: rows * cols }, (_, i) => {
          const row = Math.floor(i / cols);
          const col = i % cols;
          const key = cellKey(row, col);
          const placed = grid.get(key) ?? null;
          const isSelected =
            selectedTile?.source === "grid" &&
            selectedTile.row === row &&
            selectedTile.col === col;
          const hasSelection = selectedTile !== null;

          return (
            <GridCell
              key={key}
              row={row}
              col={col}
              placed={placed}
              isSelected={isSelected}
              isDropTarget={hasSelection && !placed}
              onClick={() => onCellClick(row, col)}
            />
          );
        })}
      </div>
    </div>
  );
}
```

> **⚠ PERFORMANCE RISK — Rendering all cells:**
> A 16×24 grid = 384 cells. Each re-renders on every grid change. This is
> fine for tap interactions (one render per action) but could be sluggish
> during drag (renders at 60fps).
> 
> **Mitigation for Phase 4:** Memoize `GridCell` with `React.memo` and ensure
> props are referentially stable. The `placed` prop changes only for affected
> cells (Map lookup is O(1)). The `isDropTarget` boolean changes for all cells
> when selection changes — consider splitting this into a CSS class toggled
> via a parent className rather than a per-cell prop.

### 6.4 — GridCell component

```tsx
// frontend/src/components/play/GridCell.tsx
"use client";

import { memo } from "react";
import type { PlacedTile } from "../../types/play";
import Tile from "../Tile";

interface Props {
  row: number;
  col: number;
  placed: PlacedTile | null;
  isSelected: boolean;
  isDropTarget: boolean;
  onClick: () => void;
}

export default memo(function GridCell({
  row, col, placed, isSelected, isDropTarget, onClick,
}: Props) {
  const baseClass = "w-12 h-12 rounded border flex items-center justify-center";

  if (placed) {
    return (
      <div
        className={`${baseClass} cursor-pointer ${isSelected ? "ring-2 ring-blue-500 ring-offset-1" : ""}`}
        onClick={onClick}
        data-row={row}
        data-col={col}
        data-slot-cell
      >
        <Tile
          color={placed.tile.color ?? null}
          number={placed.tile.number ?? null}
          isJoker={placed.tile.joker ?? false}
          size="sm"
        />
      </div>
    );
  }

  return (
    <div
      className={`${baseClass} ${isDropTarget
        ? "border-dashed border-green-300 dark:border-green-700 bg-green-50/50 dark:bg-green-900/20 cursor-pointer"
        : "border-gray-200 dark:border-gray-800"
      }`}
      onClick={onClick}
      data-row={row}
      data-col={col}
      data-slot-cell
    />
  );
});
```

### 6.5 — Tests for Phase 1

**`frontend/src/__tests__/components/play/PlayGrid.test.tsx`** (8 tests):

```
1. renders correct total number of cells (rows × cols)
2. occupied cells render Tile component
3. empty cells render as empty divs
4. selected cell has ring-blue-500 class
5. drop-target cells have border-dashed class when selection active
6. cells without selection have no drop-target styling
7. clicking a cell calls onCellClick with correct row/col
8. grid container has play-surface class (touch hardening)
```

### 6.6 — Exit criteria

- [ ] Grid renders on screen with tiles from a loaded puzzle
- [ ] Layout responds to viewport changes (landscape ↔ portrait)
- [ ] Controls bar visible with all 4 buttons
- [ ] Rack panel shows remaining tiles
- [ ] Touch hardening CSS applied to grid surface
- [ ] All buttons ≥ 44px touch target
- [ ] All Phase 1 tests pass

-----

## 7. Phase 2 — Tap-to-Place Interaction

**Sprint:** 2 (Days 6-9)
**Goal:** Users can select tiles from rack or grid, place them by tapping empty cells. Undo/redo works.

### 7.1 — Tasks

|#   |Task                                                                 |File                                         |Est |
|----|---------------------------------------------------------------------|---------------------------------------------|----|
|2.1 |Implement `tapRackTile` action                                       |`frontend/src/store/play.ts`                 |1h  |
|2.2 |Implement `tapCell` action (place or pick up)                        |`frontend/src/store/play.ts`                 |3h  |
|2.3 |Implement `returnToRack` action                                      |`frontend/src/store/play.ts`                 |0.5h|
|2.4 |Implement `undo` / `redo` actions                                    |`frontend/src/store/play.ts`                 |1h  |
|2.5 |Implement snapshot helpers (takeSnapshot, applySnapshot)             |`frontend/src/store/play.ts`                 |1h  |
|2.6 |Wire `tapCell` and `tapRackTile` to PlayGrid and PlayRack            |`frontend/src/app/[locale]/play/page.tsx`    |1h  |
|2.7 |Add visual feedback for selected rack tile (blue ring)               |`frontend/src/components/play/PlayRack.tsx`  |0.5h|
|2.8 |Add “return to rack” button when rack-source tile is selected on grid|`frontend/src/components/play/ControlBar.tsx`|0.5h|
|2.9 |Start solve timer on first placement                                 |`frontend/src/store/play.ts`                 |0.5h|
|2.10|Write interaction tests                                              |`frontend/src/__tests__/store/play.test.ts`  |3h  |

### 7.2 — Store action implementations

```typescript
// Add to frontend/src/store/play.ts inside the create() callback:

tapRackTile: (index) =>
  set((state) => {
    // Toggle selection
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

    // ── No selection active ────────────────────────────────────────
    if (!state.selectedTile) {
      if (existing) {
        // Pick up this tile
        return { selectedTile: { source: "grid", row, col } };
      }
      return {}; // tapped empty cell with no selection — do nothing
    }

    // ── Selection active, cell is occupied ─────────────────────────
    if (existing) {
      // Tapped a different occupied cell — switch selection to it
      if (
        state.selectedTile.source === "grid" &&
        state.selectedTile.row === row &&
        state.selectedTile.col === col
      ) {
        return { selectedTile: null }; // deselect
      }
      return { selectedTile: { source: "grid", row, col } };
    }

    // ── Selection active, cell is empty — PLACE the tile ───────────
    return placeTile(state, row, col);
  }),

returnToRack: () =>
  set((state) => {
    if (!state.selectedTile || state.selectedTile.source !== "grid") return {};

    const { row, col } = state.selectedTile;
    const key = cellKey(row, col);
    const placed = state.grid.get(key);
    if (!placed) return {};

    // RULE: board-source tiles cannot return to rack
    if (placed.source === "board") return {};

    // Snapshot for undo
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
      isSolved: false,
      past: [...state.past, snapshot].slice(-UNDO_MAX),
      future: [],
    };
  }),

undo: () =>
  set((state) => {
    if (state.past.length === 0) return {};
    const snapshot = state.past[state.past.length - 1];
    const futureSS = takeSnapshot(state);

    const detected = detectSets(
      snapshot.cells,
      state.gridRows,
      state.gridCols,
    );

    return {
      grid: snapshot.cells,
      rack: snapshot.rack,
      detectedSets: detected,
      isSolved: checkSolved(snapshot.cells, snapshot.rack, detected),
      past: state.past.slice(0, -1),
      future: [...state.future, futureSS],
      selectedTile: null,
    };
  }),

redo: () =>
  set((state) => {
    if (state.future.length === 0) return {};
    const snapshot = state.future[state.future.length - 1];
    const pastSS = takeSnapshot(state);

    const detected = detectSets(
      snapshot.cells,
      state.gridRows,
      state.gridCols,
    );

    return {
      grid: snapshot.cells,
      rack: snapshot.rack,
      detectedSets: detected,
      isSolved: checkSolved(snapshot.cells, snapshot.rack, detected),
      past: [...state.past, pastSS],
      future: state.future.slice(0, -1),
      selectedTile: null,
    };
  }),
```

**The `placeTile` helper (internal, not exported):**

```typescript
function placeTile(
  state: PlayState,
  targetRow: number,
  targetCol: number,
): Partial<PlayState> {
  const sel = state.selectedTile!;
  const targetKey = cellKey(targetRow, targetCol);

  // Guard: cell must be empty
  if (state.grid.has(targetKey)) return {};

  const snapshot = takeSnapshot(state);
  const newGrid = new Map(state.grid);
  let newRack = [...state.rack];

  if (sel.source === "rack") {
    const tile = state.rack[sel.index];
    newGrid.set(targetKey, { tile, source: "rack" });
    newRack = newRack.filter((_, i) => i !== sel.index);
  } else {
    // Moving a grid tile
    const srcKey = cellKey(sel.row, sel.col);
    const srcTile = state.grid.get(srcKey);
    if (!srcTile) return {}; // safety guard
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
    future: [],
    solveStartTime: state.solveStartTime ?? Date.now(),
    solveEndTime: solved ? Date.now() : null,
  };
}

function takeSnapshot(state: PlayState): PlaySnapshot {
  return {
    cells: new Map(state.grid),
    rack: [...state.rack],
  };
}
```

> **⚠ BUG RISK — Map shallow copy semantics:**
> `new Map(state.grid)` creates a new Map with the same entries. Since
> `PlacedTile` is a plain object with immutable `TileInput` inside, this
> is safe — we never mutate `PlacedTile` objects, we only add/remove Map
> entries. If anyone adds mutable fields to `PlacedTile` in the future,
> this breaks. **Guard: keep PlacedTile immutable (readonly fields).**

> **⚠ RACE CONDITION — Rapid taps:**
> Zustand’s `set()` is synchronous and batched within React’s render cycle.
> Two rapid taps in the same frame could theoretically both read the same
> `state` before either write lands. In practice this is near-impossible
> because each tap triggers a re-render before the next tap handler fires.
> **Mitigation:** None needed. Zustand guarantees consistent reads within
> each `set()` callback.

### 7.3 — Tests for Phase 2

**Add to `frontend/src/__tests__/store/play.test.ts`** (14 tests):

```
1. tapRackTile selects tile (sets selectedTile)
2. tapRackTile on already-selected tile deselects
3. tapRackTile on different tile switches selection
4. tapCell on empty cell with rack selection places tile
5. placed tile removed from rack
6. placed tile appears in grid at correct key
7. tapCell on occupied cell with no selection picks it up
8. tapCell on occupied cell then empty cell moves tile
9. board-source tile move: stays source "board" after move
10. returnToRack with board-source tile is no-op
11. returnToRack with rack-source tile returns to rack
12. undo reverses last placement (tile back in rack, cell empty)
13. redo re-applies undone action
14. new action after undo clears future stack
```

### 7.4 — Exit criteria

- [ ] User can tap a rack tile to select it (visual indicator)
- [ ] User can tap an empty grid cell to place the selected tile
- [ ] User can tap a grid tile to pick it up, then tap another cell to move it
- [ ] Undo/redo work correctly for all tile operations
- [ ] Board-source tiles cannot be returned to rack
- [ ] Timer starts on first placement
- [ ] All Phase 2 tests pass

-----

## 8. Phase 3 — Validation Overlays & Turn Sandbox

**Sprint:** 2-3 (Days 10-12)
**Goal:** Real-time validation feedback. Commit/revert sandbox. Puzzle completion detection.

### 8.1 — Tasks

|#  |Task                                                |File                                           |Est |
|---|----------------------------------------------------|-----------------------------------------------|----|
|3.1|Implement SetOverlay with color-coded borders       |`frontend/src/components/play/SetOverlay.tsx`  |2h  |
|3.2|Add validation reason labels to SetOverlay          |`frontend/src/components/play/SetOverlay.tsx`  |1h  |
|3.3|Implement `commit` action with validation gate      |`frontend/src/store/play.ts`                   |1.5h|
|3.4|Implement `revert` action with confirmation         |`frontend/src/store/play.ts`                   |1h  |
|3.5|Add commit/revert button states (disabled + tooltip)|`frontend/src/components/play/ControlBar.tsx`  |1.5h|
|3.6|Add “Validation” toggle button to ControlBar        |`frontend/src/components/play/ControlBar.tsx`  |0.5h|
|3.7|Create SolvedBanner component                       |`frontend/src/components/play/SolvedBanner.tsx`|1h  |
|3.8|Wire isSolved to show SolvedBanner                  |`frontend/src/app/[locale]/play/page.tsx`      |0.5h|
|3.9|Write tests                                         |Various test files                             |2.5h|

### 8.2 — SetOverlay component

```tsx
// frontend/src/components/play/SetOverlay.tsx
"use client";

import { memo } from "react";
import { useTranslations } from "next-intl";
import type { DetectedSet } from "../../types/play";

interface Props {
  set: DetectedSet;
}

export default memo(function SetOverlay({ set }: Props) {
  const t = useTranslations("play");
  const { validation, row, startCol, tiles } = set;

  const isIncomplete = tiles.length < 3;
  const isValid = !isIncomplete && validation.isValid;
  const isInvalid = !isIncomplete && !validation.isValid;

  const borderClass = isIncomplete
    ? "border-amber-300 dark:border-amber-700"
    : isValid
      ? "border-green-400 dark:border-green-700"
      : "border-red-400 dark:border-red-700";

  const bgClass = isIncomplete
    ? "bg-amber-50/40 dark:bg-amber-900/15"
    : isValid
      ? "bg-green-50/40 dark:bg-green-900/15"
      : "bg-red-50/40 dark:bg-red-900/15";

  return (
    <div
      className={`absolute rounded-lg border-2 ${borderClass} ${bgClass} pointer-events-none z-0`}
      style={{
        gridRow: row + 1,
        gridColumn: `${startCol + 1} / span ${tiles.length}`,
      }}
    >
      {/* Type label — bottom-left */}
      {isValid && validation.type && (
        <span className="absolute -bottom-4 left-1 text-[9px] font-medium text-green-600 dark:text-green-400">
          {validation.type}
        </span>
      )}
      {isInvalid && validation.reason && (
        <span className="absolute -bottom-4 left-1 text-[9px] font-medium text-red-500 dark:text-red-400 whitespace-nowrap">
          {t(validation.reason as Parameters<typeof t>[0])}
        </span>
      )}
    </div>
  );
});
```

### 8.3 — Commit / Revert implementation

```typescript
// Add to store/play.ts:

commit: () => {
  const state = get();

  // Gate 1: no invalid sets
  const hasInvalid = state.detectedSets.some(
    (ds) => ds.tiles.length >= 3 && !ds.validation.isValid,
  );
  if (hasInvalid) return { ok: false as const, reason: "invalid_sets" as const };

  // Gate 2: no incomplete groups (lone tiles or pairs on the grid)
  const hasIncomplete = state.detectedSets.some(
    (ds) => ds.tiles.length > 0 && ds.tiles.length < 3,
  );
  if (hasIncomplete) return { ok: false as const, reason: "incomplete_sets" as const };

  set({
    committedSnapshot: takeSnapshot(state),
    past: [],
    future: [],
  });

  return { ok: true as const };
},

revert: () =>
  set((state) => {
    const snap = state.committedSnapshot;
    const detected = detectSets(snap.cells, state.gridRows, state.gridCols);
    return {
      grid: new Map(snap.cells),
      rack: [...snap.rack],
      detectedSets: detected,
      isSolved: false,
      past: [],
      future: [],
      selectedTile: null,
    };
  }),
```

> **⚠ BUG RISK — Commit returns a value but also calls set():**
> Zustand’s `set()` inside `commit` won’t work if `commit` is defined as a
> regular function that calls `get()` and `set()` separately (not inside
> the `set(state => ...)` callback pattern). This is because we need to
> both return a `CommitResult` AND mutate the store.
> 
> **Solution:** Define `commit` as a non-set function that reads with `get()`,
> validates, calls `set()` for the mutation, and returns the result:
> 
> ```typescript
> commit: () => {
>   const state = get();
>   // ... validation checks ...
>   if (hasInvalid) return { ok: false, reason: "invalid_sets" };
>   if (hasIncomplete) return { ok: false, reason: "incomplete_sets" };
>   set({
>     committedSnapshot: { cells: new Map(state.grid), rack: [...state.rack] },
>     past: [],
>     future: [],
>   });
>   return { ok: true };
> },
> ```

### 8.4 — ControlBar button states

```tsx
// frontend/src/components/play/ControlBar.tsx

interface Props {
  canUndo: boolean;      // past.length > 0
  canRedo: boolean;      // future.length > 0
  canCommit: CommitReadiness;
  onUndo: () => void;
  onRedo: () => void;
  onCommit: () => void;
  onRevert: () => void;
  interactionMode: "tap" | "drag";
  onModeToggle: () => void;
  showValidation: boolean;
  onValidationToggle: () => void;
}

type CommitReadiness =
  | { ready: true }
  | { ready: false; reason: string };

// Derive CommitReadiness in the page component:
function getCommitReadiness(detectedSets: DetectedSet[]): CommitReadiness {
  const invalid = detectedSets.some(
    (ds) => ds.tiles.length >= 3 && !ds.validation.isValid,
  );
  if (invalid) return { ready: false, reason: "play.commitBlocked.invalidSets" };

  const incomplete = detectedSets.some(
    (ds) => ds.tiles.length > 0 && ds.tiles.length < 3,
  );
  if (incomplete) return { ready: false, reason: "play.commitBlocked.incompleteSets" };

  return { ready: true };
}
```

### 8.5 — Tests for Phase 3

**`frontend/src/__tests__/store/play.test.ts`** (add 10 tests):

```
1. commit succeeds when all sets valid and no loose tiles
2. commit returns { ok: false, reason: "invalid_sets" } when invalid set exists
3. commit returns { ok: false, reason: "incomplete_sets" } when pair exists on grid
4. commit clears undo/redo history
5. commit updates committedSnapshot
6. revert restores committedSnapshot grid
7. revert restores committedSnapshot rack
8. revert clears undo/redo history
9. isSolved true when rack empty + all sets valid
10. isSolved false when rack has tiles remaining
```

**`frontend/src/__tests__/components/play/SetOverlay.test.tsx`** (4 tests):

```
1. valid set renders green border class
2. invalid set renders red border class
3. incomplete set renders amber border class
4. valid set shows type label ("run" or "group")
```

### 8.6 — Exit criteria

- [ ] Valid sets show green overlay
- [ ] Invalid sets show red overlay with error reason
- [ ] Incomplete groups (<3 tiles) show amber overlay
- [ ] Commit button disabled with tooltip when validation fails
- [ ] Commit saves current state as committed
- [ ] Revert restores to committed state
- [ ] Puzzle solved detection works (banner appears)
- [ ] All Phase 3 tests pass

-----

## 9. Phase 4 — Drag-and-Drop Layer

**Sprint:** 3-4 (Days 13-17)
**Goal:** Optional drag-and-drop mode for power users. Toggle on/off. Tap always works.

### 9.1 — Tasks

|#  |Task                                                            |File                                                |Est|
|---|----------------------------------------------------------------|----------------------------------------------------|---|
|4.1|Create DragController (state machine, extracted for testability)|`frontend/src/lib/drag-controller.ts`               |4h |
|4.2|Create GhostTile (drag preview overlay)                         |`frontend/src/components/play/GhostTile.tsx`        |1h |
|4.3|Create SnapPreview (target cell highlight during drag)          |`frontend/src/components/play/SnapPreview.tsx`      |1h |
|4.4|Integrate Pointer Events into GridCell and PlayRack             |Various                                             |3h |
|4.5|Add hitTestGrid utility                                         |`frontend/src/lib/grid-utils.ts`                    |1h |
|4.6|Add visibility/resize cancel listeners                          |`frontend/src/app/[locale]/play/page.tsx`           |1h |
|4.7|Performance optimization (React.memo, RAF throttle)             |Various                                             |2h |
|4.8|Write drag controller tests                                     |`frontend/src/__tests__/lib/drag-controller.test.ts`|3h |

### 9.2 — DragController

```typescript
// frontend/src/lib/drag-controller.ts

export interface DragCallbacks {
  onDragStart: (origin: DragOrigin, tile: PlacedTile) => void;
  onDragMove: (clientX: number, clientY: number, snapTarget: { row: number; col: number } | null) => void;
  onDrop: (row: number, col: number) => void;
  onCancel: () => void;
}

export interface DragOrigin {
  source: "rack" | "grid";
  rackIndex?: number;
  gridRow?: number;
  gridCol?: number;
}

const THRESHOLD_PX = 10;
const WATCHDOG_MS = 3000;

export class DragController {
  private status: "idle" | "pending" | "dragging" = "idle";
  private pointerId: number | null = null;
  private origin: DragOrigin | null = null;
  private tile: PlacedTile | null = null;
  private startX = 0;
  private startY = 0;
  private watchdogTimer: ReturnType<typeof setTimeout> | null = null;
  private rafId: number | null = null;
  private callbacks: DragCallbacks;
  private hitTest: (x: number, y: number) => { row: number; col: number } | null;

  constructor(callbacks: DragCallbacks, hitTest: typeof this.hitTest) {
    this.callbacks = callbacks;
    this.hitTest = hitTest;
  }

  handlePointerDown(e: PointerEvent, origin: DragOrigin, tile: PlacedTile): void {
    // Force-cleanup any stale state (defensive)
    if (this.status !== "idle") this.cleanup();

    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    this.status = "pending";
    this.pointerId = e.pointerId;
    this.origin = origin;
    this.tile = tile;
    this.startX = e.clientX;
    this.startY = e.clientY;
  }

  handlePointerMove(e: PointerEvent): void {
    if (this.pointerId !== e.pointerId) return;

    if (this.status === "pending") {
      const dx = e.clientX - this.startX;
      const dy = e.clientY - this.startY;
      if (Math.hypot(dx, dy) > THRESHOLD_PX) {
        this.status = "dragging";
        this.callbacks.onDragStart(this.origin!, this.tile!);
        this.resetWatchdog();
      }
    }

    if (this.status === "dragging") {
      // Throttle to RAF
      if (this.rafId !== null) cancelAnimationFrame(this.rafId);
      this.rafId = requestAnimationFrame(() => {
        const snap = this.hitTest(e.clientX, e.clientY);
        this.callbacks.onDragMove(e.clientX, e.clientY, snap);
        this.rafId = null;
      });
      this.resetWatchdog();
    }
  }

  handlePointerUp(e: PointerEvent): void {
    if (this.pointerId !== e.pointerId) return;

    if (this.status === "pending") {
      // Sub-threshold: treat as tap — caller handles via normal click path
      this.cleanup();
      return;
    }

    if (this.status === "dragging") {
      const target = this.hitTest(e.clientX, e.clientY);
      if (target) {
        this.callbacks.onDrop(target.row, target.col);
      } else {
        this.callbacks.onCancel();
      }
      this.cleanup();
    }
  }

  handlePointerCancel(_e: PointerEvent): void {
    if (this.status === "dragging") {
      this.callbacks.onCancel();
    }
    this.cleanup();
  }

  /** Force-cancel from external events (visibility change, resize, etc.) */
  forceCancel(): void {
    if (this.status === "dragging") {
      this.callbacks.onCancel();
    }
    this.cleanup();
  }

  getStatus(): "idle" | "pending" | "dragging" {
    return this.status;
  }

  private resetWatchdog(): void {
    if (this.watchdogTimer) clearTimeout(this.watchdogTimer);
    this.watchdogTimer = setTimeout(() => {
      if (this.status === "dragging") {
        this.callbacks.onCancel();
        this.cleanup();
      }
    }, WATCHDOG_MS);
  }

  private cleanup(): void {
    if (this.watchdogTimer) clearTimeout(this.watchdogTimer);
    if (this.rafId !== null) cancelAnimationFrame(this.rafId);
    this.status = "idle";
    this.pointerId = null;
    this.origin = null;
    this.tile = null;
    this.watchdogTimer = null;
    this.rafId = null;
  }
}
```

### 9.3 — hitTestGrid

```typescript
// Add to frontend/src/lib/grid-utils.ts:

export function hitTestGrid(
  clientX: number,
  clientY: number,
  gridElement: HTMLElement | null,
  cols: number,
  rows: number,
): { row: number; col: number } | null {
  if (!gridElement) return null;

  const rect = gridElement.getBoundingClientRect();
  const cellPx = CELL_SIZE_PX + CELL_GAP_PX;

  const col = Math.floor((clientX - rect.left) / cellPx);
  const row = Math.floor((clientY - rect.top) / cellPx);

  if (col < 0 || col >= cols || row < 0 || row >= rows) return null;
  return { row, col };
}
```

### 9.4 — Global cancel listeners

```typescript
// In play/page.tsx useEffect:

useEffect(() => {
  const onVisibilityChange = () => {
    if (document.hidden) dragControllerRef.current?.forceCancel();
  };
  const onResize = () => {
    dragControllerRef.current?.forceCancel();
  };

  document.addEventListener("visibilitychange", onVisibilityChange);
  window.addEventListener("resize", onResize);

  // Also prevent context menu on the grid
  const onContextMenu = (e: Event) => {
    if ((e.target as HTMLElement).closest(".play-surface")) {
      e.preventDefault();
    }
  };
  document.addEventListener("contextmenu", onContextMenu);

  return () => {
    document.removeEventListener("visibilitychange", onVisibilityChange);
    window.removeEventListener("resize", onResize);
    document.removeEventListener("contextmenu", onContextMenu);
  };
}, []);
```

> **⚠ BUG RISK — Ghost tile position during scroll:**
> If the grid container scrolls while dragging, the ghost tile (positioned
> with `position: fixed` and client coordinates) will be correct, but the
> snap preview (positioned within the grid’s CSS grid) will be offset by
> the scroll amount. The `hitTestGrid` function uses `getBoundingClientRect()`
> which accounts for scroll, so the drop target is correct — but the visual
> preview may appear shifted.
> 
> **Mitigation:** During active drag, disable grid scrolling entirely
> (set `overflow: hidden` on the grid container). Re-enable on drop/cancel.

> **⚠ RACE CONDITION — Drag start + React re-render:**
> When a drag starts, `onDragStart` mutates state (marks the source tile as
> “being dragged”). This triggers a React re-render. If the re-render is slow
> enough that a `pointermove` fires before it completes, the ghost tile may
> flash at the wrong position for one frame.
> 
> **Mitigation:** The ghost tile reads `clientX/clientY` from the drag
> controller (which updates synchronously on every pointermove), not from
> React state. The React state update only controls visibility.

### 9.5 — Tests for Phase 4

**`frontend/src/__tests__/lib/drag-controller.test.ts`** (10 tests):

```
1. pointerdown sets status to "pending"
2. pointermove below threshold stays "pending"
3. pointermove above threshold transitions to "dragging", calls onDragStart
4. pointerup during "pending" transitions to "idle" (treated as tap)
5. pointerup during "dragging" on valid target calls onDrop
6. pointerup during "dragging" off-grid calls onCancel
7. pointercancel during "dragging" calls onCancel
8. watchdog fires after WATCHDOG_MS, calls onCancel
9. forceCancel() calls onCancel when dragging
10. cleanup resets all internal state
```

### 9.6 — Exit criteria

- [ ] Drag mode toggle visible and functional
- [ ] Sub-threshold movement treated as tap
- [ ] Ghost tile follows pointer during drag
- [ ] Snap preview highlights target cell
- [ ] Drop on valid cell places tile
- [ ] Drop off-grid returns tile to origin
- [ ] `pointercancel` returns tile cleanly
- [ ] Watchdog fires on 3s inactivity
- [ ] Visibility change cancels drag
- [ ] Orientation change cancels drag
- [ ] All Phase 4 tests pass

-----

## 10. Phase 5 — Board Rearrangement Polish

**Sprint:** 4 (Days 18-19)
**Goal:** Insert-shift, auto-compact, row management.

### 10.1 — Tasks

|#  |Task                                                                |File                                              |Est |
|---|--------------------------------------------------------------------|--------------------------------------------------|----|
|5.1|Implement insert-shift (Phase 5 only, not default)                  |`frontend/src/lib/grid-utils.ts`                  |1.5h|
|5.2|Implement auto-compact on commit                                    |`frontend/src/lib/grid-utils.ts` + `store/play.ts`|1.5h|
|5.3|Add “insert” mode toggle or gesture (e.g. long-press cell to insert)|`frontend/src/store/play.ts`                      |1h  |
|5.4|Auto-grow: add row when last row used                               |`frontend/src/store/play.ts`                      |0.5h|
|5.5|Write tests                                                         |Test files                                        |1.5h|

### 10.2 — Auto-grow logic

```typescript
// After every placeTile, check if we need more rows:
function maybeGrowGrid(
  grid: Map<CellKey, PlacedTile>,
  currentRows: number,
  cols: number,
): number {
  // Find the last row that has any tile
  let lastUsedRow = -1;
  for (const key of grid.keys()) {
    const row = parseInt(key.split(":")[0]);
    if (row > lastUsedRow) lastUsedRow = row;
  }

  const neededRows = lastUsedRow + GRID_WORKSPACE_ROWS + 1;
  return Math.max(currentRows, Math.min(neededRows, GRID_MAX_ROWS));
}
```

### 10.3 — Tests for Phase 5

```
1. insertTileIntoRow shifts tiles rightward
2. insertTileIntoRow at grid edge returns unchanged grid
3. compactGrid removes empty rows
4. compactGrid slides sets left (removes leading gaps)
5. compactGrid preserves gaps between sets in same row
6. auto-grow adds row when last row has tiles
7. auto-grow caps at GRID_MAX_ROWS
```

### 10.4 — Exit criteria

- [ ] Insert-shift works for inserting tiles into existing sets
- [ ] Auto-compact runs on commit, cleaning up the board
- [ ] Grid auto-grows when last row is used
- [ ] Grid respects maximum row count
- [ ] All Phase 5 tests pass

-----

## 11. Phase 6 — Completion, Polish & Ship

**Sprint:** 4-5 (Days 20-22)
**Goal:** Feature-complete. Polish. E2E tests. Ship.

### 11.1 — Tasks

|#   |Task                                                                |File                                            |Est |
|----|--------------------------------------------------------------------|------------------------------------------------|----|
|6.1 |SolvedBanner with time display + celebration                        |`frontend/src/components/play/SolvedBanner.tsx` |1.5h|
|6.2 |“Compare with solver” button (calls `/api/solve` on original puzzle)|`frontend/src/components/play/SolvedBanner.tsx` |1h  |
|6.3 |Navigation: “Play” link on solver page, “Solver” link on play page  |`frontend/src/app/[locale]/page.tsx` + play page|0.5h|
|6.4 |Persist interactionMode in localStorage                             |`frontend/src/store/play.ts`                    |0.5h|
|6.5 |`beforeunload` warning if unsaved progress                          |`frontend/src/app/[locale]/play/page.tsx`       |0.5h|
|6.6 |Add all i18n keys (en.json + de.json)                               |`frontend/src/i18n/messages/*.json`             |1.5h|
|6.7 |Keyboard shortcuts (Cmd+Z, Cmd+Shift+Z, Escape)                     |`frontend/src/app/[locale]/play/page.tsx`       |1h  |
|6.8 |Accessibility: aria-labels on grid cells                            |`frontend/src/components/play/GridCell.tsx`     |1h  |
|6.9 |Write E2E tests (6 specs)                                           |`frontend/e2e/play_*.spec.ts`                   |3h  |
|6.10|Manual iPad testing + bug fixes                                     |—                                               |2h  |

### 11.2 — SolvedBanner

```tsx
// frontend/src/components/play/SolvedBanner.tsx
"use client";

import { useTranslations } from "next-intl";

interface Props {
  solveTimeMs: number;
  onCompareWithSolver: () => void;
}

export default function SolvedBanner({ solveTimeMs, onCompareWithSolver }: Props) {
  const t = useTranslations("play");
  const seconds = Math.round(solveTimeMs / 1000);
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  const timeStr = minutes > 0
    ? `${minutes}m ${remainingSeconds}s`
    : `${remainingSeconds}s`;

  return (
    <div className="p-4 bg-green-50 dark:bg-green-900/30 border-2 border-green-400 dark:border-green-700 rounded-xl text-center space-y-2">
      <p className="text-2xl font-bold text-green-700 dark:text-green-300">
        🎉 {t("solved")}
      </p>
      <p className="text-sm text-green-600 dark:text-green-400">
        {t("solveTime", { time: timeStr })}
      </p>
      <button
        onClick={onCompareWithSolver}
        className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
      >
        {t("compareWithSolver")}
      </button>
    </div>
  );
}
```

### 11.3 — Keyboard shortcuts

```typescript
// In play/page.tsx useEffect:
useEffect(() => {
  const handler = (e: KeyboardEvent) => {
    if (e.key === "z" && (e.metaKey || e.ctrlKey) && e.shiftKey) {
      e.preventDefault();
      redo();
    } else if (e.key === "z" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      undo();
    } else if (e.key === "Escape") {
      clearSelection();
    }
  };
  window.addEventListener("keydown", handler);
  return () => window.removeEventListener("keydown", handler);
}, [undo, redo, clearSelection]);
```

> **⚠ BUG RISK — beforeunload on iPad Safari:**
> Safari on iOS does not reliably fire `beforeunload`. The page may be
> evicted from memory without warning. **Mitigation:** Auto-save progress
> to `sessionStorage` on every action (debounced by 500ms). Restore on
> page load if session data exists. This covers both browser close AND
> Safari’s aggressive page eviction.

### 11.4 — E2E tests

**`frontend/e2e/play_load_puzzle.spec.ts`:**

```typescript
test("loads a puzzle and shows tiles on the grid", async ({ page }) => {
  await page.goto("/play");
  await page.locator("summary", { hasText: /Practice Puzzle/i }).click();
  await page.getByRole("button", { name: /Easy/i }).click();
  await page.getByRole("button", { name: /Get Puzzle/i }).click();
  // Grid should have tiles (data-slot-cell with Tile children)
  await expect(page.locator("[data-slot-cell] .bg-tile-red, [data-slot-cell] .bg-tile-blue").first())
    .toBeVisible({ timeout: 10_000 });
});
```

**Additional E2E specs:**

```
2. play_tap_place.spec.ts — Tap rack tile, tap grid cell, verify tile moved
3. play_undo_redo.spec.ts — Place, undo, verify rack restored, redo, verify placed
4. play_validation.spec.ts — Build invalid set (mixed colors in run), verify red border
5. play_commit_revert.spec.ts — Place tiles, commit, move more, revert, verify state
6. play_solve.spec.ts — Load easy puzzle, solve it fully, verify solved banner
```

### 11.5 — Exit criteria

- [ ] Solved banner appears on completion with correct time
- [ ] “Compare with solver” calls `/api/solve` and shows result
- [ ] Navigation links between solver and play mode work
- [ ] Keyboard shortcuts work (desktop)
- [ ] Grid cells have aria-labels
- [ ] All i18n keys present in en.json and de.json
- [ ] All 6 E2E tests pass
- [ ] All unit tests pass (target: 60+ new tests)
- [ ] Manual iPad testing passes (see checklist in §13)

-----

## 12. Bug & Race Condition Register

This section catalogs every known risk, its trigger condition, and its mitigation.

### BUG-001: Stuck tile after pointercancel

**Trigger:** iOS fires `pointercancel` (notification, home bar, Split View). If cleanup fails, a tile visually “sticks” mid-drag.

**Mitigation:**

1. `pointercancel` handler always calls `cleanup()` + `onCancel()`
1. Watchdog timer (3s) as backup
1. `visibilitychange` listener as second backup
1. `DragController.forceCancel()` called from all external interrupt handlers

**Test:** drag-controller.test.ts #7, #8, #9

### BUG-002: Map shallow copy vs deep copy

**Trigger:** If `PlacedTile` objects are mutated after snapshot, undo would restore a mutated reference.

**Mitigation:** `PlacedTile` is structurally immutable (only `tile: TileInput` and `source: string`). We never mutate these — we only add/delete Map entries. Document this invariant.

**Test:** play.test.ts — undo restores correct tile (verify by value, not reference)

### BUG-003: Tile conservation violation

**Trigger:** A bug in `placeTile` could create or destroy tiles (e.g. placing from rack without removing from rack array).

**Mitigation:** `validateTileConservation()` runs on every commit as an integrity check. If it fails, commit is blocked and an error is logged.

**Test:** play.test.ts — commit with conservation violation is blocked

### BUG-004: Concurrent loadPuzzle calls

**Trigger:** User double-taps “Get Puzzle” before the first request returns. Second response could overwrite the first.

**Mitigation:** `isPuzzleLoading` guard at top of `loadPuzzle`. `AbortController` cancels in-flight request. Same pattern as existing `game.ts`.

**Test:** play.test.ts #6

### BUG-005: Grid cell index collision

**Trigger:** `cellKey(row, col)` produces `"1:2"` for both `(1, 2)` and potentially malformed inputs.

**Mitigation:** `cellKey` is a typed function returning `CellKey` template literal type. Rows and cols are always non-negative integers from bounded loops.

**Test:** grid-utils.test.ts — cellKey produces correct format

### BUG-006: Redo stack not cleared on new action

**Trigger:** User undoes 3 actions, then does a new action. If `future` isn’t cleared, redo would restore an inconsistent state.

**Mitigation:** Every mutating action sets `future: []`. This is in the `placeTile`, `returnToRack`, and `tapCell` code paths.

**Test:** play.test.ts #14

### BUG-007: Timer continues after tab loses focus

**Trigger:** User switches to another app, timer keeps counting.

**Mitigation:** Timer is computed as `solveEndTime - solveStartTime`, both set via `Date.now()`. If the user goes away and comes back, the time includes idle time. This is acceptable for v1 — a proper pause/resume timer is Phase 7+.

**Test:** None (accepted limitation)

### BUG-008: detectSets performance on large grids

**Trigger:** 24 rows × 16 cols = 384 cells scanned per state change. During drag, this runs at 60fps.

**Mitigation:** `detectSets` is O(rows × cols) = O(384) — trivially fast (<0.1ms). During drag, only call `detectSets` on drop (not on every pointermove). During pointermove, only compute a local snap preview.

**Test:** None (performance is negligible at this scale)

### BUG-009: React.memo invalidation from Map reference

**Trigger:** `new Map(state.grid)` creates a new reference on every state update, causing all `GridCell` components to re-render even if their specific cell didn’t change.

**Mitigation:** `GridCell` is wrapped in `React.memo`. Its props include `placed: PlacedTile | null` (the value from the Map for its cell) and a few booleans. These are referentially stable for unchanged cells because the `PlacedTile` reference is preserved by `new Map()` for entries that weren’t modified.

**Test:** None (React.memo optimization — verify visually via React DevTools Profiler)

### BUG-010: beforeunload unreliable on iOS Safari

**Trigger:** Safari may evict the page without firing `beforeunload`, losing unsaved play state.

**Mitigation:** Debounced auto-save to `sessionStorage` (500ms after each action). On page load, check for session data and offer to restore. Max storage: ~50KB (well within quota).

**Test:** E2E — manual verification on iPad

### BUG-011: Puzzle with two identical tiles — identity ambiguity

**Trigger:** A puzzle may have two copies of the same tile (e.g. two Red 5s). When both are on the grid, `tileIdentityKey` cannot distinguish them.

**Mitigation:** This only matters for the conservation check, which uses multiset counts (not identity). For grid placement, tiles are distinguished by their Map key (position). For display, they look identical — which is correct (they ARE identical in physical Rummikub).

**Test:** play-validation.test.ts — conservation check with duplicate tiles

-----

## 13. Testing Strategy

### Unit test breakdown (target: 69 tests)

|File                                       |Tests|Phase|
|-------------------------------------------|-----|-----|
|`grid-utils.test.ts`                       |10   |0    |
|`play-validation.test.ts`                  |12   |0    |
|`store/play.test.ts` — init + loadPuzzle   |6    |0    |
|`components/play/PlayGrid.test.tsx`        |8    |1    |
|`store/play.test.ts` — tap/place/undo/redo |14   |2    |
|`store/play.test.ts` — commit/revert/solved|10   |3    |
|`components/play/SetOverlay.test.tsx`      |4    |3    |
|`lib/drag-controller.test.ts`              |10   |4    |
|`lib/grid-utils.test.ts` — insert/compact  |7    |5    |

### E2E test breakdown (target: 6 specs)

|Spec                        |Phase|
|----------------------------|-----|
|`play_load_puzzle.spec.ts`  |6    |
|`play_tap_place.spec.ts`    |6    |
|`play_undo_redo.spec.ts`    |6    |
|`play_validation.spec.ts`   |6    |
|`play_commit_revert.spec.ts`|6    |
|`play_solve.spec.ts`        |6    |

### Manual iPad testing checklist (per phase)

Run on a physical iPad (preferably base iPad + iPad Pro for screen size coverage):

- [ ] No accidental text selection during any interaction
- [ ] No scroll conflict between grid and page
- [ ] No long-press context menu on any tile
- [ ] Home bar swipe does not corrupt play state
- [ ] Notification during interaction does not corrupt state
- [ ] Split View activation does not corrupt state
- [ ] All touch targets ≥ 44×44px
- [ ] Orientation change preserves full state
- [ ] Dark mode renders correctly
- [ ] Grid scrolls smoothly if it exceeds viewport

-----

## 14. File Manifest

### New files (21)

```
frontend/src/types/play.ts                                    — Type definitions
frontend/src/lib/grid-utils.ts                                — Grid algorithms
frontend/src/lib/play-validation.ts                           — Client-side validation
frontend/src/lib/drag-controller.ts                           — Drag state machine (Phase 4)
frontend/src/store/play.ts                                    — Play mode Zustand store
frontend/src/app/[locale]/play/page.tsx                       — Play route page
frontend/src/components/play/PlayLayout.tsx                   — CSS Grid layout shell
frontend/src/components/play/PlayGrid.tsx                     — 2D grid renderer
frontend/src/components/play/GridCell.tsx                     — Single grid cell
frontend/src/components/play/SetOverlay.tsx                   — Validation border overlay
frontend/src/components/play/PlayRack.tsx                     — Rack panel
frontend/src/components/play/ControlBar.tsx                   — Action buttons
frontend/src/components/play/GhostTile.tsx                    — Drag preview (Phase 4)
frontend/src/components/play/SnapPreview.tsx                  — Drop target highlight (Phase 4)
frontend/src/components/play/SolvedBanner.tsx                 — Completion celebration
frontend/src/components/play/PlayPuzzleControls.tsx           — PuzzleControls wrapper for play store
frontend/src/__tests__/lib/grid-utils.test.ts                 — Grid utility tests
frontend/src/__tests__/lib/play-validation.test.ts            — Validation tests
frontend/src/__tests__/lib/drag-controller.test.ts            — Drag controller tests (Phase 4)
frontend/src/__tests__/store/play.test.ts                     — Store tests
frontend/src/__tests__/components/play/SetOverlay.test.tsx    — Overlay tests
frontend/src/__tests__/components/play/PlayGrid.test.tsx      — Grid render tests
frontend/e2e/play_load_puzzle.spec.ts                         — E2E
frontend/e2e/play_tap_place.spec.ts                           — E2E
frontend/e2e/play_undo_redo.spec.ts                           — E2E
frontend/e2e/play_validation.spec.ts                          — E2E
frontend/e2e/play_commit_revert.spec.ts                       — E2E
frontend/e2e/play_solve.spec.ts                               — E2E
```

### Modified files (4)

```
frontend/src/app/[locale]/page.tsx           — Add "Play" nav link (1 line)
frontend/src/app/globals.css                 — Add .play-surface CSS (~20 lines)
frontend/src/i18n/messages/en.json           — Add play.* namespace (~40 keys)
frontend/src/i18n/messages/de.json           — Add play.* namespace (~40 keys)
```

### NOT modified (0 backend changes)

```
backend/*                                     — No changes
frontend/src/store/game.ts                   — Solver store untouched
frontend/src/components/SolutionView.tsx      — Solver-only
frontend/src/components/BoardSection.tsx      — Solver-only
frontend/src/components/RackSection.tsx       — Solver-only
frontend/src/components/PuzzleControls.tsx    — NOT modified (wrapped instead)
```

-----

## 15. i18n Keys

Add these to `frontend/src/i18n/messages/en.json` under a new `"play"` namespace:

```json
{
  "play": {
    "title": "Play Mode",
    "loadPuzzlePrompt": "Load a puzzle to start playing.",
    "solved": "Puzzle Solved!",
    "solveTime": "Solved in {time}",
    "compareWithSolver": "Compare with optimal solution",
    "undo": "Undo",
    "redo": "Redo",
    "commit": "Commit",
    "revert": "Revert",
    "revertConfirm": "Revert to last committed state? All changes since then will be lost.",
    "modeTap": "Tap",
    "modeDrag": "Drag",
    "showValidation": "Show hints",
    "hideValidation": "Hide hints",
    "returnToRack": "Return to rack",
    "cannotReturnBoardTile": "Board tiles must stay on the table.",
    "commitBlocked": {
      "invalidSets": "Fix invalid sets before committing.",
      "incompleteSets": "Complete all sets (min 3 tiles) before committing."
    },
    "validation": {
      "invalid": "Invalid set",
      "runMixedColors": "Run: all tiles must be the same color",
      "runDuplicateNumbers": "Run: no duplicate numbers",
      "runGapsTooLarge": "Run: not enough jokers to fill gaps",
      "runOutOfRange": "Run: tiles don't fit in 1–13 range",
      "runTooLong": "Run: maximum 13 tiles",
      "groupMixedNumbers": "Group: all tiles must have the same number",
      "groupDuplicateColors": "Group: no duplicate colors",
      "groupTooManyJokers": "Group: too many jokers",
      "groupTooLarge": "Group: maximum 4 tiles"
    },
    "nav": {
      "toSolver": "← Solver",
      "toPlay": "Play Mode →"
    },
    "aria": {
      "emptyCell": "Empty cell, row {row}, column {col}",
      "occupiedCell": "{tile} at row {row}, column {col}",
      "gridRegion": "Puzzle board grid"
    }
  }
}
```

German translations follow the same structure under `"play"` in `de.json`. (40 keys × 2 languages = 80 total.)

-----

## 16. Timeline & Dependency Graph

```
Phase 0 (2d)  ──→  Phase 1 (3d)  ──→  Phase 2 (4d)  ──→  Phase 3 (3d)  ──→  Phase 6 (3d)
                                                                │
                                                                ├──→  Phase 4 (5d)  ──→  Phase 5 (2d)
                                                                │                              │
                                                                └──────────────────────────────→ Phase 6
```

**Critical path (tap-only MVP):** Phase 0 → 1 → 2 → 3 → 6 = **15 working days**

**Full path (with drag-and-drop):** + Phase 4 → 5 → merge into Phase 6 = **22 working days**

### Recommended sprint plan

|Sprint  |Duration|Phases           |Deliverable                                       |
|--------|--------|-----------------|--------------------------------------------------|
|Sprint 1|5 days  |Phase 0 + Phase 1|Grid renders with puzzle data, iPad layout working|
|Sprint 2|7 days  |Phase 2 + Phase 3|Tap-to-place fully functional with validation     |
|Sprint 3|5 days  |Phase 4          |Drag-and-drop working (can be deferred)           |
|Sprint 4|5 days  |Phase 5 + Phase 6|Polish, E2E tests, ship                           |

-----

## 17. Definition of Done

A phase is done when:

1. All listed tasks are implemented
1. All listed unit tests pass (`npm run test`)
1. `tsc --noEmit` has zero errors
1. `next build` succeeds
1. Existing solver tests pass unchanged (104 Vitest + 5 E2E)
1. Code reviewed (or self-reviewed against this plan)
1. Phase exit criteria checklist is fully checked

The feature is shipped when:

1. All 6 phases are done
1. All 6 E2E play specs pass
1. Manual iPad testing checklist passes
1. `game.ts` has zero modifications from its pre-play-mode state
1. The solver at `/` works exactly as before