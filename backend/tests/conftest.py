"""Shared pytest fixtures for the RummikubSolve test suite."""

from __future__ import annotations

import pytest

from solver.models.board_state import BoardState
from solver.models.tile import Color, Tile
from solver.models.tileset import SetType, TileSet

# ---------------------------------------------------------------------------
# Single-tile fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def red_4() -> Tile:
    return Tile(color=Color.RED, number=4, copy_id=0)


@pytest.fixture
def blue_1() -> Tile:
    return Tile(color=Color.BLUE, number=1, copy_id=0)


@pytest.fixture
def joker_0() -> Tile:
    return Tile.joker(copy_id=0)


# ---------------------------------------------------------------------------
# Set fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_run() -> TileSet:
    """Red 4-5-6: the minimal valid run."""
    return TileSet(
        type=SetType.RUN,
        tiles=[
            Tile(Color.RED, 4, 0),
            Tile(Color.RED, 5, 0),
            Tile(Color.RED, 6, 0),
        ],
    )


@pytest.fixture
def simple_group() -> TileSet:
    """1s in three colors: the minimal valid group."""
    return TileSet(
        type=SetType.GROUP,
        tiles=[
            Tile(Color.BLUE, 1, 0),
            Tile(Color.RED, 1, 0),
            Tile(Color.BLACK, 1, 0),
        ],
    )


# ---------------------------------------------------------------------------
# BoardState fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def empty_board() -> BoardState:
    return BoardState(board_sets=[], rack=[])


@pytest.fixture
def board_with_one_run(simple_run: TileSet) -> BoardState:
    return BoardState(board_sets=[simple_run], rack=[])


@pytest.fixture
def board_with_rack(simple_run: TileSet) -> BoardState:
    """One run on board, one rack tile that extends it."""
    return BoardState(
        board_sets=[simple_run],
        rack=[Tile(Color.RED, 7, 0)],
    )
