"""Pre-computation of all valid set templates from an available tile pool.

Blueprint §3.4 — Set Enumeration Strategy:
  Runs:   4 colors × 66 start/length combos  = 264 max templates
  Groups: 13 numbers × 5 color-subset combos =  65 max templates
  Joker expansion adds variants where one tile is replaced by a joker.

Total candidate sets: typically 200–400. Trivially small for an ILP.

This module is intentionally separate from the ILP builder so that the
enumerated templates can be inspected and tested independently.

Note on copy_id:
  Templates are constructed with copy_id=0 as a placeholder. The ILP engine
  maps these abstract templates to specific physical tiles (copy_id 0 or 1)
  during model construction. Never use copy_id to identify physical tiles here.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations

from ..models.board_state import BoardState
from ..models.tile import Color, Tile
from ..models.tileset import SetType, TileSet


def enumerate_runs(state: BoardState) -> list[TileSet]:
    """Enumerate all valid run templates constructable from the available tile pool.

    A run template is included only if at least one physical copy of each
    required (color, number) tile exists in state.all_tiles.

    Args:
        state: The current board + rack state.

    Returns:
        A list of RUN TileSets. Up to 264 templates when the full pool is available.
    """
    # Count available non-joker tiles by (color, number).
    # None-guards narrow Color|None → Color and int|None → int for mypy.
    avail: Counter[tuple[Color, int]] = Counter(
        (t.color, t.number)
        for t in state.all_tiles
        if not t.is_joker and t.color is not None and t.number is not None
    )

    result: list[TileSet] = []
    for color in Color:
        for start in range(1, 12):  # 1 .. 11  (run must end ≤ 13)
            for end in range(start + 2, 14):  # start+2 .. 13  (length ≥ 3)
                required = [(color, n) for n in range(start, end + 1)]
                if all(avail[(c, n)] >= 1 for c, n in required):
                    tiles = [Tile(color=c, number=n, copy_id=0) for c, n in required]
                    result.append(TileSet(type=SetType.RUN, tiles=tiles))

    return result


def enumerate_groups(state: BoardState) -> list[TileSet]:
    """Enumerate all valid group templates constructable from the available tile pool.

    A group template is included only if at least one physical copy of each
    required (color, number) tile exists in state.all_tiles.

    Args:
        state: The current board + rack state.

    Returns:
        A list of GROUP TileSets. Up to 65 templates when the full pool is available.
        (13 numbers × (C(4,3) + C(4,4)) = 13 × 5 = 65)
    """
    avail: Counter[tuple[Color, int]] = Counter(
        (t.color, t.number)
        for t in state.all_tiles
        if not t.is_joker and t.color is not None and t.number is not None
    )

    result: list[TileSet] = []
    colors = list(Color)
    for number in range(1, 14):  # 1 .. 13
        for size in (3, 4):
            for color_combo in combinations(colors, size):
                required = [(c, number) for c in color_combo]
                if all(avail[(c, n)] >= 1 for c, n in required):
                    tiles = [Tile(color=c, number=number, copy_id=0) for c in color_combo]
                    result.append(TileSet(type=SetType.GROUP, tiles=tiles))

    return result


def enumerate_valid_sets(state: BoardState) -> list[TileSet]:
    """Return all valid set templates constructable from state.all_tiles.

    Combines run and group templates, plus single-joker expansion variants
    when at least one joker is available in the pool.

    Two types of joker variants are generated:
      Type 1 — substitute: joker replaces an *available* tile in a base
        template, freeing that tile for use in another set.
      Type 2 — fill-missing: joker fills a slot whose non-joker tile is
        *absent* from the pool, enabling templates that could not otherwise
        be formed.

    Only single-joker variants are generated; the ILP selects at most one
    joker per template via tile conservation constraints.

    Args:
        state: The current board + rack state.

    Returns:
        A list of TileSet objects — the candidate sets for the ILP.
        Typically 200–400 entries without jokers; up to ~2000 with jokers.
    """
    base = enumerate_runs(state) + enumerate_groups(state)

    joker_count = sum(1 for t in state.all_tiles if t.is_joker)
    if joker_count == 0:
        return base

    avail: Counter[tuple[Color, int]] = Counter(
        (t.color, t.number)
        for t in state.all_tiles
        if not t.is_joker and t.color is not None and t.number is not None
    )
    joker_ph = Tile.joker(copy_id=0)
    variants: list[TileSet] = []

    # Type 1: joker substitutes for a rack tile in a base template.
    # This frees the rack tile to go into a different (better) set.
    # We restrict to rack-tile slots only: freeing a board tile adds no
    # benefit (the ILP already handles all board-tile assignments via base
    # templates), but it generates O(board_tiles × templates) variants that
    # balloon the model and cause HiGHS to time out on complex boards.
    rack_tile_keys: set[tuple[Color, int]] = {
        (t.color, t.number)
        for t in state.rack
        if not t.is_joker and t.color is not None and t.number is not None
    }
    for tmpl in base:
        for p in range(len(tmpl.tiles)):
            slot = tmpl.tiles[p]
            if slot.color is None or slot.number is None:
                continue
            if (slot.color, slot.number) not in rack_tile_keys:
                continue
            new_tiles = list(tmpl.tiles)
            new_tiles[p] = joker_ph
            variants.append(TileSet(type=tmpl.type, tiles=new_tiles))

    # Type 2: joker fills the one MISSING slot in an otherwise formable set.
    # Runs with exactly 1 unavailable tile:
    for color in Color:
        for start in range(1, 12):
            for end in range(start + 2, 14):
                required = [(color, n) for n in range(start, end + 1)]
                missing = [(c, n) for c, n in required if avail[(c, n)] < 1]
                if len(missing) != 1:
                    continue
                missing_key = missing[0]
                run_tiles: list[Tile] = [
                    joker_ph if (c, n) == missing_key else Tile(color=c, number=n, copy_id=0)
                    for c, n in required
                ]
                variants.append(TileSet(type=SetType.RUN, tiles=run_tiles))

    # Groups with exactly 1 unavailable tile:
    colors = list(Color)
    for number in range(1, 14):
        for size in (3, 4):
            for color_combo in combinations(colors, size):
                required = [(c, number) for c in color_combo]
                missing = [(c, n) for c, n in required if avail[(c, n)] < 1]
                if len(missing) != 1:
                    continue
                missing_key = missing[0]
                grp_tiles: list[Tile] = [
                    joker_ph
                    if (c, number) == missing_key
                    else Tile(color=c, number=number, copy_id=0)
                    for c in color_combo
                ]
                variants.append(TileSet(type=SetType.GROUP, tiles=grp_tiles))

    return base + variants
