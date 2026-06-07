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
from .objective import compute_chain_depth

_SOLVE_TIMEOUT_SECONDS = 30.0
_UNIQUENESS_TIMEOUT_SECONDS = 10.0


def solve(
    state: BoardState,
    rules: RulesConfig | None = None,
    secondary_objective: Literal["tile_value", "disruption"] = "tile_value",
    timeout_seconds: float | None = None,
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
    effective_timeout = timeout_seconds if timeout_seconds is not None else _SOLVE_TIMEOUT_SECONDS
    model.highs.setOptionValue("time_limit", effective_timeout)
    # HiGHS time_limit is sometimes not respected in worker threads on Windows.
    # Set a simplex iteration limit as a platform-independent hard stop.
    # 50 000 iterations is generous for Rummikub ILPs (typical: < 5 000),
    # but prevents an infinite loop on degenerate configurations.
    model.highs.setOptionValue("simplex_iteration_limit", 50_000)
    model.highs.run()

    # 4. Extract the solution.
    # For first-turn solves, infeasibility means the rack can't meet the meld
    # threshold — this is a valid "no play" outcome, not an error.
    active_indices: list[int] = []
    solve_status = "success"
    if rules.is_first_turn:
        try:
            (
                new_sets, placed_tiles, remaining_rack, is_optimal, active_indices
            ) = extract_solution(model)
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
            (
                new_sets, placed_tiles, remaining_rack, is_optimal, active_indices
            ) = extract_solution(model)
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
            solve_status = "infeasible_fallback"
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
            solve_status = "timeout_fallback"

    solve_time_ms = (time.monotonic() - t_start) * 1000.0

    # 5. Generate human-readable move instructions.
    moves = generate_moves(state, new_sets, placed_tiles)

    # Compute chain depth using the original board state (not solve_state,
    # which may be rack-only for first-turn solves).
    chain_depth = compute_chain_depth(state.board_sets, new_sets, placed_tiles)

    solution = Solution(
        new_sets=new_sets,
        placed_tiles=placed_tiles,
        remaining_rack=remaining_rack,
        moves=moves,
        is_optimal=is_optimal,
        solve_time_ms=solve_time_ms,
        solve_status=solve_status,
        chain_depth=chain_depth,
        active_set_indices=active_indices,
    )

    if (
        solution.solve_status == "success"
        and not rules.is_first_turn
        and solution.tiles_placed < len(state.rack)
    ):
        solution.solve_status = "partial_placement"

    # 6. Post-solve verification (defense-in-depth per Blueprint §10.4).
    if not verify_solution(state, solution, rules):
        raise ValueError(
            "Solver returned a solution that failed post-verification. "
            "This is a bug — please report it."
        )

    return solution


def find_alternative_solution(
    state: BoardState,
    solution: Solution,
    rules: RulesConfig | None = None,
    timeout_seconds: float | None = None,
) -> Solution | None:
    """Return the best alternative Solution if one exists, else None.

    Runs the uniqueness ILP with the first solution's active sets excluded.
    If an alternative arrangement places the same number of tiles, returns
    that arrangement as a Solution (chain_depth computed; moves=[]).
    Returns None when no alternative exists (puzzle is unique).

    Cost: roughly doubles solve time because we run HiGHS twice.  Designed
    for offline puzzle pre-generation where latency is not critical.

    Args:
        state:    The board + rack state that produced *solution*.
        solution: A Solution returned by solve().  Must have active_set_indices
                  populated (always true when obtained from solve()).
        rules:    Rule variant configuration.  Uses defaults if None.
        timeout_seconds: ILP time limit.  Uses _UNIQUENESS_TIMEOUT_SECONDS if None.

    Returns:
        None      — no alternative exists; puzzle is unique.
        Solution  — an alternative arrangement with the same tile count.
                    Callers can inspect .chain_depth, .tiles_placed, etc.
    """
    if rules is None:
        rules = RulesConfig()

    if solution.tiles_placed == 0 or not solution.active_set_indices:
        return None

    solve_state = BoardState(board_sets=[], rack=state.rack) if rules.is_first_turn else state
    candidate_sets = enumerate_valid_sets(solve_state)

    model2 = build_ilp_model(
        solve_state,
        candidate_sets,
        rules,
        excluded_solutions=[solution.active_set_indices],
    )
    model2.highs.setOptionValue(
        "time_limit",
        timeout_seconds if timeout_seconds is not None else _UNIQUENESS_TIMEOUT_SECONDS,
    )
    model2.highs.run()

    try:
        new_sets2, placed2, remaining2, is_optimal2, active2 = extract_solution(model2)
    except ValueError:
        return None

    if len(placed2) < solution.tiles_placed:
        return None

    if rules.is_first_turn:
        new_sets2 = list(state.board_sets) + new_sets2
    chain_depth2 = compute_chain_depth(state.board_sets, new_sets2, placed2)
    return Solution(
        new_sets=new_sets2,
        placed_tiles=placed2,
        remaining_rack=remaining2,
        is_optimal=is_optimal2,
        solve_time_ms=0.0,
        solve_status="success",
        chain_depth=chain_depth2,
        active_set_indices=active2,
    )


def find_deep_chain_solution(
    state: BoardState,
    n_tiles: int,
    min_chain_depth: int,
    rules: RulesConfig | None = None,
    timeout_seconds: float | None = None,
    initially_excluded: list[list[int]] | None = None,
    max_iterations: int = 20,
) -> Solution | None:
    """Search all optimal solutions for one with chain_depth >= min_chain_depth.

    Iteratively excludes sub-optimal (low-depth) solutions until a deep-chain
    solution is found or all solutions placing n_tiles are exhausted.

    Used by run_ilp_gates when the primary ILP solution's chain_depth is below
    the declared minimum — the ILP solver may prefer a shallower rearrangement
    as its primary even when a deep-chain solution exists.

    Args:
        state:              Board + rack state.
        n_tiles:            Required placement count.  Solutions placing fewer
                            tiles are not considered (search stops immediately).
        min_chain_depth:    Minimum chain_depth to accept.
        rules:              Rule variant configuration.  Defaults used if None.
        timeout_seconds:    Per-ILP-call time limit.
        initially_excluded: Active-set-index lists to exclude from the very first
                            call (e.g. the primary solution already known to be
                            below the required depth).
        max_iterations:     Hard cap on ILP calls to prevent infinite loops on
                            boards with many optimal solutions.

    Returns:
        A Solution with chain_depth >= min_chain_depth, or None if no such
        solution exists within max_iterations calls.
    """
    if rules is None:
        rules = RulesConfig()

    solve_state = BoardState(board_sets=[], rack=state.rack) if rules.is_first_turn else state
    candidate_sets = enumerate_valid_sets(solve_state)
    excluded: list[list[int]] = list(initially_excluded) if initially_excluded else []
    eff_timeout = timeout_seconds if timeout_seconds is not None else _UNIQUENESS_TIMEOUT_SECONDS

    for _ in range(max_iterations):
        model = build_ilp_model(solve_state, candidate_sets, rules, excluded_solutions=excluded)
        model.highs.setOptionValue("time_limit", eff_timeout)
        model.highs.run()

        try:
            new_sets, placed, remaining, is_optimal, active = extract_solution(model)
        except ValueError:
            return None

        if len(placed) < n_tiles:
            return None

        if rules.is_first_turn:
            new_sets = list(state.board_sets) + new_sets
        chain_depth = compute_chain_depth(state.board_sets, new_sets, placed)

        if chain_depth >= min_chain_depth:
            return Solution(
                new_sets=new_sets,
                placed_tiles=placed,
                remaining_rack=remaining,
                is_optimal=is_optimal,
                solve_time_ms=0.0,
                solve_status="success",
                chain_depth=chain_depth,
                active_set_indices=active,
            )

        excluded.append(active)

    return None


def check_uniqueness(
    state: BoardState,
    solution: Solution,
    rules: RulesConfig | None = None,
    timeout_seconds: float | None = None,
) -> bool:
    """Return True if *solution* is the ONLY arrangement that places solution.tiles_placed tiles.

    Thin wrapper around find_alternative_solution().  Use that function directly
    when you need to inspect properties of the alternative (e.g. chain_depth).

    Returns:
        True  — no alternative arrangement exists (puzzle is unique).
        False — an alternative arrangement achieves the same tile count.
    """
    return find_alternative_solution(state, solution, rules, timeout_seconds) is None
