# Puzzle Generation System — Full Rebuild Implementation Plan

**Version:** 1.0
**Date:** 2026-04-12
**Status:** Implementation-ready blueprint
**Target:** Replace current sacrifice-based puzzle generator with strategic tile-removal + human-difficulty scoring

-----

## Table of Contents

1. [Current-State Assessment](#1-current-state-assessment)
1. [Recommended Target Architecture](#2-recommended-target-architecture)
1. [Phased Implementation Roadmap](#3-phased-implementation-roadmap)
1. [Exact Proposed Fixes](#4-exact-proposed-fixes)
1. [Empirical Difficulty Framework](#5-empirical-difficulty-framework)
1. [Difficulty Metrics and Validation](#6-difficulty-metrics-and-validation)
1. [Testing Strategy](#7-testing-strategy)
1. [Happy Path, Edge Cases, and Failure Modes](#8-happy-path-edge-cases-and-failure-modes)
1. [Engineering Concerns](#9-engineering-concerns)
1. [Bugs, Race Conditions, and Operational Risks](#10-bugs-race-conditions-and-operational-risks)
1. [Rollout and Transition Plan](#11-rollout-and-transition-plan)

-----

## 1. Current-State Assessment

### 1.1 What Exists Today

The puzzle generation pipeline consists of five modules:

|Module               |File                                          |Role                                                                             |
|---------------------|----------------------------------------------|---------------------------------------------------------------------------------|
|`puzzle_generator.py`|`backend/solver/generator/puzzle_generator.py`|Core generation loop: build board → sacrifice sets → sample rack → solve → filter|
|`set_enumerator.py`  |`backend/solver/generator/set_enumerator.py`  |Enumerates all valid run/group templates from a tile pool                        |
|`puzzle_store.py`    |`backend/solver/generator/puzzle_store.py`    |SQLite persistence for pre-generated puzzles                                     |
|`pregenerate.py`     |`backend/solver/generator/pregenerate.py`     |CLI batch pre-generation with multiprocessing                                    |
|`set_changes.py`     |`backend/solver/generator/set_changes.py`     |Post-solve change manifest for the UI                                            |

Supporting modules used by generation:

|Module                |File                                           |Role                                                      |
|----------------------|-----------------------------------------------|----------------------------------------------------------|
|`solver.py`           |`backend/solver/engine/solver.py`              |ILP solver entry point; also provides `check_uniqueness()`|
|`objective.py`        |`backend/solver/engine/objective.py`           |`compute_disruption_score()` and `compute_chain_depth()`  |
|`ilp_formulation.py`  |`backend/solver/engine/ilp_formulation.py`     |HiGHS ILP model construction                              |
|`rule_checker.py`     |`backend/solver/validator/rule_checker.py`     |Independent set/board validation                          |
|`solution_verifier.py`|`backend/solver/validator/solution_verifier.py`|Post-solve correctness verification                       |

The generation algorithm (current):

```
1. Create full tile pool (104 tiles + 0-2 jokers)
2. Enumerate all valid runs and groups from the pool
3. Greedily pick N non-overlapping sets as "the board"
4. Randomly choose K sets to sacrifice (remove entirely)
5. Sample M tiles from the sacrificed sets as the rack
6. Filter: reject if any rack tile trivially extends a remaining set
7. Solve: run the ILP solver on (remaining_board, rack)
8. Reject if solver doesn't place all rack tiles
9. Compute disruption_score and chain_depth from solver output
10. Filter on disruption band and minimum chain depth
11. Optionally check solution uniqueness (expert/nightmare)
12. If all filters pass → accept; else → retry
```

Difficulty parameters per tier:

|Tier     |Sacrifice|Rack size|Disruption band|Min chain depth|Uniqueness|
|---------|---------|---------|---------------|---------------|----------|
|Easy     |1        |2-3      |2-10           |0              |No        |
|Medium   |2        |3-4      |9-18           |0              |No        |
|Hard     |3        |4-5      |16-28          |1              |No        |
|Expert   |5        |6-10     |32+            |2              |Yes       |
|Nightmare|7        |10-14    |38+            |3              |Yes       |

Pre-generation uses tighter profiles:

|Tier              |Board size|Sacrifice|Rack size|Min disruption|Min chain|
|------------------|----------|---------|---------|--------------|---------|
|Expert (pregen)   |12-14     |3        |5-6      |38            |3        |
|Nightmare (pregen)|13-15     |3        |6-7      |42            |4        |

### 1.2 Parts That Can Be Reused

**Keep entirely (no changes needed):**

- `solver/engine/solver.py` — the ILP solver is correct and performant; the new generator will call it
- `solver/engine/ilp_formulation.py` — model construction is sound
- `solver/validator/rule_checker.py` — independent validation, critical for new generator
- `solver/validator/solution_verifier.py` — post-solve verification, still needed
- `solver/models/` — `Tile`, `TileSet`, `BoardState`, `Solution`, `Color`, `SetType` are stable
- `solver/config/rules.py` — `RulesConfig` is unchanged
- `solver/generator/set_enumerator.py` — needed to enumerate candidate sets for the new approach
- `solver/generator/set_changes.py` — UI change manifest, unaffected by generation changes
- `solver/generator/puzzle_store.py` — SQLite pool, schema needs minor extension but core is reusable

**Keep with modifications:**

- `solver/engine/objective.py` — `compute_disruption_score()` stays as one input to the new difficulty model; `compute_chain_depth()` stays but is downgraded from primary metric to one of many signals
- `solver/generator/pregenerate.py` — the parallel worker framework is reusable but the worker function and progress reporting need rewriting to call the new generator
- `api/main.py` — the `/api/puzzle` endpoint stays; the response model is extended with new difficulty metadata
- `api/models.py` — `PuzzleResponse` gains new fields; `PuzzleRequest` unchanged

**Delete or replace entirely:**

- `puzzle_generator.py` functions: `_attempt_generate_with_reason()`, `_extract_by_sacrifice()`, `_extract_rack()`, `_extract_custom()`, `_sample_rack_from_sacrificed_sets()`, `_pick_compatible_sets()`, `_inject_jokers_into_board()`, `_any_trivial_extension()`, `_build_rack_candidate()`, `_better_rack_candidate()`, `_estimate_complexity()`
- All difficulty band constants: `_RACK_SIZES`, `_SACRIFICE_COUNTS`, `_DISRUPTION_BANDS`, `_BOARD_SIZES`, `_MIN_CHAIN_DEPTHS`, `_PREGEN_PROFILES`, `_PREGEN_CONSTRAINTS`
- The `PuzzleResult` dataclass gains new fields
- The `generate_puzzle()` entry point is rewritten with the same signature but new internals

**Technical debt to account for:**

- `_make_pool()` / `_make_full_pool()` create all 106 tiles; these stay but should be consolidated into one function
- `_assign_copy_ids()` is duplicated between `puzzle_generator.py` and `api/main.py`; deduplicate during rebuild
- The `PuzzleGenerationError` exception and retry-loop pattern are sound and stay
- SQLite puzzle pool (`puzzle_store.py`) needs a schema migration to add new difficulty fields

### 1.3 Architectural Constraints

- The solver is stateless and processes each request independently; the new generator must also be stateless per invocation
- Pre-generation runs in separate worker processes via `ProcessPoolExecutor`; the new generator’s worker function must be pickle-safe (module-level, no closures)
- The frontend expects `PuzzleResponse` with `board_sets`, `rack`, `difficulty`, `disruption_score`, `chain_depth`, `is_unique`, `puzzle_id`; backward compatibility must be maintained
- Docker deployment uses a named volume for the puzzle SQLite DB; schema migrations must handle existing data
- The solver timeout is 30s for normal solves, 10s for uniqueness checks; the new generator must respect these

-----

## 2. Recommended Target Architecture

### 2.1 Architecture Overview

The new system has four major modules:

```
┌──────────────────────────────────────────────────────────────┐
│                     PuzzleGenerator                          │
│  (Orchestrator: calls BoardBuilder → TileRemover →           │
│   DifficultyEvaluator in sequence)                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ BoardBuilder  │  │ TileRemover  │  │ DifficultyEval    │  │
│  │              │→│              │→│                   │  │
│  │ Build a rich, │  │ Strategically │  │ Score the puzzle  │  │
│  │ overlapping   │  │ remove tiles  │  │ on multiple axes  │  │
│  │ valid board   │  │ to create the │  │ and classify      │  │
│  │              │  │ rack           │  │ difficulty         │  │
│  └──────────────┘  └──────────────┘  └───────────────────┘  │
│         │                 │                    │              │
│         └────────┬────────┘                    │              │
│                  ↓                             │              │
│          ┌──────────────┐                      │              │
│          │   Solver     │←─────────────────────┘              │
│          │ (existing)   │                                     │
│          └──────────────┘                                     │
└──────────────────────────────────────────────────────────────┘
         │
         ↓
  ┌──────────────┐     ┌──────────────────┐
  │ PuzzleStore  │     │ Pregenerate CLI  │
  │ (SQLite)     │     │ (parallel batch) │
  └──────────────┘     └──────────────────┘
```

### 2.2 Module Responsibilities

**BoardBuilder** (`board_builder.py` — new file)

- Constructs a valid board with high tile-overlap: many tiles that appear in multiple valid alternative sets
- Uses a tile-overlap graph to guide set selection, favoring boards where rearrangement options are abundant
- Controls board size (number of sets, total tiles)
- Returns a `BoardState` with only `board_sets` populated (rack empty)

**TileRemover** (`tile_remover.py` — new file)

- Takes a valid board and strategically removes individual tiles to form the rack
- Removal strategy: remove tiles that break minimum-viable sets (3-tile sets), forcing cascading rearrangements
- Each removal is verified by running the solver to confirm the puzzle is still solvable
- Removal order is guided by a heuristic that prioritizes tiles whose removal creates the deepest dependency chains
- Stops when the target rack size is reached or further removal makes the puzzle unsolvable
- Returns the modified `BoardState` (reduced board + rack)

**DifficultyEvaluator** (`difficulty_evaluator.py` — new file)

- Takes a puzzle (board + rack) and the solver’s solution and computes a multi-dimensional difficulty score
- Metrics (detailed in Section 6): branching factor, deductive depth, red herring density, working memory load, disruption score, chain depth, tile ambiguity, solution fragility
- Maps the multi-dimensional score to a difficulty tier (easy through nightmare)
- Returns a `DifficultyScore` dataclass with all metrics and the classified tier

**PuzzleGenerator** (rewritten `puzzle_generator.py`)

- Orchestrates the pipeline: BoardBuilder → TileRemover → Solver → DifficultyEvaluator
- Implements the retry loop with filtering based on DifficultyEvaluator output
- Entry point: `generate_puzzle(difficulty, ...)` with the same public signature
- Returns `PuzzleResult` (extended with new metrics)

### 2.3 Data Flow

```
generate_puzzle(difficulty="nightmare", seed=42)
  │
  ├─ rng = Random(seed)
  │
  ├─ board = BoardBuilder.build(rng, target_size=12..15, overlap_target="high")
  │    │
  │    ├─ pool = make_full_pool()        # 104 tiles
  │    ├─ all_sets = enumerate_runs(pool) + enumerate_groups(pool)
  │    ├─ overlap_graph = build_overlap_graph(all_sets)
  │    └─ board_sets = select_high_overlap_sets(overlap_graph, rng, n=target_size)
  │
  ├─ (board_with_rack, removal_log) = TileRemover.remove(board, rng,
  │        rack_size=6..8, strategy="maximize_cascade")
  │    │
  │    ├─ for each candidate tile to remove:
  │    │    ├─ trial_state = remove tile from board, add to rack
  │    │    ├─ solution = solve(trial_state)
  │    │    ├─ if solution.tiles_placed < rack_size: skip (unsolvable)
  │    │    ├─ cascade_score = estimate_cascade_depth(trial_state, solution)
  │    │    └─ rank candidates by cascade_score
  │    └─ pick best candidate, commit removal, repeat
  │
  ├─ state = BoardState(board_with_rack.board_sets, board_with_rack.rack)
  ├─ solution = solve(state)
  │
  ├─ score = DifficultyEvaluator.evaluate(state, solution)
  │    │
  │    ├─ branching_factor = compute_branching_factor(state)
  │    ├─ deductive_depth = compute_deductive_depth(state, solution)
  │    ├─ red_herring_density = compute_red_herrings(state, solution)
  │    ├─ working_memory = compute_working_memory_load(state, solution)
  │    ├─ disruption = compute_disruption_score(state.board_sets, solution.new_sets)
  │    ├─ chain_depth = compute_chain_depth(state.board_sets, solution.new_sets, solution.placed_tiles)
  │    ├─ ambiguity = compute_tile_ambiguity(state)
  │    ├─ fragility = compute_solution_fragility(state, solution)
  │    └─ tier = classify_tier(branching_factor, deductive_depth, ...)
  │
  ├─ if score.tier != requested difficulty: retry
  ├─ if difficulty in (expert, nightmare): check_uniqueness(state, solution)
  │
  └─ return PuzzleResult(board_sets, rack, score, ...)
```

### 2.4 New/Changed Data Models

**`DifficultyScore` (new dataclass in `difficulty_evaluator.py`)**:

```python
@dataclass(frozen=True)
class DifficultyScore:
    # Individual metrics (0.0–1.0 normalized)
    branching_factor: float    # avg valid placements per rack tile
    deductive_depth: float     # how many tiles must be mentally placed before verification
    red_herring_density: float # fraction of locally-valid but globally-invalid placements
    working_memory_load: float # number of sets that must be rearranged simultaneously
    tile_ambiguity: float      # avg number of candidate sets per tile
    solution_fragility: float  # how sensitive the solution is to single-tile changes

    # Legacy metrics (kept for backward compatibility and as inputs)
    disruption_score: int
    chain_depth: int

    # Composite
    composite_score: float     # weighted combination of all metrics (0–100)
    classified_tier: str       # "easy" | "medium" | "hard" | "expert" | "nightmare"
```

**`PuzzleResult` (extended)**:

```python
@dataclass
class PuzzleResult:
    board_sets: list[TileSet]
    rack: list[Tile]
    difficulty: Difficulty
    disruption_score: int
    chain_depth: int
    is_unique: bool
    joker_count: int
    # NEW fields:
    branching_factor: float
    deductive_depth: float
    red_herring_density: float
    working_memory_load: float
    tile_ambiguity: float
    solution_fragility: float
    composite_score: float
    generator_version: str       # e.g. "v2.0.0" — tracks which algorithm produced this puzzle
```

**`PuzzleResponse` API model (extended)**:

```python
class PuzzleResponse(BaseModel):
    # ... existing fields ...
    # NEW (optional, backward-compatible):
    composite_score: float = 0.0
    branching_factor: float = 0.0
    generator_version: str = "v1"
```

**SQLite schema migration** (puzzle_store.py):

```sql
ALTER TABLE puzzles ADD COLUMN branching_factor REAL DEFAULT 0.0;
ALTER TABLE puzzles ADD COLUMN deductive_depth REAL DEFAULT 0.0;
ALTER TABLE puzzles ADD COLUMN red_herring_density REAL DEFAULT 0.0;
ALTER TABLE puzzles ADD COLUMN working_memory_load REAL DEFAULT 0.0;
ALTER TABLE puzzles ADD COLUMN tile_ambiguity REAL DEFAULT 0.0;
ALTER TABLE puzzles ADD COLUMN solution_fragility REAL DEFAULT 0.0;
ALTER TABLE puzzles ADD COLUMN composite_score REAL DEFAULT 0.0;
ALTER TABLE puzzles ADD COLUMN generator_version TEXT DEFAULT 'v1';
```

### 2.5 Interfaces Between Components

```
BoardBuilder.build(rng, board_size_range, overlap_mode) → list[TileSet]

TileRemover.remove(board_sets, rng, rack_size_range, strategy, solve_timeout)
    → (remaining_board: list[TileSet], rack: list[Tile], removal_log: list[RemovalStep])

DifficultyEvaluator.evaluate(state: BoardState, solution: Solution)
    → DifficultyScore

DifficultyEvaluator.classify_tier(score: DifficultyScore) → Difficulty

generate_puzzle(difficulty, seed, ...) → PuzzleResult  # unchanged public signature
```

### 2.6 Storage / Pre-generation / Runtime Strategy

- **Easy/Medium/Hard**: generated at runtime (fast enough with the new approach, target <2s)
- **Expert**: pre-generated pool of 200+ puzzles; runtime fallback if pool empty
- **Nightmare**: pre-generated pool of 100+ puzzles; no runtime fallback (too slow)
- **Custom**: always runtime-generated; uses DifficultyEvaluator but skips tier filtering
- Pre-generated puzzles stored in SQLite with all new metric fields
- Pool draw logic unchanged (random selection, exclude seen IDs)

-----

## 3. Phased Implementation Roadmap

### Phase 0: Preparation and Infrastructure (2-3 days)

**Objective:** Set up the scaffolding for the new modules without changing existing behavior.

**Scope:**

- Create new files with empty/stub implementations
- Add the `generator_version` field to track old vs. new generator output
- Set up the SQLite schema migration
- Consolidate duplicated code (`_make_pool`, `_assign_copy_ids`)

**Tasks:**

1. Create `backend/solver/generator/board_builder.py` with class stub and docstring
1. Create `backend/solver/generator/tile_remover.py` with class stub and docstring
1. Create `backend/solver/generator/difficulty_evaluator.py` with class stub and docstring
1. Add `generator_version` field to `PuzzleResult`, defaulting to `"v1"`
1. Add `generator_version` to `PuzzleResponse` API model (optional field, default `"v1"`)
1. Write SQLite migration in `puzzle_store.py._create_tables()` using `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` pattern (SQLite 3.35+) or try/except for older versions
1. Consolidate `_make_pool()` and `_make_full_pool()` into a single `make_tile_pool(n_jokers=0)` function in a new `backend/solver/generator/tile_pool.py`
1. Move `_assign_copy_ids()` from `puzzle_generator.py` to `tile_pool.py` as a public function `assign_copy_ids()`
1. Update imports in `puzzle_generator.py` and `api/main.py` to use the new locations
1. Run existing test suite to confirm no regressions

**Files affected:**

- `backend/solver/generator/board_builder.py` (new)
- `backend/solver/generator/tile_remover.py` (new)
- `backend/solver/generator/difficulty_evaluator.py` (new)
- `backend/solver/generator/tile_pool.py` (new)
- `backend/solver/generator/puzzle_generator.py` (import changes only)
- `backend/solver/generator/puzzle_store.py` (schema migration)
- `backend/api/models.py` (new optional field)
- `backend/api/main.py` (import changes)

**Dependencies:** None (preparation only).

**Risks:**

- SQLite `ALTER TABLE ADD COLUMN` in WAL mode on a live database: safe for adding nullable columns, but the migration code must handle the case where columns already exist (re-running the migration)
- Renaming/moving functions could break import paths in tests

**Validation criteria:**

- All existing tests pass
- `generate_puzzle()` still works identically (returns v1 puzzles)
- SQLite DB can be opened with new columns present

**Exit criteria:** Green CI, no behavioral changes to existing puzzles.

-----

### Phase 1: BoardBuilder — High-Overlap Board Construction (3-5 days)

**Objective:** Build boards where many tiles participate in multiple valid sets, creating the structural foundation for difficult puzzles.

**Scope:** Implement `BoardBuilder` end to end.

**Implementation tasks:**

**1.1 — Tile overlap graph**

Build a graph where nodes are tiles and edges connect tiles that co-occur in at least one valid set template. Weight edges by the number of shared templates.

```python
# In board_builder.py

from collections import defaultdict
from solver.models.tile import Color, Tile
from solver.models.tileset import TileSet
from solver.generator.set_enumerator import enumerate_runs, enumerate_groups
from solver.generator.tile_pool import make_tile_pool

TileKey = tuple[Color, int]  # (color, number) — copy_id irrelevant at template level

def build_overlap_graph(
    all_sets: list[TileSet],
) -> dict[TileKey, dict[TileKey, int]]:
    """Map each tile key to the other tile keys it shares sets with, weighted by count."""
    adj: dict[TileKey, dict[TileKey, int]] = defaultdict(lambda: defaultdict(int))
    for ts in all_sets:
        keys = [(t.color, t.number) for t in ts.tiles if not t.is_joker and t.color and t.number]
        for i, k1 in enumerate(keys):
            for k2 in keys[i+1:]:
                adj[k1][k2] += 1
                adj[k2][k1] += 1
    return dict(adj)
```

**1.2 — Set coverage scoring**

For each candidate set, compute a “coverage score” that measures how many alternative placements its tiles have. Sets with high-coverage tiles are preferred because removing a tile from them later forces consideration of multiple alternatives.

```python
def score_set_overlap(
    ts: TileSet,
    overlap_graph: dict[TileKey, dict[TileKey, int]],
) -> float:
    """Score a set by the average overlap connectivity of its tiles."""
    keys = [(t.color, t.number) for t in ts.tiles if not t.is_joker and t.color and t.number]
    if not keys:
        return 0.0
    return sum(sum(overlap_graph.get(k, {}).values()) for k in keys) / len(keys)
```

**1.3 — Overlap-aware set selection**

Replace `_pick_compatible_sets()` with a new selection algorithm:

```python
def select_high_overlap_sets(
    all_sets: list[TileSet],
    overlap_graph: dict[TileKey, dict[TileKey, int]],
    rng: random.Random,
    target_count: int,
    overlap_bias: float = 0.7,  # 0.0 = random, 1.0 = pure overlap-greedy
) -> list[TileSet]:
    """Select non-conflicting sets biased toward high tile overlap.

    Uses a weighted random selection: each candidate set's weight is
    (1 - overlap_bias) + overlap_bias * normalized_overlap_score.
    This ensures some randomness while strongly favoring high-overlap boards.
    """
    avail: Counter[tuple[Color, int]] = Counter()
    for color in Color:
        for num in range(1, 14):
            avail[(color, num)] = 2

    # Pre-score all sets
    scored = [(ts, score_set_overlap(ts, overlap_graph)) for ts in all_sets]
    max_score = max((s for _, s in scored), default=1.0) or 1.0

    selected: list[TileSet] = []
    remaining = list(scored)

    while len(selected) < target_count and remaining:
        # Filter to sets that don't conflict with already-selected tiles
        candidates = []
        for ts, score in remaining:
            needed = Counter(
                (t.color, t.number) for t in ts.tiles
                if not t.is_joker and t.color and t.number
            )
            if all(avail[k] >= v for k, v in needed.items()):
                candidates.append((ts, score))

        if not candidates:
            break

        # Weighted random selection
        weights = [
            (1.0 - overlap_bias) + overlap_bias * (s / max_score)
            for _, s in candidates
        ]
        chosen_ts, _ = rng.choices(candidates, weights=weights, k=1)[0]

        selected.append(chosen_ts)
        for t in chosen_ts.tiles:
            if not t.is_joker and t.color and t.number:
                avail[(t.color, t.number)] -= 1

        remaining = [(ts, s) for ts, s in remaining if ts is not chosen_ts]

    return selected
```

**1.4 — BoardBuilder.build() entry point**

```python
class BoardBuilder:
    @staticmethod
    def build(
        rng: random.Random,
        board_size_range: tuple[int, int] = (10, 15),
        overlap_bias: float = 0.7,
        n_jokers: int = 0,
    ) -> list[TileSet]:
        pool = make_tile_pool(n_jokers)
        all_sets = enumerate_runs(pool) + enumerate_groups(pool)
        rng.shuffle(all_sets)  # randomize before scoring to break ties
        overlap_graph = build_overlap_graph(all_sets)
        target = rng.randint(*board_size_range)
        board_sets = select_high_overlap_sets(all_sets, overlap_graph, rng, target, overlap_bias)
        return assign_copy_ids(board_sets)
```

**Files affected:**

- `backend/solver/generator/board_builder.py` (full implementation)
- `backend/solver/generator/tile_pool.py` (if not already done in Phase 0)

**Dependencies:** Phase 0 complete.

**Risks:**

- High overlap_bias could produce boards that always look similar (low variety); mitigate with the randomness floor `(1 - overlap_bias)`
- The overlap graph for all 329 base templates is small (computed in <1ms) — no performance risk
- `rng.choices()` with weights: must ensure weights are positive (guaranteed since overlap_bias ∈ [0,1] and scores ≥ 0)

**Validation criteria:**

- `BoardBuilder.build()` consistently produces boards with 10-15 valid sets
- Boards pass `is_valid_board()` from `rule_checker.py`
- Average tile overlap (number of alternative valid set placements per tile) is measurably higher than old `_pick_compatible_sets()`: target ≥2.5 alternative sets per tile vs. old ~1.2
- Boards are sufficiently diverse: run 100 generations with different seeds, verify no two boards share >80% of tiles

**Exit criteria:** BoardBuilder passes all unit tests, produces boards with verified high overlap, completes in <50ms per invocation.

-----

### Phase 2: TileRemover — Strategic Tile Removal (5-8 days)

**Objective:** Remove individual tiles from the board to form the rack, choosing tiles that maximize solving difficulty by creating cascading rearrangement requirements.

**Scope:** Implement `TileRemover` end to end. This is the most algorithmically complex phase.

**Implementation tasks:**

**2.1 — Removal candidate scoring**

For each tile on the board, compute a “removal impact score” that estimates how much difficulty its removal would create.

```python
# In tile_remover.py

@dataclass(frozen=True)
class RemovalCandidate:
    set_index: int          # which board set the tile belongs to
    tile_index: int         # position within that set
    tile: Tile
    set_size_after: int     # size of parent set after removal
    breaks_set: bool        # True if set_size_after < 3 (set becomes invalid)
    orphan_count: int       # number of orphaned tiles if set breaks
    alternative_placements: int  # how many other valid sets this tile could join
    cascade_estimate: float # estimated depth of cascading rearrangements

@dataclass(frozen=True)
class RemovalStep:
    candidate: RemovalCandidate
    state_before: BoardState  # for debugging/replay
    solver_result: Solution   # verify solvability
```

**2.2 — Cascade depth estimation (without running the solver)**

To avoid running the full ILP for every candidate tile (which would be too slow), use a lightweight heuristic:

```python
def estimate_cascade_depth(
    board_sets: list[TileSet],
    tile_to_remove: Tile,
    set_index: int,
    all_valid_templates: list[TileSet],
) -> float:
    """Estimate how many cascading rearrangements removing this tile would cause.

    Heuristic: if removing tile T from set S makes S invalid (< 3 tiles),
    the remaining tiles of S must find new homes. For each orphaned tile O,
    count how many existing sets O could join (by extending them) vs. how many
    would need to be broken apart to accommodate O. More breakage = higher cascade.
    """
    parent_set = board_sets[set_index]
    remaining_tiles = [t for t in parent_set.tiles if t is not tile_to_remove]

    if len(remaining_tiles) >= 3:
        # Set survives as a smaller valid set — low cascade
        return 0.5

    # Set breaks — orphaned tiles need new homes
    orphans = remaining_tiles
    cascade = 0.0

    for orphan in orphans:
        # Count sets that could absorb this orphan by simple extension
        absorb_count = 0
        for i, ts in enumerate(board_sets):
            if i == set_index:
                continue
            extended = TileSet(type=ts.type, tiles=ts.tiles + [orphan])
            if is_valid_set(extended):
                absorb_count += 1

        if absorb_count == 0:
            # Orphan has no easy home — must rearrange other sets to place it
            cascade += 2.0
        elif absorb_count == 1:
            # Exactly one option — forced placement, but may displace other tiles
            cascade += 1.0
        else:
            # Multiple options — ambiguity (hard for human) but not cascading
            cascade += 0.5

    return cascade
```

**2.3 — The removal loop**

```python
class TileRemover:
    @staticmethod
    def remove(
        board_sets: list[TileSet],
        rng: random.Random,
        rack_size_range: tuple[int, int],
        strategy: str = "maximize_cascade",
        solve_timeout: float = 8.0,
        max_removal_attempts_per_tile: int = 5,
    ) -> tuple[list[TileSet], list[Tile], list[RemovalStep]] | None:
        """Strategically remove tiles from the board to form the rack.

        Returns (remaining_board, rack, removal_log) or None if unable to
        produce a solvable puzzle within the target rack size range.
        """
        target_rack_size = rng.randint(*rack_size_range)
        current_board = [TileSet(type=ts.type, tiles=list(ts.tiles)) for ts in board_sets]
        rack: list[Tile] = []
        removal_log: list[RemovalStep] = []
        all_templates = enumerate_runs(BoardState(current_board, [])) + \
                       enumerate_groups(BoardState(current_board, []))

        for step in range(target_rack_size):
            candidates = _score_all_candidates(current_board, all_templates)

            if not candidates:
                break  # No more tiles can be removed

            # Sort by cascade estimate (highest first), with randomness
            if strategy == "maximize_cascade":
                candidates.sort(key=lambda c: c.cascade_estimate, reverse=True)
                # Take from top 30% with weighted random selection
                top_n = max(1, len(candidates) // 3)
                top_candidates = candidates[:top_n]
                weights = [c.cascade_estimate + 0.1 for c in top_candidates]
                chosen = rng.choices(top_candidates, weights=weights, k=1)[0]
            else:
                chosen = rng.choice(candidates)

            # Apply the removal
            new_board = _apply_removal(current_board, chosen)
            new_rack = rack + [chosen.tile]

            # Verify solvability
            state = BoardState(board_sets=new_board, rack=new_rack)
            try:
                solution = solve(state, timeout_seconds=solve_timeout)
            except ValueError:
                # Unsolvable — try another candidate
                continue

            if solution.tiles_placed < len(new_rack):
                # Not all rack tiles placeable — try another candidate
                continue

            # Commit the removal
            removal_log.append(RemovalStep(
                candidate=chosen,
                state_before=BoardState(current_board, rack),
                solver_result=solution,
            ))
            current_board = new_board
            rack = new_rack

            # Recompute templates with updated pool
            all_templates = enumerate_runs(BoardState(current_board, rack)) + \
                          enumerate_groups(BoardState(current_board, rack))

        if len(rack) < rack_size_range[0]:
            return None  # Could not reach minimum rack size

        return current_board, rack, removal_log
```

**2.4 — Helper: apply removal**

```python
def _apply_removal(
    board_sets: list[TileSet],
    candidate: RemovalCandidate,
) -> list[TileSet]:
    """Remove the candidate tile from the board, dropping empty sets."""
    result = []
    for i, ts in enumerate(board_sets):
        if i == candidate.set_index:
            remaining = [t for j, t in enumerate(ts.tiles) if j != candidate.tile_index]
            if remaining:
                result.append(TileSet(type=ts.type, tiles=remaining))
            # If empty, drop the set entirely
        else:
            result.append(TileSet(type=ts.type, tiles=list(ts.tiles)))
    return result
```

**2.5 — Helper: score all candidates**

```python
def _score_all_candidates(
    board_sets: list[TileSet],
    all_templates: list[TileSet],
) -> list[RemovalCandidate]:
    candidates = []
    for si, ts in enumerate(board_sets):
        for ti, tile in enumerate(ts.tiles):
            set_size_after = len(ts.tiles) - 1
            breaks = set_size_after < 3
            orphans = set_size_after if breaks else 0

            # Count alternative placements for this tile
            alt_count = 0
            for tmpl in all_templates:
                for tmpl_tile in tmpl.tiles:
                    if (tmpl_tile.color == tile.color and
                        tmpl_tile.number == tile.number and
                        not tmpl_tile.is_joker):
                        alt_count += 1
                        break

            cascade = estimate_cascade_depth(board_sets, tile, si, all_templates)

            candidates.append(RemovalCandidate(
                set_index=si,
                tile_index=ti,
                tile=tile,
                set_size_after=set_size_after,
                breaks_set=breaks,
                orphan_count=orphans,
                alternative_placements=alt_count,
                cascade_estimate=cascade,
            ))

    return candidates
```

**Performance note:** The removal loop runs the solver up to `target_rack_size` times (typically 4-8 times for hard difficulties). Each solver call takes 10-100ms on typical boards. Total removal phase: 50-800ms. This is acceptable for runtime generation of easy/medium/hard and for pre-generation of expert/nightmare.

If candidates frequently fail the solvability check, the loop may need more iterations. Add a retry limit per step (default 5) and bail out if exceeded.

**Files affected:**

- `backend/solver/generator/tile_remover.py` (full implementation)

**Dependencies:** Phase 1 complete (BoardBuilder provides the input boards).

**Risks:**

- **Solver calls in a loop:** Each removal step calls `solve()`, which runs HiGHS. If boards are complex and the solver takes close to the timeout on each call, total generation time could be 5-10s per puzzle. Mitigation: use a shorter timeout (2-5s) for intermediate verification steps; the final verification uses the full timeout.
- **Greedy removal is not globally optimal:** Removing the “best” tile at step 1 might make step 2 trivial. Mitigation: the randomness in top-30% selection provides exploration. For pre-generation, this is acceptable since we generate many puzzles and keep the best.
- **Removal may leave an invalid board state:** After removing a tile from a 3-tile set, the remaining 2 tiles are “orphaned” on the board. The solver can rearrange them, but the `state` passed to the solver must represent the board AS-IS (with orphaned tiles). The solver’s existing logic handles this correctly — orphaned tiles in 2-tile “sets” are treated as board tiles that must be placed into valid sets.
  - **CRITICAL IMPLEMENTATION DETAIL:** When a 3-tile set breaks, the remaining 2 tiles should stay on the board (not go to the rack). They are board tiles that the solver must rearrange. The rack only gets the removed tile. This is the key difference from the old sacrifice approach.
  - **HOWEVER:** The current `BoardState` stores `board_sets: list[TileSet]`, and each `TileSet` is validated by the solver. A 2-tile “set” is INVALID. **Solution:** After removal, if a set has <3 tiles, dissolve it: move its remaining tiles into a special “floating board tiles” list. In practice, represent this by creating singleton “sets” that the solver treats as individual board tiles. The ILP already handles this — a 1-tile “set” will be broken apart and the tile reassigned. But `rule_checker.is_valid_set()` will reject sets with <3 tiles. **Fix:** The solver skips validation of the input board (it only validates its output). The ILP’s tile conservation constraint (each board tile must appear in some active set) handles this. So we can pass 1-tile or 2-tile “sets” in `board_sets` and the solver will rearrange them into valid sets. **Verify this with a test.**

**Validation criteria:**

- `TileRemover.remove()` returns a solvable puzzle for ≥80% of input boards (measured over 100 trials)
- Removal log shows genuine set-breaking (at least 1 set reduced to <3 tiles for hard+ puzzles)
- The solver’s solution for removed-tile puzzles has higher disruption scores than sacrifice-based puzzles of the same rack size (measured by comparison)
- The removal loop completes within 2 seconds for rack sizes ≤6 and within 5 seconds for rack sizes 7-8
- No tile conservation violations: `solution_verifier.verify_solution()` passes for every generated puzzle

**Exit criteria:** TileRemover passes all unit tests, produces solvable puzzles with measurably higher disruption than the old system, completes within time budgets.

-----

### Phase 3: DifficultyEvaluator — Multi-Metric Scoring (4-6 days)

**Objective:** Build a difficulty scoring system that measures multiple dimensions of human-perceived difficulty, replacing the current single-metric disruption/chain-depth approach.

**Scope:** Implement all difficulty metrics and the classification function.

**Implementation tasks:**

**3.1 — Branching factor**

```python
def compute_branching_factor(state: BoardState) -> float:
    """Average number of valid placements per rack tile.

    For each rack tile, count how many distinct (set, position) combinations
    would produce a valid set if the tile were placed there. Higher = harder
    because the player must evaluate more options.

    Returns a float ≥ 0. Typical range: 1.0 (forced) to 8.0+ (highly ambiguous).
    """
    if not state.rack:
        return 0.0

    all_sets_with_rack = enumerate_valid_sets(state)
    total_placements = 0

    for rack_tile in state.rack:
        placements = 0
        for candidate_set in all_sets_with_rack:
            for tmpl_tile in candidate_set.tiles:
                if (not tmpl_tile.is_joker and
                    tmpl_tile.color == rack_tile.color and
                    tmpl_tile.number == rack_tile.number):
                    placements += 1
                    break  # count each candidate set once per rack tile
        total_placements += placements

    return total_placements / len(state.rack)
```

**3.2 — Red herring density**

```python
def compute_red_herrings(state: BoardState, solution: Solution) -> float:
    """Fraction of locally-valid placements that are globally invalid.

    A "red herring" is a placement that looks valid in isolation (tile fits
    into a valid set) but is NOT part of the optimal solution. Higher density
    means more wrong turns for the player to explore and discard.
    """
    if not state.rack:
        return 0.0

    all_candidates = enumerate_valid_sets(state)

    # Which sets are actually used in the solution?
    solution_set_keys = set()
    for ts in solution.new_sets:
        key = frozenset((t.color, t.number, t.copy_id, t.is_joker) for t in ts.tiles)
        solution_set_keys.add(key)

    total_placements = 0
    red_herrings = 0

    for rack_tile in state.rack:
        for candidate_set in all_candidates:
            contains_tile = any(
                not t.is_joker and t.color == rack_tile.color and t.number == rack_tile.number
                for t in candidate_set.tiles
            )
            if not contains_tile:
                continue

            total_placements += 1
            cs_key = frozenset(
                (t.color, t.number, t.copy_id, t.is_joker) for t in candidate_set.tiles
            )
            if cs_key not in solution_set_keys:
                red_herrings += 1

    return red_herrings / total_placements if total_placements > 0 else 0.0
```

**3.3 — Working memory load**

```python
def compute_working_memory_load(
    state: BoardState, solution: Solution
) -> float:
    """Number of sets that must be simultaneously rearranged.

    Measures the "breadth" of rearrangement: how many existing sets the player
    must mentally manipulate at the same time. Higher breadth = harder because
    humans have limited working memory (Miller's 7±2 chunks).

    Returns 0 if no rearrangement needed, otherwise the count of disrupted source sets.
    """
    old_sigs = [
        frozenset((t.color, t.number, t.is_joker) for t in ts.tiles)
        for ts in state.board_sets
    ]
    new_sigs = [
        frozenset((t.color, t.number, t.is_joker) for t in ts.tiles)
        for ts in solution.new_sets
    ]

    unchanged_sigs = set(old_sigs) & set(new_sigs)
    disrupted = sum(1 for sig in old_sigs if sig not in unchanged_sigs)
    return float(disrupted)
```

**3.4 — Tile ambiguity**

```python
def compute_tile_ambiguity(state: BoardState) -> float:
    """Average number of candidate sets each tile could belong to.

    Computed over ALL tiles (board + rack). High ambiguity means the solver
    (and human) must consider many possible arrangements. This directly
    measures the search space breadth.
    """
    all_candidates = enumerate_valid_sets(state)
    all_tiles = list(state.all_tiles)

    if not all_tiles:
        return 0.0

    total_options = 0
    for tile in all_tiles:
        if tile.is_joker:
            # Jokers can go in any set — always high ambiguity
            total_options += len(all_candidates)
        else:
            options = sum(
                1 for cs in all_candidates
                if any(
                    not t.is_joker and t.color == tile.color and t.number == tile.number
                    for t in cs.tiles
                )
            )
            total_options += options

    return total_options / len(all_tiles)
```

**3.5 — Solution fragility**

```python
def compute_solution_fragility(
    state: BoardState, solution: Solution
) -> float:
    """How sensitive the solution is to single-tile changes.

    Measures: if we remove one random rack tile, how often does the remaining
    puzzle become unsolvable or require a completely different arrangement?

    High fragility = the solution is "tight" with little slack, meaning the
    player must find the exact right arrangement. Low fragility = there's lots
    of slack and many tile placements work.

    Computed by sampling: remove each rack tile in turn, re-solve, and check
    if the solution structure changes significantly.
    """
    if len(state.rack) <= 1:
        return 0.0

    changes = 0
    for i in range(len(state.rack)):
        reduced_rack = [t for j, t in enumerate(state.rack) if j != i]
        reduced_state = BoardState(board_sets=state.board_sets, rack=reduced_rack)
        try:
            reduced_solution = solve(reduced_state, timeout_seconds=2.0)
        except ValueError:
            changes += 1  # Became unsolvable → very fragile
            continue

        if reduced_solution.tiles_placed < len(reduced_rack):
            changes += 1
            continue

        # Compare solution structure
        old_disruption = compute_disruption_score(state.board_sets, solution.new_sets)
        new_disruption = compute_disruption_score(state.board_sets, reduced_solution.new_sets)
        if abs(old_disruption - new_disruption) > 3:
            changes += 1  # Significant structural change

    return changes / len(state.rack)
```

**PERFORMANCE WARNING:** `compute_solution_fragility()` runs `len(rack)` additional solver calls. For a 7-tile rack, that’s 7 extra solves. Each takes 10-100ms. Total: 70-700ms. Acceptable for pre-generation but may be too slow for runtime generation of easy/medium puzzles. **Mitigation:** Skip this metric for easy/medium tiers (set to 0.0).

**3.6 — Deductive depth**

```python
def compute_deductive_depth(state: BoardState, solution: Solution) -> float:
    """How many tiles must be mentally placed before the placement can be verified.

    This measures sequential reasoning depth: if tile A must go in set X, but
    you can only determine this AFTER deciding where tile B goes, the deductive
    depth is at least 2.

    Approximation: count how many rack tiles have exactly 1 valid placement in
    the solution (forced moves) vs. how many require choosing among alternatives
    that depend on other choices.

    Returns 0 for trivially solvable, higher for deeper reasoning chains.
    """
    if not solution.placed_tiles:
        return 0.0

    # Use chain_depth as a base (it already measures sequential dependency)
    base_depth = compute_chain_depth(
        state.board_sets, solution.new_sets, solution.placed_tiles
    )

    # Augment with branching: depth is harder when each step has multiple options
    bf = compute_branching_factor(state)

    # Heuristic: deductive depth ≈ chain_depth * log2(branching_factor + 1)
    import math
    return base_depth * math.log2(bf + 1)
```

**3.7 — Composite score and tier classification**

```python
def compute_composite_score(
    branching_factor: float,
    deductive_depth: float,
    red_herring_density: float,
    working_memory_load: float,
    tile_ambiguity: float,
    solution_fragility: float,
    disruption_score: int,
    chain_depth: int,
) -> float:
    """Weighted combination of all metrics into a 0-100 composite score."""
    # Normalize each metric to roughly 0-1 range
    bf_norm = min(branching_factor / 8.0, 1.0)
    dd_norm = min(deductive_depth / 10.0, 1.0)
    rh_norm = red_herring_density  # already 0-1
    wm_norm = min(working_memory_load / 10.0, 1.0)
    ta_norm = min(tile_ambiguity / 15.0, 1.0)
    sf_norm = solution_fragility  # already 0-1
    ds_norm = min(disruption_score / 50.0, 1.0)
    cd_norm = min(chain_depth / 5.0, 1.0)

    # Weights (sum to 1.0) — tuned based on cognitive difficulty model
    weights = {
        "branching": 0.20,
        "deductive": 0.20,
        "red_herring": 0.15,
        "working_memory": 0.15,
        "ambiguity": 0.10,
        "fragility": 0.10,
        "disruption": 0.05,
        "chain_depth": 0.05,
    }

    composite = (
        weights["branching"] * bf_norm +
        weights["deductive"] * dd_norm +
        weights["red_herring"] * rh_norm +
        weights["working_memory"] * wm_norm +
        weights["ambiguity"] * ta_norm +
        weights["fragility"] * sf_norm +
        weights["disruption"] * ds_norm +
        weights["chain_depth"] * cd_norm
    ) * 100.0

    return round(composite, 2)


TIER_THRESHOLDS = {
    "easy":      (0, 20),
    "medium":    (15, 35),
    "hard":      (30, 55),
    "expert":    (50, 75),
    "nightmare": (70, 100),
}

def classify_tier(composite_score: float) -> str:
    """Map composite score to difficulty tier. Overlapping bands are intentional."""
    for tier in ("nightmare", "expert", "hard", "medium", "easy"):
        lo, hi = TIER_THRESHOLDS[tier]
        if composite_score >= lo:
            return tier
    return "easy"
```

**3.8 — DifficultyEvaluator facade**

```python
class DifficultyEvaluator:
    @staticmethod
    def evaluate(
        state: BoardState,
        solution: Solution,
        skip_expensive: bool = False,
    ) -> DifficultyScore:
        bf = compute_branching_factor(state)
        rh = compute_red_herrings(state, solution)
        wm = compute_working_memory_load(state, solution)
        ta = compute_tile_ambiguity(state)
        sf = 0.0 if skip_expensive else compute_solution_fragility(state, solution)
        dd = compute_deductive_depth(state, solution)
        ds = compute_disruption_score(state.board_sets, solution.new_sets)
        cd = compute_chain_depth(state.board_sets, solution.new_sets, solution.placed_tiles)
        cs = compute_composite_score(bf, dd, rh, wm, ta, sf, ds, cd)
        tier = classify_tier(cs)

        return DifficultyScore(
            branching_factor=round(bf, 2),
            deductive_depth=round(dd, 2),
            red_herring_density=round(rh, 4),
            working_memory_load=round(wm, 2),
            tile_ambiguity=round(ta, 2),
            solution_fragility=round(sf, 4),
            disruption_score=ds,
            chain_depth=cd,
            composite_score=cs,
            classified_tier=tier,
        )
```

**Files affected:**

- `backend/solver/generator/difficulty_evaluator.py` (full implementation)

**Dependencies:** Phase 0 (data models), existing solver and objective modules.

**Risks:**

- **Weight tuning:** The composite score weights are educated guesses. They MUST be calibrated against actual human solving data (Phase 8 of the roadmap and Section 5). Initially, use the proposed weights and adjust based on playtesting.
- **Metric correlation:** Some metrics may be highly correlated (e.g., branching_factor and tile_ambiguity). If so, they effectively double-count the same difficulty dimension. Mitigation: compute Pearson correlations across a large sample of puzzles during validation; reduce weight of correlated metrics.
- **Performance of compute_red_herrings:** Enumerates all valid sets and checks each rack tile against them. For large boards with jokers, `enumerate_valid_sets()` can return ~2000 templates. With 8 rack tiles, that’s 16000 iterations — still trivially fast (<5ms).

**Validation criteria:**

- Easy puzzles score 0-20 composite; nightmare puzzles score 70-100
- Composite score correlates with rack size (more tiles = harder) but is NOT entirely determined by it (same rack size can produce different scores based on board structure)
- All metrics return sane values: branching_factor ≥ 1.0 for solvable puzzles, red_herring_density ∈ [0, 1], etc.
- DifficultyEvaluator.evaluate() completes in <500ms for typical puzzles (skip_expensive=True) and <2s (skip_expensive=False)

**Exit criteria:** DifficultyEvaluator produces scores that pass all validation criteria and generate a reasonable difficulty curve across 1000+ test puzzles.

-----

### Phase 4: Generator Integration (3-4 days)

**Objective:** Wire BoardBuilder + TileRemover + DifficultyEvaluator into the new `generate_puzzle()` function, replacing the old logic while maintaining the same public API.

**Scope:** Rewrite `puzzle_generator.py` internals, keeping the public interface stable.

**Implementation tasks:**

**4.1 — New `_attempt_generate_v2()` function**

```python
def _attempt_generate_v2(
    rng: random.Random,
    difficulty: Difficulty,
    solve_timeout: float | None = None,
) -> _AttemptOutcome:
    """New generation approach: build → remove → evaluate."""

    # Board size scales with difficulty
    board_size_ranges: dict[str, tuple[int, int]] = {
        "easy": (6, 9),
        "medium": (8, 11),
        "hard": (10, 13),
        "expert": (12, 15),
        "nightmare": (13, 16),
        "custom": (8, 14),
    }
    rack_size_ranges: dict[str, tuple[int, int]] = {
        "easy": (2, 3),
        "medium": (3, 4),
        "hard": (4, 5),
        "expert": (5, 7),
        "nightmare": (6, 8),
        "custom": (3, 6),
    }
    overlap_biases: dict[str, float] = {
        "easy": 0.3,
        "medium": 0.4,
        "hard": 0.5,
        "expert": 0.7,
        "nightmare": 0.85,
        "custom": 0.5,
    }

    # 1. Build a high-overlap board
    board_sets = BoardBuilder.build(
        rng=rng,
        board_size_range=board_size_ranges.get(difficulty, (8, 14)),
        overlap_bias=overlap_biases.get(difficulty, 0.5),
    )

    if len(board_sets) < 4:
        return _AttemptOutcome(result=None, rejection_reason="board_too_small")

    # 2. Remove tiles strategically
    removal_result = TileRemover.remove(
        board_sets=board_sets,
        rng=rng,
        rack_size_range=rack_size_ranges.get(difficulty, (3, 6)),
        strategy="maximize_cascade",
        solve_timeout=solve_timeout or 5.0,
    )

    if removal_result is None:
        return _AttemptOutcome(result=None, rejection_reason="removal_failed")

    remaining_board, rack, removal_log = removal_result

    # 3. Final solve verification
    state = BoardState(board_sets=remaining_board, rack=rack)
    effective_timeout = solve_timeout or 8.0
    solution = solve(state, timeout_seconds=effective_timeout)

    if solution.tiles_placed < len(rack):
        return _AttemptOutcome(
            result=None,
            rejection_reason=f"solve_{solution.solve_status}",
            rack_size=len(rack),
            tiles_placed=solution.tiles_placed,
        )

    # 4. Evaluate difficulty
    skip_expensive = difficulty in ("easy", "medium")
    score = DifficultyEvaluator.evaluate(state, solution, skip_expensive=skip_expensive)

    # 5. Check tier match
    if difficulty != "custom" and score.classified_tier != difficulty:
        # Allow adjacent tiers (e.g., generated "hard" accepted for "expert" request
        # if composite score is in the overlap band)
        tier_order = ["easy", "medium", "hard", "expert", "nightmare"]
        requested_idx = tier_order.index(difficulty)
        classified_idx = tier_order.index(score.classified_tier)
        if abs(requested_idx - classified_idx) > 1:
            return _AttemptOutcome(
                result=None,
                rejection_reason="tier_mismatch",
                disruption_score=score.disruption_score,
                chain_depth=score.chain_depth,
            )

    # 6. Uniqueness check for expert/nightmare
    is_unique = True
    if difficulty in ("expert", "nightmare"):
        is_unique = check_uniqueness(state, solution, timeout_seconds=5.0)

    return _AttemptOutcome(
        result=PuzzleResult(
            board_sets=remaining_board,
            rack=rack,
            difficulty=difficulty,
            disruption_score=score.disruption_score,
            chain_depth=score.chain_depth,
            is_unique=is_unique,
            joker_count=0,
            branching_factor=score.branching_factor,
            deductive_depth=score.deductive_depth,
            red_herring_density=score.red_herring_density,
            working_memory_load=score.working_memory_load,
            tile_ambiguity=score.tile_ambiguity,
            solution_fragility=score.solution_fragility,
            composite_score=score.composite_score,
            generator_version="v2.0.0",
        ),
        rack_size=len(rack),
        tiles_placed=solution.tiles_placed,
        disruption_score=score.disruption_score,
        chain_depth=score.chain_depth,
    )
```

**4.2 — Updated `generate_puzzle()` to use v2 by default**

```python
def generate_puzzle(
    difficulty: Difficulty = "medium",
    seed: int | None = None,
    max_attempts: int | None = None,
    generator_version: str = "v2",  # NEW: allows fallback to v1
    # ... existing params for custom mode ...
) -> PuzzleResult:
    rng = random.Random(seed)
    n_attempts = max_attempts or _DEFAULT_MAX_ATTEMPTS_V2.get(difficulty, 100)

    for _ in range(n_attempts):
        if generator_version == "v2":
            outcome = _attempt_generate_v2(rng, difficulty)
        else:
            outcome = _attempt_generate_with_reason(rng, difficulty)  # legacy

        if outcome.result is not None:
            return outcome.result

    raise PuzzleGenerationError(
        f"Could not generate a {difficulty!r} puzzle after {n_attempts} attempts."
    )
```

**4.3 — Update API endpoint**

In `api/main.py`, the `puzzle_endpoint` needs minimal changes since `generate_puzzle()` returns the same `PuzzleResult` type. Add new fields to `PuzzleResponse`:

```python
return PuzzleResponse(
    # ... existing fields ...
    composite_score=result.composite_score,
    branching_factor=result.branching_factor,
    generator_version=result.generator_version,
)
```

**4.4 — Update pregenerate.py worker**

The `_worker_generate_one` function must call the new generator:

```python
def _worker_generate_one(args: tuple[str, int]) -> _WorkerResult:
    difficulty, seed = args
    try:
        outcome = _attempt_generate_v2(
            random.Random(seed),
            difficulty=difficulty,
        )
        return _WorkerResult(
            result=outcome.result,
            rejection_reason=outcome.rejection_reason,
            # ... map other fields ...
        )
    except PuzzleGenerationError:
        return _WorkerResult(result=None, rejection_reason="generation_error")
```

**Files affected:**

- `backend/solver/generator/puzzle_generator.py` (major rewrite of internals)
- `backend/api/main.py` (response construction)
- `backend/api/models.py` (new response fields)
- `backend/solver/generator/pregenerate.py` (worker function)

**Dependencies:** Phases 1-3 complete.

**Risks:**

- **Acceptance rate:** If the new generator’s tier classification doesn’t match the requested difficulty often enough, the retry loop will exhaust attempts. Mitigation: allow adjacent-tier matches in the overlap bands (already implemented above). Also: the attempt limits should be tuned after measuring empirical acceptance rates.
- **Backward compatibility:** The `PuzzleResponse` changes are additive (new optional fields). Frontend code that doesn’t use them is unaffected. The frontend TypeScript types need updating, but since the fields are optional with defaults, old frontends won’t break.
- **Custom mode:** The custom difficulty parameters (sets_to_remove, min_board_sets, etc.) from the old generator don’t map cleanly to the new approach. Decision: custom mode uses the new generator with its own parameter mapping (board_size_range from min/max_board_sets, rack_size from sets_to_remove × 3, overlap_bias derived from min_disruption). Document the mapping clearly.

**Validation criteria:**

- `generate_puzzle("easy")` returns in <2s with composite_score 0-20
- `generate_puzzle("medium")` returns in <2s with composite_score 15-35
- `generate_puzzle("hard")` returns in <3s with composite_score 30-55
- `generate_puzzle("expert")` returns in <10s with composite_score 50-75 (or draws from pool)
- `generate_puzzle("nightmare")` draws from pre-generated pool (composite_score 70-100)
- All generated puzzles pass `solution_verifier.verify_solution()`
- API response includes new fields when generator_version=“v2”
- Pre-generation batch completes at a rate of ≥2 expert puzzles/minute and ≥0.5 nightmare puzzles/minute

**Exit criteria:** Full pipeline produces puzzles across all difficulty tiers, all tests pass, API backward-compatible.

-----

### Phase 5: Testing and Validation (3-4 days)

See Section 7 for the complete testing strategy. This phase implements it.

-----

### Phase 6: Weight Calibration and Difficulty Tuning (2-3 days)

**Objective:** Empirically tune the composite score weights and tier thresholds.

**Tasks:**

1. Generate 200 puzzles per tier using the new generator
1. Manually solve a sample of 10 puzzles per tier, recording solve time
1. Compute all metrics for each puzzle
1. Scatter-plot composite score vs. human solve time
1. Adjust weights if correlation is weak
1. Adjust tier thresholds based on observed difficulty distribution
1. Re-run generation and verify the adjusted thresholds produce better tier separation

-----

### Phase 7: Pre-generation Pool Rebuild (1-2 days)

**Objective:** Generate fresh expert and nightmare puzzle pools using the new generator.

**Tasks:**

1. Clear existing puzzle pool (or mark old puzzles with generator_version=“v1”)
1. Run `pregenerate.py --difficulty expert --count 300 --workers 6`
1. Run `pregenerate.py --difficulty nightmare --count 150 --workers 6`
1. Verify pool statistics: composite scores within tier thresholds
1. Spot-check 5 puzzles per tier by manual solving
1. Deploy updated puzzle DB to production

-----

### Phase 8: Telemetry and Continuous Improvement (ongoing)

See Section 5 for the empirical difficulty framework.

-----

## 4. Exact Proposed Fixes

### Fix 1: Replace sacrifice-based generation with strategic tile removal

**Problem:** Removing entire sets creates trivially reversible puzzles because the removed tiles were a valid set moments ago.

**Fix:** Remove individual tiles from minimum-viable (3-tile) sets, forcing the remaining orphaned tiles to be rearranged into other sets. This creates genuine dependency chains.

**Where:** `puzzle_generator.py` → new `tile_remover.py`

**Replaces:** `_extract_by_sacrifice()`, `_extract_rack()`, `_extract_custom()`, `_sample_rack_from_sacrificed_sets()`

**Tradeoff:** Slower generation (each removal requires a solver call) in exchange for dramatically harder puzzles.

### Fix 2: Replace random board construction with overlap-aware selection

**Problem:** `_pick_compatible_sets()` greedily selects non-overlapping sets, producing boards with few rearrangement possibilities.

**Fix:** Build boards using a tile-overlap graph, favoring sets whose tiles participate in many alternative valid sets. This maximizes the search space for the human solver.

**Where:** `puzzle_generator.py` → new `board_builder.py`

**Replaces:** `_pick_compatible_sets()`, `_make_full_pool()`, `_inject_jokers_into_board()`

**Tradeoff:** Boards may look less “random” and more structurally similar due to overlap bias. Mitigated by the randomness floor in weighted selection.

### Fix 3: Replace single-metric filtering with multi-dimensional scoring

**Problem:** Disruption score and chain depth are poor proxies for human difficulty. High disruption can be trivially obvious; low disruption can hide genuine cognitive challenges.

**Fix:** Compute 8 difficulty metrics and combine them into a weighted composite score. Classify tiers based on the composite, not individual metrics.

**Where:** New `difficulty_evaluator.py`, replacing disruption bands and chain depth thresholds in `puzzle_generator.py`

**Replaces:** `_DISRUPTION_BANDS`, `_MIN_CHAIN_DEPTHS`, and all disruption/chain-depth filtering in `_attempt_generate_with_reason()`

**Tradeoff:** More computation per puzzle (multiple metric calculations). Mitigated by skipping expensive metrics (solution_fragility) for easy/medium puzzles.

### Fix 4: Fix the trivial-extension filter

**Problem:** `_any_trivial_extension()` only checks if a single rack tile can be appended to an existing set. It doesn’t check if the rack tiles can form a completely new valid set among themselves (which is the main failure mode with sacrifice-based generation).

**Fix:** The strategic tile-removal approach eliminates this problem by construction: removed tiles come from different sets and are chosen specifically to NOT be trivially placeable. The old `_any_trivial_extension()` function is deleted.

**Where:** `puzzle_generator.py` — delete the function and its call site

**Replaces:** `_any_trivial_extension()`

**Tradeoff:** None. The new generation approach makes this filter unnecessary.

### Fix 5: Decouple difficulty evaluation from solver output specifics

**Problem:** Chain depth and disruption score are computed from the solver’s output (which set the solver chose to put each tile in). Different tiebreakers in the solver could produce different metrics for the same puzzle.

**Fix:** The new branching_factor and tile_ambiguity metrics are computed from the INPUT state (board + rack), not the solver’s output. They measure the problem’s inherent difficulty, not a property of one particular solution. Disruption and chain depth are retained as minor inputs to the composite but are no longer primary drivers.

**Where:** `difficulty_evaluator.py`

**Replaces:** The reliance on `compute_disruption_score()` and `compute_chain_depth()` as primary difficulty measures

**Tradeoff:** Input-only metrics can’t capture “how much rearrangement is needed” (which requires knowing the solution). Mitigated by keeping disruption and chain depth as secondary inputs.

-----

## 5. Empirical Difficulty Framework

### 5.1 Short-Term: Before Player Data Exists

**Proxy 1: Developer solve-time testing**

Manually solve 10 puzzles per tier. Record:

- Total solve time (seconds)
- Number of backtracks (times you placed a tile and then moved it)
- Number of “stuck” moments (>30s without progress)
- Self-rated difficulty (1-5 scale)

Map these to composite scores. If a “nightmare” puzzle takes you <3 minutes, the scoring is wrong.

**Proxy 2: Solver behavior analysis**

Run the solver with different secondary objectives and compare solutions:

- If the puzzle has multiple structurally different solutions (detected by `check_uniqueness()`), it’s MORE ambiguous but potentially LESS satisfying (no “aha” moment)
- If the solver takes >1s to find the optimal solution, the search space is genuinely large
- If the solver’s branching log shows many candidate evaluations, the ILP had to explore more options

**Proxy 3: Simulated naive solver**

Build a simple greedy solver that tries placements in order (most obvious first) and backtracks when stuck. Measure how many backtracks the greedy solver needs. This approximates human trial-and-error.

```python
def simulate_naive_solve(state: BoardState) -> int:
    """Returns the number of backtracks a greedy solver needs.

    The greedy solver tries placing each rack tile into the first valid
    position it finds. If it gets stuck (a tile has no valid placement),
    it backtracks by undoing the last placement and trying the next option.
    """
    # Implementation: recursive backtracking with a counter
    # This is O(n! * m) in the worst case but typically fast for small racks
    ...
```

Higher backtrack count = harder puzzle for humans.

### 5.2 Long-Term: Data-Driven Difficulty Calibration

**Telemetry to collect (play mode):**

|Event                  |Data                                                |Purpose               |
|-----------------------|----------------------------------------------------|----------------------|
|`puzzle_loaded`        |puzzle_id, difficulty, composite_score, timestamp   |Session start         |
|`tile_placed`          |puzzle_id, tile, position, timestamp                |Placement sequence    |
|`tile_moved`           |puzzle_id, from, to, timestamp                      |Rearrangement behavior|
|`tile_returned_to_rack`|puzzle_id, tile, timestamp                          |Backtracking signal   |
|`undo_pressed`         |puzzle_id, timestamp                                |Backtracking signal   |
|`puzzle_solved`        |puzzle_id, elapsed_ms, move_count, undo_count       |Completion            |
|`puzzle_abandoned`     |puzzle_id, elapsed_ms, tiles_placed, tiles_remaining|Failure signal        |
|`hint_requested`       |puzzle_id, timestamp                                |Stuck signal          |

**Behaviors that indicate difficulty:**

|Behavior                              |Signal  |Meaning                                           |
|--------------------------------------|--------|--------------------------------------------------|
|High undo count relative to moves     |Strong  |Player is backtracking — the puzzle is hard       |
|Long pauses between placements (>20s) |Moderate|Player is thinking — the puzzle requires reasoning|
|tile_returned_to_rack events          |Strong  |Player realized a placement was wrong             |
|puzzle_abandoned after >2 min         |Strong  |Puzzle exceeded player’s ability                  |
|Solve time > 5× median for that tier  |Moderate|Puzzle is harder than peers                       |
|Solve time < 0.5× median for that tier|Moderate|Puzzle is easier than peers                       |

**Distinguishing difficulty from bad UX:**

- If many players abandon puzzles in the FIRST 30 seconds → likely a UX problem (confusing interface, unclear rules), not difficulty
- If players abandon after 2+ minutes of active play → genuine difficulty
- If the same puzzle is abandoned by beginners but solved by experienced players → correctly calibrated difficulty, just too hard for beginners
- Track player “experience level” by number of puzzles solved lifetime; segment difficulty metrics by experience

**Calibration process:**

1. Collect 1000+ solve sessions per tier
1. Compute median solve time and abandonment rate per tier
1. Scatter-plot composite_score vs. median_solve_time: the relationship should be monotonically increasing
1. If the correlation is weak: re-weight the composite score formula using linear regression (solve_time ~ w1·branching + w2·deductive + …)
1. If a metric has near-zero coefficient: it’s not contributing to human difficulty; reduce its weight or remove it
1. Re-generate tier thresholds from the calibrated model

**Continuous improvement loop:**

```
Every 30 days:
  1. Export telemetry for all puzzles solved in the period
  2. Compute actual_difficulty = f(median_solve_time, abandonment_rate, undo_rate)
  3. Compare actual_difficulty vs. composite_score
  4. If correlation < 0.7:
     a. Re-fit composite weights using regression
     b. Re-classify stored puzzles with new weights
     c. Regenerate pre-generated pools
  5. Log the weight changes for audit
```

### 5.3 Implementation Location

- Telemetry events: emitted from the frontend play store (`frontend/src/store/play.ts`) via a new `telemetry.ts` module
- Telemetry backend: new endpoint `POST /api/telemetry` that writes to a separate SQLite table (or sends to an analytics service)
- Calibration script: new `backend/solver/generator/calibrate.py` CLI tool that reads telemetry and outputs updated weights
- Weight storage: `backend/solver/generator/difficulty_evaluator.py` reads weights from a JSON config file (`backend/solver/generator/difficulty_weights.json`) that can be updated without code changes

-----

## 6. Difficulty Metrics and Validation

### 6.1 Metric Definitions and Rationale

|Metric             |What it measures                          |Why it matters                               |Range   |Weight|
|-------------------|------------------------------------------|---------------------------------------------|--------|------|
|branching_factor   |Avg valid placements per rack tile        |More options = harder to find the right one  |1.0-10.0|0.20  |
|deductive_depth    |Chain depth × log2(branching)             |Deep sequential reasoning with ambiguity     |0.0-15.0|0.20  |
|red_herring_density|Fraction of wrong-but-plausible placements|Red herrings waste time and cause backtracks |0.0-1.0 |0.15  |
|working_memory_load|Number of simultaneously disrupted sets   |Humans can hold ~4 chunks in working memory  |0-12    |0.15  |
|tile_ambiguity     |Avg candidate sets per tile               |Measures raw search space size               |1.0-20.0|0.10  |
|solution_fragility |Sensitivity to single-tile removal        |Tight solutions require precision            |0.0-1.0 |0.10  |
|disruption_score   |Board tiles that changed sets (legacy)    |Proxy for physical move count                |0-50    |0.05  |
|chain_depth        |Longest dependency chain (legacy)         |Sequential reasoning (raw, without branching)|0-5     |0.05  |

### 6.2 Metrics to Keep, Change, or Remove

|Metric             |Decision       |Reason                                                                                |
|-------------------|---------------|--------------------------------------------------------------------------------------|
|disruption_score   |KEEP, DOWNGRADE|Still useful as a minor signal but should not drive classification                    |
|chain_depth        |KEEP, DOWNGRADE|Measures sequential depth but ignores branching; augmented by deductive_depth         |
|branching_factor   |ADD            |Directly measures human decision complexity                                           |
|deductive_depth    |ADD            |Combines depth with branching for a more accurate reasoning difficulty estimate       |
|red_herring_density|ADD            |Critical for human difficulty — wrong turns waste the most time                       |
|working_memory_load|ADD            |Captures breadth of simultaneous rearrangement                                        |
|tile_ambiguity     |ADD            |Measures the raw search space                                                         |
|solution_fragility |ADD            |Captures “tightness” — tight solutions require finding the exact arrangement          |
|rack size          |IMPLICIT       |Not an explicit metric but influences all others (more tiles = more everything)       |
|uniqueness         |KEEP           |Important for satisfaction (“I found THE solution”) but not a difficulty metric per se|

### 6.3 Validation Protocol

**Step 1: Sanity checks (automated)**

- branching_factor ≥ 1.0 for all solvable puzzles (if a tile has 0 valid placements, the puzzle is unsolvable)
- red_herring_density ∈ [0, 1]
- working_memory_load ≥ 0
- composite_score ∈ [0, 100]
- Tier classification is monotonically consistent: if puzzle A has composite_score > puzzle B, then tier(A) ≥ tier(B)

**Step 2: Distribution checks (batch)**

- Generate 500 puzzles per tier, plot composite score histograms
- Each tier’s distribution should have minimal overlap with non-adjacent tiers
- Easy and nightmare distributions should have ZERO overlap
- Medium and expert may overlap slightly (acceptable)

**Step 3: Correlation checks (manual + batch)**

- Manually solve 50 puzzles, record solve time
- Compute Pearson/Spearman correlation between composite_score and solve_time
- Target: r ≥ 0.6 (moderate-to-strong positive correlation)
- If r < 0.4: the composite score is a poor difficulty predictor and weights need adjustment

**Step 4: Adversarial checks**

- Intentionally construct puzzles that SHOULD be hard but might score low (e.g., a puzzle with one key insight that unlocks everything — low branching but high “aha” factor)
- Intentionally construct puzzles that SHOULD be easy but might score high (e.g., many tiles but all placements are independent — high branching but no interdependency)
- Verify the evaluator handles these cases reasonably

### 6.4 Avoiding Misleading Metrics

**Failure mode 1: High score, easy puzzle**
A puzzle with many candidate sets (high tile_ambiguity) and many red herrings but where the correct placements are all “obvious” (e.g., each rack tile matches only one color pattern). The high ambiguity is theoretical, not practical.

**Detection:** If solve time is consistently low for high-scoring puzzles, the ambiguity metric is overstated. Mitigation: weight ambiguity lower; add a “practical branching” metric that filters out placements that are obviously wrong (e.g., wrong color).

**Failure mode 2: Low score, hard puzzle**
A puzzle with low branching_factor (each tile has few options) but one critical insight (e.g., you must remove a tile from set A and add it to set B to create room for rack tile C). Low branching means low score, but the insight is hard to find.

**Detection:** If players consistently struggle with low-scoring puzzles. Mitigation: increase the weight of solution_fragility (tight solutions are harder even when branching is low).

**Failure mode 3: Metric gaming**
The generator optimizes for high composite scores, producing puzzles that score well on metrics but feel artificial. Example: boards with extremely high overlap that create huge branching factors but where the human quickly recognizes a pattern.

**Detection:** Manual playtesting. Mitigation: cap individual metrics at their 95th percentile value before computing the composite; this prevents any single metric from dominating.

-----

## 7. Testing Strategy

### 7.1 Unit Tests

**Location:** `backend/tests/generator/`

**New test files:**

|File                          |Tests                                                                           |
|------------------------------|--------------------------------------------------------------------------------|
|`test_board_builder.py`       |Board validity, overlap scoring, size constraints, seed determinism             |
|`test_tile_remover.py`        |Removal correctness, solvability preservation, orphan handling, rack size bounds|
|`test_difficulty_evaluator.py`|Metric computation correctness, composite scoring, tier classification          |
|`test_puzzle_generator_v2.py` |End-to-end generation, tier matching, backward compatibility                    |

**Key unit tests:**

```python
# test_board_builder.py
def test_board_is_valid():
    """Every set in the built board passes is_valid_set()."""

def test_board_has_target_size():
    """Board has between min and max sets."""

def test_high_overlap_boards_have_more_alternatives():
    """Boards built with overlap_bias=0.8 have higher average tile_ambiguity
    than boards built with overlap_bias=0.2."""

def test_deterministic_with_seed():
    """Same seed produces same board."""

def test_no_duplicate_physical_tiles():
    """No (color, number, copy_id) appears in more than one set."""


# test_tile_remover.py
def test_removal_preserves_solvability():
    """After removal, solve(state).tiles_placed == len(rack)."""

def test_removal_produces_target_rack_size():
    """Rack has between min and max tiles."""

def test_broken_sets_create_orphans():
    """At least one set is reduced to <3 tiles for hard+ difficulty."""

def test_board_tiles_not_in_rack():
    """Rack tiles are a subset of the original board tiles, not duplicated."""

def test_removal_log_is_complete():
    """removal_log has one entry per removed tile."""

def test_unsolvable_removal_is_skipped():
    """If removing tile X makes the puzzle unsolvable, X is not removed."""


# test_difficulty_evaluator.py
def test_branching_factor_minimum():
    """branching_factor >= 1.0 for solvable puzzles."""

def test_red_herring_density_bounds():
    """0 <= red_herring_density <= 1."""

def test_composite_score_monotonic():
    """Adding more rack tiles increases composite score."""

def test_easy_puzzle_scores_low():
    """A trivial puzzle (rack=[Red1], board=[Red2,Red3]) scores < 20."""

def test_tier_classification_consistency():
    """If composite_a > composite_b, then tier(a) >= tier(b)."""

def test_skip_expensive_skips_fragility():
    """When skip_expensive=True, solution_fragility is 0.0."""
```

### 7.2 Integration Tests

**Location:** `backend/tests/generator/test_integration.py`

```python
def test_generate_puzzle_v2_easy():
    """generate_puzzle('easy') returns a valid, solvable puzzle with score 0-25."""

def test_generate_puzzle_v2_nightmare():
    """generate_puzzle('nightmare') returns a puzzle with score >= 60."""

def test_api_puzzle_endpoint_returns_new_fields():
    """POST /api/puzzle returns composite_score and generator_version."""

def test_puzzle_store_round_trip_v2():
    """Store and retrieve a v2 puzzle with all new fields."""

def test_pregenerate_worker_produces_v2_puzzles():
    """The pregenerate worker function produces puzzles with generator_version='v2'."""
```

### 7.3 Property-Based Tests (Hypothesis)

```python
from hypothesis import given, strategies as st, settings

@given(seed=st.integers(0, 2**31))
@settings(max_examples=50, deadline=30000)
def test_generated_puzzle_always_solvable(seed):
    """Every generated puzzle, regardless of seed, is solvable by the solver."""
    result = generate_puzzle("medium", seed=seed, max_attempts=5)
    state = BoardState(board_sets=result.board_sets, rack=result.rack)
    solution = solve(state)
    assert solution.tiles_placed == len(result.rack)

@given(seed=st.integers(0, 2**31))
@settings(max_examples=50, deadline=30000)
def test_tile_conservation(seed):
    """Board + rack contain exactly the tiles from the solution."""
    result = generate_puzzle("hard", seed=seed, max_attempts=10)
    state = BoardState(board_sets=result.board_sets, rack=result.rack)
    solution = solve(state)
    assert verify_solution(state, solution)
```

Mark these as `@pytest.mark.slow` since each example runs the solver.

### 7.4 Simulation-Based Tests

```python
def test_difficulty_distribution():
    """Generate 100 puzzles per tier. Verify:
    - Easy: 90%+ have composite_score < 25
    - Medium: 80%+ have composite_score 15-40
    - Hard: 80%+ have composite_score 30-60
    - Expert: 70%+ have composite_score > 45
    - Nightmare: 70%+ have composite_score > 65
    """

def test_no_trivially_solvable_expert_puzzles():
    """Generate 50 expert puzzles. Verify none have branching_factor < 2.0
    AND disruption_score < 5 (which would indicate a trivial puzzle mislabeled as expert)."""
```

Mark as `@pytest.mark.slow`.

### 7.5 Regression Tests

```python
def test_v1_puzzles_still_solvable():
    """Load 10 v1 puzzles from the existing pool and verify the solver still solves them."""

def test_v1_api_response_compatible():
    """v1 puzzles returned via the API don't break the frontend (no missing required fields)."""
```

### 7.6 Performance Tests

```python
def test_easy_generation_under_2s():
    """generate_puzzle('easy') completes in < 2 seconds."""

def test_hard_generation_under_5s():
    """generate_puzzle('hard') completes in < 5 seconds."""

def test_board_builder_under_100ms():
    """BoardBuilder.build() completes in < 100ms."""

def test_difficulty_evaluator_under_500ms():
    """DifficultyEvaluator.evaluate(skip_expensive=True) completes in < 500ms."""
```

### 7.7 Production Monitoring

After rollout:

- Monitor `generate_puzzle()` latency via structured logging (already in place with structlog)
- Alert if error rate for puzzle generation exceeds 5%
- Monitor pre-generation acceptance rate (puzzles_accepted / attempts)
- Log composite_score distribution for generated puzzles; alert if the distribution shifts significantly

-----

## 8. Happy Path, Edge Cases, and Failure Modes

### 8.1 Happy Path

1. User selects “Expert” difficulty, clicks “Get Puzzle”
1. API receives `POST /api/puzzle { difficulty: "expert" }`
1. Endpoint draws from pre-generated pool (fast path)
1. If pool empty: generates live with the new pipeline
1. Returns puzzle with composite_score 50-75, chain_depth 2-4, branching_factor 3-6
1. User solves the puzzle in 5-15 minutes, experiences genuine challenge
1. Play mode tracks undo/redo count, solve time; telemetry confirms the puzzle was appropriately difficult

### 8.2 Edge Cases

|Case                                     |Handling                                                                                                                           |
|-----------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------|
|Empty board (0 sets after building)      |BoardBuilder retries with relaxed overlap_bias; _AttemptOutcome returns “board_too_small”                                          |
|All removals make puzzle unsolvable      |TileRemover returns None; generator retries with a new board                                                                       |
|Puzzle solvable but has composite_score 0|Only possible for trivial boards; filter rejects it unless tier is “easy”                                                          |
|Rack size 1                              |Valid for easy tier; branching_factor is still computed correctly                                                                  |
|Board with jokers                        |Phase 1 of the rebuild does NOT include jokers (n_jokers=0); add joker support in a future phase                                   |
|Custom mode with contradictory params    |(e.g., min_disruption=60, sets_to_remove=1) Generator tries and fails; returns 503 after max attempts                              |
|Two identical puzzles generated          |Extremely unlikely with different seeds but possible; puzzle_id is a UUID, no dedup needed                                         |
|Puzzle where solver times out            |TileRemover uses a short timeout (2-5s) for intermediate checks; final verification uses 8s; puzzle is rejected if solver times out|

### 8.3 Degenerate Puzzle States

|State                                                |Detection                                                                                                                                     |Handling                                                                                                     |
|-----------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------|
|All rack tiles are the same (e.g., 3× Red 5)         |branching_factor would be very high (many candidate sets contain Red 5) but actual difficulty is low (just find 3 sets that each need a Red 5)|red_herring_density distinguishes this: if most placements are wrong, it’s hard; if most are right, it’s easy|
|Board has only groups, rack tiles need runs          |TileRemover would detect this during removal (solver can’t place the tile) and skip that removal                                              |No action needed — just try a different tile                                                                 |
|Rack tiles can only form one new set among themselves|This is the sacrifice-approach failure mode — the new generator avoids it by construction (tiles come from different sets)                    |If detected (via branching_factor < 2 for all rack tiles), reject and retry                                  |
|Solver finds a placement but verification fails      |solution_verifier catches this; raise ValueError (existing behavior)                                                                          |This indicates a solver bug, not a generator bug                                                             |

### 8.4 Bad Content Despite Technical Success

|Situation                                                     |Symptom                                           |Mitigation                                                                                           |
|--------------------------------------------------------------|--------------------------------------------------|-----------------------------------------------------------------------------------------------------|
|Puzzle is solvable but requires no rearrangement              |disruption_score = 0, chain_depth = 0             |DifficultyEvaluator scores it very low; tier filter rejects for hard+                                |
|Puzzle requires rearrangement but the rearrangement is obvious|High disruption but low red_herring_density       |composite_score will be moderate, not high; may still pass for “medium”                              |
|Puzzle has one “trick” tile                                   |Low overall metrics but high subjective difficulty|solution_fragility catches this: removing the trick tile makes the puzzle unsolvable → high fragility|
|Puzzle feels artificial (too structured)                      |No metric captures “naturalness”                  |Mitigated by the randomness in BoardBuilder’s weighted selection                                     |
|Near-duplicate puzzles                                        |Two puzzles with ~90% tile overlap                |Not currently detected; add a dedup check in puzzle_store if needed                                  |

-----

## 9. Engineering Concerns

### 9.1 Maintainability

- Each new module (BoardBuilder, TileRemover, DifficultyEvaluator) has a single responsibility and a clean public interface
- All difficulty weights are in a JSON config file, not hardcoded — tunable without code changes
- The `generator_version` field on every puzzle allows tracing which algorithm produced it
- Comprehensive docstrings on all public functions explain the “why”, not just the “what”

### 9.2 Debuggability

- The `RemovalStep` log captures the full state at each removal step, enabling replay and debugging
- `DifficultyScore` is a frozen dataclass with all metrics visible — easy to print/log/inspect
- structlog is already in place; add structured log entries for each generation step:
  
  ```python
  logger.info("puzzle_generated",
      generator_version="v2",
      difficulty=difficulty,
      composite_score=score.composite_score,
      branching_factor=score.branching_factor,
      board_size=len(remaining_board),
      rack_size=len(rack),
      attempts=attempt_count,
  )
  ```

### 9.3 Reproducibility

- Every generated puzzle is deterministic given a seed: `Random(seed)` is passed through the entire pipeline
- The solver (HiGHS) is deterministic for the same input
- `generator_version` + seed fully specifies the puzzle (assuming the code at that version is available)
- The removal log + seed allows exact replay of the generation process

### 9.4 Seed Handling

- `generate_puzzle()` accepts an optional `seed` parameter
- If `seed` is None, the system uses `int(time.monotonic() * 1000) % (2**31)` (existing behavior)
- The seed is stored in the SQLite pool (`puzzles.seed` column, already exists)
- Pre-generation increments seeds sequentially from a base: `base_seed + attempt_number`

### 9.5 Versioning

- `generator_version` field: `"v1"` = old sacrifice-based, `"v2.0.0"` = new tile-removal
- Stored in SQLite, returned in API responses, logged in telemetry
- Allows A/B comparison of puzzle quality between versions
- Version format: `"v{major}.{minor}.{patch}"` — increment minor for weight changes, major for algorithm changes

### 9.6 Migration Safety

- The old generator is NOT deleted in Phase 4 — it’s preserved behind a `generator_version` parameter
- `generate_puzzle(generator_version="v1")` calls the old code; `"v2"` calls the new code
- Default switches to `"v2"` only after Phase 5 (testing) confirms the new generator is ready
- Pre-generated pools are tagged with version; drawing from the pool only returns puzzles matching the requested version (or any version if not specified)

### 9.7 Rollout Strategy

See Section 11.

### 9.8 Fallback Strategy

If the new generator produces worse puzzles than expected:

1. Switch `generator_version` default back to `"v1"` in `generate_puzzle()` — one-line change
1. Pre-generated pools with v1 puzzles are still available (not deleted)
1. Monitor composite scores and player telemetry to understand what went wrong
1. Fix the issue and re-deploy as v2.1.0

-----

## 10. Bugs, Race Conditions, and Operational Risks

### 10.1 Concurrency: SQLite Writer Contention (puzzle_store.py)

**Risk:** Multiple pre-generation workers write to the same SQLite file simultaneously. SQLite WAL mode handles concurrent reads but serializes writes. With 6+ workers, write contention could cause `sqlite3.OperationalError: database is locked`.

**Current mitigation:** Each worker calls `store.store()` sequentially from the main process (the future results are collected in the main loop). This is correct — workers don’t write directly.

**New risk from Phase 7:** If the pre-generation process is interrupted mid-batch, the SQLite database may have partially committed puzzles with new-format data alongside old-format data. The `generator_version` column prevents confusion.

**Mitigation:** Always use transactions in `puzzle_store.py` (already done via `self.conn.commit()`). Add explicit `BEGIN IMMEDIATE` for the store operation to prevent torn writes.

### 10.2 Performance Collapse: Solver Timeout Cascade (TileRemover)

**Risk:** If the board is complex (many tiles, many candidate sets), each solver call in the removal loop could take close to the timeout. With 6-8 removal steps × 5 candidate retries × 5s timeout = 150-200 seconds per puzzle attempt. This would make pre-generation impossibly slow.

**Mitigation:**

- Use a short timeout (2s) for intermediate removal-step verification
- If a candidate times out, immediately move to the next candidate (don’t wait)
- Add an overall time budget per attempt (e.g., 30s); abort if exceeded
- Log timeout rates; if >20% of removal steps time out, the board is too complex and should be rejected

**Implementation:**

```python
REMOVAL_STEP_TIMEOUT = 2.0
TOTAL_ATTEMPT_TIMEOUT = 30.0

t_start = time.monotonic()
for step in range(target_rack_size):
    if time.monotonic() - t_start > TOTAL_ATTEMPT_TIMEOUT:
        break  # bail out
    ...
    solution = solve(state, timeout_seconds=REMOVAL_STEP_TIMEOUT)
    ...
```

### 10.3 Hidden Coupling: Tile Identity Confusion

**Risk:** The solver uses `id(tile)` for identity in some places (e.g., `board_tile_ids = {id(t) for ...}` in solver.py). The new TileRemover creates new `TileSet` objects with copies of tiles. If tiles are copied (new Python objects), `id()` checks will fail.

**Where:** `solver.py` lines 98-99: `board_tile_ids = {id(t) for ts in solve_state.board_sets for t in ts.tiles}` and line 107: `new_set_tile_ids = {id(t) for ts in new_sets for t in ts.tiles}`.

**Mitigation:** The solver’s `id()` check compares tiles from `solve_state` (input) with tiles from `new_sets` (output). As long as the solver’s internal logic doesn’t copy tile objects (it shouldn’t — it works with indices into `all_tiles`), this is safe. **However:** the TileRemover must ensure that tiles passed to the solver are the SAME Python objects (not copies). Use `ts.tiles` references directly, not `list(ts.tiles)` copies.

**Test:** Add a test that specifically verifies `id()`-based tracking works with TileRemover-produced boards:

```python
def test_solver_tile_identity_with_removed_tiles():
    """Tiles from TileRemover output retain Python object identity through solve()."""
```

### 10.4 State Inconsistency: Orphaned Board Tiles

**Risk:** When TileRemover breaks a 3-tile set, the remaining 2 tiles stay on the board as an invalid “set.” If the solver’s input validation rejects sets with <3 tiles, the solve will fail with a 422 error.

**Analysis:** The solver (`solver.py`) does NOT validate input board sets. It feeds them directly to `enumerate_valid_sets(state)` and `build_ilp_model(state, ...)`. The ILP’s tile conservation constraint requires each board tile to appear in exactly one active set. As long as the candidate sets are enumerated correctly (they are — `enumerate_valid_sets` looks at `state.all_tiles`, not individual sets), the solver will find valid placements for orphaned tiles.

**Test:** Add a test with a deliberately invalid input board (sets with 1-2 tiles):

```python
def test_solver_handles_orphaned_tiles():
    """Solver produces a valid solution even when input board has sub-3-tile 'sets'."""
    state = BoardState(
        board_sets=[
            TileSet(type=SetType.RUN, tiles=[Tile(Color.RED, 5, 0)]),  # 1-tile "set"
            TileSet(type=SetType.RUN, tiles=[Tile(Color.RED, 6, 0), Tile(Color.RED, 7, 0)]),  # 2-tile "set"
        ],
        rack=[Tile(Color.RED, 4, 0), Tile(Color.RED, 8, 0)],
    )
    solution = solve(state)
    assert solution.tiles_placed == 2
    assert verify_solution(state, solution)
```

### 10.5 Caching: Stale Template Enumeration

**Risk:** TileRemover calls `enumerate_valid_sets()` after each removal step to update the candidate set list. If this call is expensive (~5ms per call × 8 steps = 40ms — negligible) there’s no caching concern. But if someone adds a cache (e.g., `@functools.lru_cache`), the cache key must account for the changing board state.

**Mitigation:** Do not cache `enumerate_valid_sets()` in the TileRemover path. The function is cheap enough to call repeatedly.

### 10.6 Floating Point: Composite Score Boundary Effects

**Risk:** The composite score is a weighted sum of normalized floats. Tier boundaries (e.g., 30.0 for hard) could cause flapping: a puzzle that scores 29.99 is classified as “medium” while 30.01 is “hard.” Minor floating-point differences across platforms could cause different classifications.

**Mitigation:** Use a hysteresis band: accept puzzles within ±2 points of the boundary for adjacent tiers. The existing code already allows adjacent-tier matches (Phase 4, task 4.1).

### 10.7 Memory: Removal Log Growth

**Risk:** The `RemovalStep` dataclass stores `state_before: BoardState` for each removal step. For a 8-step removal, this means 8 copies of the board state. Each board state has ~50 tiles × ~12 sets = ~600 tile objects. Negligible in memory but worth noting.

**Mitigation:** For pre-generation, the removal log can be dropped after the puzzle is accepted. For debugging, it’s valuable to keep.

-----

## 11. Rollout and Transition Plan

### 11.1 Phase-Gated Rollout

|Gate          |Condition                                                       |Action                                              |
|--------------|----------------------------------------------------------------|----------------------------------------------------|
|Dev Gate      |All unit + integration tests pass                               |Merge to main, deploy to staging                    |
|Quality Gate  |Manual playtest of 20 puzzles per tier confirms difficulty      |Enable v2 generator in production with v1 fallback  |
|Pool Gate     |Pre-generated expert (200+) and nightmare (100+) pools populated|Switch default to v2 for pool-drawn tiers           |
|Telemetry Gate|7 days of production data shows no regression in solve rates    |Remove v1 fallback code (deferred; keep for 30 days)|

### 11.2 Parallel Running

During the transition period:

1. **API behavior:** `POST /api/puzzle` uses v2 by default. If v2 fails (max attempts exceeded), falls back to v1 transparently. Log which version was used.
1. **Pre-generated pool:** v1 and v2 puzzles coexist in the same SQLite database, distinguished by `generator_version`. Pool draw prefers v2; if no v2 puzzles available for the requested tier, falls back to v1.
1. **Frontend:** No changes needed — the API response is backward-compatible. The new `composite_score`, `branching_factor`, and `generator_version` fields are optional and can be displayed in a “stats badge” when present.

### 11.3 Migration of Existing Puzzles

Existing v1 puzzles in the SQLite pool:

- **Do not delete them.** They serve as fallback if v2 pool is empty.
- **Do not re-score them** with the new DifficultyEvaluator — their difficulty classification stays as-is.
- **Mark them** with `generator_version='v1'` (already done via schema migration in Phase 0).
- **Gradually replace:** As v2 puzzles are generated and added to the pool, v1 puzzles will naturally become the minority. After 90 days, consider pruning v1 puzzles from the pool.

### 11.4 Rollback Plan

If v2 puzzles receive negative player feedback (too hard, too easy, or feel artificial):

1. **Immediate:** Set `generator_version` default to `"v1"` in `puzzle_generator.py` (one-line change, no deployment needed if using environment variables)
1. **Short-term:** Disable v2 in the pool draw logic (only draw v1 puzzles)
1. **Investigation:** Compare telemetry for v1 vs. v2 puzzles: solve times, abandonment rates, undo counts
1. **Fix forward:** Adjust weights or algorithm, deploy as v2.1.0

### 11.5 Quality Thresholds for Release

v2 is released to production only if:

- ≥95% of generated puzzles pass solution verification
- Easy puzzles solve in <1 minute by the developer
- Medium puzzles solve in 1-3 minutes
- Hard puzzles solve in 3-8 minutes
- Expert puzzles solve in 5-15 minutes
- Nightmare puzzles take >10 minutes to solve (or the developer gives up)
- Pre-generation acceptance rate ≥ 5% for expert and ≥ 1% for nightmare (vs. current <0.5% for nightmare with the old system)
- No regression in API latency for easy/medium/hard (still <2s)

-----

## Appendix A: File Inventory

### New Files

|File                                                  |Module                    |Lines (est.)|
|------------------------------------------------------|--------------------------|------------|
|`backend/solver/generator/board_builder.py`           |BoardBuilder              |150-200     |
|`backend/solver/generator/tile_remover.py`            |TileRemover               |250-350     |
|`backend/solver/generator/difficulty_evaluator.py`    |DifficultyEvaluator       |300-400     |
|`backend/solver/generator/tile_pool.py`               |Shared tile pool utilities|50-80       |
|`backend/solver/generator/difficulty_weights.json`    |Weight config             |15-20       |
|`backend/tests/generator/test_board_builder.py`       |Tests                     |150-200     |
|`backend/tests/generator/test_tile_remover.py`        |Tests                     |200-300     |
|`backend/tests/generator/test_difficulty_evaluator.py`|Tests                     |200-300     |
|`backend/tests/generator/test_puzzle_generator_v2.py` |Integration tests         |150-200     |

### Modified Files

|File                                          |Changes                                                                                    |
|----------------------------------------------|-------------------------------------------------------------------------------------------|
|`backend/solver/generator/puzzle_generator.py`|New `_attempt_generate_v2()`, updated `generate_puzzle()`, deleted old extraction functions|
|`backend/solver/generator/puzzle_store.py`    |Schema migration, new fields in store/retrieve                                             |
|`backend/solver/generator/pregenerate.py`     |Worker function updated to call v2                                                         |
|`backend/api/models.py`                       |New fields on PuzzleResponse                                                               |
|`backend/api/main.py`                         |Pass new fields to response                                                                |
|`frontend/src/types/api.ts`                   |New optional fields on PuzzleResponse                                                      |

### Deleted Code (within modified files)

- `_pick_compatible_sets()` — replaced by BoardBuilder
- `_extract_by_sacrifice()` — replaced by TileRemover
- `_extract_rack()` — replaced by TileRemover
- `_extract_custom()` — replaced by TileRemover with custom params
- `_sample_rack_from_sacrificed_sets()` — deleted
- `_any_trivial_extension()` — unnecessary with new approach
- `_build_rack_candidate()` / `_better_rack_candidate()` — deleted
- `_estimate_complexity()` — replaced by DifficultyEvaluator
- `_inject_jokers_into_board()` — deferred to future phase
- `_SACRIFICE_COUNTS`, `_DISRUPTION_BANDS`, `_BOARD_SIZES`, `_MIN_CHAIN_DEPTHS`, `_PREGEN_PROFILES`, `_PREGEN_CONSTRAINTS` — replaced by new difficulty parameters

-----

## Appendix B: Estimated Timeline

|Phase                         |Duration|Cumulative|
|------------------------------|--------|----------|
|Phase 0: Preparation          |2-3 days|2-3 days  |
|Phase 1: BoardBuilder         |3-5 days|5-8 days  |
|Phase 2: TileRemover          |5-8 days|10-16 days|
|Phase 3: DifficultyEvaluator  |4-6 days|14-22 days|
|Phase 4: Generator Integration|3-4 days|17-26 days|
|Phase 5: Testing & Validation |3-4 days|20-30 days|
|Phase 6: Weight Calibration   |2-3 days|22-33 days|
|Phase 7: Pool Rebuild         |1-2 days|23-35 days|

**Total estimated effort: 23-35 developer-days**

This includes implementation, testing, and initial calibration. Ongoing telemetry and weight refinement (Phase 8) is continuous and not included in the estimate.