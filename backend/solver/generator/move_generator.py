"""Translation of a raw ILP solution into human-readable MoveInstructions.

Given the old BoardState and the new arrangement of TileSets from the
solver, this module computes the minimal sequence of physical moves a
player must make to transition from the old board to the new board.
"""

from __future__ import annotations

from ..models.board_state import BoardState, MoveInstruction
from ..models.tile import Color, Tile
from ..models.tileset import TileSet

# A canonical key that uniquely identifies a physical tile.
_TileKey = tuple[Color | None, int | None, int]


def _key(tile: Tile) -> _TileKey:
    return (tile.color, tile.number, tile.copy_id)


def _fmt(tiles: list[Tile]) -> str:
    """Human-readable comma-separated tile description."""
    parts: list[str] = []
    for t in tiles:
        if t.is_joker:
            parts.append("Joker")
        else:
            color = t.color.value.capitalize() if t.color else "?"
            parts.append(f"{color} {t.number}")
    return ", ".join(parts)


def generate_moves(
    old_state: BoardState,
    new_sets: list[TileSet],
    placed_tiles: list[Tile],
) -> list[MoveInstruction]:
    """Compute ordered MoveInstructions from old board state to new arrangement.

    Args:
        old_state:     The board state before solving.
        new_sets:      The proposed new board arrangement (full board).
        placed_tiles:  Tiles taken from the rack and placed this turn.

    Returns:
        An ordered list of MoveInstruction objects describing each physical
        step the player must make.  Sets that are completely unchanged from
        the old board produce no instruction.
    """
    # Keys of tiles placed from the rack this turn.
    placed_keys: frozenset[_TileKey] = frozenset(_key(t) for t in placed_tiles)

    # Fingerprint each old board set as a frozenset of tile keys.
    old_fingerprints: list[frozenset[_TileKey]] = [
        frozenset(_key(t) for t in ts.tiles) for ts in old_state.board_sets
    ]

    moves: list[MoveInstruction] = []

    for new_set in new_sets:
        # Separate the tiles in this set into rack-origin vs board-origin.
        from_rack = [t for t in new_set.tiles if _key(t) in placed_keys]
        from_board = [t for t in new_set.tiles if _key(t) not in placed_keys]

        if not from_rack:
            # Set contains only board tiles.  Emit an instruction only if it
            # doesn't exactly match any pre-existing set (i.e. was reshuffled).
            board_fp = frozenset(_key(t) for t in from_board)
            if board_fp not in old_fingerprints:
                moves.append(
                    MoveInstruction(
                        action="rearrange",
                        description=f"Rearrange into {new_set.type.value}: {_fmt(from_board)}",
                    )
                )
            continue

        if not from_board:
            # Entirely new set built from rack tiles.
            moves.append(
                MoveInstruction(
                    action="create",
                    description=f"Create new {new_set.type.value}: {_fmt(from_rack)}",
                )
            )
            continue

        # Mixed set: rack tiles added to (part of) an existing board set.
        # Find the old set whose tiles overlap most with the board tiles here.
        board_fp = frozenset(_key(t) for t in from_board)
        best_idx: int | None = None
        best_overlap = 0
        for i, fp in enumerate(old_fingerprints):
            overlap = len(fp & board_fp)
            if overlap > best_overlap:
                best_overlap, best_idx = overlap, i

        rack_desc = _fmt(from_rack)
        if best_idx is not None and old_fingerprints[best_idx] == board_fp:
            # All board tiles in this new set came from one unchanged old set
            # → player simply extends that set with rack tiles.
            moves.append(
                MoveInstruction(
                    action="extend",
                    description=f"Add {rack_desc} to set {best_idx + 1}",
                    set_index=best_idx,
                )
            )
        else:
            # Board tiles were drawn from multiple old sets → complex rearrangement.
            moves.append(
                MoveInstruction(
                    action="rearrange",
                    description=f"Rearrange with {rack_desc}: {_fmt(new_set.tiles)}",
                    set_index=best_idx,
                )
            )

    return moves
