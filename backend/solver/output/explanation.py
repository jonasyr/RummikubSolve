"""Generate human-readable move instruction text from MoveInstructions.

Produces natural-language strings like:
  "Add Red 7 to the end of Set 1"
  "Create new group: Blue 4, Red 4, Black 4"
  "Split Set 2 after position 3, adding Yellow 1 to the new set"

These strings are shown in the move list panel in the UI (Blueprint §6.3).
"""

from __future__ import annotations

from ..models.board_state import MoveInstruction


def describe_move(move: MoveInstruction, set_number: int | None = None) -> str:
    """Produce a human-readable string describing a single move.

    Args:
        move:       The MoveInstruction to describe.
        set_number: 1-based set number for display (e.g. "Set 2").

    Returns:
        A natural-language string.
    """
    raise NotImplementedError
