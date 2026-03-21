"""Pre-computation of all valid set templates from an available tile pool.

Blueprint §3.4 — Set Enumeration Strategy:
  Runs:   4 colors × ~66 start/length combos  ≈ 264 max templates
  Groups: 13 numbers × 5 color-subset combos  ≈  65 max templates
  Joker expansion adds variants where one tile is replaced by a joker.

Total candidate sets: typically 200–400. Trivially small for an ILP.

This module is intentionally separate from the ILP builder so that the
enumerated templates can be inspected and tested independently.
"""

from __future__ import annotations

from ..models.board_state import BoardState
from ..models.tileset import TileSet


def enumerate_valid_sets(state: BoardState) -> list[TileSet]:
    """Return all valid set templates constructable from state.all_tiles.

    A template is only included if every required tile exists in the pool
    (respecting copy counts). Joker variants are included when a joker is
    available.

    Args:
        state: The current board + rack state.

    Returns:
        A list of TileSet objects — the candidate sets for the ILP.
    """
    raise NotImplementedError


def enumerate_runs(state: BoardState) -> list[TileSet]:
    """Enumerate all valid run templates from the available tile pool."""
    raise NotImplementedError


def enumerate_groups(state: BoardState) -> list[TileSet]:
    """Enumerate all valid group templates from the available tile pool."""
    raise NotImplementedError
