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
from ..models.tile import Tile
from ..models.tileset import SetType, TileSet


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
    if rules is None:
        rules = RulesConfig()

    tiles = tileset.tiles
    if len(tiles) < 3:
        return False

    jokers = [t for t in tiles if t.is_joker]
    non_jokers = [t for t in tiles if not t.is_joker]

    if tileset.type == SetType.RUN:
        return _is_valid_run(non_jokers, jokers, rules)
    if tileset.type == SetType.GROUP:
        return _is_valid_group(non_jokers, jokers)
    return False


def _is_valid_run(
    non_jokers: list[Tile],
    jokers: list[Tile],
    rules: RulesConfig,
) -> bool:
    """Validate a run (same color, consecutive numbers, jokers fill gaps)."""
    total = len(non_jokers) + len(jokers)
    if total > 13:
        return False

    # A run of pure jokers is structurally valid (colour/number assigned at play time).
    # In practice the standard set has only 2 jokers, so total ≥ 3 is impossible here,
    # but the rule itself does not forbid it.
    if not non_jokers:
        return True

    # All non-joker tiles must share a single color.
    if len({t.color for t in non_jokers}) > 1:
        return False

    # Narrow int | None → int. Non-joker tiles always have a number (enforced by
    # Tile.__post_init__), but mypy cannot infer this from is_joker alone.
    numbers: list[int] = [t.number for t in non_jokers if t.number is not None]
    if len(numbers) != len(non_jokers):
        return False  # Malformed non-joker tile (guarded by domain invariants).

    numbers.sort()

    # Duplicate numbers are never valid in a run.
    if len(numbers) != len(set(numbers)):
        return False

    n_min, n_max = numbers[0], numbers[-1]

    # Jokers must cover all internal gaps between non-joker numbers.
    internal_gaps = (n_max - n_min + 1) - len(non_jokers)
    if internal_gaps > len(jokers):
        return False  # Not enough jokers to bridge the gaps.

    if rules.allow_wrap_runs:
        # With wrap-around we only enforce total ≤ 13 (already done above).
        return True

    # Without wrap: find a valid start position `a` such that the run
    # [a, a+1, ..., a+total-1] lies entirely within [1, 13] and contains
    # every non-joker number.
    #   a ≤ n_min  (n_min must be inside the run)
    #   a ≥ n_max - total + 1  (n_max must be inside the run)
    #   a ≥ 1  (run starts at or after 1)
    #   a ≤ 14 - total  (run ends at or before 13)
    lo = max(1, n_max - total + 1)
    hi = min(n_min, 14 - total)
    return lo <= hi


def _is_valid_group(non_jokers: list[Tile], jokers: list[Tile]) -> bool:
    """Validate a group (same number, distinct colors, 3–4 tiles total)."""
    total = len(non_jokers) + len(jokers)
    if total > 4:
        return False

    if not non_jokers:
        # All jokers — structurally valid.
        return True

    # All non-joker tiles must share the same number.
    if len({t.number for t in non_jokers}) > 1:
        return False

    # All non-joker tiles must have distinct colors.
    colors = [t.color for t in non_jokers]
    if len(colors) != len(set(colors)):
        return False

    # Jokers fill remaining color slots (max 4 colors total).
    remaining_color_slots = 4 - len(set(colors))
    return not len(jokers) > remaining_color_slots


def is_valid_board(state: BoardState, rules: RulesConfig | None = None) -> bool:
    """Return True if every set on the board is valid and tile counts are legal.

    Also checks that no physical tile (color+number+copy_id) appears in more
    than one set — i.e. no tile is double-counted.

    Args:
        state: The board state to validate.
        rules: Rule variant configuration. Uses defaults if None.

    Returns:
        True if the entire board is valid, False otherwise.
    """
    if rules is None:
        rules = RulesConfig()

    for tileset in state.board_sets:
        if not is_valid_set(tileset, rules):
            return False

    # Each physical tile must appear in at most one set.
    seen: set[tuple[object, object, int, bool]] = set()
    for tile in state.board_tiles:
        key = (tile.color, tile.number, tile.copy_id, tile.is_joker)
        if key in seen:
            return False
        seen.add(key)

    return True
