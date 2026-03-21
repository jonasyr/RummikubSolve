"""Independent rule validation for individual TileSets and full BoardStates.

Blueprint §10.4 — Post-solve verification is mandatory:
  Even with a proven solver, always verify the solution against an
  independent rule checker before returning it to the user. This catches
  formulation bugs, solver edge cases, and gives defense-in-depth.

This module is intentionally independent of the ILP engine so that it
can serve as a trusted cross-check.
"""

from __future__ import annotations

from ..config.rules import RulesConfig
from ..models.board_state import BoardState
from ..models.tileset import TileSet


def is_valid_set(tileset: TileSet, rules: RulesConfig | None = None) -> bool:
    """Return True if tileset is a valid run or group under the given rules.

    A run:   ≥3 tiles, same color, consecutive numbers (no gaps),
             no wrap-around unless rules.allow_wrap_runs=True.
    A group: ≥3 tiles, same number, each tile a different color, max 4.
    Jokers may substitute for any missing tile.

    Args:
        tileset: The set to validate.
        rules:   Rule variant configuration. Uses defaults if None.

    Returns:
        True if the set is valid, False otherwise.
    """
    raise NotImplementedError


def is_valid_board(state: BoardState, rules: RulesConfig | None = None) -> bool:
    """Return True if every set on the board is valid and tile counts are legal.

    Also checks that no tile appears more times than it exists in the
    standard 106-tile set.

    Args:
        state: The board state to validate.
        rules: Rule variant configuration. Uses defaults if None.

    Returns:
        True if the entire board is valid, False otherwise.
    """
    raise NotImplementedError
