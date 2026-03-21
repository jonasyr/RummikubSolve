"""Post-solve solution verification (defense-in-depth).

Verifies that a Solution returned by the ILP solver is:
  1. Consistent with the original BoardState (no tiles added or lost)
  2. Composed entirely of valid sets (via rule_checker)
  3. Optimal in the sense that placed_tiles are actually on the board

Blueprint §10.4:
  A solver that returns an invalid solution is worse than one that
  returns no solution. This module is the last gate before the API
  sends a response to the client.
"""

from __future__ import annotations

from ..config.rules import RulesConfig
from ..models.board_state import BoardState, Solution


def verify_solution(
    original_state: BoardState,
    solution: Solution,
    rules: RulesConfig | None = None,
) -> bool:
    """Verify that solution is a valid, consistent outcome of original_state.

    Checks:
      - Every board tile appears in exactly one set in solution.new_sets.
      - Every placed_tile appears in exactly one set in solution.new_sets.
      - No tile appears more times than it exists.
      - Every set in solution.new_sets passes is_valid_set().
      - placed_tiles ∪ remaining_rack == original_state.rack.

    Args:
        original_state: The board state that was solved.
        solution:       The solver's proposed solution.
        rules:          Rule variant configuration. Uses defaults if None.

    Returns:
        True if the solution is valid, False otherwise.
    """
    raise NotImplementedError
