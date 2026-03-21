"""Translation of a raw ILP solution into human-readable MoveInstructions.

Given the old BoardState and the new arrangement of TileSets from the
solver, this module computes the minimal sequence of physical moves a
player must make to transition from the old board to the new board.
"""

from __future__ import annotations

from ..models.board_state import BoardState, MoveInstruction
from ..models.tileset import TileSet


def generate_moves(
    old_state: BoardState,
    new_sets: list[TileSet],
    placed_tiles_indices: list[int],
) -> list[MoveInstruction]:
    """Compute ordered MoveInstructions from old board state to new arrangement.

    Args:
        old_state:            The board state before solving.
        new_sets:             The proposed new board arrangement.
        placed_tiles_indices: Indices into old_state.rack of placed tiles.

    Returns:
        An ordered list of MoveInstruction objects.
    """
    raise NotImplementedError
