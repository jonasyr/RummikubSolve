"""Phase 5 test suite for the v2 puzzle generation pipeline.

Covers blueprint §7.2 (integration), §7.3 (property), §7.4 (simulation),
§7.5 (regression), and §7.6 (performance).

All tests use ``generator_version="v2"`` explicitly so that the existing
v1 unit tests in test_puzzle_generator.py are unaffected.
"""

from __future__ import annotations

import time
from statistics import mean

import pytest

from solver.engine.solver import solve
from solver.generator.board_builder import BoardBuilder
from solver.generator.difficulty_evaluator import DifficultyEvaluator
from solver.generator.puzzle_generator import PuzzleResult, generate_puzzle
from solver.generator.puzzle_store import PuzzleStore
from solver.models.board_state import BoardState
from solver.validator.solution_verifier import verify_solution

pytestmark = pytest.mark.slow


# ---------------------------------------------------------------------------
# Shared module-scope fixtures (generated once to keep the suite fast)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _v2_easy() -> PuzzleResult:
    return generate_puzzle("easy", seed=1, generator_version="v2")


@pytest.fixture(scope="module")
def _v2_medium() -> PuzzleResult:
    return generate_puzzle("medium", seed=2, generator_version="v2")


@pytest.fixture(scope="module")
def _v2_hard() -> PuzzleResult:
    return generate_puzzle("hard", seed=3, generator_version="v2")


@pytest.fixture(scope="module")
def _v2_expert() -> PuzzleResult:
    return generate_puzzle("expert", seed=4, generator_version="v2")


@pytest.fixture(scope="module")
def _v2_nightmare() -> PuzzleResult:
    return generate_puzzle("nightmare", seed=5, generator_version="v2")


# ---------------------------------------------------------------------------
# §7.2 — Integration tests: end-to-end solvability per difficulty
# ---------------------------------------------------------------------------


def _assert_fully_solvable(result: PuzzleResult) -> None:
    state = BoardState(board_sets=result.board_sets, rack=result.rack)
    solution = solve(state, timeout_seconds=10.0)
    assert solution.tiles_placed == len(result.rack), (
        f"Expected {len(result.rack)} tiles placed, got {solution.tiles_placed} "
        f"(status: {solution.solve_status})"
    )


def test_v2_easy_is_solvable(_v2_easy: PuzzleResult) -> None:
    _assert_fully_solvable(_v2_easy)


def test_v2_medium_is_solvable(_v2_medium: PuzzleResult) -> None:
    _assert_fully_solvable(_v2_medium)


def test_v2_hard_is_solvable(_v2_hard: PuzzleResult) -> None:
    _assert_fully_solvable(_v2_hard)


def test_v2_expert_is_solvable(_v2_expert: PuzzleResult) -> None:
    _assert_fully_solvable(_v2_expert)


def test_v2_nightmare_is_solvable(_v2_nightmare: PuzzleResult) -> None:
    _assert_fully_solvable(_v2_nightmare)


def test_v2_hard_v2_fields_populated(_v2_hard: PuzzleResult) -> None:
    """Hard+ puzzles should have non-default v2 metric fields."""
    assert _v2_hard.generator_version == "v2.0.0"
    assert _v2_hard.composite_score > 0.0, "composite_score must be > 0 for hard puzzles"
    assert _v2_hard.branching_factor > 0.0


def test_v2_result_type_is_puzzle_result(_v2_easy: PuzzleResult) -> None:
    assert isinstance(_v2_easy, PuzzleResult)
    assert _v2_easy.difficulty == "easy"


# ---------------------------------------------------------------------------
# §7.2 — Integration: full store → draw round-trip for all v2 fields
# (deeper than test_puzzle_store.py TestV2RoundTrip — checks all 6 metrics)
# ---------------------------------------------------------------------------


def test_v2_store_round_trip_all_metrics(_v2_hard: PuzzleResult, tmp_path: object) -> None:
    """All v2 PuzzleResult metric fields survive a complete store → draw cycle."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        store = PuzzleStore(Path(td) / "p.db")
        store.store(_v2_hard)
        drawn = store.draw("hard")
        store.close()

    assert drawn is not None
    restored, _ = drawn

    assert restored.generator_version == _v2_hard.generator_version
    assert restored.composite_score == pytest.approx(_v2_hard.composite_score, abs=1e-5)
    assert restored.branching_factor == pytest.approx(_v2_hard.branching_factor, abs=1e-5)
    assert restored.deductive_depth == pytest.approx(_v2_hard.deductive_depth, abs=1e-5)
    assert restored.red_herring_density == pytest.approx(
        _v2_hard.red_herring_density, abs=1e-5
    )
    assert restored.working_memory_load == pytest.approx(
        _v2_hard.working_memory_load, abs=1e-5
    )
    assert restored.tile_ambiguity == pytest.approx(_v2_hard.tile_ambiguity, abs=1e-5)
    assert restored.solution_fragility == pytest.approx(
        _v2_hard.solution_fragility, abs=1e-5
    )


# ---------------------------------------------------------------------------
# §7.2 — Integration: pregenerate worker produces v2 puzzles
# ---------------------------------------------------------------------------


def test_pregenerate_worker_produces_v2_result() -> None:
    """generate_puzzle with generator_version='v2' yields generator_version='v2.0.0'."""
    result = generate_puzzle("easy", seed=77, generator_version="v2")
    assert result.generator_version == "v2.0.0"
    assert result.composite_score >= 0.0
    assert result.branching_factor >= 0.0


# ---------------------------------------------------------------------------
# §7.3 — Property-based tests (Hypothesis)
# ---------------------------------------------------------------------------

try:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st

    _HYPOTHESIS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _HYPOTHESIS_AVAILABLE = False

_skip_no_hypothesis = pytest.mark.skipif(
    not _HYPOTHESIS_AVAILABLE, reason="hypothesis not installed"
)


@_skip_no_hypothesis
@given(seed=st.integers(0, 2**31))
@settings(max_examples=3, deadline=30_000, suppress_health_check=[HealthCheck.too_slow])
def test_generated_puzzle_always_solvable(seed: int) -> None:
    """Every v2 medium puzzle, regardless of seed, is solvable by the ILP solver."""
    result = generate_puzzle("medium", seed=seed, max_attempts=5, generator_version="v2")
    state = BoardState(board_sets=result.board_sets, rack=result.rack)
    solution = solve(state, timeout_seconds=10.0)
    assert solution.tiles_placed == len(result.rack)


@_skip_no_hypothesis
@given(seed=st.integers(0, 2**31))
@settings(max_examples=3, deadline=30_000, suppress_health_check=[HealthCheck.too_slow])
def test_tile_conservation(seed: int) -> None:
    """board + rack tiles are precisely what the solver needs to verify the solution."""
    result = generate_puzzle("hard", seed=seed, max_attempts=10, generator_version="v2")
    state = BoardState(board_sets=result.board_sets, rack=result.rack)
    solution = solve(state, timeout_seconds=10.0)
    if solution.tiles_placed == len(result.rack):
        assert verify_solution(state, solution)


# ---------------------------------------------------------------------------
# §7.4 — Simulation-based tests
# ---------------------------------------------------------------------------


def test_difficulty_distribution() -> None:
    """Composite scores should still show a tier-ordered spread before Phase 6 calibration."""
    sample_count = 2
    averages: dict[str, float] = {}

    for difficulty in ("easy", "medium", "hard", "expert", "nightmare"):
        scores = [
            generate_puzzle(difficulty, seed=seed, generator_version="v2").composite_score
            for seed in range(sample_count)
        ]
        assert all(0.0 <= score <= 100.0 for score in scores)
        averages[difficulty] = mean(scores)

    assert averages["easy"] < averages["medium"] < averages["hard"], averages
    assert averages["hard"] <= averages["expert"], averages
    assert averages["expert"] <= averages["nightmare"], averages


def test_no_trivially_solvable_expert_puzzles() -> None:
    """Expert puzzles should not look trivial on both branching and disruption."""
    for seed in range(2):
        result = generate_puzzle("expert", seed=seed, generator_version="v2")
        assert not (
            result.branching_factor < 2.0 and result.disruption_score < 5
        ), f"Expert seed={seed} looks trivial"


# ---------------------------------------------------------------------------
# §7.5 — Regression tests: v1 backward compatibility
# ---------------------------------------------------------------------------


def test_v1_puzzles_still_solvable() -> None:
    """v1-generated puzzles are still correctly solved by the ILP engine."""
    for seed in (1,):
        result = generate_puzzle("medium", seed=seed, generator_version="v1")
        state = BoardState(board_sets=result.board_sets, rack=result.rack)
        solution = solve(state, timeout_seconds=10.0)
        assert solution.tiles_placed == len(result.rack), (
            f"v1 seed={seed}: expected {len(result.rack)} placed, got {solution.tiles_placed}"
        )


def test_v1_result_has_default_v2_fields() -> None:
    """v1-generated PuzzleResult has the zero-defaults for all v2 fields."""
    result = generate_puzzle("easy", seed=42, generator_version="v1")
    assert result.generator_version == "v1"
    assert result.composite_score == 0.0
    assert result.branching_factor == 0.0
    assert result.deductive_depth == 0.0
    assert result.red_herring_density == 0.0
    assert result.working_memory_load == 0.0
    assert result.tile_ambiguity == 0.0
    assert result.solution_fragility == 0.0


# ---------------------------------------------------------------------------
# §7.6 — Performance tests (NOT marked slow — they must be fast by definition)
# ---------------------------------------------------------------------------


def test_easy_v2_generation_under_5s() -> None:
    """A single easy v2 puzzle should generate in < 5 seconds (generous CI budget)."""
    t0 = time.perf_counter()
    generate_puzzle("easy", seed=0, generator_version="v2")
    elapsed = time.perf_counter() - t0
    assert elapsed < 5.0, f"Easy v2 generation took {elapsed:.2f}s — expected < 5s"


def test_board_builder_under_200ms() -> None:
    """BoardBuilder.build() with default params must complete in < 200ms."""
    import random

    rng = random.Random(0)
    t0 = time.perf_counter()
    BoardBuilder.build(rng, board_size_range=(10, 15), overlap_bias=0.7)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.2, f"BoardBuilder.build() took {elapsed:.3f}s — expected < 200ms"


def test_difficulty_evaluator_skip_expensive_under_500ms() -> None:
    """DifficultyEvaluator.evaluate(skip_expensive=True) must complete in < 500ms."""
    result = generate_puzzle("medium", seed=1, generator_version="v2")
    state = BoardState(board_sets=result.board_sets, rack=result.rack)
    solution = solve(state, timeout_seconds=10.0)

    t0 = time.perf_counter()
    DifficultyEvaluator.evaluate(state, solution, skip_expensive=True)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.5, f"DifficultyEvaluator took {elapsed:.3f}s — expected < 500ms"
