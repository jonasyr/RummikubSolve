"""Base classes for the template-based puzzle generation pipeline.

Every puzzle template must subclass :class:`Template` and declare the three
class-level identity fields (``template_id``, ``template_version``, ``tier``).
The :class:`TemplateInstance` frozen dataclass is the sole return type of
:meth:`Template.generate` and carries all information needed by
``generator_core`` to run the gate pipeline.

See ``Puzzle Generation Rebuild Plan.md`` §4.2.1, §4.3.1.
"""
from __future__ import annotations

__all__ = ["Template", "TemplateInstance", "TemplateInvariantError"]

import abc
import random
from dataclasses import dataclass
from typing import Any, ClassVar, Literal

from solver.models.tile import Tile
from solver.models.tileset import TileSet


@dataclass(frozen=True)
class TemplateInstance:
    """Immutable snapshot produced by :meth:`Template.generate`.

    ``frozen=True`` prevents attribute re-assignment after construction.
    The ``board_sets`` and ``rack`` lists may still be mutated in-place,
    but ``generator_core`` treats them as read-only.

    Fields
    ------
    template_id:
        Matches :attr:`Template.template_id` of the generating template.
    template_version:
        Matches :attr:`Template.template_version` of the generating template.
    tier:
        Difficulty tier this instance targets.
    board_sets:
        Board position passed to :class:`~solver.models.board_state.BoardState`.
    rack:
        Rack tiles the player must place.
    declared_chain_depth:
        Minimum ``chain_depth`` this template guarantees.  The ILP gate
        verifies the solved puzzle meets this value; a shortfall indicates
        a template bug (see :class:`TemplateInvariantError`).
    declared_disruption_min:
        Minimum disruption score this template guarantees (diagnostic only).
    construction_notes:
        Free-form per-template diagnostics captured at construction time.
        Keys and value types are template-specific.
    """

    template_id: str
    template_version: str
    tier: Literal["hard", "expert", "nightmare"]
    board_sets: list[TileSet]
    rack: list[Tile]
    declared_chain_depth: int
    declared_disruption_min: int
    construction_notes: dict[str, Any]


class Template(abc.ABC):
    """Abstract base class for all puzzle templates.

    Subclasses must declare three class variables that identify the template
    uniquely within the registry:

    .. code-block:: python

        class MyTemplate(Template):
            template_id = "T1_joker_displacement_v1"
            template_version = "1"
            tier = "expert"

            def generate(self, rng: random.Random) -> TemplateInstance:
                ...

    :attr:`template_id` is the primary registry key and must be globally
    unique.  :attr:`template_version` is bumped whenever the construction
    logic changes in a way that alters the puzzle distribution.

    Use :func:`~solver.generator.templates.register_template` to add a
    concrete subclass to the registry.
    """

    template_id: ClassVar[str]
    template_version: ClassVar[str]
    tier: ClassVar[Literal["hard", "expert", "nightmare"]]

    @abc.abstractmethod
    def generate(self, rng: random.Random) -> TemplateInstance:
        """Construct one puzzle instance from the given RNG state.

        The caller is responsible for seeding ``rng`` before calling this
        method.  Implementations must use *only* ``rng`` as their source of
        randomness (no ``random.random()``, no ``os.urandom()``) to guarantee
        seed-reproducibility.

        Parameters
        ----------
        rng:
            Pre-seeded :class:`random.Random` instance.  Must be the sole
            randomness source used during construction.

        Returns
        -------
        :class:`TemplateInstance`
            A fully-constructed board + rack ready for gate evaluation.
        """


class TemplateInvariantError(Exception):
    """Raised when a puzzle violates an invariant declared by its template.

    This indicates a **template bug**, not a random seed failure.
    ``generator_core`` must not silently retry on this exception — it
    should surface it immediately so the template can be fixed.

    Example triggers
    ----------------
    - ILP solve yields ``chain_depth < declared_chain_depth``.
    - A tile appears in both ``board_sets`` and ``rack`` simultaneously.
    - Any assertion inside :meth:`Template.generate` that cannot be met for
      any seed.
    """
