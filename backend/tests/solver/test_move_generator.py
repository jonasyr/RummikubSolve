"""Unit tests for solver.generator.move_generator.generate_moves."""

from __future__ import annotations

from solver.generator.move_generator import generate_moves
from solver.models.board_state import BoardState
from solver.models.tile import Color, Tile
from solver.models.tileset import SetType, TileSet

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def t(color: Color, number: int, copy_id: int = 0) -> Tile:
    return Tile(color, number, copy_id)


def run_set(color: Color, *numbers: int) -> TileSet:
    return TileSet(type=SetType.RUN, tiles=[Tile(color, n, 0) for n in numbers])


def group_set(number: int, *colors: Color) -> TileSet:
    return TileSet(type=SetType.GROUP, tiles=[Tile(c, number, 0) for c in colors])


R, B, BL, Y = Color.RED, Color.BLUE, Color.BLACK, Color.YELLOW


# ---------------------------------------------------------------------------
# No tiles placed
# ---------------------------------------------------------------------------


def test_no_tiles_placed_returns_empty() -> None:
    """When nothing is placed, moves list is empty."""
    board = [run_set(R, 4, 5, 6)]
    state = BoardState(board_sets=board, rack=[t(B, 1)])
    new_sets = board  # unchanged
    moves = generate_moves(state, new_sets, placed_tiles=[])
    assert moves == []


# ---------------------------------------------------------------------------
# Create (rack-only new sets)
# ---------------------------------------------------------------------------


def test_create_run_from_rack() -> None:
    """Three rack tiles form a brand-new run → action='create'."""
    state = BoardState(board_sets=[], rack=[t(R, 7), t(R, 8), t(R, 9)])
    placed = [t(R, 7), t(R, 8), t(R, 9)]
    new_sets = [run_set(R, 7, 8, 9)]
    moves = generate_moves(state, new_sets, placed)
    assert len(moves) == 1
    assert moves[0].action == "create"
    assert "run" in moves[0].description


def test_create_group_from_rack() -> None:
    """Three rack tiles form a brand-new group → action='create'."""
    state = BoardState(board_sets=[], rack=[t(B, 5), t(R, 5), t(BL, 5)])
    placed = [t(B, 5), t(R, 5), t(BL, 5)]
    new_sets = [group_set(5, B, R, BL)]
    moves = generate_moves(state, new_sets, placed)
    assert len(moves) == 1
    assert moves[0].action == "create"
    assert "group" in moves[0].description


# ---------------------------------------------------------------------------
# Extend (add rack tiles to an existing board set)
# ---------------------------------------------------------------------------


def test_extend_run_at_end() -> None:
    """Red 7 from rack extends Red 4-5-6 on the board → action='extend'."""
    board_run = run_set(R, 4, 5, 6)
    state = BoardState(board_sets=[board_run], rack=[t(R, 7)])
    placed = [t(R, 7)]
    new_sets = [run_set(R, 4, 5, 6, 7)]
    moves = generate_moves(state, new_sets, placed)
    assert len(moves) == 1
    assert moves[0].action == "extend"
    assert moves[0].set_index == 0
    assert "Red 7" in moves[0].description


def test_extend_run_at_start() -> None:
    """Red 4 from rack extends Red 5-6-7 on the board → action='extend'."""
    board_run = run_set(R, 5, 6, 7)
    state = BoardState(board_sets=[board_run], rack=[t(R, 4)])
    placed = [t(R, 4)]
    new_sets = [run_set(R, 4, 5, 6, 7)]
    moves = generate_moves(state, new_sets, placed)
    assert len(moves) == 1
    assert moves[0].action == "extend"
    assert moves[0].set_index == 0


def test_extend_correct_set_index_with_multiple_board_sets() -> None:
    """When there are two board sets, set_index must point to the right one."""
    board1 = run_set(R, 1, 2, 3)
    board2 = run_set(B, 4, 5, 6)
    state = BoardState(board_sets=[board1, board2], rack=[t(B, 7)])
    placed = [t(B, 7)]
    new_sets = [board1, run_set(B, 4, 5, 6, 7)]
    moves = generate_moves(state, new_sets, placed)
    extend_moves = [m for m in moves if m.action == "extend"]
    assert len(extend_moves) == 1
    assert extend_moves[0].set_index == 1  # board2 is index 1


# ---------------------------------------------------------------------------
# Unchanged board sets produce no instruction
# ---------------------------------------------------------------------------


def test_unchanged_board_set_no_instruction() -> None:
    """A board set that stays identical produces no move instruction."""
    board1 = run_set(R, 1, 2, 3)
    board2 = run_set(B, 7, 8, 9)
    state = BoardState(board_sets=[board1, board2], rack=[t(R, 10), t(R, 11), t(R, 12)])
    placed = [t(R, 10), t(R, 11), t(R, 12)]
    # Both board sets unchanged; a new run is created from rack.
    new_sets = [board1, board2, run_set(R, 10, 11, 12)]
    moves = generate_moves(state, new_sets, placed)
    # Only one instruction: 'create' for the new run.
    assert len(moves) == 1
    assert moves[0].action == "create"
