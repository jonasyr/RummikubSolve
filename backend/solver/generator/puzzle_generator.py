"""Random puzzle generation for practice mode.

Blueprint §9.1 — Puzzle Generation:
  Generate a random valid board, remove a subset of tiles to form the
  rack, solve to verify the rack can be placed, and classify difficulty.

All non-custom difficulties use the "complete sacrifice" strategy:
  N sets are removed entirely from the board. M tiles sampled from the
  removed sets become the rack. Because the source sets no longer exist
  on the board, the player must genuinely rearrange the remaining board
  to place any rack tile — trivial extensions are explicitly rejected.

Difficulty is controlled by three levers:
  1. Number of sacrificed sets  → how many "homes" disappear
  2. Rack size                  → how many tiles need placing
  3. Disruption band            → minimum board rearrangement required

Disruption score (compute_disruption_score) measures how many board tiles
were moved to a different set group in the solver's solution. A higher
score means more rearrangement was required — a harder puzzle.

Solvability is guaranteed by construction. Joker-free in v1.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from typing import Literal

from ..engine.objective import compute_disruption_score
from ..engine.solver import check_uniqueness, solve
from ..models.board_state import BoardState
from ..models.tile import Color, Tile
from ..models.tileset import TileSet
from ..validator.rule_checker import is_valid_set
from .set_enumerator import enumerate_groups, enumerate_runs

Difficulty = Literal["easy", "medium", "hard", "expert", "nightmare", "custom"]

# ---------------------------------------------------------------------------
# Difficulty configuration constants
# ---------------------------------------------------------------------------

# Rack size range (min, max) tiles per difficulty.
_RACK_SIZES: dict[str, tuple[int, int]] = {
    "easy": (2, 3),
    "medium": (3, 4),
    "hard": (4, 5),
    "expert": (6, 10),    # was (4, 6); larger rack forces deeper mental search
    "nightmare": (10, 14), # was (5, 7); 10–14 tiles overwhelms working memory
}

# Number of complete board sets sacrificed (removed entirely) per difficulty.
_SACRIFICE_COUNTS: dict[str, int] = {
    "easy": 1,
    "medium": 2,
    "hard": 3,
    "expert": 5,     # was 4; one extra sacrifice drives more rearrangement
    "nightmare": 7,  # was 6; 7 sacrificed sets from 22–28 = massive rearrangement pressure
}

# Disruption band: (min_inclusive, max_inclusive).
# None as max means no upper bound.
# Bands are non-overlapping to guarantee Nightmare > Expert > Hard > Medium > Easy.
# These are calibrated for the content-based compute_disruption_score metric.
# Adjust after running empirical samples if generation rate is too low.
_DISRUPTION_BANDS: dict[str, tuple[int, int | None]] = {
    "easy": (2, 10),
    "medium": (9, 18),
    "hard": (16, 28),
    "expert": (32, None),    # was (29, None); higher floor with larger boards
    "nightmare": (38, None), # larger boards give ILP more routing options → same floor as before
}

# Board size range (number of sets, BEFORE sacrifice) per difficulty.
# Larger boards give the sacrifice strategy more candidates to work with.
_BOARD_SIZES: dict[str, tuple[int, int]] = {
    "easy": (5, 9),
    "medium": (7, 11),
    "hard": (9, 13),
    "expert": (16, 22),    # was (13, 18); larger table = more disruption potential
    "nightmare": (22, 28), # was (15, 20); prevents visual scan of entire board
}

# Minimum chain_depth required per difficulty (Phase 3).
# chain_depth measures the nesting depth of board rearrangements in the solution.
# 0 = pure placement, 1 = simple rearrangement, 2 = two-step convergence, 3+ = deep chains.
_MIN_CHAIN_DEPTHS: dict[str, int] = {
    "easy": 0,
    "medium": 0,
    "hard": 1,
    "expert": 2,    # was 1; Expert requires a real two-step sequential dependency
    "nightmare": 3, # was 2; requires genuine 2-step sequential chain under the new DAG metric
}

# Whether to compute uniqueness for this difficulty (Phase 3).
# check_uniqueness() re-solves the ILP and is called once per returned puzzle
# (not per candidate), so the overhead is small (~1-10 s per Expert/Nightmare puzzle).
# The result is stored in PuzzleResult.is_unique for informational use.
# NOTE: the complete-sacrifice strategy typically yields non-unique solutions
# (many equivalent rearrangements exist on large boards); uniqueness gating is
# reserved for a future puzzle generation strategy.
_COMPUTES_UNIQUE: dict[str, bool] = {
    "easy": False,
    "medium": False,
    "hard": False,
    "expert": True,
    "nightmare": True,
    "custom": True,   # Phase 7a: always compute for custom (shown in stats badge)
}

# Number of joker tiles to add to the tile pool, per difficulty.
# Jokers on the board force the player to deduce what each joker represents
# before reasoning about rearrangements — a significant complexity multiplier.
_JOKER_COUNTS: dict[str, tuple[int, int]] = {
    "easy": (0, 0),
    "medium": (0, 0),
    "hard": (0, 1),
    "expert": (1, 2),
    "nightmare": (1, 2),
    "custom": (0, 0),
}

# Max tile-sample attempts inside _extract_by_sacrifice before giving up
# on a board and letting the outer loop retry with a fresh board.
_MAX_SAMPLE_ATTEMPTS = 20

# Default max outer-loop attempts per difficulty (Phase 3).
# Expert and Nightmare add chain_depth + uniqueness filters that lower the
# acceptance rate significantly, so they need more attempts to reliably
# produce a valid puzzle. Callers can override by passing max_attempts explicitly.
_DEFAULT_MAX_ATTEMPTS: dict[str, int] = {
    "easy": 150,
    "medium": 150,
    "hard": 200,
    "expert": 600,     # was 400; larger boards + chain_depth ≥ 2 lower acceptance rate
    "nightmare": 1500, # was 600; chain_depth ≥ 4 + uniqueness is rare, needs more tries
    "custom": 150,
}

# Stricter thresholds used by pregenerate.py (offline batch, no time pressure).
# Live API generation uses _MIN_CHAIN_DEPTHS / _DISRUPTION_BANDS (relaxed) to
# guarantee response within timeout. Pool-drawn puzzles must meet these stricter
# thresholds so they deliver the intended 15–30 min difficulty experience.
_PREGEN_CONSTRAINTS: dict[str, dict[str, int]] = {
    "expert": {
        "min_chain_depth": 3,   # vs live: 2; requires a genuine 2-step sequential chain
        "min_disruption": 38,   # vs live: 32; forces significant board rearrangement
    },
    "nightmare": {
        "min_chain_depth": 4,   # vs live: 3; the original target from the plan
        "min_disruption": 45,   # vs live: 38; achievable ~2% of candidates; batch is fine
    },
}

# Max attempts for pre-generation. Strict constraints have low acceptance rates,
# so pre-generation needs far more attempts than live generation.
_PREGEN_MAX_ATTEMPTS: dict[str, int] = {
    "expert": 5000,
    "nightmare": 10000,
}

# Solver timeouts used during pre-generation.
# Shorter than the live defaults (30 s solve / 10 s uniqueness) so degenerate
# boards that the ILP cannot solve in a reasonable window are rejected quickly.
# 8 s is conservative enough that genuine nightmare boards still pass.
_PREGEN_SOLVE_TIMEOUT: float = 8.0
_PREGEN_UNIQUENESS_TIMEOUT: float = 5.0


class PuzzleGenerationError(Exception):
    """Raised when a puzzle cannot be generated within the attempt limit."""


@dataclass
class PuzzleResult:
    board_sets: list[TileSet]
    rack: list[Tile]
    difficulty: Difficulty
    disruption_score: int
    chain_depth: int = 0    # Phase 3: longest rearrangement chain in the solution
    is_unique: bool = True  # Phase 3: True if uniqueness not required OR verified
    joker_count: int = 0    # Phase 4: number of jokers in the tile pool (0 = joker-free)


def generate_puzzle(
    difficulty: Difficulty = "medium",
    seed: int | None = None,
    max_attempts: int | None = None,
    pregen: bool = False,
    sets_to_remove: int = 3,
    # Custom mode knobs — ignored for all non-custom difficulties:
    min_board_sets: int = 8,
    max_board_sets: int = 14,
    min_chain_depth: int = 0,
    min_disruption: int = 0,
    solve_timeout: float | None = None,
) -> PuzzleResult:
    """Generate a random, pre-verified Rummikub puzzle at the given difficulty.

    Args:
        difficulty:      "easy", "medium", "hard", "expert", "nightmare", or "custom".
        seed:            Optional RNG seed for reproducible puzzles.
        max_attempts:    How many boards to try before giving up. Defaults to a
                         per-difficulty value from _DEFAULT_MAX_ATTEMPTS (live) or
                         _PREGEN_MAX_ATTEMPTS (pregen). Override by passing explicitly.
        pregen:          If True, apply stricter _PREGEN_CONSTRAINTS (higher chain_depth
                         and disruption floors) for offline batch pre-generation. Uses
                         _PREGEN_MAX_ATTEMPTS as the default attempt budget. This produces
                         harder puzzles suitable for the pool; live generation keeps the
                         relaxed defaults to guarantee response within API timeout.
                         Pass 0 to raise PuzzleGenerationError immediately (useful
                         for testing the error path).
        sets_to_remove:  Number of complete sets to sacrifice (custom only; range 1–8).
        min_board_sets:  Minimum board sets before sacrifice (custom only; range 5–25).
        max_board_sets:  Maximum board sets before sacrifice (custom only; range 5–25).
        min_chain_depth: Minimum chain depth required in the solution (custom only; 0–4).
        min_disruption:  Minimum disruption score required (custom only; 0–60).

    Returns:
        A PuzzleResult whose rack the solver can fully place, with a
        disruption_score in the target band for the given difficulty.

    Raises:
        ValueError:             If difficulty is not a known value.
        PuzzleGenerationError:  If no suitable puzzle is found.
    """
    if difficulty not in ("easy", "medium", "hard", "expert", "nightmare", "custom"):
        raise ValueError(
            f"Unknown difficulty {difficulty!r}. "
            f"Use 'easy', 'medium', 'hard', 'expert', 'nightmare', or 'custom'."
        )

    if max_attempts is not None:
        n_attempts = max_attempts
    elif pregen:
        n_attempts = _PREGEN_MAX_ATTEMPTS.get(
            difficulty, _DEFAULT_MAX_ATTEMPTS.get(difficulty, 150)
        )
    else:
        n_attempts = _DEFAULT_MAX_ATTEMPTS.get(difficulty, 150)

    # When pregen=True and no explicit solve_timeout given, use the shorter
    # pregen timeout so degenerate boards are skipped quickly instead of
    # burning the full 30-second live window on a hopeless ILP run.
    effective_solve_timeout: float | None = solve_timeout
    if pregen and effective_solve_timeout is None:
        effective_solve_timeout = _PREGEN_SOLVE_TIMEOUT

    rng = random.Random(seed)
    for _ in range(n_attempts):
        result = _attempt_generate(
            rng, difficulty, sets_to_remove,
            min_board_sets, max_board_sets, min_chain_depth, min_disruption,
            pregen=pregen,
            solve_timeout=effective_solve_timeout,
        )
        if result is not None:
            return result

    raise PuzzleGenerationError(
        f"Could not generate a {difficulty!r} puzzle after {n_attempts} attempts."
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _attempt_generate(
    rng: random.Random,
    difficulty: Difficulty,
    sets_to_remove: int = 3,
    min_board_sets: int = 8,
    max_board_sets: int = 14,
    min_chain_depth: int = 0,
    min_disruption: int = 0,
    pregen: bool = False,
    solve_timeout: float | None = None,
) -> PuzzleResult | None:
    joker_lo, joker_hi = _JOKER_COUNTS.get(difficulty, (0, 0))
    n_jokers = rng.randint(joker_lo, joker_hi)
    full_pool = _make_pool(n_jokers)
    all_sets = enumerate_runs(full_pool) + enumerate_groups(full_pool)
    rng.shuffle(all_sets)

    # Scale the board target per difficulty so there are enough sets to sacrifice.
    if difficulty == "custom":
        lo, hi = min_board_sets, max_board_sets
    else:
        lo, hi = _BOARD_SIZES[difficulty]
    n_target = rng.randint(lo, hi)

    board_sets = _pick_compatible_sets(all_sets, n_target)
    if len(board_sets) < 3:
        return None

    board_sets = _assign_copy_ids(board_sets)

    # Inject jokers into the board so they appear as actual board tiles
    # (enumerate_runs/groups don't produce joker-containing templates).
    if n_jokers > 0:
        board_sets = _inject_jokers_into_board(board_sets, n_jokers, rng)

    input_board, rack = _extract_rack(board_sets, difficulty, rng, sets_to_remove)
    if len(rack) < 2:
        return None

    # Verify: solver must place ALL rack tiles.
    state = BoardState(board_sets=input_board, rack=rack)
    solution = solve(state, rules=None, timeout_seconds=solve_timeout)
    if solution.tiles_placed < len(rack):
        return None

    # Compute disruption score and validate against the difficulty band.
    # When pregen=True, use stricter _PREGEN_CONSTRAINTS floors (higher chain_depth
    # and disruption minimums) so pool-drawn puzzles are genuinely harder.
    score = compute_disruption_score(input_board, solution.new_sets)
    if difficulty == "custom":
        effective_lo_d: int = min_disruption
        effective_hi_d: int | None = None
        effective_min_chain: int = min_chain_depth
    elif pregen and difficulty in _PREGEN_CONSTRAINTS:
        pc = _PREGEN_CONSTRAINTS[difficulty]
        effective_lo_d = pc["min_disruption"]
        effective_hi_d = None
        effective_min_chain = pc["min_chain_depth"]
    else:
        effective_lo_d, effective_hi_d = _DISRUPTION_BANDS[difficulty]
        effective_min_chain = _MIN_CHAIN_DEPTHS.get(difficulty, 0)

    if score < effective_lo_d:
        return None
    if effective_hi_d is not None and score > effective_hi_d:
        return None
    if solution.chain_depth < effective_min_chain:
        return None

    # Compute uniqueness (informational, not a gate).
    # Expert/Nightmare/Custom compute it so the stats badge can display it.
    # Large boards with many equivalent rearrangements typically yield non-unique
    # solutions, so gating on uniqueness would make Nightmare generation infeasible.
    # Called once per candidate that passes all other filters.
    is_unique = True
    if _COMPUTES_UNIQUE.get(difficulty, False):
        uniqueness_timeout = _PREGEN_UNIQUENESS_TIMEOUT if pregen else solve_timeout
        is_unique = check_uniqueness(state, solution, timeout_seconds=uniqueness_timeout)

    # Count jokers that actually appear on the board (jokers in sacrificed sets
    # may end up in the rack or get dropped during sampling).
    actual_joker_count = sum(1 for ts in input_board for t in ts.tiles if t.is_joker)

    return PuzzleResult(
        board_sets=input_board,
        rack=rack,
        difficulty=difficulty,
        disruption_score=score,
        chain_depth=solution.chain_depth,
        is_unique=is_unique,
        joker_count=actual_joker_count,
    )


def _make_full_pool() -> BoardState:
    """104 non-joker tiles (4 colors × 13 numbers × 2 copies), no jokers."""
    rack = [Tile(color, n, copy_id) for color in Color for n in range(1, 14) for copy_id in (0, 1)]
    return BoardState(board_sets=[], rack=rack)


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


def _inject_jokers_into_board(
    board_sets: list[TileSet],
    n_jokers: int,
    rng: random.Random,
) -> list[TileSet]:
    """Replace 1–2 random non-joker tiles in board sets with joker tiles.

    The replaced tiles are removed from the board entirely (as if they were
    never placed there). The joker takes the replaced tile's position in the
    set, which remains valid because jokers can substitute for any tile.

    Only replaces tiles in sets with ≥ 4 tiles so that set-type ambiguity is
    preserved: a 3-tile set with a joker replaced would be trivially identifiable,
    reducing the cognitive challenge.
    """
    if n_jokers == 0 or not board_sets:
        return board_sets

    result = [TileSet(type=ts.type, tiles=list(ts.tiles)) for ts in board_sets]

    # Collect (set_index, tile_index) positions eligible for joker replacement.
    candidates: list[tuple[int, int]] = []
    for si, ts in enumerate(result):
        if len(ts.tiles) >= 4:
            for ti in range(len(ts.tiles)):
                if not ts.tiles[ti].is_joker:
                    candidates.append((si, ti))

    if not candidates:
        return result

    n_replace = min(n_jokers, len(candidates))
    chosen = rng.sample(candidates, n_replace)

    for idx, (si, ti) in enumerate(chosen):
        result[si].tiles[ti] = Tile.joker(copy_id=idx)

    return result


def _pick_compatible_sets(all_sets: list[TileSet], n: int) -> list[TileSet]:
    """Greedily select up to n sets that share no physical tile copies."""
    avail: Counter[tuple[Color | None, int | None]] = Counter()
    for color in Color:
        for num in range(1, 14):
            avail[(color, num)] = 2

    selected: list[TileSet] = []
    for ts in all_sets:
        if len(selected) >= n:
            break
        needed: Counter[tuple[Color | None, int | None]] = Counter(
            (t.color, t.number)
            for t in ts.tiles
            if not t.is_joker and t.color is not None and t.number is not None
        )
        if all(avail[k] >= v for k, v in needed.items()):
            selected.append(ts)
            for k, v in needed.items():
                avail[k] -= v

    return selected


def _assign_copy_ids(board_sets: list[TileSet]) -> list[TileSet]:
    """Assign copy_ids 0/1 to distinguish duplicate (color, number) tiles."""
    seen: Counter[tuple[Color | None, int | None]] = Counter()
    result: list[TileSet] = []
    for ts in board_sets:
        new_tiles: list[Tile] = []
        for t in ts.tiles:
            if t.is_joker:
                new_tiles.append(t)
            else:
                copy_id = seen[(t.color, t.number)]
                new_tiles.append(Tile(color=t.color, number=t.number, copy_id=copy_id))
                seen[(t.color, t.number)] += 1
        result.append(TileSet(type=ts.type, tiles=new_tiles))
    return result


def _extract_rack(
    board_sets: list[TileSet],
    difficulty: Difficulty,
    rng: random.Random,
    sets_to_remove: int = 3,
) -> tuple[list[TileSet], list[Tile]]:
    if difficulty == "custom":
        return _extract_custom(board_sets, rng, sets_to_remove)
    n_sacrifice = _SACRIFICE_COUNTS[difficulty]
    rack_size_range = _RACK_SIZES[difficulty]
    return _extract_by_sacrifice(board_sets, rng, n_sacrifice, rack_size_range)


def _extract_by_sacrifice(
    board_sets: list[TileSet],
    rng: random.Random,
    num_sacrifice: int,
    rack_size_range: tuple[int, int],
) -> tuple[list[TileSet], list[Tile]]:
    """Sacrifice num_sacrifice complete sets; sample rack tiles from them.

    Selects num_sacrifice sets to remove entirely from the board. Those sets'
    tiles are the candidate pool; rack_size tiles are sampled from them.
    Because the source sets no longer appear on the board, the player cannot
    trivially re-add any rack tile — they must rearrange the remaining board.

    Tries up to _MAX_SAMPLE_ATTEMPTS different tile samples per board before
    returning failure (the outer loop will then retry with a fresh board).

    Args:
        board_sets:       Current board before extraction.
        rng:              Seeded random instance.
        num_sacrifice:    Number of sets to remove entirely.
        rack_size_range:  (min, max) rack tile count.

    Returns:
        (remaining_board, rack) on success, or (board_sets, []) on failure.
    """
    if len(board_sets) < num_sacrifice + 2:
        return board_sets, []

    # Pick which sets to sacrifice (try a random selection).
    sacrifice_indices = set(rng.sample(range(len(board_sets)), num_sacrifice))
    remaining = [ts for i, ts in enumerate(board_sets) if i not in sacrifice_indices]
    sacrifice_tiles = [
        t for i, ts in enumerate(board_sets) if i in sacrifice_indices for t in ts.tiles
    ]

    rack_min, rack_max = rack_size_range
    rack_size = rng.randint(rack_min, min(rack_max, len(sacrifice_tiles)))
    if rack_size < 2:
        return board_sets, []

    # Try multiple tile samples until we find one with no trivial extension.
    for _ in range(_MAX_SAMPLE_ATTEMPTS):
        rack = rng.sample(sacrifice_tiles, rack_size)
        if not _any_trivial_extension(rack, remaining):
            return remaining, rack

    return board_sets, []  # no valid sample found; caller retries with new board


def _any_trivial_extension(rack: list[Tile], board_sets: list[TileSet]) -> bool:
    """Return True if any rack tile can be directly appended to any board set.

    Uses the same rule_checker as the solver, so the check is authoritative.
    A puzzle is rejected if this returns True — the player would have an
    obvious move without needing to rearrange anything.
    """
    for tile in rack:
        for ts in board_sets:
            if is_valid_set(TileSet(type=ts.type, tiles=ts.tiles + [tile])):
                return True
    return False


def _extract_custom(
    board_sets: list[TileSet], rng: random.Random, n: int
) -> tuple[list[TileSet], list[Tile]]:
    """Remove n complete sets. Rack = all tiles from the removed sets.

    Requires at least n + 2 sets on the board so that at least 2 remain
    after extraction (giving the solver something to work with).
    """
    if len(board_sets) < n + 2:
        return board_sets, []
    indices = set(rng.sample(range(len(board_sets)), n))
    rack = [t for i, ts in enumerate(board_sets) if i in indices for t in ts.tiles]
    remaining = [ts for i, ts in enumerate(board_sets) if i not in indices]
    return remaining, rack
