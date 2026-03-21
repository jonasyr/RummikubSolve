"""Compute the visual diff between the old board and the new board.

Used by the frontend to highlight which tiles moved where, and by
move_generator to produce human-readable instructions.

The diff is at the TileSet level: for each set in the new arrangement,
annotate which tiles are newly placed (from rack) and which tiles moved
from a different set index.
"""

from __future__ import annotations

from ..models.board_state import BoardState
from ..models.tileset import TileSet


def compute_diff(
    old_state: BoardState,
    new_sets: list[TileSet],
) -> list[dict[str, object]]:
    """Compute per-set annotations for the frontend diff view.

    For each set in new_sets, return a dict with:
      "new_tile_indices": list[int]  — positions of tiles that came from rack
      "moved_tile_indices": list[int] — positions of tiles that changed sets

    Args:
        old_state: The board state before solving.
        new_sets:  The proposed new board arrangement.

    Returns:
        A list of annotation dicts, one per set in new_sets.
    """
    raise NotImplementedError
