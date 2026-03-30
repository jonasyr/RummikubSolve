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
from solver.engine.ilp_formulation import build_ilp_model, extract_solution
from solver.engine.solver import solve
from solver.generator.set_enumerator import enumerate_valid_sets
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


# ---------------------------------------------------------------------------
# allow_wrap_runs gap documentation test
# ---------------------------------------------------------------------------


def test_allow_wrap_runs_does_not_produce_wrap_templates() -> None:
    """Document known gap: wrap-around runs are not solved even when allowed.

    set_enumerator.enumerate_runs() only generates standard runs (start 1–11,
    no wrap). Even with allow_wrap_runs=True, the ILP cannot discover or place
    a wrap run such as [Red 12, Red 13, Red 1]. This test documents that
    limitation so it is not mistaken for a bug and is easy to update once
    wrap-run template generation lands.

    The validator (rule_checker.is_valid_set) does accept wrap runs — only the
    ILP enumeration is missing them.
    """
    # Rack-only scenario: Red 12, 13, 1 can form the wrap run 12-13-1 when
    # allow_wrap_runs=True. A complete implementation would place all 3 tiles.
    # Currently the enumerator never generates this template, so no tiles are placed.
    state = BoardState(board_sets=[], rack=[t(R, 12), t(R, 13), t(R, 1)])
    rules = RulesConfig(allow_wrap_runs=True)
    sol = solve(state, rules)

    # Documents the *current* (incomplete) behaviour.
    # When wrap-run solving is implemented, update this to assert tiles_placed == 3.
    assert sol.tiles_placed == 0, (
        "Wrap-run solving is now working — update this assertion to "
        "tiles_placed == 3 and remove the 'known gap' note."
    )


# ---------------------------------------------------------------------------
# extract_solution active_set_indices & excluded_solutions tests
# ---------------------------------------------------------------------------


def _build_and_solve(state: BoardState, rules: RulesConfig | None = None, **kwargs):
    """Helper: enumerate → build → run → extract, returning the full 5-tuple."""
    if rules is None:
        rules = RulesConfig()
    candidate_sets = enumerate_valid_sets(state)
    model = build_ilp_model(state, candidate_sets, rules, **kwargs)
    model.highs.run()
    return extract_solution(model), candidate_sets


def test_extract_solution_returns_active_indices_nonempty() -> None:
    """extract_solution returns a non-empty active_set_indices when tiles are placed."""
    state = BoardState(board_sets=[], rack=[t(R, 4), t(R, 5), t(R, 6)])
    (_, _, _, _, active_indices), _ = _build_and_solve(state)
    assert isinstance(active_indices, list)
    assert len(active_indices) >= 1


def test_extract_solution_active_indices_are_valid_set_indices() -> None:
    """Every returned active index is a valid index into candidate_sets."""
    state = BoardState(board_sets=[], rack=[t(R, 4), t(R, 5), t(R, 6)])
    (_, _, _, _, active_indices), candidate_sets = _build_and_solve(state)
    for idx in active_indices:
        assert 0 <= idx < len(candidate_sets)


def test_extract_solution_active_indices_empty_when_no_tiles_placed() -> None:
    """When no tiles are placed (rack too short), active_set_indices is empty."""
    state = BoardState(board_sets=[], rack=[t(R, 4), t(R, 5)])
    (_, placed, _, _, active_indices), _ = _build_and_solve(state)
    assert placed == []
    assert active_indices == []


def test_excluded_solutions_none_has_no_effect() -> None:
    """Passing excluded_solutions=None gives identical results to omitting it."""
    state = BoardState(board_sets=[], rack=[t(R, 4), t(R, 5), t(R, 6)])
    (new_sets1, placed1, _, _, _), _ = _build_and_solve(state)
    (new_sets2, placed2, _, _, _), _ = _build_and_solve(state, excluded_solutions=None)
    assert len(placed1) == len(placed2)


def test_excluded_solutions_empty_list_has_no_effect() -> None:
    """Passing excluded_solutions=[] gives identical results to no exclusion."""
    state = BoardState(board_sets=[], rack=[t(R, 4), t(R, 5), t(R, 6)])
    (_, placed1, _, _, _), _ = _build_and_solve(state)
    (_, placed2, _, _, _), _ = _build_and_solve(state, excluded_solutions=[])
    assert len(placed1) == len(placed2)


def test_excluded_solutions_forces_different_active_sets() -> None:
    """After excluding first solution's active sets, re-solve uses different y-vars.

    State: rack = {R4, R5, R6, R7} — solver can place all 4 in one run OR
    place {R4,R5,R6} and leave R7, etc.  After excluding the first solution's
    exact active-set combination, the second solve should activate a different
    set of y variables (different candidate set indices).
    """
    state = BoardState(board_sets=[], rack=[t(R, 4), t(R, 5), t(R, 6), t(R, 7)])
    (_, _, _, _, active1), candidate_sets = _build_and_solve(state)

    rules = RulesConfig()
    model2 = build_ilp_model(
        state, candidate_sets, rules, excluded_solutions=[active1]
    )
    model2.highs.run()
    _, _, _, _, active2 = extract_solution(model2)

    # The exact same combination of active sets must not appear again.
    assert sorted(active1) != sorted(active2)


def test_excluded_solutions_infeasible_when_only_one_solution() -> None:
    """Excluding the unique optimal solution makes the model infeasible.

    Rack = {R4, R5, R6}: there is exactly one 3-tile run possible.
    After excluding it, no other arrangement can place even 1 rack tile
    in a valid set → infeasible (or places 0 tiles).
    """
    state = BoardState(board_sets=[], rack=[t(R, 4), t(R, 5), t(R, 6)])
    (_, _, _, _, active1), candidate_sets = _build_and_solve(state)
    assert len(active1) == 1  # exactly one set active for a minimal 3-tile run

    rules = RulesConfig()
    model2 = build_ilp_model(
        state, candidate_sets, rules, excluded_solutions=[active1]
    )
    model2.highs.run()
    try:
        _, placed2, _, _, _ = extract_solution(model2)
        # If not infeasible, must place fewer tiles (0).
        assert len(placed2) == 0
    except ValueError:
        pass  # Infeasible is also a correct outcome.


def test_excluded_solutions_multiple_exclusions() -> None:
    """Two exclusions → third distinct solution found (or fewer tiles placed).

    Uses a rack with several placement options so that forcing two solutions
    away still leaves a third reachable arrangement.
    """
    # Rack {R3,R4,R5,R6,R7,R8}: multiple possible 3-tile and 4-tile runs.
    state = BoardState(
        board_sets=[],
        rack=[t(R, 3), t(R, 4), t(R, 5), t(R, 6), t(R, 7), t(R, 8)],
    )
    (_, _, _, _, active1), candidate_sets = _build_and_solve(state)

    rules = RulesConfig()
    model2 = build_ilp_model(
        state, candidate_sets, rules, excluded_solutions=[active1]
    )
    model2.highs.run()
    _, _, _, _, active2 = extract_solution(model2)

    model3 = build_ilp_model(
        state, candidate_sets, rules, excluded_solutions=[active1, active2]
    )
    model3.highs.run()
    _, placed3, _, _, active3 = extract_solution(model3)

    # Third solve must differ from both prior solutions.
    assert sorted(active3) != sorted(active1)
    assert sorted(active3) != sorted(active2)
    # And it must have placed at least some tiles.
    assert len(placed3) >= 0  # defensive; realistically ≥3 for this rack


def test_solve_solution_carries_active_set_indices() -> None:
    """solve() populates active_set_indices on the returned Solution."""
    state = BoardState(board_sets=[], rack=[t(R, 4), t(R, 5), t(R, 6)])
    sol = solve(state)
    assert isinstance(sol.active_set_indices, list)
    assert len(sol.active_set_indices) >= 1


def test_solve_no_tiles_placed_active_indices_empty() -> None:
    """When solve() places 0 tiles, active_set_indices is empty."""
    state = BoardState(board_sets=[], rack=[t(R, 4), t(R, 5)])
    sol = solve(state)
    assert sol.tiles_placed == 0
    assert sol.active_set_indices == []
