"""Objective function composition for the ILP model.

Blueprint §1.3 — Two-tier objective:
  Primary:   maximise tiles placed from rack
  Secondary: minimise edit distance between old board and new board
             (tiebreaker — prefer solutions that disrupt fewer sets)
"""

from __future__ import annotations

from ..models.tileset import TileSet


def compute_disruption_score(
    old_board_sets: list[TileSet],
    new_board_sets: list[TileSet],
) -> int:
    """Count how many board tiles appear in a different set index.

    Used as the secondary minimisation objective (tiebreaker).
    Lower is better (fewer physical tile movements required).

    Args:
        old_board_sets: Sets on the board before solving.
        new_board_sets: Proposed sets after solving.

    Returns:
        Number of board tiles that changed set membership.
    """
    raise NotImplementedError
