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


def test_full_disruption_all_tiles_moved() -> None:
    """All tiles moved to a different set index → disruption = tile count."""
    old = [run_set(t(R, 4), t(R, 5), t(R, 6)), run_set(t(B, 7), t(B, 8), t(B, 9))]
    # Swap the two sets (each tile now has a different set index).
    new = [old[1], old[0]]
    assert compute_disruption_score(old, new) == 6  # all 6 tiles moved


def test_partial_disruption() -> None:
    """Only tiles in the rearranged set count as disrupted."""
    set_a = run_set(t(R, 4), t(R, 5), t(R, 6))
    set_b = run_set(t(B, 7), t(B, 8), t(B, 9))
    # set_a stays at index 0; set_b extended with Blue 10 at index 1.
    set_b_extended = run_set(t(B, 7), t(B, 8), t(B, 9), t(B, 10))
    old = [set_a, set_b]
    new = [set_a, set_b_extended]
    # Blue 7, 8, 9 remain in index 1 → 0 disrupted from old board tiles.
    assert compute_disruption_score(old, new) == 0


def test_empty_boards() -> None:
    """Empty old and new boards → disruption = 0."""
    assert compute_disruption_score([], []) == 0


def test_tile_same_set_different_copy_id() -> None:
    """Different copy_id values are treated as different physical tiles."""
    # Old board: Red 5 copy 0 in set 0.
    old = [run_set(t(R, 4), t(R, 5, 0), t(R, 6))]
    # New board: Red 5 copy 1 in set 0 (copy 0 is now elsewhere).
    new = [run_set(t(R, 4), t(R, 5, 1), t(R, 6))]
    # Red 5 copy 0 is not in any new set → disrupted (missing from new_assignment).
    # Red 4 and Red 6 are in same index → not disrupted.
    assert compute_disruption_score(old, new) == 1
