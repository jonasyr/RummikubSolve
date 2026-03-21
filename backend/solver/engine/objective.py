"""Objective function composition for the ILP model.

Blueprint §1.3 — Two-tier objective:
  Primary:   maximise tiles placed from rack
  Secondary: minimise edit distance between old board and new board
             (tiebreaker — prefer solutions that disrupt fewer sets)
"""

from __future__ import annotations

from ..models.tile import Color, Tile
from ..models.tileset import TileSet


def _tile_key(t: Tile) -> tuple[Color | None, int | None, int, bool]:
    return (t.color, t.number, t.copy_id, t.is_joker)


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
    old_assignment: dict[tuple[Color | None, int | None, int, bool], int] = {}
    for i, ts in enumerate(old_board_sets):
        for tile in ts.tiles:
            old_assignment[_tile_key(tile)] = i

    new_assignment: dict[tuple[Color | None, int | None, int, bool], int] = {}
    for i, ts in enumerate(new_board_sets):
        for tile in ts.tiles:
            new_assignment[_tile_key(tile)] = i

    disrupted = 0
    for key, old_idx in old_assignment.items():
        if new_assignment.get(key) != old_idx:
            disrupted += 1
    return disrupted
