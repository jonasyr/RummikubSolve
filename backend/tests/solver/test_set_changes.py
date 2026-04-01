"""Unit tests for the build_set_changes origin-tracking helper (Phase UI-1).

Tests the pure-solver module solver.generator.set_changes, which has no
FastAPI / HTTP dependencies and can be imported directly.
"""

from __future__ import annotations

from collections import Counter

from solver.generator.set_changes import build_old_tile_origin_map, build_set_changes
from solver.models.tile import Color, Tile
from solver.models.tileset import SetType, TileSet

# ---------------------------------------------------------------------------
# Shorthand helpers (mirrors test_move_generator.py style)
# ---------------------------------------------------------------------------

R, B, BL, Y = Color.RED, Color.BLUE, Color.BLACK, Color.YELLOW


def t(color: Color, number: int, copy_id: int = 0) -> Tile:
    return Tile(color, number, copy_id)


def joker(copy_id: int = 0) -> Tile:
    return Tile.joker(copy_id=copy_id)


def run_ts(color: Color, *numbers: int, copy_ids: list[int] | None = None) -> TileSet:
    ids = copy_ids or [0] * len(numbers)
    return TileSet(
        type=SetType.RUN,
        tiles=[Tile(color, n, cid) for n, cid in zip(numbers, ids, strict=True)],
    )


def group_ts(number: int, *colors: Color) -> TileSet:
    return TileSet(
        type=SetType.GROUP,
        tiles=[Tile(c, number, 0) for c in colors],
    )


def make_sigs(board: list[TileSet]) -> list[Counter]:
    return [
        Counter((tile.color, tile.number, tile.is_joker) for tile in ts.tiles)
        for ts in board
    ]


# ---------------------------------------------------------------------------
# build_old_tile_origin_map
# ---------------------------------------------------------------------------


def test_origin_map_single_set() -> None:
    board = [run_ts(R, 3, 4, 5)]
    mapping = build_old_tile_origin_map(board)
    assert mapping[(R, 3, 0, False)] == 0
    assert mapping[(R, 4, 0, False)] == 0
    assert mapping[(R, 5, 0, False)] == 0


def test_origin_map_two_sets() -> None:
    board = [run_ts(R, 3, 4, 5), group_ts(7, B, R, BL)]
    mapping = build_old_tile_origin_map(board)
    assert mapping[(R, 3, 0, False)] == 0
    assert mapping[(B, 7, 0, False)] == 1
    assert mapping[(R, 7, 0, False)] == 1


def test_origin_map_joker() -> None:
    board = [TileSet(type=SetType.RUN, tiles=[joker(0), t(R, 4), t(R, 5)])]
    mapping = build_old_tile_origin_map(board)
    assert mapping[(None, None, 0, True)] == 0
    assert mapping[(R, 4, 0, False)] == 0


def test_origin_map_empty_board() -> None:
    assert build_old_tile_origin_map([]) == {}


def test_origin_map_copy_id_distinguishes_duplicates() -> None:
    """Two copies of the same tile must map to their respective board sets."""
    board = [
        TileSet(type=SetType.RUN, tiles=[Tile(R, 5, 0), t(R, 6), t(R, 7)]),
        TileSet(type=SetType.RUN, tiles=[Tile(R, 5, 1), t(B, 6), t(B, 7)]),
    ]
    mapping = build_old_tile_origin_map(board)
    assert mapping[(R, 5, 0, False)] == 0
    assert mapping[(R, 5, 1, False)] == 1


# ---------------------------------------------------------------------------
# build_set_changes — action "new"
# ---------------------------------------------------------------------------


def test_new_action_rack_only_run() -> None:
    """Three rack tiles form a brand-new run → action='new', all origins 'hand'."""
    placed = [t(R, 7), t(R, 8), t(R, 9)]
    new_sets = [run_ts(R, 7, 8, 9)]
    changes = build_set_changes(
        old_board_sets=[],
        new_sets=new_sets,
        placed_tiles=placed,
        old_set_sigs=[],
    )
    assert len(changes) == 1
    sc = changes[0]
    assert sc.action == "new"
    assert sc.source_set_indices is None
    assert sc.source_description is None
    assert all(tile.origin == "hand" for tile in sc.tiles)


def test_new_action_rack_only_group() -> None:
    placed = [t(B, 5), t(R, 5), t(BL, 5)]
    new_sets = [group_ts(5, B, R, BL)]
    changes = build_set_changes(
        old_board_sets=[],
        new_sets=new_sets,
        placed_tiles=placed,
        old_set_sigs=[],
    )
    assert changes[0].action == "new"
    assert all(tile.origin == "hand" for tile in changes[0].tiles)


def test_new_action_result_set_type_is_preserved() -> None:
    placed = [t(R, 1), t(R, 2), t(R, 3)]
    new_sets = [run_ts(R, 1, 2, 3)]
    changes = build_set_changes([], new_sets, placed, [])
    assert changes[0].set_type == "run"


# ---------------------------------------------------------------------------
# build_set_changes — action "unchanged"
# ---------------------------------------------------------------------------


def test_unchanged_action_for_unmodified_set() -> None:
    board = [run_ts(R, 4, 5, 6)]
    changes = build_set_changes(
        old_board_sets=board,
        new_sets=board,
        placed_tiles=[],
        old_set_sigs=make_sigs(board),
    )
    assert len(changes) == 1
    sc = changes[0]
    assert sc.action == "unchanged"
    assert sc.source_set_indices is None
    assert sc.source_description is None
    assert all(tile.origin != "hand" for tile in sc.tiles)


def test_unchanged_tile_origins_are_old_set_indices() -> None:
    board = [run_ts(R, 4, 5, 6)]
    changes = build_set_changes(board, board, [], make_sigs(board))
    for tile in changes[0].tiles:
        assert tile.origin == 0


def test_unchanged_with_multiple_board_sets() -> None:
    board = [run_ts(R, 4, 5, 6), group_ts(7, B, R, BL)]
    placed = [t(Y, 7)]
    new_run = run_ts(R, 4, 5, 6)
    new_group = TileSet(type=SetType.GROUP, tiles=[t(B, 7), t(R, 7), t(BL, 7), t(Y, 7)])
    changes = build_set_changes(board, [new_run, new_group], placed, make_sigs(board))
    unchanged = [c for c in changes if c.action == "unchanged"]
    assert len(unchanged) == 1
    assert unchanged[0].set_type == "run"


# ---------------------------------------------------------------------------
# build_set_changes — action "extended"
# ---------------------------------------------------------------------------


def test_extended_action_adds_one_rack_tile() -> None:
    board = [run_ts(R, 4, 5, 6)]
    placed = [t(R, 7)]
    new_sets = [run_ts(R, 4, 5, 6, 7)]
    changes = build_set_changes(board, new_sets, placed, make_sigs(board))
    assert len(changes) == 1
    sc = changes[0]
    assert sc.action == "extended"
    assert sc.source_set_indices == (0,)
    origins = [tile.origin for tile in sc.tiles]
    assert origins.count("hand") == 1
    assert origins.count(0) == 3


def test_extended_tile_origins_correct() -> None:
    board = [run_ts(R, 4, 5, 6)]
    placed = [t(R, 7)]
    new_run = TileSet(type=SetType.RUN, tiles=[t(R, 4), t(R, 5), t(R, 6), t(R, 7)])
    changes = build_set_changes(board, [new_run], placed, make_sigs(board))
    sc = changes[0]
    tile_map = {(tile.color, tile.number): tile.origin for tile in sc.tiles}
    assert tile_map[(R, 4)] == 0
    assert tile_map[(R, 7)] == "hand"


def test_extended_correct_source_index_with_multiple_board_sets() -> None:
    board = [run_ts(R, 1, 2, 3), run_ts(B, 4, 5, 6)]
    placed = [t(B, 7)]
    new_sets = [run_ts(R, 1, 2, 3), run_ts(B, 4, 5, 6, 7)]
    changes = build_set_changes(board, new_sets, placed, make_sigs(board))
    extended = [c for c in changes if c.action == "extended"]
    assert len(extended) == 1
    assert extended[0].source_set_indices == (1,)


def test_extended_multiple_rack_tiles_to_one_set() -> None:
    board = [run_ts(B, 5, 6, 7)]
    placed = [t(B, 8), t(B, 9)]
    new_sets = [run_ts(B, 5, 6, 7, 8, 9)]
    changes = build_set_changes(board, new_sets, placed, make_sigs(board))
    sc = changes[0]
    assert sc.action == "extended"
    assert sc.source_set_indices == (0,)
    origins = [tile.origin for tile in sc.tiles]
    assert origins.count("hand") == 2


# ---------------------------------------------------------------------------
# build_set_changes — action "rearranged"
# ---------------------------------------------------------------------------


def test_rearranged_board_only_moves_tiles_between_sets() -> None:
    """Tiles that cross from two old sets into one new set → action='rearranged'."""
    board = [
        TileSet(type=SetType.RUN, tiles=[t(B, 3), t(B, 4), t(B, 5)]),
        TileSet(type=SetType.RUN, tiles=[t(B, 6), t(B, 7), t(B, 8)]),
    ]
    # New set draws tiles from both old sets (no rack tiles added).
    new_mixed = TileSet(
        type=SetType.RUN, tiles=[t(B, 3), t(B, 4), t(B, 5), t(B, 6)]
    )
    changes = build_set_changes(board, [new_mixed], [], make_sigs(board))
    sc = changes[0]
    assert sc.action == "rearranged"
    assert sc.source_set_indices is not None
    assert 0 in sc.source_set_indices
    assert 1 in sc.source_set_indices


def test_rearranged_source_description_populated() -> None:
    board = [
        TileSet(type=SetType.RUN, tiles=[t(R, 3), t(R, 4), t(R, 5)]),
        TileSet(type=SetType.RUN, tiles=[t(R, 6), t(R, 7), t(R, 8)]),
    ]
    new_mixed = TileSet(
        type=SetType.RUN, tiles=[t(R, 3), t(R, 4), t(R, 5), t(R, 6)]
    )
    changes = build_set_changes(board, [new_mixed], [], make_sigs(board))
    sc = changes[0]
    assert sc.action == "rearranged"
    assert sc.source_description is not None
    assert len(sc.source_description) > 0


def test_rearranged_with_rack_tiles_from_multiple_sources() -> None:
    """Hand tile + tiles from two board sets → 'rearranged', not 'extended'."""
    board = [
        TileSet(type=SetType.RUN, tiles=[t(R, 3), t(R, 4), t(R, 5)]),
        TileSet(type=SetType.RUN, tiles=[t(R, 6), t(R, 7), t(R, 8)]),
    ]
    placed = [t(R, 9)]
    new_set = TileSet(
        type=SetType.RUN, tiles=[t(R, 3), t(R, 4), t(R, 6), t(R, 9)]
    )
    changes = build_set_changes(board, [new_set], placed, make_sigs(board))
    sc = changes[0]
    assert sc.action == "rearranged"
    assert sc.source_set_indices is not None
    assert len(sc.source_set_indices) == 2


def test_rearranged_source_description_includes_set_numbers() -> None:
    board = [
        TileSet(type=SetType.RUN, tiles=[t(R, 3), t(R, 4), t(R, 5)]),
        TileSet(type=SetType.RUN, tiles=[t(B, 6), t(B, 7), t(B, 8)]),
    ]
    new_set = TileSet(type=SetType.RUN, tiles=[t(R, 3), t(B, 6), t(B, 7)])
    changes = build_set_changes(board, [new_set], [], make_sigs(board))
    sc = changes[0]
    if sc.action == "rearranged" and sc.source_description:
        assert "Set 1" in sc.source_description or "Set 2" in sc.source_description


# ---------------------------------------------------------------------------
# build_set_changes — mixed scenarios with multiple action types
# ---------------------------------------------------------------------------


def test_unchanged_and_extended_coexist() -> None:
    board = [run_ts(R, 1, 2, 3), run_ts(B, 4, 5, 6)]
    placed = [t(B, 7)]
    new_sets = [run_ts(R, 1, 2, 3), run_ts(B, 4, 5, 6, 7)]
    changes = build_set_changes(board, new_sets, placed, make_sigs(board))
    actions = {c.action for c in changes}
    assert "unchanged" in actions
    assert "extended" in actions


def test_new_and_unchanged_coexist() -> None:
    board = [run_ts(R, 1, 2, 3)]
    placed = [t(B, 5), t(B, 6), t(B, 7)]
    new_sets = [run_ts(R, 1, 2, 3), run_ts(B, 5, 6, 7)]
    changes = build_set_changes(board, new_sets, placed, make_sigs(board))
    actions = {c.action for c in changes}
    assert "unchanged" in actions
    assert "new" in actions


def test_count_matches_number_of_new_sets() -> None:
    board = [run_ts(R, 1, 2, 3), group_ts(5, B, R, BL)]
    placed = [t(R, 4), t(Y, 5), t(B, 9), t(B, 10), t(B, 11)]
    new_sets = [
        run_ts(R, 1, 2, 3, 4),
        group_ts(5, B, R, BL, Y),
        run_ts(B, 9, 10, 11),
    ]
    changes = build_set_changes(board, new_sets, placed, make_sigs(board))
    assert len(changes) == len(new_sets)


# ---------------------------------------------------------------------------
# build_set_changes — joker tile handling
# ---------------------------------------------------------------------------


def test_joker_from_rack_has_hand_origin() -> None:
    j = joker(0)
    placed = [j]
    new_set = TileSet(type=SetType.RUN, tiles=[t(R, 4), t(R, 5), j])
    board = [run_ts(R, 4, 5, 6)]
    changes = build_set_changes(board, [new_set], placed, make_sigs(board))
    sc = changes[0]
    joker_tile = next(tile for tile in sc.tiles if tile.is_joker)
    assert joker_tile.origin == "hand"


def test_joker_from_board_has_int_origin() -> None:
    j = joker(0)
    board_set = TileSet(type=SetType.RUN, tiles=[j, t(R, 4), t(R, 5)])
    changes = build_set_changes([board_set], [board_set], [], make_sigs([board_set]))
    sc = changes[0]
    joker_tile = next(tile for tile in sc.tiles if tile.is_joker)
    assert joker_tile.origin == 0


# ---------------------------------------------------------------------------
# build_set_changes — copy_id pass-through
# ---------------------------------------------------------------------------


def test_copy_id_preserved_in_tile_output() -> None:
    board = [TileSet(type=SetType.RUN, tiles=[Tile(R, 5, 0), t(R, 6), t(R, 7)])]
    placed = [Tile(R, 5, 1)]  # second physical copy of Red 5
    new_set = TileSet(
        type=SetType.GROUP,
        tiles=[Tile(R, 5, 0), Tile(R, 5, 1), t(B, 5)],
    )
    changes = build_set_changes(board, [new_set], placed, make_sigs(board))
    sc = changes[0]
    copy_ids = {tile.copy_id for tile in sc.tiles}
    assert 0 in copy_ids
    assert 1 in copy_ids


def test_hand_tile_copy_id_correct() -> None:
    """copy_id is correctly preserved for rack-origin tiles."""
    placed = [Tile(R, 5, 1)]  # second copy
    new_set = TileSet(type=SetType.RUN, tiles=[Tile(R, 5, 1), t(R, 6), t(R, 7)])
    board = [run_ts(R, 6, 7, 8)]
    changes = build_set_changes(board, [new_set], placed, make_sigs(board))
    sc = changes[0]
    hand_tiles = [tile for tile in sc.tiles if tile.origin == "hand"]
    assert len(hand_tiles) == 1
    assert hand_tiles[0].copy_id == 1


# ---------------------------------------------------------------------------
# build_set_changes — empty board (all sets must be "new")
# ---------------------------------------------------------------------------


def test_empty_board_all_sets_are_new() -> None:
    placed = [t(R, 1), t(R, 2), t(R, 3), t(B, 4), t(B, 5), t(B, 6)]
    new_sets = [run_ts(R, 1, 2, 3), run_ts(B, 4, 5, 6)]
    changes = build_set_changes([], new_sets, placed, [])
    assert all(c.action == "new" for c in changes)
    assert all(
        all(tile.origin == "hand" for tile in c.tiles)
        for c in changes
    )


def test_result_set_type_run_preserved() -> None:
    placed = [t(R, 7), t(R, 8), t(R, 9)]
    changes = build_set_changes([], [run_ts(R, 7, 8, 9)], placed, [])
    assert changes[0].set_type == "run"


def test_result_set_type_group_preserved() -> None:
    placed = [t(B, 5), t(R, 5), t(BL, 5)]
    changes = build_set_changes([], [group_ts(5, B, R, BL)], placed, [])
    assert changes[0].set_type == "group"


# ---------------------------------------------------------------------------
# build_set_changes — empty new_sets (no solution)
# ---------------------------------------------------------------------------


def test_empty_new_sets_returns_empty_list() -> None:
    board = [run_ts(R, 1, 2, 3)]
    changes = build_set_changes(board, [], [], make_sigs(board))
    assert changes == []
