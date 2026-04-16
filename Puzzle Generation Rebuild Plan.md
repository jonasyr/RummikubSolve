# Puzzle Generation Rebuild Plan

**Status:** Proposal for implementation
**Target date:** 2026-04-16
**Scope:** Replace the entire puzzle generation pipeline (v1 sacrifice + v2 tile-removal) with a deterministic, template-based constructive generator.
**Owner:** To be assigned.
**Prerequisite reading:** `PUZZLE_DIFFICULTY_PROBLEM.md`, `CHANGELOG.md` (entries from 2026-03-29 onward).

-----

## 1. Executive Summary

### 1.1 The problem in one paragraph

Every puzzle the current system generates — across all five difficulty tiers — is trivially easy. The Phase 7 calibration batch (`phase7_batch_v1`, 25 puzzles) showed nightmare-tier puzzles solved in an average of 28 seconds with **zero undos across 25 puzzles**. Composite scores of 80–90/100 corresponded to trivial human solve experiences. This is not a calibration bug. It is a structural consequence of the chosen generation approach.

### 1.2 Why the current system fails

Two independent structural failures compound:

**(F1) The v2 `TileRemover` pipeline leaks the solution.** Sequential single-tile removal from a valid board leaves 1–2 tile stubs (orphaned partial sets) on the board. These stubs act as visual “fill-in-the-blank” hints that tell a human player exactly where rack tiles belong. The intended `_any_trivial_extension_v2` gate is forced to ignore these stubs (it only checks complete sets of ≥3 tiles) because otherwise it would reject 100% of generated puzzles. The filter is blind precisely where it must see.

**(F2) The eight-metric difficulty evaluator measures ILP complexity, not human search difficulty.** Branching factor, deductive depth, red herring density, working memory load, tile ambiguity, solution fragility, disruption score, and chain depth are all properties of the integer linear program. Humans do not enumerate candidate sets — they pattern-match and prune visually. A puzzle with `branching_factor = 40` can be solved in seconds if a single placement is visually obvious. None of these eight metrics detects visual obviousness.

A third-order failure sits on top: the composite score’s calibration (`difficulty_weights.json`, `_MIN_DISRUPTION_V2`, `_MIN_FRAGILITY_V2`, `TIER_THRESHOLDS`) was derived from developer intuition and 735 polluted telemetry events from Phase 6, not from real human play data. The only metric with a plausible causal link to human difficulty (`chain_depth`) carries weight 0.05 out of 1.00.

### 1.3 Why a random-sample-and-score approach cannot fix this

The set of human-hard Rummikub puzzles is a vanishingly thin subset of the random-puzzle space. Random sampling cannot reliably hit a thin target subset no matter how good the post-hoc scorer is. Sudoku hard-puzzle generators abandoned this approach over 15 years ago in favor of constructive techniques (Inkala’s 16-clue puzzles, the X-Wing / Swordfish catalog). Rummikub has no established template catalog; this rebuild creates one.

### 1.4 Recommended architecture

**Template-based deterministic construction with ILP uniqueness enforcement and heuristic-solver post-filtering.** Each template encodes a structurally hard puzzle pattern (joker displacement chain, false-extension trap, multi-group merge, run-to-group transformation). Every generated puzzle is uniqueness-verified and survives a human-analog heuristic solver. Generation runs offline; live requests draw from a pregenerated pool.

### 1.5 What this document delivers

A repository-specific, phase-by-phase implementation plan. An engineer or autonomous coding agent following this plan end-to-end should produce a working template-based puzzle generator, retire the obsolete v2 pipeline, and demonstrate measurable improvement over Phase 7 baseline within 6 weeks of work.

-----

## 2. Goals and Non-Goals

### 2.1 Goals

**G1.** Generate puzzles that require genuine human search effort. Nightmare-tier puzzles should take an average of 10+ minutes for an experienced player, with measurable undo counts and return-to-rack events.

**G2.** Each generated puzzle must have a verified unique optimal solution. `check_uniqueness` passes as a hard gate, not an informational metric.

**G3.** Generation is deterministic given a seed and template choice. The same seed on the same template always produces the same puzzle.

**G4.** Generation success rate per attempt is ≥20% for hard/expert/nightmare (current v2: <1% for true hardness; template-based construction targets much higher by design).

**G5.** Difficulty is enforced by structural invariants at construction time, not measured after the fact.

**G6.** The system is inspectable and debuggable. When a template produces puzzles that turn out too easy in telemetry, the offending template can be identified and fixed or retired locally without destabilizing the pipeline.

### 2.2 Explicit non-goals

**NG1.** No more random-sample-and-score. The entire `BoardBuilder` → `TileRemover` → `DifficultyEvaluator` flow is abandoned as a generation strategy (though individual components may be reused as library functions).

**NG2.** The eight-metric composite score is not repaired. It is decommissioned as a generation gate. Individual metrics may survive as diagnostic tools.

**NG3.** No attempt to achieve a single universal “hardness number.” Different templates produce different kinds of hard, and that is acceptable and intended.

**NG4.** Live API-time generation of hard/expert/nightmare puzzles is no longer a target. These tiers are pool-only. Easy and medium may remain live-generated.

**NG5.** The v1 sacrifice generator is not resurrected as the primary path. It was better than v2 for hardness but still probabilistic. It may survive as a fallback for easy/medium tiers only.

-----

## 3. Current State Analysis

This section maps the existing code to enable decisive surgical changes. File paths are relative to the repository root.

### 3.1 Generation-related modules

|File                                               |Lines (approx)|Current role                                                                                                                                     |Disposition                                                                                                                                                                                                                                                                                                                            |
|---------------------------------------------------|--------------|-------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|`backend/solver/generator/puzzle_generator.py`     |~750          |Top-level generator, contains v1 (`_attempt_generate_with_reason`) and v2 (`_attempt_generate_v2`) paths, difficulty constants, custom-mode logic|**Rewrite**. Keep only `_assign_copy_ids` (→ relocated), `_pick_compatible_sets` (→ relocated), `PuzzleResult` dataclass (→ simplified). Remove everything else.                                                                                                                                                                       |
|`backend/solver/generator/board_builder.py`        |~200          |Constructs valid high-overlap boards via overlap-graph-biased selection                                                                          |**Retain as library, demote from pipeline**. Useful for tests and as a component inside templates. Not called by the new main generator.                                                                                                                                                                                               |
|`backend/solver/generator/tile_remover.py`         |~350          |Strategic tile removal (the core v2 generator)                                                                                                   |**Delete**. This is the primary source of F1. Its only caller is `_attempt_generate_v2`. Once that caller is gone, this module is dead code.                                                                                                                                                                                           |
|`backend/solver/generator/difficulty_evaluator.py` |~350          |Eight-metric evaluator, composite score, tier classification                                                                                     |**Delete the generation-gate role; retain selected metrics as diagnostic tools**. Specifically: `compute_chain_depth` (from `objective.py`), `compute_disruption_score` survive. The `DifficultyEvaluator.evaluate` facade, `DifficultyScore` dataclass, `TIER_THRESHOLDS`, `classify_tier`, and composite-score machinery are retired.|
|`backend/solver/generator/difficulty_weights.json` |-             |Weights and normalization ceilings for composite score                                                                                           |**Delete**. No longer used.                                                                                                                                                                                                                                                                                                            |
|`backend/solver/generator/set_enumerator.py`       |~250          |Enumerates valid run/group templates including joker variants                                                                                    |**Retain unchanged**. Fundamental building block used everywhere.                                                                                                                                                                                                                                                                      |
|`backend/solver/generator/tile_pool.py`            |~50           |`make_tile_pool`, `assign_copy_ids`                                                                                                              |**Retain unchanged**.                                                                                                                                                                                                                                                                                                                  |
|`backend/solver/generator/move_generator.py`       |~120          |Human-readable move instructions for the /solve endpoint                                                                                         |**Retain unchanged**. Unrelated to puzzle generation.                                                                                                                                                                                                                                                                                  |
|`backend/solver/generator/set_changes.py`          |~180          |Per-set change manifest for /solve responses                                                                                                     |**Retain unchanged**.                                                                                                                                                                                                                                                                                                                  |
|`backend/solver/generator/puzzle_store.py`         |~150          |SQLite pool for pregenerated puzzles                                                                                                             |**Retain with schema additions**. New columns for template identity (see §4.4).                                                                                                                                                                                                                                                        |
|`backend/solver/generator/telemetry_store.py`      |~150          |Telemetry event persistence                                                                                                                      |**Retain unchanged**.                                                                                                                                                                                                                                                                                                                  |
|`backend/solver/generator/pregenerate.py`          |~350          |Parallel CLI for batch pregeneration                                                                                                             |**Refactor**. Point it at the new generator entry point. Retain multiprocessing infrastructure and sync logic.                                                                                                                                                                                                                         |
|`backend/solver/generator/gen_calibration_batch.py`|~150          |Calibration batch generator CLI                                                                                                                  |**Refactor**. Same as above.                                                                                                                                                                                                                                                                                                           |
|`backend/solver/generator/calibrate.py`            |~300          |Calibration analysis tool (`--batch`, `--stats`, `--fit-weights`)                                                                                |**Retain**. The `--fit-weights` mode is explicitly not used for the new system’s tier classification but retained for diagnostic analysis of human difficulty predictors.                                                                                                                                                              |

### 3.2 Solver and validation modules (unchanged)

|File                                           |Role                                             |Disposition          |
|-----------------------------------------------|-------------------------------------------------|---------------------|
|`backend/solver/engine/solver.py`              |Main solve() entry, `check_uniqueness()`         |**Retain unchanged**.|
|`backend/solver/engine/ilp_formulation.py`     |HiGHS ILP model construction                     |**Retain unchanged**.|
|`backend/solver/engine/objective.py`           |`compute_disruption_score`, `compute_chain_depth`|**Retain unchanged**.|
|`backend/solver/validator/rule_checker.py`     |`is_valid_set`, `is_valid_board`                 |**Retain unchanged**.|
|`backend/solver/validator/solution_verifier.py`|Post-solve verification                          |**Retain unchanged**.|
|`backend/solver/models/`                       |Tile, TileSet, BoardState, Solution              |**Retain unchanged**.|
|`backend/solver/config/rules.py`               |RulesConfig                                      |**Retain unchanged**.|

### 3.3 API layer

|File                   |Role                                    |Disposition                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
|-----------------------|----------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|`backend/api/main.py`  |FastAPI endpoints, `/api/puzzle` handler|**Refactor puzzle endpoint**. Calls new generator entry point. The pool-drawing logic stays. Live generation path simplifies.                                                                                                                                                                                                                                                                                                                                                                            |
|`backend/api/models.py`|Pydantic request/response models        |**Refactor `PuzzleRequest`**: drop custom-mode fields (`sets_to_remove`, `min_board_sets`, `max_board_sets`, `min_chain_depth`, `min_disruption`). Add optional `template_id` field for diagnostic/debug use. **Refactor `PuzzleResponse`**: drop `composite_score`, `branching_factor`, `deductive_depth`, `red_herring_density`, `working_memory_load`, `tile_ambiguity`, `solution_fragility`. Add `template_id`, `template_name`. Keep `chain_depth`, `is_unique`, `disruption_score` as diagnostics.|

### 3.4 Frontend (minimal impact)

|File                                        |Role                   |Disposition                                                                                                                        |
|--------------------------------------------|-----------------------|-----------------------------------------------------------------------------------------------------------------------------------|
|`frontend/src/types/api.ts`                 |TS mirror of API models|**Mirror the backend model changes.** Remove composite score field. Custom mode disappears from UI.                                |
|`frontend/src/components/PuzzleControls.tsx`|Difficulty selector    |**Remove custom mode UI**. Remove stats badge references to `branching_factor` etc. Keep `chain_depth` badge as diagnostic display.|
|`frontend/src/store/game.ts`                |Play-mode state        |**Update `lastPuzzleMeta` type**.                                                                                                  |
|`frontend/src/store/play.ts`                |Play-mode state        |**Update telemetry fields**: remove composite-score-related context sending.                                                       |

### 3.5 Test infrastructure

|File / directory                                   |Role                      |Disposition                                                                                     |
|---------------------------------------------------|--------------------------|------------------------------------------------------------------------------------------------|
|`backend/tests/solver/test_puzzle_generator.py`    |Current generator tests   |**Rewrite**. New tests for template-based generator; old v1/v2 tests deleted.                   |
|`backend/tests/solver/test_board_builder.py`       |BoardBuilder tests        |**Retain**. BoardBuilder survives as a library.                                                 |
|`backend/tests/solver/test_tile_remover.py`        |TileRemover tests         |**Delete**. TileRemover is gone.                                                                |
|`backend/tests/solver/test_difficulty_evaluator.py`|DifficultyEvaluator tests |**Delete** (partially — keep tests for individual metric functions that survive as diagnostics).|
|`backend/tests/api/test_puzzle_endpoint.py`        |/api/puzzle endpoint tests|**Rewrite**. New request/response schema.                                                       |

### 3.6 Design problems summary (operational)

|Problem                                                     |Location                                                                           |Severity|Resolution                                      |
|------------------------------------------------------------|-----------------------------------------------------------------------------------|--------|------------------------------------------------|
|Sequential tile removal leaks solution via orphan stubs     |`tile_remover.py` entire module                                                    |Critical|Delete module                                   |
|Trivial-extension gate forced to ignore stubs               |`puzzle_generator.py:_any_trivial_extension_v2`                                    |Critical|Delete function; new strict gate in templates   |
|ILP-complexity metrics mistaken for human difficulty        |`difficulty_evaluator.py` lines computing branching/deductive/ambiguity            |High    |Remove from generation gates                    |
|Composite score calibration derived from developer intuition|`difficulty_weights.json`, `_MIN_DISRUPTION_V2`, `_MIN_FRAGILITY_V2`               |High    |Delete; replace with structural gates           |
|Uniqueness treated as informational, not enforced           |`puzzle_generator.py:_attempt_generate_with_reason` line calling `check_uniqueness`|High    |Make it a hard gate in template path            |
|Chain-depth under-weighted (0.05)                           |`difficulty_weights.json`                                                          |Medium  |Replace weighting with hard minimum per template|
|Tier boundaries use overlapping bands                       |`difficulty_evaluator.py:TIER_THRESHOLDS`                                          |Medium  |Tier becomes template property, not score range |
|`PuzzleRequest` custom-mode parameters proliferate          |`api/models.py:PuzzleRequest`                                                      |Low     |Remove; custom mode retired                     |

-----

## 4. Target Architecture

### 4.1 Architectural overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                      OFFLINE PREGENERATION                           │
│                                                                      │
│   ┌──────────────┐      ┌──────────────┐      ┌──────────────┐       │
│   │ Template     │─────>│ Template     │─────>│ Structural   │       │
│   │ Catalog      │      │ Instantiator │      │ Gates        │       │
│   └──────────────┘      └──────────────┘      └──────┬───────┘       │
│                                                      │               │
│                                                      v               │
│   ┌──────────────┐      ┌──────────────┐      ┌──────────────┐       │
│   │ PuzzleStore  │<─────│ Heuristic    │<─────│ ILP          │       │
│   │ (SQLite)     │      │ Solver Gate  │      │ Verification │       │
│   └──────────────┘      └──────────────┘      └──────────────┘       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         ONLINE API                                   │
│                                                                      │
│   /api/puzzle (hard/expert/nightmare) ──> PuzzleStore.draw()         │
│   /api/puzzle (easy/medium)           ──> Live v1 fallback           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                       TELEMETRY LOOP                                 │
│                                                                      │
│   Real player solve times ──> calibrate.py ──> Template rankings     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Component responsibilities

#### 4.2.1 Template Catalog (`templates/__init__.py` and per-template modules)

A registry of puzzle templates. Each template is a Python module defining:

- A unique `template_id` string (e.g. `"T1_joker_displacement_v1"`)
- A `tier` declaration (`"hard"`, `"expert"`, `"nightmare"`)
- A `generate(rng, difficulty_params)` function returning a `TemplateInstance`
- Structural invariants it guarantees (documented in docstring and enforced by assertions)

Templates are the **single source of truth for what “hard” means** in this system. The catalog is a Python dict of `template_id → module`. New templates register themselves via a decorator.

#### 4.2.2 Template Instantiator (`generator_core.py`)

The main generation entry point. Given a tier and optional template_id:

1. Select a template from the catalog matching the tier.
1. Call the template’s `generate(rng, params)` to get a `TemplateInstance`.
1. Materialize the instance into a `BoardState` plus rack.
1. Run gates (§4.2.3, 4.2.4, 4.2.5). On any gate failure, log with reason and retry with a new seed or template.
1. Return a `PuzzleResult` with template identity recorded.

Replaces `generate_puzzle()` in `puzzle_generator.py`.

#### 4.2.3 Structural Gates (`gates/structural.py`)

Fast, pre-ILP checks that reject obviously broken templates before expensive solver runs:

- **No-trivial-extension gate (strict version):** For every rack tile, no single board set (including partial stubs of any size) can be trivially extended to a valid set by appending that rack tile.
- **No-single-home gate:** For every rack tile, there are either zero valid placements in the candidate set list or at least two. No rack tile has a unique trivial home.
- **Joker-structural gate (for joker-containing templates):** If a joker is on the board, the solution must move it. If a joker is in the rack, it must fill a non-obvious slot.
- **Tile-conservation check:** Board tiles + rack tiles correspond to a valid physical pool.

Each gate returns `(ok: bool, reason: str)`. The reason is logged to telemetry for debugging.

#### 4.2.4 ILP Verification Gate (`gates/ilp.py`)

Wraps existing `solve()` and `check_uniqueness()`:

- **Solvability:** `solve(state)` places all rack tiles (no partial placement).
- **Uniqueness (hard gate):** `check_uniqueness(state, solution)` returns `True`.
- **Chain-depth minimum:** `solution.chain_depth >= template_declared_minimum`.

Reuses existing solver infrastructure without modification.

#### 4.2.5 Heuristic Solver Gate (`gates/heuristic_solver.py`)

A deliberately human-analog solver that models what a competent but not-omniscient player attempts. Its only job is to **fail** on puzzles that are meant to be hard. Any puzzle the heuristic solver successfully completes in its bounded search is rejected as trivial.

The heuristic solver uses, in priority order:

1. Place any rack tile that has exactly one trivial extension slot on the board.
1. Place any rack tile that completes an existing orphan 2-tile stub.
1. Attempt single-set breaks (take one tile out of a board set, check if the released tile enables a rack-placement, verify the broken set is still reformable).
1. Stop at depth 2 breaks. Do not attempt multi-set merges. Do not attempt joker displacement.

If after these steps the rack is empty and the board is valid, the puzzle is trivial for a human → rejected. The heuristic solver is explicitly weaker than the ILP by design.

This gate is the operational definition of “not-trivial.”

#### 4.2.6 PuzzleStore (unchanged with schema additions)

Existing `puzzle_store.py` with these added columns:

- `template_id TEXT NOT NULL DEFAULT 'legacy'`
- `template_version TEXT NOT NULL DEFAULT '0'`
- `heuristic_solver_rejected BOOLEAN NOT NULL DEFAULT 0` (for diagnostic queries)

Pool queries can filter by template for A/B testing different template versions.

#### 4.2.7 Live fallback path (`legacy_sacrifice.py`, optional)

Easy and medium puzzles remain live-generated via a slimmed-down v1 sacrifice generator. This is a pragmatic concession: easy puzzles are fine being trivial — users want practice, not challenge. This path:

- Uses the existing `_pick_compatible_sets` (relocated).
- Uses a `_extract_by_sacrifice` variant (relocated and simplified).
- Runs the strict trivial-extension gate (§4.2.3) only for medium tier.
- Does not run ILP uniqueness.
- Can be disabled by config; all tiers would then be pool-only.

### 4.3 Data models

#### 4.3.1 `TemplateInstance` (new, in `templates/base.py`)

```python
@dataclass(frozen=True)
class TemplateInstance:
    template_id: str
    template_version: str
    tier: Literal["hard", "expert", "nightmare"]
    board_sets: list[TileSet]
    rack: list[Tile]
    # Diagnostic metadata captured at construction time:
    declared_chain_depth: int      # what the template guarantees
    declared_disruption_min: int    # what the template guarantees
    construction_notes: dict        # free-form per-template diagnostics
```

#### 4.3.2 Simplified `PuzzleResult` (replace existing)

```python
@dataclass
class PuzzleResult:
    board_sets: list[TileSet]
    rack: list[Tile]
    difficulty: Difficulty
    seed: int | None
    template_id: str
    template_version: str
    # Verified (not declared) metrics:
    chain_depth: int
    disruption_score: int
    is_unique: bool
    joker_count: int
```

Note: no `composite_score`, no `branching_factor`, no `deductive_depth`, etc. All eight-metric fields gone.

#### 4.3.3 Simplified `PuzzleResponse` (Pydantic)

Mirrors `PuzzleResult`. Specifically drops the v2 metric fields.

### 4.4 PuzzleStore schema migration

Add columns via existing `_MIGRATION_COLUMNS` idiom in `puzzle_store.py`. Backwards-compatible with existing pools. Old rows default `template_id='legacy'`.

### 4.5 Generation control flow

```
generate_puzzle(tier, seed, template_id=None)
    rng = Random(seed)
    attempts = 0
    while attempts < MAX_ATTEMPTS:
        template = choose_template(tier, rng, template_id)
        instance = template.generate(rng)
        state = BoardState(board_sets=instance.board_sets, rack=instance.rack)

        # Structural gates (cheap)
        ok, reason = structural_gates.check(state)
        if not ok:
            log_rejection(template.id, reason); attempts += 1; continue

        # ILP gates (expensive)
        solution = solve(state)
        if solution.tiles_placed < len(state.rack):
            log_rejection(template.id, "not_solvable"); attempts += 1; continue

        if not check_uniqueness(state, solution, timeout=10.0):
            log_rejection(template.id, "not_unique"); attempts += 1; continue

        if solution.chain_depth < instance.declared_chain_depth:
            # Template invariant violation — this is a template bug, not a seed bug
            raise TemplateInvariantError(template.id, "chain_depth below declared minimum")

        # Heuristic solver gate (cheap)
        if heuristic_solver.solves(state):
            log_rejection(template.id, "heuristic_solved"); attempts += 1; continue

        return PuzzleResult(...)

    raise PuzzleGenerationError(f"Exhausted attempts for tier={tier}")
```

### 4.6 Target directory structure (after migration)

```
backend/solver/generator/
├── __init__.py
├── generator_core.py              # NEW: generate_puzzle() entry, retry loop
├── templates/
│   ├── __init__.py                # NEW: template registry + decorator
│   ├── base.py                    # NEW: TemplateInstance, Template ABC
│   ├── t1_joker_displacement.py   # NEW: Joker displacement chain
│   ├── t2_false_extension.py      # NEW: False-extension trap
│   ├── t3_multi_group_merge.py    # NEW: Multi-group merge
│   ├── t4_run_group_transform.py  # NEW: Run-to-group transformation
│   └── t5_compound.py             # NEW: Composition of T1-T4 (nightmare tier)
├── gates/
│   ├── __init__.py
│   ├── structural.py              # NEW: Fast pre-ILP filters
│   ├── ilp.py                     # NEW: Wraps solve() + check_uniqueness()
│   └── heuristic_solver.py        # NEW: Human-analog solver
├── legacy_sacrifice.py            # NEW: Slim v1 for easy/medium live generation
├── board_builder.py               # RETAINED (library, not pipeline)
├── set_enumerator.py              # RETAINED unchanged
├── tile_pool.py                   # RETAINED unchanged
├── move_generator.py              # RETAINED unchanged
├── set_changes.py                 # RETAINED unchanged
├── puzzle_store.py                # RETAINED (schema additions)
├── telemetry_store.py             # RETAINED unchanged
├── pregenerate.py                 # REFACTORED (points to new entry)
├── gen_calibration_batch.py       # REFACTORED (points to new entry)
└── calibrate.py                   # RETAINED

# DELETED:
# - puzzle_generator.py  (logic absorbed into generator_core.py and legacy_sacrifice.py)
# - tile_remover.py
# - difficulty_evaluator.py
# - difficulty_weights.json
```

-----

## 5. Concrete Technical Decisions

### 5.1 Chosen approach: Template-based construction with ILP + heuristic gates

**Decision.** Implement template-based deterministic construction as the sole generation path for hard/expert/nightmare. Keep a slim sacrifice generator only for live easy/medium fallback.

**Why this over alternatives.**

|Alternative                                  |Rejected because                                                                                                                                                                           |
|---------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|Keep v2, recalibrate weights                 |Failure F1 is structural (solution leaks via orphan stubs). No weight changes repair it. Phase 7 proved this empirically.                                                                  |
|Resurrect v1 as primary                      |Still probabilistic. Uniqueness rejection rate for nightmare was measured in single-digit percentages, unreliable.                                                                         |
|Generate-and-test with new metrics (DED, SOS)|Still samples randomly from a thin target subset. Target hit rate remains bounded below what constructive methods deliver. Valuable as template quality metric, not as generation strategy.|
|Constraint-programming with z3 / MiniZinc    |“Human-hard” is not finitely axiomatizable. The CSP encoding reduces to template constraints anyway. Higher tooling cost for the same result.                                              |
|Rewrite from zero                            |Most of the existing infrastructure (ILP solver, rule checker, pool, telemetry) is sound. Full rewrite discards working code. Surgical replacement of the generation layer only.           |

### 5.2 How uniqueness is enforced

Uniqueness is a **hard gate** in `gates/ilp.py`. The existing `check_uniqueness()` function in `solver.py` is used unchanged. Templates must be designed so uniqueness is architecturally likely (e.g. T2 inserts a “blocker rack tile” that has no other valid placement). When a template produces non-unique puzzles with high frequency, the template itself is fixed; this is detected by template-level telemetry and handled in the template’s own module, not the pipeline.

### 5.3 How difficulty is modeled

Difficulty is **structural**, not scalar. A puzzle is nightmare-tier because it instantiates a nightmare-designated template, which by construction contains at least one of:

- A joker displacement chain of length ≥ 3 (T1 variant).
- A false-extension trap that defeats the greedy-extend heuristic (T2).
- A multi-group merge requiring simultaneous rearrangement of ≥ 3 board positions (T3).
- A run-to-group transformation (T4).
- A composition of two of the above (T5).

Each template enforces its tier’s structural invariant at construction time. The `chain_depth` metric survives as a **verification** that the construction succeeded — it is checked after the ILP solve and raises `TemplateInvariantError` if the template’s declared minimum is not met (indicating a template bug, not a random failure).

### 5.4 How trivial puzzles are prevented from recurring

Three independent layers:

- **Structural gates** (§4.2.3) reject any puzzle where a rack tile has a unique trivial home or where any board set can be trivially extended.
- **Heuristic solver gate** (§4.2.5) is a positive test for non-triviality. The heuristic solver explicitly models the human greedy approach. If it finds the solution, the puzzle is by definition trivial.
- **Template-level design review**: every new template has a written documentation section “Why this is not trivial” that the code reviewer checks against.

### 5.5 What old components may be reused

**Reused unchanged.**

- `solver/engine/` entire directory.
- `solver/models/` entire directory.
- `solver/validator/` entire directory.
- `solver/config/rules.py`.
- `solver/generator/set_enumerator.py`.
- `solver/generator/tile_pool.py`.
- `solver/generator/move_generator.py`.
- `solver/generator/set_changes.py`.
- `solver/generator/telemetry_store.py`.

**Reused with changes.**

- `solver/generator/puzzle_store.py`: schema migration adds `template_id`, `template_version` columns.
- `solver/generator/pregenerate.py`: repointed at the new entry, multiprocessing infrastructure retained.
- `solver/generator/gen_calibration_batch.py`: same.
- `solver/generator/calibrate.py`: retained; the `--fit-weights` mode is explicitly documented as diagnostic-only in the new world.

**Not reused (deleted).**

- `solver/generator/tile_remover.py`.
- `solver/generator/difficulty_evaluator.py`.
- `solver/generator/difficulty_weights.json`.
- Most of `solver/generator/puzzle_generator.py` (some helpers migrate; the file itself goes).

### 5.6 Retry and failure semantics

If `generate_puzzle` exhausts `MAX_ATTEMPTS` for a tier, it raises `PuzzleGenerationError`. The API layer then:

- For pool queries: returns a 404 or degraded response. Pool starvation is a pregeneration ops issue, not a live-generation problem.
- For live queries (easy/medium only): falls back to `legacy_sacrifice.py`.

Templates that are systematically failing (> 50% rejection rate after 1000 attempts) get flagged in telemetry. Template-level debugging ensues.

-----

## 6. File-by-File Migration Plan

Every file in the repository that is affected. Disposition is one of: **KEEP**, **REFACTOR**, **REPLACE**, **DELETE**, **CREATE**.

### 6.1 Backend — generator package

|File                                                 |Disposition |Action                                                                                                              |
|-----------------------------------------------------|------------|--------------------------------------------------------------------------------------------------------------------|
|`backend/solver/generator/puzzle_generator.py`       |**REPLACE** |Contents moved into `generator_core.py` (new) and `legacy_sacrifice.py` (new). File itself deleted after migration. |
|`backend/solver/generator/tile_remover.py`           |**DELETE**  |After `_attempt_generate_v2` is removed. No remaining importers.                                                    |
|`backend/solver/generator/difficulty_evaluator.py`   |**DELETE**  |Migrate `compute_chain_depth` and `compute_disruption_score` references to `objective.py` (they already live there).|
|`backend/solver/generator/difficulty_weights.json`   |**DELETE**  |                                                                                                                    |
|`backend/solver/generator/board_builder.py`          |**KEEP**    |Demoted from pipeline to library. Unchanged.                                                                        |
|`backend/solver/generator/set_enumerator.py`         |**KEEP**    |Unchanged.                                                                                                          |
|`backend/solver/generator/tile_pool.py`              |**KEEP**    |Unchanged.                                                                                                          |
|`backend/solver/generator/move_generator.py`         |**KEEP**    |Unchanged.                                                                                                          |
|`backend/solver/generator/set_changes.py`            |**KEEP**    |Unchanged.                                                                                                          |
|`backend/solver/generator/puzzle_store.py`           |**REFACTOR**|Add `template_id`, `template_version` columns to schema; update serialization/deserialization.                      |
|`backend/solver/generator/telemetry_store.py`        |**KEEP**    |Unchanged.                                                                                                          |
|`backend/solver/generator/pregenerate.py`            |**REFACTOR**|`_worker_generate_one` calls new generator entry. Retain parallel infrastructure.                                   |
|`backend/solver/generator/gen_calibration_batch.py`  |**REFACTOR**|Calls new generator entry.                                                                                          |
|`backend/solver/generator/calibrate.py`              |**KEEP**    |Document that `--fit-weights` is diagnostic-only in the new system.                                                 |
|`backend/solver/generator/calibration_batches/*.json`|**KEEP**    |Historical batches; new Phase-8 batch will be added.                                                                |

### 6.2 Backend — new files to create

|File                                                          |Purpose                                                       |Approximate size|
|--------------------------------------------------------------|--------------------------------------------------------------|----------------|
|`backend/solver/generator/generator_core.py`                  |Main `generate_puzzle()` entry, retry loop, template selection|200 lines       |
|`backend/solver/generator/legacy_sacrifice.py`                |Live fallback for easy/medium                                 |150 lines       |
|`backend/solver/generator/templates/__init__.py`              |Template registry, `@register_template` decorator             |80 lines        |
|`backend/solver/generator/templates/base.py`                  |`TemplateInstance`, `Template` ABC                            |100 lines       |
|`backend/solver/generator/templates/t1_joker_displacement.py` |Joker displacement chain template                             |250 lines       |
|`backend/solver/generator/templates/t2_false_extension.py`    |False-extension trap template                                 |200 lines       |
|`backend/solver/generator/templates/t3_multi_group_merge.py`  |Multi-group merge template                                    |250 lines       |
|`backend/solver/generator/templates/t4_run_group_transform.py`|Run-to-group transformation template                          |200 lines       |
|`backend/solver/generator/templates/t5_compound.py`           |Composition of other templates                                |200 lines       |
|`backend/solver/generator/gates/__init__.py`                  |Package marker                                                |10 lines        |
|`backend/solver/generator/gates/structural.py`                |Pre-ILP filters                                               |150 lines       |
|`backend/solver/generator/gates/ilp.py`                       |ILP solvability + uniqueness gate                             |80 lines        |
|`backend/solver/generator/gates/heuristic_solver.py`          |Human-analog solver                                           |250 lines       |

### 6.3 Backend — API layer

|File                   |Disposition |Action                                                                                                                                                     |
|-----------------------|------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|
|`backend/api/models.py`|**REFACTOR**|`PuzzleRequest`: drop custom-mode fields. Add `template_id: str | None`. `PuzzleResponse`: drop eight-metric fields; add `template_id`, `template_version`.|
|`backend/api/main.py`  |**REFACTOR**|`/api/puzzle` endpoint simplified: pool-first for hard+, live fallback for easy/medium only.                                                               |

### 6.4 Backend — tests

|File                                               |Disposition |Action                                                                                                     |
|---------------------------------------------------|------------|-----------------------------------------------------------------------------------------------------------|
|`backend/tests/solver/test_puzzle_generator.py`    |**REPLACE** |New tests for `generator_core`. Old v1/v2 tests deleted.                                                   |
|`backend/tests/solver/test_tile_remover.py`        |**DELETE**  |                                                                                                           |
|`backend/tests/solver/test_difficulty_evaluator.py`|**REPLACE** |Keep tests only for surviving metrics; remove composite-score tests. Rename to `test_objective_metrics.py`.|
|`backend/tests/solver/test_board_builder.py`       |**KEEP**    |                                                                                                           |
|`backend/tests/solver/test_puzzle_store.py`        |**REFACTOR**|Add tests for new columns.                                                                                 |
|`backend/tests/solver/test_set_enumerator.py`      |**KEEP**    |                                                                                                           |
|`backend/tests/solver/test_ilp_solver.py`          |**KEEP**    |                                                                                                           |
|`backend/tests/solver/test_solution_verifier.py`   |**KEEP**    |                                                                                                           |
|`backend/tests/solver/test_uniqueness.py`          |**KEEP**    |                                                                                                           |
|`backend/tests/api/test_puzzle_endpoint.py`        |**REFACTOR**|Update to new request/response schema.                                                                     |
|`backend/tests/api/test_solve_endpoint.py`         |**KEEP**    |Unrelated.                                                                                                 |

### 6.5 Backend — tests to create

|File                                                           |Purpose                                                                  |
|---------------------------------------------------------------|-------------------------------------------------------------------------|
|`backend/tests/solver/templates/test_t1_joker_displacement.py` |Per-template unit tests: determinism, invariant satisfaction, uniqueness |
|`backend/tests/solver/templates/test_t2_false_extension.py`    |Same                                                                     |
|`backend/tests/solver/templates/test_t3_multi_group_merge.py`  |Same                                                                     |
|`backend/tests/solver/templates/test_t4_run_group_transform.py`|Same                                                                     |
|`backend/tests/solver/templates/test_t5_compound.py`           |Same                                                                     |
|`backend/tests/solver/gates/test_structural.py`                |Gate unit tests with hand-crafted pass/fail cases                        |
|`backend/tests/solver/gates/test_heuristic_solver.py`          |Heuristic solver behavior tests                                          |
|`backend/tests/solver/test_generator_core.py`                  |End-to-end tests via `generate_puzzle()`                                 |
|`backend/tests/regression/test_no_trivial_puzzles.py`          |Regression corpus: generate N puzzles, assert none are heuristic-solvable|

### 6.6 Frontend

|File                                        |Disposition |Action                                                                                          |
|--------------------------------------------|------------|------------------------------------------------------------------------------------------------|
|`frontend/src/types/api.ts`                 |**REFACTOR**|Mirror backend model changes. Drop `composite_score` etc. Add `template_id`, `template_version`.|
|`frontend/src/components/PuzzleControls.tsx`|**REFACTOR**|Remove custom-mode UI. Remove composite-score badge.                                            |
|`frontend/src/store/game.ts`                |**REFACTOR**|Update `lastPuzzleMeta` and `loadPuzzle` to new response shape.                                 |
|`frontend/src/store/play.ts`                |**REFACTOR**|Update telemetry payloads.                                                                      |
|`frontend/src/lib/telemetry.ts`             |**REFACTOR**|Drop eight-metric fields from payloads.                                                         |
|`frontend/src/__tests__/` various           |**REFACTOR**|Update to new shape where affected.                                                             |

### 6.7 Documentation

|File                                          |Disposition|Action                                    |
|----------------------------------------------|-----------|------------------------------------------|
|`PUZZLE_DIFFICULTY_PROBLEM.md`                |**KEEP**   |Historical record of what failed.         |
|`CHANGELOG.md`                                |**EXTEND** |Add entries for each phase of the rebuild.|
|`PUZZLE_GENERATION_REBUILD_PLAN.md`           |**CREATE** |This document.                            |
|`backend/solver/generator/templates/README.md`|**CREATE** |Template authoring guide.                 |

-----

## 7. Step-by-Step Implementation Plan

Seven phases. Each phase is a mergeable unit of work with its own Definition of Done. Phases are sequential — Phase N depends on Phase N-1.

### Phase A — Infrastructure and API scaffolding

**Goal.** Prepare the target file structure, schema changes, and API models. No generator logic changes yet. The v2 system remains operational.

**Concrete changes.**

A1. Create empty files:

- `backend/solver/generator/generator_core.py` with stub `generate_puzzle()` that raises `NotImplementedError`.
- `backend/solver/generator/templates/__init__.py`, `templates/base.py`.
- `backend/solver/generator/gates/__init__.py`, `gates/structural.py`, `gates/ilp.py`, `gates/heuristic_solver.py`.

A2. `puzzle_store.py`: add `template_id TEXT NOT NULL DEFAULT 'legacy'` and `template_version TEXT NOT NULL DEFAULT '0'` to `_CREATE_TABLE` and `_MIGRATION_COLUMNS`. Update `_serialize_*` / `_deserialize_row`. Update `store()` signature to accept template metadata.

A3. `api/models.py`: add optional `template_id: str | None = None` to `PuzzleRequest`. Add `template_id: str = "legacy"`, `template_version: str = "0"` to `PuzzleResponse`. **Do not remove** existing fields yet — this phase is additive only.

A4. `api/main.py`: pass `template_id=""` to `_result_to_response` calls (no behavioral change).

A5. Test updates: `test_puzzle_store.py` gets new tests for the added columns. All existing tests continue to pass.

**Files affected.** `puzzle_store.py`, `api/models.py`, `api/main.py`, `test_puzzle_store.py`, 8 new empty files.

**Expected result.** All existing tests pass. New files exist but are not wired. v2 still works.

**Risks.** Schema migration could fail on existing DBs. Mitigation: the `contextlib.suppress(sqlite3.OperationalError)` pattern in `_create_tables` handles this; verify against a production-size DB.

**Definition of Done.**

- All existing tests pass.
- A fresh DB has the new columns.
- An existing DB with rows receives the columns via `ALTER TABLE` without data loss.
- `api/main.py` still returns valid responses.

### Phase B — Structural gates and heuristic solver

**Goal.** Implement the non-ILP filters in isolation. Full unit test coverage. These components are pure functions: given a board state, return a boolean.

**Concrete changes.**

B1. `gates/structural.py`:

- `check_no_trivial_extension(rack, board_sets) -> (bool, str)`: strict version rejecting extensions of any board set of any size ≥ 1.
- `check_no_single_home(rack, candidate_sets) -> (bool, str)`: rack tile must have 0 or ≥2 candidate placements.
- `check_joker_structural(state, solution_hint=None) -> (bool, str)`: joker on board implies movement in solution.
- `run_all_gates(state) -> (bool, list[str])`: dispatch.

B2. `gates/heuristic_solver.py`:

- `HeuristicSolver` class with `solves(state, max_depth=2) -> bool`.
- Priority rules as per §4.2.5.
- Pure function, no side effects, no solver calls. Uses only `set_enumerator` and `rule_checker`.

B3. `gates/ilp.py`:

- `run_ilp_gates(state, declared_chain_depth) -> (bool, str, Solution | None)`: calls `solve()` and `check_uniqueness()` in sequence.

B4. Comprehensive unit tests:

- `test_structural.py`: hand-crafted board states with known pass/fail outcomes. At least 20 tests.
- `test_heuristic_solver.py`: hand-crafted puzzles where heuristic should/shouldn’t solve. At least 15 tests. Crucially: **include Phase 7 puzzles** (seeds 10000–10004 per tier from `phase7_batch_v1`) and assert that the heuristic solver **does solve them**. This validates the heuristic is strong enough to recognize triviality.

**Files affected.** Three new files in `gates/`, three new test files.

**Expected result.** Gates and heuristic solver are testable in isolation. Phase 7 “nightmare” puzzles are detected as trivial by `HeuristicSolver.solves()` returning `True`.

**Risks.** The heuristic solver may be too strong (rejects legitimately hard puzzles) or too weak (accepts trivial ones). Mitigation: calibrate against the Phase 7 batch as a fixed benchmark. If the heuristic doesn’t solve Phase 7 nightmare puzzles, it is too weak and must be strengthened.

**Definition of Done.**

- All Phase 7 calibration puzzles are `heuristic_solver.solves() == True`. This is the acceptance criterion.
- Unit tests cover ≥15 hand-crafted non-trivial puzzles that `heuristic_solver.solves() == False`.
- No coverage regression in the rest of the solver package.

### Phase C — First template: T1 (joker displacement chain)

**Goal.** Implement one complete template end-to-end, including tests, template authoring documentation, and integration into `generator_core.py`. This phase proves the architecture.

**Concrete changes.**

C1. `templates/base.py`:

- `TemplateInstance` dataclass as per §4.3.1.
- `Template` ABC with `generate(rng) -> TemplateInstance` and `tier` class attribute.

C2. `templates/__init__.py`:

- `TEMPLATE_REGISTRY: dict[str, Template]`.
- `@register_template` decorator.
- `get_template(template_id) -> Template`.
- `list_templates(tier) -> list[str]`.

C3. `templates/t1_joker_displacement.py`:

- Define `T1JokerDisplacementV1`.
- Construction logic: choose a chain length L ∈ {3, 4}. Choose a chain of (color, number) triples where each tile’s movement requires the previous to be freed. Build the board with the chain embedded. Insert a joker at the chain head. Place “starter” rack tile that must replace the joker.
- Uniqueness must be provably enforced by construction (the alternative placements are blocked by rack tile values that have no other home).
- `declared_chain_depth = L`.

C4. `templates/README.md`:

- Template authoring guide. Required sections per template: structural invariants, uniqueness argument, why this is not trivial, expected rejection rate bounds.

C5. `generator_core.py`:

- `generate_puzzle(difficulty, seed=None, template_id=None, max_attempts=None) -> PuzzleResult`.
- Selects template from registry matching tier (or specific ID).
- Runs gates in order: structural → ILP → heuristic solver.
- Retries on gate failure.
- Records rejection reasons in telemetry.

C6. `tests/solver/templates/test_t1_joker_displacement.py`:

- Determinism: same seed → same puzzle.
- Invariant: every instance has `chain_depth >= declared_chain_depth` after ILP solve.
- Uniqueness: every instance passes `check_uniqueness`.
- Non-triviality: no instance is `heuristic_solver.solves() == True`.
- Generate 50 instances; measure rejection rates per gate.

**Files affected.** Two template files, generator_core.py, new test file, templates README.

**Expected result.** `generate_puzzle(difficulty="expert", template_id="T1_joker_displacement_v1")` returns a working hard puzzle in >10% of attempts. All structural invariants verified.

**Risks.**

- T1 construction is non-trivial. Budget 3–5 days.
- Uniqueness may be frequently violated if alternative placements aren’t fully blocked. Mitigation: iterate on the template, adding blocker rack tiles as needed. Keep a per-template log of rejection reasons.
- Generated puzzles may still be solved by the heuristic solver if the joker displacement isn’t deep enough. Mitigation: minimum chain length 3 is enforced, and the heuristic solver explicitly cannot attempt joker displacement.

**Definition of Done.**

- `generate_puzzle(difficulty="expert", template_id="T1_joker_displacement_v1")` succeeds within 10 attempts on ≥95% of seeds in the range 1..1000.
- Generated puzzles: 100% pass uniqueness, 100% have `chain_depth >= 3`, 0% are heuristic-solvable.
- Template README has a complete authoring entry.

### Phase D — Templates T2, T3, T4, T5

**Goal.** Complete the template catalog. Each template is a separate sub-phase. Order: T2 → T3 → T4 → T5.

**Per-template concrete changes** (repeat for D1–D4):

- Implement `templates/t{N}_*.py`.
- Write per-template unit tests (same pattern as C6).
- Add template-specific section to `templates/README.md`.
- Generate 50 instances for the template to establish rejection rate profile.

**T5 note.** T5 is a composition of T1–T4 for nightmare tier specifically. It picks two base templates and overlays their structures on a single board. This requires interaction-aware construction logic; budget extra time.

**Files affected.** Four template files, four test files, README updates.

**Expected result.** Five templates total, each independently verified.

**Risks.** Template design aesthetics: a player who sees 10 T1 puzzles in a row learns the pattern. Mitigation: the generator rotates among templates at the tier level, not per-request. Also T5 combines patterns to obscure individual types.

**Definition of Done.**

- All five templates produce puzzles meeting their declared invariants.
- Cross-template tests: generating 100 puzzles across all templates yields 0 heuristic-solvable instances.
- Per-template rejection rate documented in README.

### Phase E — Retire v2 pipeline

**Goal.** Remove the v2 generation path from the active code paths. Keep files temporarily for reference.

**Concrete changes.**

E1. `puzzle_generator.py`:

- Remove `_attempt_generate_v2` function and all v2 constants (`_BOARD_SIZE_RANGES_V2`, `_RACK_SIZE_RANGES_V2`, `_OVERLAP_BIASES_V2`, `_DEFAULT_MAX_ATTEMPTS_V2`, `_MIN_DISRUPTION_V2`, `_MIN_FRAGILITY_V2`, `_TIER_ORDER`, `_any_trivial_extension_v2`).
- Change `generate_puzzle()` default for `generator_version` to route to `generator_core.generate_puzzle()` for hard+ tiers.
- Keep the v1 `_attempt_generate_with_reason` path for easy/medium.

E2. `pregenerate.py`:

- `_worker_generate_one` calls `generator_core.generate_puzzle()` for hard+ tiers.
- Update CLI defaults.

E3. `gen_calibration_batch.py`:

- Same. Defaults to `generator_version="template"`.

E4. Delete `tile_remover.py`. Confirm no imports remain via `grep -r "tile_remover" backend/`.

E5. Delete `difficulty_evaluator.py`. Confirm no imports remain.

E6. Delete `difficulty_weights.json`. Confirm no references.

E7. Delete `tests/solver/test_tile_remover.py`.

E8. Rewrite `tests/solver/test_difficulty_evaluator.py` → `test_objective_metrics.py`: keep tests for `compute_chain_depth`, `compute_disruption_score` (which live in `objective.py`). Drop tests for composite score, normalization, tier classification.

E9. `api/models.py`: remove v2 fields from `PuzzleResponse` (`composite_score`, `branching_factor`, `deductive_depth`, `red_herring_density`, `working_memory_load`, `tile_ambiguity`, `solution_fragility`).

E10. `api/models.py`: remove v2 fields from `PuzzleRequest` custom-mode section (retiring custom mode). Keep `sets_to_remove` etc. marked as deprecated for one release; they become no-ops.

E11. Frontend `types/api.ts`: mirror the removals.

E12. Frontend `PuzzleControls.tsx`: remove custom-mode panel and composite-score badge.

E13. Frontend tests: update to new shape.

**Files affected.** 13 files, most deletions.

**Expected result.** v2 code is gone. Live traffic for hard+ uses `generator_core`. Live traffic for easy/medium still uses v1.

**Risks.** Hidden references to v2 symbols. Mitigation: run `pytest` + `tsc --noEmit` + `ruff check` after each deletion. Any broken import surfaces immediately.

**Definition of Done.**

- `grep -r "tile_remover" backend/` returns zero results.
- `grep -r "difficulty_evaluator" backend/` returns zero results.
- `grep -r "composite_score" backend/ frontend/src/` returns zero results (except migration notes in changelog).
- All tests pass.
- `/api/puzzle?difficulty=nightmare` returns a template-generated puzzle.

### Phase F — Legacy sacrifice generator for easy/medium

**Goal.** Preserve easy/medium live generation with minimal code. Easy puzzles are intentionally allowed to be trivial.

**Concrete changes.**

F1. `legacy_sacrifice.py`:

- Extract from `puzzle_generator.py`: `_make_pool`, `_pick_compatible_sets`, `_extract_by_sacrifice`, `_any_trivial_extension` (original v1).
- Expose `generate_easy(rng)` and `generate_medium(rng)`.
- Medium runs the new strict structural gate (from Phase B) to avoid completely trivial placements.
- Easy does not.
- No ILP uniqueness check (easy/medium tolerate multiple solutions).

F2. `generator_core.generate_puzzle()` dispatches:

- `tier in {"easy", "medium"}` → `legacy_sacrifice`.
- `tier in {"hard", "expert", "nightmare"}` → template path.

F3. Delete `puzzle_generator.py` after confirming all needed helpers have moved.

F4. Update imports everywhere.

**Files affected.** `legacy_sacrifice.py` (new), `generator_core.py`, `puzzle_generator.py` (deleted).

**Expected result.** Clean separation. Live generation works for all tiers.

**Definition of Done.**

- `puzzle_generator.py` is deleted.
- Easy and medium puzzles generate live in <500 ms per API call.
- All tests pass.

### Phase G — Pregeneration, calibration, and telemetry loop

**Goal.** Populate a production-scale pool and establish the calibration feedback loop.

**Concrete changes.**

G1. Run `pregenerate.py --all --count 50` offline. Expect ~3 templates × 3 tiers × 50 puzzles = 450 pregenerated puzzles. Nightmare and expert fully template-generated; hard gets a mix.

G2. Create `phase8_batch_v1.json` calibration batch from the pregenerated pool, 5 puzzles per tier, 25 total. Use pool UUIDs (like Phase 7).

G3. Run calibration on phase8_batch_v1: targets are

- Nightmare: average solve time ≥ 8 min, average undo count ≥ 3, zero self-labeled “trivial”.
- Expert: average solve time ≥ 4 min, average undo count ≥ 1.
- Hard: average solve time ≥ 90 s.

G4. Telemetry extensions: add `template_id`, `template_version` to telemetry events. Update `calibrate.py` to report per-template statistics.

G5. Write post-Phase-8 evaluation document at `POST_PHASE_8_EVALUATION.md` comparing Phase 7 vs Phase 8 metrics.

**Files affected.** Pool DB, calibration batch JSON, telemetry store, `calibrate.py`, new evaluation doc.

**Expected result.** Measurable improvement over Phase 7. If the hypothesis is correct, nightmare solve times should be measured in minutes, not seconds. If not, the rebuild has failed and we need to reassess.

**Risks.**

- Calibration by a single developer is still noisy. Mitigation: if the developer finds nightmare puzzles solvable in <2 min, there is a problem regardless of population statistics.
- Templates may produce puzzles that are structurally hard but feel arbitrary. Qualitative feedback in self-label and notes fields is important.

**Definition of Done.**

- Pool has ≥30 puzzles per hard+ tier.
- Phase 8 calibration batch exists, committed, and has been played.
- Post-Phase-8 evaluation is written with pass/fail judgment.
- If failed: a remediation plan is added to this document at §Appendix.

-----

## 8. Migration Strategy

### 8.1 Parallel operation window

Phases A, B, C run alongside the active v2 system. Both coexist until Phase E. This is achieved by:

- Keeping `generate_puzzle(generator_version="v2")` functional during development.
- `generator_core.generate_puzzle()` being gated behind an explicit call until Phase E.
- Pool content unaffected: existing Phase 7 puzzles remain in the pool with `template_id='legacy'`.

### 8.2 Stabilization before rewrite

Before Phase B begins, run the existing test suite and capture a baseline: all tests pass, lint clean, mypy strict clean. Any regression caught during the rebuild must be fixable to that baseline, not negotiated.

### 8.3 Isolation of touched code

The generator package is isolated from the rest of the application by a single entry point (`generate_puzzle`). As long as that signature is preserved (even if internals change radically), the rest of the codebase is unaffected.

Touch list (beyond the generator package):

- `api/models.py`: request/response fields.
- `api/main.py`: one function, `puzzle_endpoint`.
- Frontend types and UI: adapt to response shape.

Everything else is untouched.

### 8.4 Preventing instability during rebuild

- Phases A, B are additive. No deletions. Zero regression risk.
- Phase C adds a new entry point that is only invoked by explicit opt-in. Regression risk: zero.
- Phase D: each template is independent. A broken template fails its own tests; other paths unaffected.
- Phase E is the one-shot switch. Before merging, the `phase8_batch_v1` calibration must be at least one run that shows the template path produces puzzles. This is enforced by a pre-merge checklist.
- Phases F, G are cleanup.

### 8.5 When to retire old components permanently

End of Phase E: delete v2 code (`tile_remover.py`, `difficulty_evaluator.py`, `difficulty_weights.json`). Keep deleted files in git history; do not restore.

End of Phase F: delete `puzzle_generator.py`.

End of Phase G: if Phase 8 calibration shows the new system works, archive Phase 7 calibration data as historical. If Phase 8 shows failure, escalate per §11.

-----

## 9. Test Strategy

### 9.1 Test categories and coverage requirements

**Unit tests.**

Per-module tests for all new code. Coverage target: 90% statement coverage for `templates/`, `gates/`, `generator_core.py`.

- `test_structural.py`: each gate in isolation with crafted inputs.
- `test_heuristic_solver.py`: crafted puzzles with known expected solve/fail outcomes.
- `test_t{N}_*.py`: one test file per template.
- `test_generator_core.py`: the retry loop, rejection accounting, seed determinism.

**Property tests** (using `hypothesis`, already a dep per `pyproject.toml`).

- For each template: generate 50 instances over random seeds; assert uniqueness and non-triviality invariants hold for all. (Slow-marked.)
- For the pipeline end-to-end: `generate_puzzle` always returns a puzzle whose rack tiles can all be placed, or raises `PuzzleGenerationError`. Never returns an invalid intermediate state.

**Integration tests.**

- `test_generator_core.py`: `generate_puzzle("nightmare", seed=N)` for N in [1..100]. Assert: ≥95% return a valid puzzle, 100% of returned puzzles pass uniqueness and non-triviality.
- API-level: `/api/puzzle?difficulty=nightmare` returns a response with `template_id != "legacy"` and all schema fields populated.

**Golden / test corpus for puzzle difficulty.**

Create `backend/tests/fixtures/golden_puzzles/` with hand-curated puzzles:

- `trivial_001.json` through `trivial_010.json`: known-trivial puzzles (including the Phase 7 batch). `HeuristicSolver.solves()` must return `True` for all.
- `hard_001.json` through `hard_010.json`: hand-crafted puzzles that are structurally hard (designed by reviewing the template construction logic). `HeuristicSolver.solves()` must return `False`, `check_uniqueness` must return `True`.

**Regression tests against trivial puzzle output.**

`test_no_trivial_puzzles.py`:

```
Generate N=50 puzzles at each of hard/expert/nightmare tier.
For each puzzle:
    assert not heuristic_solver.solves(puzzle_state)
```

This is the canonical regression test. If it ever fails, the rebuild is broken.

**Tests for uniqueness.**

- Per-template: every generated puzzle passes `check_uniqueness`.
- Cross-template: in a batch of 100 puzzles, all pass uniqueness.
- Edge cases: puzzles with exactly two optimal arrangements (`check_uniqueness` returns `False`) must be rejected.

**Tests for difficulty heuristics.**

- Chain depth verification: `solve(puzzle).chain_depth >= declared_chain_depth` for all templates.
- Disruption score: recorded but not gated beyond diagnostic assertions.

**Performance and batch-generation tests.**

- Per-template timing: generating 50 instances of each template completes within a tier-specific time budget:
  - Hard: 50 puzzles in ≤ 5 minutes total.
  - Expert: 50 puzzles in ≤ 15 minutes total.
  - Nightmare: 50 puzzles in ≤ 30 minutes total.
- These budgets assume offline pregeneration, not live API. Live API budgets (easy/medium only) remain < 1 s per puzzle.

### 9.2 Test data

**Hand-crafted puzzle JSONs** in `tests/fixtures/golden_puzzles/`. Format mirrors the API response for direct deserialization.

**Seeded batches.** Each template test uses a fixed seed range (e.g. seeds 10000–10049) so regressions are detectable.

**Phase 7 calibration batch.** Kept as a fixed fixture for regression testing. Any new heuristic solver that does not classify all Phase 7 puzzles as trivial is wrong.

### 9.3 Metrics collected

- Rejection rate per template (target: <80% rejections during normal generation).
- Generation time per template (p50, p95, p99).
- Uniqueness pass rate (target: 100% after template-level fixes).
- Heuristic-solver rejection rate (for debugging: if a template’s heuristic-rejection rate drifts upward, that means generated puzzles have become too easy).

### 9.4 Objective success criteria

A run of the Phase 8 calibration batch (25 puzzles) is considered successful if:

- Median nightmare solve time ≥ 8 minutes.
- Median expert solve time ≥ 4 minutes.
- Zero nightmare/expert puzzles labeled “trivial” by the player.
- At least 50% of nightmare puzzles show ≥3 undo events.

Numerical thresholds are anchored in the gap between the Phase 7 observed times (~30 s nightmare) and the design target (10–30 min per `PUZZLE_DIFFICULTY_PROBLEM.md`). These numbers are conservative minimums; true success means exceeding them significantly.

-----

## 10. Difficulty Evaluation and Benchmarking

### 10.1 Metrics collected per generated puzzle

At generation time (cheap, always computed):

- `template_id`, `template_version`
- `chain_depth` (from solver)
- `disruption_score` (from solver)
- `joker_count`
- `is_unique` (from `check_uniqueness`)
- `heuristic_solver_rejected` (from heuristic gate)
- Generation wall-clock time

At calibration time (from telemetry):

- Solve time (median, p25, p75)
- Undo count (mean, median)
- Return-to-rack count
- Self-rating (1-10)
- Self-label (trivial / straightforward / challenging / brutal)
- Stuck moments (>30 s pauses)

### 10.2 Uniqueness metrics

- Pool-wide: what fraction of pool puzzles have `is_unique = True`? Target: 100%.
- Per-template: same. Target: 100%. Any template below 95% is bugged.

### 10.3 Per-generation success rate

For each template, measured by running `generate_puzzle(template_id=T)` for 100 random seeds and counting the ratio of successful returns to attempts. Targets:

- T1 (joker displacement): ≥40%
- T2 (false extension): ≥50%
- T3 (multi-group merge): ≥30%
- T4 (run-group transform): ≥50%
- T5 (compound): ≥20%

Templates below these thresholds indicate either a buggy template or unrealistic structural requirements. Remediation: template-level fix, not pipeline retuning.

### 10.4 Trivial puzzle fraction

Measured over a generation run by counting `heuristic_solver.solves(puzzle) == True` cases pre-rejection. Target: trivial fraction converges to near-zero after the heuristic-solver gate is applied (this is by construction — the gate rejects trivial puzzles).

### 10.5 Batch evaluation

Phase 8 calibration batch is the primary evaluation artifact. Structure:

- `phase8_batch_v1.json`: 25 puzzles (5 per tier × 5 tiers) with pool UUIDs.
- Completed calibration run generates a CSV export via `export_telemetry.py`.
- `POST_PHASE_8_EVALUATION.md` summarizes results with pass/fail judgment per G3 targets.

### 10.6 Alt-vs-new comparison

Phase 7 and Phase 8 use identical tier structures (5 puzzles per tier, same calibration UI, same self-rating questions). Direct comparison:

|Metric                                 |Phase 7 (v2 baseline)|Phase 8 target|Phase 8 actual|
|---------------------------------------|---------------------|--------------|--------------|
|Nightmare solve time (avg)             |28 s                 |≥8 min        |TBD           |
|Nightmare undos (avg)                  |0                    |≥3            |TBD           |
|Expert solve time (avg)                |18 s                 |≥4 min        |TBD           |
|Expert undos (avg)                     |0                    |≥1            |TBD           |
|Hard solve time (avg)                  |13 s                 |≥90 s         |TBD           |
|Self-labeled “trivial” rate (all tiers)|88%                  |≤10%          |TBD           |

### 10.7 Benchmark dataset

The Phase 7 batch itself serves as a *negative* benchmark: the heuristic solver must classify all 25 Phase 7 puzzles as trivial. If a new heuristic implementation fails on this, it is under-calibrated.

A *positive* benchmark is the hand-crafted `hard_001.json` through `hard_010.json` set: the heuristic solver must not solve these (they are human-designed to require multi-step non-greedy reasoning), and every new template’s generated puzzles must have comparable structural properties.

-----

## 11. Risks and Failure Modes

### R1. Templates exist but produce puzzles that humans still find trivial

**Scenario.** All gates pass. Heuristic solver fails. But human players solve nightmare in < 2 minutes.

**Likelihood.** Medium. The heuristic solver is an approximation of human reasoning; gaps are possible.

**Detection.** Phase 8 calibration solve times < target.

**Mitigation.**

- Strengthen the heuristic solver: add a depth-3 break attempt, or add multi-set merge detection.
- If strengthening makes the heuristic too strong (rejects legitimately hard puzzles), introduce a stricter template invariant (e.g. require chain_depth ≥ 4 for nightmare).
- Last resort: retire a template that consistently produces trivial-feeling puzzles.

### R2. Templates fail to produce puzzles at all

**Scenario.** A template’s structural constraints are so tight that no valid instance exists within reasonable seeds.

**Likelihood.** Medium. Template design is non-trivial.

**Detection.** Per-template rejection rate > 95% after 1000 attempts.

**Mitigation.**

- Relax the template’s internal constraints while preserving the guaranteed invariants.
- Bump `max_attempts` per template.
- Split the template into sub-variants.

### R3. Uniqueness check is too slow for nightmare-scale puzzles

**Scenario.** `check_uniqueness` runs the ILP with exclusions, which can time out on large puzzles.

**Likelihood.** Low-medium. Nightmare puzzles have ~16 board sets, rack size 7-8, which is well within solver capacity.

**Detection.** Pregeneration time per puzzle > 30 s average on a reasonable dev machine.

**Mitigation.**

- Increase `_UNIQUENESS_TIMEOUT_SECONDS` for nightmare only.
- Skip uniqueness check if the template *mathematically* guarantees it (documented per template).
- Last resort: pregeneration moves to a dedicated batch job with higher timeouts.

### R4. The heuristic solver is miscalibrated

**Scenario.** Heuristic solver classifies some Phase 7 nightmare puzzles as non-trivial.

**Likelihood.** Low, but specifically monitored in Phase B.

**Detection.** Phase B unit test fails: `heuristic_solver.solves(phase7_nightmare_puzzle)` returns `False`.

**Mitigation.** This is a must-fix in Phase B. The heuristic solver cannot be weaker than a human’s greedy approach; if it is, the entire architecture falls apart.

### R5. Seed determinism breaks because of non-deterministic template internals

**Scenario.** A template uses a non-seeded random source (e.g. `random.random()` instead of `rng.random()`), breaking reproducibility.

**Likelihood.** Medium. Easy mistake.

**Detection.** Same seed produces different puzzles across runs.

**Mitigation.** Lint rule: `grep -n "random\." backend/solver/generator/templates/*.py | grep -v "rng\." | grep -v "^import random"` must return zero results. Add to CI.

### R6. Player recognition degrades template hardness over time

**Scenario.** A player who has played 30 T1 puzzles learns to spot joker displacement chains in seconds.

**Likelihood.** High over time, near-zero for new players.

**Detection.** Calibration telemetry shows solve times declining within a tier as sessions accumulate.

**Mitigation.**

- Template rotation: the generator must never serve the same template twice in a row for the same player (requires player-state tracking, outside current scope but documented as future work).
- T5 compound templates mix recognizable patterns.
- Periodically retire overexposed templates and replace with new designs.

### R7. Template-level bugs silently violate uniqueness

**Scenario.** A template claims to produce unique puzzles, but some seeds violate this.

**Likelihood.** Medium.

**Detection.** Hard-gate on `check_uniqueness`; rejections are logged. Per-template rejection rate for `not_unique` > 10% triggers template review.

**Mitigation.** The hard gate prevents the violation from reaching users. Remediation is a template-level patch.

### R8. Easy/medium live path breaks because dependencies moved

**Scenario.** `legacy_sacrifice.py` extraction misses a helper; live generation for easy/medium crashes.

**Likelihood.** Medium. Refactoring risk.

**Detection.** Integration tests in Phase F.

**Mitigation.** Do not delete `puzzle_generator.py` until Phase F is fully green.

### R9. Frontend regressions due to schema changes

**Scenario.** A frontend component still references `composite_score` or other removed fields.

**Likelihood.** High if not carefully checked.

**Detection.** `tsc --noEmit` after each frontend change. TypeScript catches all removed-field accesses.

**Mitigation.** Run frontend typecheck in CI. Block merges on TS errors.

### R10. Pool starvation for nightmare if pregeneration is slow

**Scenario.** Pool has fewer puzzles than active players; clients see the same puzzle twice.

**Likelihood.** Medium, depending on player volume.

**Detection.** `puzzle_store.count("nightmare")` low; pool-empty logs in API.

**Mitigation.**

- Target 100+ nightmare puzzles in pool before Phase G closes.
- `gen_calibration_batch.py` cron to regenerate batches weekly.

-----

## 12. Engineering Guidelines

### 12.1 Module boundaries

- `templates/` only generate `TemplateInstance` objects. No solver calls inside templates (except the construction helpers for verification assertions in **debug**). All validation happens in `gates/`.
- `gates/` only accept a fully-materialized `BoardState` and return boolean judgments. No construction logic.
- `generator_core.py` orchestrates templates and gates. No construction logic, no gate logic.
- The API layer passes requests through to `generator_core.generate_puzzle()`. No generation logic in the API.

### 12.2 No hidden logic in UI/glue code

- The frontend displays what the API returns. It does not compute difficulty locally.
- The solver is not invoked from the frontend.
- Telemetry payloads include template metadata as-is from the API response.

### 12.3 Deterministic interfaces

Given a `(tier, seed, template_id)` tuple, `generate_puzzle()` produces the same `PuzzleResult` every time. Templates must not use non-seeded randomness. This is enforced by the CI lint from R5.

### 12.4 Reproducible seeds where sensible

- Generation seeds are reproducible.
- Tests use fixed seed ranges.
- The pregeneration CLI prints the seed of each generated puzzle for post-hoc debugging.

### 12.5 Logging and debuggability

All rejections at any gate are logged with:

- Template ID and version.
- Rejection reason.
- Seed.
- Relevant metrics (e.g. chain depth achieved, heuristic solver depth).

Use the existing `structlog` infrastructure. Log level `info` for successful generations, `warning` for repeated rejections of the same (template, reason) pair, `error` for template-invariant violations.

### 12.6 Metric capture

Every generated puzzle that is stored carries:

- `template_id`, `template_version`
- Generation seed
- Attempt count
- All verified metrics (chain_depth, disruption_score, is_unique, heuristic_solver_rejected)

These go into `puzzle_store.py` and are queryable via SQL for ad-hoc analysis.

### 12.7 Configurability without architecture dilution

- Template parameters (chain length, number of distraction sets) are per-template module constants. They are not in a config file because changing them changes the template’s identity and requires a version bump.
- Tier-level retry budgets are constants in `generator_core.py`.
- Nothing is in `difficulty_weights.json`. That file is deleted.

### 12.8 Clean separation between construction, evaluation, and selection

- Construction: templates + generator_core retry loop.
- Evaluation: gates.
- Selection: API pool drawing with `seen_ids` exclusion.

These are three separate concerns in three separate code locations. Mixing them is a code review rejection.

### 12.9 Code review checklist for new templates

Every new template PR must:

- [ ] Declare structural invariants in the docstring.
- [ ] Include a “Why this is not trivial” section.
- [ ] Include a uniqueness argument (why alternatives are blocked).
- [ ] Have unit tests covering: determinism, invariant satisfaction, uniqueness, heuristic-solver rejection, rejection rate measurement over 100 seeds.
- [ ] Include at least one hand-verified example puzzle as a JSON fixture.

-----

## 13. Open Assumptions and Explicit Decisions

|#  |Assumption                                                                                                                                     |Decision made                                                                                                                                                        |Should validate by                                                                                                       |
|---|-----------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------|
|A1 |Sudoku-style template-based generation transfers to Rummikub.                                                                                  |**Proceed assuming yes.** Rummikub has established hard patterns in human play (joker chains, false extensions). These are the direct analogs of Sudoku’s X-Wing etc.|Phase 8 calibration showing solve times matching targets.                                                                |
|A2 |The heuristic solver can be made strong enough to detect all Phase-7 trivial puzzles without being so strong it rejects legitimately hard ones.|**Proceed assuming yes.** Validated in Phase B with Phase 7 batch as fixed test.                                                                                     |Phase B unit tests. If they fail persistently, the architecture assumption is broken and a fundamental rethink is needed.|
|A3 |5 templates provide enough variety for 100+ pool puzzles without pattern recognition becoming dominant.                                        |**Proceed assuming yes for initial rollout.** Plan for 10 templates within 3 months post-launch.                                                                     |Telemetry tracking solve time decline within a single player’s sessions.                                                 |
|A4 |Single-developer calibration (Phase 8) is sufficient to validate the rebuild.                                                                  |**Proceed.** Phase 8 is a sanity check, not a scientific result. A proper user study is out of scope for this rebuild.                                               |Post-Phase-8 evaluation judgment.                                                                                        |
|A5 |Easy/medium puzzles are allowed to be trivial.                                                                                                 |**Proceed.** These are for UX practice, not challenge. Legacy sacrifice generator suffices.                                                                          |Product decision, not technical.                                                                                         |
|A6 |Seeds map 1-to-1 to puzzles. A given seed on a given template produces exactly one puzzle.                                                     |**Decision: yes.** Do not allow templates to have additional internal randomness beyond `rng`. Enforced by lint.                                                     |R5 CI lint.                                                                                                              |
|A7 |`check_uniqueness` with timeout 10 s is reliable for nightmare-scale puzzles.                                                                  |**Proceed with current timeout; monitor in Phase G.** If timeouts become common, raise per-tier limits.                                                              |Phase G pregeneration timing.                                                                                            |
|A8 |The existing ILP solver handles template-generated puzzles without regression.                                                                 |**Proceed assuming yes.** The solver does not care how the puzzle was generated.                                                                                     |All existing solver tests continue to pass.                                                                              |
|A9 |T5 compound templates produce meaningfully harder puzzles than individual T1-T4.                                                               |**Proceed assuming yes for initial design.** If empirically false, T5 is retired and the nightmare tier uses T1-T4 directly with higher chain-depth minimums.        |Phase 8 nightmare solve times.                                                                                           |
|A10|The `template_id` API field is useful to clients.                                                                                              |**Expose it but do not guarantee semantics for clients.** Templates may be retired or renamed. The API documents `template_id` as opaque.                            |Ongoing API contract discipline.                                                                                         |

-----

## 14. Final Decision

### 14.1 Architecture to be implemented

Template-based deterministic puzzle generation with ILP uniqueness enforcement and heuristic-solver post-filtering. Hard, expert, and nightmare tiers are served from a pregenerated pool populated by templates. Easy and medium are live-generated by a slimmed-down v1 sacrifice generator.

### 14.2 Components retained from the current system

- All of `solver/engine/`, `solver/models/`, `solver/validator/`, `solver/config/`.
- `solver/generator/set_enumerator.py`, `tile_pool.py`, `move_generator.py`, `set_changes.py`.
- `solver/generator/board_builder.py` as a library component (not called from the pipeline).
- `solver/generator/puzzle_store.py` with schema additions.
- `solver/generator/telemetry_store.py`.
- `solver/generator/calibrate.py` as a diagnostic tool.
- `solver/generator/pregenerate.py` and `gen_calibration_batch.py` as refactored orchestration CLIs.
- The entire API layer, with request/response schema simplifications.

### 14.3 Components removed

- `solver/generator/tile_remover.py`.
- `solver/generator/difficulty_evaluator.py`.
- `solver/generator/difficulty_weights.json`.
- Most of `solver/generator/puzzle_generator.py` (rest moves to `legacy_sacrifice.py`).
- Eight composite-score metric fields from API responses and frontend.
- Custom-mode puzzle parameters.

### 14.4 New components

- `solver/generator/generator_core.py`.
- `solver/generator/legacy_sacrifice.py`.
- `solver/generator/templates/` package with 5 template modules.
- `solver/generator/gates/` package with structural, ILP, and heuristic-solver gates.

### 14.5 Implementation order

A → B → C → D (T2, T3, T4, T5 sequentially) → E → F → G. Seven phases, estimated 4–6 weeks of focused work.

### 14.6 Why this approach is the one likely to succeed

Four independent reasons converge on the template-based approach:

**Structural.** The Phase 7 failure mode is that random generation cannot reliably hit the thin target subset of human-hard Rummikub puzzles. Template-based construction does not sample — it constructs members of that subset directly. The constructive approach is the only known way to break out of the thin-target-subset problem. This is a mathematical observation, not an engineering preference.

**Empirical.** Other puzzle domains with analogous difficulty challenges (Sudoku, Nonogram, KenKen) converged on template-based or rule-based construction after abandoning random-and-test. This is not a coincidence; the underlying combinatorial constraint is the same.

**Economic.** Template design is labor-intensive but its cost is up-front and capped. Random-sample-and-score costs are ongoing: every kalibration batch requires tuning weights, thresholds, gates, normalizations. Template-based systems have flat maintenance cost; probabilistic systems have compounding costs as metrics drift against reality.

**Organizational.** Template-based debugging is locally scoped. When a template produces bad puzzles, you fix that template. When a composite score is miscalibrated, you do not know which component is wrong; you tune all of them and hope. The feedback loop in a template system is short and specific.

The rebuild is not guaranteed. Template design is non-trivial and the heuristic solver may need iteration. But every identified risk has a documented mitigation, and the failure modes are localizable. The current system’s failure mode — “all puzzles trivial regardless of configuration” — has no known mitigation short of exactly this rebuild.

The decision is: **execute this plan. Start with Phase A. Do not attempt parallel alternatives.**

-----

## Appendix: Checklist for Phase Handoffs

Each phase closes with these confirmations before the next phase begins:

**Phase A closure:**

- [ ] `pytest` clean on full suite
- [ ] `ruff check` clean
- [ ] `mypy --strict` clean on `backend/solver/` and `backend/api/`
- [ ] `tsc --noEmit` clean on frontend
- [ ] Schema migration verified on existing DB

**Phase B closure:**

- [ ] `HeuristicSolver.solves()` returns `True` for all 25 Phase 7 batch puzzles
- [ ] ≥15 hand-crafted non-trivial puzzles `HeuristicSolver.solves() == False`
- [ ] 90% statement coverage on `gates/`

**Phase C closure:**

- [ ] T1 template produces ≥95% success rate on seeds 1..1000 with 10 max_attempts
- [ ] All T1 puzzles: unique, chain_depth ≥ 3, not heuristic-solvable

**Phase D closure:**

- [ ] T2, T3, T4, T5 all pass Phase C-style criteria
- [ ] Cross-template regression test: 100 puzzles, 0 heuristic-solvable

**Phase E closure:**

- [ ] `tile_remover.py`, `difficulty_evaluator.py`, `difficulty_weights.json` deleted
- [ ] Full test suite green
- [ ] `/api/puzzle?difficulty=nightmare` returns template-generated response

**Phase F closure:**

- [ ] `puzzle_generator.py` deleted
- [ ] Easy and medium live generation < 500 ms per call
- [ ] Frontend: `tsc --noEmit` clean, no `composite_score` references

**Phase G closure:**

- [ ] Pool has ≥ 30 puzzles per hard+ tier
- [ ] `phase8_batch_v1.json` exists and has been calibrated
- [ ] `POST_PHASE_8_EVALUATION.md` written with pass/fail judgment
- [ ] Phase 8 solve times meet or exceed targets (see §10.6 table)

-----

*End of document.*
