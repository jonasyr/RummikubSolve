"""Tests for the domain model layer (solver/models/ and api/models).

These tests verify pure data construction and invariants — no solver logic.
All tests must pass from the very first commit of the foundation.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.models import TileInput
from solver.models.board_state import BoardState, MoveInstruction, Solution
from solver.models.tile import Color, Tile
from solver.models.tileset import SetType, TileSet

# ---------------------------------------------------------------------------
# Color enum
# ---------------------------------------------------------------------------


def test_color_enum_values() -> None:
    assert Color.BLUE.value == "blue"
    assert Color.RED.value == "red"
    assert Color.BLACK.value == "black"
    assert Color.YELLOW.value == "yellow"


def test_color_enum_count() -> None:
    assert len(Color) == 4


# ---------------------------------------------------------------------------
# Tile construction
# ---------------------------------------------------------------------------


def test_tile_basic_construction() -> None:
    t = Tile(color=Color.BLUE, number=7, copy_id=0)
    assert t.color == Color.BLUE
    assert t.number == 7
    assert t.copy_id == 0
    assert not t.is_joker


def test_tile_all_colors() -> None:
    for color in Color:
        t = Tile(color=color, number=1, copy_id=0)
        assert t.color == color


def test_tile_all_numbers() -> None:
    for n in range(1, 14):
        t = Tile(color=Color.RED, number=n, copy_id=0)
        assert t.number == n


def test_tile_copy_ids() -> None:
    t0 = Tile(Color.RED, 5, copy_id=0)
    t1 = Tile(Color.RED, 5, copy_id=1)
    assert t0 != t1  # Different physical tiles


def test_tile_frozen_immutable() -> None:
    t = Tile(Color.RED, 5, copy_id=0)
    with pytest.raises(AttributeError):
        t.number = 6  # type: ignore[misc]


def test_tile_invalid_number_too_high() -> None:
    with pytest.raises(ValueError, match="1 and 13"):
        Tile(Color.BLUE, 14, copy_id=0)


def test_tile_invalid_number_zero() -> None:
    with pytest.raises(ValueError, match="1 and 13"):
        Tile(Color.BLUE, 0, copy_id=0)


def test_tile_invalid_copy_id() -> None:
    with pytest.raises(ValueError, match="copy_id"):
        Tile(Color.BLUE, 5, copy_id=2)


def test_tile_missing_color_raises() -> None:
    with pytest.raises(ValueError):
        Tile(color=None, number=5, copy_id=0, is_joker=False)


def test_tile_missing_number_raises() -> None:
    with pytest.raises(ValueError):
        Tile(color=Color.RED, number=None, copy_id=0, is_joker=False)


# ---------------------------------------------------------------------------
# Joker construction
# ---------------------------------------------------------------------------


def test_joker_factory() -> None:
    j = Tile.joker(copy_id=0)
    assert j.is_joker
    assert j.color is None
    assert j.number is None
    assert j.copy_id == 0


def test_joker_copy_ids_distinct() -> None:
    j0 = Tile.joker(copy_id=0)
    j1 = Tile.joker(copy_id=1)
    assert j0 != j1


def test_joker_str() -> None:
    assert "Joker" in str(Tile.joker(0))


# ---------------------------------------------------------------------------
# Tile hashability and use as dict key
# ---------------------------------------------------------------------------


def test_tile_hashable() -> None:
    t = Tile(Color.RED, 5, copy_id=0)
    d = {t: "value"}
    assert d[t] == "value"


def test_tile_set_membership() -> None:
    t1 = Tile(Color.RED, 5, copy_id=0)
    t2 = Tile(Color.RED, 5, copy_id=0)
    s = {t1}
    assert t2 in s  # Same value → same hash


# ---------------------------------------------------------------------------
# TileSet
# ---------------------------------------------------------------------------


def test_tileset_run_construction() -> None:
    tiles = [Tile(Color.RED, n, 0) for n in [4, 5, 6]]
    ts = TileSet(type=SetType.RUN, tiles=tiles)
    assert ts.type == SetType.RUN
    assert len(ts) == 3


def test_tileset_group_construction() -> None:
    tiles = [
        Tile(Color.BLUE, 7, 0),
        Tile(Color.RED, 7, 0),
        Tile(Color.BLACK, 7, 0),
    ]
    ts = TileSet(type=SetType.GROUP, tiles=tiles)
    assert ts.type == SetType.GROUP
    assert len(ts) == 3


def test_tileset_empty() -> None:
    ts = TileSet(type=SetType.RUN)
    assert len(ts) == 0


def test_set_type_values() -> None:
    assert SetType.RUN.value == "run"
    assert SetType.GROUP.value == "group"


# ---------------------------------------------------------------------------
# BoardState
# ---------------------------------------------------------------------------


def test_board_state_empty() -> None:
    state = BoardState(board_sets=[], rack=[])
    assert state.all_tiles == []
    assert state.board_tiles == []


def test_board_state_all_tiles(simple_run: TileSet) -> None:
    rack_tile = Tile(Color.RED, 7, 0)
    state = BoardState(board_sets=[simple_run], rack=[rack_tile])
    assert len(state.all_tiles) == 4
    assert rack_tile in state.all_tiles


def test_board_state_board_tiles_excludes_rack(simple_run: TileSet) -> None:
    rack_tile = Tile(Color.RED, 7, 0)
    state = BoardState(board_sets=[simple_run], rack=[rack_tile])
    assert rack_tile not in state.board_tiles
    assert len(state.board_tiles) == 3


def test_board_state_multiple_sets() -> None:
    run = TileSet(SetType.RUN, [Tile(Color.RED, n, 0) for n in [4, 5, 6]])
    group = TileSet(
        SetType.GROUP,
        [
            Tile(Color.BLUE, 1, 0),
            Tile(Color.RED, 1, 0),
            Tile(Color.BLACK, 1, 0),
        ],
    )
    state = BoardState(board_sets=[run, group], rack=[])
    assert len(state.board_tiles) == 6


# ---------------------------------------------------------------------------
# Solution
# ---------------------------------------------------------------------------


def test_solution_tile_counts() -> None:
    placed = [Tile(Color.RED, 7, 0), Tile(Color.BLUE, 3, 0)]
    remaining = [Tile(Color.BLACK, 9, 0)]
    sol = Solution(
        new_sets=[],
        placed_tiles=placed,
        remaining_rack=remaining,
        is_optimal=True,
        solve_time_ms=12.5,
    )
    assert sol.tiles_placed == 2
    assert sol.tiles_remaining == 1


def test_solution_defaults() -> None:
    sol = Solution(new_sets=[], placed_tiles=[], remaining_rack=[])
    assert sol.is_optimal is False
    assert sol.solve_time_ms == 0.0
    assert sol.moves == []


# ---------------------------------------------------------------------------
# MoveInstruction
# ---------------------------------------------------------------------------


def test_move_instruction_construction() -> None:
    move = MoveInstruction(action="extend", description="Add Red 7 to Set 1", set_index=0)
    assert move.action == "extend"
    assert move.set_index == 0
    assert move.tile is None


# ---------------------------------------------------------------------------
# TileInput API model validation (AAA)
# ---------------------------------------------------------------------------


def test_tile_input_joker_minimal_valid() -> None:
    """A bare joker (no color, no number) is a valid TileInput."""
    # Arrange / Act
    tile = TileInput(joker=True)

    # Assert
    assert tile.joker is True
    assert tile.color is None
    assert tile.number is None


def test_tile_input_joker_with_color_raises() -> None:
    """A joker tile that also specifies a color violates the domain invariant."""
    # Arrange — invalid: joker cannot carry a color
    with pytest.raises(ValidationError, match="Joker tiles must not have"):
        # Act
        TileInput(joker=True, color="red")  # type: ignore[arg-type]


def test_tile_input_joker_with_number_raises() -> None:
    """A joker tile that also specifies a number violates the domain invariant."""
    # Arrange — invalid: joker cannot carry a number
    with pytest.raises(ValidationError, match="Joker tiles must not have"):
        # Act
        TileInput(joker=True, number=5)
