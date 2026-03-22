"""Tests for solver/generator/set_enumerator.py.

Verifies template counts with known-answer arithmetic and spot-checks
that specific expected templates are present / absent.
"""

from __future__ import annotations

from solver.generator.set_enumerator import (
    enumerate_groups,
    enumerate_runs,
    enumerate_valid_sets,
)
from solver.models.board_state import BoardState
from solver.models.tile import Color, Tile
from solver.models.tileset import SetType, TileSet

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_state(*tiles: Tile) -> BoardState:
    """BoardState with the given tiles on the rack, empty board."""
    return BoardState(board_sets=[], rack=list(tiles))


def has_run(templates: list[TileSet], color: Color, start: int, end: int) -> bool:
    """Return True if a run [color start..end] is in templates."""
    expected = {(color, n) for n in range(start, end + 1)}
    for ts in templates:
        if ts.type == SetType.RUN:
            actual = {(t.color, t.number) for t in ts.tiles}
            if actual == expected:
                return True
    return False


def has_group(templates: list[TileSet], number: int, *colors: Color) -> bool:
    """Return True if a group of number with exactly colors is in templates."""
    expected = {(c, number) for c in colors}
    for ts in templates:
        if ts.type == SetType.GROUP:
            actual = {(t.color, t.number) for t in ts.tiles}
            if actual == expected:
                return True
    return False


# ---------------------------------------------------------------------------
# Full-pool counts (all 104 non-joker tiles available)
# ---------------------------------------------------------------------------


def test_enumerate_runs_full_pool_count(full_tile_pool: BoardState) -> None:
    # 4 colors × 66 start/length combos = 264 run templates.
    runs = enumerate_runs(full_tile_pool)
    assert len(runs) == 264


def test_enumerate_groups_full_pool_count(full_tile_pool: BoardState) -> None:
    # 13 numbers × (C(4,3) + C(4,4)) = 13 × 5 = 65 group templates.
    groups = enumerate_groups(full_tile_pool)
    assert len(groups) == 65


def test_enumerate_valid_sets_full_pool_total(full_tile_pool: BoardState) -> None:
    total = enumerate_valid_sets(full_tile_pool)
    # Each of the 329 templates (264 runs + 65 groups) is duplicated once because
    # the full pool contains 2 physical copies of every tile. The ILP needs N copies
    # of a template to be able to assign distinct physical copies to each instance.
    assert len(total) == 658  # 329 templates × 2 copies each


def test_enumerate_valid_sets_is_union(full_tile_pool: BoardState) -> None:
    runs = enumerate_runs(full_tile_pool)
    groups = enumerate_groups(full_tile_pool)
    total = enumerate_valid_sets(full_tile_pool)
    # Full pool has 2 copies of every tile → each template appears twice.
    assert len(total) == 2 * (len(runs) + len(groups))


# ---------------------------------------------------------------------------
# Spot-checks: specific templates present / absent
# ---------------------------------------------------------------------------


def test_full_pool_contains_red_456(full_tile_pool: BoardState) -> None:
    assert has_run(enumerate_runs(full_tile_pool), Color.RED, 4, 6)


def test_full_pool_contains_blue_1_to_13(full_tile_pool: BoardState) -> None:
    assert has_run(enumerate_runs(full_tile_pool), Color.BLUE, 1, 13)


def test_full_pool_contains_group_7_three_colors(full_tile_pool: BoardState) -> None:
    assert has_group(
        enumerate_groups(full_tile_pool),
        7,
        Color.BLUE,
        Color.RED,
        Color.BLACK,
    )


def test_full_pool_contains_group_1_all_colors(full_tile_pool: BoardState) -> None:
    assert has_group(
        enumerate_groups(full_tile_pool),
        1,
        Color.BLUE,
        Color.RED,
        Color.BLACK,
        Color.YELLOW,
    )


# ---------------------------------------------------------------------------
# Minimal pool: only Red 4, Red 5, Red 6 (one copy each)
# ---------------------------------------------------------------------------


def test_minimal_run_pool_single_run() -> None:
    state = make_state(
        Tile(Color.RED, 4, 0),
        Tile(Color.RED, 5, 0),
        Tile(Color.RED, 6, 0),
    )
    runs = enumerate_runs(state)
    assert len(runs) == 1
    assert has_run(runs, Color.RED, 4, 6)


def test_minimal_run_pool_no_groups() -> None:
    state = make_state(
        Tile(Color.RED, 4, 0),
        Tile(Color.RED, 5, 0),
        Tile(Color.RED, 6, 0),
    )
    assert enumerate_groups(state) == []


def test_minimal_pool_no_longer_run_when_tile_missing() -> None:
    # Only Red 4 and Red 6 — no Red 5 → no run containing 5.
    state = make_state(
        Tile(Color.RED, 4, 0),
        Tile(Color.RED, 6, 0),
    )
    runs = enumerate_runs(state)
    assert not any(any(t.number == 5 for t in ts.tiles) for ts in runs)
    assert len(runs) == 0  # 4-6 span requires 5, which is absent


# ---------------------------------------------------------------------------
# Groups — one number available in all 4 colors
# ---------------------------------------------------------------------------


def test_one_number_all_colors_five_group_templates() -> None:
    # All four copies of "7" (one per color, one copy_id each).
    state = make_state(
        Tile(Color.BLUE, 7, 0),
        Tile(Color.RED, 7, 0),
        Tile(Color.BLACK, 7, 0),
        Tile(Color.YELLOW, 7, 0),
    )
    groups = enumerate_groups(state)
    # C(4,3) = 4 size-3 groups + C(4,4) = 1 size-4 group = 5 total.
    assert len(groups) == 5


def test_one_number_three_colors_only_four_group_templates() -> None:
    # "7" in Blue, Red, Black only — no Yellow.
    state = make_state(
        Tile(Color.BLUE, 7, 0),
        Tile(Color.RED, 7, 0),
        Tile(Color.BLACK, 7, 0),
    )
    groups = enumerate_groups(state)
    # Only 1 size-3 combination possible (Blue+Red+Black); no size-4 (Yellow missing).
    assert len(groups) == 1


def test_missing_color_excludes_groups_requiring_it() -> None:
    # No Black tiles at all — no groups should include Black.
    non_black = (Color.BLUE, Color.RED, Color.YELLOW)
    state = make_state(*[Tile(color, n, 0) for color in non_black for n in range(1, 14)])
    groups = enumerate_groups(state)
    for ts in groups:
        for tile in ts.tiles:
            assert tile.color != Color.BLACK


# ---------------------------------------------------------------------------
# Empty pool
# ---------------------------------------------------------------------------


def test_empty_pool_no_runs() -> None:
    state = BoardState(board_sets=[], rack=[])
    assert enumerate_runs(state) == []


def test_empty_pool_no_groups() -> None:
    state = BoardState(board_sets=[], rack=[])
    assert enumerate_groups(state) == []


def test_empty_pool_no_sets() -> None:
    state = BoardState(board_sets=[], rack=[])
    assert enumerate_valid_sets(state) == []


# ---------------------------------------------------------------------------
# All templates are valid runs or groups (sanity cross-check with rule_checker)
# ---------------------------------------------------------------------------


def test_all_enumerated_sets_are_valid(full_tile_pool: BoardState) -> None:
    from solver.validator.rule_checker import is_valid_set

    for ts in enumerate_valid_sets(full_tile_pool):
        assert is_valid_set(ts), f"Invalid template: {ts!r}"


# ---------------------------------------------------------------------------
# Double-joker (Type-3) variant generation
# ---------------------------------------------------------------------------


def test_two_jokers_generates_double_joker_variants() -> None:
    """With 2 jokers in the pool, Type-3 double-joker templates are generated."""
    # Pool: Red 4, Red 5, Red 6 + 2 jokers → base run [R4,R5,R6] exists.
    # Type-3 variants should include [Joker,R5,Joker], [Joker,R4,Joker]? No —
    # [Joker,R4,Joker] would need positions 0 and 2 from [R4,R5,R6] replaced:
    # resulting in [Joker,R5,Joker]. Let's verify at least one double-joker template.
    state = make_state(
        Tile(Color.RED, 4, 0),
        Tile(Color.RED, 5, 0),
        Tile(Color.RED, 6, 0),
        Tile.joker(copy_id=0),
        Tile.joker(copy_id=1),
    )
    sets = enumerate_valid_sets(state)
    double_joker_templates = [
        ts for ts in sets
        if sum(1 for t in ts.tiles if t.is_joker) == 2
    ]
    assert len(double_joker_templates) > 0, "Expected at least one double-joker template"
    # All double-joker templates must pass the rule checker.
    from solver.validator.rule_checker import is_valid_set
    for ts in double_joker_templates:
        assert is_valid_set(ts), f"Invalid double-joker template: {ts!r}"


def test_one_joker_no_double_joker_variants() -> None:
    """With only 1 joker in the pool, no double-joker templates are generated."""
    state = make_state(
        Tile(Color.RED, 4, 0),
        Tile(Color.RED, 5, 0),
        Tile(Color.RED, 6, 0),
        Tile.joker(copy_id=0),
    )
    sets = enumerate_valid_sets(state)
    double_joker_templates = [
        ts for ts in sets
        if sum(1 for t in ts.tiles if t.is_joker) == 2
    ]
    assert double_joker_templates == [], "Expected no double-joker templates with only 1 joker"
