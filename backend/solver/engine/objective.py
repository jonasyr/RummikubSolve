"""Objective function utilities for the ILP model.

Blueprint §1.3 — Two-tier objective:
  Primary:   maximise tiles placed from rack
  Secondary: tiebreaker among equal-placement solutions

Current ILP secondary objective (v0.13.0, in ilp_formulation.py):
  Minimise the sum of face values of tiles left in hand.

Planned dual-solution feature:
  The solver will eventually expose *two* solutions to the user:
    (A) Minimise remaining tile value  — current behaviour
    (B) Minimise board disruption      — fewer physical tile moves required
  `compute_disruption_score()` below is the metric for option B.
  It is used during puzzle generation to classify difficulty bands.
  Wiring it into the ILP objective (so the solver actively minimises
  disruption for option B) is future work; see ilp_formulation.py for
  the planned encoding.
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
    """Count board tiles no longer grouped with their original set-mates.

    Uses greedy content-based matching: for each old board set, find the
    new set that contains the most of its tiles (the "best match"). Tiles
    that did not end up in that best-match set are counted as disrupted.

    This is reordering-invariant — if the solver outputs the same sets in a
    different order, disruption is 0. Adding a rack tile to an otherwise
    unchanged set also scores 0.

    Examples:
        Old set {A,B,C} → new set {A,B,C,D}: disruption += 0
        Old set {A,B,C} → split into {A,D} and {B,C,E}: disruption += 1
        Old sets reordered but content unchanged: disruption = 0

    Lower is better (fewer physical tile movements required).

    Args:
        old_board_sets: Sets on the board before solving.
        new_board_sets: Proposed sets after solving.

    Returns:
        Number of board tiles that changed effective set membership.
    """
    # Map each tile key to the index of its new set.
    new_assignment: dict[tuple[Color | None, int | None, int, bool], int] = {}
    for j, ts in enumerate(new_board_sets):
        for tile in ts.tiles:
            new_assignment[_tile_key(tile)] = j

    disrupted = 0
    for old_ts in old_board_sets:
        # Vote: how many tiles from this old set ended up in each new set?
        vote: dict[int, int] = {}
        for tile in old_ts.tiles:
            key = _tile_key(tile)
            if key in new_assignment:
                j = new_assignment[key]
                vote[j] = vote.get(j, 0) + 1

        if not vote:
            continue  # all tiles from this set missing from new board (shouldn't happen)

        # Tiles NOT in the best-matching new set are disrupted.
        best_count = max(vote.values())
        disrupted += len(old_ts.tiles) - best_count

    return disrupted
