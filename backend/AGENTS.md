# RummikubSolve — Backend Memory

<!-- AUTO-MANAGED: project-description -->
## Overview

**RummikubSolve** is a full-stack Rummikub assistant: a FastAPI backend with an HiGHS-based ILP solver that computes optimal moves and generates structurally hard puzzles, paired with a Next.js frontend for play mode and solution display. The backend is the primary engineering surface; it lives at `backend/` within the monorepo root.

**Current phase:** Phase C of the Puzzle Generation Rebuild — implementing concrete template-based puzzle generators to replace the old random-sample-and-score pipeline.

**Active branch:** `38-generator-template-t1-joker-displacement-chain` — T1 Joker Displacement Chain template (issue #38). All tests pass as of 2026-06-07.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: build-commands -->
## Build & Development Commands

```bash
# Install (from backend/)
pip install -e ".[dev]"

# Run API locally
uvicorn api.main:app --reload --port 8000

# Tests (use .venv/bin/pytest, NOT python -m pytest — the venv is not the default Python)
.venv/bin/pytest tests/                          # all tests
.venv/bin/pytest -m "not slow"                   # skip slow ILP/generation tests
.venv/bin/pytest tests/solver/templates/ -q      # template tests only

# Lint / type check
.venv/bin/ruff check solver/ api/
.venv/bin/mypy --strict solver/ api/

# Frontend (from frontend/)
npm run dev          # :3000
npm run test         # Vitest
npm run e2e          # Playwright (needs running backend)
```

**Critical note:** `python -m pytest` picks up the system Python and collects nothing. Always use `.venv/bin/pytest`.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: architecture -->
## Architecture

```
backend/
├── api/
│   ├── main.py          # FastAPI app: /health, /api/solve, /api/puzzle, /api/telemetry
│   └── models.py        # Pydantic request/response models
├── solver/
│   ├── engine/
│   │   ├── solver.py           # solve(), find_alternative_solution(), find_deep_chain_solution()
│   │   ├── ilp_formulation.py  # build_ilp_model(), extract_solution()
│   │   └── objective.py        # compute_chain_depth() — DAG longest-path metric
│   ├── generator/
│   │   ├── generator_core.py   # generate_puzzle() — retry loop over templates + gates
│   │   ├── puzzle_result.py    # PuzzleResult dataclass, PuzzleGenerationError
│   │   ├── gates/
│   │   │   ├── structural.py        # run_pre_ilp_gates() — fast structural checks
│   │   │   ├── ilp.py               # run_ilp_gates() — uniqueness + chain-depth enforcement
│   │   │   └── heuristic_solver.py  # HeuristicSolver — human-analog greedy solver
│   │   ├── templates/
│   │   │   ├── base.py              # Template ABC, TemplateInstance, @register_template
│   │   │   ├── __init__.py          # Registry: get_template(), list_templates()
│   │   │   └── t1_joker_displacement.py  # T1JokerDisplacementV1 — first concrete template
│   │   ├── puzzle_generator.py  # Legacy random-sample generator (still used for non-template)
│   │   └── puzzle_store.py      # SQLite pool for pre-generated puzzles
│   ├── models/
│   │   ├── tile.py        # Tile, Color (BLUE/RED/BLACK/YELLOW)
│   │   ├── tileset.py     # TileSet, SetType (RUN/GROUP)
│   │   └── board_state.py # BoardState, Solution
│   └── validator/         # Rule checker, solution verifier
└── tests/
    ├── api/               # Puzzle endpoint, solve endpoint
    └── solver/
        ├── gates/         # ILP gate, structural, heuristic solver
        ├── templates/     # T1 template tests (248 tests)
        └── test_generator_core.py
```

**Data flow (template-based generation):**
1. `api/main.py` → `generate_puzzle()` if `template_id` in request
2. `generator_core.py`: pick template from registry → `template.generate(rng)` → `run_pre_ilp_gates()` → `run_ilp_gates()` → retry up to N times
3. `run_ilp_gates()`: `solve()` → `find_deep_chain_solution()` (if shallow) → `find_alternative_solution()` (uniqueness check)
4. Returns `PuzzleResult` → serialized to `PuzzleResponse`

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: conventions -->
## Code Conventions

- **Python 3.12**, `mypy --strict`, `ruff` with `line-length = 100`
- **Imports:** `from __future__ import annotations` at top of every module; group stdlib → third-party → internal
- **Types:** explicit return types on all public functions; `list[X]` not `List[X]`; `X | None` not `Optional[X]`
- **Naming:** `snake_case` for modules/functions/variables; `PascalCase` for classes; `_SCREAMING_SNAKE` for module-level constants
- **Tests:** `test_*.py` files; `pytest`; `@pytest.mark.slow` on any test touching real ILP/solver; use `.venv/bin/pytest` not `python -m pytest`
- **Commits:** Conventional Commits format — `feat(scope): ...`, `fix(scope): ...`, `test(scope): ...`, `perf(scope): ...`
- **Comments:** sparse; only when the WHY is non-obvious (algorithm invariants, solver quirks)
- **No `TemplateInvariantError` for `chain_too_shallow`** — this was a design decision: `chain_too_shallow` is retried (not re-raised) because the ILP may pick a shallow primary when a deep solution exists

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: patterns -->
## Detected Patterns

### Template System
Templates extend `Template` ABC, decorate with `@register_template`, implement `generate(rng: random.Random) -> TemplateInstance`. The `rng` is the sole randomness source. Templates are imported in `templates/__init__.py` to trigger registration.

### ILP Gate Logic (as of branch #38)
`run_ilp_gates()` flow:
1. `solve()` → primary solution
2. If `solution.chain_depth < declared_chain_depth`: call `find_deep_chain_solution()` (iterative exclusion, up to 20 ILP calls)
3. `find_alternative_solution()` → returns `Solution | None`
4. Reject as `not_unique` only if alternative exists **AND** `alt.chain_depth >= declared_chain_depth`

This means lower-difficulty alternatives (chain_depth below the tier threshold) do not count as uniqueness violations.

### Structural Gate Invariants (T1 template)
- S0 is a 4-colour GROUP (max capacity 4 tiles) → appending any 5th tile always invalid → blocks all trivial extensions for trigger
- Blocker runs contain `copy_id=1` of completer tiles → prevents duplicate extension
- Distractor sets use Z-colour at {1–3} and {11–13} — always non-adjacent to chain range n+1..n+3 (n ∈ {3..7})

### API Routing Pattern
`puzzle_endpoint()` checks `request.template_id`: if non-null and non-"legacy" → routes to `generate_template_puzzle()` from `generator_core`; otherwise → legacy `generate_puzzle()` from `puzzle_generator`.

### Test Fixture Pattern
Slow ILP tests use `@pytest.mark.slow`. Fast structural tests (no ILP) check invariants over 20 seeds. Module-scoped fixtures share expensive solver results within a test class.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: git-insights -->
## Git Insights & Phase History

### Rebuild Plan phases completed (merged to dev):
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

### In progress (branch #38, not yet merged):
- T1 Joker Displacement Chain template (`t1_joker_displacement.py`)
- ILP gate refactored: `check_uniqueness` → `find_alternative_solution` + `find_deep_chain_solution`
- `chain_too_shallow` now retried (not re-raised as `TemplateInvariantError`)
- T1 test UI added to `PlayPuzzleControls.tsx` (T1 seed input + "T1 test" button)
- 248 template tests + 59 gate/API/generator tests all pass

### Key design decisions:
- **Template construction pivoted from original plan in `.tmp`**: Original design had S0 as a RUN with joker, S1 as a GROUP. Final implementation uses S0 as a 4-colour GROUP (max capacity blocks all trivial extensions cleanly) and S1 as a C-colour RUN. This made the uniqueness argument cleaner.
- **`chain_too_shallow` retry**: Original gate raised `TemplateInvariantError` immediately (treating shallow chain as template bug). Changed to retry because ILP may legitimately pick a shallow primary solution when a deep one exists — it's an ILP limitation, not a template design bug.
- **Uniqueness check tiered**: An alternative solution that doesn't meet the declared `chain_depth` tier is not a competing expert-level path, so it doesn't trigger `not_unique`.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: best-practices -->
## Best Practices

- **`check_uniqueness` is now `find_alternative_solution`** — returns `Solution | None`, not `bool`. Any code importing `check_uniqueness` from `solver.engine.solver` is broken.
- **Do not import `check_uniqueness`** — it no longer exists. Use `find_alternative_solution` or `find_deep_chain_solution`.
- **Puzzle generation is offline** — `generate_template_puzzle()` can take seconds. The `/api/puzzle` endpoint is not latency-sensitive; use it for pre-generation only.
- **Slow tests require real ILP** — never mock `solve()` in slow tests; mock the entire `run_ilp_gates()` function instead (`_PATCH_ILP`).
- **Template n range clamped to {3..7}** — n=8 is excluded: n+2=10 is adjacent to D3 distractor start (11), enabling a trivial extension. If adding new templates with similar structure, verify the range.
- **Frontend test file exists**: `frontend/src/__tests__/components/play/PlayPuzzleControls.test.tsx` is untracked — needs to be staged before PR.

<!-- END AUTO-MANAGED -->

<!-- MANUAL -->
## Custom Notes

### What's next (issue #38 completion checklist)
- [ ] Confirm frontend test (`PlayPuzzleControls.test.tsx`) passes: `cd frontend && npm run test`
- [ ] Check if issue #39 items are satisfied (fixture snapshot `t1_seed_1.json`, rejection-rate test ≥40%)
- [ ] Stage all files and open PR for branch `38-generator-template-t1-joker-displacement-chain`
- [ ] PR closes issue #38, base branch `dev`

### Open issue pipeline — critical path
Issues #38–#63 are all open. Full dependency chain:

**Phase 4 — Templates:**
- **#38** T1 Joker Displacement ← ACTIVE
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
- **#48** Route hard/expert/nightmare API traffic through `generator_core` (current branch partially does this for explicit template_id)
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

### Known issues / gotchas
- `python -m pytest` silently collects 0 tests — use `.venv/bin/pytest`
- `check_uniqueness` no longer exists in `solver.engine.solver` — it was renamed to `find_alternative_solution` (returns `Solution | None`, not `bool`) on branch #38
- The `.tmp` file in `backend/` contains historical Claude Code session context; gitignored
- `backend/.serena/` is untracked — Serena project state; can be gitignored
- SonarCloud is wired to `dev` branch (not `main`); PRs target `dev`
- Issue #39 (T1 test suite) may need: fixture snapshot JSON (`tests/fixtures/templates/t1_seed_1.json`) and `@pytest.mark.slow` rejection-rate test asserting ≥40% success over seeds 1–100

<!-- END MANUAL -->
