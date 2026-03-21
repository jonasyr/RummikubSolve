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
  Timeout: 2 s hard cap enforced via HiGHS time_limit option.
"""

from __future__ import annotations

import time

from ..config.rules import RulesConfig
from ..generator.set_enumerator import enumerate_valid_sets
from ..models.board_state import BoardState, Solution
from ..validator.solution_verifier import verify_solution
from .ilp_formulation import build_ilp_model, extract_solution

_SOLVE_TIMEOUT_SECONDS = 2.0


def solve(state: BoardState, rules: RulesConfig | None = None) -> Solution:
    """Solve a Rummikub board state optimally.

    Returns the Solution that places the maximum number of rack tiles.
    Always verifies the solution against the independent rule checker before
    returning. Raises ValueError if the board state is structurally invalid.

    Args:
        state: The current board + rack state.
        rules: Rule variant configuration. Uses defaults if None.

    Returns:
        A Solution — is_optimal=True if the solver proved optimality within
        the 2-second time limit.

    Raises:
        ValueError: If the state is invalid or the solver returns an
                    inconsistent result.
    """
    if rules is None:
        rules = RulesConfig()

    t_start = time.monotonic()

    # 1. Enumerate candidate set templates from all available tiles.
    candidate_sets = enumerate_valid_sets(state)

    # 2. Build the ILP model.
    model = build_ilp_model(state, candidate_sets, rules)

    # 3. Set solver options and run.
    model.highs.setOptionValue("time_limit", _SOLVE_TIMEOUT_SECONDS)
    model.highs.run()

    # 4. Extract the solution (raises ValueError if infeasible).
    new_sets, placed_tiles, remaining_rack, is_optimal = extract_solution(model)

    solve_time_ms = (time.monotonic() - t_start) * 1000.0

    solution = Solution(
        new_sets=new_sets,
        placed_tiles=placed_tiles,
        remaining_rack=remaining_rack,
        moves=[],  # move_generator not yet implemented (Phase 3)
        is_optimal=is_optimal,
        solve_time_ms=solve_time_ms,
    )

    # 5. Post-solve verification (defense-in-depth per Blueprint §10.4).
    if not verify_solution(state, solution, rules):
        raise ValueError(
            "Solver returned a solution that failed post-verification. "
            "This is a bug — please report it."
        )

    return solution
