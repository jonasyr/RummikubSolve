# Changelog

All notable changes to this project are documented here.
Format: **Phase → What was done → Why it matters**

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
