# Changelog

All notable changes to this project are documented here.
Format: **Phase → What was done → Why it matters**

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
