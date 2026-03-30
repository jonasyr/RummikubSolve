# Puzzle Difficulty Implementation — Post-Mortem Evaluation

**Date:** 2026-03-30
**Scope:** Evaluate the autonomous agent’s implementation of the puzzle difficulty overhaul (v0.32.0 branch)
**Method:** Line-by-line code review against the original plan, game theory analysis, and empirical feasibility assessment

-----

## Executive Summary

The agent did solid engineering work — the DAG algorithm rewrite, cycle-safe Kahn’s BFS, joker pool integration, and test updates are all well-executed. But the **calibration retreat** undermines the core goal. The plan called for puzzles that take 15–30 minutes to solve; the implemented constants produce puzzles that are harder than before but still solvable in 2–5 minutes by a skilled player. The fundamental issue is that the agent treated generation feasibility as a hard constraint when it should have been treated as a pre-generation problem.

**Verdict:** Good code, wrong tradeoffs. The difficulty ceiling needs to go higher, and the approach to achieving it needs to change.

-----

## 1. What Was Done Well

### 1.1 DAG Algorithm (objective.py) — ✅ Correct and Improved

The rewrite from convergence-breadth to DAG-longest-path is the right call. The old metric counted “how many disrupted sources feed one set” — that’s not sequential complexity. The new algorithm builds actual directed edges and measures the longest path.

**Specific good decisions:**

- **Kahn’s BFS instead of recursive DFS.** The agent discovered that step 5 (rack-tile edge construction) can create cycles in the adjacency list. Recursive DFS would infinite-loop. Kahn’s topological sort handles this gracefully — nodes in cycles never reach in-degree 0, so they’re effectively ignored. This is the correct solution.
- **Inheritor/dependent edge direction.** For each disrupted old set, the new set that got the most tiles is the “inheritor,” and edges point inheritor → dependent. This correctly models “breaking old set O restructured the inheritor, which freed tiles for the dependent.” The direction matters for path length.
- **Rack-tile prerequisite edges.** Step 5 adds edges from other destinations → the rack-tile set when a new set combines rack tiles with tiles from a disrupted source. This captures “I can’t place my rack tile until I’ve broken old set O, which also affects set X.”

### 1.2 Joker Integration — ✅ Clean Implementation

The `_JOKER_COUNTS` constant and `_make_pool()` function are minimal and correct. The existing set enumerator already handles joker tiles (Type 1/2/3 variants), so the only change needed was seeding the pool with jokers. The agent correctly:

- Added jokers to the pool before enumeration (not after)
- Used `rng.randint(joker_lo, joker_hi)` for difficulty-controlled randomness
- Kept custom mode at (0, 0) jokers since custom is user-controlled
- Left `_make_full_pool()` intact for backward compatibility

### 1.3 Test Updates — ✅ Thorough

160 tests passing across all three test files (34 objective + 58 generator + 34 endpoint + others). The agent correctly updated assertion values when the chain depth semantics changed (old depth 1 → new depth 2 for split scenarios).

### 1.4 RecursionError Fix — ✅ Good Engineering

The agent encountered a real bug (infinite recursion from cyclic edges), diagnosed it correctly, and chose the right fix (Kahn’s algorithm). This is exactly the kind of issue an autonomous agent should handle — runtime failures during testing that require algorithmic changes.

-----

## 2. What’s Problematic

### 2.1 The Calibration Retreat — ❌ Wrong Tradeoff

This is the central issue. The original plan specified:

|Parameter            |Plan    |Implemented  |Retreat Reason                                                |
|---------------------|--------|-------------|--------------------------------------------------------------|
|Nightmare chain depth|4       |3            |“depth ≥ 4 occurs ~23% of solvable candidates”                |
|Nightmare disruption |45      |38           |“only 2% reach 45 on large boards”                            |
|Nightmare uniqueness |Required|Informational|“nightmare-sized boards almost always have multiple solutions”|

The agent’s reasoning was: “these constraints make live generation infeasible (too many attempts needed).” But **that’s exactly why we built the pre-generation system.** The entire point of Phases 4–5 (PuzzleStore + pregenerate.py CLI) was to decouple generation time from request latency. Nightmare puzzles were always expected to take 5–60 seconds each to generate — that’s fine for a batch CLI that runs overnight.

**What should have happened:** Keep the strict constraints (chain ≥ 4, disruption ≥ 45, uniqueness required) and rely on pre-generation. The live fallback path would use relaxed constraints, but pool-drawn puzzles would meet the full spec.

**Impact:** A skilled player who can solve current Expert in 1–2 minutes will solve the “new Nightmare” in maybe 3–5 minutes. That’s better than before but nowhere near the 15–30 minute target.

### 2.2 Rack Size Mismatch — ⚠️ Partially Wrong

The plan specified nightmare rack (10, 14). The implementation has (10, 14) in the constant, but then `_extract_by_sacrifice` samples `rng.randint(rack_min, min(rack_max, len(sacrifice_tiles)))`. With 7 sacrificed sets of 3–5 tiles each, `sacrifice_tiles` is typically 21–35 tiles. So `min(14, 21+)` = 14, which means the full range is used. This is correct.

However, the agent’s empirical sampling showed nightmare generation was working, which means the rack sizes are being generated correctly. The issue is that 10–14 rack tiles with only chain depth 3 and no uniqueness constraint doesn’t produce the overwhelming combinatorial complexity intended. **The rack size is right, but it’s wasted without the other constraints.**

### 2.3 Expert Constants — ⚠️ Mixed

|Parameter   |Old     |New     |Assessment                                |
|------------|--------|--------|------------------------------------------|
|Rack        |(4, 6)  |(6, 10) |✅ Good — 6–10 tiles is meaningful         |
|Board       |(13, 18)|(16, 22)|✅ Good — larger scan space                |
|Chain depth |1       |2       |✅ Good — requires real sequential thinking|
|Disruption  |29      |32      |⚠️ Marginal — only 3 points higher         |
|Max attempts|400     |600     |✅ Appropriate for stricter filters        |

Expert improvements are reasonable. The concern is that Expert and Nightmare are now too close together — Expert requires chain ≥ 2 with disruption ≥ 32, Nightmare requires chain ≥ 3 with disruption ≥ 38. That’s only one chain-depth step and 6 disruption points apart. The difficulty curve should be exponential, not linear.

### 2.4 Chain Depth Metric — ⚠️ Subtle Semantic Issue

The new algorithm is better than the old one, but it still has a conceptual limitation. Consider this scenario:

```
Old board: Set A (R1,R2,R3), Set B (R4,R5,R6), Set C (B1,B2,B3)
Solution:  Set X (R1,R2,R3,R4), Set Y (R5,R6,B3), Set Z (B1,B2,rack_tile)
```

Here:

- Set A is disrupted (tiles went to X)
- Set B is disrupted (R4→X, R5,R6→Y)
- Set C is disrupted (B3→Y, B1,B2→Z)

The DAG edges would be:

- B’s inheritor is Y (got 2 tiles), dependent is X (got 1 tile) → edge Y→X
- C’s inheritor is Z (got 2 tiles), dependent is Y (got 1 tile) → edge Z→Y
- Rack-tile edge: Z has rack tile + tiles from disrupted C → edge Z gets prerequisites

So the path is Z→Y→X, depth = 3. **This is correct for sequential reasoning** — the player must realize that breaking C frees B3 for Y, which frees R4 for X.

But what about when the same depth score arises from **independent parallel breaks** that happen to feed into the same set? The metric doesn’t distinguish between “A→B→C sequential chain” and “A→C and B→C parallel convergence with a shared dependency.” Both could report depth 3. For puzzle difficulty, sequential chains are harder than parallel convergence because the player must think N steps ahead, not just find N independent rearrangements.

**This isn’t a bug** — it’s a limitation. The metric is a reasonable approximation. But it means a chain-depth-3 puzzle can range from “moderately complex” to “genuinely deep” depending on the DAG structure.

### 2.5 Uniqueness Check Abandoned — ❌ Premature Surrender

The agent’s reasoning: “nightmare-sized boards almost always have multiple equivalent solutions, so gating on uniqueness would make generation infeasible.”

This is true for the complete-sacrifice strategy — but it points to a deeper problem: **the generation strategy itself is the bottleneck, not the uniqueness check.** Complete sacrifice removes N sets entirely, leaving the remaining board intact. The ILP then has enormous freedom in how to rearrange tiles to accommodate the rack. Of course there are multiple solutions.

A better strategy for generating unique-solution puzzles would be:

1. Start with a solved board (all tiles in valid sets)
1. Choose a specific rearrangement path (the intended solution)
1. Extract exactly the tiles that make that specific path necessary
1. Verify no other path places the same number of tiles

This is harder to implement but would produce genuinely unique puzzles. The current complete-sacrifice strategy is fundamentally incompatible with uniqueness. The agent correctly identified this incompatibility but drew the wrong conclusion — instead of abandoning uniqueness, the strategy should evolve.

-----

## 3. Bugs and Code Issues

### 3.1 `_make_pool()` Joker copy_id Range — ⚠️ Edge Case

```python
def _make_pool(n_jokers: int = 0) -> BoardState:
    ...
    for j in range(n_jokers):
        rack.append(Tile.joker(copy_id=j))
    return BoardState(board_sets=[], rack=rack)
```

`Tile.__post_init__` enforces `copy_id in (0, 1)`. If `n_jokers > 2` is ever passed, this crashes. Currently `_JOKER_COUNTS` caps at 2, so it’s safe. But the function doesn’t validate its input — a future caller could pass `n_jokers=3` and get a `ValueError`. Add a guard:

```python
if n_jokers > 2:
    raise ValueError(f"At most 2 jokers allowed, got {n_jokers}")
```

### 3.2 Joker Tiles Not Tracked in PuzzleResult — ⚠️ Incomplete

`_attempt_generate()` computes `n_jokers = rng.randint(joker_lo, joker_hi)` and passes it to `_make_pool()`, but **never stores it in PuzzleResult.joker_count**. The current code:

```python
return PuzzleResult(
    board_sets=input_board,
    rack=rack,
    difficulty=difficulty,
    disruption_score=score,
    chain_depth=solution.chain_depth,
    is_unique=is_unique,
    # joker_count is missing! defaults to 0
)
```

The `joker_count` field exists on `PuzzleResult` (added in Phase 4) but is never populated by the updated `_attempt_generate()`. This means:

- The puzzle store records `joker_count=0` for all puzzles, even those with jokers
- The API response always reports 0 jokers
- Pre-generated pool queries can’t filter by joker presence

**Fix:** Add `joker_count=n_jokers` to the `PuzzleResult` constructor call.

### 3.3 Jokers in Board Sets Not Handled by `_pick_compatible_sets` — ⚠️ Silent Failure

`_pick_compatible_sets()` tracks availability by `(color, number)` pairs. Joker tiles have `color=None, number=None`. The current code:

```python
needed: Counter[tuple[Color | None, int | None]] = Counter(
    (t.color, t.number)
    for t in ts.tiles
    if not t.is_joker and t.color is not None and t.number is not None
)
```

This correctly skips jokers when counting needed tiles. But the enumerated sets from `enumerate_runs()` and `enumerate_groups()` **don’t include joker variants** — those are only added by `enumerate_valid_sets()`. Since `_attempt_generate()` calls `enumerate_runs(full_pool) + enumerate_groups(full_pool)` (not `enumerate_valid_sets()`), joker-containing set templates are never generated for the board.

This means **jokers are added to the tile pool but never appear in any board set**. They’re just dead tiles sitting in the pool. The set enumerator generates non-joker templates from the pool, and since jokers don’t have a `(color, number)` pair, they’re invisible to `enumerate_runs()` and `enumerate_groups()`.

**Impact:** The `_JOKER_COUNTS` feature has zero effect on puzzle difficulty right now. Jokers are in the pool but never on the board. This completely negates the intended complexity multiplier.

**Fix:** Either:

- (A) Call `enumerate_valid_sets(full_pool)` instead of `enumerate_runs() + enumerate_groups()` to include joker-containing templates in board construction, OR
- (B) After building the board, randomly replace 1–2 tiles in existing sets with jokers (preserving set validity), then add those jokers to the available pool

Option B is simpler and more controllable — you know exactly where the jokers end up.

### 3.4 `_any_trivial_extension` Performance on Large Boards — ⚠️ Slow

With nightmare boards of 22–28 sets and racks of 10–14 tiles, `_any_trivial_extension` checks every `(rack_tile, board_set)` pair by constructing a new TileSet and calling `is_valid_set()`. That’s `14 × 28 = 392` validity checks per sample, with up to `_MAX_SAMPLE_ATTEMPTS = 20` samples per board. Each `is_valid_set()` call does string comparisons and set operations.

This isn’t catastrophically slow, but it’s called in the inner loop of generation. For nightmare with 1500 attempts, that’s potentially `1500 × 20 × 392 = 11.7 million` validity checks. On a fast machine this is ~seconds, but it adds up.

**Not a bug, but worth noting** — if generation speed becomes an issue, this is the first optimization target. A hash-based pre-check (“does any board set have the right color/number to extend with this tile?”) would eliminate 90%+ of candidates without constructing TileSets.

-----

## 4. Architectural Assessment

### 4.1 The Core Problem: Complete Sacrifice Is a Ceiling

The complete-sacrifice strategy has a fundamental difficulty ceiling. By removing entire sets from the board, you guarantee solvability (the removed tiles can always reform their original sets). But this also means:

1. **The solution space is huge.** The ILP has enormous flexibility in rearranging 15–21 remaining sets to accommodate 10–14 rack tiles. Multiple valid rearrangements always exist.
1. **Chain depth is bounded by board structure.** The maximum chain depth depends on how many sets share tiles with each other. With randomly selected sets from a shuffled pool, inter-set tile sharing is sparse. Deep sequential dependencies require sets that are tightly interlocked — which random selection rarely produces.
1. **Disruption is bounded by ILP optimality.** The ILP finds the arrangement that places the most tiles with the least rearrangement (due to the tile-value secondary objective). It actively minimizes disruption. You’re fighting the solver’s optimization when you want high disruption.

**The strategic insight:** To create genuinely hard puzzles, you need a generation strategy that works *with* the ILP, not against it. Instead of “generate random board, remove tiles, hope the solution is complex,” you should “design a specific complex solution, then construct a board that requires it.”

### 4.2 Proposed Alternative: Reverse-Engineering Strategy

Instead of forward generation (build board → sacrifice → solve → measure), use reverse generation:

1. **Start with a target solution structure.** Define the rearrangement chain you want: “Set A breaks into A1+A2, A2 combines with tiles from B to form B’, freeing tile X, which goes into C with rack tiles.”
1. **Construct the board that requires this structure.** Place tiles into sets such that the target chain is the only way to place all rack tiles.
1. **Verify with the solver.** Run the ILP and check that it finds the intended solution.
1. **Verify uniqueness.** Re-solve with exclusion constraint. Since the board was designed for one specific solution, uniqueness is likely.

This is significantly more complex to implement but would produce puzzles with guaranteed deep chains and potential uniqueness. It’s the difference between finding a needle in a haystack (current approach) and manufacturing the needle.

### 4.3 Near-Term Fix: Two-Tier Nightmare

A pragmatic middle ground that doesn’t require a strategy rewrite:

**Pool-only Nightmare with strict constraints:**

- Chain depth ≥ 4 (achievable ~23% of the time per the agent’s data)
- Disruption ≥ 45 (achievable ~2% of the time)
- Uniqueness checked (informational, not gated)
- Pre-generation only — no live fallback
- Generate 500 puzzles overnight, accept the ~0.5% that pass all filters = ~2–3 puzzles per batch run
- Run the batch multiple times or with different seeds to build a pool of 50–100 certified nightmare puzzles

**Live-fallback Nightmare with relaxed constraints:**

- The current implementation (chain ≥ 3, disruption ≥ 38, no uniqueness gate)
- Used when the pool is empty
- Labeled differently in the UI: “Nightmare (from pool)” vs “Nightmare (generated)”

This gives the best puzzles when the pool has them, and a reasonable fallback when it doesn’t.

-----

## 5. Specific Code Changes Recommended

### 5.1 Fix: Populate joker_count in PuzzleResult

**File:** `backend/solver/generator/puzzle_generator.py`
**Location:** `_attempt_generate()` return statement (~line 275)

```python
# CURRENT (bug):
return PuzzleResult(
    board_sets=input_board,
    rack=rack,
    difficulty=difficulty,
    disruption_score=score,
    chain_depth=solution.chain_depth,
    is_unique=is_unique,
    # joker_count defaults to 0 — WRONG when n_jokers > 0
)

# FIX:
return PuzzleResult(
    board_sets=input_board,
    rack=rack,
    difficulty=difficulty,
    disruption_score=score,
    chain_depth=solution.chain_depth,
    is_unique=is_unique,
    joker_count=n_jokers,  # propagate actual joker count
)
```

### 5.2 Fix: Make Jokers Actually Appear on the Board

**File:** `backend/solver/generator/puzzle_generator.py`
**Location:** `_attempt_generate()`, after `_assign_copy_ids()` and before `_extract_rack()`

Add a function that injects jokers into existing board sets:

```python
def _inject_jokers_into_board(
    board_sets: list[TileSet],
    n_jokers: int,
    rng: random.Random,
) -> list[TileSet]:
    """Replace 1–2 random non-joker tiles in board sets with joker tiles.

    The replaced tiles become "freed" — they're removed from the board
    entirely (simulating that they were never placed). The joker takes
    the replaced tile's position in the set, which remains valid because
    jokers can substitute for any tile.

    This creates mental complexity: the player must deduce what each joker
    represents before reasoning about rearrangements.
    """
    if n_jokers == 0 or not board_sets:
        return board_sets

    result = [TileSet(type=ts.type, tiles=list(ts.tiles)) for ts in board_sets]

    # Collect all (set_index, tile_index) positions eligible for joker replacement.
    # Exclude sets with only 3 tiles (replacing would leave ambiguity about set type).
    candidates: list[tuple[int, int]] = []
    for si, ts in enumerate(result):
        if len(ts.tiles) >= 4:  # only replace in sets with room for ambiguity
            for ti in range(len(ts.tiles)):
                if not ts.tiles[ti].is_joker:
                    candidates.append((si, ti))

    if not candidates:
        return result

    # Randomly select positions to replace with jokers.
    n_replace = min(n_jokers, len(candidates))
    chosen = rng.sample(candidates, n_replace)

    for idx, (si, ti) in enumerate(chosen):
        result[si].tiles[ti] = Tile.joker(copy_id=idx)

    return result
```

Then in `_attempt_generate()`:

```python
board_sets = _assign_copy_ids(board_sets)

# Inject jokers into the board (Phase 8 — joker complexity multiplier)
if n_jokers > 0:
    board_sets = _inject_jokers_into_board(board_sets, n_jokers, rng)

input_board, rack = _extract_rack(board_sets, difficulty, rng, sets_to_remove)
```

### 5.3 Fix: Add Input Validation to _make_pool

**File:** `backend/solver/generator/puzzle_generator.py`

```python
def _make_pool(n_jokers: int = 0) -> BoardState:
    """104 non-joker tiles plus n_jokers joker tiles."""
    if not (0 <= n_jokers <= 2):
        raise ValueError(f"n_jokers must be 0, 1, or 2; got {n_jokers}")
    rack: list[Tile] = [
        Tile(color, n, copy_id)
        for color in Color
        for n in range(1, 14)
        for copy_id in (0, 1)
    ]
    for j in range(n_jokers):
        rack.append(Tile.joker(copy_id=j))
    return BoardState(board_sets=[], rack=rack)
```

### 5.4 Recommended: Add Pre-Generation Tiers to puzzle_generator.py

Add a `_PREGEN_CONSTRAINTS` dict that specifies stricter thresholds used during batch pre-generation:

```python
# Stricter thresholds used by pregenerate.py (offline batch, no time pressure).
# Live generation uses _MIN_CHAIN_DEPTHS / _DISRUPTION_BANDS (relaxed).
_PREGEN_CONSTRAINTS: dict[str, dict[str, int]] = {
    "expert": {
        "min_chain_depth": 3,    # vs live: 2
        "min_disruption": 38,    # vs live: 32
    },
    "nightmare": {
        "min_chain_depth": 4,    # vs live: 3
        "min_disruption": 45,    # vs live: 38
    },
}
```

Then add a `pregen=False` parameter to `generate_puzzle()`:

```python
def generate_puzzle(
    difficulty: Difficulty = "medium",
    seed: int | None = None,
    max_attempts: int | None = None,
    pregen: bool = False,  # NEW: use stricter constraints for batch pre-generation
    ...
) -> PuzzleResult:
```

And in `_attempt_generate()`, apply the stricter constraints when `pregen=True`:

```python
# Choose chain depth floor based on whether this is pre-generation
if pregen and difficulty in _PREGEN_CONSTRAINTS:
    min_chain = _PREGEN_CONSTRAINTS[difficulty]["min_chain_depth"]
else:
    min_chain = _MIN_CHAIN_DEPTHS.get(difficulty, 0)
```

This way:

- **Live generation** (API request) uses relaxed thresholds → always generates within timeout
- **Pre-generation** (CLI batch) uses strict thresholds → produces genuinely hard puzzles for the pool
- **Pool-drawn puzzles** meet the strict spec; live fallback is labeled as such

### 5.5 Recommended: Update pregenerate.py to Use Strict Mode

```python
# In _generate_batch():
result = generate_puzzle(
    difficulty=difficulty,
    seed=seed,
    pregen=True,  # Use strict pre-generation constraints
)
```

-----

## 6. Constants Recommendation

Based on the agent’s empirical data (p90 disruption=39, chain≥4 at 23%, uniqueness pass rate near 0% on large boards):

### Live Generation (API fallback)

|Parameter   |Easy |Medium|Hard  |Expert |Nightmare|
|------------|-----|------|------|-------|---------|
|Rack        |(2,3)|(3,4) |(4,5) |(6,10) |(10,14)  |
|Board       |(5,9)|(7,11)|(9,13)|(16,22)|(22,28)  |
|Sacrifice   |1    |2     |3     |5      |7        |
|Chain depth |0    |0     |1     |2      |3        |
|Disruption  |2–10 |9–18  |16–28 |≥32    |≥38      |
|Jokers      |0    |0     |0–1   |1–2    |1–2      |
|Max attempts|150  |150   |200   |600    |1500     |

*(These match the agent’s implementation — they’re reasonable for live generation.)*

### Pre-Generation (CLI batch, pool-drawn)

|Parameter   |Expert             |Nightmare          |
|------------|-------------------|-------------------|
|Chain depth |≥ 3                |≥ 4                |
|Disruption  |≥ 38               |≥ 45               |
|Uniqueness  |Computed, not gated|Computed, not gated|
|Max attempts|5000               |10000              |

*(These are the original plan’s numbers. Pre-generation can afford the low acceptance rate.)*

-----

## 7. Summary of Issues by Severity

### Critical (affects core goal)

1. **Jokers never appear on the board** — `_JOKER_COUNTS` feature is completely non-functional because `enumerate_runs()` + `enumerate_groups()` don’t produce joker templates. Zero complexity added despite the feature being “implemented.”
1. **`joker_count` not populated** — `PuzzleResult.joker_count` is always 0, so the puzzle store, API response, and frontend stats badge all report 0 jokers regardless of actual joker presence.
1. **Calibration retreat too aggressive** — Nightmare chain depth 3 + disruption 38 + no uniqueness is not meaningfully harder than Expert chain depth 2 + disruption 32. The difficulty gap between Expert and Nightmare is too small.

### Moderate (quality issues)

1. **No `_make_pool()` input validation** — Passing `n_jokers > 2` crashes with an unhelpful `ValueError` from `Tile.__post_init__`.
1. **No pre-generation tier separation** — Live and batch generation use the same constraints. The pre-generation system was built precisely to allow stricter offline constraints.
1. **`_any_trivial_extension` performance** — O(rack × board × set_size) per sample, 20 samples per board, 1500 boards. Not critical now but will slow down as board sizes increase further.

### Low (cosmetic / documentation)

1. **`_make_full_pool()` is now dead code** — Only called by tests that should use `_make_pool(0)` instead. Not harmful but confusing.
1. **PUZZLE_REWORK_STATUS.md not updated** — The status document should reflect the Phase 8 implementation and calibration deviations.

-----

## 8. Recommended Action Plan

### Immediate (before next deploy)

1. **Fix joker_count population** — One-line fix in `_attempt_generate()`. (5 min)
1. **Add `_make_pool()` validation** — Guard `n_jokers` range. (2 min)
1. **Implement `_inject_jokers_into_board()`** — Make jokers actually functional. (30 min + tests)

### Short-term (next session)

1. **Add pre-generation tier** — `pregen=True` parameter with `_PREGEN_CONSTRAINTS`. (1 hour)
1. **Update `pregenerate.py`** to use `pregen=True`. (5 min)
1. **Run a batch**: `python -m solver.generator.pregenerate --difficulty nightmare --count 500` with strict constraints. Accept the 1–5 puzzles that pass. Run multiple times with different seeds to build a pool of 20–50 certified nightmare puzzles. (30 min hands-off time)
1. **Test with the target user** — Have your girlfriend try 3 pool-drawn nightmare puzzles and report solve times.

### Medium-term (future session)

1. **Explore reverse-engineering generation** — Design solutions first, then construct boards. This is the path to truly unique, deeply-chained puzzles that take 15–30 minutes.
1. **Add a “Nightmare+” tier** that’s pool-only (no live fallback) with chain ≥ 5, uniqueness required, and reverse-engineered generation.

-----

## 9. Final Assessment

The autonomous agent did competent engineering — the code works, tests pass, and the difficulty did increase. But it optimized for the wrong metric: **generation reliability** instead of **puzzle difficulty**. When faced with the tradeoff “make generation feasible vs. make puzzles hard,” it chose feasibility every time. That’s the safe engineering choice, but it’s the wrong product choice for this use case.

The pre-generation system exists precisely so that generation doesn’t need to be feasible in real-time. Nightmare puzzles should be rare, precious, and brutally hard. If it takes 10,000 attempts to find one that meets the spec, that’s fine — run the CLI overnight. The agent had all the tools to do this (PuzzleStore, pregenerate.py, pool-drawing in the API) but never used them to their full potential.

**Bottom line:** The infrastructure is solid. The tuning knobs just need to be turned higher for the pre-generation path.