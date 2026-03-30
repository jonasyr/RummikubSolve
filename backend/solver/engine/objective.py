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
    """Compute the longest rearrangement dependency chain in a solution.

    Measures SEQUENTIAL depth via DAG longest-path, not convergence breadth.

      0 = pure placement — no board rearrangement needed
      1 = disruption occurred but no sequential dependencies
      2 = simple rearrangement — one set broken (inheritor + dependent);
          or multiple parallel breaks that each independently enable a new set
      3 = two-step sequential chain — break A enables B which enables C
      4+ = deep sequential chains

    Algorithm:
      1. Map each board tile key → old set index.
      2. For each old set, record which new sets received its tiles.
      3. An old set is *disrupted* if its tiles ended up in 2+ new sets.
      4. For each disrupted old set: the new set that received the most of its
         tiles is the "inheritor"; add directed edges inheritor → every other
         recipient in the dependency DAG.
      5. For each new set that contains rack tiles AND board tiles from a
         disrupted old set: the other destinations of that old set are
         prerequisites — add edges other_destination → this set.
      6. Return longest path in the DAG + 1 (or 1 if disruption with no edges).

    The key difference from the old metric: the old version counted
    len(contributing) — how many disrupted sources feed one set (breadth).
    This version builds an actual DAG and measures the longest path, so a
    chain A→B→C→D gives depth 4, whereas the old metric would report 1.

    Args:
        old_board_sets: Board sets before the move.
        new_board_sets: Board sets after the move (solver output).
        placed_tiles:   Tiles moved from the rack to the board.

    Returns:
        Chain depth (non-negative integer).
    """
    if not old_board_sets:
        return 0

    from collections import defaultdict

    TileKey = tuple[Color | None, int | None, int, bool]
    placed_keys: set[TileKey] = {_tile_key(t) for t in placed_tiles}

    # Step 1 — map each board tile key to its old set index.
    old_membership: dict[TileKey, int] = {}
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

    # Step 4 — build dependency DAG between new sets.
    # For each disrupted old set: the new set that received the most of its
    # tiles is the "inheritor" (it restructures the old set); all other
    # recipient new sets depend on that break — add edges inheritor → dependent.
    adj: dict[int, set[int]] = defaultdict(set)

    for oi in disrupted_old:
        dests = list(old_set_destinations[oi])
        tile_counts: dict[int, int] = {}
        for ni in dests:
            count = sum(
                1 for tile in new_board_sets[ni].tiles
                if _tile_key(tile) in old_membership
                and old_membership[_tile_key(tile)] == oi
            )
            tile_counts[ni] = count

        inheritor = max(tile_counts, key=lambda ni: tile_counts[ni])
        for ni in dests:
            if ni != inheritor:
                adj[inheritor].add(ni)

    # Step 5 — rack-tile sets that combine with tiles from disrupted sources.
    # Their formation depends on the other destinations of each disrupted source.
    for ni, ts in enumerate(new_board_sets):
        has_rack = any(_tile_key(t) in placed_keys for t in ts.tiles)
        if not has_rack:
            continue
        disrupted_sources: set[int] = set()
        for tile in ts.tiles:
            key = _tile_key(tile)
            if key not in placed_keys and key in old_membership:
                oi = old_membership[key]
                if oi in disrupted_old:
                    disrupted_sources.add(oi)
        for source_oi in disrupted_sources:
            for other_ni in old_set_destinations[source_oi]:
                if other_ni != ni:
                    adj[other_ni].add(ni)

    # Step 6 — longest path in the DAG + 1.
    # Use Kahn's topological-sort algorithm (BFS) so cycles in the adjacency
    # list don't cause infinite recursion.  Nodes inside a cycle never reach
    # in_degree 0, so they stay at dist=0 and are effectively ignored.
    if not adj:
        return 1  # disruption occurred but no sequential dependencies

    all_nodes: set[int] = set(adj.keys())
    for targets in adj.values():
        all_nodes |= targets

    in_degree: dict[int, int] = {n: 0 for n in all_nodes}
    for targets in adj.values():
        for v in targets:
            in_degree[v] += 1

    from collections import deque
    queue: deque[int] = deque(n for n in all_nodes if in_degree[n] == 0)
    dist: dict[int, int] = {n: 0 for n in all_nodes}

    while queue:
        u = queue.popleft()
        for v in adj.get(u, set()):
            if dist[u] + 1 > dist[v]:
                dist[v] = dist[u] + 1
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    return max(dist.values()) + 1
