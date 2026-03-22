"""Unit tests for solver/generator/puzzle_generator.py."""

from __future__ import annotations

import pytest

from solver.engine.solver import solve
from solver.generator.puzzle_generator import (
    PuzzleGenerationError,
    PuzzleResult,
    generate_puzzle,
)
from solver.models.board_state import BoardState
from solver.validator.rule_checker import is_valid_set


# ---------------------------------------------------------------------------
# Happy-path: one puzzle per difficulty
# ---------------------------------------------------------------------------


def test_easy_puzzle_generates() -> None:
    result = generate_puzzle(difficulty="easy", seed=1)
    assert isinstance(result, PuzzleResult)
    assert result.difficulty == "easy"
    assert 2 <= len(result.rack) <= 3


def test_medium_puzzle_generates() -> None:
    result = generate_puzzle(difficulty="medium", seed=2)
    assert result.difficulty == "medium"
    assert len(result.rack) >= 3


def test_hard_puzzle_generates() -> None:
    result = generate_puzzle(difficulty="hard", seed=3)
    assert result.difficulty == "hard"
    assert len(result.rack) >= 6


# ---------------------------------------------------------------------------
# Correctness invariants
# ---------------------------------------------------------------------------


def test_board_sets_all_valid() -> None:
    result = generate_puzzle(difficulty="medium", seed=10)
    for ts in result.board_sets:
        assert is_valid_set(ts), f"Invalid board set: {ts!r}"


def test_puzzle_is_fully_solvable() -> None:
    result = generate_puzzle(difficulty="medium", seed=11)
    state = BoardState(board_sets=result.board_sets, rack=result.rack)
    solution = solve(state)
    assert solution.tiles_placed == len(result.rack)


def test_rack_minimum_size() -> None:
    min_rack = {"easy": 2, "medium": 3, "hard": 6}
    for seed in range(5):
        for difficulty in ("easy", "medium", "hard"):
            result = generate_puzzle(difficulty=difficulty, seed=seed)  # type: ignore[arg-type]
            assert len(result.rack) >= min_rack[difficulty], (
                f"Rack too small for {difficulty} (seed={seed}): got {len(result.rack)}"
            )


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


def test_seeded_puzzle_is_deterministic() -> None:
    a = generate_puzzle(difficulty="medium", seed=42)
    b = generate_puzzle(difficulty="medium", seed=42)
    # Compare board_sets and rack by tile keys.
    def tiles_key(ts_list: list) -> list:  # type: ignore[type-arg]
        return [
            [(t.color, t.number, t.copy_id) for t in ts.tiles]
            for ts in ts_list
        ]

    assert tiles_key(a.board_sets) == tiles_key(b.board_sets)
    assert [(t.color, t.number, t.copy_id) for t in a.rack] == [
        (t.color, t.number, t.copy_id) for t in b.rack
    ]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_invalid_difficulty_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown difficulty"):
        generate_puzzle(difficulty="extreme")  # type: ignore[arg-type]


def test_zero_attempts_raises_generation_error() -> None:
    with pytest.raises(PuzzleGenerationError):
        generate_puzzle(difficulty="medium", max_attempts=0)


# ---------------------------------------------------------------------------
# Tile-conservation invariants
# ---------------------------------------------------------------------------


def test_rack_tiles_not_in_board() -> None:
    """No physical tile (color, number, copy_id) appears in both rack and board_sets."""
    result = generate_puzzle(difficulty="medium", seed=10)
    board_keys = {
        (t.color, t.number, t.copy_id)
        for ts in result.board_sets
        for t in ts.tiles
    }
    rack_keys = {(t.color, t.number, t.copy_id) for t in result.rack}
    assert board_keys.isdisjoint(rack_keys), (
        f"Overlap between board and rack: {board_keys & rack_keys}"
    )


def test_copy_ids_valid() -> None:
    """Every tile in a generated puzzle has copy_id in {0, 1}."""
    result = generate_puzzle(difficulty="hard", seed=5)
    all_tiles = [t for ts in result.board_sets for t in ts.tiles] + result.rack
    invalid = [(t.color, t.number, t.copy_id) for t in all_tiles if t.copy_id not in (0, 1)]
    assert invalid == [], f"Tiles with invalid copy_id: {invalid}"
