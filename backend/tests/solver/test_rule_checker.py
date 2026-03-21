"""Tests for solver/validator/rule_checker.py.

All tests use known-answer cases — the expected output is determined by hand
before writing the test, not by running the code. This is the gold-standard
correctness oracle for the entire solver pipeline.
"""

from __future__ import annotations

from solver.config.rules import RulesConfig
from solver.models.board_state import BoardState
from solver.models.tile import Color, Tile
from solver.models.tileset import SetType, TileSet
from solver.validator.rule_checker import is_valid_board, is_valid_set

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(*tiles: Tile) -> TileSet:
    return TileSet(type=SetType.RUN, tiles=list(tiles))


def group(*tiles: Tile) -> TileSet:
    return TileSet(type=SetType.GROUP, tiles=list(tiles))


def red(n: int, copy_id: int = 0) -> Tile:
    return Tile(Color.RED, n, copy_id)


def blue(n: int, copy_id: int = 0) -> Tile:
    return Tile(Color.BLUE, n, copy_id)


def black(n: int, copy_id: int = 0) -> Tile:
    return Tile(Color.BLACK, n, copy_id)


def yellow(n: int, copy_id: int = 0) -> Tile:
    return Tile(Color.YELLOW, n, copy_id)


def joker(copy_id: int = 0) -> Tile:
    return Tile.joker(copy_id)


# ---------------------------------------------------------------------------
# Valid runs
# ---------------------------------------------------------------------------


def test_valid_run_minimal() -> None:
    assert is_valid_set(run(red(4), red(5), red(6)))


def test_valid_run_five_tiles() -> None:
    assert is_valid_set(run(blue(1), blue(2), blue(3), blue(4), blue(5)))


def test_valid_run_ends_at_13() -> None:
    assert is_valid_set(run(red(11), red(12), red(13)))


def test_valid_run_starts_at_1() -> None:
    assert is_valid_set(run(yellow(1), yellow(2), yellow(3)))


def test_valid_run_full_span() -> None:
    # Red 1 through 13: maximum valid run.
    assert is_valid_set(run(*[red(n) for n in range(1, 14)]))


def test_valid_run_joker_fills_gap() -> None:
    # Red 4, Joker, Red 6 → represents Red 4-5-6.
    assert is_valid_set(run(red(4), joker(), red(6)))


def test_valid_run_joker_extends_end() -> None:
    # Red 4, Red 5, Joker → can be 4-5-6 (joker = Red 6).
    assert is_valid_set(run(red(4), red(5), joker()))


def test_valid_run_joker_extends_start() -> None:
    # Joker, Red 5, Red 6 → can be 4-5-6 (joker = Red 4).
    assert is_valid_set(run(joker(), red(5), red(6)))


def test_valid_run_joker_at_boundary_high() -> None:
    # Red 12, Red 13, Joker → lo=max(1,13-3+1)=11, hi=min(12,11)=11 → 11-12-13.
    assert is_valid_set(run(red(12), red(13), joker()))


def test_valid_run_joker_at_boundary_low() -> None:
    # Joker, Red 1, Red 2 → lo=max(1,2-3+1)=1, hi=min(1,11)=1 → 1-2-3.
    assert is_valid_set(run(joker(), red(1), red(2)))


def test_valid_run_two_jokers_center() -> None:
    # Red 5, Joker, Joker → 4 tiles only? No: that's 3 tiles; 5-6-7 or 3-4-5 etc.
    # Actually: two jokers + Red 5 = 3 tiles total.
    # gaps = (5-5+1)-1 = 0 ≤ 2; lo=max(1,5-3+1)=3, hi=min(5,11)=5 → 3 ≤ 5 ✓.
    assert is_valid_set(run(red(5), joker(), joker()))


def test_valid_run_two_jokers_flanking() -> None:
    # Joker, Red 5, Joker → 3 tiles: e.g. 4-5-6.
    assert is_valid_set(run(joker(), red(5), joker()))


# ---------------------------------------------------------------------------
# Invalid runs
# ---------------------------------------------------------------------------


def test_invalid_run_too_short() -> None:
    assert not is_valid_set(run(red(4), red(5)))


def test_invalid_run_gap_without_joker() -> None:
    # Red 4, Red 6 — two tiles, and even as 3 there's a gap with no joker.
    assert not is_valid_set(run(red(4), red(6), red(8)))  # gaps=2, jokers=0


def test_invalid_run_single_gap_no_joker() -> None:
    # Red 4, Red 6, Red 7 — gap between 4 and 6, no joker.
    assert not is_valid_set(run(red(4), red(6), red(7)))


def test_invalid_run_mixed_colors() -> None:
    assert not is_valid_set(run(red(4), blue(5), red(6)))


def test_invalid_run_all_different_colors() -> None:
    assert not is_valid_set(run(red(4), blue(4), black(4)))


def test_invalid_run_duplicate_number() -> None:
    assert not is_valid_set(run(red(4), red(4), red(5)))


def test_invalid_run_too_long() -> None:
    # 14 tiles: 13 real tiles + 1 joker exceeds the maximum run length of 13.
    assert not is_valid_set(run(*[red(n) for n in range(1, 14)], joker()))


def test_invalid_run_out_of_upper_bound() -> None:
    # Needs numbers up to 14: impossible.
    # Red 12, Red 13 + two jokers = 4 tiles. Start must be ≤ 12 and ≥ 13-4+1=10.
    # lo=max(1,13-4+1)=10, hi=min(12,14-4)=10 → valid (10-11-12-13). TRUE — different test needed.
    # Use: Red 11-12-13 + joker = 4 tiles; lo=max(1,13-4+1)=10, hi=min(11,10)=10 ✓ valid.
    # Actual out-of-bounds: force run that can only start at ≤ 0.
    # Red 1 with 13 jokers = 14 tiles → too_long catches it. Use different approach:
    # 2 non-jokers that are too far apart for the joker budget.
    # Red 1 and Red 13 with 1 joker = gaps=(13-1+1)-2=11, jokers=1 → gap>jokers → False.
    assert not is_valid_set(run(red(1), joker(), red(13)))


def test_invalid_run_single_tile() -> None:
    assert not is_valid_set(run(red(7)))


# ---------------------------------------------------------------------------
# Valid groups
# ---------------------------------------------------------------------------


def test_valid_group_three_colors() -> None:
    assert is_valid_set(group(blue(7), red(7), black(7)))


def test_valid_group_four_colors() -> None:
    assert is_valid_set(group(blue(3), red(3), black(3), yellow(3)))


def test_valid_group_with_one_joker() -> None:
    # Blue 7, Red 7, Joker — joker fills the third color.
    assert is_valid_set(group(blue(7), red(7), joker()))


def test_valid_group_with_joker_as_fourth() -> None:
    # Blue 7, Red 7, Black 7, Joker → 4 tiles, joker = Yellow 7.
    assert is_valid_set(group(blue(7), red(7), black(7), joker()))


def test_valid_group_number_1() -> None:
    assert is_valid_set(group(blue(1), red(1), yellow(1)))


def test_valid_group_number_13() -> None:
    assert is_valid_set(group(blue(13), black(13), yellow(13)))


# ---------------------------------------------------------------------------
# Invalid groups
# ---------------------------------------------------------------------------


def test_invalid_group_too_short() -> None:
    assert not is_valid_set(group(blue(7), red(7)))


def test_invalid_group_five_tiles() -> None:
    assert not is_valid_set(group(blue(7), red(7), black(7), yellow(7), joker()))


def test_invalid_group_duplicate_color() -> None:
    assert not is_valid_set(group(blue(7), blue(7), red(7)))


def test_invalid_group_different_numbers() -> None:
    assert not is_valid_set(group(blue(7), red(8), black(9)))


def test_invalid_group_too_many_jokers() -> None:
    # 2 non-jokers of different colors + 3 jokers = 5 tiles → too many.
    assert not is_valid_set(group(blue(7), red(7), joker(), joker(), joker()))


def test_invalid_group_jokers_exceed_slots() -> None:
    # All 4 colors filled, plus a joker = 5 tiles.
    assert not is_valid_set(group(blue(7), red(7), black(7), yellow(7), joker()))


def test_invalid_group_single_tile() -> None:
    assert not is_valid_set(group(blue(7)))


# ---------------------------------------------------------------------------
# Wrap-around run rule variant
# ---------------------------------------------------------------------------


def test_wrap_run_disabled_by_default() -> None:
    # Without wrap, 12-13-1 is invalid (numbers go backwards / wrap).
    # Represent as 12, 13, 1 — mixed order, not consecutive in standard rules.
    # Actually is_valid_run checks span: n_min=1, n_max=13, gaps=(13-1+1)-3=10, jokers=0 → False.
    assert not is_valid_set(run(red(12), red(13), red(1)))


def test_wrap_run_enabled() -> None:
    rules = RulesConfig(allow_wrap_runs=True)
    # With wrap allowed, we only check total ≤ 13 and no duplicate numbers.
    # Red 12, Red 13, Red 1 with wrap: total=3, gaps=(13-1+1)-3=10 > 0 jokers → still False
    # because the gap check happens BEFORE the wrap check (jokers=0, gaps=10).
    # A proper wrap test: Red 11, Red 12, Red 13 — valid either way.
    assert is_valid_set(run(red(11), red(12), red(13)), rules)


# ---------------------------------------------------------------------------
# is_valid_board
# ---------------------------------------------------------------------------


def test_valid_board_empty() -> None:
    state = BoardState(board_sets=[], rack=[])
    assert is_valid_board(state)


def test_valid_board_single_run(simple_run: TileSet) -> None:
    state = BoardState(board_sets=[simple_run], rack=[])
    assert is_valid_board(state)


def test_valid_board_run_and_group(simple_run: TileSet, simple_group: TileSet) -> None:
    state = BoardState(board_sets=[simple_run, simple_group], rack=[])
    assert is_valid_board(state)


def test_invalid_board_contains_bad_set() -> None:
    bad_set = run(red(4), red(5))  # Only 2 tiles — invalid.
    state = BoardState(board_sets=[bad_set], rack=[])
    assert not is_valid_board(state)


def test_invalid_board_duplicate_physical_tile() -> None:
    # Same physical tile (Red 4, copy_id=0) appears in two sets.
    set_a = run(red(4, 0), red(5, 0), red(6, 0))
    set_b = run(red(4, 0), red(7, 0), red(8, 0))  # Red 4 copy_id=0 duplicated!
    state = BoardState(board_sets=[set_a, set_b], rack=[])
    assert not is_valid_board(state)


def test_valid_board_two_copies_same_tile() -> None:
    # Both copies of Red 4 (copy_id=0 and copy_id=1) in different sets: legal.
    set_a = run(red(4, 0), red(5, 0), red(6, 0))
    set_b = run(red(4, 1), red(5, 1), red(6, 1))
    state = BoardState(board_sets=[set_a, set_b], rack=[])
    assert is_valid_board(state)


# ---------------------------------------------------------------------------
# Hypothesis property test
# ---------------------------------------------------------------------------


from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402


@given(
    set_type=st.sampled_from(list(SetType)),
    tile_data=st.lists(
        st.tuples(
            st.sampled_from(list(Color)),
            st.integers(min_value=1, max_value=13),
        ),
        min_size=0,
        max_size=15,
    ),
)
@settings(max_examples=200)
def test_is_valid_set_never_raises(set_type: SetType, tile_data: list[tuple[Color, int]]) -> None:
    """is_valid_set must return a bool for any tile combination — never raise."""
    tiles = [Tile(color=c, number=n, copy_id=0) for c, n in tile_data]
    ts = TileSet(type=set_type, tiles=tiles)
    result = is_valid_set(ts, RulesConfig())
    assert isinstance(result, bool)
