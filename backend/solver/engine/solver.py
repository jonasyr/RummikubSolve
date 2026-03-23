"""High-level solver interface: takes a BoardState, returns a Solution.

This is the single entry point for Phase 2's /api/solve endpoint.
Internally it orchestrates:
  1. set_enumerator  → candidate_sets
  2. ilp_formulation → HiGHS model
  3. HiGHS .run()    → raw solution
  4. solution extraction → Solution dataclass
  5. solution_verifier   → post-solve sanity check

Blueprint §4.2 — Solver Engine:
  Runs in-process within the FastAPI worker (no IPC overhead).
  Stateless — each request is fully independent.
  Timeout: 30 s hard cap enforced via HiGHS time_limit option.
  (Blueprint §4.2 originally specified 2 s; raised to 30 s in v0.12.1 to
  accommodate complex joker boards that require more search time.)
"""

from __future__ import annotations

import time
from typing import Literal

from ..config.rules import RulesConfig
from ..generator.move_generator import generate_moves
from ..generator.set_enumerator import enumerate_valid_sets
from ..models.board_state import BoardState, Solution
from ..validator.solution_verifier import verify_solution
from .ilp_formulation import build_ilp_model, extract_solution

_SOLVE_TIMEOUT_SECONDS = 30.0


def solve(
    state: BoardState,
    rules: RulesConfig | None = None,
    secondary_objective: Literal["tile_value", "disruption"] = "tile_value",
) -> Solution:
    """Solve a Rummikub board state optimally.

    Returns the Solution that places the maximum number of rack tiles.
    Always verifies the solution against the independent rule checker before
    returning. Raises ValueError if the board state is structurally invalid.

    Args:
        state:               The current board + rack state.
        rules:               Rule variant configuration. Uses defaults if None.
        secondary_objective: Tiebreaker when multiple solutions place the same
                             number of tiles. "tile_value" (default) minimises
                             remaining tile face value. "disruption" is reserved
                             for the planned dual-solution feature and raises
                             NotImplementedError until implemented in the ILP.

    Returns:
        A Solution — is_optimal=True if the solver proved optimality within
        the 30-second time limit.

    Raises:
        ValueError: If the state is invalid or the solver returns an
                    inconsistent result.
    """
    if rules is None:
        rules = RulesConfig()

    t_start = time.monotonic()

    # For the first turn the player may only place their own rack tiles; the
    # existing board is preserved unchanged.  We solve a rack-only sub-problem
    # and prepend the original board sets to the output afterwards.
    solve_state = BoardState(board_sets=[], rack=state.rack) if rules.is_first_turn else state

    # 1. Enumerate candidate set templates from all available tiles.
    candidate_sets = enumerate_valid_sets(solve_state)

    # 2. Build the ILP model.
    model = build_ilp_model(solve_state, candidate_sets, rules, secondary_objective)

    # 3. Set solver options and run.
    model.highs.setOptionValue("time_limit", _SOLVE_TIMEOUT_SECONDS)
    model.highs.run()

    # 4. Extract the solution.
    # For first-turn solves, infeasibility means the rack can't meet the meld
    # threshold — this is a valid "no play" outcome, not an error.
    if rules.is_first_turn:
        try:
            new_sets, placed_tiles, remaining_rack, is_optimal = extract_solution(model)
        except ValueError:
            # Can't reach the threshold → player must draw; board is unchanged.
            new_sets = list(state.board_sets)
            placed_tiles = []
            remaining_rack = list(state.rack)
            is_optimal = True
        else:
            # Prepend the original (untouched) board sets.
            new_sets = list(state.board_sets) + new_sets
    else:
        try:
            new_sets, placed_tiles, remaining_rack, is_optimal = extract_solution(model)
        except ValueError:
            # Infeasible — the board enumeration couldn't find a valid rearrangement.
            # This should not happen with a valid board; fall back to no-move so we
            # never return a 422 error when the board itself is valid.
            import structlog as _sl

            _sl.get_logger().warning("solver.infeasible_fallback_non_first_turn")
            new_sets = list(state.board_sets)
            placed_tiles = []
            remaining_rack = list(state.rack)
            is_optimal = False
        # Detect timeout-without-solution: every board tile must appear in new_sets.
        # If any are missing, HiGHS timed out before finding a feasible integer
        # solution. Fall back to no-move (board unchanged, all rack tiles in hand).
        # id() is safe here because Tile objects are frozen dataclasses that
        # are created once per request and never copied within the solve path.
        # If a refactor ever creates new Tile instances with the same values,
        # switch to a key-tuple set: {(t.color, t.number, t.copy_id, t.is_joker)
        # for ts in ... for t in ts.tiles} — as used in solution_verifier.py.
        board_tile_ids = {id(t) for ts in solve_state.board_sets for t in ts.tiles}
        new_set_tile_ids = {id(t) for ts in new_sets for t in ts.tiles}
        if board_tile_ids - new_set_tile_ids:
            import structlog as _sl

            _sl.get_logger().warning(
                "solver.timeout_fallback",
                missing_board_tiles=len(board_tile_ids - new_set_tile_ids),
            )
            new_sets = list(state.board_sets)
            placed_tiles = []
            remaining_rack = list(state.rack)
            is_optimal = False

    solve_time_ms = (time.monotonic() - t_start) * 1000.0

    # 5. Generate human-readable move instructions.
    moves = generate_moves(state, new_sets, placed_tiles)

    solution = Solution(
        new_sets=new_sets,
        placed_tiles=placed_tiles,
        remaining_rack=remaining_rack,
        moves=moves,
        is_optimal=is_optimal,
        solve_time_ms=solve_time_ms,
    )

    # 6. Post-solve verification (defense-in-depth per Blueprint §10.4).
    if not verify_solution(state, solution, rules):
        raise ValueError(
            "Solver returned a solution that failed post-verification. "
            "This is a bug — please report it."
        )

    return solution
