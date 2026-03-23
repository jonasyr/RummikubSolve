"""Tests for solver/engine/objective.py (compute_disruption_score)."""

from __future__ import annotations

from solver.engine.objective import compute_disruption_score
from solver.models.tile import Color, Tile
from solver.models.tileset import SetType, TileSet

R, B, BL, Y = Color.RED, Color.BLUE, Color.BLACK, Color.YELLOW


def t(color: Color, number: int, copy_id: int = 0) -> Tile:
    return Tile(color, number, copy_id)


def run_set(*tiles: Tile) -> TileSet:
    return TileSet(SetType.RUN, list(tiles))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_disruption_identical_boards() -> None:
    """Same sets in same order → disruption = 0."""
    sets = [run_set(t(R, 4), t(R, 5), t(R, 6))]
    assert compute_disruption_score(sets, sets) == 0


def test_no_disruption_reordered_sets() -> None:
    """Swapping complete sets (same content, different order) → disruption = 0.

    The new content-based algorithm is reordering-invariant.
    The old index-based algorithm incorrectly returned 6 in this case.
    """
    old = [run_set(t(R, 4), t(R, 5), t(R, 6)), run_set(t(B, 7), t(B, 8), t(B, 9))]
    new = [old[1], old[0]]  # Swap the two sets.
    assert compute_disruption_score(old, new) == 0


def test_disruption_split_set() -> None:
    """One old set split across two new sets → disrupted tiles counted."""
    # Old: one run of 4.
    old = [run_set(t(R, 4), t(R, 5), t(R, 6), t(R, 7))]
    # New: split into two sets of 2 (invalid Rummikub, but tests the metric).
    new = [run_set(t(R, 4), t(R, 5)), run_set(t(R, 6), t(R, 7))]
    # Best match for old set: whichever new set has 2 tiles → 2 tiles in best set.
    # 4 - 2 = 2 disrupted.
    assert compute_disruption_score(old, new) == 2


def test_no_disruption_set_extended_with_rack_tile() -> None:
    """Old set extended by a rack tile → disruption = 0 (tiles stay grouped)."""
    set_a = run_set(t(R, 4), t(R, 5), t(R, 6))
    set_b = run_set(t(B, 7), t(B, 8), t(B, 9))
    set_b_extended = run_set(t(B, 7), t(B, 8), t(B, 9), t(B, 10))
    old = [set_a, set_b]
    new = [set_a, set_b_extended]
    # B7, B8, B9 all end up in the same new set → 0 disrupted.
    assert compute_disruption_score(old, new) == 0


def test_full_disruption_tiles_scattered() -> None:
    """All tiles from one old set end up in different new sets → max disruption."""
    # Old: one set {R4, R5, R6}.
    old = [run_set(t(R, 4), t(R, 5), t(R, 6))]
    # New: each tile in its own set (not valid Rummikub, but tests the metric).
    new = [run_set(t(R, 4)), run_set(t(R, 5)), run_set(t(R, 6))]
    # Best match: 1 tile in best set → 3 - 1 = 2 disrupted.
    assert compute_disruption_score(old, new) == 2


def test_empty_boards() -> None:
    """Empty old and new boards → disruption = 0."""
    assert compute_disruption_score([], []) == 0


def test_tile_same_set_different_copy_id() -> None:
    """Different copy_id values are treated as different physical tiles."""
    # Old board: Red 5 copy 0 in the set.
    old = [run_set(t(R, 4), t(R, 5, 0), t(R, 6))]
    # New board: Red 5 copy 1 replaces copy 0 (copy 0 is absent).
    new = [run_set(t(R, 4), t(R, 5, 1), t(R, 6))]
    # R4 and R6 vote for new set 0; R5c0 is missing from new_assignment.
    # best_count = 2, disrupted += 3 - 2 = 1.
    assert compute_disruption_score(old, new) == 1


def test_multiple_sets_partial_disruption() -> None:
    """Only tiles in rearranged sets count as disrupted; stable sets score 0."""
    stable = run_set(t(BL, 1), t(BL, 2), t(BL, 3))
    old_moving = run_set(t(R, 7), t(R, 8), t(R, 9))
    # Stable set unchanged; moving set split: R7 joins another set, R8+R9 stay.
    new_moving_a = run_set(t(R, 8), t(R, 9))
    new_moving_b = run_set(t(R, 7), t(Y, 7), t(B, 7))  # R7 in a group now
    old = [stable, old_moving]
    new = [stable, new_moving_a, new_moving_b]
    # stable: all 3 tiles in same new set → 0 disrupted.
    # old_moving: R8+R9 in new_moving_a (vote 2), R7 in new_moving_b (vote 1).
    #   best_count = 2, disrupted += 3 - 2 = 1.
    assert compute_disruption_score(old, new) == 1
