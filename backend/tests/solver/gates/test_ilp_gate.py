"""Unit tests for solver/generator/gates/ilp.py.

Tests are a mix of real-ILP and mock-based:

- Real ILP: the two "happy-path adjacent" cases (passes and not_solvable)
  that need to verify actual solver behaviour.
- Mock: the three edge-case branches (fallback status, not_unique,
  chain_too_shallow) where we want deterministic, fast tests that do not
  depend on ILP solver internals.

All board states use the same minimal helpers copied from test_structural.py.
"""
from __future__ import annotations

from unittest.mock import patch

from solver.generator.gates.ilp import run_ilp_gates
from solver.models.board_state import BoardState, Solution
from solver.models.tile import Color, Tile
from solver.models.tileset import SetType, TileSet

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tile(color: Color, number: int, copy_id: int = 0) -> Tile:
    return Tile(color=color, number=number, copy_id=copy_id, is_joker=False)


def _run(*tiles: Tile) -> TileSet:
    return TileSet(type=SetType.RUN, tiles=list(tiles))


def _group(*tiles: Tile) -> TileSet:
    return TileSet(type=SetType.GROUP, tiles=list(tiles))


def _state(board_sets: list[TileSet], rack: list[Tile]) -> BoardState:
    return BoardState(board_sets=board_sets, rack=rack)


def _fake_solution(**overrides: object) -> Solution:
    """Build a minimal valid Solution for mock usage."""
    defaults: dict[str, object] = dict(
        new_sets=[],
        placed_tiles=[],
        remaining_rack=[],
        is_optimal=True,
        solve_time_ms=0.0,
        solve_status="success",
        chain_depth=0,
        active_set_indices=[],
    )
    defaults.update(overrides)
    return Solution(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Reusable board state: run(B1,B2,B3) + rack=[B4]
# Trivially solvable and unique.
# ---------------------------------------------------------------------------

_B1 = _tile(Color.BLUE, 1)
_B2 = _tile(Color.BLUE, 2)
_B3 = _tile(Color.BLUE, 3)
_B4 = _tile(Color.BLUE, 4)

_SIMPLE_STATE = _state([_run(_B1, _B2, _B3)], [_B4])

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunIlpGates:
    def test_solvable_unique_passes(self) -> None:
        """Real ILP: run(B1-3) + rack=[B4] is solvable, unique, chain_depth≥0."""
        ok, reason, solution = run_ilp_gates(_SIMPLE_STATE, declared_chain_depth=0)

        assert ok is True
        assert reason == ""
        assert solution is not None
        assert solution.tiles_placed == 1

    def test_not_solvable_rack_tile_has_no_home(self) -> None:
        """Real ILP: Y6 has no valid placement on a board with group(B7,R7,K7)."""
        state = _state(
            [_group(_tile(Color.BLUE, 7), _tile(Color.RED, 7), _tile(Color.BLACK, 7))],
            [_tile(Color.YELLOW, 6)],
        )

        ok, reason, solution = run_ilp_gates(state, declared_chain_depth=0)

        assert ok is False
        assert reason == "not_solvable"
        assert solution is not None
        assert solution.tiles_placed == 0

    def test_solve_status_fallback_rejected(self) -> None:
        """Mock: solver returns timeout_fallback status — gate rejects even if all tiles placed."""
        # tiles_placed == len(rack) so the not_solvable check passes,
        # but solve_status indicates an unreliable solve path.
        fake = _fake_solution(
            placed_tiles=[_B4],
            solve_status="timeout_fallback",
        )

        with patch("solver.generator.gates.ilp.solve", return_value=fake):
            ok, reason, solution = run_ilp_gates(_SIMPLE_STATE, declared_chain_depth=0)

        assert ok is False
        assert reason == "solve_status:timeout_fallback"
        assert solution is fake

    def test_not_unique_rejected(self) -> None:
        """Mock: check_uniqueness returns False — gate rejects with 'not_unique'."""
        with patch("solver.generator.gates.ilp.check_uniqueness", return_value=False):
            ok, reason, solution = run_ilp_gates(_SIMPLE_STATE, declared_chain_depth=0)

        assert ok is False
        assert reason == "not_unique"
        assert solution is not None

    def test_chain_depth_too_shallow(self) -> None:
        """Real ILP: declared_chain_depth=999 exceeds any real result — gate rejects."""
        ok, reason, solution = run_ilp_gates(_SIMPLE_STATE, declared_chain_depth=999)

        assert ok is False
        assert reason.startswith("chain_too_shallow:")
        # Reason format: "chain_too_shallow:<actual><declared>"
        assert "<999" in reason
        assert solution is not None
