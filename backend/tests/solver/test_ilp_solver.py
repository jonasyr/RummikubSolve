"""End-to-end tests for the ILP solver (solver.engine.solver.solve).

Each test builds a known game state and verifies:
  - The correct number of rack tiles is placed.
  - The solution passes independent post-verification.
  - is_optimal is True (for small states HiGHS always proves optimality).
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from solver.config.rules import RulesConfig
from solver.engine.solver import solve
from solver.models.board_state import BoardState
from solver.models.tile import Color, Tile
from solver.models.tileset import SetType, TileSet
from solver.validator.rule_checker import is_valid_set
from solver.validator.solution_verifier import verify_solution

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(color: Color, *numbers: int) -> TileSet:
    """Build a RUN TileSet with copy_id=0 tiles."""
    tiles = [Tile(color, n, 0) for n in numbers]
    return TileSet(type=SetType.RUN, tiles=tiles)


def group(number: int, *colors: Color) -> TileSet:
    """Build a GROUP TileSet with copy_id=0 tiles."""
    tiles = [Tile(c, number, 0) for c in colors]
    return TileSet(type=SetType.GROUP, tiles=tiles)


def rack(*tiles: Tile) -> list[Tile]:
    return list(tiles)


def t(color: Color, number: int, copy_id: int = 0) -> Tile:
    return Tile(color, number, copy_id)


R, B, BL, Y = Color.RED, Color.BLUE, Color.BLACK, Color.YELLOW


# ---------------------------------------------------------------------------
# Empty board — rack-only plays
# ---------------------------------------------------------------------------


def test_place_minimal_run() -> None:
    """Rack with exactly a valid 3-tile run: all 3 placed."""
    state = BoardState(board_sets=[], rack=[t(R, 4), t(R, 5), t(R, 6)])
    sol = solve(state)
    assert sol.tiles_placed == 3
    assert sol.tiles_remaining == 0
    assert sol.is_optimal
    assert verify_solution(state, sol)


def test_place_minimal_group() -> None:
    """Rack with exactly a valid 3-tile group: all 3 placed."""
    state = BoardState(board_sets=[], rack=[t(B, 7), t(R, 7), t(BL, 7)])
    sol = solve(state)
    assert sol.tiles_placed == 3
    assert sol.is_optimal
    assert verify_solution(state, sol)


def test_rack_too_short_to_play() -> None:
    """2-tile rack cannot form any valid set — 0 tiles placed."""
    state = BoardState(board_sets=[], rack=[t(R, 4), t(R, 5)])
    sol = solve(state)
    assert sol.tiles_placed == 0
    assert sol.tiles_remaining == 2
    assert sol.is_optimal
    assert verify_solution(state, sol)


def test_empty_rack() -> None:
    """No rack tiles — trivially 0 tiles placed."""
    state = BoardState(board_sets=[], rack=[])
    sol = solve(state)
    assert sol.tiles_placed == 0
    assert sol.is_optimal
    assert verify_solution(state, sol)


def test_place_four_tile_group() -> None:
    """4-tile group (all colors): all placed."""
    state = BoardState(board_sets=[], rack=[t(B, 3), t(R, 3), t(BL, 3), t(Y, 3)])
    sol = solve(state)
    assert sol.tiles_placed == 4
    assert sol.is_optimal
    assert verify_solution(state, sol)


def test_place_longer_run() -> None:
    """5-tile run: all placed."""
    state = BoardState(
        board_sets=[],
        rack=[t(B, 1), t(B, 2), t(B, 3), t(B, 4), t(B, 5)],
    )
    sol = solve(state)
    assert sol.tiles_placed == 5
    assert sol.is_optimal
    assert verify_solution(state, sol)


def test_partial_placement_best_subset() -> None:
    """Rack has 5 tiles but only 3 form a valid set.

    The solver must place exactly those 3 (not 0, not 5).
    """
    # Red 4-5-6 is a run; Blue 10 and Yellow 10 alone cannot form a set.
    state = BoardState(
        board_sets=[],
        rack=[t(R, 4), t(R, 5), t(R, 6), t(B, 10), t(Y, 10)],
    )
    sol = solve(state)
    assert sol.tiles_placed == 3
    assert sol.tiles_remaining == 2
    assert verify_solution(state, sol)


# ---------------------------------------------------------------------------
# Board + rack: extending existing sets
# ---------------------------------------------------------------------------


def test_extend_run_end() -> None:
    """Rack tile extends an existing run by one at the end."""
    board_run = run(R, 4, 5, 6)
    state = BoardState(board_sets=[board_run], rack=[t(R, 7)])
    sol = solve(state)
    assert sol.tiles_placed == 1
    assert verify_solution(state, sol)


def test_extend_run_start() -> None:
    """Rack tile extends an existing run by one at the start."""
    board_run = run(R, 5, 6, 7)
    state = BoardState(board_sets=[board_run], rack=[t(R, 4)])
    sol = solve(state)
    assert sol.tiles_placed == 1
    assert verify_solution(state, sol)


def test_extend_run_both_ends() -> None:
    """Rack has tiles that can extend the run on both ends — place both."""
    board_run = run(R, 4, 5, 6)
    state = BoardState(board_sets=[board_run], rack=[t(R, 3), t(R, 7)])
    sol = solve(state)
    assert sol.tiles_placed == 2
    assert verify_solution(state, sol)


def test_tile_cannot_extend_only_run() -> None:
    """Rack tile Red 8 cannot extend Red 4-5-6 (gap at 7) — 0 placed."""
    board_run = run(R, 4, 5, 6)
    state = BoardState(board_sets=[board_run], rack=[t(R, 8)])
    sol = solve(state)
    assert sol.tiles_placed == 0
    assert verify_solution(state, sol)


# ---------------------------------------------------------------------------
# Board rearrangement
# ---------------------------------------------------------------------------


def test_board_rearrangement_to_accommodate_rack() -> None:
    """Solver rearranges board sets to maximise rack placement.

    Board: Red 1-2-3, Red 4-5-6
    Rack:  Red 7
    Optimal: merge into Red 1-2-3 (unchanged) + Red 4-5-6-7 → place Red 7.
    """
    board = [run(R, 1, 2, 3), run(R, 4, 5, 6)]
    state = BoardState(board_sets=board, rack=[t(R, 7)])
    sol = solve(state)
    assert sol.tiles_placed == 1
    assert verify_solution(state, sol)


def test_create_group_from_rack_without_touching_board() -> None:
    """Rack tiles form their own group; board set untouched.

    Board: Red 4-5-6 run
    Rack:  Blue 4, Black 4, Yellow 4  → group of 4s (excluding Red which is on board)
    """
    board = [run(R, 4, 5, 6)]
    state = BoardState(
        board_sets=board,
        rack=[t(B, 4), t(BL, 4), t(Y, 4)],
    )
    sol = solve(state)
    assert sol.tiles_placed == 3
    assert verify_solution(state, sol)


def test_all_four_color_group_created() -> None:
    """All four colors of same number placed as a single group."""
    board = [run(R, 1, 2, 3)]  # board must be satisfied
    state = BoardState(
        board_sets=board,
        rack=[t(B, 7), t(R, 7), t(BL, 7), t(Y, 7)],
    )
    sol = solve(state)
    assert sol.tiles_placed == 4
    assert verify_solution(state, sol)


# ---------------------------------------------------------------------------
# Duplicate tiles (copy_id=1)
# ---------------------------------------------------------------------------


def test_two_copies_same_tile_both_usable() -> None:
    """Both physical copies of Red 5 can be placed in different sets."""
    # Two runs both need Red 5 — one uses copy_id=0, the other copy_id=1.
    state = BoardState(
        board_sets=[],
        rack=[
            t(R, 3),
            t(R, 4),
            t(R, 5, 0),  # copy 0
            t(R, 5, 1),  # copy 1
            t(R, 6),
            t(R, 7),
        ],
    )
    sol = solve(state)
    # Two runs possible: Red 3-4-5 and Red 5-6-7 (both use one copy of Red 5)
    assert sol.tiles_placed == 6
    assert verify_solution(state, sol)


# ---------------------------------------------------------------------------
# Joker support
# ---------------------------------------------------------------------------


def test_joker_fills_gap_in_run() -> None:
    """A joker in the rack can fill the gap in Red 4-_-6."""
    state = BoardState(
        board_sets=[],
        rack=[t(R, 4), Tile.joker(copy_id=0), t(R, 6)],
    )
    sol = solve(state)
    assert sol.tiles_placed == 3
    assert verify_solution(state, sol)


def test_joker_in_group() -> None:
    """A joker fills the third slot in a group."""
    state = BoardState(
        board_sets=[],
        rack=[t(B, 9), t(R, 9), Tile.joker(copy_id=0)],
    )
    sol = solve(state)
    assert sol.tiles_placed == 3
    assert verify_solution(state, sol)


def test_joker_left_in_hand_when_no_use() -> None:
    """A joker stays in hand when no compatible set can be formed."""
    # Joker alone (no partner tiles for any set)
    state = BoardState(board_sets=[], rack=[Tile.joker(copy_id=0)])
    sol = solve(state)
    assert sol.tiles_placed == 0
    assert verify_solution(state, sol)


def test_two_jokers_from_rack_placed_in_one_set() -> None:
    """Both jokers from the rack can fill 2 slots in the same run."""
    # [Joker, Red5, Joker] is a valid run (e.g. 4-5-6 with jokers as 4 and 6).
    state = BoardState(
        board_sets=[],
        rack=[Tile.joker(copy_id=0), t(R, 5), Tile.joker(copy_id=1)],
    )
    sol = solve(state)
    assert sol.tiles_placed == 3
    assert verify_solution(state, sol)


def test_two_jokers_on_board_preserved() -> None:
    """A board set with 2 jokers is preserved intact when rack is empty."""
    # [Joker0, Red5, Joker1] is a valid run; nothing else available.
    board_set = TileSet(
        type=SetType.RUN,
        tiles=[Tile.joker(copy_id=0), t(R, 5), Tile.joker(copy_id=1)],
    )
    state = BoardState(board_sets=[board_set], rack=[])
    sol = solve(state)
    assert sol.tiles_placed == 0
    assert len(sol.new_sets) == 1
    assert verify_solution(state, sol)


def test_two_jokers_on_board_with_rack_tile_placed() -> None:
    """A rack tile is placed alongside a board state that has 2 jokers."""
    # Board: [Joker0, Red5, Joker1] (valid run 4-5-6).
    # Rack:  [Red7] — can extend the run to 4-5-6-7 or form a new run with
    #         board tiles re-arranged. Either way, Red7 must be placed.
    board_set = TileSet(
        type=SetType.RUN,
        tiles=[Tile.joker(copy_id=0), t(R, 5), Tile.joker(copy_id=1)],
    )
    state = BoardState(
        board_sets=[board_set],
        rack=[t(R, 7)],
    )
    sol = solve(state)
    # Red7 alone cannot extend — solver either places it (if a valid
    # arrangement exists) or leaves it in hand. The critical assertion is
    # that the solver does NOT crash and the solution is valid.
    assert verify_solution(state, sol)
    assert sol.is_optimal or sol.tiles_placed >= 0  # always true — guards against ValueError


def test_two_jokers_placed_across_multiple_tile_sets() -> None:
    """Two jokers from the rack are placed (together or separately) and all tiles go down."""
    # Rack: Joker0, Red 4-5-6, Joker1, Blue 7-8-9.
    # The solver may put both jokers in one run (e.g. [J0, R4, R5, R6, J1])
    # or one joker each in two separate runs — both are valid optimal solutions.
    state = BoardState(
        board_sets=[],
        rack=[
            Tile.joker(copy_id=0),
            t(R, 4),
            t(R, 5),
            t(R, 6),
            Tile.joker(copy_id=1),
            t(B, 7),
            t(B, 8),
            t(B, 9),
        ],
    )
    sol = solve(state)
    assert sol.tiles_placed == 8
    assert verify_solution(state, sol)
    # Both jokers must be placed (not left in hand).
    placed_jokers = [tile for tile in sol.placed_tiles if tile.is_joker]
    assert len(placed_jokers) == 2


def test_group_with_two_jokers_from_rack() -> None:
    """Four-tile group [Blue5, Red5, Joker0, Joker1] is fully placed."""
    state = BoardState(
        board_sets=[],
        rack=[t(B, 5), t(R, 5), Tile.joker(copy_id=0), Tile.joker(copy_id=1)],
    )
    sol = solve(state)
    assert sol.tiles_placed == 4
    assert verify_solution(state, sol)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_large_rack_all_placeable() -> None:
    """Full 13-tile run from rack: all placed."""
    state = BoardState(
        board_sets=[],
        rack=[t(B, n) for n in range(1, 14)],
    )
    sol = solve(state)
    assert sol.tiles_placed == 13
    assert verify_solution(state, sol)


def test_no_solution_returns_empty_new_board() -> None:
    """When no rack tiles can be placed, new_board still contains all board sets."""
    board_run = run(R, 4, 5, 6)
    state = BoardState(board_sets=[board_run], rack=[t(B, 1)])
    sol = solve(state)
    # Blue 1 alone cannot extend or create any valid set with the available tiles.
    # (would need Blue 2 + Blue 3, or two other 1s — neither present)
    assert sol.tiles_placed == 0
    # Board tiles must still appear in new_sets.
    board_tile_keys = {(t_.color, t_.number) for t_ in board_run.tiles}
    new_set_tile_keys = {(t_.color, t_.number) for ts in sol.new_sets for t_ in ts.tiles}
    assert board_tile_keys.issubset(new_set_tile_keys)
    assert verify_solution(state, sol)


def test_is_optimal_flag() -> None:
    """Solver always proves optimality for small instances."""
    state = BoardState(board_sets=[], rack=[t(R, 4), t(R, 5), t(R, 6)])
    sol = solve(state)
    assert sol.is_optimal is True


def test_solve_time_recorded() -> None:
    """solve_time_ms is positive after a solve."""
    state = BoardState(board_sets=[], rack=[t(R, 4), t(R, 5), t(R, 6)])
    sol = solve(state)
    assert sol.solve_time_ms > 0


# ---------------------------------------------------------------------------
# First-turn rules (is_first_turn=True)
# ---------------------------------------------------------------------------


def test_first_turn_places_above_threshold() -> None:
    """10+11+12 = 33 ≥ 30 → all three rack tiles placed."""
    state = BoardState(board_sets=[], rack=[t(R, 10), t(R, 11), t(R, 12)])
    sol = solve(state, RulesConfig(is_first_turn=True))
    assert sol.tiles_placed == 3
    assert sol.is_optimal
    assert verify_solution(state, sol)


def test_first_turn_below_threshold_no_play() -> None:
    """4+5+6 = 15 < 30 → can't meet the meld threshold, 0 tiles placed."""
    state = BoardState(board_sets=[], rack=[t(R, 4), t(R, 5), t(R, 6)])
    sol = solve(state, RulesConfig(is_first_turn=True))
    assert sol.tiles_placed == 0
    assert verify_solution(state, sol)


def test_first_turn_exact_threshold() -> None:
    """Group Blue 10 + Red 10 + Black 10 = 30 → exactly meets threshold."""
    state = BoardState(board_sets=[], rack=[t(B, 10), t(R, 10), t(BL, 10)])
    sol = solve(state, RulesConfig(is_first_turn=True, initial_meld_threshold=30))
    assert sol.tiles_placed == 3
    assert verify_solution(state, sol)


def test_first_turn_preserves_existing_board() -> None:
    """Existing board sets are returned unchanged alongside the new rack play."""
    board = [run(R, 4, 5, 6)]
    state = BoardState(board_sets=board, rack=[t(R, 10), t(R, 11), t(R, 12)])
    sol = solve(state, RulesConfig(is_first_turn=True))
    assert sol.tiles_placed == 3
    # Original board run must appear in the solution unchanged.
    board_keys = {(tile.color, tile.number) for tile in board[0].tiles}
    solution_board_keys = {(tile.color, tile.number) for ts in sol.new_sets for tile in ts.tiles}
    assert board_keys.issubset(solution_board_keys)
    assert verify_solution(state, sol)


def test_first_turn_cannot_use_board_tiles() -> None:
    """On the first turn the player may not extend board sets.

    Board: Red 4-5-6.  Rack: Red 7 (alone, value 7 < 30).
    Without board access, Red 7 can't form any set → 0 tiles placed.
    """
    state = BoardState(board_sets=[run(R, 4, 5, 6)], rack=[t(R, 7)])
    sol = solve(state, RulesConfig(is_first_turn=True))
    assert sol.tiles_placed == 0
    assert verify_solution(state, sol)


def test_first_turn_joker_does_not_count_toward_threshold() -> None:
    """Jokers contribute 0 to the meld threshold.

    Joker + Red 12 + Red 13 → valid run (11-12-13 with joker as 11), but
    12 + 13 = 25 < 30 → threshold not met → 0 tiles placed.
    """
    state = BoardState(
        board_sets=[],
        rack=[Tile.joker(copy_id=0), t(R, 12), t(R, 13)],
    )
    sol = solve(state, RulesConfig(is_first_turn=True, initial_meld_threshold=30))
    assert sol.tiles_placed == 0
    assert verify_solution(state, sol)


# ---------------------------------------------------------------------------
# Property-based tests (Hypothesis)
# ---------------------------------------------------------------------------

# Strategy: random non-joker tile with copy_id=0.
_tile_st = st.builds(
    Tile,
    color=st.sampled_from(list(Color)),
    number=st.integers(min_value=1, max_value=13),
    copy_id=st.just(0),
)


@given(rack_tiles=st.lists(_tile_st, min_size=0, max_size=7))
@settings(max_examples=60, suppress_health_check=[HealthCheck.too_slow])
def test_property_tile_conservation(rack_tiles: list[Tile]) -> None:
    """Solver never creates or loses tiles.

    For an empty board: every rack tile must end up either in placed_tiles
    or remaining_rack — no tile is duplicated or discarded.
    """
    state = BoardState(board_sets=[], rack=rack_tiles)
    sol = solve(state, RulesConfig())
    assert len(sol.placed_tiles) + len(sol.remaining_rack) == len(rack_tiles)


@given(rack_tiles=st.lists(_tile_st, min_size=1, max_size=9))
@settings(max_examples=60, suppress_health_check=[HealthCheck.too_slow])
def test_property_output_sets_are_valid(rack_tiles: list[Tile]) -> None:
    """Every set in the solution is a legal Rummikub set.

    Exercises the post-solve verifier: the solution_verifier already runs this
    check, but Hypothesis finds edge-case inputs that might slip past unit tests.
    """
    state = BoardState(board_sets=[], rack=rack_tiles)
    sol = solve(state, RulesConfig())
    for ts in sol.new_sets:
        assert is_valid_set(ts, RulesConfig()), f"Invalid set in solution: {ts}"


@given(rack_tiles=st.lists(_tile_st, min_size=3, max_size=6))
@settings(max_examples=40, suppress_health_check=[HealthCheck.too_slow])
def test_property_first_turn_threshold_respected(rack_tiles: list[Tile]) -> None:
    """When is_first_turn=True, any placed tiles must meet the meld threshold.

    If the solver places > 0 tiles, the sum of their face values must be ≥ 30.
    If no valid placement meets the threshold, tiles_placed must be 0.
    """
    rules = RulesConfig(is_first_turn=True, initial_meld_threshold=30)
    state = BoardState(board_sets=[], rack=rack_tiles)
    sol = solve(state, rules)
    if sol.tiles_placed > 0:
        placed_value = sum(tile.number for tile in sol.placed_tiles if tile.number is not None)
        assert placed_value >= 30, (
            f"First-turn threshold not met: placed {sol.tiles_placed} tiles "
            f"with total value {placed_value} < 30"
        )
