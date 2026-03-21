from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .tile import Tile


class SetType(StrEnum):
    """The two valid set types in Rummikub."""

    RUN = "run"
    GROUP = "group"


@dataclass
class TileSet:
    """A Rummikub set: an ordered collection of tiles forming a run or group.

    Run:   ≥3 consecutive numbers, same color. Tiles ordered by number.
    Group: ≥3 same number, each a different color (max 4). Tiles ordered
           by color (consistent ordering aids diffing).

    Validation of set rules is NOT performed here — that is the
    responsibility of solver/validator/rule_checker.py.
    """

    type: SetType
    tiles: list[Tile] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.tiles)

    def __repr__(self) -> str:
        tiles_str = ", ".join(str(t) for t in self.tiles)
        return f"TileSet({self.type.value}, [{tiles_str}])"
