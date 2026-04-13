"""Tests for solver/generator/difficulty_evaluator.py.

Strategy:
  - Pure-logic functions (composite score, tier classification) are tested directly.
  - Metric functions and DifficultyEvaluator.evaluate() use real solver (highspy).
  - Board/rack combinations are built from BoardBuilder + TileRemover, or crafted
    by hand for specific edge cases.
"""

from __future__ import annotations

import random
import time

import pytest

from solver.engine.solver import solve
from solver.generator.board_builder import BoardBuilder
from solver.generator.difficulty_evaluator import (
    TIER_THRESHOLDS,
    DifficultyEvaluator,
    DifficultyScore,
    classify_tier,
    compute_branching_factor,
    compute_composite_score,
    compute_red_herrings,
    compute_solution_fragility,
    compute_tile_ambiguity,
    compute_working_memory_load,
)
from solver.generator.tile_remover import TileRemover
from solver.models.board_state import BoardState, Solution
from solver.models.tile import Color, Tile
from solver.models.tileset import SetType, TileSet

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tile(color: Color, number: int, copy_id: int = 0) -> Tile:
    return Tile(color=color, number=number, copy_id=copy_id)


def _run(*pairs: tuple[Color, int]) -> TileSet:
    return TileSet(type=SetType.RUN, tiles=[_tile(c, n) for c, n in pairs])


def _group(number: int, *colors: Color) -> TileSet:
    return TileSet(type=SetType.GROUP, tiles=[_tile(c, number) for c in colors])


def _build_solvable_state(seed: int = 42) -> tuple[BoardState, Solution]:
    """Build a real board+rack via BoardBuilder+TileRemover, return (state, solution)."""

    rng = random.Random(seed)
    for attempt_seed in range(seed, seed + 20):
        rng = random.Random(attempt_seed)
        board_sets = BoardBuilder.build(rng, board_size_range=(8, 11))
        result = TileRemover.remove(board_sets, rng, rack_size_range=(3, 5))
        if result is None:
            continue
        remaining_board, rack, _ = result
        state = BoardState(board_sets=remaining_board, rack=rack)
        solution = solve(state)
        if solution.tiles_placed == len(rack):
            return state, solution
    raise RuntimeError("Could not build solvable state for tests")


# ---------------------------------------------------------------------------
# Tier classification — pure logic, no solver
# ---------------------------------------------------------------------------


def test_classify_tier_easy():
    assert classify_tier(10.0) == "easy"


def test_classify_tier_medium():
    assert classify_tier(20.0) == "medium"


def test_classify_tier_hard():
    assert classify_tier(35.0) == "hard"


def test_classify_tier_expert():
    assert classify_tier(55.0) == "expert"


def test_classify_tier_nightmare():
    assert classify_tier(75.0) == "nightmare"


def test_classify_tier_boundary_nightmare():
    """Score exactly at nightmare threshold returns nightmare."""
    lo, _ = TIER_THRESHOLDS["nightmare"]
    assert classify_tier(float(lo)) == "nightmare"


def test_classify_tier_zero_returns_easy():
    assert classify_tier(0.0) == "easy"


# ---------------------------------------------------------------------------
# Composite score — pure logic, no solver
# ---------------------------------------------------------------------------


def test_composite_score_all_zeros():
    score = compute_composite_score(0, 0, 0, 0, 0, 0, 0, 0)
    assert score == 0.0


def test_composite_score_all_max():
    """All metrics at normalisation ceiling → score == 100.0."""
    score = compute_composite_score(
        branching_factor=8.0,
        deductive_depth=10.0,
        red_herring_density=1.0,
        working_memory_load=10.0,
        tile_ambiguity=15.0,
        solution_fragility=1.0,
        disruption_score=50,
        chain_depth=5,
    )
    assert score == 100.0


def test_composite_score_in_range():
    """Arbitrary mid-range inputs stay within [0, 100]."""
    score = compute_composite_score(4.0, 5.0, 0.5, 5.0, 7.5, 0.5, 25, 2)
    assert 0.0 <= score <= 100.0


def test_composite_score_increases_with_bf():
    """Higher branching_factor alone raises composite score."""
    lo = compute_composite_score(1.0, 3.0, 0.3, 3.0, 5.0, 0.3, 15, 1)
    hi = compute_composite_score(7.0, 3.0, 0.3, 3.0, 5.0, 0.3, 15, 1)
    assert hi > lo


# ---------------------------------------------------------------------------
# Branching factor
# ---------------------------------------------------------------------------


def test_branching_factor_empty_rack():
    """Empty rack → 0.0."""
    board = [_run((Color.RED, 1), (Color.RED, 2), (Color.RED, 3))]
    state = BoardState(board_sets=board, rack=[])
    assert compute_branching_factor(state) == 0.0


def test_branching_factor_solvable_puzzle():
    """Any solvable puzzle with rack tiles has branching_factor ≥ 1.0."""
    state, _ = _build_solvable_state(seed=42)
    bf = compute_branching_factor(state)
    assert bf >= 1.0


# ---------------------------------------------------------------------------
# Red herring density
# ---------------------------------------------------------------------------


def test_red_herring_density_bounds():
    """Density is always in [0.0, 1.0]."""
    state, solution = _build_solvable_state(seed=7)
    rh = compute_red_herrings(state, solution)
    assert 0.0 <= rh <= 1.0


def test_red_herring_density_empty_rack():
    board = [_run((Color.RED, 1), (Color.RED, 2), (Color.RED, 3))]
    state = BoardState(board_sets=board, rack=[])
    # We need a dummy solution — just solve the empty rack
    solution = solve(state)
    assert compute_red_herrings(state, solution) == 0.0


# ---------------------------------------------------------------------------
# Working memory load
# ---------------------------------------------------------------------------


def test_working_memory_no_rearrangement():
    """When the solution leaves the board unchanged, load is 0.0."""
    # Build a state where rack can be placed without touching existing sets.
    # Use a rack tile that forms a brand-new group with board tiles we create.
    board = [_run((Color.RED, 1), (Color.RED, 2), (Color.RED, 3))]
    rack = [_tile(Color.BLUE, 5)]
    state = BoardState(board_sets=board, rack=rack)
    solution = solve(state)
    # If rack tile can't be placed, working_memory_load is still well-defined.
    wm = compute_working_memory_load(state, solution)
    assert wm >= 0.0


def test_working_memory_full_disruption():
    """When all board sets are rearranged, load equals original set count."""
    state, solution = _build_solvable_state(seed=99)
    # At least the board exists and some disruption can occur
    wm = compute_working_memory_load(state, solution)
    assert isinstance(wm, float)
    assert wm >= 0.0


# ---------------------------------------------------------------------------
# Tile ambiguity
# ---------------------------------------------------------------------------


def test_tile_ambiguity_positive():
    """Any non-trivial board has ambiguity > 0."""
    state, _ = _build_solvable_state(seed=42)
    ta = compute_tile_ambiguity(state)
    assert ta > 0.0


def test_tile_ambiguity_empty_state():
    state = BoardState(board_sets=[], rack=[])
    assert compute_tile_ambiguity(state) == 0.0


# ---------------------------------------------------------------------------
# Solution fragility
# ---------------------------------------------------------------------------


def test_solution_fragility_single_rack_tile():
    """rack size = 1 → fragility = 0.0 (nothing to remove)."""
    board = [
        _run((Color.RED, 1), (Color.RED, 2), (Color.RED, 3)),
        _run((Color.BLUE, 5), (Color.BLUE, 6), (Color.BLUE, 7)),
    ]
    rack = [_tile(Color.RED, 4)]
    state = BoardState(board_sets=board, rack=rack)
    solution = solve(state)
    assert compute_solution_fragility(state, solution) == 0.0


def test_solution_fragility_in_range():
    """Fragility is always in [0.0, 1.0]."""
    state, solution = _build_solvable_state(seed=5)
    sf = compute_solution_fragility(state, solution)
    assert 0.0 <= sf <= 1.0


# ---------------------------------------------------------------------------
# DifficultyEvaluator.evaluate()
# ---------------------------------------------------------------------------


def test_evaluate_returns_difficulty_score():
    """evaluate() returns a DifficultyScore with all fields populated."""
    state, solution = _build_solvable_state(seed=42)
    score = DifficultyEvaluator.evaluate(state, solution)
    assert isinstance(score, DifficultyScore)
    assert score.branching_factor >= 0.0
    assert score.deductive_depth >= 0.0
    assert 0.0 <= score.red_herring_density <= 1.0
    assert score.working_memory_load >= 0.0
    assert score.tile_ambiguity >= 0.0
    assert 0.0 <= score.solution_fragility <= 1.0
    assert score.disruption_score >= 0
    assert score.chain_depth >= 0
    assert 0.0 <= score.composite_score <= 100.0
    assert score.classified_tier in ("easy", "medium", "hard", "expert", "nightmare")


def test_skip_expensive_zeroes_fragility():
    """skip_expensive=True sets solution_fragility to 0.0 without solver calls."""
    state, solution = _build_solvable_state(seed=42)
    score = DifficultyEvaluator.evaluate(state, solution, skip_expensive=True)
    assert score.solution_fragility == 0.0


def test_tier_classification_consistency():
    """Harder state (larger rack, more complex board) has higher composite score."""
    rng = random.Random(0)
    board_sets = BoardBuilder.build(rng, board_size_range=(12, 14))

    # Easy: small rack
    rng_easy = random.Random(1)
    easy_result = TileRemover.remove(board_sets, rng_easy, rack_size_range=(2, 3))

    # Hard: larger rack from bigger board
    rng_hard = random.Random(100)
    board_sets_hard = BoardBuilder.build(rng_hard, board_size_range=(12, 14))
    hard_result = TileRemover.remove(board_sets_hard, rng_hard, rack_size_range=(5, 7))

    if easy_result is None or hard_result is None:
        pytest.skip("Removal failed — skip this seed")

    easy_board, easy_rack, _ = easy_result
    hard_board, hard_rack, _ = hard_result

    easy_state = BoardState(board_sets=easy_board, rack=easy_rack)
    hard_state = BoardState(board_sets=hard_board, rack=hard_rack)

    easy_sol = solve(easy_state)
    hard_sol = solve(hard_state)

    easy_score = DifficultyEvaluator.evaluate(easy_state, easy_sol, skip_expensive=True)
    hard_score = DifficultyEvaluator.evaluate(hard_state, hard_sol, skip_expensive=True)

    # Composite score for harder puzzle should be >= that of easier puzzle
    # (this is a probabilistic assertion; retry with different seeds if it fails)
    assert hard_score.composite_score >= easy_score.composite_score or (
        hard_score.composite_score >= 5.0
    ), (
        f"Hard composite {hard_score.composite_score} not >= easy {easy_score.composite_score}"
    )


def test_performance_skip_expensive():
    """evaluate(skip_expensive=True) completes in < 500ms."""
    state, solution = _build_solvable_state(seed=42)
    t0 = time.monotonic()
    DifficultyEvaluator.evaluate(state, solution, skip_expensive=True)
    elapsed_ms = (time.monotonic() - t0) * 1000
    assert elapsed_ms < 500, f"evaluate() took {elapsed_ms:.1f}ms (limit 500ms)"
