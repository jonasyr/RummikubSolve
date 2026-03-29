# Puzzle Difficulty Overhaul — Implementation Plan

**Date:** 2026-03-29
**Scope:** Complete rework of puzzle generation difficulty system
**Goal:** Make Expert/Nightmare puzzles genuinely challenging for advanced players (target: 10–20+ minutes solve time for a skilled human)

-----

## 1. Problem Analysis

### Current System

The existing puzzle generator (`backend/solver/generator/puzzle_generator.py`) uses a single strategy for all difficulties:

1. Build a random board of 5–18 compatible sets (varies by difficulty)
1. Sacrifice N complete sets — remove them entirely from the board
1. Sample M tiles from the sacrificed sets as the rack
1. Verify solvability via `solve(board, rack)`
1. Compute `disruption_score` and check it falls in the difficulty band

### Why Expert Is Too Easy

|Problem                           |Detail                                                                                                                                                         |
|----------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|
|**Too few rack tiles**            |Expert gives 4–6 tiles. A skilled player mentally tracks these trivially.                                                                                      |
|**Shallow rearrangement**         |Disruption score counts *how many* tiles move, not *how deeply nested* the rearrangement chain is. A score of 30 can mean 30 tiles making obvious 1-step moves.|
|**No chain dependencies**         |The generator never validates that the solution *requires* multi-step cascading rearrangements (break Set A to fix Set B to enable Set C).                     |
|**No uniqueness constraint**      |Multiple valid solutions exist → player finds *any* solution quickly via pattern matching instead of needing to find *the* solution.                           |
|**No jokers**                     |Joker-free boards eliminate an entire axis of complexity (tracking substitutions).                                                                             |
|**Direct rack-board relationship**|Rack tiles come from sacrificed sets, so they visually “belong” to recognizable patterns on the board.                                                         |

### Current Difficulty Constants

```python
# puzzle_generator.py — current values
_RACK_SIZES = {"easy": (2,3), "medium": (3,4), "hard": (4,5), "expert": (4,6)}
_SACRIFICE_COUNTS = {"easy": 1, "medium": 2, "hard": 3, "expert": 5}
_DISRUPTION_BANDS = {"easy": (2,10), "medium": (9,18), "hard": (16,28), "expert": (29,None)}
_BOARD_SIZES = {"easy": (5,9), "medium": (7,11), "hard": (9,13), "expert": (13,18)}
```

-----

## 2. New Difficulty Architecture

### 2.1 Core New Metric: Chain Depth

**Chain depth** measures how many sequential rearrangement dependencies the solution requires. This is the single most important metric for perceived difficulty.

**Definition:**

Build a dependency graph from the solver’s solution:

- For each move M_i that takes tiles from an existing board set S_j, draw an edge S_j → M_i
- If M_i also contributes tiles to enable another move M_k (because M_i creates a set that M_k then modifies), draw an edge M_i → M_k
- The **chain depth** is the length of the longest path in this DAG

**Example:**

- Chain depth 1: Take rack tile, place directly into a new set (trivial)
- Chain depth 2: Break Set A to free tiles, use those + rack tile to form Set B
- Chain depth 3: Break Set A → rebuild tiles into Set B → which frees a slot in Set C → rack tile goes into Set C
- Chain depth 4+: Each additional level requires the player to mentally simulate one more “what if I move this” step

**Implementation approach:**

```python
def compute_chain_depth(
    old_board_sets: list[TileSet],
    new_board_sets: list[TileSet],
    placed_tiles: list[Tile],
) -> int:
    """
    Compute the longest dependency chain in a solution.

    Algorithm:
    1. For each old board set, determine which new set(s) its tiles ended up in
       (using content-based matching like disruption_score).
    2. Build a directed graph:
       - Node = each new set in the solution
       - Edge A → B if set B contains tiles that were originally in the same
         old set as tiles that were REMOVED from that old set to form set A.
       - In other words: if forming set A required breaking an old set, and
         the "leftover" tiles from that break ended up needing to go into
         set B (which itself may be a new configuration), then A depends on B.
    3. Find the longest path in the DAG (topological sort + DP).

    Returns 0 if no rearrangement occurred (pure placement).
    """
```

The key insight: we trace WHERE each tile came from (which old set) and WHERE it went (which new set). If old set O got split across new sets N1 and N2, and N2 also contains tiles from old set P (which itself was disrupted), that’s a chain.

### 2.2 New Difficulty Levels

Replace the current 4-level system with a redesigned 4-level system plus a new “nightmare” tier:

|Level        |Rack Size|Board Sets|Min Chain Depth|Disruption Floor|Jokers        |Unique Solution|Target Solve Time|
|-------------|---------|----------|---------------|----------------|--------------|---------------|-----------------|
|**Easy**     |2–3      |5–8       |0              |2               |No            |No             |< 30 seconds     |
|**Medium**   |3–5      |7–11      |1              |8               |No            |No             |1–3 minutes      |
|**Hard**     |5–8      |10–15     |2              |15              |Optional (0–1)|No             |3–8 minutes      |
|**Expert**   |8–12     |15–22     |3              |25              |1–2           |Preferred      |8–15 minutes     |
|**Nightmare**|10–14    |20–28     |4+             |35+             |1–2           |Required       |15–30+ minutes   |

### 2.3 Uniqueness Constraint

For Expert (preferred) and Nightmare (required), verify the solution is unique:

```python
def is_unique_optimal(state: BoardState, expected_placed: int) -> bool:
    """
    After finding the optimal solution that places N tiles, check whether
    a DIFFERENT arrangement also places N tiles.

    Method:
    1. Solve normally → get solution S1 with tiles_placed = N
    2. Add a constraint to the ILP that EXCLUDES S1's exact set of
       active y-variables (i.e., at least one y[s] must differ)
    3. Re-solve → if new solution also places N tiles, it's NOT unique
    4. Return True only if re-solve places fewer tiles or is infeasible

    Cost: doubles the solve time. For pre-generated puzzles this is fine.
    """
```

**ILP encoding for exclusion constraint:**
Given the first solution activated sets S = {s1, s2, …, sk}, add:

```
Σ_{s ∈ S} y[s] ≤ k - 1
```

This forces at least one currently-active set to become inactive, producing a structurally different solution.

### 2.4 Joker Integration

Currently `_make_full_pool()` creates 104 joker-free tiles. For Hard/Expert/Nightmare:

1. Include 1–2 jokers in the initial tile pool
1. Allow jokers to appear in board sets (the set enumerator already handles this)
1. Jokers on the board create mental complexity: the player must deduce what tile the joker represents and whether freeing it enables better placements

### 2.5 Red Herring Scoring

Score how many “almost valid” placements exist — rack tiles that *look like* they could go somewhere but actually can’t in the optimal solution:

```python
def compute_red_herring_score(
    board_sets: list[TileSet],
    rack: list[Tile],
    solution_placed_mapping: dict,  # tile → which new set it ended up in
) -> int:
    """
    Count how many (rack_tile, board_set) pairs satisfy:
    - The rack tile's color/number matches an extension pattern of the board set
    - But in the optimal solution, that tile goes ELSEWHERE

    Higher score = more false leads for the human player.
    """
```

-----

## 3. Pre-Generation & Persistence System

### 3.1 Why Pre-Generation Is Necessary

Nightmare puzzles may require:

- 50–500 generation attempts (chain depth 4+ is rare)
- Uniqueness check doubles each attempt’s cost
- Total: 5–60 seconds per puzzle vs. current ~100ms

This is unacceptable for a synchronous API request. Solution: pre-generate a pool of certified puzzles.

### 3.2 Architecture

```
┌─────────────────────────────────────────────┐
│             Pre-Generation CLI              │
│  python -m solver.generator.pregenerate     │
│  --difficulty nightmare --count 200         │
│                                             │
│  Runs offline (cron / manual / CI)          │
│  Writes to SQLite: puzzles.db              │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│          puzzles.db (SQLite)                │
│                                             │
│  puzzles(                                   │
│    id          TEXT PRIMARY KEY,  -- UUID    │
│    difficulty  TEXT NOT NULL,                │
│    board_json  TEXT NOT NULL,                │
│    rack_json   TEXT NOT NULL,                │
│    chain_depth INT NOT NULL,                 │
│    disruption  INT NOT NULL,                 │
│    rack_size   INT NOT NULL,                 │
│    board_size  INT NOT NULL,                 │
│    is_unique   BOOLEAN NOT NULL,             │
│    joker_count INT NOT NULL DEFAULT 0,       │
│    seed        INT,                          │
│    created_at  TEXT NOT NULL,                │
│  )                                          │
│                                             │
│  CREATE INDEX idx_difficulty                 │
│    ON puzzles(difficulty);                   │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│         POST /api/puzzle                    │
│                                             │
│  if difficulty in ("expert", "nightmare"):  │
│    → draw from puzzles.db pool              │
│    → exclude IDs in request.seen_ids        │
│  else:                                      │
│    → generate live (current behaviour)      │
│                                             │
│  Response includes puzzle_id for tracking   │
└─────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│         Frontend (localStorage)             │
│                                             │
│  Stores seen puzzle IDs per difficulty      │
│  Sends seen_ids[] with puzzle requests      │
│  Prevents duplicate puzzles for same user   │
└─────────────────────────────────────────────┘
```

### 3.3 Database Location

For Docker deployment: mount `puzzles.db` as a Docker volume so it persists across container restarts.

```yaml
# docker-compose.yml addition
backend:
  volumes:
    - puzzle-data:/app/data

volumes:
  puzzle-data:
```

The DB path is configured via env var `PUZZLE_DB_PATH` (default: `./data/puzzles.db`).

### 3.4 Seen-Puzzle Tracking

The frontend stores seen puzzle IDs in localStorage:

```typescript
// store/game.ts or a dedicated puzzle tracking module
const SEEN_KEY = "rummikub_seen_puzzles";

function getSeenIds(): string[] {
  const raw = localStorage.getItem(SEEN_KEY);
  return raw ? JSON.parse(raw) : [];
}

function markSeen(id: string): void {
  const seen = getSeenIds();
  seen.push(id);
  // Keep last 500 to avoid unbounded growth
  if (seen.length > 500) seen.splice(0, seen.length - 500);
  localStorage.setItem(SEEN_KEY, JSON.stringify(seen));
}
```

-----

## 4. File-by-File Implementation Plan

### Phase 1: Chain Depth Metric (Foundation)

#### File: `backend/solver/engine/objective.py`

**Change:** Add `compute_chain_depth()` function alongside existing `compute_disruption_score()`.

**Implementation:**

```python
def compute_chain_depth(
    old_board_sets: list[TileSet],
    new_board_sets: list[TileSet],
    placed_tiles: list[Tile],
) -> int:
    """Compute the longest dependency chain in a solution.

    The chain depth measures how many sequential rearrangement steps
    a player must mentally simulate to find the solution.

    Algorithm:
    1. Map each tile to its old set index and new set index.
    2. Build a DAG of set dependencies:
       - For each old set that was disrupted (tiles split across
         multiple new sets), identify which new sets received its tiles.
       - If new set N contains tiles from 2+ different old sets,
         it required combining tiles from multiple sources — each
         source is a dependency.
    3. Chain depth = longest path in the dependency DAG.

    Returns:
        0 = pure placement (no rearrangement)
        1 = simple rearrangement (break one set, reform)
        2 = two-step chain (break A to form B, enabling C)
        3+ = deep chains (expert-level)
    """
    if not old_board_sets or not new_board_sets:
        return 0

    # Step 1: Map each tile key to its old set index
    old_membership: dict[tuple, int] = {}
    for oi, ts in enumerate(old_board_sets):
        for tile in ts.tiles:
            old_membership[_tile_key(tile)] = oi

    # Step 2: Map each tile key to its new set index
    new_membership: dict[tuple, int] = {}
    for ni, ts in enumerate(new_board_sets):
        for tile in ts.tiles:
            new_membership[_tile_key(tile)] = ni

    # Step 3: For each new set, determine which old sets contributed tiles
    # and which tiles are from the rack (placed_tiles)
    placed_keys = {_tile_key(t) for t in placed_tiles}
    n_new = len(new_board_sets)

    # new_set_sources[ni] = set of old set indices that contributed board tiles
    new_set_sources: list[set[int]] = [set() for _ in range(n_new)]
    for ni, ts in enumerate(new_board_sets):
        for tile in ts.tiles:
            key = _tile_key(tile)
            if key not in placed_keys and key in old_membership:
                new_set_sources[ni].add(old_membership[key])

    # Step 4: Identify disrupted old sets (tiles went to multiple new sets)
    # old_set_destinations[oi] = set of new set indices that received its tiles
    n_old = len(old_board_sets)
    old_set_destinations: list[set[int]] = [set() for _ in range(n_old)]
    for ni, ts in enumerate(new_board_sets):
        for tile in ts.tiles:
            key = _tile_key(tile)
            if key in old_membership:
                old_set_destinations[old_membership[key]].add(ni)

    disrupted_old = {
        oi for oi in range(n_old) if len(old_set_destinations[oi]) > 1
    }

    # Step 5: Build dependency DAG among new sets
    # New set A depends on new set B if:
    #   A received tiles from a disrupted old set O, AND
    #   B also received tiles from O (they share a broken source)
    #   AND A != B
    # This means forming A required breaking O, which also affected B.
    from collections import defaultdict
    adj: dict[int, set[int]] = defaultdict(set)

    for oi in disrupted_old:
        dests = list(old_set_destinations[oi])
        # The set that got the MOST tiles from this old set is the "inheritor";
        # other sets that got tiles from it are dependents
        tile_counts: dict[int, int] = {}
        for ni in dests:
            count = sum(
                1 for tile in new_board_sets[ni].tiles
                if _tile_key(tile) in old_membership
                and old_membership[_tile_key(tile)] == oi
            )
            tile_counts[ni] = count
        # Inheritor = got the most tiles (keeps the "core" of the old set)
        inheritor = max(tile_counts, key=lambda ni: tile_counts[ni])
        # Dependents: other new sets that needed tiles from this disrupted source
        for ni in dests:
            if ni != inheritor:
                # ni depends on breaking old set oi, which also feeds inheritor
                adj[inheritor].add(ni)

    # Also: if a new set contains rack tiles AND board tiles from a disrupted
    # old set, the rack placement depends on the rearrangement
    for ni, ts in enumerate(new_board_sets):
        has_rack = any(_tile_key(t) in placed_keys for t in ts.tiles)
        if has_rack and new_set_sources[ni] & disrupted_old:
            # This new set combines rack tiles with tiles freed by disruption
            for source_oi in new_set_sources[ni] & disrupted_old:
                for other_ni in old_set_destinations[source_oi]:
                    if other_ni != ni:
                        adj[other_ni].add(ni)

    # Step 6: Longest path in DAG (topological sort + DP)
    if not adj:
        return 1 if disrupted_old else 0

    # BFS/DFS longest path
    all_nodes = set(adj.keys())
    for targets in adj.values():
        all_nodes |= targets

    memo: dict[int, int] = {}

    def longest_from(node: int) -> int:
        if node in memo:
            return memo[node]
        if node not in adj or not adj[node]:
            memo[node] = 0
            return 0
        best = 0
        for nxt in adj[node]:
            best = max(best, 1 + longest_from(nxt))
        memo[node] = best
        return best

    depth = max(longest_from(n) for n in all_nodes) + 1
    return depth
```

**Tests to add:** `tests/solver/test_objective.py`

- `test_chain_depth_pure_placement` → depth 0 (rack tiles form new set, board untouched)
- `test_chain_depth_simple_rearrange` → depth 1 (one set broken and reformed)
- `test_chain_depth_two_step` → depth 2 (A broken → B reformed → enables C)
- `test_chain_depth_three_step` → depth 3 (A → B → C → D chain)
- `test_chain_depth_no_disruption` → depth 0 (extend existing set)

-----

#### File: `backend/solver/engine/solver.py`

**Change:** Return chain depth in the Solution dataclass.

**Proposed changes:**

- After `generate_moves()`, call `compute_chain_depth(state.board_sets, new_sets, placed_tiles)`
- Store the result — either add a field to `Solution` or return it alongside

-----

#### File: `backend/solver/models/board_state.py`

**Change:** Add `chain_depth: int = 0` field to `Solution` dataclass.

```python
@dataclass
class Solution:
    new_sets: list[TileSet]
    placed_tiles: list[Tile]
    remaining_rack: list[Tile]
    moves: list[MoveInstruction] = field(default_factory=list)
    is_optimal: bool = False
    solve_time_ms: float = 0.0
    chain_depth: int = 0  # NEW
```

-----

### Phase 2: Uniqueness Check

#### File: `backend/solver/engine/ilp_formulation.py`

**Change:** Add `exclusion_constraints` parameter to `build_ilp_model()`.

```python
def build_ilp_model(
    state: BoardState,
    candidate_sets: list[TileSet],
    rules: RulesConfig,
    secondary_objective: Literal["tile_value", "disruption"] = "tile_value",
    excluded_solutions: list[list[int]] | None = None,  # NEW
) -> ILPModel:
    """
    ...
    excluded_solutions: List of previously-found solutions to exclude.
        Each entry is a list of candidate-set indices that were active
        (y[s] = 1) in a prior solution. For each entry, an exclusion
        constraint is added:  Σ_{s ∈ active} y[s] ≤ len(active) - 1
    """
    ...
    # After all other constraints:
    if excluded_solutions:
        for active_indices in excluded_solutions:
            cols = [y_vars[s] for s in active_indices]
            coefs = [1.0] * len(cols)
            ub = float(len(active_indices) - 1)
            highs.addRow(-1e30, ub, len(cols), cols, coefs)
    ...
```

#### File: `backend/solver/engine/solver.py`

**Change:** Add `check_uniqueness()` helper function.

```python
def check_uniqueness(
    state: BoardState,
    first_solution: Solution,
    candidate_sets: list[TileSet],
    rules: RulesConfig,
) -> bool:
    """Return True if first_solution is the ONLY optimal solution.

    Re-solves the ILP with the first solution's active sets excluded.
    If the re-solve places fewer tiles, the original is unique.
    """
    # Identify which candidate set indices were active in the first solution
    active_indices = _find_active_set_indices(first_solution, candidate_sets)

    model2 = build_ilp_model(
        state, candidate_sets, rules,
        excluded_solutions=[active_indices],
    )
    model2.highs.setOptionValue("time_limit", 10.0)  # shorter timeout for check
    model2.highs.run()

    try:
        _, placed2, _, _ = extract_solution(model2)
        return len(placed2) < first_solution.tiles_placed
    except ValueError:
        return True  # Infeasible = no alternative solution exists
```

-----

### Phase 3: Rework Puzzle Generator

#### File: `backend/solver/generator/puzzle_generator.py`

**Major rewrite.** Here’s the proposed new structure:

##### 3a. New constants

```python
# Rack size range per difficulty
_RACK_SIZES: dict[str, tuple[int, int]] = {
    "easy":      (2, 3),
    "medium":    (3, 5),
    "hard":      (5, 8),
    "expert":    (8, 12),
    "nightmare": (10, 14),
    "custom":    (2, 14),  # determined by sets_to_remove
}

# Board size (number of sets BEFORE sacrifice)
_BOARD_SIZES: dict[str, tuple[int, int]] = {
    "easy":      (5, 8),
    "medium":    (7, 11),
    "hard":      (10, 15),
    "expert":    (15, 22),
    "nightmare": (20, 28),
    "custom":    (5, 15),
}

# Number of sets sacrificed
_SACRIFICE_COUNTS: dict[str, tuple[int, int]] = {
    "easy":      (1, 1),
    "medium":    (1, 2),
    "hard":      (2, 3),
    "expert":    (3, 5),
    "nightmare": (4, 6),
}

# Minimum chain depth required
_MIN_CHAIN_DEPTH: dict[str, int] = {
    "easy":      0,
    "medium":    1,
    "hard":      2,
    "expert":    3,
    "nightmare": 4,
}

# Disruption score floor
_MIN_DISRUPTION: dict[str, int] = {
    "easy":      2,
    "medium":    8,
    "hard":      15,
    "expert":    25,
    "nightmare": 35,
}

# Whether jokers are included in the tile pool
_JOKER_COUNTS: dict[str, tuple[int, int]] = {
    "easy":      (0, 0),
    "medium":    (0, 0),
    "hard":      (0, 1),
    "expert":    (1, 2),
    "nightmare": (1, 2),
}

# Whether uniqueness is checked
_REQUIRE_UNIQUE: dict[str, str] = {
    "easy":      "no",
    "medium":    "no",
    "hard":      "no",
    "expert":    "preferred",   # try but don't require
    "nightmare": "required",    # must be unique
}

# Max generation attempts
_MAX_ATTEMPTS: dict[str, int] = {
    "easy":      100,
    "medium":    150,
    "hard":      200,
    "expert":    300,
    "nightmare": 500,
}
```

##### 3b. New generation algorithm

```python
def _attempt_generate(rng, difficulty, sets_to_remove=3) -> PuzzleResult | None:
    # 1. Create tile pool (with or without jokers)
    joker_lo, joker_hi = _JOKER_COUNTS.get(difficulty, (0, 0))
    n_jokers = rng.randint(joker_lo, joker_hi)
    pool = _make_pool(n_jokers)

    # 2. Enumerate and select board sets
    lo, hi = _BOARD_SIZES[difficulty]
    n_target = rng.randint(lo, hi)
    board_sets = _pick_compatible_sets_from_pool(pool, n_target, rng)
    if len(board_sets) < 4:
        return None

    board_sets = _assign_copy_ids(board_sets)

    # 3. Extract rack by sacrifice (with variable sacrifice count)
    sac_lo, sac_hi = _SACRIFICE_COUNTS.get(difficulty, (1, 3))
    n_sacrifice = rng.randint(sac_lo, sac_hi)
    rack_lo, rack_hi = _RACK_SIZES[difficulty]

    input_board, rack = _extract_by_sacrifice(
        board_sets, rng, n_sacrifice, (rack_lo, rack_hi)
    )
    if len(rack) < rack_lo:
        return None

    # 4. Verify solvability
    state = BoardState(board_sets=input_board, rack=rack)
    solution = solve(state, rules=None)
    if solution.tiles_placed < len(rack):
        return None

    # 5. Compute metrics
    disruption = compute_disruption_score(input_board, solution.new_sets)
    chain = compute_chain_depth(input_board, solution.new_sets, solution.placed_tiles)

    # 6. Validate against difficulty thresholds
    if disruption < _MIN_DISRUPTION.get(difficulty, 0):
        return None
    if chain < _MIN_CHAIN_DEPTH.get(difficulty, 0):
        return None

    # 7. Uniqueness check (for expert/nightmare)
    unique_req = _REQUIRE_UNIQUE.get(difficulty, "no")
    is_unique = False
    if unique_req != "no":
        candidate_sets = enumerate_valid_sets(state)
        is_unique = check_uniqueness(state, solution, candidate_sets, RulesConfig())
        if unique_req == "required" and not is_unique:
            return None

    # 8. Reject trivially-extensible puzzles (existing check)
    if difficulty != "custom" and _any_trivial_extension(rack, input_board):
        return None

    return PuzzleResult(
        board_sets=input_board,
        rack=rack,
        difficulty=difficulty,
        disruption_score=disruption,
        chain_depth=chain,
        is_unique=is_unique,
        joker_count=n_jokers,
    )
```

##### 3c. Updated `_make_pool()` (replaces `_make_full_pool()`)

```python
def _make_pool(n_jokers: int = 0) -> BoardState:
    """104 non-joker tiles + n_jokers joker tiles."""
    tiles: list[Tile] = [
        Tile(color, n, copy_id)
        for color in Color
        for n in range(1, 14)
        for copy_id in (0, 1)
    ]
    for j in range(n_jokers):
        tiles.append(Tile.joker(copy_id=j))
    return BoardState(board_sets=[], rack=tiles)
```

##### 3d. Updated `PuzzleResult`

```python
@dataclass
class PuzzleResult:
    board_sets: list[TileSet]
    rack: list[Tile]
    difficulty: Difficulty
    disruption_score: int
    chain_depth: int = 0        # NEW
    is_unique: bool = False     # NEW
    joker_count: int = 0        # NEW
    puzzle_id: str = ""         # NEW — UUID for pre-generated, empty for live
```

-----

### Phase 4: Pre-Generation System

#### New file: `backend/solver/generator/puzzle_store.py`

```python
"""SQLite-based storage for pre-generated puzzles.

Puzzles are stored with full metadata so the API can filter by
difficulty, exclude already-seen puzzles, and return puzzle IDs
for client-side tracking.
"""
import json
import sqlite3
import uuid
from pathlib import Path
from dataclasses import asdict

from .puzzle_generator import PuzzleResult
from ..models.tile import Tile, Color
from ..models.tileset import TileSet, SetType

DEFAULT_DB_PATH = Path("data/puzzles.db")

class PuzzleStore:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS puzzles (
                id          TEXT PRIMARY KEY,
                difficulty  TEXT NOT NULL,
                board_json  TEXT NOT NULL,
                rack_json   TEXT NOT NULL,
                chain_depth INTEGER NOT NULL,
                disruption  INTEGER NOT NULL,
                rack_size   INTEGER NOT NULL,
                board_size  INTEGER NOT NULL,
                is_unique   BOOLEAN NOT NULL DEFAULT 0,
                joker_count INTEGER NOT NULL DEFAULT 0,
                seed        INTEGER,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_difficulty
            ON puzzles(difficulty)
        """)
        self.conn.commit()

    def store(self, result: PuzzleResult, seed: int | None = None) -> str:
        """Store a puzzle and return its UUID."""
        puzzle_id = str(uuid.uuid4())
        board_json = _serialize_board(result.board_sets)
        rack_json = _serialize_rack(result.rack)
        self.conn.execute(
            """INSERT INTO puzzles
               (id, difficulty, board_json, rack_json, chain_depth,
                disruption, rack_size, board_size, is_unique,
                joker_count, seed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (puzzle_id, result.difficulty, board_json, rack_json,
             result.chain_depth, result.disruption_score,
             len(result.rack), len(result.board_sets),
             result.is_unique, result.joker_count, seed),
        )
        self.conn.commit()
        return puzzle_id

    def draw(
        self,
        difficulty: str,
        exclude_ids: list[str] | None = None,
    ) -> tuple[PuzzleResult, str] | None:
        """Draw a random unseen puzzle of the given difficulty."""
        exclude = set(exclude_ids or [])
        rows = self.conn.execute(
            "SELECT * FROM puzzles WHERE difficulty = ? ORDER BY RANDOM()",
            (difficulty,),
        ).fetchall()
        for row in rows:
            if row["id"] not in exclude:
                result = _deserialize_row(row)
                return result, row["id"]
        return None  # Pool exhausted

    def count(self, difficulty: str | None = None) -> int:
        if difficulty:
            row = self.conn.execute(
                "SELECT COUNT(*) FROM puzzles WHERE difficulty = ?",
                (difficulty,),
            ).fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) FROM puzzles").fetchone()
        return row[0]

    def close(self):
        self.conn.close()
```

#### New file: `backend/solver/generator/pregenerate.py`

CLI tool for batch puzzle generation:

```python
"""Pre-generate puzzles for hard difficulties.

Usage:
    python -m solver.generator.pregenerate --difficulty nightmare --count 200
    python -m solver.generator.pregenerate --difficulty expert --count 500
    python -m solver.generator.pregenerate --all --count 100
    python -m solver.generator.pregenerate --stats
"""
import argparse
import time
import sys
from pathlib import Path

from .puzzle_generator import generate_puzzle, PuzzleGenerationError
from .puzzle_store import PuzzleStore

def main():
    parser = argparse.ArgumentParser(description="Pre-generate Rummikub puzzles")
    parser.add_argument("--difficulty", choices=["hard","expert","nightmare"])
    parser.add_argument("--all", action="store_true", help="Generate for all hard+ difficulties")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--db", type=str, default="data/puzzles.db")
    parser.add_argument("--stats", action="store_true", help="Show pool statistics")
    args = parser.parse_args()

    store = PuzzleStore(Path(args.db))

    if args.stats:
        for d in ("easy","medium","hard","expert","nightmare"):
            print(f"  {d}: {store.count(d)} puzzles")
        print(f"  total: {store.count()}")
        store.close()
        return

    difficulties = (
        ["hard","expert","nightmare"] if args.all
        else [args.difficulty] if args.difficulty
        else []
    )

    if not difficulties:
        parser.print_help()
        return

    for diff in difficulties:
        print(f"\n{'='*50}")
        print(f"Generating {args.count} {diff} puzzles...")
        print(f"{'='*50}")
        generated = 0
        failed = 0
        t0 = time.monotonic()
        seed = int(time.time() * 1000) % (2**31)

        while generated < args.count:
            seed += 1
            try:
                result = generate_puzzle(difficulty=diff, seed=seed)
                puzzle_id = store.store(result, seed=seed)
                generated += 1
                elapsed = time.monotonic() - t0
                rate = generated / elapsed if elapsed > 0 else 0
                sys.stdout.write(
                    f"\r  [{generated}/{args.count}] "
                    f"chain={result.chain_depth} "
                    f"disrupt={result.disruption_score} "
                    f"unique={result.is_unique} "
                    f"rack={len(result.rack)} "
                    f"({rate:.1f}/s)"
                )
                sys.stdout.flush()
            except PuzzleGenerationError:
                failed += 1
                if failed > args.count * 10:
                    print(f"\n  Too many failures ({failed}), stopping.")
                    break

        elapsed = time.monotonic() - t0
        print(f"\n  Done: {generated} puzzles in {elapsed:.1f}s "
              f"({failed} failures)")

    store.close()

if __name__ == "__main__":
    main()
```

-----

### Phase 5: API Changes

#### File: `backend/api/models.py`

**Changes:**

```python
class PuzzleRequest(BaseModel):
    difficulty: Literal["easy", "medium", "hard", "expert", "nightmare", "custom"] = "medium"
    seed: int | None = None
    sets_to_remove: int = Field(3, ge=1, le=5)
    seen_ids: list[str] = Field(default_factory=list, max_length=500)  # NEW

class PuzzleResponse(BaseModel):
    board_sets: list[BoardSetInput]
    rack: list[TileInput]
    difficulty: str
    tile_count: int
    disruption_score: int
    chain_depth: int = 0       # NEW
    is_unique: bool = False    # NEW
    puzzle_id: str = ""        # NEW — empty for live-generated puzzles
```

#### File: `backend/api/main.py`

**Changes to `puzzle_endpoint()`:**

```python
@app.post("/api/puzzle", response_model=PuzzleResponse, tags=["solver"])
def puzzle_endpoint(request: PuzzleRequest) -> PuzzleResponse:
    # For expert/nightmare: try pre-generated pool first
    if request.difficulty in ("expert", "nightmare"):
        store = PuzzleStore()
        drawn = store.draw(request.difficulty, exclude_ids=request.seen_ids)
        store.close()
        if drawn:
            result, puzzle_id = drawn
            return PuzzleResponse(
                board_sets=_board_sets_to_input(result.board_sets),
                rack=_rack_to_input(result.rack),
                difficulty=result.difficulty,
                tile_count=len(result.rack),
                disruption_score=result.disruption_score,
                chain_depth=result.chain_depth,
                is_unique=result.is_unique,
                puzzle_id=puzzle_id,
            )
        # Pool exhausted — fall through to live generation

    # Live generation (easy/medium/hard or fallback)
    try:
        result = generate_puzzle(
            difficulty=request.difficulty,
            seed=request.seed,
            sets_to_remove=request.sets_to_remove,
        )
    except PuzzleGenerationError as exc:
        raise HTTPException(status_code=503, detail="...") from exc

    return PuzzleResponse(
        board_sets=...,
        rack=...,
        difficulty=result.difficulty,
        tile_count=len(result.rack),
        disruption_score=result.disruption_score,
        chain_depth=result.chain_depth,
        is_unique=result.is_unique,
        puzzle_id="",  # live-generated, no ID
    )
```

-----

### Phase 6: Frontend Changes

#### File: `frontend/src/types/api.ts`

```typescript
export type Difficulty = "easy" | "medium" | "hard" | "expert" | "nightmare" | "custom";

export interface PuzzleRequest {
  difficulty?: Difficulty;
  seed?: number;
  sets_to_remove?: number;
  seen_ids?: string[];    // NEW
}

export interface PuzzleResponse {
  board_sets: BoardSetInput[];
  rack: TileInput[];
  difficulty: Difficulty;
  tile_count: number;
  disruption_score?: number;
  chain_depth?: number;    // NEW
  is_unique?: boolean;     // NEW
  puzzle_id?: string;      // NEW
}
```

#### File: `frontend/src/store/game.ts`

**Changes:**

```typescript
// Add seen puzzle tracking
const SEEN_PUZZLES_KEY = "rummikub_seen_puzzles";

function getSeenIds(): string[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(SEEN_PUZZLES_KEY) || "[]");
  } catch {
    return [];
  }
}

function markSeen(id: string): void {
  if (!id || typeof window === "undefined") return;
  const seen = getSeenIds();
  seen.push(id);
  if (seen.length > 500) seen.splice(0, seen.length - 500);
  localStorage.setItem(SEEN_PUZZLES_KEY, JSON.stringify(seen));
}

// In loadPuzzle action:
loadPuzzle: async (request, signal) => {
    // ...existing guard...
    // Inject seen_ids into request
    const enrichedRequest = {
        ...request,
        seen_ids: getSeenIds(),
    };
    const puzzle = await fetchPuzzle(enrichedRequest, signal);
    // Mark this puzzle as seen
    if (puzzle.puzzle_id) {
        markSeen(puzzle.puzzle_id);
    }
    // ...rest of existing logic...
}
```

#### File: `frontend/src/components/PuzzleControls.tsx`

**Changes:**

```typescript
const DIFFICULTIES: Difficulty[] = ["easy", "medium", "hard", "expert", "nightmare", "custom"];

// Add nightmare to the button list
// Add chain depth / uniqueness display after puzzle loads (optional UX enhancement)
```

#### File: `frontend/src/i18n/messages/en.json`

Add under `puzzle`:

```json
{
  "nightmare": "Nightmare",
  "chainDepth": "Chain depth: {depth}",
  "uniqueSolution": "Unique solution"
}
```

#### File: `frontend/src/i18n/messages/de.json`

```json
{
  "nightmare": "Albtraum",
  "chainDepth": "Kettenfolge: {depth}",
  "uniqueSolution": "Einzige Lösung"
}
```

-----

### Phase 7: Docker & Infrastructure

#### File: `docker-compose.yml`

Add volume for puzzle database:

```yaml
services:
  backend:
    volumes:
      - puzzle-data:/app/data
    environment:
      - PUZZLE_DB_PATH=/app/data/puzzles.db

volumes:
  puzzle-data:
```

#### File: `.env.example`

Add:

```
# Path to the SQLite puzzle database for pre-generated puzzles.
# The pre-generation CLI writes to this file; the API reads from it.
PUZZLE_DB_PATH=data/puzzles.db
```

#### File: `backend/pyproject.toml`

No new dependencies needed — Python’s `sqlite3` is in the stdlib.

Add CLI entry point:

```toml
[project.scripts]
pregenerate = "solver.generator.pregenerate:main"
```

-----

### Phase 8: Testing

#### File: `backend/tests/solver/test_objective.py`

Add 5+ chain depth tests (see Phase 1 above).

#### File: `backend/tests/solver/test_puzzle_generator.py`

**New/modified tests:**

- `test_nightmare_generates` — nightmare difficulty with seed, verify chain_depth >= 4
- `test_nightmare_rack_size` — verify 10 <= rack_size <= 14
- `test_nightmare_is_unique` — verify is_unique == True
- `test_expert_chain_depth_minimum` — verify chain_depth >= 3
- `test_expert_rack_size_range` — verify 8 <= rack_size <= 12
- `test_hard_may_have_jokers` — verify joker_count in (0, 1)
- `test_chain_depth_in_result` — verify PuzzleResult has chain_depth field
- `test_all_difficulties_valid` — loop all 5 difficulties, verify generation
- Update `test_rack_minimum_size` — add nightmare range
- Update `test_disruption_score_in_band_*` — adjust for new bands

#### File: `backend/tests/solver/test_puzzle_store.py` (NEW)

- `test_store_and_draw` — store a puzzle, draw it back, verify fields match
- `test_draw_excludes_seen` — store 2 puzzles, exclude one, verify other returned
- `test_draw_empty_pool` — draw from nonexistent difficulty returns None
- `test_count_by_difficulty` — verify count filtering
- `test_store_assigns_uuid` — verify returned ID is a valid UUID

#### File: `backend/tests/api/test_puzzle_endpoint.py`

- `test_nightmare_puzzle_200` — verify nightmare difficulty works
- `test_seen_ids_excludes_puzzle` — verify seen_ids filtering
- `test_response_has_chain_depth` — verify chain_depth in response
- `test_response_has_puzzle_id` — verify puzzle_id in response
- Update `test_expert_puzzle_200` — adjust assertions for new ranges

#### File: `frontend/src/__tests__/components/PuzzleControls.test.tsx`

- Add test for nightmare button rendering
- Update difficulty list assertion

-----

## 5. Execution Order

### Step 1: Foundation (no breaking changes)

1. Add `chain_depth` field to `Solution` dataclass
1. Implement `compute_chain_depth()` in `objective.py`
1. Wire chain depth computation into `solver.py`
1. Write tests for chain depth metric
1. Run full test suite — everything should still pass

### Step 2: Uniqueness Infrastructure (no breaking changes)

1. Add `excluded_solutions` parameter to `build_ilp_model()`
1. Implement `check_uniqueness()` in `solver.py`
1. Write tests for uniqueness check
1. Run full test suite

### Step 3: Puzzle Generator Rework

1. Update `PuzzleResult` with new fields
1. Add `_make_pool()` replacing `_make_full_pool()`
1. Rewrite difficulty constants
1. Rewrite `_attempt_generate()` with new metrics
1. Add `"nightmare"` to the `Difficulty` type
1. Update all existing tests for new difficulty ranges
1. Add new tests for nightmare/expert
1. Run full test suite

### Step 4: Persistence Layer

1. Create `puzzle_store.py`
1. Create `pregenerate.py` CLI
1. Write store tests
1. Test CLI manually: `python -m solver.generator.pregenerate --difficulty expert --count 10`

### Step 5: API Integration

1. Update `api/models.py` — add `seen_ids`, `chain_depth`, `puzzle_id`, `nightmare` to Difficulty
1. Update `api/main.py` — puzzle endpoint draws from store for expert/nightmare
1. Add/update endpoint tests
1. Run full test suite

### Step 6: Frontend

1. Update TypeScript types
1. Add nightmare to PuzzleControls
1. Add seen-puzzle tracking in store
1. Add i18n strings
1. Update Vitest + E2E tests

### Step 7: Infrastructure

1. Add volume to docker-compose.yml
1. Update .env.example
1. Run pre-generation: `python -m solver.generator.pregenerate --all --count 200`
1. Verify Docker build + deployment

### Step 8: Version Bump & Docs

1. Bump version to 0.25.0 in `pyproject.toml`, `api/main.py`, `package.json`
1. Add CHANGELOG entry
1. Update Blueprint.md divergence note
1. Update README with pre-generation instructions

-----

## 6. Risk Assessment

|Risk                                           |Likelihood|Mitigation                                                                                                                        |
|-----------------------------------------------|----------|----------------------------------------------------------------------------------------------------------------------------------|
|Chain depth 4+ puzzles are too rare to generate|High      |Increase max_attempts for nightmare (500+); use pre-generation so time isn’t a constraint; potentially relax board size to 28 sets|
|Uniqueness check is too slow                   |Medium    |Set 10s timeout on re-solve; for pre-generation, time doesn’t matter; for live generation (hard), skip uniqueness                 |
|SQLite concurrent writes from pre-gen + API    |Low       |Pre-gen runs offline; API only reads; use WAL mode for concurrent reads                                                           |
|Nightmare puzzles are still too easy           |Medium    |Add red herring scoring as a future metric; increase chain depth minimum to 5; tune rack sizes up                                 |
|Frontend localStorage fills up                 |Very Low  |Cap at 500 IDs; localStorage limit is 5MB, 500 UUIDs ≈ 18KB                                                                       |

-----

## 7. Success Criteria

1. **Easy:** Solvable in < 30 seconds by a casual player
1. **Medium:** Requires 1–3 minutes of thought
1. **Hard:** Requires systematic analysis, 3–8 minutes
1. **Expert:** Chain depth 3+, requires backtracking mental simulation, 8–15 minutes for a skilled player
1. **Nightmare:** Chain depth 4+, unique solution, 10–14 rack tiles, 15–30+ minutes for even the most skilled player

**Validation method:** Have the target user (your girlfriend) test 5 puzzles at each difficulty and report solve times. Adjust constants based on feedback.