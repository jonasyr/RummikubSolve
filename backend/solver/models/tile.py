from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Color(StrEnum):
    """The four tile colors in standard Rummikub."""

    BLUE = "blue"
    RED = "red"
    BLACK = "black"
    YELLOW = "yellow"


@dataclass(frozen=True)
class Tile:
    """Represents a single physical Rummikub tile.

    Standard set: numbers 1–13 in four colors, two copies each (104 tiles)
    plus 2 jokers = 106 tiles total.

    copy_id (0 or 1) distinguishes the two physical copies of an otherwise
    identical tile, which is important for the ILP (each physical tile can
    only be assigned to one set).

    For jokers:
      - is_joker=True
      - color and number are None when unassigned; they are set to the
        identity the joker substitutes for once placed in a set context.
    """

    color: Color | None
    number: int | None  # 1–13; None for an unassigned joker
    copy_id: int  # 0 or 1
    is_joker: bool = False

    def __post_init__(self) -> None:
        if not self.is_joker:
            if self.color is None or self.number is None:
                raise ValueError("Non-joker tiles must have color and number.")
            if not (1 <= self.number <= 13):
                raise ValueError(f"Tile number must be between 1 and 13, got {self.number}.")
        if self.copy_id not in (0, 1):
            raise ValueError(f"copy_id must be 0 or 1, got {self.copy_id}.")

    @classmethod
    def joker(cls, copy_id: int) -> Tile:
        """Convenience constructor for an unassigned joker."""
        return cls(color=None, number=None, copy_id=copy_id, is_joker=True)

    def __str__(self) -> str:
        if self.is_joker:
            return f"Joker[{self.copy_id}]"
        assert self.color is not None and self.number is not None
        return f"{self.color.value.capitalize()} {self.number} [{self.copy_id}]"

    def __repr__(self) -> str:
        return f"Tile({self!s})"
