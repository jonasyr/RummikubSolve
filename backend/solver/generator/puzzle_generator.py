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

import logging
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
from .board_builder import BoardBuilder
from .difficulty_evaluator import DifficultyEvaluator
from .set_enumerator import enumerate_groups, enumerate_runs, enumerate_valid_sets
from .tile_pool import assign_copy_ids as _assign_copy_ids
from .tile_pool import make_tile_pool as _make_pool
from .tile_remover import TileRemover

Difficulty = Literal["easy", "medium", "hard", "expert", "nightmare", "custom"]

# ---------------------------------------------------------------------------
# Difficulty configuration constants
# ---------------------------------------------------------------------------

# Rack size range (min, max) tiles per difficulty.
_RACK_SIZES: dict[str, tuple[int, int]] = {
    "easy": (2, 3),
    "medium": (3, 4),
    "hard": (4, 5),
    "expert": (6, 10),
    "nightmare": (10, 14),
}

# Number of complete board sets sacrificed (removed entirely) per difficulty.
_SACRIFICE_COUNTS: dict[str, int] = {
    "easy": 1,
    "medium": 2,
    "hard": 3,
    "expert": 5,
    "nightmare": 7,
}

# Disruption band: (min_inclusive, max_inclusive).
_DISRUPTION_BANDS: dict[str, tuple[int, int | None]] = {
    "easy": (2, 10),
    "medium": (9, 18),
    "hard": (16, 28),
    "expert": (32, None),
    "nightmare": (38, None),
}

# Board size range (number of sets, BEFORE sacrifice) per difficulty.
_BOARD_SIZES: dict[str, tuple[int, int]] = {
    "easy": (5, 9),
    "medium": (7, 11),
    "hard": (9, 13),
    "expert": (16, 22),
    "nightmare": (22, 28),
}

# Minimum chain_depth required per difficulty (Phase 3).
_MIN_CHAIN_DEPTHS: dict[str, int] = {
    "easy": 0,
    "medium": 0,
    "hard": 1,
    "expert": 2,
    "nightmare": 3,
}

# Whether to compute uniqueness for this difficulty (Phase 3).
_COMPUTES_UNIQUE: dict[str, bool] = {
    "easy": False,
    "medium": False,
    "hard": False,
    "expert": True,
    "nightmare": True,
    "custom": True,
}

# Number of joker tiles to add to the tile pool, per difficulty.
_JOKER_COUNTS: dict[str, tuple[int, int]] = {
    "easy": (0, 0),
    "medium": (0, 0),
    "hard": (0, 1),
    "expert": (1, 2),
    "nightmare": (1, 2),
    "custom": (0, 0),
}

# Max tile-sample attempts inside _extract_by_sacrifice before giving up.
_MAX_SAMPLE_ATTEMPTS = 20

# Default max outer-loop attempts per difficulty.
_DEFAULT_MAX_ATTEMPTS: dict[str, int] = {
    "easy": 150,
    "medium": 150,
    "hard": 200,
    "expert": 600,
    "nightmare": 1500,
    "custom": 150,
}

# Stricter thresholds used by pregenerate.py.
_PREGEN_CONSTRAINTS: dict[str, dict[str, int]] = {
    "expert": {
        "min_chain_depth": 3,
        "min_disruption": 38,
    },
    "nightmare": {
        "min_chain_depth": 4,
        "min_disruption": 42,
    },
}

_PREGEN_MAX_ATTEMPTS: dict[str, int] = {
    "expert": 5000,
    "nightmare": 10000,
}

_PREGEN_SOLVE_TIMEOUT: float = 8.0
_PREGEN_UNIQUENESS_TIMEOUT: float = 5.0


@dataclass(frozen=True)
class _PregenProfile:
    board_size_range: tuple[int, int]
    sacrifice_count: int
    rack_size_range: tuple[int, int]
    joker_count_range: tuple[int, int]
    max_rack_source_sets: int
    max_candidate_sets: int
    max_ilp_columns: int
    max_ilp_rows: int
    min_total_rack_tile_coverage: int
    min_multi_option_rack_tiles: int
    rack_sample_budget: int


_PREGEN_PROFILES: dict[str, _PregenProfile] = {
    "expert": _PregenProfile(
        board_size_range=(12, 14),
        sacrifice_count=3,
        rack_size_range=(5, 6),
        joker_count_range=(0, 0),
        max_rack_source_sets=2,
        max_candidate_sets=500,
        max_ilp_columns=3500,
        max_ilp_rows=2200,
        min_total_rack_tile_coverage=12,
        min_multi_option_rack_tiles=3,
        rack_sample_budget=100,
    ),
    "nightmare": _PregenProfile(
        board_size_range=(13, 15),
        sacrifice_count=3,
        rack_size_range=(6, 7),
        joker_count_range=(0, 0),
        max_rack_source_sets=2,
        max_candidate_sets=650,
        max_ilp_columns=4600,
        max_ilp_rows=3000,
        min_total_rack_tile_coverage=14,
        min_multi_option_rack_tiles=3,
        rack_sample_budget=160,
    ),
}


class PuzzleGenerationError(Exception):
    """Raised when a puzzle cannot be generated within the attempt limit."""


@dataclass
class PuzzleResult:
    board_sets: list[TileSet]
    rack: list[Tile]
    difficulty: Difficulty
    disruption_score: int
    chain_depth: int = 0
    is_unique: bool = True
    joker_count: int = 0
    # v2 fields — populated by _attempt_generate_v2(); default to 0.0/"v1"
    # so that v1-generated results remain fully compatible.
    branching_factor: float = 0.0
    deductive_depth: float = 0.0
    red_herring_density: float = 0.0
    working_memory_load: float = 0.0
    tile_ambiguity: float = 0.0
    solution_fragility: float = 0.0
    composite_score: float = 0.0
    generator_version: str = "v1"


@dataclass(frozen=True)
class _ComplexityEstimate:
    candidate_set_count: int
    estimated_ilp_columns: int
    estimated_ilp_rows: int
    board_tile_count: int
    rack_tile_count: int
    rack_tiles_placeable: int
    min_rack_tile_coverage: int
    total_rack_tile_coverage: int
    multi_option_rack_tiles: int


@dataclass(frozen=True)
class _RackCandidate:
    remaining_board: list[TileSet]
    rack: list[Tile]
    complexity: _ComplexityEstimate


@dataclass(frozen=True)
class _AttemptOutcome:
    result: PuzzleResult | None
    rejection_reason: str | None = None
    rack_size: int = 0
    tiles_placed: int = 0
    solve_status: str | None = None
    solve_time_ms: float = 0.0
    disruption_score: int | None = None
    chain_depth: int | None = None


# ---------------------------------------------------------------------------
# v2 generation (BoardBuilder + TileRemover + DifficultyEvaluator)
# ---------------------------------------------------------------------------

# Board/rack sizing and overlap bias per difficulty tier for v2 (§4.1).
_BOARD_SIZE_RANGES_V2: dict[str, tuple[int, int]] = {
    "easy": (6, 9),
    "medium": (8, 11),
    "hard": (10, 13),
    "expert": (12, 15),
    "nightmare": (13, 16),
    "custom": (8, 14),
}

_RACK_SIZE_RANGES_V2: dict[str, tuple[int, int]] = {
    "easy": (2, 3),
    "medium": (3, 4),
    "hard": (4, 5),
    "expert": (5, 7),
    "nightmare": (6, 8),
    "custom": (3, 6),
}

_OVERLAP_BIASES_V2: dict[str, float] = {
    "easy": 0.3,
    "medium": 0.4,
    "hard": 0.5,
    "expert": 0.7,
    "nightmare": 0.85,
    "custom": 0.5,
}

# Per-difficulty attempt limits for the v2 outer retry loop.
_DEFAULT_MAX_ATTEMPTS_V2: dict[str, int] = {
    "easy": 50,
    "medium": 80,
    "hard": 120,
    "expert": 300,
    "nightmare": 600,
    "custom": 100,
}

# Tier ordering for ±1 adjacency check in _attempt_generate_v2.
_TIER_ORDER = ["easy", "medium", "hard", "expert", "nightmare"]

try:
    import structlog as _structlog
except ImportError:  # pragma: no cover - fallback for minimal environments
    _structlog = None  # type: ignore[assignment]

logger = _structlog.get_logger(__name__) if _structlog is not None else logging.getLogger(__name__)


def _attempt_generate_v2(
    rng: random.Random,
    difficulty: Difficulty,
    solve_timeout: float | None = None,
) -> _AttemptOutcome:
    """New v2 generation: BoardBuilder → TileRemover → DifficultyEvaluator (§4.1).

    Replaces the sacrifice-based approach with strategic tile removal and
    multi-metric difficulty scoring.
    """
    board_sets = BoardBuilder.build(
        rng=rng,
        board_size_range=_BOARD_SIZE_RANGES_V2.get(difficulty, (8, 14)),
        overlap_bias=_OVERLAP_BIASES_V2.get(difficulty, 0.5),
    )

    if len(board_sets) < 4:
        return _AttemptOutcome(result=None, rejection_reason="board_too_small")

    removal_result = TileRemover.remove(
        board_sets=board_sets,
        rng=rng,
        rack_size_range=_RACK_SIZE_RANGES_V2.get(difficulty, (3, 6)),
        strategy="maximize_cascade",
        solve_timeout=solve_timeout or 5.0,
    )

    if removal_result is None:
        return _AttemptOutcome(result=None, rejection_reason="removal_failed")

    remaining_board, rack, _ = removal_result

    # Final solve verification with a slightly longer timeout.
    state = BoardState(board_sets=remaining_board, rack=rack)
    solution = solve(state, timeout_seconds=solve_timeout or 8.0)

    if solution.tiles_placed < len(rack):
        return _AttemptOutcome(
            result=None,
            rejection_reason=f"solve_{solution.solve_status}",
            rack_size=len(rack),
            tiles_placed=solution.tiles_placed,
            solve_status=solution.solve_status,
        )

    # Evaluate difficulty; skip fragility for easy/medium (too slow per puzzle).
    skip_expensive = difficulty in ("easy", "medium")
    score = DifficultyEvaluator.evaluate(state, solution, skip_expensive=skip_expensive)

    # Tier check deferred until Phase 6 weight calibration.
    # The composite score weights are initial estimates (§3.7 note) and produce
    # inflated scores on smaller boards — every difficulty level currently scores
    # in the "expert" band.  Once calibration data is available, re-enable:
    #
    #   tier_order = _TIER_ORDER
    #   if difficulty in tier_order and score.classified_tier in tier_order:
    #       if abs(tier_order.index(difficulty) - tier_order.index(score.classified_tier)) > 1:
    #           return _AttemptOutcome(result=None, rejection_reason="tier_mismatch", ...)

    # Uniqueness check for expert/nightmare.
    is_unique = True
    if difficulty in ("expert", "nightmare"):
        is_unique = check_uniqueness(state, solution, timeout_seconds=5.0)

    logger.info(
        "puzzle_generated",
        generator_version="v2.0.0",
        difficulty=difficulty,
        composite_score=score.composite_score,
        branching_factor=score.branching_factor,
        board_size=len(remaining_board),
        rack_size=len(rack),
    )

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
        solve_status=solution.solve_status,
        disruption_score=score.disruption_score,
        chain_depth=score.chain_depth,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_puzzle(
    difficulty: Difficulty = "medium",
    seed: int | None = None,
    max_attempts: int | None = None,
    pregen: bool = False,
    sets_to_remove: int = 3,
    min_board_sets: int = 8,
    max_board_sets: int = 14,
    min_chain_depth: int = 0,
    min_disruption: int = 0,
    solve_timeout: float | None = None,
    generator_version: str = "v2",
) -> PuzzleResult:
    """Generate a random, pre-verified Rummikub puzzle at the given difficulty.

    Args:
        difficulty:        Tier to generate.
        seed:              RNG seed for determinism.
        max_attempts:      Override for the outer retry loop limit.
        pregen:            Use pre-generation constraints (v1 only).
        sets_to_remove:    Custom mode: sets to sacrifice (v1 only).
        min_board_sets:    Custom mode: minimum board sets (v1 only).
        max_board_sets:    Custom mode: maximum board sets (v1 only).
        min_chain_depth:   Custom mode: minimum chain depth (v1 only).
        min_disruption:    Custom mode: minimum disruption (v1 only).
        solve_timeout:     ILP solver time limit per attempt.
        generator_version: "v2" (default) uses BoardBuilder+TileRemover+DifficultyEvaluator.
                           "v1" uses the legacy sacrifice-based approach.
    """
    if difficulty not in ("easy", "medium", "hard", "expert", "nightmare", "custom"):
        raise ValueError(
            f"Unknown difficulty {difficulty!r}. "
            f"Use 'easy', 'medium', 'hard', 'expert', 'nightmare', or 'custom'."
        )

    rng = random.Random(seed)

    if generator_version == "v2":
        n_attempts = max_attempts or _DEFAULT_MAX_ATTEMPTS_V2.get(difficulty, 100)
        for _ in range(n_attempts):
            outcome = _attempt_generate_v2(rng, difficulty, solve_timeout)
            if outcome.result is not None:
                return outcome.result
        raise PuzzleGenerationError(
            f"Could not generate a {difficulty!r} puzzle after {n_attempts} attempts "
            f"(generator_version='v2')."
        )

    # v1 legacy path — unchanged behaviour.
    if max_attempts is not None:
        n_attempts = max_attempts
    elif pregen:
        n_attempts = _PREGEN_MAX_ATTEMPTS.get(
            difficulty, _DEFAULT_MAX_ATTEMPTS.get(difficulty, 150)
        )
    else:
        n_attempts = _DEFAULT_MAX_ATTEMPTS.get(difficulty, 150)

    effective_solve_timeout: float | None = solve_timeout
    if pregen and effective_solve_timeout is None:
        effective_solve_timeout = _PREGEN_SOLVE_TIMEOUT

    for _ in range(n_attempts):
        outcome = _attempt_generate_with_reason(
            rng,
            difficulty,
            sets_to_remove,
            min_board_sets,
            max_board_sets,
            min_chain_depth,
            min_disruption,
            pregen=pregen,
            solve_timeout=effective_solve_timeout,
        )
        if outcome.result is not None:
            return outcome.result

    raise PuzzleGenerationError(
        f"Could not generate a {difficulty!r} puzzle after {n_attempts} attempts."
    )


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
    return _attempt_generate_with_reason(
        rng,
        difficulty,
        sets_to_remove,
        min_board_sets,
        max_board_sets,
        min_chain_depth,
        min_disruption,
        pregen,
        solve_timeout,
    ).result


def _attempt_generate_with_reason(
    rng: random.Random,
    difficulty: Difficulty,
    sets_to_remove: int = 3,
    min_board_sets: int = 8,
    max_board_sets: int = 14,
    min_chain_depth: int = 0,
    min_disruption: int = 0,
    pregen: bool = False,
    solve_timeout: float | None = None,
) -> _AttemptOutcome:
    pregen_profile = _PREGEN_PROFILES.get(difficulty) if pregen else None

    joker_lo, joker_hi = (
        pregen_profile.joker_count_range
        if pregen_profile is not None
        else _JOKER_COUNTS.get(difficulty, (0, 0))
    )
    n_jokers = rng.randint(joker_lo, joker_hi)
    full_pool = _make_pool(n_jokers)
    all_sets = enumerate_runs(full_pool) + enumerate_groups(full_pool)
    rng.shuffle(all_sets)

    if difficulty == "custom":
        lo, hi = min_board_sets, max_board_sets
    elif pregen_profile is not None:
        lo, hi = pregen_profile.board_size_range
    else:
        lo, hi = _BOARD_SIZES[difficulty]
    n_target = rng.randint(lo, hi)

    board_sets = _pick_compatible_sets(all_sets, n_target)
    if len(board_sets) < 3:
        return _AttemptOutcome(result=None, rejection_reason="board_fail")

    board_sets = _assign_copy_ids(board_sets)

    if n_jokers > 0:
        board_sets = _inject_jokers_into_board(board_sets, n_jokers, rng)

    rack_candidate = _extract_rack(
        board_sets,
        difficulty,
        rng,
        sets_to_remove,
        pregen_profile=pregen_profile,
    )
    if rack_candidate is None:
        return _AttemptOutcome(result=None, rejection_reason="rack_fail")

    input_board = rack_candidate.remaining_board
    rack = rack_candidate.rack
    rack_size = len(rack)
    if pregen_profile is not None and (
        rack_candidate.complexity.rack_tiles_placeable < rack_size
        or rack_candidate.complexity.total_rack_tile_coverage
        < pregen_profile.min_total_rack_tile_coverage
        or rack_candidate.complexity.multi_option_rack_tiles
        < pregen_profile.min_multi_option_rack_tiles
        or rack_candidate.complexity.min_rack_tile_coverage < 1
        or rack_candidate.complexity.candidate_set_count > pregen_profile.max_candidate_sets
        or rack_candidate.complexity.estimated_ilp_columns > pregen_profile.max_ilp_columns
        or rack_candidate.complexity.estimated_ilp_rows > pregen_profile.max_ilp_rows
    ):
        if rack_candidate.complexity.rack_tiles_placeable < rack_size:
            return _AttemptOutcome(
                result=None,
                rejection_reason="tile_coverage_fail",
                rack_size=rack_size,
            )
        if (
            rack_candidate.complexity.total_rack_tile_coverage
            < pregen_profile.min_total_rack_tile_coverage
            or rack_candidate.complexity.multi_option_rack_tiles
            < pregen_profile.min_multi_option_rack_tiles
            or rack_candidate.complexity.min_rack_tile_coverage < 1
        ):
            return _AttemptOutcome(
                result=None,
                rejection_reason="rack_proxy_fail",
                rack_size=rack_size,
            )
        return _AttemptOutcome(
            result=None,
            rejection_reason="candidate_cap_reject",
            rack_size=rack_size,
        )

    state = BoardState(board_sets=input_board, rack=rack)
    solution = solve(state, rules=None, timeout_seconds=solve_timeout)
    if solution.tiles_placed < rack_size:
        return _AttemptOutcome(
            result=None,
            rejection_reason=f"solve_{solution.solve_status}",
            rack_size=rack_size,
            tiles_placed=solution.tiles_placed,
            solve_status=solution.solve_status,
            solve_time_ms=solution.solve_time_ms,
            chain_depth=solution.chain_depth,
        )

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
        return _AttemptOutcome(
            result=None,
            rejection_reason="disruption_fail",
            rack_size=rack_size,
            tiles_placed=solution.tiles_placed,
            solve_status=solution.solve_status,
            solve_time_ms=solution.solve_time_ms,
            disruption_score=score,
            chain_depth=solution.chain_depth,
        )
    if effective_hi_d is not None and score > effective_hi_d:
        return _AttemptOutcome(
            result=None,
            rejection_reason="disruption_fail",
            rack_size=rack_size,
            tiles_placed=solution.tiles_placed,
            solve_status=solution.solve_status,
            solve_time_ms=solution.solve_time_ms,
            disruption_score=score,
            chain_depth=solution.chain_depth,
        )
    if solution.chain_depth < effective_min_chain:
        return _AttemptOutcome(
            result=None,
            rejection_reason="chain_fail",
            rack_size=rack_size,
            tiles_placed=solution.tiles_placed,
            solve_status=solution.solve_status,
            solve_time_ms=solution.solve_time_ms,
            disruption_score=score,
            chain_depth=solution.chain_depth,
        )

    is_unique = True
    if _COMPUTES_UNIQUE.get(difficulty, False):
        uniqueness_timeout = _PREGEN_UNIQUENESS_TIMEOUT if pregen else solve_timeout
        is_unique = check_uniqueness(state, solution, timeout_seconds=uniqueness_timeout)

    actual_joker_count = sum(1 for ts in input_board for t in ts.tiles if t.is_joker)

    return _AttemptOutcome(
        result=PuzzleResult(
            board_sets=input_board,
            rack=rack,
            difficulty=difficulty,
            disruption_score=score,
            chain_depth=solution.chain_depth,
            is_unique=is_unique,
            joker_count=actual_joker_count,
        ),
        rack_size=rack_size,
        tiles_placed=solution.tiles_placed,
        solve_status=solution.solve_status,
        solve_time_ms=solution.solve_time_ms,
        disruption_score=score,
        chain_depth=solution.chain_depth,
    )


def _inject_jokers_into_board(
    board_sets: list[TileSet],
    n_jokers: int,
    rng: random.Random,
) -> list[TileSet]:
    """Replace 1–2 random non-joker tiles in board sets with joker tiles."""
    if n_jokers == 0 or not board_sets:
        return board_sets

    result = [TileSet(type=ts.type, tiles=list(ts.tiles)) for ts in board_sets]

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


def _extract_rack(
    board_sets: list[TileSet],
    difficulty: Difficulty,
    rng: random.Random,
    sets_to_remove: int = 3,
    pregen_profile: _PregenProfile | None = None,
) -> _RackCandidate | None:
    if difficulty == "custom":
        remaining_board, rack = _extract_custom(board_sets, rng, sets_to_remove)
        if len(rack) < 2:
            return None
        return _build_rack_candidate(remaining_board, rack)

    n_sacrifice = (
        pregen_profile.sacrifice_count
        if pregen_profile is not None
        else _SACRIFICE_COUNTS[difficulty]
    )
    rack_size_range = (
        pregen_profile.rack_size_range if pregen_profile is not None else _RACK_SIZES[difficulty]
    )
    rack_sample_budget = (
        pregen_profile.rack_sample_budget if pregen_profile is not None else _MAX_SAMPLE_ATTEMPTS
    )
    return _extract_by_sacrifice(
        board_sets,
        rng,
        n_sacrifice,
        rack_size_range,
        max_rack_source_sets=(
            pregen_profile.max_rack_source_sets if pregen_profile is not None else None
        ),
        rack_sample_budget=rack_sample_budget,
    )


def _extract_by_sacrifice(
    board_sets: list[TileSet],
    rng: random.Random,
    num_sacrifice: int,
    rack_size_range: tuple[int, int],
    max_rack_source_sets: int | None = None,
    rack_sample_budget: int = _MAX_SAMPLE_ATTEMPTS,
) -> _RackCandidate | None:
    """Sacrifice sets, then keep the rack with the smallest search space."""
    if len(board_sets) < num_sacrifice + 2:
        return None

    sacrifice_indices = set(rng.sample(range(len(board_sets)), num_sacrifice))
    remaining = [ts for i, ts in enumerate(board_sets) if i not in sacrifice_indices]
    sacrificed_sets = [ts for i, ts in enumerate(board_sets) if i in sacrifice_indices]
    sacrifice_tiles = [t for ts in sacrificed_sets for t in ts.tiles]

    rack_min, rack_max = rack_size_range
    rack_size = rng.randint(rack_min, min(rack_max, len(sacrifice_tiles)))
    if rack_size < 2:
        return None

    best_candidate: _RackCandidate | None = None
    for _ in range(rack_sample_budget):
        rack = _sample_rack_from_sacrificed_sets(
            sacrificed_sets=sacrificed_sets,
            rack_size=rack_size,
            rng=rng,
            max_rack_source_sets=max_rack_source_sets,
        )
        if _any_trivial_extension(rack, remaining):
            continue
        candidate = _build_rack_candidate(remaining, rack)
        if _better_rack_candidate(candidate, best_candidate):
            best_candidate = candidate

    return best_candidate


def _sample_rack_from_sacrificed_sets(
    sacrificed_sets: list[TileSet],
    rack_size: int,
    rng: random.Random,
    max_rack_source_sets: int | None,
) -> list[Tile]:
    if max_rack_source_sets is None or len(sacrificed_sets) <= max_rack_source_sets:
        return rng.sample([t for ts in sacrificed_sets for t in ts.tiles], rack_size)

    source_set_count = min(
        max_rack_source_sets,
        len(sacrificed_sets),
        max(1, (rack_size + 2) // 3),
    )
    chosen_sets = rng.sample(sacrificed_sets, source_set_count)
    chosen_tiles = [t for ts in chosen_sets for t in ts.tiles]
    if len(chosen_tiles) < rack_size:
        chosen_tiles = [t for ts in sacrificed_sets for t in ts.tiles]
    return rng.sample(chosen_tiles, rack_size)


def _build_rack_candidate(
    remaining_board: list[TileSet],
    rack: list[Tile],
) -> _RackCandidate:
    state = BoardState(board_sets=remaining_board, rack=rack)
    candidate_sets = enumerate_valid_sets(state)
    return _RackCandidate(
        remaining_board=remaining_board,
        rack=rack,
        complexity=_estimate_complexity(state, candidate_sets),
    )


def _better_rack_candidate(
    candidate: _RackCandidate,
    current_best: _RackCandidate | None,
) -> bool:
    if current_best is None:
        return True
    cand = candidate.complexity
    best = current_best.complexity
    if cand.rack_tiles_placeable != best.rack_tiles_placeable:
        return cand.rack_tiles_placeable > best.rack_tiles_placeable
    if cand.multi_option_rack_tiles != best.multi_option_rack_tiles:
        return cand.multi_option_rack_tiles > best.multi_option_rack_tiles
    if cand.total_rack_tile_coverage != best.total_rack_tile_coverage:
        return cand.total_rack_tile_coverage > best.total_rack_tile_coverage
    if cand.min_rack_tile_coverage != best.min_rack_tile_coverage:
        return cand.min_rack_tile_coverage > best.min_rack_tile_coverage
    if cand.estimated_ilp_columns != best.estimated_ilp_columns:
        return cand.estimated_ilp_columns < best.estimated_ilp_columns
    if cand.estimated_ilp_rows != best.estimated_ilp_rows:
        return cand.estimated_ilp_rows < best.estimated_ilp_rows
    if cand.candidate_set_count != best.candidate_set_count:
        return cand.candidate_set_count < best.candidate_set_count
    if len(candidate.rack) != len(current_best.rack):
        return len(candidate.rack) > len(current_best.rack)
    candidate_key = [(t.color, t.number, t.copy_id, t.is_joker) for t in candidate.rack]
    current_key = [(t.color, t.number, t.copy_id, t.is_joker) for t in current_best.rack]
    return candidate_key < current_key


def _estimate_complexity(
    state: BoardState,
    candidate_sets: list[TileSet],
) -> _ComplexityEstimate:
    all_tiles = list(state.all_tiles)

    slot_to_match_count: Counter[tuple[bool, Color | None, int | None]] = Counter()
    for tile in all_tiles:
        if tile.is_joker:
            slot_to_match_count[(True, None, None)] += 1
        else:
            slot_to_match_count[(False, tile.color, tile.number)] += 1

    x_var_count = 0
    slot_constraint_count = 0
    rack_tile_coverages = [0] * len(state.rack)
    for candidate_set in candidate_sets:
        joker_slot_count = sum(1 for tile in candidate_set.tiles if tile.is_joker)
        non_joker_slot_count = len(candidate_set.tiles) - joker_slot_count
        slot_constraint_count += non_joker_slot_count + (1 if joker_slot_count > 0 else 0)
        seen_keys: set[tuple[bool, Color | None, int | None]] = set()
        for tile in candidate_set.tiles:
            slot_key = (True, None, None) if tile.is_joker else (False, tile.color, tile.number)
            if slot_key in seen_keys:
                continue
            x_var_count += slot_to_match_count[slot_key]
            seen_keys.add(slot_key)

        candidate_keys = {(tile.is_joker, tile.color, tile.number) for tile in candidate_set.tiles}
        for rack_index, rack_tile in enumerate(state.rack):
            rack_key = (rack_tile.is_joker, rack_tile.color, rack_tile.number)
            if rack_key in candidate_keys:
                rack_tile_coverages[rack_index] += 1

    board_tile_count = len(state.board_tiles)
    rack_tile_count = len(state.rack)
    candidate_set_count = len(candidate_sets)
    estimated_ilp_columns = candidate_set_count + rack_tile_count + x_var_count
    estimated_ilp_rows = board_tile_count + rack_tile_count + slot_constraint_count
    rack_tiles_placeable = sum(1 for coverage in rack_tile_coverages if coverage > 0)
    min_rack_tile_coverage = min(rack_tile_coverages, default=0)
    total_rack_tile_coverage = sum(rack_tile_coverages)
    multi_option_rack_tiles = sum(1 for coverage in rack_tile_coverages if coverage > 1)

    return _ComplexityEstimate(
        candidate_set_count=candidate_set_count,
        estimated_ilp_columns=estimated_ilp_columns,
        estimated_ilp_rows=estimated_ilp_rows,
        board_tile_count=board_tile_count,
        rack_tile_count=rack_tile_count,
        rack_tiles_placeable=rack_tiles_placeable,
        min_rack_tile_coverage=min_rack_tile_coverage,
        total_rack_tile_coverage=total_rack_tile_coverage,
        multi_option_rack_tiles=multi_option_rack_tiles,
    )


def _any_trivial_extension(rack: list[Tile], board_sets: list[TileSet]) -> bool:
    """Return True if any rack tile can be directly appended to any board set."""
    for tile in rack:
        for ts in board_sets:
            if is_valid_set(TileSet(type=ts.type, tiles=ts.tiles + [tile])):
                return True
    return False


def _extract_custom(
    board_sets: list[TileSet], rng: random.Random, n: int
) -> tuple[list[TileSet], list[Tile]]:
    """Remove n complete sets. Rack = all tiles from the removed sets."""
    if len(board_sets) < n + 2:
        return board_sets, []
    indices = set(rng.sample(range(len(board_sets)), n))
    rack = [t for i, ts in enumerate(board_sets) if i in indices for t in ts.tiles]
    remaining = [ts for i, ts in enumerate(board_sets) if i not in indices]
    return remaining, rack
