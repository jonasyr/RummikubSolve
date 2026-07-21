# Changelog

All notable changes to this project are documented here.
Format: **Phase → What was done → Why it matters**

---

## [Unreleased] — 2026-04-22 — Rebuild Plan: Phase A (Infrastructure) + Phase B (Gates & Heuristic Solver)

Implements §7 Phase A and Phase B of `Puzzle Generation Rebuild Plan.md`.
All 8 issues (#27–#33, #67) closed; 8 PRs merged (#64–#72).

### Phase A — Infrastructure scaffolding (issues #27–#29, #67; PRs #64–#68)

- `solver/generator/gates/` package created with skeleton files for `structural.py`, `ilp.py`, `heuristic_solver.py`
- `solver/generator/templates/` package created with skeleton files for `base.py`, `__init__.py`, and templates T1–T5
- `solver/generator/generator_core.py` and `legacy_sacrifice.py` stubs created
- `PuzzleStore` schema extended: `template_id TEXT DEFAULT 'legacy'` and `template_version TEXT DEFAULT '0'` columns added via `_MIGRATION_COLUMNS` idiom; backwards-compatible with existing pool rows
- `PuzzleResponse` and `PuzzleRequest` extended with `template_id` / `template_version` fields (additive; no breaking change)
- `tests/api/test_puzzle_endpoint.py` split into fast (mocked ILP, ~2s) and slow (real solver, ~500s) suites via `@pytest.mark.slow`; removed ~1200s redundant puzzle generation in CI

### Phase B — Structural gates and heuristic solver (issues #30–#33; PRs #69–#72)

- `gates/structural.py` — three pre-ILP gates: `check_no_trivial_extension` (strict, any board set size), `check_no_single_home`, `check_joker_structural`; plus `run_pre_ilp_gates` / `run_post_ilp_gates` combiners
- `gates/__init__.py` — re-exports all gate functions
- `gates/heuristic_solver.py` — `HeuristicSolver.solves()` 4-rule priority loop with cycle detection and greedy fallback; see deviation notes in `Puzzle Generation Rebuild Plan.md §Implementation Notes`
- `tests/solver/gates/test_structural_integration.py` — 27 tests covering all gate combinations + Phase 7 easy/medium regression
- `tests/solver/gates/test_heuristic_solver.py` — 65 fast tests + slow Phase 7 regression for all 25 calibration puzzles; 6 parametrised hard-fixture tests
- `tests/solver/gates/conftest.py` — session-scoped `phase7_easy_medium` (10 puzzles) and `phase7_hard_expert_nightmare` (15 puzzles) fixtures shared between both test modules
- `tests/fixtures/golden_puzzles/hard_001–006.json` — 6 hand-crafted `PuzzleResponse`-shaped fixtures that `HeuristicSolver.solves()` must return `False` for
- `tests/fixtures/golden_puzzles/README.md` — fixture format documentation

---

## [Unreleased] — 2026-04-16 — Phase 7: First Clean Calibration — All Puzzles Still Trivially Easy

### Result
25 puzzles across all tiers (phase7_batch_v1) solved in under 1 minute, zero undos, all labeled "trivial" or "straightforward". The difficulty system remains non-functional. See `PUZZLE_DIFFICULTY_PROBLEM.md` for full root-cause analysis and proposed directions.

| Tier      | Score (avg) | Solve time (avg) | Target      |
|-----------|-------------|------------------|-------------|
| easy      | 39.0        | ~4s              | 30s – 2min  |
| medium    | 58.7        | ~7s              | 1min – 3min |
| hard      | 59.8        | ~13s             | 2min – 5min |
| expert    | 71.0        | ~18s             | 5min – 15min|
| nightmare | 80.9        | ~28s             | 10min – 30min|

### Added
- `PUZZLE_DIFFICULTY_PROBLEM.md` — detailed post-mortem: root causes, history of attempts, hypotheses for a real fix, full calibration data
- `_any_trivial_extension_v2()` — v2-specific trivial extension gate; rejects rack tiles that extend complete (≥3 tile) board sets only (partial stubs excluded to avoid 100% rejection rate)
- `_solve_timed()` daemon-thread wrapper in `tile_remover.py` — hard Python-level deadline for HiGHS calls in AnyIO worker threads on Windows where `time_limit` is not respected
- `batch_run_id` UUID per calibration session; emitted in `puzzle_solved`, `puzzle_rated`, `puzzle_abandoned` telemetry events
- "New Run" button and post-completion overlay in calibration UI
- `puzzle_id` fast-path in puzzle API — pool lookup by ID; live-generated puzzles also persisted to pool
- `gen_calibration_batch.py` — writes output to `solver/generator/calibration_batches/` by default (no manual copying)
- `calibrate.py --run-id` filter; per-run breakdown in default batch report
- `phase7_batch_v1.json` calibration batch (25 puzzles, seeds 10000–10004 per tier)
- `simplex_iteration_limit = 50_000` in HiGHS solver as platform-independent iteration cap

### Changed
- `BATCH_NAME` in calibration page updated to `phase7_batch_v1`
- `numpy` added to `pyproject.toml` (for `--fit-weights`)
- `_MIN_DISRUPTION_V2` / `_MIN_FRAGILITY_V2` quality gates enabled in `_attempt_generate_v2()`
- Tier mismatch check re-enabled (was commented out since Phase 4)

---

## [Unreleased] — 2026-04-16 — Phase 6: Calibration Results Remediation

### Backend — Difficulty scoring (P0)
- `difficulty_weights.json`: normalization ceilings raised to match observed metric ranges; previous values (branching=8, deductive=10, working_memory=10, tile_ambiguity=15) were far below actual outputs (6–41, 9–16, 4–14, 18–34), causing all tiers to clamp to 1.0 and score 59–97 regardless of difficulty
- `difficulty_evaluator.py`: `TIER_THRESHOLDS` recalibrated from observed distributions after ceiling fix: easy `(0,52)`, medium `(38,68)`, hard `(55,85)`, expert `(68,92)`, nightmare `(75,100)`
- `difficulty_evaluator.py`: `red_herring_density` redesigned — old definition (non-solution sets / all sets) was always ~0.95; new definition counts only candidate placements that **conflict** with the solution by competing for the same board tiles; easy puzzles now score ~0.0, harder tiers score higher
- `puzzle_generator.py`: tier-matching check re-enabled (was commented out since Phase 4); tolerates ±1 adjacent tier, rejects anything further
- `puzzle_generator.py`: per-tier minimum quality gates added (`_MIN_DISRUPTION_V2`, `_MIN_FRAGILITY_V2`); rejects perceptually trivial puzzles that pass the solver but have too little rearrangement or fragility

### Backend — Data quality (P1)
- `telemetry_store.py`: `puzzle_rated` events now upsert — re-rating the same attempt deletes the previous row before inserting; duplicate ratings no longer accumulate
- `api/main.py`: live-generated puzzles (easy/medium/hard non-pool path) are now persisted via `PuzzleStore.store()` and return a non-empty `puzzle_id`; telemetry events can now be linked to the puzzle
- `pyproject.toml`: `numpy>=2.0.0` added as a runtime dependency

### Frontend — Telemetry (P1)
- `play.ts`: `puzzle_solved` event now includes `tiles_placed` (= `puzzle.tile_count`) and `tiles_remaining` (= 0)

### Backend — Calibration tooling (P2)
- `calibrate.py`: added `--stats` mode — queries the puzzle pool DB and prints per-tier composite score distributions (min/avg/max)
- `calibrate.py`: added `--fit-weights` mode — fits a log-linear regression (`numpy.linalg.lstsq`) of solve time on normalised metrics across a telemetry batch; clips negative coefficients to 0 and normalises to sum=1; prints suggested `difficulty_weights.json` updates to stdout only, does not auto-write; warns if fewer than 20 solved sessions per tier

---

## [Unreleased] — 2026-04-14 — Phase 0–6 calibration foundation

### Backend — Generator and Persistence
- `difficulty_weights.json` added and `difficulty_evaluator.py` now loads score weights/ceilings from JSON instead of hardcoding them.
- `puzzle_store.py` now round-trips the full v2 metric set: `deductive_depth`, `red_herring_density`, `working_memory_load`, `tile_ambiguity`, `solution_fragility`, plus existing `composite_score`, `branching_factor`, `generator_version`.
- `PuzzleResult` now carries `seed`; live-generated puzzles get a deterministic effective seed even when the caller omitted one.
- `PuzzleStore` now preserves `seed` for both direct stores and pregenerated pool rows; pool-drawn puzzles surface that seed back to the API.
- `tile_remover.py` now skips trial removals that trigger solver post-verification `ValueError`s instead of aborting generation.
- `export_telemetry.py` added for CSV export of telemetry data.
- `calibrate.py` added as a reporting-only calibration CLI for fixed-seed batches.
- `calibration_batches/phase6_batch_v1.json` added as the first committed 25-puzzle fixed-seed developer batch.

### Backend — API and Telemetry
- `PuzzleResponse` now includes `seed` and the full v2 metric set.
- `POST /api/telemetry` expanded to support richer calibration telemetry:
  - `attempt_id`
  - `batch_name`
  - `batch_index`
  - `puzzle_abandoned`
  - `puzzle_rated`
  - manual rating fields (`self_rating`, `self_label`, `stuck_moments`, `notes`)
- `telemetry_events` schema extended to persist calibration fields and richer attempt/session metadata.
- `GET /api/calibration-batch/{batch_name}` added to serve fixed-seed developer batch manifests.

### Frontend — Telemetry and Calibration UI
- `telemetry.ts` now carries `seed`, `attempt_id`, and calibration batch metadata through emitted events.
- `play.ts` now generates a new `attemptId` on every puzzle load and propagates calibration batch context through automatic telemetry.
- Normal `/play` clears calibration context on mount so calibration metadata does not leak into standard sessions.
- New developer calibration route: `/[locale]/play/calibration`
  - fixed batch loading from backend
  - progress tracking in localStorage
  - manual rating UI
  - abandon reporting
  - visible seed/difficulty/metric badges for each calibration puzzle
- Calibration route is gated by a simple developer password prompt (`123`) stored in sessionStorage.
- Normal play now includes a link into the calibration route.

### Frontend — i18n and UX fixes
- Added EN/DE calibration strings.
- Fixed `SetOverlay` translation lookup so already-prefixed validation keys (`play.validation.*`) no longer resolve as `play.play.*`.

### Tests and Verification
- Added/updated backend coverage for:
  - telemetry storage
  - telemetry endpoint validation
  - calibration batch endpoint
  - telemetry CSV export
  - puzzle store seed round-trip
- Verified:
  - backend focused suite: `38 passed`
  - frontend play-store tests: `50 passed`
  - frontend `tsc --noEmit`: passed

---

## [0.43.0] — 2026-04-13 — Phase 4: Generator Integration (v2 pipeline)

### Backend — Generator (`backend/solver/generator/puzzle_generator.py`)
- `_attempt_generate_v2()`: new generation function wiring BoardBuilder → TileRemover → DifficultyEvaluator; replaces sacrifice-based approach for all non-custom difficulties
- `generate_puzzle()`: added `generator_version="v2"` parameter; v2 is the default; v1 still accessible via `generator_version="v1"` for backward compatibility
- `PuzzleResult`: extended with `branching_factor`, `deductive_depth`, `red_herring_density`, `working_memory_load`, `tile_ambiguity`, `solution_fragility`, `composite_score`, `generator_version` (all default to 0.0 / "v1" for backward compatibility)
- `_DEFAULT_MAX_ATTEMPTS_V2`: per-difficulty attempt limits for v2

### Backend — API (`backend/api/models.py`, `backend/api/main.py`)
- `PuzzleResponse`: added `composite_score`, `branching_factor`, `generator_version` (additive, optional fields with defaults — backward-compatible)
- `_result_to_response()`: exposes new fields in API response

### Backend — Pregenerate (`backend/solver/generator/pregenerate.py`)
- Worker updated to call `_attempt_generate_v2()` directly

### Tests
- `test_puzzle_generator.py`: 5 new Phase 4 tests — v2 returns puzzle result, tier match, new fields populated, API serialization, v1 fallback
- **Total: ~220 passing**

---

## [0.42.0] — 2026-04-13 — Phase 3: DifficultyEvaluator

### Backend — Generator (`backend/solver/generator/difficulty_evaluator.py`)
- New module: 8-metric difficulty scoring system replacing single disruption/chain-depth filtering
- `DifficultyScore` dataclass: 10 fields covering all difficulty dimensions
- `compute_branching_factor()`: average valid placements per rack tile
- `compute_red_herrings()`: fraction of placements not in the optimal solution
- `compute_working_memory_load()`: count of board sets disrupted by the solution
- `compute_tile_ambiguity()`: average candidate sets per tile (board + rack)
- `compute_solution_fragility()`: sensitivity to single-tile removal (expensive; skipped for easy/medium)
- `compute_deductive_depth()`: chain_depth × log₂(branching_factor + 1)
- `compute_composite_score()`: weighted combination of all 8 metrics → 0–100 scale
- `TIER_THRESHOLDS`: easy(0–20), medium(15–35), hard(30–55), expert(50–75), nightmare(70–100)
- `classify_tier()`: maps composite score to difficulty tier (overlapping bands)
- `DifficultyEvaluator.evaluate()`: facade with `skip_expensive=False` flag; caches `enumerate_valid_sets()` result to avoid triple enumeration

### Tests (`backend/tests/solver/test_difficulty_evaluator.py`)
- 14 tests using real solver (no mocks): bounds checks, edge cases (empty rack, trivial puzzle), tier classification, performance guard (<500ms with skip_expensive=True)

### Versions
- `backend/pyproject.toml` bumped to **0.42.0**

---

## [0.41.0] — 2026-04-13 — Phase 2: TileRemover (Strategic Tile Removal)

### Backend — Generator (`backend/solver/generator/tile_remover.py`)
- New module: strategic tile removal replacing complete-set sacrifice approach
- `RemovalCandidate` dataclass: pre-scored removal option with cascade estimate, orphan count, alternative placements
- `RemovalStep` dataclass: committed removal record with pre-removal board snapshot for replay
- `estimate_cascade_depth()`: heuristic scoring (+2.0/+1.0/+0.5 per orphan based on absorber count)
- `_score_all_candidates()`: scores every board tile as a removal candidate in O(n·templates)
- `_apply_removal()`: index-based removal preserving Tile object identity (required by solver's id()-based tracking)
- `TileRemover.remove()`: top-30% weighted random selection with per-step solvability verification; retries up to 5 candidates per step; guards with 2s per-step and 30s total timeouts

### Tests (`backend/tests/solver/test_tile_remover.py`)
- 23 tests: pure-logic helpers (cascade depth, apply removal, scoring) + real-solver integration tests

### Versions
- `backend/pyproject.toml` bumped to **0.41.0**

---

## [0.40.0] — 2026-04-13 — Phase 1: BoardBuilder (High-Overlap Board Construction)

### Backend — Generator
- `backend/solver/generator/tile_pool.py` (new): `make_tile_pool()` and `assign_copy_ids()` extracted from `puzzle_generator.py`; consolidated pool creation with joker support
- `backend/solver/generator/board_builder.py` (new): overlap-graph-guided board construction replacing greedy `_pick_compatible_sets()`
  - `build_overlap_graph()`: adjacency map of tile co-occurrence across templates
  - `score_set_overlap()`: average connectivity score per set
  - `select_high_overlap_sets()`: weighted random selection with `overlap_bias` parameter (0=random, 1=greedy)
  - `BoardBuilder.build()`: full pipeline — pool → enumerate → shuffle → graph → select → assign_copy_ids

### Tests (`backend/tests/solver/test_board_builder.py`)
- 21 tests: board validity, no duplicate tiles, copy_id correctness, size constraints, seed determinism, overlap graph symmetry, overlap bias effectiveness (<100ms performance guard)

### Versions
- `backend/pyproject.toml` bumped to **0.40.0**

---

## [0.39.0] — 2026-04-09 — Play Mode Phase 5.4/6.1/6.3–6.6 + Docker fixes

### Frontend — Store (`frontend/src/store/play.ts`)
- Auto-grow grid: placing a tile in the last visible row automatically adds workspace rows
  (capped at `GRID_MAX_ROWS = 24`). Grid only grows during placement; `revert` recomputes
  rows from the committed snapshot so the grid can shrink back to fit.
- `setInteractionMode` now persists the chosen mode to `localStorage("play:interactionMode")`.

### Frontend — Pages
- **Play page**: hydrates `interactionMode` from localStorage on mount; warns before
  navigating away when there are uncommitted changes (`beforeunload` event).
- **Solver page**: "Play Mode →" link added to the header (locale-aware).

### Frontend — Components
- **SolvedBanner**: 🎉 emojis + `pop-in` scale/fade entrance animation.

### Frontend — i18n
- Added `page.toPlay` key (en + de).

### Docker
- Fixed health checks: replaced `curl` (not installed in `python:3.12-slim` or
  `node:20-alpine`) with Python `urllib` (backend) and `wget` (frontend). Without
  this fix `depends_on: condition: service_healthy` would never be satisfied and
  nginx would fail to start.
- Added named volume `puzzle_data` for the backend SQLite puzzle pool DB so
  pregenerated puzzles survive container rebuilds.

### Tests
- `play.test.ts`: +2 auto-grow tests (AAA, happy-path).
- **Total: 197 passing, 7 todo, 0 failed**

### Versions
- `frontend/package.json` and `backend/pyproject.toml` bumped to **0.39.0**.

---

## [0.38.0] — 2026-04-09 — Play Mode: run order enforcement & commit feedback

### Frontend — Validation (`frontend/src/lib/play-validation.ts`)
- `validateAsRun` now requires non-joker tiles to be placed in strictly ascending
  left-to-right order. Placing [6, 8, 7] is now invalid ("runNotOrdered"). Previously
  the validator sorted tiles before checking, so any permutation was accepted.

### Frontend — Components
- **ControlBar**: commit button flashes green and shows "Committed!" for 2 s on success.

### Frontend — i18n
- Added `play.validation.runNotOrdered` (en + de) and `play.commitSuccess` (en + de).

### Tests
- `play-validation.test.ts`: +1 test confirming [6, 8, 7] is invalid with `runNotOrdered`.
- **Total: 195 passing, 7 todo, 0 failed**

---

## [0.37.0] — 2026-04-09 — Play Mode Phase 3: commit/revert & solved state

### Frontend — Store (`frontend/src/store/play.ts`)
- Implement `commit`: three sequential validation gates — (0) tile conservation check
  using `validateTileConservation`; (1) no ≥3-tile sets with failing validation; (2) no
  orphan 1-2 tile groups. On success: advances `committedSnapshot`, clears `past`/`future`,
  clears `selectedTile`. Returns typed `CommitResult`.
- Implement `revert`: restores `grid` and `rack` from `committedSnapshot` (shallow copies),
  recomputes `detectedSets` and `isSolved`, clears `past`/`future`/`selectedTile`.
- Extend `CommitResult` type with `"tile_conservation"` reason.

### Frontend — Components
- **ControlBar**: commit button now disabled (with tooltip) when the board has invalid or
  incomplete sets. Derived from `detectedSets` without calling `commit()` proactively.
- **SolvedBanner** (new): fixed-position overlay rendered when `isSolved` is true. Displays
  solved message and elapsed solve time. Self-contained — reads from store, no props.

### Frontend — Page
- `play/page.tsx`: renders `<SolvedBanner />` as the last child of `PlayLayout`.

### Tests
- `play.test.ts`: 6 Phase 3 todos converted to real tests + 4 additional = 10 new tests
- `SolvedBanner.test.tsx`: 3 new tests (hidden/visible/time display)
- **Total: 194 passing, 7 todo (grid-utils), 0 failed**

---

## [0.36.1] — 2026-04-09 — Layout hotfix: touch scrollability & grid containment

### Fixed
- **Play mode — board scrollable on all touch devices:** Changed `touch-action: none` to
  `touch-action: pan-x pan-y` on `.play-surface`. The board had `overflow: auto` but
  `touch-action: none` silently blocked browser pan gestures, making the 800 px-wide grid
  inaccessible on phones and tablets without a hardware mouse.
- **Play mode — grid stays within CSS grid track:** Added `min-height: 0` to both the board
  and rack grid-area divs. Without it, CSS grid items with `min-height: auto` grow beyond
  their `1fr` track and `overflow: auto` never triggers. This caused the bottom rows to
  overflow the viewport on iPad landscape instead of scrolling.
- **Known dev-only artifact:** The Next.js dev overlay button ("N") is fixed at the
  bottom-left corner and overlaps the first rack tile in iPad portrait orientation. This only
  appears in development mode; production builds are unaffected.

---

## [0.36.0] — 2026-04-09 — Play Mode Phase 2: tap interaction & undo/redo

### Frontend — Store (`frontend/src/store/play.ts`)
- Implement `tapRackTile`: toggle rack tile selection; tapping same tile deselects, tapping
  different tile switches selection
- Implement `tapCell`: state machine — no selection + occupied cell = pick up; no selection +
  empty cell = no-op; selection + occupied same cell = deselect; selection + occupied other
  cell = switch; selection + empty cell = place (calls `placeTile` helper)
- Implement `returnToRack`: removes rack-source grid tile from grid and appends to rack;
  board-source tiles are no-ops (permanently locked)
- Implement `undo`: pops past stack, pushes current state to future stack, restores snapshot,
  recomputes derived state, clears selection
- Implement `redo`: pops future stack, pushes current state to past stack, restores snapshot,
  recomputes derived state, clears selection
- Add private `takeSnapshot` helper: shallow-copies grid Map and rack array
- Add private `placeTile` helper: handles rack-by-index removal and grid-tile moves; preserves
  `PlacedTile.source`; pushes undo snapshot; starts `solveStartTime` on first placement;
  sets `solveEndTime` if `checkSolved` returns true; clears redo stack on new action
- Fix import: add `checkSolved` to `grid-utils` import

### Frontend — Component (`frontend/src/components/play/ControlBar.tsx`)
- Add conditional "Return to Rack" button: visible only when a rack-source grid tile is
  selected (derived via `cellKey` lookup on `selectedTile`); calls `returnToRack` action

### Frontend — Tests (`frontend/src/__tests__/store/play.test.ts`)
- Implement all 17 Phase 2 `it.todo` scaffolds: `tapRackTile` (3), `tapCell` (7),
  `returnToRack` (2), `undo/redo` (5); each describe block has a shared `setupPuzzle`
  `beforeEach` (board row 0 = red 5/6/7, rack = red 1 + blue 2)
- Test count: 164 → **181 passing**, 30 → **13 todo**, 0 failed

### Frontend — e2e (`frontend/e2e/play_interact.spec.ts`)
- Add 7 new Playwright specs: rack tile selection ring, deselect on double-tap, place on
  empty cell, pick up grid tile, move grid tile, undo placement, return-to-rack flow
- All specs mock `**/api/puzzle` — backend not required

---

## [0.35.0] — 2026-04-09 — Play Mode Phase 1: grid rendering & iPad layout

### Frontend — Components (`frontend/src/components/play/`)
- Add `PlayLayout.tsx`: CSS Grid shell with responsive grid-areas (`controls / board / rack`);
  portrait = stacked, landscape ≥1024px = rack column beside board
- Add `ControlBar.tsx`: Undo / Redo / Commit / Revert + validation toggle;
  all buttons `h-11` (44px touch target); Undo/Redo disabled when history is empty;
  back-link to solver via `useLocale`
- Add `PlayGrid.tsx`: 2-D grid renderer — iterates `rows × cols` cells, renders
  `GridCell` for each position, renders `SetOverlay` after cells (DOM-order stacking)
- Add `GridCell.tsx`: single memoised cell (`React.memo`); occupied cells render `Tile`;
  `data-slot-cell` attribute used as e2e selector anchor;
  selection ring (`ring-blue-500`) and drop-target styling (`border-dashed`)
- Add `SetOverlay.tsx`: absolute-positioned amber / green / red validation overlay;
  pixel formula: `width = tiles × cellPx − CELL_GAP_PX`; `pointer-events-none`;
  shows type label for valid sets, i18n error string for invalid sets
- Add `PlayRack.tsx`: scrollable rack panel (`play-rack-scroll`);
  portrait = horizontal wrap, landscape = vertical column; calls `tapRackTile` stub
- Add `PlayPuzzleControls.tsx`: standalone puzzle loader bound to `usePlayStore`
  (not `useGameStore`); 5 difficulty buttons; AbortController cleanup on unmount

### Frontend — CSS (`frontend/src/app/globals.css`)
- Add `.play-surface`: `touch-action:none`, `user-select:none`, `-webkit-*` variants
- Add `.play-rack-scroll`: `touch-action:pan-y`, `-webkit-overflow-scrolling:touch`
- Add `.play-layout`: `100dvh` CSS Grid with `safe-area-inset-*` padding;
  responsive `@media (min-width:1024px)` rule for landscape two-column layout

### Frontend — Route (`frontend/src/app/[locale]/play/page.tsx`)
- Replace Phase 0 stub with fully wired `PlayLayout + ControlBar + PlayPuzzleControls
  + PlayGrid + PlayRack`; page owns all `gridArea` assignments

### Frontend — i18n
- Add `getPuzzle` and `loading` keys to `play.*` namespace in `en.json` and `de.json`

### Frontend — Tests
- Add `frontend/src/__tests__/components/play/PlayGrid.test.tsx`: 8 unit tests
  (cell count, occupied rendering, empty rendering, selection ring, drop-target styling,
  no-selection styling, click callback, touch-hardening class)
- Add `frontend/e2e/play_load_puzzle.spec.ts`: 5 Playwright specs (chromium +
  mobile-chrome + mobile-safari): load prompt, puzzle load via mocked API,
  four control buttons visible, 44px touch target, play-surface class present

---

## [0.34.0] — 2026-04-09 — Play Mode Phase 0: route, store, and algorithms

### Frontend — Types (`frontend/src/types/play.ts`)
- Add `PlacedTile`, `CellKey`, `cellKey()`, `DetectedSet`, `SetValidation`,
  `TileSelection`, `PlaySnapshot`, `DragState` interfaces
- Add grid constants: `GRID_COLS=16`, `GRID_MIN_ROWS=6`, `GRID_MAX_ROWS=24`,
  `GRID_WORKSPACE_ROWS=3`, `UNDO_MAX=50`, `CELL_SIZE_PX=48`, `CELL_GAP_PX=2`

### Frontend — Library
- Add `frontend/src/lib/grid-utils.ts`: `puzzleToGrid`, `detectSets`, `checkSolved`,
  `validateTileConservation`; Phase-5 implementations `insertTileIntoRow`, `compactGrid`
- Add `frontend/src/lib/play-validation.ts`: `validateTileGroup`, private `validateAsRun`,
  `validateAsGroup`; all validation error reasons are `play.validation.*` i18n keys

### Frontend — Store (`frontend/src/store/play.ts`)
- Add isolated `usePlayStore` (Zustand); fully separated from `useGameStore` (zero coupling)
- `loadPuzzle` implemented: calls `fetchPuzzle`, maps puzzle to grid, detects sets,
  initialises `committedSnapshot`; mirrors `game.ts` abort/error/loading-guard pattern
- Phase 2 actions (`tapCell`, `tapRackTile`, `undo`, `redo`, `returnToRack`) stubbed as no-ops
- Phase 3 actions (`commit`, `revert`) stubbed

### Frontend — Route (`frontend/src/app/[locale]/play/page.tsx`)
- Add `/play` route: minimal shell with inline "Load Easy Puzzle" button;
  Phase 1 will replace with `PlayLayout + PlayGrid + PlayRack + PlayPuzzleControls`

### Frontend — i18n
- Add `play.*` namespace (40 keys) to `en.json` and `de.json`:
  navigation, validation errors, aria labels, control bar labels, commit/revert UI

### Frontend — Tests
- Add `frontend/src/__tests__/lib/grid-utils.test.ts`: 20 tests (Phase 0 happy paths +
  edge cases) + Phase 5 scaffolds (`it.todo`)
- Add `frontend/src/__tests__/lib/play-validation.test.ts`: 16 tests covering valid/invalid
  runs and groups, joker handling, incomplete sets (<3 tiles, no reason string)
- Add `frontend/src/__tests__/store/play.test.ts`: 14 Phase-0 tests (initial state,
  loadPuzzle, error handling, simple actions) + Phase 2/3 scaffolds (`it.todo`)

---

## [0.33.0] — 2026-04-01 — UI rework: set-centric solution view (ui_rework phases 1–4)

### Backend — Per-set change manifest (`backend/api/`, `backend/solver/generator/set_changes.py`)

- **Phase UI-1:** `POST /api/solve` now returns a `set_changes[]` array alongside the
  existing `moves[]` and `new_board[]` fields (full backward compatibility preserved).
- **`solver/generator/set_changes.py`** (new pure module, no FastAPI deps):
  - `TileWithOriginData` dataclass: every tile carries an `origin` field —
    `"hand"` (placed from rack this turn) or an `int` (0-based index of the old board
    set the tile was taken from).
  - `SetChangeData` dataclass: per-result-set record with `action`, `tiles`,
    `set_type`, `source_set_indices`, `source_description`.
  - `build_old_tile_origin_map()`: builds a `(color, number, copy_id, is_joker) →
    [set_index, …]` map from the pre-solve board state for O(1) tile lookup.
  - `build_set_changes()`: classifies each result set as one of four actions:
    - `"new"` — every tile came from the rack.
    - `"extended"` — rack tiles added to exactly one existing board set.
    - `"rearranged"` — tiles sourced from multiple board sets or mixed with rack tiles
      in a non-extend pattern.
    - `"unchanged"` — set is identical (same tiles, same signature) to a pre-solve set.
- **`api/models.py`**: new Pydantic models `TileWithOrigin`, `SetChangeResultSet`,
  `SetChange`; `SolveResponse` gains `set_changes: list[SetChange] = []`.
- **`api/main.py`**: thin adapter converts `SetChangeData` → `SetChange` Pydantic model;
  `cast(Literal["run","group"], d.set_type)` satisfies mypy strict mode.

### Backend — Tests
- **`tests/solver/test_set_changes.py`** (new, 30 unit tests): imports pure
  `solver.generator.set_changes` directly — no web stack required.
  Covers `build_old_tile_origin_map`, all four action classifications, copy-id
  disambiguation, joker handling, and `source_set_indices` tuple correctness.
- **`tests/api/test_solve_endpoint.py`** (+12 integration tests): `set_changes` field
  presence, count, action values, origin correctness, backward compatibility with
  `moves[]`, empty array on `no_solution`.

### Backend — CI performance
- Added `@pytest.mark.slow` to 163 tests that require multiple solver calls each
  (puzzle generation, uniqueness verification, hypothesis property tests, puzzle
  endpoint integration).
- `pytest -m "not slow"` now runs 250 tests in ~2–3 minutes (was 413 tests, 24+ min).
- Run the full suite locally with `pytest` or `pytest -m slow` for the slow subset.

### Frontend — Types (`frontend/src/types/api.ts`)
- New interfaces mirroring backend models: `TileWithOrigin`, `SetChangeResultSet`,
  `SetChange`; `SolveResponse.set_changes?: SetChange[]` (optional for back-compat).

### Frontend — Phase UI-2: SetChangeCards (`frontend/src/components/SolutionView.tsx`)
- **Complete rewrite** of `SolutionView`. The fake step-navigator UI (Prev/Next buttons,
  progress dots, before/after panels, `moves[]`-driven instructions) is removed.
- One `SetChangeCard` per `SetChange` entry, sorted: new → extended → rearranged →
  unchanged.
- Cards colour-coded by action (green / blue / amber / gray).
- Tiles from the player's rack highlighted with a yellow ring (`origin === "hand"`).
- Run tiles sorted by number; group tile order preserved.
- Unchanged sets collapsed behind a toggle button by default.
- `originalBoard` prop removed from `SolutionView`; `page.tsx` updated accordingly.
- i18n: added `solution.source` key (`"was: {desc}"` / `"war: {desc}"`).

### Frontend — Phase UI-3: Provenance toggle
- **"Show origins" / "Hide origins"** toggle button above the cards.
- When on, each tile shows a tiny chip below it: `HAND` (rack) or `SET N` (1-based
  index of the old board set the tile came from).
- Labels hidden by default; reset automatically on each new solution.
- `Tile.tsx`: new `label?: string` prop renders an 8 px neutral chip below the tile face.
  All 13 existing Tile tests unaffected (prop is optional).
- i18n keys added: `showProvenance`, `hideProvenance`, `originHand`, `originSet` (EN + DE).

### Frontend — Phase UI-4: Tile tap-to-highlight
- **Click any tile** to cross-highlight every tile in the solution sharing the same
  `(color, number)` key (or all jokers) with a blue ring. Click the same tile again to
  deselect.
- Blue "selected" ring takes visual precedence over the yellow "from hand" ring.
- `selectedTileKey` state in `SolutionView`; reset via `useEffect` on new solution.
- `Tile.tsx`: new `selected?: boolean` + `onClick?: () => void` props;
  `cursor-pointer` class applied when clickable.
- Helper `tileKey(tile)` encodes jokers as `"joker"`, colored tiles as `"color:number"`.

### Frontend — Tests
- `SolutionView.test.tsx` (24 tests): no-solution, summary bar, card rendering, tile
  highlighting, sort order, unchanged collapse/expand, remaining rack, fallback, run
  tile sorting, absence of step navigator.
- `SolutionView.provenance.test.tsx` (10 tests): toggle visibility, button show/hide,
  HAND label, SET N 1-based conversion, state reset on new solution.
- `SolutionView.taphighlight.test.tsx` (7 tests): single-tile select/deselect, switch,
  cross-card highlight, joker grouping, state reset.
- `Tile.test.tsx` (+7 tests): label chip presence/absence, selected ring (blue),
  selected overrides highlighted, `onClick` called, `cursor-pointer` class.
- Total: **104 unit tests pass** (was 56 before this release).

### Frontend — Playwright E2E
- `solve_basic_run.spec.ts`: updated assertion from removed `"Move instructions"` heading
  to new `"NEW"` badge.
- `extend_board_set.spec.ts`: updated assertion from removed move-description text to
  new `"+"` badge.

---

## [0.32.0] — 2026-03-31 — Nightmare difficulty overhaul + joker infrastructure (phases 8 + 8b)

### Backend — Chain depth metric (`backend/solver/engine/objective.py`)
- **`compute_chain_depth()`** completely rewritten from a convergence-breadth metric to a
  **DAG longest-path algorithm**. Builds a directed graph where `inheritor → dependent`
  edges model sequential set dependencies; uses Kahn's BFS topological sort (cycle-safe)
  to find the longest path.
- New semantics: a simple split now returns depth 2 (was 1); a genuine 2-step sequential
  chain returns 3 (was 2). Old tests updated to reflect the new metric.
- **RecursionError fix:** step 5 (rack-tile prerequisite edges) can create back-edges
  producing cycles. Replaced recursive DFS with Kahn's algorithm; cyclic nodes are
  naturally excluded because they never reach in-degree 0.

### Backend — Difficulty constants (`backend/solver/generator/puzzle_generator.py`)
- All six difficulty configuration dicts updated for Expert and Nightmare:

  | Parameter | Expert (old → new) | Nightmare (old → new) |
  |-----------|-------------------|-----------------------|
  | Rack size | (4,6) → (6,10) | (5,7) → (10,14) |
  | Board size | (13,18) → (16,22) | (15,20) → (22,28) |
  | Sacrifice | 4 → 5 | 6 → 7 |
  | Chain depth (live) | 1 → 2 | 2 → 3 |
  | Disruption floor (live) | 29 → 32 | 35 → 38 |
  | Max attempts | 400 → 600 | 600 → 1500 |

- **Uniqueness:** computed for Expert/Nightmare (informational, never a generation gate —
  complete-sacrifice produces too many equivalent rearrangements for gating to be feasible).

### Backend — Joker infrastructure (Phase 8)
- **`_JOKER_COUNTS`** dict: `hard (0,1)`, `expert (1,2)`, `nightmare (1,2)`.
- **`_make_pool(n_jokers)`**: builds the 104-tile base pool plus `n_jokers` joker tiles.
  Raises `ValueError` if `n_jokers` is outside `[0, 2]` (guard against `Tile.__post_init__`
  crash with invalid `copy_id`).
- **`_inject_jokers_into_board(board_sets, n_jokers, rng)`**: physically places jokers into
  existing board sets with ≥ 4 tiles by replacing a random non-joker tile. This bypasses
  the limitation that `enumerate_runs()`/`enumerate_groups()` don't produce joker-containing
  set templates. Jokers in sacrificed sets may end up in the rack (expected).
- **`PuzzleResult.joker_count`** now reflects jokers actually visible on `board_sets`
  (previously always 0 — field was declared but never populated).

### Backend — Pre-generation tier (Phase 8b)
- **`_PREGEN_CONSTRAINTS`**: stricter thresholds for offline batch generation:
  Expert (chain ≥ 3, disruption ≥ 38); Nightmare (chain ≥ 4, disruption ≥ 45).
  These are the original plan's targets — achievable in batch, infeasible for live API.
- **`_PREGEN_MAX_ATTEMPTS`**: 5,000 (Expert) / 10,000 (Nightmare) for the batch CLI.
- **`generate_puzzle(pregen=False)`**: new `pregen` parameter. When `True`, applies
  `_PREGEN_CONSTRAINTS` and uses `_PREGEN_MAX_ATTEMPTS` as default budget. Default `False`
  leaves live generation completely unchanged.
- **`pregenerate.py`**: now passes `pregen=True` so all CLI-generated pool puzzles meet
  the strict spec. Pool-drawn puzzles deliver the intended 15–30 min difficulty experience;
  live fallback uses relaxed thresholds to stay within API timeout.

### Backend — Tests
- **`test_objective.py`**: all chain-depth assertions updated for new DAG semantics
  (depth 1 → 2 for split scenarios, depth 2 → 3 for two-step chains).
- **`test_puzzle_generator.py`**: 20 new tests across three new classes:
  - `TestMakePoolValidation` (5): `_make_pool()` range validation.
  - `TestInjectJokersIntoBoard` (5): joker placement correctness.
  - `TestPregenTier` (6): `_PREGEN_CONSTRAINTS` structure, threshold ordering invariants,
    `pregen=True` end-to-end generation, solvability.
  - Existing tests updated: rack/board size ranges, chain depth floors, `is_unique` semantic.
- **`test_puzzle_endpoint.py`**: nightmare rack range `(5,7) → (10,14)`;
  expert rack range `(2,6) → (6,10)`; disruption floor `≥ 26 → ≥ 32`; `is_unique`
  relaxed from `is True` to `isinstance(bool)`.

### Calibration notes (deviations from original plan)
- Nightmare **live** chain floor is 3, not 4 (plan target). Depth ≥ 4 occurs ~23% of
  solvable candidates; with uniqueness gating (nearly 0% pass rate for complete-sacrifice),
  live generation would be infeasible. The pregen=True path enforces the original depth ≥ 4.
- Nightmare **live** disruption floor is 38, not 45. Empirical p90 on nightmare-scale boards
  is 39 (larger boards give ILP more routing options). pregen=True enforces ≥ 45.
- Uniqueness is **informational only** for live generation. Complete-sacrifice always yields
  many equivalent rearrangements; gating on uniqueness would require pre-generation only.

### New file — `IMPLEMEMTATION EVALUATION.md`
- Post-mortem evaluation identifying three critical bugs (joker_count always 0, jokers
  never on board, calibration retreat), plus moderate and low-severity issues.
- Defines the two-phase fix plan implemented in this release.

---

## [0.31.0] — 2026-03-29 — Custom mode rework (puzzle rework phase 7a)

### Backend — Puzzle generator (`backend/solver/generator/puzzle_generator.py`)
- **`generate_puzzle()`** gains four new keyword arguments used when `difficulty == "custom"`:
  `min_board_sets` (default 8), `max_board_sets` (default 14), `min_chain_depth` (default 0),
  `min_disruption` (default 0). All are ignored for non-custom difficulties.
- Custom mode now applies **chain depth** and **disruption** filters (previously bypassed entirely).
- Custom mode now **computes uniqueness** (`check_uniqueness()`) and stores the result in
  `PuzzleResult.is_unique` — informational only, never a generation gate.
- Board sizing for custom is now fully explicit (`min_board_sets`/`max_board_sets`) rather
  than derived from `sets_to_remove` via a formula.
- `_COMPUTES_UNIQUE` gains `"custom": True`.

### Backend — API models (`backend/api/models.py`)
- `PuzzleRequest` gains four new custom-mode fields: `min_board_sets`, `max_board_sets`,
  `min_chain_depth`, `min_disruption` (all validated and defaulted).
- `sets_to_remove` maximum expanded from **5 to 8** to allow larger custom puzzles.

### Backend — API endpoint (`backend/api/main.py`)
- `puzzle_endpoint()` passes all five custom parameters to `generate_puzzle()`.

### Frontend — Puzzle controls (`frontend/src/components/PuzzleControls.tsx`)
- **Custom mode** now shows a full parameter panel instead of a single "sets to remove"
  stepper. Parameters exposed: sets to sacrifice (1–8), board sets range (5–25),
  min chain depth (0–4 with descriptive label), min disruption (0–60, step 5).
- **Slow-generation warning** (amber) appears when settings are likely to be slow:
  `min_chain_depth ≥ 2`, `min_disruption ≥ 20`, or `sets_to_remove ≥ 6`.
- **Uniqueness info note** (grey) is always shown in the custom panel explaining that
  uniqueness is computed and displayed but not enforced.
- `Stepper` extracted as a local helper function to de-duplicate ±-button markup.

### Frontend — Types (`frontend/src/types/api.ts`)
- `PuzzleRequest` gains `min_board_sets?`, `max_board_sets?`, `min_chain_depth?`,
  `min_disruption?` optional fields.

### Frontend — i18n (`frontend/src/i18n/messages/en.json` + `de.json`)
- Added 11 new `puzzle.*` keys for the custom parameter panel labels, chain depth level
  names, slow-generation warning, and uniqueness info note.

### Backend — Tests
- `test_custom_sets_to_remove_six_422` renamed to `test_custom_sets_to_remove_nine_422`
  (6 is now valid; 9 is the first invalid value).
- 5 new tests in `test_puzzle_endpoint.py`: chain depth respected, disruption respected,
  board size params accepted, `sets_to_remove=8` valid, `is_unique` present for custom.
- 5 new tests in `test_puzzle_generator.py`: same invariants at unit level.

### Frontend — Tests
- `PuzzleControls.test.tsx`: replaced old single-stepper tests with new custom panel
  tests; 4 new tests: panel shows all controls, sets-to-sacrifice range 1–8, slow warning
  hidden by default, uniqueness note always visible, custom request contains all params.

### New file — `PUZZLE_REWORK_STATUS.md`
- Root-level document tracking which phases of the Puzzle Rework Plan were implemented,
  where deviations occurred, and what remains open.

---

## [0.30.0] — 2026-03-29 — Frontend integration (puzzle rework phase 6)

### Frontend — Puzzle controls (`frontend/src/components/PuzzleControls.tsx`)
- **Nightmare difficulty button** added to the difficulty selector row.
  Players can now request Nightmare-tier puzzles directly from the UI.
- **Metadata badge** displayed below the difficulty buttons after a puzzle loads.
  Shows chain depth (e.g. "Chain depth: 3") and, for Expert/Nightmare puzzles with a
  verified unique solution, a green "✓ Unique solution" indicator.

### Frontend — Game store (`frontend/src/store/game.ts`)
- **`lastPuzzleMeta`** field (`chainDepth`, `isUnique`, `difficulty`) added to `GameState`.
  Populated by `loadPuzzle` after each successful puzzle fetch; cleared by `reset()`.
  Chain depth defaults to `0` and `isUnique` to `false` when the API omits those fields.

### Frontend — i18n (`frontend/src/i18n/messages/en.json` + `de.json`)
- Added `puzzle.nightmare`, `puzzle.chainDepth`, `puzzle.uniqueSolution` translation keys.
  EN: "Nightmare", "Chain depth: {depth}", "Unique solution".
  DE: "Albtraum", "Kettenfolge: {depth}", "Einzige Lösung".

### Frontend — Tests
- **`PuzzleControls.test.tsx`**: updated to assert Nightmare button is present; 6 new tests
  covering nightmare selection, nightmare puzzle request, and stats badge visibility (null,
  chain depth shown, unique indicator shown/hidden).
- **`game.test.ts`**: 4 new tests verifying `lastPuzzleMeta` initial value, population from
  `loadPuzzle`, default values for missing response fields, and clearance on `reset()`.
  Added `vi.mock("../../lib/api")` so `loadPuzzle` runs without real HTTP calls.

---

## [0.29.0] — 2026-03-29 — API pool integration (puzzle rework phase 5)

### Backend — API models (`backend/api/models.py`)
- **`PuzzleRequest`** gains `seen_ids: list[str]` (default `[]`, max 500 entries).
  The client sends UUIDs of previously seen puzzles so the API can avoid returning
  duplicates when drawing from the pre-generated pool.
- **`PuzzleResponse`** gains `puzzle_id: str` (default `""`).
  Set to the UUID assigned at pre-generation time for pool-drawn puzzles; empty string
  for live-generated puzzles (Easy/Medium/Hard/Custom, or expert/nightmare fallback).

### Backend — API endpoint (`backend/api/main.py`)
- **Expert and Nightmare requests** now first attempt to draw from the pre-generated
  SQLite pool (`PuzzleStore.draw(difficulty, exclude_ids=seen_ids)`).
  If the pool is empty or all stored puzzles are excluded, the endpoint falls through
  to live generation (same behaviour as v0.28.0 and earlier).
- Easy, Medium, Hard, and Custom continue to use live generation exclusively.
- Pool hits are logged as `puzzle_pool_hit`; exhausted pools as `puzzle_pool_empty`.

### Backend — Tests
- **`backend/tests/api/test_puzzle_endpoint.py`** — 13 new tests in 3 new classes:
  - `TestSeenIdsValidation` (4): absent / empty / valid / too-many
  - `TestPuzzleIdField` (4): presence and empty-string guarantee for non-pool tiers
  - `TestPoolIntegration` (5): pool hit, pool empty (fallback), seen_ids forwarding,
    nightmare pool, easy bypasses pool — all using `monkeypatch` + `MagicMock`

### Frontend — Type definitions (`frontend/src/types/api.ts`)
- `PuzzleRequest` gains optional `seen_ids?: string[]`.
- `PuzzleResponse` gains `puzzle_id: string`.

### Frontend — Game store (`frontend/src/store/game.ts`)
- `GameState` gains `seenPuzzleIds: string[]`, hydrated from `localStorage` at startup.
- `loadPuzzle()` automatically injects `seen_ids` into every request and accumulates
  `puzzle_id` values returned by the API (non-empty only).
- Seen IDs are persisted under `rummikub_seen_puzzles` in `localStorage` and capped
  at 500 entries to bound storage growth.

---

## [0.28.0] — 2026-03-29 — Pre-generation system (puzzle rework phase 4)

### Backend — Puzzle generator (`backend/solver/generator/puzzle_generator.py`)
- **`PuzzleResult`** gains `joker_count: int = 0`. Defaults to `0` for all current
  puzzles (the generator is still joker-free). The field is present so `PuzzleStore`
  can record it in the database and the schema stays stable when joker support lands.

### Backend — Puzzle store (`backend/solver/generator/puzzle_store.py`) — new file
- **`PuzzleStore`** class: SQLite-backed pool for pre-generated puzzles.
  - `__init__(db_path)`: creates the file and schema on first use; parent directories
    are created automatically.
  - `store(result, seed?) → str`: persists a `PuzzleResult` and returns its UUID.
  - `draw(difficulty, exclude_ids?) → (PuzzleResult, str) | None`: draws a random
    unseen puzzle, skipping any IDs in `exclude_ids`. Returns `None` when the pool
    is exhausted.
  - `count(difficulty?) → int`: total stored puzzles, optionally filtered by difficulty.
  - `close()`: closes the SQLite connection.
- Schema: `puzzles(id, difficulty, board_json, rack_json, chain_depth, disruption,
  rack_size, board_size, is_unique, joker_count, seed, created_at)` with an index
  on `difficulty` for fast pool queries.
- Default DB path: `data/puzzles.db`; overridable via `PUZZLE_DB_PATH` env var.

### Backend — Pre-generation CLI (`backend/solver/generator/pregenerate.py`) — new file
- `python -m solver.generator.pregenerate --difficulty nightmare --count 200` generates
  N puzzles at the given difficulty and stores them in the SQLite pool.
- `--all` generates for `hard`, `expert`, and `nightmare` in sequence.
- `--stats` prints per-difficulty pool counts and exits.
- Real-time progress: `[n/total] chain=N disrupt=N unique=T rack=N (rate/s)`.

### Backend — Tests
- **`backend/tests/solver/test_puzzle_store.py`** — 21 new tests in 4 classes:
  `TestPuzzleStoreInit` (3), `TestStoreAndCount` (6), `TestDraw` (6), `TestRoundtrip` (6).
  All use the pytest `tmp_path` fixture for isolated ephemeral SQLite files.
  A module-scoped `_medium_result` fixture generates one `medium` puzzle once per
  module to avoid repeated ILP calls.

---

## [0.27.0] — 2026-03-29 — Puzzle generation integration (puzzle rework phase 3)

### Backend — Puzzle generator (`backend/solver/generator/puzzle_generator.py`)

- **`_MIN_CHAIN_DEPTHS`** dict added: Easy/Medium `0`, Hard `1`, Expert `1`, Nightmare `2`.
  `_attempt_generate()` rejects any candidate whose `solution.chain_depth` is below the
  floor for the requested difficulty. The check is free — `chain_depth` is already computed
  by `solve()` (Phase 1) — and runs before the expensive uniqueness gate.

- **`_COMPUTES_UNIQUE`** dict added: `expert` and `nightmare` set to `True`; all other
  tiers `False`. When set, `check_uniqueness()` (Phase 2) is called once per returned
  puzzle and the result is stored in `PuzzleResult.is_unique` for informational use.
  Generation does NOT gate on uniqueness: the complete-sacrifice strategy inherently
  yields non-unique solutions on large boards (many equivalent rearrangements exist for
  100%-rack-placement puzzles); uniqueness gating is deferred to a future strategy.

- **"nightmare" difficulty tier** added across all config dicts:
  - Board: 15–20 sets (before sacrifice)
  - Sacrifice: 6 complete sets removed
  - Rack: 5–7 tiles
  - Disruption: ≥ 38 (strictly above Expert's typical floor)
  - Chain depth: ≥ 3 (deep rearrangement chains)
  - Uniqueness: enforced

- **`PuzzleResult`** gains two new fields:
  - `chain_depth: int = 0` — populated from `solution.chain_depth` after each successful
    candidate. Reflects the longest rearrangement dependency chain in the ILP solution.
  - `is_unique: bool = True` — `True` if uniqueness is not required for this difficulty
    (Easy/Medium/Hard/Custom) or if `check_uniqueness()` confirmed a single optimal
    arrangement (Expert/Nightmare).

### Backend — API models (`backend/api/models.py`)

- **`PuzzleRequest.difficulty`** Literal extended with `"nightmare"`.
- **`PuzzleResponse`** gains `chain_depth: int = 0` and `is_unique: bool = True`.

### Backend — API endpoint (`backend/api/main.py`)

- `puzzle_endpoint` maps `result.chain_depth` and `result.is_unique` into `PuzzleResponse`.
- Version bumped to `0.27.0`.

### Frontend — Types (`frontend/src/types/api.ts`)

- `Difficulty` union extended with `"nightmare"`.
- `PuzzleResponse` interface gains `disruption_score: number` (was missing from the TS
  mirror despite being returned by the backend since v0.22.0), `chain_depth: number`,
  and `is_unique: boolean`.

### Backend — Tests

- **`backend/tests/solver/test_puzzle_generator.py`** — 28 new tests in 4 classes:
  - `TestPuzzleResultNewFields` (7 tests): verifies `chain_depth` and `is_unique` are
    present and correct for every difficulty tier including `custom`.
  - `TestChainDepthFiltering` (5 tests): confirms `_MIN_CHAIN_DEPTHS` floors are enforced
    across multiple seeds and that the config dict covers all standard tiers.
  - `TestNightmareDifficulty` (9 tests): nightmare generates, rack/disruption/chain_depth
    constraints met, `is_unique` is a bool (informational), determinism, solvability,
    valid board sets. Fixture-scoped to run the expensive generation only once.
  - `TestUniquenessComputation` (6 tests): `_COMPUTES_UNIQUE` covers all tiers; Expert and
    Nightmare compute and store `is_unique` (may be True or False); non-expert defaults True.
- **`backend/tests/api/test_puzzle_endpoint.py`** — 5 new tests in `TestPuzzleResponseNewFields`:
  `chain_depth` and `is_unique` present on easy response; expert response meets both floors;
  nightmare endpoint returns 200 with correct rack range, `is_unique=True`, `chain_depth ≥ 3`.

---

## [0.26.0] — 2026-03-29 — Uniqueness check (puzzle rework phase 2)

### Backend — ILP formulation (`backend/solver/engine/ilp_formulation.py`)

- **`build_ilp_model()` gains `excluded_solutions: list[list[int]] | None = None`** parameter.
  Each entry is a list of candidate-set indices (`active_set_indices`) from a prior solve.
  For each entry the constraint `Σ_{s ∈ active} y[s] ≤ len(active) - 1` is added, forcing
  HiGHS to find a structurally different arrangement on the next run.

- **`extract_solution()` now returns a 5-tuple** `(new_sets, placed_tiles, remaining_rack,
  is_optimal, active_set_indices)`. The new fifth element is the list of candidate-set
  indices where `y[s] = 1` in the ILP solution — used by `check_uniqueness()` as input
  to the next exclusion constraint.

### Backend — Solution model (`backend/solver/models/board_state.py`)

- **`active_set_indices: list[int] = []`** field added to `Solution` dataclass. Stores
  the ILP `y[s] = 1` indices for the solved arrangement. Not exposed in the API response
  (the API models map fields explicitly). Populated automatically by `solve()`.

### Backend — Solver (`backend/solver/engine/solver.py`)

- All three `extract_solution()` call sites in `solve()` updated to unpack the new 5-tuple.
  Fallback / timeout paths use `active_set_indices = []`.
- **`check_uniqueness(state, solution, rules) → bool`** added:
  re-solves the ILP with the first solution's active sets excluded. Returns `True` if
  the original solution is the only arrangement that places `solution.tiles_placed` tiles
  (i.e. the re-solve is infeasible or places fewer tiles). Returns `False` if an
  alternative arrangement exists. Designed for offline puzzle pre-generation where a
  puzzle with two equally-valid solutions is too easy.
- `_UNIQUENESS_TIMEOUT_SECONDS = 10.0` constant added (separate from the 30 s solve cap).

### Backend — Tests

- **`backend/tests/solver/test_ilp_solver.py`** — 10 new tests:
  active-indices extraction, exclusion-constraint correctness, infeasibility when only
  one solution exists, multiple-exclusion chaining, and integration with `solve()`.
- **`backend/tests/solver/test_uniqueness.py`** — new file with 26 tests across 5 classes:
  unique solutions (single run, joker with no ambiguity, rearrangement-forced uniqueness),
  non-unique solutions (two equivalent groups, tile fits two runs, symmetric board,
  joker ambiguity), rules integration (first-turn, meld threshold), and edge cases
  (empty `active_set_indices`, determinism, zero-tile scenario).

---

## [0.25.0] — 2026-03-29 — Chain depth metric (puzzle rework phase 1)

### Backend — Objective metrics (`backend/solver/engine/objective.py`)

- **`compute_chain_depth(old_board_sets, new_board_sets, placed_tiles) → int`** added
  alongside the existing `compute_disruption_score()`. Measures how many distinct
  disrupted old sets feed tiles into the most complex new set in a solution:
  - `0` = pure placement — no board rearrangement required
  - `1` = simple rearrangement — one or more sets broken, each new set draws
    from at most one disrupted source
  - `2` = two-step convergence — one new set combines freed tiles from two
    separately disrupted old sets (requires two breaking steps)
  - `3+` = deep chains — N disruptions all feed into a single new set

  This is the foundation metric for Expert/Nightmare difficulty tiers in the
  forthcoming puzzle rework.

### Backend — Solution model (`backend/solver/models/board_state.py`)

- **`chain_depth: int = 0`** field added to `Solution` dataclass — every solve
  result now carries its chain depth automatically, with no API changes needed.

### Backend — Solver (`backend/solver/engine/solver.py`)

- Imports and calls `compute_chain_depth()` after each solve and stores the result
  in the returned `Solution`.

### Backend — Tests (`backend/tests/solver/test_objective.py`)

- 26 new unit tests covering `compute_chain_depth()`:
  - Depth-0 cases: empty board, untouched sets, rack-only placement, reordering
  - Depth-1 cases: simple splits, freed-tile + rack placement, independent parallel
    disruptions, single tile migration between sets
  - Depth-2 cases: two disrupted sets converging in one new set
  - Depth-3+ cases: three-disruption convergence
  - Edge cases: joker tiles, `copy_id` sensitivity, group sets, large boards
  - Integration: parallel vs. chained disruptions, stable sets mixed with disrupted

---

## [0.24.1] — 2026-03-26 — Mobile header overflow fix

### Frontend — Header (`frontend/src/app/[locale]/page.tsx`)

- **Header wraps gracefully on narrow screens**: added `flex-wrap gap-y-2` to the outer
  header div so title and controls stack to two rows on viewports where they don't fit
  side-by-side (e.g. 375px iPhones in German locale where "Zurücksetzen" is ~96px wide).

- **`whitespace-nowrap` on checkbox label and reset button**: prevents "Erster Zug"
  wrapping mid-label and "Zurücksetzen" clipping at the edge of the screen.

- **Controls gap reduced from `gap-3` → `gap-2`** (saves 4px per gap, no visual impact on
  desktop); controls row right-aligns (`justify-end`) when it wraps to a second line.

---

## [0.24.0] — 2026-03-26 — iOS Home Screen icon & version display

### Frontend — iOS PWA icon (`frontend/public/`)

- **Proper apple-touch-icon added** (`apple-touch-icon.png`, 180×180 RGB PNG): replaces
  the missing icon that iOS Safari would fall back to a screenshot for. No transparency —
  iOS requirement. Icon shows 4 Rummikub tiles in a 2×2 grid in the game's four colors
  (red, blue, black, orange) on the app's blue theme background.

- **Manifest icons regenerated**: `icon-192.png` (192×192) and `icon-512.png` (512×512)
  replaced — previous placeholders were only ~2 KB, rendering as a blurry smear at any
  size. New icons use the same tile design, safe-zone compliant for maskable use.

- **manifest.json updated**: 180×180 entry added to the `icons` array.

### Frontend — iOS Home Screen title (`frontend/src/app/[locale]/layout.tsx`)

- **`apple-mobile-web-app-title` fixed to `"RummiSolve"`** (10 characters): "RummikubSolve"
  at 13 characters sits right at the iOS truncation boundary and shows "..." on some
  devices. 10 characters fits every iPhone grid size without truncation.

- **`<link rel="apple-touch-icon">` added** via Next.js `icons.apple` metadata field —
  ensures iOS Safari picks up the 180×180 icon rather than guessing.

### Frontend — Version display (`frontend/src/app/[locale]/page.tsx`, `next.config.ts`)

- **Subtle version footer**: `v0.24.0` renders as a single xs-sized muted line at the
  bottom of the main column. Visible but unobtrusive.

- **Version sourced from `package.json`** via `NEXT_PUBLIC_APP_VERSION` env var injected
  in `next.config.ts` — single source of truth; bumping `package.json` version
  automatically updates the displayed string on next build.

### Version sync (`frontend/package.json`)

- `"version"` field corrected from `"0.1.0"` to `"0.24.0"` to match the real changelog
  state; was left at the project-scaffold default and never updated.

---

## [0.23.0] — 2026-03-23 — SolutionView UX refinement & navigation improvements

### Frontend — SolutionView restructure (`frontend/src/components/SolutionView.tsx`)

- **Step navigator moved above board list**: the Prev/Next buttons, Before→After panel,
  and progress dots now render immediately below the summary bar — no scrolling required
  to reach the tutorial controls, even on Expert puzzles with 13-18 board sets.

- **"Rack tiles this step" row added to Before→After panel**: each step card now shows
  a labelled row with the exact rack tiles being placed in that step (highlighted in yellow).
  For pure board-rearrangement steps (no rack tiles), an italic fallback message is shown
  ("Board rearrangement — no rack tiles this step").

- **Rack progress tracker**: a mini strip below the Before→After panel displays every rack
  tile placed across all steps. Tiles from already-completed steps are dimmed (`opacity-40`),
  the current step's tiles are highlighted with a yellow ring, future-step tiles are slightly
  faded (`opacity-60`), and unplaced tiles (remaining_rack) appear at the end without a ring.
  The tracker is only rendered when there are tiles to show.

- **Unchanged sets collapsed by default**: the board overview now hides unchanged (gray)
  sets by default, reducing visual clutter on complex boards. A toggle link ("Show all N sets" /
  "Hide unchanged") lets the user expand them. State resets to collapsed on each new solution.
  The step-highlight logic is preserved because the filter runs after index-mapping
  (`.map((set, si) => ({ set, si })).filter(…).map(({ set, si }) => …)`), keeping `si`
  aligned to the original `new_board` indices.

### Frontend — Auto-scroll to solution (`frontend/src/app/[locale]/page.tsx`)

- **Smooth scroll on solve**: after a successful solve, the page automatically scrolls to
  the solution section (`scrollIntoView({ behavior: "smooth", block: "start" })`). Users
  no longer have to manually scroll past the entire board input to find the result.

### Frontend — PuzzleControls auto-close (`frontend/src/components/PuzzleControls.tsx`)

- **Panel collapses after puzzle loads**: the `<details>` element is programmatically closed
  when `isPuzzleLoading` transitions from `true` to `false`, reclaiming screen space after
  a puzzle is loaded. A `wasLoadingRef` guard prevents premature closing on initial page render.

### Frontend — Translations (`frontend/src/i18n/messages/en.json`, `de.json`)

- Added 5 new keys under `"solution"`: `rackThisStep`, `boardRearrangeOnly`, `rackProgress`,
  `showUnchanged`, `hideUnchanged` — both English and German.

---

## [0.22.0] — 2026-03-23 — Disruption-based puzzle difficulty system

### Puzzle generation — core feature

- **All difficulties now require genuine board rearrangement** (`backend/solver/generator/puzzle_generator.py`):
  Easy, Medium, Hard, and Expert all use the "complete sacrifice" strategy — N sets are
  removed entirely from the board and M rack tiles are sampled from them. Because the source
  sets no longer exist on the board, the player cannot trivially re-add any tile; board
  disruption is mandatory for every difficulty. The old Easy/Medium/Hard strategies (run-end
  removal, single-set removal) are replaced.

- **Disruption score classifies difficulty** (`puzzle_generator.py`): after generating a
  candidate puzzle and solving it, `compute_disruption_score()` is called on the solution.
  The score must fall in the difficulty's target band or the attempt is discarded. Non-overlapping
  bands guarantee Expert puzzles always require more disruption than Hard:
  Easy 2–10 · Medium 9–18 · Hard 16–28 · Expert 26+.

- **Unified sacrifice extraction helper** (`_extract_by_sacrifice()`): replaces four separate
  extraction functions. Parameterised by sacrifice count and rack-size range; tries up to 20
  tile samples per board before giving up so the outer retry loop only retriggers on genuinely
  hard-to-satisfy configurations.

- **Rack sizes updated**: Easy 2–3 · Medium 3–4 · Hard 4–5 · Expert 2–6 (wild — unpredictability
  is part of the Expert challenge). Expert is no longer pinned to exactly 2 tiles.

- **`PuzzleResult.disruption_score`** (new field): the disruption score of the generating
  solution is stored and returned to callers. Exposed in the API response as `disruption_score`.

- **Difficulty constants centralised**: `_RACK_SIZES`, `_SACRIFICE_COUNTS`, `_DISRUPTION_BANDS`,
  `_BOARD_SIZES` — adjust any of these to tune generation behaviour without touching algorithm
  logic.

### Metric fix

- **`compute_disruption_score()` rewritten with content-based matching**
  (`backend/solver/engine/objective.py`): old algorithm compared set indices, which inflated
  scores whenever the solver reordered unchanged sets. New greedy algorithm: for each old board
  set, find the new set that contains the most of its tiles (best match); tiles not in that set
  are counted as disrupted. A reordered-but-identical board now scores 0. An extended set
  (rack tile added to an unchanged set) also scores 0.

### Future-proofing: dual-solution groundwork

- **`secondary_objective` parameter added to `build_ilp_model()` and `solve()`**
  (`backend/solver/engine/ilp_formulation.py`, `solver.py`): default is `"tile_value"`
  (unchanged behaviour). Passing `"disruption"` raises `NotImplementedError` with a detailed
  comment describing the planned encoding — so the dual-solution feature (two solutions:
  minimise tile value vs minimise disruption) can be wired in without refactoring the call
  sites.

### API

- **`PuzzleResponse.disruption_score`** (`backend/api/models.py`): new integer field exposed
  in every `/api/puzzle` response. Clients can display or log the score; it is also the
  mechanism through which future difficulty visualisation can be built.

### Testing

- **`test_objective.py`** (8 tests, +4): added `test_no_disruption_reordered_sets` (key
  regression for the content-based fix), `test_disruption_split_set`,
  `test_full_disruption_tiles_scattered`, `test_multiple_sets_partial_disruption`. Updated
  `test_full_disruption_all_tiles_moved` → now expects 0 (reordering no longer inflates score).

- **`test_puzzle_generator.py`** (26 tests, +8): `test_disruption_score_in_band_*` for all
  four non-custom difficulties; `test_all_difficulties_require_no_trivial_extension`;
  `test_puzzle_result_has_disruption_score`; updated rack-size and Expert assertions.

- **`test_puzzle_endpoint.py`** (+2 assertions): `disruption_score` field present and ≥ 0 in
  all puzzle responses; Expert `disruption_score` ≥ 26; Expert rack size 2–6 (was `== 2`).

---

## [0.21.0] — 2026-03-22 — Expert difficulty — 2026-03-22 — Full-repo audit fixes (post-v0.19)

### Infrastructure — P0

- **Backend port 8000 no longer exposed on host** (`docker-compose.yml`): removed
  `ports: - "8000:8000"` from the backend service. Backend is reachable only through
  the nginx proxy on port 80, preventing direct LAN access that bypassed CORS headers.
  Same treatment applied to frontend port 3000.
- **Frontend healthcheck + nginx startup sequencing** (`docker-compose.yml`): added a
  `healthcheck` to the frontend service (`curl -f http://localhost:3000`, 15 s start period)
  and updated nginx `depends_on` to use `condition: service_healthy` for both backend and
  frontend. Eliminates 502 errors during cold-start when Next.js was still initialising.
- **Removed deprecated `version: "3.9"` field** (`docker-compose.yml`): Docker Compose v2+
  ignores this field and emits deprecation warnings.

### Infrastructure — P1

- **nginx `X-Forwarded-Proto` header** (`nginx/nginx.conf`): added
  `proxy_set_header X-Forwarded-Proto $scheme` to all three proxy locations. Needed for
  future TLS setups (Tailscale, Cloudflare Tunnel) so the backend knows the original scheme.
- **nginx `client_max_body_size 1m`** (`nginx/nginx.conf`): explicit request-body limit
  replacing the implicit nginx default. Prevents confusion if tile payloads ever grow.

### API contract — P1

- **`SolveResponse.status` narrowed** (`backend/api/models.py`): removed unused `"error"`
  literal from the status type. The endpoint never returns `"error"` — errors are raised as
  `HTTPException`. TypeScript clients now get the accurate `"solved" | "no_solution"` union.
- **`BoardSetOutput.type` and `TileOutput.color` tightened** (`backend/api/models.py`):
  changed from plain `str`/`str | None` to `Literal["run","group"]` and
  `Literal["blue","red","black","yellow"] | None`. Frontend TypeScript clients now receive
  the same specific types as they send.
- **`RulesInput` comment on `joker_retrieval`** (`backend/api/models.py`): added inline
  comment explaining the field is intentionally absent from the API model until the ILP
  formulation implements it.

### Documentation — P1 / P2

- **`solver.py` docstring timeout** (`backend/solver/engine/solver.py`): corrected stale
  "2 s hard cap" to "30 s" (raised in v0.12.1). Added note that Blueprint §4.2 is outdated.
- **`solver.py` `id()` comment** (`backend/solver/engine/solver.py`): added inline comment
  on the `id()`-based board-tile tracking explaining why it is safe and pointing to the
  key-tuple alternative used in `solution_verifier.py`.
- **`set_enumerator.py` wrap-run gap** (`backend/solver/generator/set_enumerator.py`):
  added NOTE to `enumerate_runs()` docstring documenting that `allow_wrap_runs=True` affects
  the validator but not the ILP template generation.
- **`objective.py` dual-solution comment** (`backend/solver/engine/objective.py`): updated
  module docstring to explain `compute_disruption_score()` is not currently called but is
  preserved for a planned dual-solution feature (disruption-minimising vs value-minimising).
- **`Blueprint.md` drift disclaimer** (`Blueprint.md`): added a header note listing known
  divergences between the Blueprint and the actual implementation (timeout, deleted modules,
  deployment target, puzzle generator status).

### Testing — P3

- **`PuzzleControls.test.tsx`** (new, 7 Vitest tests): covers difficulty button rendering,
  active-selection class, disabled state while loading, and `loadPuzzle` called with correct
  difficulty and an `AbortSignal`. Total Vitest tests: 33 → **40**.
- **`test_ilp_solver.py`** (+1 test): `test_allow_wrap_runs_does_not_produce_wrap_templates`
  documents the known gap where `allow_wrap_runs=True` affects validation but the ILP
  enumerator never generates wrap templates.
- **`test_solve_endpoint.py`** (+1 test): `test_empty_rack_returns_no_solution` verifies
  that an empty rack (`{"board": [], "rack": []}`) returns a 200 with `status="no_solution"`
  and `tiles_placed=0`. Protects the no-min-length schema contract.

Total backend tests: 189 → **191 pass**.

---

## [0.19.0] — 2026-03-22 — Post-v0.18 audit fixes

### Fixed — bugs

- **`game.ts:loadPuzzle`**: `isBuildingSet` was not reset to `false` when a puzzle loaded
  successfully, leaving the set-builder dialog open with the new board's data. Fixed by adding
  `isBuildingSet: false` to the success-path `set({...})` call.

- **`game.ts:loadPuzzle`**: race condition if called twice in rapid succession (possible in the
  render-cycle window before the disabled button re-renders). Fixed by: (a) adding `get` to the
  Zustand create callback and checking `get().isPuzzleLoading` at entry; (b) adding
  `AbortSignal` support to `fetchPuzzle` in `lib/api.ts`; (c) managing an `abortRef` in
  `PuzzleControls.tsx` that cancels any still-in-flight request before starting a new one
  (mirrors the pattern already used for `/api/solve` in `page.tsx`).

- **`api/main.py:_tile_to_input`**: used `assert` (disabled by `python -O`) instead of an
  explicit `raise ValueError` for the non-joker nil-check. Also replaced two
  `# type: ignore[arg-type]` comments on enum `.value` assignments with `cast()` calls, making
  the mypy strict-mode suppression explicit and self-documenting.

- **`set_enumerator.py`**: confusing `(c, _)` unpacking on line 256 in the Type-3 double-joker
  group loop discarded the number from `grp_keys` and silently relied on the outer-scope
  `number` variable. Renamed to `(c, n)` and used `n` directly — semantically identical but
  no longer fragile under refactoring.

### Added — tests

- `test_puzzle_generator.py`: `test_rack_tiles_not_in_board` — verifies no `(color, number,
  copy_id)` triple appears in both `board_sets` and `rack` (tile conservation invariant).
- `test_puzzle_generator.py`: `test_copy_ids_valid` — verifies all tiles have `copy_id` in
  `{0, 1}` (bounds guard for `_assign_copy_ids`).
- `test_set_enumerator.py`: `test_double_joker_group_variants` — verifies Type-3 generation
  produces valid double-joker group templates (not just runs).
- `test_ilp_solver.py`: `test_two_jokers_placed_across_multiple_tile_sets` — verifies both
  jokers are placed (not left in hand) when sufficient tiles exist; does not prescribe which
  sets they land in.
- `test_ilp_solver.py`: `test_group_with_two_jokers_from_rack` — verifies a 4-tile group
  `[Blue5, Red5, Joker0, Joker1]` is fully placed (exercises group path of double-joker
  constraint).
- `test_puzzle_endpoint.py`: `test_default_difficulty_uses_medium` — verifies POST with empty
  body returns `difficulty="medium"`.
- `test_puzzle_endpoint.py`: `test_board_set_min_tiles_count` — verifies every board set in
  the response has ≥ 3 tiles (Rummikub minimum).

Total tests: 182 → **189 pass**.

---

## [0.18.0] — 2026-03-22 — Puzzle Generator (Phase 6b)

### Added

- **`POST /api/puzzle`** — new endpoint that returns a randomly generated, pre-verified
  Rummikub practice puzzle. Accepts `difficulty` ("easy"/"medium"/"hard") and an optional
  `seed` for reproducibility. Returns `board_sets`, `rack`, `difficulty`, and `tile_count`.
  503 on generation failure (retry-able), 422 on invalid difficulty.

- **`solver/generator/puzzle_generator.py`** — core algorithm:
  - Enumerates all valid runs + groups on a full 104-tile (non-joker) pool.
  - Greedily selects 5–9 compatible sets (no shared physical tile copies).
  - Extracts the rack according to difficulty:
    - `easy`: 2–3 tiles from the ends of long runs (remaining run stays ≥ 3 tiles).
    - `medium`: removes 1 complete set (3–5 tiles).
    - `hard`: removes 2 complete sets (6–12 tiles).
  - Verifies solvability: `solve(board, rack).tiles_placed == len(rack)`.
  - Raises `PuzzleGenerationError` after `max_attempts` (default 150).

- **Frontend — Practice Puzzle panel** (`PuzzleControls.tsx`):
  - Collapsible panel (same `<details>/<summary>` pattern as RulesPanel).
  - Three difficulty toggle buttons (Easy / Medium / Hard).
  - "Get Puzzle ▶" button with spinner while loading.
  - On load: populates board and rack; clears previous solution.
  - Mounted in `app/[locale]/page.tsx` between RulesPanel and RackSection.

- **Frontend i18n** — `puzzle` namespace added to `en.json` and `de.json`
  (keys: `title`, `easy`, `medium`, `hard`, `getButton`, `loading`, `error`).

- **TypeScript** — `PuzzleRequest` / `PuzzleResponse` / `Difficulty` types in `types/api.ts`.
  `fetchPuzzle()` function in `lib/api.ts`. `isPuzzleLoading` state + `loadPuzzle()` action
  in `store/game.ts`.

### Tests

- `tests/solver/test_puzzle_generator.py` — 9 unit tests covering happy path for each
  difficulty, board validity, full solvability, rack-size minima, determinism, and error handling.
- `tests/api/test_puzzle_endpoint.py` — 6 integration tests covering all three difficulties,
  invalid input (422), required fields, and seeded determinism.
- `frontend/e2e/puzzle_mode.spec.ts` — E2E: open panel → select Easy → Get Puzzle → Solve.

---

## [0.17.0] — 2026-03-22 — Double-joker solver fix (Phase 6a)

### Fixed — solver correctness

- **Type-3 double-joker template generation** (`solver/generator/set_enumerator.py`):
  `enumerate_valid_sets` now generates variants where 2 jokers occupy any 2 positions in a
  run or group, when at least 2 physical jokers are available. Uses a direct enumeration
  approach (like the existing Type-2 fill-missing) covering all sub-cases: both slots
  available, both missing, or one of each. Enables sets like `[Joker, Red5, Joker]` (run
  4-5-6 with both jokers) that were previously silently unreachable.

- **Slot satisfaction fix for multi-joker templates** (`solver/engine/ilp_formulation.py`):
  The slot-satisfaction loop previously added the constraint `Σ_jokers x[t][s] = y[s]` once
  per joker slot, which is redundant for double-joker templates — one physical joker could
  satisfy both copies and the template could activate with only 1 joker. Replaced with a
  single combined constraint `Σ_jokers x[t][s] = (num_joker_slots) * y[s]` per template,
  requiring exactly as many physical jokers as there are joker slots. Fully backward-
  compatible: single-joker templates produce the same constraint as before (coefficient=1).

### Tests

- `test_two_jokers_from_rack_placed_in_one_set` — rack `[Joker, Red5, Joker]` → all 3 placed.
- `test_two_jokers_on_board_preserved` — board `[Joker, Red5, Joker]`, empty rack → no crash,
  board intact, solution valid.
- `test_two_jokers_on_board_with_rack_tile_placed` — board has double-joker set + rack tile →
  solver does not crash, solution passes verification.
- `test_two_jokers_generates_double_joker_variants` — Type-3 templates generated when 2 jokers
  in pool; all pass rule checker.
- `test_one_joker_no_double_joker_variants` — no double-joker templates with only 1 joker.

---

## [0.16.0] — 2026-03-22 — CI hardening & version sync (P2 session)

### Fixed
- **Version sync**: bumped `backend/pyproject.toml` and `backend/api/main.py` from stale
  `0.13.0` to `0.16.0`; updated version assertion in `tests/api/test_solve_endpoint.py`
  to match.
- **Docker healthcheck**: added `healthcheck:` directive to the `backend` service in
  `docker-compose.yml` (`curl -f http://localhost:8000/health`, 10 s interval, 5 retries).
  Without this, the `frontend` `depends_on: backend: condition: service_healthy` condition
  caused `docker compose up` to hang indefinitely.

### CI
- **Vitest wired into frontend CI** (`.github/workflows/frontend.yml`): added
  `npm run test` step after the build step so all 33 Vitest unit tests run on every push
  and pull request to `main` or `claude/**` branches.

---

## [0.15.0] — 2026-03-22 — Testing & quality improvements (P1 session)

### Testing — frontend

- **Vitest unit test setup** (`frontend/vitest.config.ts`, `package.json`): installed
  Vitest 2.x with `@vitejs/plugin-react`, `jsdom`, `@testing-library/react`, and
  `@testing-library/jest-dom`. Added `test` and `test:watch` npm scripts. E2E spec
  files are excluded via `vitest.config.ts` to prevent Playwright tests being picked
  up by Vitest. Total: 33 unit tests.
- **Zustand store tests** (`src/__tests__/store/game.test.ts`, 15 tests): covers every
  action — `addRackTile`, `removeRackTile`, `addBoardSet`, `removeBoardSet`,
  `updateBoardSet`, `setIsFirstTurn`, `setIsBuildingSet`, `setLoading`, `setError`,
  `setSolution`, and `reset`.
- **Tile component tests** (`src/__tests__/components/Tile.test.tsx`, 11 tests): number
  rendering, joker star symbol, `size` variant CSS classes (`xs`/`sm`/`md`), remove
  button presence and callback, and highlight ring on/off.
- **LocaleSwitcher component tests** (`src/__tests__/components/LocaleSwitcher.test.tsx`,
  7 tests): EN/DE button rendering, active locale `bg-blue-600` class, `aria-current`
  attribute, inactive locale calls `router.replace`, active locale click is a no-op.

### Testing — E2E viewport expansion

- **Mobile and tablet viewports** (`playwright.config.ts`): added Pixel 5 (393×851,
  Android mid-range) and iPhone SE (375×667, smallest supported iPhone) Playwright
  projects alongside the existing Desktop Chrome project. All 5 existing spec files now
  run across 3 device profiles (15 total test runs). No spec changes required — tests
  use role/text locators that work at any viewport.

### Testing — backend property tests

- **Hypothesis property-based solver tests** (`tests/solver/test_ilp_solver.py`,
  3 new tests, 60-40 examples each): addresses Audit Report finding of only 1 existing
  Hypothesis test.
  - `test_property_tile_conservation`: verifies `placed_tiles + remaining_rack == rack`
    for any random rack (no tiles created or lost by the solver).
  - `test_property_output_sets_are_valid`: verifies every set in the solution passes
    `is_valid_set` for any random rack input.
  - `test_property_first_turn_threshold_respected`: verifies that when `is_first_turn=True`,
    any placement meets the 30-point meld threshold.

### Fixes

- **pyproject.toml version** (`backend/pyproject.toml`): bumped from `0.6.0` to `0.13.0`
  to match `api/main.py` (missed in the previous session).

---

## [0.14.0] — 2026-03-22 — Deployment fixes & polish (P0/P1/P2 session)

### Deployment — critical fixes (P0)

- **nginx reverse proxy** (`nginx/nginx.conf`, `docker-compose.yml`): added nginx service
  on port 80 that proxies `/api/*` and `/health` to `backend:8000` and everything else to
  `frontend:3000`. Set `NEXT_PUBLIC_API_URL: ""` in the frontend Docker build args so the
  browser uses relative URLs (`/api/solve`) — resolves the critical issue where the baked-in
  `http://backend:8000` URL was unreachable by browsers outside Docker.
- **Container restart policies** (`docker-compose.yml`): added `restart: unless-stopped` to
  backend and frontend services so containers recover automatically after server reboots.
- **Version bump** (`backend/api/main.py`): `app.version` updated from `"0.6.0"` to
  `"0.13.0"` so `/health` returns the correct version.

### Cleanup — P1

- **Remove dead output module** (`backend/solver/output/`): deleted the empty
  `__init__.py` left from the v0.7.0 module deletion. No imports referenced it.
- **Document joker_retrieval stub** (`backend/solver/config/rules.py`): added a NOTE
  comment and a `# TODO` marker clarifying that the field is accepted for forward
  compatibility but has no effect on ILP behaviour.
- **PWA icons** (`frontend/public/icons/`, `manifest.json`): generated 192×192 and
  512×512 PNG icons (blue `#1e40af` background, white "R" lettermark) and populated
  `manifest.json`'s previously-empty `"icons"` array. Enables PWA installation on mobile.

### Polish — P2

- **Dark mode** (6 frontend component files): wired up the existing CSS variables from
  `globals.css` to Tailwind `dark:` classes across `page.tsx`, `RackSection`,
  `BoardSection`, `SolutionView`, `RulesPanel`, and `LocaleSwitcher`. Uses
  `prefers-color-scheme` media strategy — no JS toggle required. Tile colors (red/blue/
  black/yellow) intentionally left unchanged as they carry semantic meaning.
- **README home-server deployment guide** (`README.md`): added Home Server Deployment
  section explaining the nginx proxy architecture, setup steps, and HTTPS options
  (Tailscale / Cloudflare Tunnel). Updated Docker section and environment variable table.
- **.env.example** (`env.example`): updated `NEXT_PUBLIC_API_URL` comment to clarify
  Docker vs local development usage.

---

## [0.13.0] — 2026-03-21 — UX cleanup & solver quality improvements

### UX improvements (frontend)

- **Tooltips on solution badges** (`SolutionView.tsx`): the `↺`, `NEU`/`NEW`, `+`,
  and `unverändert`/`unchanged` badges now show a `title` tooltip on hover explaining
  what each status means. Both EN and DE strings added to `messages/*.json`.
- **Tiles sorted within runs** (`SolutionView.tsx`): tiles inside a run-type solution
  set are now sorted ascending by number before display (e.g. 7 · 8 · 9 instead of
  7 · 9 · 8). Original indices are preserved for rack-tile highlighting.
- **Move descriptions fully translated** (`SolutionView.tsx`): move instruction text
  was previously returned as English-only strings from the backend. The frontend now
  reconstructs localised descriptions from structured data (`new_board`, `new_tile_indices`,
  `set_index`) using new ICU translation keys (`moveDesc.*`, `colors.*`, `types.*`) in
  both `en.json` and `de.json`.
- **Add-set builder appears at top** (`BoardSection.tsx`): the inline tile-picker for
  adding a new board set previously rendered below all existing sets, requiring scroll
  when many sets were present. It now appears immediately below the section header.
- **Auto-detect run vs group** (`BoardSection.tsx`): removed the manual "Folge / Gruppe"
  type selector. The app now tries `run` first and `group` second, accepts whichever
  validates, and shows the detected type in the confirmation feedback. This also removes
  the now-unused `typeRun` / `typeGroup` translation keys from the component logic.
- **Rack tiles counted in board set picker** (`BoardSection.tsx`): the tile-grid picker
  used when building a board set did not account for tiles already on the rack. A tile
  present on the rack now shows count ≥ 1 in the picker, preventing double-booking.

### Solver improvement (backend)

- **Minimise remaining tile value as secondary objective** (`engine/ilp_formulation.py`):
  when no perfect solution exists (not all rack tiles can be placed), the ILP now
  prefers arrangements that leave the lowest total face value in hand. Implemented by
  adding `tile.number / 200.0` to each hand variable's objective coefficient — small
  enough to never override the primary "maximise tiles placed" goal.

---

## [0.12.1] — 2026-03-21 — Post-release solver & test patches

### Bug fixes

- **Backend — duplicate-board-set infeasibility** (`generator/set_enumerator.py`):
  when the board contained two identical sets (e.g. two copies of Red 1-2-3 using both
  physical tile copies), the ILP had only one binary template for that set and could not
  activate it twice → declared infeasible. Each base template is now duplicated up to
  N times where N = `min(available copies of required tiles)`, resolving the constraint.
- **Backend — joker-board infeasibility** (`generator/set_enumerator.py`,
  `engine/solver.py`): type-1 joker variants were incorrectly restricted to rack tiles,
  causing infeasibility when a joker was a board tile whose covered number also appeared
  elsewhere on the board. Reverted to generating type-1 variants for all tile positions
  with fingerprint-based deduplication. Solver timeout raised from 2 s to 30 s for
  complex joker boards.
- **Backend — timeout leaves board tiles unplaced** (`engine/solver.py`): if HiGHS
  timed out before finding a feasible integer solution, `extract_solution` could return
  a partial result missing board tiles. Added a post-extraction guard that detects
  missing board tiles and falls back to no-move (unchanged board, full rack in hand).
- **Backend — copy_id always 0** (`api/main.py`, `validator/solution_verifier.py`):
  all tiles were assigned `copy_id=0` regardless of duplicates, so the ILP treated
  both physical copies of a tile as the same variable. Replaced `_tile_input_to_domain`
  with `_assign_copy_ids` which assigns `copy_id=0`/`1` based on occurrence order
  across board + rack tiles together.
- **Frontend — RulesPanel `FORMATTING_ERROR`** (`components/RulesPanel.tsx`):
  `dangerouslySetInnerHTML` combined with `t()` caused next-intl to throw
  `FORMATTING_ERROR` because `<strong>` tags were parsed as unresolved ICU variables.
  Switched to `t.rich()` with a `strong` component renderer — no `dangerouslySetInnerHTML`
  needed, no XSS surface.
- **E2E — strict-mode locator violations** (`e2e/board_section.spec.ts`,
  `e2e/extend_board_set.spec.ts`): tile buttons and type labels matched multiple
  elements when both the rack and board-builder pickers were visible simultaneously.
  Scoped all tile interactions to the containing `section` element and updated
  assertions to match actual rendered text.

---

## [0.12.0] — 2026-03-21 — Phase 10: Post-merge Bug Fixes, New Tests & Changelog

### Bug fixes

- **Backend — joker validation** (`api/models.py`): a tile sent as
  `{"joker": true, "color": "red"}` previously passed Pydantic validation and
  silently violated the domain invariant. A guard now raises
  `"Joker tiles must not have a color or number."`, returning HTTP 422.
- **Backend — event-loop blocking** (`api/main.py`): the `/api/solve` endpoint
  was declared `async def` despite containing no async I/O. Changed to `def` so
  FastAPI correctly routes it through a thread pool and the event loop stays free
  for other requests.
- **Backend — Counter type annotations** (`api/main.py`): `Counter` generics
  used `str | None` for tile colour fields, but the domain `Tile.color` is a
  `Color` enum. Updated to `Color | None` for correct mypy inference.
- **Frontend — concurrent-solve race condition** (`app/[locale]/page.tsx`):
  rapid clicks on "Solve" would send overlapping requests; a slower response
  could overwrite a newer one. An `AbortController` stored in a `useRef` now
  cancels the previous in-flight fetch before starting a new one. `AbortError`
  is silently swallowed so the UI stays clean.
- **Frontend — missing `aria-live`** (`app/[locale]/page.tsx`): the error
  banner had `role="alert"` but no `aria-live` attribute. Added
  `aria-live="assertive"` so screen readers announce errors immediately.
- **Frontend — accidental reset** (`app/[locale]/page.tsx`): the Reset button
  wiped all board/rack data without confirmation. A `window.confirm()` guard is
  now shown whenever tiles or sets are present. The confirmation message is
  fully translated (`page.resetConfirm` in `en.json` / `de.json`).

### New tests

- **Backend API** — 9 new tests added to `tests/api/test_solve_endpoint.py`,
  each following strict AAA (Arrange / Act / Assert) structure:
  - `test_solve_group_happy_path` — three same-number different-colour tiles
  - `test_solve_with_joker_in_run` — joker fills a gap in a run
  - `test_solve_extends_existing_board_set` — rack tile extends a board run
  - `test_solve_two_tiles_in_rack_returns_no_solution` — insufficient tiles
  - `test_solve_response_contains_all_required_fields` — schema completeness
  - `test_is_unchanged_true_for_unmodified_board_set` — `is_unchanged` flag
  - `test_new_tile_indices_populated_for_rack_tile` — highlight index accuracy
  - `test_joker_with_color_returns_422` — validates joker guard (B1 above)
  - `test_joker_with_number_returns_422` — validates joker guard (B1 above)
- **Backend unit** — 3 new tests added to `tests/test_models.py`:
  - `test_tile_input_joker_minimal_valid` — bare joker is valid
  - `test_tile_input_joker_with_color_raises` — ValidationError expected
  - `test_tile_input_joker_with_number_raises` — ValidationError expected
- **E2E Playwright** — 2 new spec files:
  - `e2e/board_section.spec.ts` — add a set via UI, verify it renders
  - `e2e/extend_board_set.spec.ts` — add board run + rack tile, solve,
    assert extend move shown with correct set reference

---

## [0.11.0] — 2026-03-21 — Phase 9: Multi-language i18n (EN + DE)

### New features

- **`next-intl ^3`** installed; URL-based locale routing (`/en/`, `/de/`) via
  `next-intl/middleware` and `defineRouting`.
- **`src/middleware.ts`** (new): routes every request through next-intl middleware so
  the browser is redirected to `/en` or `/de` based on `Accept-Language` headers and
  cookie preference.
- **`src/i18n/config.ts`** (new): single source of truth — `locales = ["en", "de"]`,
  `defaultLocale = "en"`, exported `Locale` type.
- **`src/i18n/routing.ts`** (new): `defineRouting({ locales, defaultLocale })` consumed
  by middleware and `createNavigation`.
- **`src/i18n/request.ts`** (new): `getRequestConfig` dynamically imports the matching
  `messages/{locale}.json` file per request.
- **`src/i18n/navigation.ts`** (new): typed `Link`, `useRouter`, `usePathname` via
  `createNavigation(routing)`.
- **`src/i18n/messages/en.json`** (new): ~100 English strings across namespaces:
  `common`, `meta`, `page`, `rulesPanel`, `rack`, `board` (with `errors`), `tilePicker`,
  `tile`, `solution`, `errorBoundary`, `localeSwitcher`. ICU plurals for tile counts
  and move summaries.
- **`src/i18n/messages/de.json`** (new): full German translation (e.g.
  `page.solve` → "Lösen", `rack.heading` → "Deine Steine",
  `board.heading` → "Tisch-Sätze", `solution.badge.new` → "NEU").
- **`src/app/[locale]/layout.tsx`** (new): locale-aware root layout with
  `<html lang={locale}>`, `<NextIntlClientProvider>`, and `generateMetadata` using
  translated title/description.
- **`src/app/[locale]/page.tsx`** (new): main page moved here; uses
  `useTranslations("page")` and renders `<LocaleSwitcher />`.
- **`src/components/LocaleSwitcher.tsx`** (new): EN / DE toggle buttons using
  `useLocale()` + typed `router.replace(pathname, { locale })` — no page reload needed.

### Updated components

- `BoardSection.tsx`: `validateSet` now returns `{ key, params } | null` instead of a
  plain string; component resolves the translation key via `t(key, params)`. Headings,
  labels, buttons, and error messages fully translated.
- `RackSection.tsx`, `RulesPanel.tsx`, `SolutionView.tsx`, `TileGridPicker.tsx`,
  `Tile.tsx`, `ErrorBoundary.tsx` — all use `useTranslations(namespace)`.
- `ErrorBoundary.tsx`: added optional `heading?` and `fallback?` props + new
  `TranslatedErrorBoundary` functional wrapper that injects translated strings.
- `src/app/layout.tsx`: reduced to a pass-through wrapper (HTML/body live in
  `[locale]/layout.tsx`).
- `next.config.ts`: wrapped with `createNextIntlPlugin`.

### Bug fixes

- Fixed ruff formatting in `backend/api/main.py` and `backend/api/models.py`
  (trailing whitespace / alignment issues flagged by CI).

---

## [0.10.0] — 2026-03-21 — Phase 8: Rules Panel + Solution Clarity

### New features

- `RulesPanel.tsx` (new): collapsible "ℹ How sets work" panel inserted between the
  page header and the rack picker. Uses native `<details>/<summary>` — zero JS, zero
  React state, closed by default. Explains Run, Group, First-turn threshold (≥30 pts),
  and Joker rules.
- `page.tsx`: imports and renders `<RulesPanel />`.

### Solution display improvements

- **4-way set-status badges** (`SolutionView.tsx`): sets in the solution board now carry
  a colored border + badge derived entirely from existing fields (`is_unchanged`,
  `new_tile_indices`, `tiles.length`) — no new API data needed:
  - **NEW** (green border + green badge) — all tiles came from the rack
  - **+** (blue border + blue badge) — existing set extended with rack tiles
  - **↺** (amber border + amber badge) — board tiles reshuffled, no new tiles
  - *unchanged* (gray, muted) — set is identical to the pre-solve board
- **Move summary line**: one-liner above the step list, e.g.
  *"3 moves: 2 new sets, 1 extension"*, computed from `solution.moves`.
- **Action-typed move bullets**: the numbered circle next to each instruction is now
  color-coded — green for `create`, blue for `extend`, amber for `rearrange`.
  The `action` field was already present in `MoveOutput` but was never surfaced in
  the UI.

### Verification

```
tsc --noEmit:  0 errors
next build:    clean
```

---

## [0.9.0] — 2026-03-21 — Phase 7: Physical Executability

### Bug fixes

- **`new_tile_indices` over-highlighting** (`api/main.py`): replaced `placed_key_set`
  (a plain Python `set`) with a `Counter` that is consumed one entry at a time as tiles
  are matched. Previously, when the same tile appeared in both the board and the rack
  (e.g. Red 5 on board + Red 5 in rack), the set collapsed both copies to one key and
  highlighted every matching tile — including board tiles never placed from the rack.

### New features

- **`is_unchanged` field** (`api/models.py`, `api/main.py`): `BoardSetOutput` now
  carries `is_unchanged: bool`. Computed in `main.py` by comparing each new set's tile
  multiset (`Counter` of color+number+joker) against the old board sets. A set is
  unchanged when no rack tiles were added AND the tile composition matches an existing
  board set exactly.
- **Set numbers in solution UI** (`SolutionView.tsx`): each set in the solution board
  now displays a bold number prefix ("1.", "2.", …) that directly corresponds to the
  set indices referenced in move instructions ("Add to set 2").
- **Source-set hint in rearrange descriptions** (`move_generator.py`): pure-board
  rearrangement moves now say *"Take tiles from set 2 and reform as run: Red 4, Red 5,
  Red 6"* instead of the previous opaque *"Rearrange into run: …"*. The best-matching
  old set is found by tile-key overlap and referenced by 1-based index.
- **`is_unchanged` in frontend types** (`types/api.ts`): `BoardSetOutput` extended
  with `is_unchanged?: boolean`.

### Verification

```
pytest:       147 passed, 0 failed
tsc --noEmit: 0 errors
next build:   clean
```

---

## [0.8.0] — 2026-03-21 — Phase 6: UX Flow Fixes

### Bug fixes

- **Rack picker tile count** (`RackSection.tsx`): `tileCount` now sums tiles across
  both `rack` AND `boardSets`, enforcing the 2-copy Rummikub limit globally. Previously
  only rack tiles were counted, allowing >2 copies of the same tile when some were
  already on the board.
- **Pydantic 422 error format** (`api.ts`): `detail` arrays (FastAPI's default Pydantic
  validation shape) are now joined into a readable string instead of rendering as
  `[object Object],[object Object]`.
- **`SolutionView` null safety** (`SolutionView.tsx`): all `.map()`, `.length`, and
  `.includes()` calls on `new_board`, `moves`, `remaining_rack`, and `new_tile_indices`
  guarded with optional chaining / `?? []` to prevent runtime render crashes when any
  field is unexpectedly null.

### New features

- **`isBuildingSet` store field** (`store/game.ts`): builder open/closed state moved
  from local `useState` in `BoardSection` into the Zustand store. `reset()` clears it
  via `initialState`. Enables page-level awareness of the builder state.
- **Solve button guarded** (`page.tsx`): Solve is disabled and shows *"Finish editing
  first"* while the board set builder is open (`isBuildingSet`), preventing the solver
  from running with incomplete board state.
- **Board locked during solve** (`BoardSection.tsx`): Add Set / Edit (✎) / Remove (×)
  buttons are disabled while `isLoading`, preventing mid-flight board mutations that
  would make the response inconsistent with what was sent.
- **Reset closes builder** (`BoardSection.tsx` + `store/game.ts`): clicking Reset now
  also closes the builder UI because `isBuildingSet` is part of `initialState`.
- **`ErrorBoundary` component** (`ErrorBoundary.tsx`, new): React class-based error
  boundary wrapping `<SolutionView>`. Render errors that previously surfaced only in the
  browser console now show a user-friendly red fallback panel instead of a blank screen.

### Verification

```
tsc --noEmit: 0 errors
next build:   clean
```

---

## [0.7.0] — 2026-03-21 — Phase 5: Cleanup, Polish & API Tests

### Bug fixes

- `api/main.py`: `MoveOutput.set_index` was dropped during serialisation — fixed
  by passing `set_index=m.set_index` in the list comprehension.
- `api/main.py` + `pyproject.toml`: version was `"0.2.0"` / `"0.1.0"` (Phase 2
  artefacts never updated); both now read `"0.6.0"`.
- `BoardSection.tsx`: `TileGridPicker` inside the set builder had no `tileCount`
  prop — users could add more than 2 copies of a tile to a board set, violating
  game rules. Now tracks tiles in the pending set + existing board sets.

### New features

- Board set editing: each set now has an ✎ edit button that repopulates the
  inline builder. `updateBoardSet` (already in the store) is wired up.
- `SolveResponse.is_first_turn` field echoed back to frontend; `SolutionView`
  uses it to show "Below threshold" vs "No valid move" in the `no_solution` case.

### Validation

- `models.py`: Pydantic `Field` constraints added —
  board set `tiles` requires 3–13 entries; `rack` capped at 104;
  `board` capped at 50 sets. Invalid inputs now return 422 with clear messages.
- `solution_verifier.py`: added first-turn meld-threshold check as defense-in-depth.

### Tests

- `tests/api/test_solve_endpoint.py` (new): 9 integration tests covering `/health`,
  `/api/solve` happy paths, 422 error paths, first-turn rules, and `set_index`
  serialisation. Uses `httpx.AsyncClient` + ASGI transport (no real network).
- `test_rule_checker.py`: one Hypothesis property test — `is_valid_set` must return
  a `bool` for any tile combination (200 random examples, never raises).

### Code quality

- Deleted dead-code stubs: `solver/output/solution_formatter.py`,
  `diff_calculator.py`, `explanation.py` — logic already inlined in `main.py`.
- Fixed `type: ignore[arg-type]` in `main.py` with an explicit `Literal` annotation.
- Added per-request `structlog` line in `/api/solve` handler.
- Added `role="alert"` on the frontend error banner.

### Docs

- `README.md`: added environment-variable table, E2E test instructions, expanded
  Docker Compose section, and dev-status link.
- `CHANGELOG.md`: this entry.

---

## [0.6.0] — 2026-03-21 — Phase 4: Observability, Containerisation & E2E Tests

### What was implemented

**Observability — `backend/api/main.py`**

- Sentry SDK initialised at startup via `SENTRY_DSN` env var; no-op (zero overhead)
  when the variable is unset or empty. `traces_sample_rate=0.1` captures 10 % of
  transactions for performance monitoring. `send_default_pii=False` by default.
- `structlog` now configured explicitly: JSON renderer in `ENVIRONMENT=production`,
  colored `ConsoleRenderer` in development. Log level set to `INFO` via standard
  `logging.basicConfig`.
- CORS `allow_origins` now driven by `ALLOWED_ORIGIN` env var (default `"*"`).
  Fixes a pre-existing spec violation where `allow_credentials=True` was combined
  with the wildcard origin; credentials are now disabled when the origin is `"*"`.

**Environment documentation — `.env.example`**

- Documents all four env vars with defaults, descriptions, and production examples:
  `SENTRY_DSN`, `ENVIRONMENT`, `ALLOWED_ORIGIN`, `NEXT_PUBLIC_API_URL`.
- `docker-compose.yml` updated to forward `ENVIRONMENT`, `SENTRY_DSN`, and
  `ALLOWED_ORIGIN` from the host shell / `.env` file into the backend container.

**Frontend containerisation**

- `frontend/next.config.ts`: `output: "standalone"` uncommented — Next.js emits a
  self-contained `server.js` + minimal `node_modules` tree during `next build`.
- `frontend/Dockerfile`: multi-stage image (`node:22-alpine` builder → runner).
  `NEXT_PUBLIC_API_URL` accepted as a `--build-arg` (baked into the JS bundle at
  build time). Non-root `nextjs` user in the runtime stage.
- `docker-compose.yml`: `frontend` service added; depends on `backend`
  `service_healthy` so the UI waits for the API before accepting traffic.

**Playwright E2E tests — `frontend/e2e/`**

- `playwright.config.ts`: Chromium-only, `webServer` auto-starts `next dev`,
  single worker + 1 retry in CI, HTML report artifact on failure.
- `package.json`: `@playwright/test ^1.50.0` added to devDependencies; `e2e` and
  `e2e:ui` npm scripts added.
- `e2e/solve_basic_run.spec.ts`: adds Red 10–12 to rack, solves, asserts
  "3 tiles placed" + "Optimal" + "Move instructions" visible.
- `e2e/solve_first_turn.spec.ts` (2 tests): first-turn pass (33 ≥ 30) and
  first-turn block (15 < 30 → "no tiles can be placed").
- `e2e/tile_limit.spec.ts`: clicks same tile twice, asserts button is disabled on
  the second copy (count ≥ 2).

**CI — `.github/workflows/e2e.yml`**

- Triggered on pushes/PRs touching `backend/**` or `frontend/**`.
- Starts the FastAPI backend in the background, waits for `/health` with retries,
  then runs Playwright (which auto-starts the Next.js dev server via `webServer`).
- Uploads the Playwright HTML report as a workflow artifact on failure (7-day
  retention).

### Verification (all passed before commit)

```
pytest:          137 passed, 0 failed
ruff check:      0 errors
ruff format:     clean
mypy strict:     no issues in 24 source files
tsc --noEmit:    0 errors (includes playwright.config.ts)
next lint:       0 warnings / errors
next build:      ✓ standalone output — .next/standalone/server.js present
```

### What is NOT here yet

- Actual deployment to Vercel + Fly.io (requires external service configuration)
- PWA icon assets (manifest.json placeholder remains)
- Database / persistence layer (stateless solver by design)

---

## [0.5.0] — 2026-03-21 — Phase 2b + 3b: First-Turn Rule, Move Generator & Tile Count Limits

### What was implemented

**Phase 2b — First-Turn ILP Constraint**

- `backend/solver/engine/ilp_formulation.py`: Constraint 3 added — when `rules.is_first_turn=True`,
  encodes `Σ placed_tile_numbers ≥ initial_meld_threshold` as an upper-bound row on `h[t]` variables.
  Jokers contribute 0 points toward the threshold. If the rack value is below the threshold the
  upper bound becomes negative, HiGHS returns `kInfeasible`, and `solver.py` maps that to 0 tiles placed.
- `backend/solver/engine/solver.py`: First-turn solves build a rack-only `BoardState(board_sets=[], rack=...)`;
  `ValueError` from an infeasible ILP is caught and returned as a "no play" outcome instead of a 422 error;
  original board sets are prepended to the result unchanged so the full board is always in the response.
- 6 new ILP tests: above threshold, below threshold, exact threshold, board preservation, board-tile
  isolation, and joker-has-no-value.

**Phase 3b — Move Generator**

- `backend/solver/generator/move_generator.py`: replaces `NotImplementedError` with a diff-based
  implementation. For each new set, partitions tiles into rack-origin vs board-origin and classifies
  the move as `create` (set built entirely from rack), `extend` (rack tiles added to an identifiable
  existing set — carries `set_index`), or `rearrange` (board tiles redistributed across sets).
  Unchanged board sets emit no instruction.
- `backend/solver/engine/solver.py`: `generate_moves` wired in; `moves=[]` placeholder removed.
- 7 new move-generator unit tests in `tests/solver/test_move_generator.py`.

**Phase 3b — Tile Count Limits (frontend)**

- `frontend/src/components/TileGridPicker.tsx`: new optional `tileCount` prop; tile buttons are
  disabled at count ≥ 2 (Rummikub maximum) and show a small count badge overlay when ≥ 1 copy is
  already in the rack.
- `frontend/src/components/RackSection.tsx`: per-tile counts derived from the rack array via
  `useCallback` and passed to `TileGridPicker`.
- `frontend/src/components/SolutionView.tsx`: numbered "Move instructions" section rendered when
  `solution.moves.length > 0`.

### Verification (all passed before commit)

```
pytest:          137 passed, 0 failed  (124 existing + 13 new)
ruff check:      0 errors
ruff format:     clean
mypy strict:     no issues in 24 source files
tsc --noEmit:    0 errors
next lint:       0 warnings / errors
next build:      ✓ clean
```

### What is NOT here yet (next phase)

- Sentry integration — Phase 4
- Playwright E2E tests — Phase 4
- Frontend Dockerfile / standalone containerisation — Phase 4
- Environment variable documentation (`.env.example`) — Phase 4

---

## [0.4.0] — 2026-03-21 — Phase 3: Frontend Core UI

### What was implemented

**`frontend/src/lib/api.ts`** — API client

- `solvePuzzle(request) → Promise<SolveResponse>`: POST to `/api/solve`
- Reads `NEXT_PUBLIC_API_URL` (falls back to `http://localhost:8000`)
- Throws with backend `detail` message on non-2xx; catches JSON parse failures

**`frontend/src/components/Tile.tsx`** — tile chip component

- Three sizes: `xs` (20×24 px, used in picker), `sm` (28×32 px), `md` (36×40 px)
- Color backgrounds via static `BG` map (`tile-blue/red/black/yellow` from Tailwind config)
- Joker renders `★` in yellow-on-dark; `highlighted` prop adds a yellow ring (marks newly placed tiles); `onRemove` renders an `×` overlay button

**`frontend/src/components/TileGridPicker.tsx`** — 4×13 click grid

- 4 rows (blue, red, black, yellow) × 13 columns (1–13) + joker button
- Uses `size="xs"` + `gap-[2px]`: grid is 284 px, fits 320 px–375 px screens without overflow
- Purely presentational; calls `onSelect(tile)` on click

**`frontend/src/components/RackSection.tsx`** — rack input and display

- Embeds `TileGridPicker`; clicking adds tile via `addRackTile`
- Displays current rack as removable tile chips

**`frontend/src/components/BoardSection.tsx`** — board set editor

- Lists existing sets with per-set remove button
- "Add Set" opens inline set-builder: RUN/GROUP toggle + `TileGridPicker` for pending tiles + confirm/cancel

**`frontend/src/components/SolutionView.tsx`** — solution display

- Handles all three statuses: `solved` (summary bar + new board + remaining rack), `no_solution` (yellow callout), `error` (red callout)
- Tiles in `new_tile_indices` rendered with `highlighted` ring to identify rack placements

**`frontend/src/app/page.tsx`** — main page (replaced placeholder)

- `"use client"` single-column mobile layout: header (title + first-turn toggle + reset), rack, board, solve button, error banner, solution
- Solve button disabled while loading or rack is empty
- `handleSolve` dispatches to Zustand store: `setLoading` → `solvePuzzle` → `setSolution` / `setError`

**Fixes applied after audit:**

- `Tile`: added `xs` size (20 px wide) so the picker grid fits all screens ≥ 320 px
- `SolutionView`: `status="error"` now shows a red callout instead of falling through to a broken render
- `globals.css`: `overflow-x: hidden` on body prevents horizontal page scroll
- `manifest.json`: removed references to non-existent icon files

### Verification (all passed before commit)

```
tsc --noEmit:   0 errors
next lint:      0 warnings / errors
next build:     ✓ 3.36 kB page bundle
```

### What is NOT here yet (next phases)

- `generator/move_generator.py` — human-readable move instructions (Phase 3b)
- Per-tile quantity limits in UI — max 2 copies per tile type (Phase 3b)
- Board set edit (currently only delete) (Phase 3b)
- Initial meld threshold constraint in ILP (`rules.is_first_turn` — Phase 2b)
- PWA icons (placeholder icons needed before Phase 4 deploy)
- Sentry integration — Phase 4
- Playwright E2E tests — Phase 4

---

## [0.3.0] — 2026-03-21 — Phase 2: ILP Solver + API Endpoint

### What was implemented

**`backend/solver/generator/set_enumerator.py`** — joker expansion added to `enumerate_valid_sets`

- Two types of single-joker variants generated when jokers are in the pool:
  - **Type 1 (substitute):** joker replaces an *available* tile in a base template, freeing that tile for another set
  - **Type 2 (fill-missing):** joker fills a slot whose non-joker tile is *absent* from the pool — enabling templates that couldn't otherwise form (e.g., [Red 4, Joker, Red 6] when Red 5 is missing)
- `enumerate_runs` and `enumerate_groups` remain unchanged (pure non-joker, used as base)
- No jokers in pool → result is identical to Phase 1a (existing tests unchanged)

**`backend/solver/engine/ilp_formulation.py`** — ILP model construction

- `ILPModel` dataclass: wraps a `highspy.Highs` instance + variable index mappings (`y_vars`, `x_vars`, `h_vars`, `rack_tile_indices`)
- `build_ilp_model(state, candidate_sets, rules) → ILPModel`:
  - **Variables:** `y[s] ∈ {0,1}` per template, `x[t,s] ∈ {0,1}` per (tile, template) pair (sparse), `h[t] ∈ {0,1}` per rack tile
  - **Constraint 1 — Tile conservation:** board tiles placed exactly once; rack tiles placed or held
  - **Constraint 2 — Slot satisfaction:** each template slot filled by exactly one matching physical tile when the template is active
  - **Objective:** minimize Σ h[t] (= maximize tiles placed from rack)
  - Joker slots detected from `tile.is_joker` on template tiles; physical jokers fill them
  - Infeasible board → encoded as `0 = 1` constraint so HiGHS propagates infeasibility
- `extract_solution(model) → (new_sets, placed_tiles, remaining_rack, is_optimal)`:
  - Reads `col_value` with EPS=0.5 threshold; treats `kModelEmpty` (empty pool) as optimal

**`backend/solver/engine/solver.py`** — main orchestrator

- `solve(state, rules) → Solution`:
  1. `enumerate_valid_sets` → candidate templates
  2. `build_ilp_model` → HiGHS model
  3. `model.highs.run()` with 2-second time limit
  4. `extract_solution` → Solution dataclass
  5. `verify_solution` → raises `ValueError` if post-verification fails
- Returns `is_optimal=True` when HiGHS proves optimality (always for typical game sizes)

**`backend/solver/engine/objective.py`** — disruption scoring

- `compute_disruption_score(old_board_sets, new_board_sets) → int`: counts board tiles that moved to a different set index; used as a post-solve metric (not yet encoded in ILP objective)

**`backend/solver/validator/solution_verifier.py`** — post-solve verification

- `verify_solution(state, solution, rules) → bool`:
  - All sets in `solution.new_sets` pass `is_valid_set`
  - `placed_tiles ∪ remaining_rack == original_state.rack` (by tile keys)
  - Tiles in `new_sets == board_tiles ∪ placed_tiles` (multiset equality)

**`backend/api/main.py`** — `/api/solve` endpoint activated (Phase 2)

- `POST /api/solve` converts Pydantic request → domain `BoardState`, calls `solve()`, converts `Solution` → `SolveResponse`
- `new_tile_indices` annotated per set (identifies which tiles came from the rack)
- Returns `status: "solved"` if any tiles placed, `"no_solution"` if rack unchanged
- Error paths: 422 for invalid input or infeasible board

**`backend/tests/solver/test_ilp_solver.py`** — 22 known-answer ILP tests

- Empty board rack-only plays: minimal run, minimal group, 4-tile group, 13-tile run, too-short rack
- Extending existing board sets: end, start, both ends; gap prevents extension
- Board rearrangement: merging runs across positions to place more rack tiles
- Group from rack without disturbing board; all-four-color group
- Duplicate tiles: both copies of same tile usable in different sets simultaneously
- Joker: fills gap in run, fills slot in group, stays in hand when no compatible set
- Edge cases: empty rack (is_optimal=True), solve_time_ms > 0

**`backend/tests/solver/test_solution_verifier.py`** — 9 tests for verify_solution

**`backend/tests/solver/test_objective.py`** — 5 tests for compute_disruption_score

### Verification (all passed before commit)
```
pytest:         124 passed, 0 failed  (88 existing + 36 new)
ruff check:     0 errors
ruff format:    clean
mypy strict:    no issues in 24 source files
```

### What is NOT here yet (next phases)
- `generator/move_generator.py` — human-readable move instructions (Phase 3)
- `output/` modules — diff, formatter, explanation (Phase 3)
- Initial meld threshold constraint in ILP (rules.is_first_turn — Phase 2b)
- Double-joker template variants (currently only single-joker expansion)
- Frontend UI components (tile grid picker, board display, solution view) — Phase 3
- Sentry integration — Phase 4
- Playwright E2E tests — Phase 4

---

## [0.2.0] — 2026-03-21 — Phase 1a: Rule Checker + Set Enumerator

### What was implemented

**`backend/solver/validator/rule_checker.py`** — first real solver logic; pure Python, no dependencies

- `is_valid_set(tileset, rules)` — returns True/False for any TileSet:
  - Dispatches to `_is_valid_run` or `_is_valid_group` based on `tileset.type`
  - **Run validation:** separates jokers from non-jokers; checks same-color, no duplicate
    numbers, then verifies jokers cover internal gaps (`n_max-n_min+1 - len(non_jokers) ≤ len(jokers)`);
    finally checks a valid start position `a` exists within `[1, 14-total]` containing all
    non-joker numbers; respects `rules.allow_wrap_runs`
  - **Group validation:** checks ≤4 tiles total, same number, distinct colors among non-jokers,
    and len(jokers) ≤ (4 - distinct color count)
- `is_valid_board(state, rules)` — checks every set passes `is_valid_set` and that no physical
  tile `(color, number, copy_id, is_joker)` appears more than once across all board sets

**`backend/solver/generator/set_enumerator.py`** — pre-computes candidate sets for the ILP

- `enumerate_runs(state)` — iterates 4 colors × starts 1–11 × ends start+2–13; includes a run
  template only when every required `(color, number)` has ≥1 copy in `state.all_tiles`;
  templates use `copy_id=0` as a placeholder (ILP resolves physical tile assignment)
- `enumerate_groups(state)` — iterates 13 numbers × size-3 and size-4 color combinations
  (`itertools.combinations`); same availability check
- `enumerate_valid_sets(state)` — combines runs + groups; TODO comment marks the joker-expansion
  point needed before Phase 2 ILP work

**`backend/tests/conftest.py`** — added `full_tile_pool` fixture (all 104 non-joker tiles in rack)

**`backend/tests/solver/test_rule_checker.py`** — 42 known-answer tests covering:
- Valid runs: minimal, long, full span (1–13), joker fills gap, joker extends start/end,
  two jokers, boundary cases (ending at 13, starting near 1)
- Invalid runs: too short, gap without joker, mixed colors, duplicate number, too long (14 tiles),
  span too wide for joker count
- Valid groups: size 3 and 4, with joker, boundary numbers
- Invalid groups: too short, too large (5 tiles), duplicate color, different numbers, too many jokers
- Wrap-around rule variant (disabled by default; enabled via RulesConfig)
- Board validation: empty, valid multi-set, invalid set in board, duplicate physical tile, two
  legal copies of same tile

**`backend/tests/solver/test_set_enumerator.py`** — 18 known-answer tests covering:
- Full pool: 264 runs, 65 groups, 329 total (exact arithmetic verified)
- Spot-checks: Red 4-5-6 present, Blue 1-13 present, specific groups present
- Minimal pool: only Red 4-5-6 → exactly 1 run template
- Missing tile: pool without Red 5 → no run containing 5
- Single-number pool: all four "7" tiles → exactly 5 group templates (C(4,3)+C(4,4))
- Three-color pool: only one 3-color group possible, no 4-color group
- Missing color: no groups include a color absent from the pool
- Empty pool: 0 runs, 0 groups
- Cross-validation: every enumerated template passes `is_valid_set`

### Verification (all passed before commit)
```
pytest:         88 passed, 0 failed  (28 existing + 60 new)
ruff check:     0 errors
ruff format:    clean
mypy strict:    no issues in 24 source files
```

### What is NOT here yet (next phases)
- Joker-expansion in `enumerate_valid_sets` (marked TODO — needed for ILP Phase 2)
- `solution_verifier.py` (depends on rule_checker; implements full post-solve cross-check)
- `engine/ilp_formulation.py` — ILP model construction with HiGHS (Phase 2)
- `engine/solver.py` — main orchestrator: enumerate → formulate → solve → verify (Phase 2)
- `engine/objective.py` — `compute_disruption_score` secondary objective (Phase 2)
- `generator/move_generator.py` — human-readable move instructions (Phase 2/3)
- `output/` modules — diff, formatter, explanation (Phase 3)
- `/api/solve` endpoint (Phase 2)

---

## [0.1.0] — 2026-03-21 — Project Foundation

### What was set up

**Repository skeleton**
- `.gitignore` — covers Python (`__pycache__`, `.venv`, `*.pyc`), Node (`node_modules/`, `.next/`), Docker, editor files
- `.editorconfig` — enforces LF line endings, UTF-8, 4-space indent for Python, 2-space for TS/JS/JSON/YAML
- `README.md` — project overview, architecture table, quick-start commands for backend / frontend / Docker
- `docker-compose.yml` — single `backend` service with file-watch sync for local development (no rebuild on code changes)

**Backend — `backend/`**

- `pyproject.toml` — Python 3.12+, hatchling build, all runtime deps pinned:
  `fastapi`, `uvicorn[standard]`, `pydantic>=2.8`, `highspy>=1.7`, `structlog`, `sentry-sdk[fastapi]`
  Dev deps: `pytest`, `pytest-asyncio` (auto mode), `httpx`, `hypothesis`, `ruff`, `mypy` (strict)

- `solver/models/tile.py` — `Color(StrEnum)` with four values (`blue/red/black/yellow`);
  `Tile` as a **frozen hashable dataclass** (copy_id distinguishes the two physical copies of each tile);
  `__post_init__` validates number range 1–13 and copy_id ∈ {0,1}; `Tile.joker()` factory for unassigned jokers

- `solver/models/tileset.py` — `SetType(StrEnum)` (`run`/`group`); `TileSet` dataclass holding an ordered tile list

- `solver/models/board_state.py` — `BoardState` with computed properties `board_tiles` and `all_tiles`;
  `Solution` with `tiles_placed`/`tiles_remaining` properties; `MoveInstruction` for human-readable steps

- `solver/config/rules.py` — `RulesConfig` dataclass: `initial_meld_threshold` (default 30),
  `is_first_turn`, `allow_wrap_runs`, `joker_retrieval` — all rule variants from Blueprint §1.4

- **All solver modules as stubs** (correct signatures + `raise NotImplementedError`, ready to implement):
  - `solver/generator/set_enumerator.py` — `enumerate_valid_sets`, `enumerate_runs`, `enumerate_groups`
  - `solver/generator/move_generator.py` — `generate_moves`
  - `solver/engine/ilp_formulation.py` — `build_ilp_model`
  - `solver/engine/solver.py` — `solve` (main entry point for Phase 2)
  - `solver/engine/objective.py` — `compute_disruption_score` (secondary tiebreaker objective)
  - `solver/validator/rule_checker.py` — `is_valid_set`, `is_valid_board`
  - `solver/validator/solution_verifier.py` — `verify_solution` (post-solve defense-in-depth check)
  - `solver/output/solution_formatter.py` — `format_solution`
  - `solver/output/diff_calculator.py` — `compute_diff`
  - `solver/output/explanation.py` — `describe_move`

- `api/models.py` — Pydantic v2 `SolveRequest` / `SolveResponse` and all nested types;
  `TileInput` has a `@model_validator` that enforces (color+number) OR (joker=true)

- `api/main.py` — FastAPI app with `/health` endpoint returning `{"status":"ok","version":"0.1.0"}`;
  CORS middleware (wildcard, tighten in production); `/api/solve` left as commented stub for Phase 2

- `Dockerfile` — `python:3.12-slim`, non-root `app` user, `HEALTHCHECK` via urllib, listens on port 8000

- `tests/conftest.py` — shared fixtures: `red_4`, `blue_1`, `joker_0`, `simple_run`, `simple_group`,
  `empty_board`, `board_with_one_run`, `board_with_rack`
- `tests/test_models.py` — **28 tests**, all green:
  Color enum values/count, Tile construction/validation/immutability/hashability,
  joker factory, TileSet, BoardState properties, Solution counts, MoveInstruction

**Frontend — `frontend/`**

- `package.json` — Next.js 15.2.0, React 19, Zustand 5, Tailwind CSS 3.4, TypeScript 5
- `tsconfig.json` — Next.js App Router standard config, strict mode, path alias `@/*`
- `next.config.ts` — minimal config, `reactStrictMode: true`
- `tailwind.config.ts` — content paths set; custom `tile.*` colors (`blue/red/black/yellow`) pre-defined
- `postcss.config.js` — Tailwind + autoprefixer
- `.eslintrc.json` — `next/core-web-vitals` + `next/typescript`
- `src/app/globals.css` — Tailwind directives, CSS variables for dark mode, `env(safe-area-inset-*)` body padding
- `src/app/layout.tsx` — root layout with full PWA metadata, `viewport` with `viewportFit: "cover"` for notch support
- `src/app/page.tsx` — placeholder home page (replaced in Phase 3)
- `src/types/api.ts` — TypeScript mirror of backend Pydantic models (`TileInput`, `SolveRequest`, `SolveResponse`, etc.)
- `src/store/game.ts` — Zustand v5 store: `boardSets`, `rack`, `isFirstTurn`, `isLoading`, `solution`, `error`; all CRUD actions + `reset()`
- `public/manifest.json` — PWA manifest: `standalone` display, theme color `#1e40af`, icon placeholders

**CI/CD — `.github/workflows/`**

- `backend.yml` — triggers on `backend/**` changes; runs `ruff check`, `ruff format --check`, `mypy solver/ api/`, `pytest -v`
- `frontend.yml` — triggers on `frontend/**` changes; runs `tsc --noEmit`, `next lint`, `next build`
- Both workflows use dependency caching (pip / npm)

### Verification (all passed before commit)
```
pytest:         28 passed, 0 failed
ruff check:     0 errors
ruff format:    clean
mypy strict:    no issues in 24 source files
```

### What is NOT here yet (next phases)
- ILP solver logic (`solver/engine/`, `solver/generator/`, `solver/validator/`, `solver/output/`) — Phase 1
- `/api/solve` endpoint — Phase 2
- Frontend UI components (tile grid picker, board display, solution view) — Phase 3
- Sentry integration — Phase 4
- Playwright E2E tests — Phase 4

---

## Template for future entries

```
## [0.x.0] — YYYY-MM-DD — <Phase name>

### What was added / changed
- ...

### Verification
...

### What is NOT here yet
- ...
```
