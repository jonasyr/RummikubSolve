"""Unit tests for solver/generator/tile_pool.py (Phase 0 / Phase 5)."""

from __future__ import annotations

import pytest

from solver.generator.tile_pool import assign_copy_ids, make_tile_pool
from solver.models.tile import Color, Tile
from solver.models.tileset import SetType, TileSet


# ---------------------------------------------------------------------------
# make_tile_pool
# ---------------------------------------------------------------------------


def test_make_tile_pool_default_is_104_tiles() -> None:
    """n_jokers=0 produces exactly 104 non-joker tiles, board empty."""
    pool = make_tile_pool()
    assert len(pool.rack) == 104
    assert pool.board_sets == []
    assert all(not t.is_joker for t in pool.rack)


def test_make_tile_pool_one_joker() -> None:
    """n_jokers=1 produces 105 tiles with exactly one joker."""
    pool = make_tile_pool(n_jokers=1)
    assert len(pool.rack) == 105
    jokers = [t for t in pool.rack if t.is_joker]
    assert len(jokers) == 1
    assert jokers[0].copy_id == 0


def test_make_tile_pool_two_jokers() -> None:
    """n_jokers=2 produces 106 tiles with two jokers (copy_id 0 and 1)."""
    pool = make_tile_pool(n_jokers=2)
    assert len(pool.rack) == 106
    jokers = [t for t in pool.rack if t.is_joker]
    assert len(jokers) == 2
    assert {j.copy_id for j in jokers} == {0, 1}


def test_make_tile_pool_invalid_joker_count_raises() -> None:
    """n_jokers outside [0, 2] raises ValueError."""
    with pytest.raises(ValueError, match="n_jokers must be 0, 1, or 2"):
        make_tile_pool(n_jokers=3)


# ---------------------------------------------------------------------------
# assign_copy_ids
# ---------------------------------------------------------------------------


def test_assign_copy_ids_assigns_0_then_1() -> None:
    """Two tiles with the same (color, number) get copy_id 0 then 1."""
    sets = [
        TileSet(
            type=SetType.RUN,
            tiles=[
                Tile(Color.RED, 5, 0),
                Tile(Color.RED, 6, 0),
                Tile(Color.RED, 7, 0),
            ],
        ),
        TileSet(
            type=SetType.RUN,
            tiles=[
                Tile(Color.RED, 5, 0),  # second occurrence of RED-5
                Tile(Color.RED, 8, 0),
                Tile(Color.RED, 9, 0),
            ],
        ),
    ]
    result = assign_copy_ids(sets)
    red5_ids = [
        t.copy_id
        for ts in result
        for t in ts.tiles
        if t.color == Color.RED and t.number == 5
    ]
    assert red5_ids == [0, 1]
