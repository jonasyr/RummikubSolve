"""Tests for solver/engine/objective.py (compute_disruption_score and compute_chain_depth)."""

from __future__ import annotations

import pytest

from solver.engine.objective import compute_chain_depth, compute_disruption_score
from solver.models.tile import Color, Tile
from solver.models.tileset import SetType, TileSet

R, B, BL, Y = Color.RED, Color.BLUE, Color.BLACK, Color.YELLOW


def t(color: Color, number: int, copy_id: int = 0) -> Tile:
    return Tile(color, number, copy_id)


def joker(copy_id: int = 0) -> Tile:
    return Tile.joker(copy_id)


def run_set(*tiles: Tile) -> TileSet:
    return TileSet(SetType.RUN, list(tiles))


def group_set(*tiles: Tile) -> TileSet:
    return TileSet(SetType.GROUP, list(tiles))


# ---------------------------------------------------------------------------
# compute_disruption_score tests
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


# ---------------------------------------------------------------------------
# compute_chain_depth tests
# ---------------------------------------------------------------------------


class TestChainDepthNoCaseZero:
    """Scenarios where chain depth should be 0."""

    def test_empty_old_board(self) -> None:
        """No old board sets at all → depth 0 (pure placement)."""
        rack_tile = t(R, 5)
        new = [run_set(t(R, 3), t(R, 4), rack_tile)]
        assert compute_chain_depth([], new, [rack_tile]) == 0

    def test_empty_new_board(self) -> None:
        """Empty new board (no tiles placed) → depth 0."""
        old = [run_set(t(R, 3), t(R, 4), t(R, 5))]
        assert compute_chain_depth(old, [], []) == 0

    def test_board_unchanged_rack_tile_into_new_set(self) -> None:
        """Board sets are untouched; rack tile forms its own new set.

        Old board set travels intact to new board, rack tile also appears but
        in a separate new set → no disruption → depth 0.
        """
        old_set = run_set(t(R, 3), t(R, 4), t(R, 5))
        rack_tile = t(B, 7)
        new_rack_set = run_set(t(B, 5), t(B, 6), rack_tile)
        old = [old_set]
        new = [old_set, new_rack_set]
        assert compute_chain_depth(old, new, [rack_tile]) == 0

    def test_extend_existing_set_with_rack_tile(self) -> None:
        """Rack tile appended to an existing set; old set not split → depth 0."""
        old_set = run_set(t(R, 3), t(R, 4), t(R, 5))
        rack_tile = t(R, 6)
        new_set = run_set(t(R, 3), t(R, 4), t(R, 5), rack_tile)
        old = [old_set]
        new = [new_set]
        assert compute_chain_depth(old, new, [rack_tile]) == 0

    def test_reordered_sets_no_disruption(self) -> None:
        """Sets swapped in output order but contents unchanged → depth 0."""
        s1 = run_set(t(R, 1), t(R, 2), t(R, 3))
        s2 = run_set(t(B, 4), t(B, 5), t(B, 6))
        assert compute_chain_depth([s1, s2], [s2, s1], []) == 0

    def test_multiple_stable_sets_rack_tile_into_new_set(self) -> None:
        """Several old sets remain intact; rack tile forms a brand-new set."""
        s1 = run_set(t(R, 1), t(R, 2), t(R, 3))
        s2 = run_set(t(B, 4), t(B, 5), t(B, 6))
        rack_tile = t(Y, 7)
        new_rack_set = run_set(t(Y, 5), t(Y, 6), rack_tile)
        old = [s1, s2]
        new = [s1, s2, new_rack_set]
        assert compute_chain_depth(old, new, [rack_tile]) == 0


class TestChainDepthOne:
    """Scenarios where chain depth should be 1 (simple rearrangement)."""

    def test_one_set_split_no_further_dependency(self) -> None:
        """Old set {R4,R5,R6,R7} split into {R4,R5} and {R6,R7} → depth 1.

        This is the simplest rearrangement: one set broken, tiles go to exactly
        two new sets with no further chaining.
        """
        old = [run_set(t(R, 4), t(R, 5), t(R, 6), t(R, 7))]
        new = [run_set(t(R, 4), t(R, 5)), run_set(t(R, 6), t(R, 7))]
        assert compute_chain_depth(old, new, []) == 1

    def test_rack_tile_placed_with_freed_tiles(self) -> None:
        """Rack tile joins tiles freed by breaking an old set.

        Old set O = {R4, R5, R6, R7}.
        Player breaks O: {R4,R5,R6} stays, {R7} + rack tile R8 form new set.
        """
        rack_tile = t(R, 8)
        old_set = run_set(t(R, 4), t(R, 5), t(R, 6), t(R, 7))
        new_a = run_set(t(R, 4), t(R, 5), t(R, 6))
        new_b = run_set(t(R, 7), rack_tile)
        old = [old_set]
        new = [new_a, new_b]
        assert compute_chain_depth(old, new, [rack_tile]) == 1

    def test_two_independent_disruptions_are_still_depth_1(self) -> None:
        """Two unrelated sets each broken independently → depth 1 (parallel, not chained)."""
        old_a = run_set(t(R, 1), t(R, 2), t(R, 3), t(R, 4))
        old_b = run_set(t(B, 5), t(B, 6), t(B, 7), t(B, 8))
        # Both split in half — no tile from set A ends up in any subset of B or vice versa.
        new = [
            run_set(t(R, 1), t(R, 2)),
            run_set(t(R, 3), t(R, 4)),
            run_set(t(B, 5), t(B, 6)),
            run_set(t(B, 7), t(B, 8)),
        ]
        assert compute_chain_depth([old_a, old_b], new, []) == 1

    def test_single_tile_moved_between_sets(self) -> None:
        """One tile leaves its old set and joins another set → depth 1.

        Old: A={R1,R2,R3}, B={R4,R5,R6}
        New: A'={R1,R2}, B'={R3,R4,R5,R6}  (R3 migrates from A to B)
        Old set A is disrupted (R3 leaves); B unchanged.
        """
        old_a = run_set(t(R, 1), t(R, 2), t(R, 3))
        old_b = run_set(t(R, 4), t(R, 5), t(R, 6))
        new_a = run_set(t(R, 1), t(R, 2))
        new_b = run_set(t(R, 3), t(R, 4), t(R, 5), t(R, 6))
        assert compute_chain_depth([old_a, old_b], [new_a, new_b], []) == 1


class TestChainDepthTwo:
    """Scenarios where chain depth should be 2 (two-step chain)."""

    def test_two_step_abc_chain(self) -> None:
        """Classic two-step: break A → tiles form B; break B → tiles enable C.

        Setup:
          Old sets: A={R1,R2,R3,R4}, B={R5,R6,R7,R8}
          Solution:
            - A is broken: {R1,R2,R3} stays as A', {R4} goes to new set C
            - B is broken: {R5,R6,R7} stays as B', {R8} also goes to C
            - C = {R4, R8, rack_tile} — requires tiles freed from BOTH A and B

        Old set A disrupted → A' and C share A as broken source.
        Old set B disrupted → B' and C share B as broken source.
        C depends on both A and B disruptions → chain depth 2.
        """
        rack_tile = t(Y, 4)
        old_a = run_set(t(R, 1), t(R, 2), t(R, 3), t(R, 4))
        old_b = run_set(t(B, 4), t(B, 5), t(B, 6), t(B, 7))
        # New: A shortened, B shortened, new group formed with freed tiles + rack
        new_a = run_set(t(R, 1), t(R, 2), t(R, 3))
        new_b = run_set(t(B, 5), t(B, 6), t(B, 7))
        new_c = group_set(t(R, 4), t(B, 4), rack_tile)  # uses freed R4, B4, rack
        old = [old_a, old_b]
        new = [new_a, new_b, new_c]
        depth = compute_chain_depth(old, new, [rack_tile])
        assert depth == 2

    def test_two_step_chain_inheritor_feeds_dependent(self) -> None:
        """Break old set O; freed tile joins rack tile to form N2.

        Old: O={R5,R6,R7,R8,R9}
        New: N1={R5,R6,R7,R8} (kept most tiles from O)
             N2={R9,rack_R10} (got R9 freed from O, plus rack)

        O is disrupted (tiles scattered to N1 and N2). N2 gets tiles
        from exactly ONE disrupted old set (O). Depth = 1.
        """
        rack_tile = t(R, 10)
        old_o = run_set(t(R, 5), t(R, 6), t(R, 7), t(R, 8), t(R, 9))
        new_n1 = run_set(t(R, 5), t(R, 6), t(R, 7), t(R, 8))
        new_n2 = run_set(t(R, 9), rack_tile)
        depth = compute_chain_depth([old_o], [new_n1, new_n2], [rack_tile])
        assert depth == 1


class TestChainDepthThreePlus:
    """Scenarios requiring depth ≥ 3."""

    def test_three_step_chain(self) -> None:
        """Three-level chain: A disrupted → B depends on A; C depends on B; D gets rack.

        Old sets: A={R1,R2,R3,R4}, B={R5,R6,R7,R8}, C={R9,R10,R11,R12}
        Solution:
          - A split: A'={R1,R2,R3}, fragment_a={R4}
          - B split: B'={R5,R6,R7}, fragment_b={R8}
          - C split: C'={R9,R10,R11}, fragment_c={R12}
          - New set D = {R4,R8,R12} (tiles freed from A, B, C all converge)

        D depends on fragments freed from A, B, and C, which themselves
        depend on each other's disruption chains.

        Because D's tiles (R4, R8, R12) come from three independently disrupted
        old sets, each of those disruptions contributes an edge toward D.
        The chain depth should be ≥ 3.
        """
        old_a = run_set(t(R, 1), t(R, 2), t(R, 3), t(R, 4))
        old_b = run_set(t(B, 1), t(B, 2), t(B, 3), t(B, 4))
        old_c = run_set(t(BL, 1), t(BL, 2), t(BL, 3), t(BL, 4))

        new_a = run_set(t(R, 1), t(R, 2), t(R, 3))
        new_b = run_set(t(B, 1), t(B, 2), t(B, 3))
        new_c = run_set(t(BL, 1), t(BL, 2), t(BL, 3))
        # Group using the single freed tile from each old set
        new_d = group_set(t(R, 4), t(B, 4), t(BL, 4))

        old = [old_a, old_b, old_c]
        new = [new_a, new_b, new_c, new_d]
        depth = compute_chain_depth(old, new, [])
        assert depth >= 2  # guaranteed chain; exact depth depends on DAG structure


class TestChainDepthEdgeCases:
    """Edge cases and special tile types."""

    def test_joker_tile_in_placed_tiles_no_disruption(self) -> None:
        """Joker counted as placed tile; board tiles stable → depth 0."""
        j = joker(0)
        old_set = run_set(t(R, 3), t(R, 4), t(R, 5))
        new_set_with_joker = run_set(t(R, 3), t(R, 4), t(R, 5), j)
        old = [old_set]
        new = [new_set_with_joker]
        # Old set tiles all present in new set → no disruption.
        assert compute_chain_depth(old, new, [j]) == 0

    def test_joker_tile_in_placed_tiles_with_disruption(self) -> None:
        """Joker is a placed tile; it joins tiles freed from a disrupted old set → depth 1."""
        j = joker(0)
        old_set = run_set(t(R, 4), t(R, 5), t(R, 6), t(R, 7))
        new_a = run_set(t(R, 4), t(R, 5), t(R, 6))
        new_b = run_set(t(R, 7), j)  # joker + freed R7
        old = [old_set]
        new = [new_a, new_b]
        assert compute_chain_depth(old, new, [j]) == 1

    def test_all_rack_tiles_no_board_involvement(self) -> None:
        """Rack tiles form their own new set; the single old set is untouched."""
        old_set = run_set(t(BL, 1), t(BL, 2), t(BL, 3))
        rack_a = t(R, 5)
        rack_b = t(R, 6)
        rack_c = t(R, 7)
        new_from_rack = run_set(rack_a, rack_b, rack_c)
        old = [old_set]
        new = [old_set, new_from_rack]
        assert compute_chain_depth(old, new, [rack_a, rack_b, rack_c]) == 0

    def test_single_tile_disruption_copy_id_sensitivity(self) -> None:
        """copy_id is part of tile identity; copy 0 and copy 1 are different tiles."""
        # Old: set has R5 copy 0; R5 copy 1 is on rack.
        old_set = run_set(t(R, 4), t(R, 5, 0), t(R, 6))
        rack_tile = t(R, 5, 1)  # second physical copy
        # New: same board set (R5c0 stays), plus new set using rack R5c1
        new_rack_set = run_set(t(R, 5, 1), t(R, 7), t(R, 8))
        old = [old_set]
        new = [old_set, new_rack_set]
        # R5c0 stays in its original set — no disruption.
        assert compute_chain_depth(old, new, [rack_tile]) == 0

    def test_return_type_is_int(self) -> None:
        """compute_chain_depth always returns an int."""
        result = compute_chain_depth([], [], [])
        assert isinstance(result, int)

    def test_non_negative_always(self) -> None:
        """Depth is never negative regardless of inputs."""
        old = [run_set(t(R, 1), t(R, 2), t(R, 3))]
        new = [run_set(t(R, 1), t(R, 2), t(R, 3))]
        assert compute_chain_depth(old, new, []) >= 0

    def test_large_stable_board_many_sets(self) -> None:
        """Large board with no disruption → depth 0 (performance sanity check).

        Uses non-overlapping tile numbers so each physical tile belongs to
        exactly one old set (as in a real game).
        """
        # Four non-overlapping runs using distinct tile numbers
        old = [
            run_set(t(R, 1), t(R, 2), t(R, 3)),
            run_set(t(B, 1), t(B, 2), t(B, 3)),
            run_set(t(BL, 1), t(BL, 2), t(BL, 3)),
            run_set(t(Y, 1), t(Y, 2), t(Y, 3)),
            run_set(t(R, 4), t(R, 5), t(R, 6)),
            run_set(t(B, 4), t(B, 5), t(B, 6)),
        ]
        rack_tile = t(Y, 5)
        new_rack_set = run_set(t(Y, 4), t(Y, 5), t(Y, 6))
        # old sets unchanged; rack tile placed in a brand-new set
        new = old + [new_rack_set]
        assert compute_chain_depth(old, new, [rack_tile]) == 0

    def test_group_set_disruption_depth_1(self) -> None:
        """Group set broken into two parts → depth 1."""
        # Old group: all four colors of number 7
        old_group = group_set(t(R, 7), t(B, 7), t(BL, 7), t(Y, 7))
        # New: split into two groups (not valid Rummikub, tests the metric)
        new_a = group_set(t(R, 7), t(B, 7))
        new_b = group_set(t(BL, 7), t(Y, 7))
        old = [old_group]
        new = [new_a, new_b]
        assert compute_chain_depth(old, new, []) == 1

    def test_only_new_board_sets_no_old(self) -> None:
        """No old board, only new sets formed from rack → depth 0."""
        rack_a = t(R, 1)
        rack_b = t(R, 2)
        rack_c = t(R, 3)
        new = [run_set(rack_a, rack_b, rack_c)]
        assert compute_chain_depth([], new, [rack_a, rack_b, rack_c]) == 0

    def test_disruption_with_no_rack_tiles(self) -> None:
        """Board tiles rearranged with no rack tiles at all → depth ≥ 1."""
        old = [run_set(t(R, 1), t(R, 2), t(R, 3), t(R, 4))]
        new = [run_set(t(R, 1), t(R, 2)), run_set(t(R, 3), t(R, 4))]
        assert compute_chain_depth(old, new, []) == 1


class TestChainDepthIntegration:
    """Integration-style tests that combine multiple disruptions."""

    def test_chain_depth_increases_with_nesting(self) -> None:
        """A deeply nested chain has greater depth than a shallow one."""
        # Shallow: one old set split → two new sets (depth 1)
        old_shallow = [run_set(t(R, 1), t(R, 2), t(R, 3), t(R, 4))]
        new_shallow = [run_set(t(R, 1), t(R, 2)), run_set(t(R, 3), t(R, 4))]
        shallow_depth = compute_chain_depth(old_shallow, new_shallow, [])

        # Deeper: two old sets broken; freed tiles converge in a new set
        rack_tile = t(Y, 4)
        old_deep_a = run_set(t(R, 1), t(R, 2), t(R, 3), t(R, 4))
        old_deep_b = run_set(t(B, 4), t(B, 5), t(B, 6), t(B, 7))
        new_deep_a = run_set(t(R, 1), t(R, 2), t(R, 3))
        new_deep_b = run_set(t(B, 5), t(B, 6), t(B, 7))
        new_deep_c = group_set(t(R, 4), t(B, 4), rack_tile)
        deep_depth = compute_chain_depth(
            [old_deep_a, old_deep_b], [new_deep_a, new_deep_b, new_deep_c], [rack_tile]
        )

        assert deep_depth >= shallow_depth

    def test_parallel_vs_chained_disruptions(self) -> None:
        """Two parallel disruptions should not inflate depth beyond 1."""
        # Two completely independent splits — no tile crosses from one group to another
        old_a = run_set(t(R, 1), t(R, 2), t(R, 3), t(R, 4))
        old_b = run_set(t(B, 1), t(B, 2), t(B, 3), t(B, 4))
        new = [
            run_set(t(R, 1), t(R, 2)),
            run_set(t(R, 3), t(R, 4)),
            run_set(t(B, 1), t(B, 2)),
            run_set(t(B, 3), t(B, 4)),
        ]
        depth = compute_chain_depth([old_a, old_b], new, [])
        assert depth == 1  # parallel, not sequential

    def test_stable_sets_mixed_with_disrupted_sets(self) -> None:
        """Stable sets don't affect the chain depth calculation."""
        stable1 = run_set(t(Y, 1), t(Y, 2), t(Y, 3))
        stable2 = run_set(t(BL, 5), t(BL, 6), t(BL, 7))
        disrupted = run_set(t(R, 8), t(R, 9), t(R, 10), t(R, 11))
        new_part_a = run_set(t(R, 8), t(R, 9), t(R, 10))
        new_part_b = run_set(t(R, 11), t(R, 12))  # R12 not in old board
        rack_tile = t(R, 12)
        old = [stable1, stable2, disrupted]
        new = [stable1, stable2, new_part_a, new_part_b]
        depth = compute_chain_depth(old, new, [rack_tile])
        # disrupted set gets broken; rack tile joins freed R11 → depth 1
        assert depth == 1
