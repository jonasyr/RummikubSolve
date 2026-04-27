"""Simplified PuzzleResult dataclass and PuzzleGenerationError for the template pipeline.

These are the public result types produced by
:func:`~solver.generator.generator_core.generate_puzzle`.  They live in their
own module so they can be imported without pulling in the legacy
``puzzle_generator`` module, which stays untouched until Phase F of the rebuild.

See ``Puzzle Generation Rebuild Plan.md`` §4.3.2.
"""
from __future__ import annotations

__all__ = ["PuzzleGenerationError", "PuzzleResult"]

from dataclasses import dataclass

from solver.models.tile import Tile
from solver.models.tileset import TileSet


@dataclass
class PuzzleResult:
    """Verified puzzle produced by the template-based generation pipeline.

    All fields are set after the full gate pipeline has passed.  Metrics
    (``chain_depth``, ``disruption_score``) are *verified* by the ILP solver,
    not declared by the template.

    Fields
    ------
    board_sets:
        Board position as a list of :class:`~solver.models.tileset.TileSet`.
    rack:
        Tiles the player must place.
    difficulty:
        Tier string — ``"hard"``, ``"expert"``, or ``"nightmare"``.
    seed:
        RNG seed used (stored even when auto-generated so results can be
        reproduced from the returned object).
    template_id:
        ID of the template that produced this puzzle.
    template_version:
        Version of that template.
    chain_depth:
        Solver-verified chain depth (``>= template.declared_chain_depth``).
    disruption_score:
        Solver-verified disruption score.
    is_unique:
        Always ``True`` — uniqueness is a hard gate in this pipeline.
    joker_count:
        Number of joker tiles in ``rack``.
    """

    board_sets: list[TileSet]
    rack: list[Tile]
    difficulty: str  # "hard" | "expert" | "nightmare"
    seed: int | None
    template_id: str
    template_version: str
    chain_depth: int
    disruption_score: int
    is_unique: bool
    joker_count: int


class PuzzleGenerationError(Exception):
    """Raised when no valid puzzle is produced within the attempt budget.

    This is an operational failure (no template produced an accepted instance
    within ``max_attempts``), not a template bug.  Template bugs raise
    :exc:`~solver.generator.templates.base.TemplateInvariantError` instead.
    """
