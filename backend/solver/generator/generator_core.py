"""Template-based puzzle generation entry point.

:func:`generate_puzzle` is the replacement for the legacy
``puzzle_generator.generate_puzzle`` for the ``hard``, ``expert``, and
``nightmare`` difficulty tiers.  It orchestrates:

1. Template selection from :data:`~solver.generator.templates.TEMPLATE_REGISTRY`.
2. Instance construction via :meth:`~solver.generator.templates.base.Template.generate`.
3. Pre-ILP structural gates (fast, pure-function filters).
4. ILP gate (solvability, uniqueness, chain-depth verification).
5. Post-ILP structural gates (joker-movement verification).
6. Heuristic solver gate (human-analog triviality check).

On any gate failure the attempt is logged and a new seed / template is tried.
``TemplateInvariantError`` is re-raised immediately (not retried) because a
``chain_too_shallow`` result indicates a template bug, not a random seed failure.

See ``Puzzle Generation Rebuild Plan.md`` §4.2.2 and §4.5.
"""
from __future__ import annotations

__all__ = ["generate_puzzle"]

import random
from typing import Literal

import structlog

from solver.engine.objective import compute_disruption_score
from solver.generator.gates.heuristic_solver import HeuristicSolver
from solver.generator.gates.ilp import run_ilp_gates
from solver.generator.gates.structural import run_post_ilp_gates, run_pre_ilp_gates
from solver.generator.puzzle_result import PuzzleGenerationError, PuzzleResult
from solver.generator.set_enumerator import enumerate_valid_sets
from solver.generator.templates import get_template, list_templates
from solver.generator.templates.base import TemplateInvariantError
from solver.models.board_state import BoardState

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Per-tier retry budgets.  These are tuned for offline pregeneration, not
# live API calls (hard/expert/nightmare are always served from a pool).
# ---------------------------------------------------------------------------
_DEFAULT_MAX_ATTEMPTS: dict[str, int] = {
    "hard": 50,
    "expert": 100,
    "nightmare": 200,
}


def generate_puzzle(
    difficulty: Literal["hard", "expert", "nightmare"],
    seed: int | None = None,
    template_id: str | None = None,
    max_attempts: int | None = None,
) -> PuzzleResult:
    """Generate one puzzle for the given difficulty tier.

    Parameters
    ----------
    difficulty:
        Target tier — ``"hard"``, ``"expert"``, or ``"nightmare"``.
    seed:
        RNG seed.  If ``None``, a random seed is drawn from :mod:`random` and
        stored in the returned :class:`~solver.generator.puzzle_result.PuzzleResult`
        so the run can be reproduced.
    template_id:
        If given, force selection of a specific registered template.  If the
        ID is not registered, :exc:`KeyError` propagates immediately.
        If ``None``, a template is chosen uniformly at random from the templates
        registered for *difficulty*.
    max_attempts:
        Override the default per-tier retry budget.  Useful in tests.

    Returns
    -------
    :class:`~solver.generator.puzzle_result.PuzzleResult`
        A fully gate-verified puzzle.

    Raises
    ------
    PuzzleGenerationError
        When no valid puzzle is produced within *max_attempts*, or when the
        registry contains no templates for the requested tier.
    TemplateInvariantError
        When the ILP solver returns a ``chain_depth`` below the template's
        declared minimum.  This indicates a **template bug** and is never
        retried.
    """
    effective_seed = seed if seed is not None else random.randrange(2**32)
    rng = random.Random(effective_seed)
    effective_max = (
        max_attempts if max_attempts is not None else _DEFAULT_MAX_ATTEMPTS[difficulty]
    )

    for attempt in range(1, effective_max + 1):
        # ------------------------------------------------------------------
        # 1. Select template
        # ------------------------------------------------------------------
        if template_id is not None:
            template = get_template(template_id)
        else:
            ids = list_templates(tier=difficulty)
            if not ids:
                raise PuzzleGenerationError(
                    f"No templates registered for tier={difficulty!r}."
                )
            template = get_template(rng.choice(ids))

        # ------------------------------------------------------------------
        # 2. Instantiate: let the template construct board + rack
        # ------------------------------------------------------------------
        instance = template.generate(rng)
        state = BoardState(board_sets=instance.board_sets, rack=instance.rack)

        # ------------------------------------------------------------------
        # 3. Pre-ILP structural gates (cheap, pure-function)
        # ------------------------------------------------------------------
        candidate_sets = enumerate_valid_sets(state)
        pre_ok, pre_reasons = run_pre_ilp_gates(
            instance.rack, instance.board_sets, candidate_sets
        )
        if not pre_ok:
            for reason in pre_reasons:
                logger.info(
                    "puzzle_rejected",
                    template_id=template.template_id,
                    reason=reason,
                    seed=effective_seed,
                    attempt=attempt,
                )
            continue

        # ------------------------------------------------------------------
        # 4. ILP gate (solvability, uniqueness, chain-depth)
        # ------------------------------------------------------------------
        ilp_ok, ilp_reason, solution = run_ilp_gates(
            state, instance.declared_chain_depth
        )
        if not ilp_ok:
            # chain_too_shallow is a template-design bug, not a seed failure.
            # Re-raise immediately so the caller can fix the template rather
            # than silently exhausting the retry budget.
            if ilp_reason.startswith("chain_too_shallow:"):
                raise TemplateInvariantError(
                    f"Template {template.template_id!r} declared "
                    f"chain_depth>={instance.declared_chain_depth} "
                    f"but the solver returned: {ilp_reason}"
                )
            logger.info(
                "puzzle_rejected",
                template_id=template.template_id,
                reason=ilp_reason,
                seed=effective_seed,
                attempt=attempt,
            )
            continue

        # solution is guaranteed non-None when ilp_ok is True.
        assert solution is not None  # noqa: S101 — mypy narrowing

        # ------------------------------------------------------------------
        # 5. Post-ILP structural gates (joker movement, etc.)
        # ------------------------------------------------------------------
        post_ok, post_reasons = run_post_ilp_gates(state, solution)
        if not post_ok:
            for reason in post_reasons:
                logger.info(
                    "puzzle_rejected",
                    template_id=template.template_id,
                    reason=reason,
                    seed=effective_seed,
                    attempt=attempt,
                )
            continue

        # ------------------------------------------------------------------
        # 6. Heuristic solver gate (human-analog triviality check)
        # ------------------------------------------------------------------
        if HeuristicSolver().solves(state):
            logger.info(
                "puzzle_rejected",
                template_id=template.template_id,
                reason="heuristic_solved",
                seed=effective_seed,
                attempt=attempt,
            )
            continue

        # ------------------------------------------------------------------
        # 7. All gates passed — build and return the result
        # ------------------------------------------------------------------
        disruption = compute_disruption_score(instance.board_sets, solution.new_sets)
        joker_count = sum(1 for t in instance.rack if t.is_joker)

        logger.info(
            "puzzle_generated",
            template_id=template.template_id,
            difficulty=difficulty,
            seed=effective_seed,
            attempt=attempt,
            chain_depth=solution.chain_depth,
        )

        return PuzzleResult(
            board_sets=instance.board_sets,
            rack=instance.rack,
            difficulty=difficulty,
            seed=effective_seed,
            template_id=template.template_id,
            template_version=template.template_version,
            chain_depth=solution.chain_depth,
            disruption_score=disruption,
            is_unique=True,
            joker_count=joker_count,
        )

    raise PuzzleGenerationError(
        f"Failed to generate a {difficulty!r} puzzle after {effective_max} attempts."
    )
