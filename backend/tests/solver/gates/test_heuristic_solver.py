"""Unit tests for solver/generator/gates/heuristic_solver.py.

All tests use hand-crafted Tile/TileSet objects — no solver calls, no puzzle
generation, no fixtures.  Each test is fast (< 10 ms).
"""
from __future__ import annotations

from solver.generator.gates.heuristic_solver import HeuristicSolver
from solver.models.board_state import BoardState
from solver.models.tile import Color, Tile
from solver.models.tileset import SetType, TileSet

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tile(color: Color, number: int, copy_id: int = 0) -> Tile:
    return Tile(color=color, number=number, copy_id=copy_id, is_joker=False)


def _joker(copy_id: int = 0) -> Tile:
    return Tile.joker(copy_id=copy_id)


def _run(*tiles: Tile) -> TileSet:
    return TileSet(type=SetType.RUN, tiles=list(tiles))


def _group(*tiles: Tile) -> TileSet:
    return TileSet(type=SetType.GROUP, tiles=list(tiles))


def _state(board_sets: list[TileSet], rack: list[Tile]) -> BoardState:
    return BoardState(board_sets=board_sets, rack=rack)


B = Color.BLUE
R = Color.RED
K = Color.BLACK
Y = Color.YELLOW

SOLVER = HeuristicSolver()


# ===========================================================================
# Empty-rack edge cases
# ===========================================================================


class TestSolvesEmptyRack:
    def test_empty_rack_empty_board(self) -> None:
        """Empty rack and board → trivially solved."""
        assert SOLVER.solves(_state(board_sets=[], rack=[])) is True

    def test_empty_rack_with_valid_board(self) -> None:
        """Empty rack with a valid board → solved immediately."""
        board = [_run(_tile(B, 1), _tile(B, 2), _tile(B, 3))]
        assert SOLVER.solves(_state(board, rack=[])) is True


# ===========================================================================
# Rule 1 — Single-home placement
# ===========================================================================


class TestRule1SingleHome:
    def test_single_home_placed_returns_true(self) -> None:
        """Rack tile with exactly one valid home is placed; rack empties → True."""
        board = [_run(_tile(B, 5), _tile(B, 6), _tile(B, 7))]
        rack = [_tile(B, 8)]
        assert SOLVER.solves(_state(board, rack)) is True

    def test_zero_homes_no_rules_fire(self) -> None:
        """Rack tile fits no board set → False."""
        board = [_run(_tile(B, 1), _tile(B, 2), _tile(B, 3))]
        rack = [_tile(R, 9)]  # wrong color, no red sets on board
        assert SOLVER.solves(_state(board, rack)) is False

    def test_two_homes_rule1_skips_returns_false(self) -> None:
        """Rack tile with two valid homes → Rule 1 doesn't fire → False (no other rule fires)."""
        # B8 extends both runs: B5..B8 and B8..B11.
        # No stubs → Rule 2 skips. Both sets are 3-tile → Rule 3 skips. → False.
        board = [
            _run(_tile(B, 5), _tile(B, 6), _tile(B, 7)),   # B8 appends → valid
            _run(_tile(B, 9), _tile(B, 10), _tile(B, 11)),  # B8 prepends → valid
        ]
        rack = [_tile(B, 8)]
        assert SOLVER.solves(_state(board, rack)) is False

    def test_multiple_tiles_first_single_home_placed(self) -> None:
        """With several rack tiles, only the one with a single home is placed first."""
        board = [_run(_tile(B, 5), _tile(B, 6), _tile(B, 7))]
        rack = [_tile(B, 8), _tile(R, 9)]  # B8 → 1 home, R9 → 0 homes
        # Rule 1 places B8. rack=[R9], board=[[B5,B6,B7,B8]]. R9 still has 0 homes → False.
        assert SOLVER.solves(_state(board, rack)) is False


# ===========================================================================
# Rule 2 — Stub completion
# ===========================================================================


class TestRule2StubCompletion:
    def test_stub_completed_returns_true(self) -> None:
        """2-tile stub + matching rack tile → stub completed → True."""
        board = [_run(_tile(B, 5), _tile(B, 6))]
        rack = [_tile(B, 7)]
        assert SOLVER.solves(_state(board, rack)) is True

    def test_stub_group_completed(self) -> None:
        """2-tile group stub completed by rack tile → True."""
        board = [_group(_tile(B, 7), _tile(R, 7))]
        rack = [_tile(K, 7)]
        assert SOLVER.solves(_state(board, rack)) is True

    def test_wrong_tile_does_not_complete_stub(self) -> None:
        """Rack tile that doesn't complete the stub → False."""
        board = [_run(_tile(B, 5), _tile(B, 6))]
        rack = [_tile(R, 7)]  # wrong color
        assert SOLVER.solves(_state(board, rack)) is False

    def test_rule2_fires_when_tile_has_two_homes(self) -> None:
        """Rule 2 fires specifically for 2-tile stubs even when Rule 1 is skipped (2 homes)."""
        # K7 fits TWO homes: group[B7,R7] (2-tile stub → K7 completes it) AND
        # group[B7(cp1),R7(cp1),Y7(cp1)] (3-tile → K7 extends to 4-tile group).
        # Rule 1 skips (2 homes). Rule 2 sees board[0] is a 2-tile stub → fires → True.
        # Final board: [[B7,R7,K7], [B7(cp1),R7(cp1),Y7(cp1)]] — both valid sets.
        board = [
            _group(_tile(B, 7), _tile(R, 7)),  # 2-tile stub
            _group(  # valid 3-tile group
                _tile(B, 7, copy_id=1), _tile(R, 7, copy_id=1), _tile(Y, 7, copy_id=1)
            ),
        ]
        rack = [_tile(K, 7)]
        assert SOLVER.solves(_state(board, rack)) is True


# ===========================================================================
# Rule 3 — Single-set break (depth 1)
# ===========================================================================


class TestRule3SingleBreak:
    def _board_for_break(self) -> list[TileSet]:
        """Board used across Rule 3 tests.

        B9 (rack) fits TWO homes: extends [B5,B6,B7,B8] → 5-tile run, AND fits
        into [R9,K9,Y9] group → 4-color group. Rule 1 skips (2 homes). No 2-tile
        stubs → Rule 2 skips. Rule 3 breaks [B5,B6,B7,B8] by releasing B8, places
        B9 into the group. Remaining rack=[B8], which has exactly 1 home ([B5,B6,B7])
        → Rule 1 places it. No cycle; terminates with True.
        """
        return [
            _run(_tile(B, 5), _tile(B, 6), _tile(B, 7), _tile(B, 8)),
            _group(_tile(R, 9), _tile(K, 9), _tile(Y, 9)),
        ]

    def test_break_enables_placement(self) -> None:
        """Rule 3 breaks a 4-tile set; the released tile allows the rack tile to find 1 home."""
        board = self._board_for_break()
        rack = [_tile(B, 9)]
        assert SOLVER.solves(_state(board, rack)) is True

    def test_break_depth0_returns_false(self) -> None:
        """Same puzzle with max_depth=0 → Rule 3 disabled → False."""
        board = self._board_for_break()
        rack = [_tile(B, 9)]
        assert SOLVER.solves(_state(board, rack), max_depth=0) is False

    def test_break_depth1_returns_true(self) -> None:
        """Same puzzle with max_depth=1 → Rule 3 enabled → True."""
        board = self._board_for_break()
        rack = [_tile(B, 9)]
        assert SOLVER.solves(_state(board, rack), max_depth=1) is True

    def test_3tile_set_not_broken(self) -> None:
        """Sets with exactly 3 tiles are never broken (remainder would be 2-tile, invalid set)."""
        board = [_run(_tile(R, 1), _tile(R, 2), _tile(R, 3))]
        rack = [_tile(B, 9)]  # can never be placed; 3-tile set won't be broken
        assert SOLVER.solves(_state(board, rack)) is False


# ===========================================================================
# Rule 4 — Depth-2 check (max_depth parameter boundary)
# ===========================================================================


class TestRule4DepthBoundary:
    def test_max_depth_default_is_2(self) -> None:
        """Default max_depth=2 solves the Rule 3 scenario."""
        board = [
            _run(_tile(B, 5), _tile(B, 6), _tile(B, 7), _tile(B, 8)),
            _group(_tile(R, 9), _tile(K, 9), _tile(Y, 9)),
        ]
        rack = [_tile(B, 9)]
        assert SOLVER.solves(_state(board, rack)) is True  # max_depth=2 by default

    def test_max_depth_0_disables_all_breaks(self) -> None:
        """max_depth=0 disables both Rule 3 and Rule 4; only Rules 1 & 2 active."""
        board = [
            _run(_tile(B, 5), _tile(B, 6), _tile(B, 7), _tile(B, 8)),
            _group(_tile(R, 9), _tile(K, 9), _tile(Y, 9)),
        ]
        rack = [_tile(B, 9)]
        assert SOLVER.solves(_state(board, rack), max_depth=0) is False


# ===========================================================================
# Impossible positions
# ===========================================================================


class TestReturnsFalseOnImpossible:
    def test_completely_incompatible_rack(self) -> None:
        """Rack tile shares no color or number with any board set → False."""
        board = [_run(_tile(B, 1), _tile(B, 2), _tile(B, 3))]
        rack = [_tile(R, 9)]
        assert SOLVER.solves(_state(board, rack)) is False

    def test_empty_board_non_empty_rack(self) -> None:
        """Non-empty rack with empty board → nothing to extend → False."""
        assert SOLVER.solves(_state(board_sets=[], rack=[_tile(B, 5)])) is False

    def test_two_rack_tiles_no_placement(self) -> None:
        """Two rack tiles with no valid homes → False."""
        board = [_run(_tile(B, 1), _tile(B, 2), _tile(B, 3))]
        rack = [_tile(R, 9), _tile(Y, 5)]
        assert SOLVER.solves(_state(board, rack)) is False


# ===========================================================================
# State immutability
# ===========================================================================


class TestStateNotMutated:
    def test_original_rack_unchanged_on_success(self) -> None:
        """solves() must not mutate the caller's rack (success path)."""
        board = [_run(_tile(B, 5), _tile(B, 6), _tile(B, 7))]
        rack = [_tile(B, 8)]
        state = _state(board, rack)
        original = repr(state.rack)
        SOLVER.solves(state)
        assert repr(state.rack) == original

    def test_original_board_unchanged_on_success(self) -> None:
        """solves() must not mutate the caller's board_sets (success path)."""
        board = [_run(_tile(B, 5), _tile(B, 6), _tile(B, 7))]
        rack = [_tile(B, 8)]
        state = _state(board, rack)
        original = repr(state.board_sets)
        SOLVER.solves(state)
        assert repr(state.board_sets) == original

    def test_original_rack_unchanged_on_failure(self) -> None:
        """solves() must not mutate the caller's rack (failure path)."""
        board = [_run(_tile(B, 1), _tile(B, 2), _tile(B, 3))]
        rack = [_tile(R, 9)]
        state = _state(board, rack)
        original = repr(state.rack)
        SOLVER.solves(state)
        assert repr(state.rack) == original
