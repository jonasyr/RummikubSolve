"""Fast, pure-function structural gates for pre- and post-ILP puzzle filtering.

All functions are side-effect-free and make no solver calls. They form the first
rejection layer in the template-based generation pipeline.

See PUZZLE_GENERATION_REBUILD_PLAN.md §4.2.3.
"""
from __future__ import annotations

__all__ = [
    "check_no_trivial_extension",
    "check_no_single_home",
    "check_joker_structural",
    "run_pre_ilp_gates",
    "run_post_ilp_gates",
]

from solver.models.board_state import BoardState, Solution
from solver.models.tile import Color, Tile
from solver.models.tileset import TileSet
from solver.validator.rule_checker import is_valid_set

# Type alias for the sibling-tile fingerprint used in joker tracking.
_SiblingKey = tuple[Color | None, int | None, int]


def check_no_trivial_extension(
    rack: list[Tile], board_sets: list[TileSet]
) -> tuple[bool, str]:
    """Return (False, reason) if any rack tile trivially extends any board set.

    This is the *strict* version: unlike ``_any_trivial_extension_v2`` in
    ``puzzle_generator.py``, it checks board sets of any size including 1- and
    2-tile partial stubs.  ``is_valid_set`` sorts numbers internally so
    appending is sufficient (prepend gives the same verdict).

    Reason format: ``"trivial_extension:<color>:<number>:<copy_id>:<set_idx>"``
    """
    for tile in rack:
        for idx, ts in enumerate(board_sets):
            candidate = TileSet(type=ts.type, tiles=ts.tiles + [tile])
            if is_valid_set(candidate):
                tile_repr = f"{tile.color}:{tile.number}:{tile.copy_id}"
                return False, f"trivial_extension:{tile_repr}:{idx}"
    return True, ""


def check_no_single_home(
    rack: list[Tile], candidate_sets: list[TileSet]
) -> tuple[bool, str]:
    """Return (False, reason) if any non-joker rack tile has exactly one candidate home.

    A rack tile's "home count" is the number of candidate sets that contain a
    non-joker tile with the same ``(color, number)``.  Joker rack tiles are
    skipped because they can fill any slot.

    Reason format: ``"single_home:<color>:<number>:<copy_id>"``
    """
    for tile in rack:
        if tile.is_joker:
            continue
        homes = sum(
            1
            for cs in candidate_sets
            if any(
                not t.is_joker and t.color == tile.color and t.number == tile.number
                for t in cs.tiles
            )
        )
        if homes == 1:
            tile_repr = f"{tile.color}:{tile.number}:{tile.copy_id}"
            return False, f"single_home:{tile_repr}"
    return True, ""


def check_joker_structural(
    state: BoardState, solution: Solution
) -> tuple[bool, str]:
    """Return (False, reason) if a board joker was not displaced by the solution.

    For each joker in ``state.board_sets`` we compute a fingerprint of its
    sibling tiles (the non-joker tiles in the same set).  If the same joker
    ends up in a new set with an identical sibling fingerprint it was never
    moved.

    This is a post-ILP gate: it requires the solved ``Solution``.

    Reason format: ``"board_joker_idle:copy_id=<n>"``
    """
    # Build: copy_id → frozenset of sibling (color, number, copy_id) keys
    board_joker_siblings: dict[int, frozenset[_SiblingKey]] = {}
    for ts in state.board_sets:
        for tile in ts.tiles:
            if tile.is_joker:
                siblings: frozenset[_SiblingKey] = frozenset(
                    (t.color, t.number, t.copy_id)
                    for t in ts.tiles
                    if not t.is_joker
                )
                board_joker_siblings[tile.copy_id] = siblings

    if not board_joker_siblings:
        return True, ""

    # Find where each board joker ended up in the solution's new board.
    joker_new_siblings: dict[int, frozenset[_SiblingKey]] = {}
    for ts in solution.new_sets:
        for tile in ts.tiles:
            if tile.is_joker:
                new_siblings: frozenset[_SiblingKey] = frozenset(
                    (t.color, t.number, t.copy_id)
                    for t in ts.tiles
                    if not t.is_joker
                )
                joker_new_siblings[tile.copy_id] = new_siblings

    for copy_id, orig_siblings in board_joker_siblings.items():
        new_siblings_for_joker = joker_new_siblings.get(copy_id)
        if new_siblings_for_joker == orig_siblings:
            return False, f"board_joker_idle:copy_id={copy_id}"

    return True, ""


def run_pre_ilp_gates(
    rack: list[Tile],
    board_sets: list[TileSet],
    candidate_sets: list[TileSet],
) -> tuple[bool, list[str]]:
    """Run all pre-ILP structural gates and collect every failure reason.

    Returns ``(True, [])`` if all gates pass; ``(False, reasons)`` otherwise.
    All gates are always evaluated so the caller receives a full rejection report.
    """
    reasons: list[str] = []

    ok, reason = check_no_trivial_extension(rack, board_sets)
    if not ok:
        reasons.append(reason)

    ok, reason = check_no_single_home(rack, candidate_sets)
    if not ok:
        reasons.append(reason)

    return not reasons, reasons


def run_post_ilp_gates(
    state: BoardState, solution: Solution
) -> tuple[bool, list[str]]:
    """Run all post-ILP structural gates and collect every failure reason.

    Returns ``(True, [])`` if all gates pass; ``(False, reasons)`` otherwise.
    """
    reasons: list[str] = []

    ok, reason = check_joker_structural(state, solution)
    if not ok:
        reasons.append(reason)

    return not reasons, reasons
