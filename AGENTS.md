# RummikubSolve — Project Memory

<!-- AUTO-MANAGED: project-description -->
## Overview

**RummikubSolve** is a full-stack Rummikub assistant: a FastAPI backend with a HiGHS-based ILP solver that computes optimal moves and generates structurally hard puzzles, paired with a Next.js frontend for play mode and solution display.

**Current phase:** Phase C of the Puzzle Generation Rebuild — implementing concrete template-based puzzle generators to replace the old random-sample-and-score pipeline.

**Active branch:** `38-generator-template-t1-joker-displacement-chain` — T1 Joker Displacement Chain template (issue #38). All 307 backend tests + 207 frontend tests pass as of 2026-06-07.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: build-commands -->
## Build & Development Commands

```bash
# ── Backend (from repo root or backend/) ──────────────────────────────────────
cd backend
pip install -e ".[dev]"                       # install runtime + dev deps

uvicorn api.main:app --reload --port 8000     # run API locally

# Tests — CRITICAL: use .venv/bin/pytest, NOT python -m pytest
# python -m pytest picks up the system Python and silently collects 0 tests
.venv/bin/pytest tests/                          # all tests
.venv/bin/pytest -m "not slow"                   # skip slow ILP/generation tests
.venv/bin/pytest tests/solver/templates/ -q      # template tests only

# Lint / type check
.venv/bin/ruff check solver/ api/
.venv/bin/mypy --strict solver/ api/

# ── Frontend (from repo root or frontend/) ────────────────────────────────────
cd frontend
npm install
npm run dev          # :3000
npm run build        # production build
npm run test         # Vitest unit tests
npm run e2e          # Playwright e2e (requires running backend)

# ── Full stack ────────────────────────────────────────────────────────────────
docker compose up --build    # nginx + frontend + backend together
```

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: architecture -->
## Architecture

```
RummikubSolve/
├── backend/
│   ├── api/
│   │   ├── main.py          # FastAPI app: /health, /api/solve, /api/puzzle, /api/telemetry
│   │   └── models.py        # Pydantic request/response models
│   ├── solver/
│   │   ├── engine/
│   │   │   ├── solver.py           # solve(), find_alternative_solution(), find_deep_chain_solution()
│   │   │   ├── ilp_formulation.py  # build_ilp_model(), extract_solution()
│   │   │   └── objective.py        # compute_chain_depth() — DAG longest-path metric
│   │   ├── generator/
│   │   │   ├── generator_core.py   # generate_puzzle() — retry loop over templates + gates
│   │   │   ├── puzzle_result.py    # PuzzleResult dataclass, PuzzleGenerationError
│   │   │   ├── gates/
│   │   │   │   ├── structural.py        # run_pre_ilp_gates() — fast structural checks
│   │   │   │   ├── ilp.py               # run_ilp_gates() — uniqueness + chain-depth enforcement
│   │   │   │   └── heuristic_solver.py  # HeuristicSolver — human-analog greedy solver
│   │   │   ├── templates/
│   │   │   │   ├── base.py              # Template ABC, TemplateInstance, @register_template
│   │   │   │   ├── __init__.py          # Registry: get_template(), list_templates()
│   │   │   │   └── t1_joker_displacement.py  # T1JokerDisplacementV1 — first concrete template
│   │   │   ├── puzzle_generator.py  # Legacy random-sample generator (still used for non-template)
│   │   │   └── puzzle_store.py      # SQLite pool for pre-generated puzzles
│   │   ├── models/
│   │   │   ├── tile.py        # Tile, Color (BLUE/RED/BLACK/YELLOW)
│   │   │   ├── tileset.py     # TileSet, SetType (RUN/GROUP)
│   │   │   └── board_state.py # BoardState, Solution
│   │   └── validator/         # Rule checker, solution verifier
│   └── tests/
│       ├── api/               # Puzzle endpoint, solve endpoint
│       ├── fixtures/
│       │   └── templates/     # Snapshot fixtures (e.g. t1_seed_1.json) for regression testing
│       └── solver/
│           ├── gates/         # ILP gate, structural, heuristic solver
│           ├── templates/     # T1 template tests (fast structural + slow ILP)
│           └── test_generator_core.py
├── frontend/
│   ├── src/
│   │   ├── app/               # Next.js App Router — page routes
│   │   ├── components/        # Reusable React components (PascalCase filenames)
│   │   │   └── play/          # Play-mode UI: RackSection, PlayPuzzleControls, etc.
│   │   ├── store/             # Zustand client state (camelCase actions)
│   │   ├── i18n/              # Translations (en/de)
│   │   └── __tests__/         # Vitest unit tests (colocated near feature areas)
│   └── e2e/                   # Playwright end-to-end specs
├── nginx/                     # Reverse proxy config
└── docker-compose.yml
```

**Data flow (template-based generation):**
1. `api/main.py` → `generate_puzzle()` if `template_id` in request
2. `generator_core.py`: pick template → `template.generate(rng)` → `run_pre_ilp_gates()` → `run_ilp_gates()` → retry up to N times
3. `run_ilp_gates()`: `solve()` → `find_deep_chain_solution()` (if shallow) → `find_alternative_solution()` (uniqueness)
4. Returns `PuzzleResult` → serialized to `PuzzleResponse`

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: conventions -->
## Code Conventions

### Backend (Python)
- **Python 3.12**, `mypy --strict`, `ruff` with `line-length = 100`
- `from __future__ import annotations` at top of every module
- Imports grouped: stdlib → third-party → internal
- Explicit return types on all public functions; `list[X]` not `List[X]`; `X | None` not `Optional[X]`
- `snake_case` for modules/functions/variables; `PascalCase` for classes; `_SCREAMING_SNAKE` for module-level constants
- Tests in `test_*.py` files; `@pytest.mark.slow` on any test touching real ILP/solver
- **Always use `.venv/bin/pytest`** — `python -m pytest` picks up system Python and silently collects 0 tests

### Frontend (TypeScript/React)
- 2-space indentation; PascalCase for components (`RackSection.tsx`); camelCase for hooks/store actions
- Vitest + Testing Library for unit tests; Playwright for e2e
- Test files: `*.test.ts(x)` for unit, `*.spec.ts` for e2e

### Shared
- **Commits:** Conventional Commits — `feat(scope): ...`, `fix(scope): ...`, `test(scope): ...`, `chore: ...`
- **Comments:** sparse; only when WHY is non-obvious (algorithm invariants, solver quirks)
- **SonarCloud** wired to `dev` branch; PRs target `dev` (not `main`)

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: patterns -->
## Detected Patterns

### Template System
Templates extend `Template` ABC, decorate with `@register_template`, implement `generate(rng: random.Random) -> TemplateInstance`. The `rng` is the sole randomness source. Templates are imported in `templates/__init__.py` to trigger registration.

`@register_template` idempotency: re-decorating the same class (e.g. module re-import during test collection) is silently ignored; registering a different class with a duplicate `template_id` raises `ValueError` immediately.

### ILP Gate Logic (as of branch #38)
`run_ilp_gates()` flow:
1. `solve()` → primary solution
2. If `solution.chain_depth < declared_chain_depth`: call `find_deep_chain_solution()` (iterative exclusion, up to 20 ILP calls)
3. `find_alternative_solution()` → returns `Solution | None`
4. Reject as `not_unique` only if alternative exists **AND** `alt.chain_depth >= declared_chain_depth`

Lower-difficulty alternatives (chain_depth below the tier threshold) do not count as uniqueness violations.

### Structural Gate Invariants (T1 template)
- S0 is a 4-colour GROUP (max capacity 4 tiles) → appending any 5th tile always invalid → blocks all trivial extensions for trigger
- Blocker runs contain `copy_id=1` of completer tiles → prevents duplicate extension
- Distractor sets use Z-colour at {1–3} and {11–13} — always non-adjacent to chain range n+1..n+3 (n ∈ {3..7})

### API Routing Pattern
`puzzle_endpoint()` checks `request.template_id`: non-null and non-"legacy" → routes to `generate_template_puzzle()` from `generator_core`; otherwise → legacy `generate_puzzle()` from `puzzle_generator`.

### Test Fixture Pattern
Slow ILP tests use `@pytest.mark.slow`. Fast structural tests (no ILP) check invariants over 20 seeds (`_SEEDS_FAST = range(1, 21)`); slow gate compliance tests use 10 seeds (`_SEEDS_ILP = range(1, 11)`). Module-scoped fixtures share expensive solver results within a test class. Fast tests mock `run_ilp_gates` via `_PATCH_ILP`. JSON snapshot fixtures in `tests/fixtures/templates/` (e.g. `t1_seed_1.json`) lock deterministic output for regression detection.

`isolated_registry` fixture (in `test_generator_core.py`) monkeypatches `TEMPLATE_REGISTRY` to an empty dict for the duration of each test — prevents cross-test registry pollution when templates auto-register on import. Patch constants (`_PATCH_PRE`, `_PATCH_ILP`, `_PATCH_POST`, `_PATCH_HS`, `_PATCH_DISRUPTION`, `_PATCH_ENUM`) all target the import site in `generator_core`, not the definition site.

`test_ilp_gate.py` tests `run_ilp_gates()` directly with real ILP (happy path, not_solvable, chain_too_shallow) and mocks (`find_alternative_solution`, timeout_fallback). Lower-depth alternatives (`alt.chain_depth < declared_chain_depth`) do NOT trigger `not_unique` — gate passes.

`test_puzzle_generator_v2.py` is the Phase 5 v2 pipeline test suite (§7.2–§7.6). The entire module is marked `pytestmark = pytest.mark.slow`. Module-scoped fixtures `_v2_easy/_v2_medium/_v2_hard/_v2_expert/_v2_nightmare` (seeds 1–5) are generated once per session to avoid ~1200s of redundant ILP calls. Exception: §7.6 performance tests (`test_easy_v2_generation_under_5s`, `test_board_builder_under_200ms`) are NOT marked slow — they assert fast wall-clock bounds. `test_difficulty_distribution` checks composite scores in [0,100] and easy < medium ordering but does NOT enforce strict adjacent-tier ordering (hard/expert/nightmare) due to HiGHS non-determinism in `solution_fragility`. Hypothesis tests (`test_generated_puzzle_always_solvable`, `test_tile_conservation`) use `max_examples=1` and `assume(False)` on `PuzzleGenerationError` to skip seeds where low `max_attempts` exhausts budget.

### Frontend State Pattern
Zustand store in `src/store/`. Play mode state (rack, board, solution) lives in a single store slice. Components dispatch camelCase actions; no direct mutation.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: git-insights -->
## Git Insights & Phase History

### Rebuild plan phases merged to dev:
- **#27 (PR #64)** — Skeleton files: `templates/`, `gates/`, `generator_core.py` stub
- **#28 (PR #65)** — `PuzzleStore` schema extended with `template_id`, `template_version`
- **#29 (PR #66)** — `PuzzleResponse`/`PuzzleRequest` gained `template_id`, `template_version` fields
- **#30 (PR #69)** — Structural gates module: 5 pure functions in `gates/structural.py`
- **#31 (PR #70)** — Phase 7 regression integration tests
- **#32 (PR #71)** — `HeuristicSolver` with 4-rule priority loop + greedy fallback
- **#33 (PR #72)** — Heuristic solver acceptance tests + hard puzzle fixture corpus
- **#34 (PR #73)** — `run_ilp_gates()` ILP gate wrapper
- **#35 (PR #74)** — Template base classes + registry
- **#36 (PR #75)** — `generator_core.py` retry loop + rejection logging
- **#37 (PR #76)** — End-to-end integration tests for `generator_core`

### In progress (branch #38, PR #81):
- T1 Joker Displacement Chain template (`t1_joker_displacement.py`) fully implemented
- ILP gate refactored: `check_uniqueness` → `find_alternative_solution` + `find_deep_chain_solution`
- `chain_too_shallow` now retried (not re-raised as `TemplateInvariantError`)
- T1 test UI added to `PlayPuzzleControls.tsx` (T1 seed input + "T1 test" button)
- Snapshot fixture `tests/fixtures/templates/t1_seed_1.json` added for regression testing
- Full template test suite in `tests/solver/templates/` (fast structural + slow ILP)
- Template authoring guide (`solver/generator/templates/README.md`): authoring contract, code review checklist, T1 chain construction proof, why-unique argument, rejection-rate table by gate
- `test_ilp_gate.py`: uses `find_alternative_solution` mock; covers lower-depth-alternative pass case and `solve_status:timeout_fallback` rejection
- `test_t1_joker_displacement.py`: 20-seed structural invariant tests + 10-seed slow gate compliance; checks `construction_notes` keys (`chain_color`, `base_n`, `joker_substitutes`)
- `test_generator_core.py`: `isolated_registry` fixture prevents cross-test registry pollution; 6 patch constants all target import site in `generator_core`
- `test_puzzle_generator_v2.py`: Phase 5 v2 pipeline suite — §7.2 integration (solvability + store round-trip for all 7 metric fields), §7.3 property (Hypothesis, max_examples=1), §7.4 simulation (difficulty distribution, non-trivial expert guard), §7.5 regression (v1 backward compatibility), §7.6 performance (easy < 5s, BoardBuilder < 200ms); module-scoped fixtures added after perf optimization to eliminate redundant puzzle generation

### Key design decisions:
- **T1 template pivot**: Original design had S0 as a RUN with joker, S1 as a GROUP. Final implementation uses S0 as a 4-colour GROUP (max capacity blocks trivial extensions cleanly) and S1 as a C-colour RUN.
- **`chain_too_shallow` retry**: Changed from raising `TemplateInvariantError` to retry — ILP may legitimately pick a shallow primary when a deep one exists; it's an ILP limitation, not a template bug.
- **Uniqueness check tiered**: Alternatives below declared `chain_depth` don't trigger `not_unique`.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: best-practices -->
## Best Practices

- **`check_uniqueness` no longer exists** — renamed to `find_alternative_solution` (returns `Solution | None`, not `bool`). Any code importing `check_uniqueness` from `solver.engine.solver` is broken.
- **Puzzle generation is offline** — `generate_template_puzzle()` can take seconds. `/api/puzzle` is not latency-sensitive; use it for pre-generation only.
- **Slow tests require real ILP** — never mock `solve()` in slow tests; mock the entire `run_ilp_gates()` instead (`_PATCH_ILP` pattern in test modules).
- **Snapshot fixtures** — `tests/fixtures/templates/t1_seed_1.json` locks template output for seed=1. Unexpected diffs signal regressions; intentional changes require fixture regeneration.
- **Template n range clamped to {3..7}** — n=8 excluded: n+2=10 is adjacent to D3 distractor start (11), enabling trivial extension. Verify range when adding new templates with similar structure.
- **Frontend tests**: use `npm run test` (Vitest) for unit tests and `npm run e2e` (Playwright) for browser flows — always run both before marking frontend tasks done.
- **Template README required** — `solver/generator/templates/README.md` documents the authoring contract (required docstring sections, code review checklist) and per-template invariants (chain construction, why-unique proof, rejection-rate table). Every new template must have a section there before merging.
- **ILP gate reason format** — rejection reasons from `run_ilp_gates()`: `not_solvable`, `not_unique`, `chain_too_shallow:<actual><declared>` (e.g. `chain_too_shallow:2<999`), `solve_status:<status>` (e.g. `solve_status:timeout_fallback`). Use `.startswith()` checks, not equality, for `chain_too_shallow`.

<!-- END AUTO-MANAGED -->

<!-- MANUAL -->
## Custom Notes

### Open issue pipeline — critical path
Issues #38–#63 are all open. Full dependency chain:

**Phase 4 — Templates:**
- **#38** T1 Joker Displacement ← ACTIVE (PR #81 open, targets dev)
- **#39** T1 test suite (fixture snapshot + rejection-rate test may still be needed)
- **#40** T2 False Extension Trap (`t2_false_extension.py`, tier=hard, chain_depth=2, success ≥50%)
- **#41** T2 test suite
- **#42** T3 Multi-Group Merge (`t3_multi_group_merge.py`, tier=nightmare, chain_depth=3, success ≥30%)
- **#43** T3 test suite
- **#44** T4 Run-to-Group Transformation (`t4_run_group_transform.py`, tier=expert, chain_depth=2, success ≥50%)
- **#45** T4 test suite
- **#46** T5 Compound Template (`t5_compound.py`, tier=nightmare, chain_depth=4, success ≥20%)
- **#47** T5 tests + cross-template regression (100 puzzles, all non-trivial)

**Phase 5 — Integration:**
- **#48** Route hard/expert/nightmare API traffic through `generator_core`
- **#49** Update `pregenerate.py` and `gen_calibration_batch.py` for `generator_core`
- **#50** Populate Phase-8 pool (≥30 puzzles per tier, `phase8_batch_v1.json`)

**Phase 6 — v2 Deletion:**
- **#51** Extract legacy sacrifice generator for easy/medium into `legacy_sacrifice.py`
- **#52** Remove custom-mode parameters from API + frontend
- **#53** Delete `tile_remover.py`, `difficulty_evaluator.py`, `difficulty_weights.json`
- **#54** Delete `puzzle_generator.py`
- **#55** Collapse duplicate `PuzzleResult` dataclass
- **#56** Remove 8-metric fields from API and frontend

**Phase 7 — Calibration:**
- **#57** Golden puzzle fixture library (10 trivial + 10 hand-crafted non-trivial)
- **#58** Performance benchmarks (nightmare ≤30 min for 50 puzzles)
- **#59** `calibrate.py` per-template reporting
- **#60** Play through Phase-8 calibration (human-in-the-loop)

**Phase 8 — Hardening:**
- **#61** Seed-determinism lint for templates
- **#62** Rejection-rate CI monitoring
- **#63** Operational runbook + final cleanup

### Known gotchas
- `python -m pytest` silently collects 0 tests — use `.venv/bin/pytest`
- `check_uniqueness` no longer exists in `solver.engine.solver` — use `find_alternative_solution`
- The `.tmp` file in `backend/` contains historical Claude Code session context; gitignored
- SonarCloud is wired to `dev` branch (not `main`); PRs target `dev`
- Issue #39 (T1 test suite) may need: fixture snapshot (`tests/fixtures/templates/t1_seed_1.json`, which now exists) and a `@pytest.mark.slow` rejection-rate test asserting ≥40% success over seeds 1–100

<!-- END MANUAL -->
