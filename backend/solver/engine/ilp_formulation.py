"""Construction of the HiGHS ILP model from a BoardState.

Blueprint §2.2 — ILP Formulation:

Decision variables:
  x[t][s] ∈ {0,1}  — tile t is assigned to set s
  h[t]    ∈ {0,1}  — tile t remains in hand (rack tiles only)
  y[s]    ∈ {0,1}  — set s is active (selected in the solution)

Objective: minimise Σ h[t] for t ∈ rack
           (equivalently: maximise tiles placed from rack)

Constraints:
  1. Each tile assigned to exactly one active set or stays in hand.
  2. A set is active only if all its tiles are assigned to it.
  3. Board tiles may not remain in hand (they must all be placed).
  4. Joker assignment: a joker may fill exactly one tile slot per set.

Secondary objective (tiebreaker): minimise board disruption
  (number of board tiles that move to a different set index).
"""

from __future__ import annotations

from ..config.rules import RulesConfig
from ..models.board_state import BoardState
from ..models.tileset import TileSet


def build_ilp_model(
    state: BoardState,
    candidate_sets: list[TileSet],
    rules: RulesConfig,
) -> object:  # Returns a configured highspy.Highs instance
    """Build and configure the HiGHS ILP model.

    Args:
        state:          Current board + rack state.
        candidate_sets: Pre-enumerated valid set templates (from set_enumerator).
        rules:          Rule variant configuration.

    Returns:
        A configured highspy.Highs instance ready to call .run() on.
    """
    raise NotImplementedError
