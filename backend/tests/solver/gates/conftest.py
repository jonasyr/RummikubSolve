"""Shared session-scoped fixtures for Phase 7 calibration puzzle generation.

Session scope ensures each difficulty group is generated exactly once per
``pytest`` invocation, regardless of how many test modules import the fixture.
This eliminates duplicate puzzle generation when both ``test_structural_integration``
and ``test_heuristic_solver`` need the same Phase 7 v2 puzzles.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from solver.generator.puzzle_generator import PuzzleResult, generate_puzzle

_BATCH_PATH = (
    Path(__file__).parents[3]  # backend/
    / "solver/generator/calibration_batches/phase7_batch_v1.json"
)


def _generate_batch(
    difficulties: set[str],
    label: str,
) -> list[tuple[str, int, PuzzleResult]]:
    """Generate all Phase 7 v2 puzzles for the given difficulty set.

    Prints per-puzzle progress to stdout so slow generation is visible in
    ``pytest -s`` / ``--log-cli-level=INFO`` runs.
    """
    entries = json.loads(_BATCH_PATH.read_text())["entries"]
    subset = [e for e in entries if e["difficulty"] in difficulties]
    results: list[tuple[str, int, PuzzleResult]] = []
    for idx, e in enumerate(subset, 1):
        difficulty, seed = e["difficulty"], e["seed"]
        print(f"\n  [{label}] generating {idx}/{len(subset)}: {difficulty} seed={seed} …",
              flush=True)
        result = generate_puzzle(difficulty, seed=seed, generator_version="v2")
        print(f"  [{label}] done      {idx}/{len(subset)}: {difficulty} seed={seed} "
              f"rack={len(result.rack)} sets={len(result.board_sets)}",
              flush=True)
        results.append((difficulty, seed, result))
    return results


@pytest.fixture(scope="session")
def phase7_easy_medium() -> list[tuple[str, int, PuzzleResult]]:
    """10 easy+medium Phase 7 v2 puzzles — generated once for the whole session.

    Shared between ``test_structural_integration`` and ``test_heuristic_solver``
    to avoid regenerating the same 10 puzzles in each module.
    Run with ``pytest -s`` to see per-puzzle progress.
    """
    return _generate_batch({"easy", "medium"}, "easy+medium")


@pytest.fixture(scope="session")
def phase7_hard_expert_nightmare() -> list[tuple[str, int, PuzzleResult]]:
    """15 hard+expert+nightmare Phase 7 v2 puzzles — generated once per session.

    These puzzles take significantly longer to generate than easy/medium
    (expert/nightmare include uniqueness checks).
    Run with ``pytest -s`` to see per-puzzle progress.
    Tests using this fixture should be marked ``@pytest.mark.slow``.
    """
    return _generate_batch({"hard", "expert", "nightmare"}, "hard/expert/nightmare")
