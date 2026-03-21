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

    # Count physical copies of each (color, number) tile in the pool.
    # Rummikub has 2 copies of every tile, so the board can contain two
    # identical valid sets (e.g. two [1R,2R,3R] runs). The ILP uses a
    # binary y[s] per template, so each template can only be activated once.
    # We must include each template N times (N = min copies of required tiles)
    # so the ILP can assign distinct physical tile copies to each instance.
    avail: Counter[tuple[Color, int]] = Counter(
        (t.color, t.number)
        for t in state.all_tiles
        if not t.is_joker and t.color is not None and t.number is not None
    )
    expanded: list[TileSet] = []
    for tmpl in base:
        required = [
            (t.color, t.number)
            for t in tmpl.tiles
            if not t.is_joker and t.color is not None and t.number is not None
        ]
        n_copies = min((avail[(c, n)] for c, n in required), default=1)
        for _ in range(n_copies):
            expanded.append(tmpl)
    base = expanded

    joker_count = sum(1 for t in state.all_tiles if t.is_joker)
    if joker_count == 0:
        return base

    joker_ph = Tile.joker(copy_id=0)
    variants: list[TileSet] = []

    # Type 1: joker substitutes for any tile in a base template.
    # This allows the physical joker (whether a board tile or rack tile) to
    # occupy a slot in a template, freeing the original tile for another set.
    # We must generate variants for ALL positions — restricting to rack-tile
    # slots only causes infeasibility when the joker is a board tile and the
    # tile it covers in the original set is also present in the pool as another
    # board tile (so type 2 "fill-missing" won't generate the template either).
    # Deduplication via fingerprints prevents identical templates from being
    # added twice (e.g. when type 1 and type 2 would produce the same variant).
    seen_variants: set[tuple] = set()

    for tmpl in base:
        for p in range(len(tmpl.tiles)):
            slot = tmpl.tiles[p]
            if slot.color is None or slot.number is None:
                continue  # already a joker slot — skip
            new_tiles = list(tmpl.tiles)
            new_tiles[p] = joker_ph
            fp = (tmpl.type, tuple((t.is_joker, t.color, t.number) for t in new_tiles))
            if fp not in seen_variants:
                seen_variants.add(fp)
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
                fp2 = (SetType.RUN, tuple((t.is_joker, t.color, t.number) for t in run_tiles))
                if fp2 not in seen_variants:
                    seen_variants.add(fp2)
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
                fp2 = (SetType.GROUP, tuple((t.is_joker, t.color, t.number) for t in grp_tiles))
                if fp2 not in seen_variants:
                    seen_variants.add(fp2)
                    variants.append(TileSet(type=SetType.GROUP, tiles=grp_tiles))

    return base + variants
