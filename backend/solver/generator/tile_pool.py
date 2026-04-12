"""Shared tile pool utilities for puzzle generation.

Consolidates _make_pool() and _assign_copy_ids() from puzzle_generator.py
so that BoardBuilder and future modules can import them without pulling in
the entire generation pipeline.
"""

from __future__ import annotations

from collections import Counter

from ..models.board_state import BoardState
from ..models.tile import Color, Tile
from ..models.tileset import TileSet


def make_tile_pool(n_jokers: int = 0) -> BoardState:
    """Return a BoardState with the full tile pool in the rack.

    Creates 104 non-joker tiles (4 colors × 13 numbers × copy_id 0 and 1)
    plus n_jokers joker tiles. Board is empty; all tiles are in the rack so
    that enumerate_runs / enumerate_groups can see them via state.all_tiles.

    Args:
        n_jokers: Number of joker tiles to include (0, 1, or 2).

    Returns:
        BoardState with board_sets=[] and rack containing all tiles.
    """
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


def assign_copy_ids(board_sets: list[TileSet]) -> list[TileSet]:
    """Assign copy_id 0 or 1 to each tile in a list of board sets.

    Templates produced by enumerate_runs / enumerate_groups use copy_id=0
    as a placeholder. This function assigns the correct physical copy_id so
    that the two copies of any (color, number) tile are distinguishable.

    The first occurrence of each (color, number) pair receives copy_id=0;
    the second receives copy_id=1. Joker tiles are passed through unchanged.

    Args:
        board_sets: Sets with placeholder copy_ids (typically all 0).

    Returns:
        New list of TileSets with copy_ids correctly assigned.
    """
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
