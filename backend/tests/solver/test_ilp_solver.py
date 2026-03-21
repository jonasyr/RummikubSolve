"""End-to-end tests for the ILP solver (solver.engine.solver.solve).

Each test builds a known game state and verifies:
  - The correct number of rack tiles is placed.
  - The solution passes independent post-verification.
  - is_optimal is True (for small states HiGHS always proves optimality).
"""

from __future__ import annotations

from solver.config.rules import RulesConfig
from solver.engine.solver import solve
from solver.models.board_state import BoardState
from solver.models.tile import Color, Tile
from solver.models.tileset import SetType, TileSet
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
