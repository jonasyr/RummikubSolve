# Changelog

All notable changes to this project are documented here.
Format: **Phase → What was done → Why it matters**

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
