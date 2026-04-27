"""ILP gate wrapper for the template-based puzzle generation pipeline.

This module is a pure orchestration layer: it calls the existing ``solve()``
and ``check_uniqueness()`` functions from ``solver.engine.solver`` in the
correct order and translates their return values into the standard gate
protocol — ``(ok: bool, reason: str, solution: Solution | None)``.

**No solver logic is duplicated here.**  All rejection reasons produced by
this gate are surfaced to the caller for telemetry logging.

Timeout semantics
-----------------
Both ``solve_timeout`` and ``uniqueness_timeout`` are passed directly to the
underlying solver.  A ``solve_timeout`` of ``None`` disables the per-call
time limit (use only in offline pregeneration).  The defaults (10 s each) are
appropriate for interactive / live-generation paths.

Chain-depth failure semantics
------------------------------
If ``solution.chain_depth < declared_chain_depth`` the gate returns
``(False, "chain_too_shallow:<actual><declared>", solution)``.
This indicates a **template bug**, not a random seed failure: the template
promised a minimum chain depth that the ILP did not achieve.  The generator
core should raise a ``TemplateInvariantError`` on this reason rather than
silently retrying.
"""
from __future__ import annotations

__all__ = ["run_ilp_gates"]

from solver.engine.solver import check_uniqueness, solve
from solver.models.board_state import BoardState, Solution

_FALLBACK_STATUSES = frozenset({"timeout_fallback", "infeasible_fallback"})


def run_ilp_gates(
    state: BoardState,
    declared_chain_depth: int,
    solve_timeout: float = 10.0,
    uniqueness_timeout: float = 10.0,
) -> tuple[bool, str, Solution | None]:
    """Run ILP solvability, uniqueness, and chain-depth checks in order.

    Parameters
    ----------
    state:
        The board + rack to verify.
    declared_chain_depth:
        Minimum ``chain_depth`` the generating template claims to produce.
        A solved puzzle below this threshold is a template invariant violation.
    solve_timeout:
        Seconds allowed for the primary ILP solve.  Passed to ``solve()``.
    uniqueness_timeout:
        Seconds allowed for the uniqueness ILP.  Passed to ``check_uniqueness()``.

    Returns
    -------
    ``(True, "", solution)`` if all checks pass.
    ``(False, reason, solution_or_none)`` on the first failure, where
    ``reason`` is one of:

    - ``"not_solvable"`` — solver could not place all rack tiles.
    - ``"solve_status:<status>"`` — solver used a fallback path (timeout /
      infeasible).
    - ``"not_unique"`` — an alternative arrangement achieves the same
      tile-placement count.
    - ``"chain_too_shallow:<actual><declared>"`` — template invariant
      violated; chain depth below the declared minimum.
    """
    # Step 1: attempt to solve.
    solution = solve(state, timeout_seconds=solve_timeout)

    # Step 2: all rack tiles must be placed.
    if solution.tiles_placed < len(state.rack):
        return False, "not_solvable", solution

    # Step 3: reject fallback solve paths (timeout / infeasible approximations).
    if solution.solve_status in _FALLBACK_STATUSES:
        return False, f"solve_status:{solution.solve_status}", solution

    # Step 4–5: the optimal solution must be unique.
    if not check_uniqueness(state, solution, timeout_seconds=uniqueness_timeout):
        return False, "not_unique", solution

    # Step 6: template chain-depth invariant.
    if solution.chain_depth < declared_chain_depth:
        return (
            False,
            f"chain_too_shallow:{solution.chain_depth}<{declared_chain_depth}",
            solution,
        )

    # All checks passed.
    return True, "", solution
