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
  Timeout: 2 s hard cap enforced by the caller (FastAPI endpoint).
"""

from __future__ import annotations

from ..config.rules import RulesConfig
from ..models.board_state import BoardState, Solution


def solve(state: BoardState, rules: RulesConfig | None = None) -> Solution:
    """Solve a Rummikub board state optimally.

    Returns the Solution that places the maximum number of rack tiles,
    with minimum board disruption as a tiebreaker. Always verifies the
    solution against the rule checker before returning.

    Args:
        state: The current board + rack state.
        rules: Rule variant configuration. Uses defaults if None.

    Returns:
        A Solution — is_optimal=True if the solver proved optimality.

    Raises:
        ValueError: If the state is invalid (e.g. impossible tile counts).
    """
    raise NotImplementedError
