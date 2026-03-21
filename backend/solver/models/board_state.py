from __future__ import annotations

from dataclasses import dataclass, field

from .tile import Tile
from .tileset import TileSet


@dataclass
class MoveInstruction:
    """A single human-readable step in the solution.

    Examples:
      action="extend", description="Add Red 7 to the end of Set 1"
      action="create",  description="Create new group: Blue 4, Red 4, Black 4"
      action="split",   description="Split Set 2 at position 3"
    """

    action: str  # "extend" | "create" | "split" | "rearrange"
    description: str  # Human-readable text shown to the user
    set_index: int | None = None  # Which existing set is affected (if any)
    tile: Tile | None = None  # Which tile is moved (if applicable)


@dataclass
class BoardState:
    """Complete game state snapshot: the board and the player's rack.

    board_sets: all valid sets currently on the table
    rack:       tiles the player holds and wants to place
    """

    board_sets: list[TileSet]
    rack: list[Tile]

    @property
    def board_tiles(self) -> list[Tile]:
        """Flat list of every tile on the board (across all sets)."""
        return [tile for ts in self.board_sets for tile in ts.tiles]

    @property
    def all_tiles(self) -> list[Tile]:
        """All tiles in play: board tiles + rack tiles."""
        return self.board_tiles + self.rack


@dataclass
class Solution:
    """The solver's output for a given BoardState.

    new_sets:       the proposed board arrangement after placing tiles
    placed_tiles:   tiles moved from the rack to the board
    remaining_rack: tiles that could not be placed (stay on rack)
    moves:          ordered list of human-readable move instructions
    is_optimal:     True if the solver proved this is the best possible move
    solve_time_ms:  wall-clock time taken by the ILP solver
    """

    new_sets: list[TileSet]
    placed_tiles: list[Tile]
    remaining_rack: list[Tile]
    moves: list[MoveInstruction] = field(default_factory=list)
    is_optimal: bool = False
    solve_time_ms: float = 0.0

    @property
    def tiles_placed(self) -> int:
        return len(self.placed_tiles)

    @property
    def tiles_remaining(self) -> int:
        return len(self.remaining_rack)
