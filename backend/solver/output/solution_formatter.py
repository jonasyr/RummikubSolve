"""Convert a Solution dataclass into the JSON-serialisable API response dict.

Keeps the solver domain types (Tile, TileSet, Solution) strictly separated
from the API response format (TileOutput, BoardSetOutput, SolveResponse).
"""

from __future__ import annotations

from ..models.board_state import BoardState, Solution


def format_solution(original_state: BoardState, solution: Solution) -> dict[str, object]:
    """Serialize a Solution into the /api/solve JSON response shape.

    Args:
        original_state: The board state that was solved (needed to compute
                        which tile indices are newly placed).
        solution:       The verified solver output.

    Returns:
        A dict matching the SolveResponse Pydantic model structure.
    """
    raise NotImplementedError
