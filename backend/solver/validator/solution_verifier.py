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

from collections import Counter

from ..config.rules import RulesConfig
from ..models.board_state import BoardState, Solution
from ..models.tile import Color, Tile
from ..validator.rule_checker import is_valid_set


def _tile_key(t: Tile) -> tuple[Color | None, int | None, int, bool]:
    return (t.color, t.number, t.copy_id, t.is_joker)


def verify_solution(
    original_state: BoardState,
    solution: Solution,
    rules: RulesConfig | None = None,
) -> bool:
    """Verify that solution is a valid, consistent outcome of original_state.

    Checks:
      - Every set in solution.new_sets passes is_valid_set().
      - placed_tiles ∪ remaining_rack == original_state.rack (by tile keys).
      - The multiset of tiles in new_sets == board_tiles ∪ placed_tiles.

    Args:
        original_state: The board state that was solved.
        solution:       The solver's proposed solution.
        rules:          Rule variant configuration. Uses defaults if None.

    Returns:
        True if the solution is valid, False otherwise.
    """
    if rules is None:
        rules = RulesConfig()

    # 1. All sets in the proposed solution must be individually valid.
    for ts in solution.new_sets:
        if not is_valid_set(ts, rules):
            return False

    # 2. Rack accounting: placed + remaining must equal the original rack.
    placed_keys: Counter[tuple[Color | None, int | None, int, bool]] = Counter(
        _tile_key(t) for t in solution.placed_tiles
    )
    remaining_keys: Counter[tuple[Color | None, int | None, int, bool]] = Counter(
        _tile_key(t) for t in solution.remaining_rack
    )
    original_rack_keys: Counter[tuple[Color | None, int | None, int, bool]] = Counter(
        _tile_key(t) for t in original_state.rack
    )
    if placed_keys + remaining_keys != original_rack_keys:
        return False

    # 3. The tiles appearing in new_sets must be exactly board_tiles + placed_tiles.
    new_set_keys: Counter[tuple[Color | None, int | None, int, bool]] = Counter(
        _tile_key(t) for ts in solution.new_sets for t in ts.tiles
    )
    board_keys: Counter[tuple[Color | None, int | None, int, bool]] = Counter(
        _tile_key(t) for t in original_state.board_tiles
    )
    return new_set_keys == board_keys + placed_keys
