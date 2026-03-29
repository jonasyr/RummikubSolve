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


def compute_chain_depth(
    old_board_sets: list[TileSet],
    new_board_sets: list[TileSet],
    placed_tiles: list[Tile],
) -> int:
    """Compute the longest dependency chain in a solution.

    Chain depth measures how many distinct old-set disruptions a player
    must mentally trace to construct the most complex new set.

      0 = pure placement — no board rearrangement needed
      1 = simple rearrangement — one or more sets broken, each new set
          draws tiles from at most one disrupted source
      2 = two-step convergence — one new set combines freed tiles from two
          separately disrupted old sets (requires two breaking steps)
      3+ = deep chains — N disruptions all feed into a single new set

    Algorithm:
      1. Map each board tile key → old set index.
      2. For each old set, record which new sets received its tiles
         (old_set_destinations).
      3. An old set is *disrupted* if its tiles ended up in 2+ new sets.
      4. For each new set, count how many distinct disrupted old sets
         contributed board tiles to it.
      5. Return the maximum such count (or 0 if no disruption occurred).

    Args:
        old_board_sets: Board sets before the move.
        new_board_sets: Board sets after the move (solver output).
        placed_tiles:   Tiles moved from the rack to the board.

    Returns:
        Chain depth (non-negative integer).
    """
    if not old_board_sets:
        return 0

    placed_keys: set[tuple] = {_tile_key(t) for t in placed_tiles}

    # Step 1 — map each board tile key to its old set index.
    old_membership: dict[tuple, int] = {}
    for oi, ts in enumerate(old_board_sets):
        for tile in ts.tiles:
            old_membership[_tile_key(tile)] = oi

    # Step 2 — for each old set, which new sets received its board tiles?
    n_old = len(old_board_sets)
    old_set_destinations: list[set[int]] = [set() for _ in range(n_old)]
    for ni, ts in enumerate(new_board_sets):
        for tile in ts.tiles:
            key = _tile_key(tile)
            if key in old_membership:
                old_set_destinations[old_membership[key]].add(ni)

    # Step 3 — disrupted old sets: tiles scattered across 2+ new sets.
    disrupted_old: set[int] = {
        oi for oi in range(n_old) if len(old_set_destinations[oi]) > 1
    }

    if not disrupted_old:
        return 0

    # Step 4 — for each new set, count distinct disrupted old sets
    # that contributed board tiles (rack tiles don't count as "from" an old set).
    max_depth = 0
    for ts in new_board_sets:
        contributing: set[int] = set()
        for tile in ts.tiles:
            key = _tile_key(tile)
            if key not in placed_keys and key in old_membership:
                oi = old_membership[key]
                if oi in disrupted_old:
                    contributing.add(oi)
        if contributing:
            max_depth = max(max_depth, len(contributing))

    # Step 5 — at least depth 1 when any disruption occurred.
    return max(1, max_depth)
