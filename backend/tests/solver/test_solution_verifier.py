"""Tests for solver/validator/solution_verifier.py."""

from __future__ import annotations

from solver.models.board_state import BoardState, Solution
from solver.models.tile import Color, Tile
from solver.models.tileset import SetType, TileSet
from solver.validator.solution_verifier import verify_solution

R, B, BL, Y = Color.RED, Color.BLUE, Color.BLACK, Color.YELLOW


def t(color: Color, number: int, copy_id: int = 0) -> Tile:
    return Tile(color, number, copy_id)


def _solution(
    new_sets: list[TileSet],
    placed: list[Tile],
    remaining: list[Tile],
) -> Solution:
    return Solution(
        new_sets=new_sets,
        placed_tiles=placed,
        remaining_rack=remaining,
        moves=[],
        is_optimal=True,
        solve_time_ms=0.0,
    )


# ---------------------------------------------------------------------------
# Valid solutions
# ---------------------------------------------------------------------------


def test_valid_solution_empty_board_run_placed() -> None:
    """Placing a 3-tile run from an empty board is valid."""
    tiles = [t(R, 4), t(R, 5), t(R, 6)]
    state = BoardState(board_sets=[], rack=tiles)
    new_set = TileSet(SetType.RUN, tiles)
    sol = _solution([new_set], placed=tiles, remaining=[])
    assert verify_solution(state, sol)


def test_valid_solution_board_preserved_rack_added() -> None:
    """Board run preserved, one rack tile extends it."""
    board_tiles = [t(R, 4), t(R, 5), t(R, 6)]
    rack_tile = t(R, 7)
    board_run = TileSet(SetType.RUN, board_tiles)
    state = BoardState(board_sets=[board_run], rack=[rack_tile])

    new_run = TileSet(SetType.RUN, board_tiles + [rack_tile])
    sol = _solution([new_run], placed=[rack_tile], remaining=[])
    assert verify_solution(state, sol)


def test_valid_solution_no_tiles_placed() -> None:
    """Board unchanged, rack tile stays — valid no-op solution."""
    board_tiles = [t(R, 4), t(R, 5), t(R, 6)]
    rack_tile = t(B, 1)
    board_run = TileSet(SetType.RUN, board_tiles)
    state = BoardState(board_sets=[board_run], rack=[rack_tile])

    sol = _solution([board_run], placed=[], remaining=[rack_tile])
    assert verify_solution(state, sol)


def test_valid_solution_empty_board_empty_rack() -> None:
    """Trivial empty solution is valid."""
    state = BoardState(board_sets=[], rack=[])
    sol = _solution([], placed=[], remaining=[])
    assert verify_solution(state, sol)


# ---------------------------------------------------------------------------
# Invalid solutions
# ---------------------------------------------------------------------------


def test_invalid_solution_set_fails_rule_checker() -> None:
    """A solution containing an invalid set (too short) is rejected."""
    tiles = [t(R, 4), t(R, 5)]  # Only 2 tiles — not a valid set.
    state = BoardState(board_sets=[], rack=tiles)
    bad_set = TileSet(SetType.RUN, tiles)
    sol = _solution([bad_set], placed=tiles, remaining=[])
    assert not verify_solution(state, sol)


def test_invalid_solution_missing_board_tile() -> None:
    """A solution that loses a board tile is rejected."""
    board_tiles = [t(R, 4), t(R, 5), t(R, 6)]
    board_run = TileSet(SetType.RUN, board_tiles)
    state = BoardState(board_sets=[board_run], rack=[])

    # Only include Red 4 and Red 5 in the new set — Red 6 is missing.
    incomplete = TileSet(SetType.RUN, board_tiles[:2])
    sol = _solution([incomplete], placed=[], remaining=[])
    assert not verify_solution(state, sol)


def test_invalid_solution_extra_tile_added() -> None:
    """A solution that introduces a tile not in the original state is rejected."""
    state = BoardState(board_sets=[], rack=[t(R, 4), t(R, 5), t(R, 6)])
    # Adds a Blue 7 that was never in the rack.
    extra_tile = t(B, 7)
    new_set = TileSet(SetType.RUN, [t(R, 4), t(R, 5), t(R, 6), extra_tile])
    sol = _solution(
        [new_set],
        placed=[t(R, 4), t(R, 5), t(R, 6)],
        remaining=[],
    )
    # new_set contains Blue 7 which is not in placed_tiles
    assert not verify_solution(state, sol)


def test_invalid_solution_rack_accounting_wrong() -> None:
    """placed + remaining ≠ original rack → rejected."""
    rack_tiles = [t(R, 4), t(R, 5), t(R, 6)]
    state = BoardState(board_sets=[], rack=rack_tiles)
    new_set = TileSet(SetType.RUN, rack_tiles)
    # Claims to have placed all 3 but also lists one in remaining.
    sol = _solution([new_set], placed=rack_tiles, remaining=[t(R, 4)])
    assert not verify_solution(state, sol)


def test_invalid_solution_placed_tile_not_in_new_sets() -> None:
    """placed_tiles lists a tile that isn't actually in any new set."""
    rack_tiles = [t(R, 4), t(R, 5), t(R, 6)]
    state = BoardState(board_sets=[], rack=rack_tiles)
    # Claims placed includes Red 4 but new_sets contains Blue 4 instead.
    sol = _solution(
        [TileSet(SetType.RUN, [t(B, 4), t(R, 5), t(R, 6)])],
        placed=[t(R, 4), t(R, 5), t(R, 6)],
        remaining=[],
    )
    assert not verify_solution(state, sol)
