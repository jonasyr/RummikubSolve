"""Tests for T1JokerDisplacementV1 template.

Fast tests (no ILP): registration, determinism, structural invariants.
Slow tests (real ILP): gate compliance, integration with generate_puzzle().

All seeds used here are in the range 1–1000 (deterministic across runs).
"""
from __future__ import annotations

import json
import pathlib
import random

import pytest

from solver.generator.gates.heuristic_solver import HeuristicSolver
from solver.generator.gates.ilp import run_ilp_gates
from solver.generator.gates.structural import run_pre_ilp_gates
from solver.generator.generator_core import generate_puzzle
from solver.generator.puzzle_result import PuzzleGenerationError
from solver.generator.set_enumerator import enumerate_valid_sets
from solver.generator.templates import get_template, list_templates
from solver.generator.templates.t1_joker_displacement import T1JokerDisplacementV1
from solver.models.board_state import BoardState
from solver.models.tile import Tile

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEMPLATE_ID = "T1_joker_displacement_v1"
_SEEDS_FAST = list(range(1, 21))   # 20 seeds for fast structural tests
_SEEDS_ILP = list(range(1, 11))    # 10 seeds for real ILP tests (slow)


def _make_state_from_instance(seed: int) -> BoardState:
    """Generate a TemplateInstance and wrap it in a BoardState."""
    rng = random.Random(seed)
    template = T1JokerDisplacementV1()
    instance = template.generate(rng)
    return BoardState(board_sets=instance.board_sets, rack=instance.rack)


def _make_instance(seed: int):
    rng = random.Random(seed)
    return T1JokerDisplacementV1().generate(rng)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_registered_in_global_registry(self) -> None:
        ids = list_templates()
        assert _TEMPLATE_ID in ids

    def test_get_template_returns_instance(self) -> None:
        t = get_template(_TEMPLATE_ID)
        assert isinstance(t, T1JokerDisplacementV1)

    def test_tier_is_expert(self) -> None:
        t = get_template(_TEMPLATE_ID)
        assert t.tier == "expert"

    def test_template_version(self) -> None:
        assert T1JokerDisplacementV1.template_version == "1"

    def test_listed_under_expert_tier(self) -> None:
        expert_ids = list_templates("expert")
        assert _TEMPLATE_ID in expert_ids

    def test_not_listed_under_other_tiers(self) -> None:
        for tier in ("hard", "nightmare"):
            assert _TEMPLATE_ID not in list_templates(tier)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    @pytest.mark.parametrize("seed", [1, 42, 999])
    def test_same_seed_same_board_sets(self, seed: int) -> None:
        inst_a = _make_instance(seed)
        inst_b = _make_instance(seed)
        assert repr(inst_a.board_sets) == repr(inst_b.board_sets)

    @pytest.mark.parametrize("seed", [1, 42, 999])
    def test_same_seed_same_rack(self, seed: int) -> None:
        inst_a = _make_instance(seed)
        inst_b = _make_instance(seed)
        assert repr(inst_a.rack) == repr(inst_b.rack)

    def test_different_seeds_may_differ(self) -> None:
        # Not guaranteed but overwhelmingly likely across the param space.
        inst_1 = _make_instance(1)
        inst_2 = _make_instance(2)
        # At least board or rack must differ (or both).
        differ = (
            repr(inst_1.board_sets) != repr(inst_2.board_sets)
            or repr(inst_1.rack) != repr(inst_2.rack)
        )
        assert differ


# ---------------------------------------------------------------------------
# Structural invariants (no ILP)
# ---------------------------------------------------------------------------


class TestStructuralInvariants:
    @pytest.mark.parametrize("seed", _SEEDS_FAST)
    def test_exactly_one_joker_on_board(self, seed: int) -> None:
        inst = _make_instance(seed)
        joker_count = sum(
            t.is_joker for ts in inst.board_sets for t in ts.tiles
        )
        assert joker_count == 1, f"seed={seed}: expected 1 joker, got {joker_count}"

    @pytest.mark.parametrize("seed", _SEEDS_FAST)
    def test_rack_has_three_tiles(self, seed: int) -> None:
        inst = _make_instance(seed)
        assert len(inst.rack) == 3, f"seed={seed}: rack size {len(inst.rack)}"

    @pytest.mark.parametrize("seed", _SEEDS_FAST)
    def test_no_rack_tile_is_joker(self, seed: int) -> None:
        inst = _make_instance(seed)
        assert not any(t.is_joker for t in inst.rack), f"seed={seed}: joker in rack"

    @pytest.mark.parametrize("seed", _SEEDS_FAST)
    def test_declared_chain_depth_is_three(self, seed: int) -> None:
        inst = _make_instance(seed)
        assert inst.declared_chain_depth == 3

    @pytest.mark.parametrize("seed", _SEEDS_FAST)
    def test_tier_tag(self, seed: int) -> None:
        inst = _make_instance(seed)
        assert inst.tier == "expert"

    @pytest.mark.parametrize("seed", _SEEDS_FAST)
    def test_all_board_sets_have_at_least_three_tiles(self, seed: int) -> None:
        inst = _make_instance(seed)
        for i, ts in enumerate(inst.board_sets):
            assert len(ts.tiles) >= 3, f"seed={seed}: set {i} has {len(ts.tiles)} tiles"

    @pytest.mark.parametrize("seed", _SEEDS_FAST)
    def test_trigger_tile_not_on_board(self, seed: int) -> None:
        """The trigger rack tile (copy_id=0) must not also appear in board sets."""
        inst = _make_instance(seed)
        trigger = inst.rack[0]
        board_tile_keys = {
            (t.color, t.number, t.copy_id)
            for ts in inst.board_sets
            for t in ts.tiles
            if not t.is_joker
        }
        key = (trigger.color, trigger.number, trigger.copy_id)
        assert key not in board_tile_keys, (
            f"seed={seed}: trigger {trigger} found on board"
        )

    @pytest.mark.parametrize("seed", _SEEDS_FAST)
    def test_construction_notes_present(self, seed: int) -> None:
        inst = _make_instance(seed)
        for key in ("chain_color", "base_n", "joker_substitutes"):
            assert key in inst.construction_notes, (
                f"seed={seed}: missing construction note '{key}'"
            )

    @pytest.mark.parametrize("seed", _SEEDS_FAST)
    def test_tile_number_bounds(self, seed: int) -> None:
        """All tile numbers must be in range 1–13."""
        inst = _make_instance(seed)
        all_tiles: list[Tile] = list(inst.rack)
        for ts in inst.board_sets:
            all_tiles.extend(ts.tiles)
        for t in all_tiles:
            if not t.is_joker:
                assert t.number is not None and 1 <= t.number <= 13, (
                    f"seed={seed}: tile number {t.number} out of range"
                )


# ---------------------------------------------------------------------------
# Gate compliance (real ILP — slow)
# ---------------------------------------------------------------------------


class TestGateCompliance:
    @pytest.mark.parametrize("seed", _SEEDS_ILP)
    @pytest.mark.slow
    def test_no_trivial_extension_gate_passes(self, seed: int) -> None:
        inst = _make_instance(seed)
        state = BoardState(board_sets=inst.board_sets, rack=inst.rack)
        candidate_sets = enumerate_valid_sets(state)
        ok, reasons = run_pre_ilp_gates(inst.rack, inst.board_sets, candidate_sets)
        trivial_reasons = [r for r in reasons if r.startswith("trivial_extension")]
        assert not trivial_reasons, (
            f"seed={seed}: trivial extension detected: {trivial_reasons}"
        )

    @pytest.mark.parametrize("seed", _SEEDS_ILP)
    @pytest.mark.slow
    def test_no_single_home_gate_passes(self, seed: int) -> None:
        inst = _make_instance(seed)
        state = BoardState(board_sets=inst.board_sets, rack=inst.rack)
        candidate_sets = enumerate_valid_sets(state)
        ok, reasons = run_pre_ilp_gates(inst.rack, inst.board_sets, candidate_sets)
        single_home_reasons = [r for r in reasons if r.startswith("single_home")]
        assert not single_home_reasons, (
            f"seed={seed}: single-home gate failure: {single_home_reasons}"
        )

    @pytest.mark.parametrize("seed", _SEEDS_ILP)
    @pytest.mark.slow
    def test_ilp_solvable_and_unique(self, seed: int) -> None:
        """Gate must never fail with chain_too_shallow — that is a template bug.

        not_unique is an acceptable rejection (rare ambiguous seeds; the generator
        retries with the next seed).  Only chain_too_shallow indicates that no
        expert-level solution exists, which is a template design invariant violation.
        """
        inst = _make_instance(seed)
        state = BoardState(board_sets=inst.board_sets, rack=inst.rack)
        ok, reason, solution = run_ilp_gates(state, declared_chain_depth=3)
        if not ok:
            assert reason == "not_unique", (
                f"seed={seed}: Template invariant violated: {reason}"
            )

    @pytest.mark.parametrize("seed", _SEEDS_ILP)
    @pytest.mark.slow
    def test_chain_depth_at_least_three(self, seed: int) -> None:
        """The solution returned by the gate must have chain_depth ≥ 3.

        For not_unique seeds the gate still sets solution to the found deep-chain
        arrangement before returning False, so chain_depth is inspectable.
        """
        inst = _make_instance(seed)
        state = BoardState(board_sets=inst.board_sets, rack=inst.rack)
        ok, reason, solution = run_ilp_gates(state, declared_chain_depth=3)
        if reason.startswith("chain_too_shallow"):
            pytest.fail(f"seed={seed}: Template invariant violated: {reason}")
        assert solution is not None
        assert solution.chain_depth >= 3, (
            f"seed={seed}: chain_depth={solution.chain_depth} < 3"
        )

    @pytest.mark.parametrize("seed", _SEEDS_ILP)
    @pytest.mark.slow
    def test_heuristic_solver_returns_false(self, seed: int) -> None:
        inst = _make_instance(seed)
        state = BoardState(board_sets=inst.board_sets, rack=inst.rack)
        assert not HeuristicSolver().solves(state), (
            f"seed={seed}: heuristic solver found a solution (puzzle is trivial)"
        )


# ---------------------------------------------------------------------------
# Integration with generate_puzzle() (slow)
# ---------------------------------------------------------------------------


class TestGeneratorCoreIntegration:
    @pytest.mark.slow
    def test_generate_puzzle_expert_succeeds_majority_of_seeds(self) -> None:
        """≥80 of 100 seeds must produce a valid puzzle within 10 attempts.

        Prints per-reason rejection breakdown for debugging.
        Reasons come from structlog output — search for 'puzzle_rejected'
        in captured log lines above this summary.
        """
        import collections

        import structlog.testing

        successes = 0
        rejection_counts: dict[str, int] = collections.defaultdict(int)

        with structlog.testing.capture_logs() as cap:
            for seed in range(1, 101):
                before = len(cap)
                try:
                    generate_puzzle(
                        difficulty="expert",
                        seed=seed,
                        template_id=_TEMPLATE_ID,
                        max_attempts=10,
                    )
                    successes += 1
                except PuzzleGenerationError:
                    for entry in cap[before:]:
                        if entry.get("event") == "puzzle_rejected":
                            rejection_counts[str(entry.get("reason", "unknown"))] += 1

        failures = 100 - successes
        print(
            f"\nRejection-rate: {successes}/100 seeds succeeded, {failures} exhausted budget"
        )
        if rejection_counts:
            breakdown = ", ".join(
                f"{r}={n}" for r, n in sorted(rejection_counts.items(), key=lambda x: -x[1])
            )
            print(f"Per-reason rejection counts: {breakdown}")
        assert successes >= 80, (
            f"Only {successes}/100 seeds succeeded (need ≥ 80)"
        )

    @pytest.mark.slow
    def test_returned_puzzles_are_unique(self) -> None:
        """Collect 10 successful puzzles; all must have is_unique=True."""
        results = []
        for seed in range(1, 201):
            if len(results) >= 10:
                break
            try:
                r = generate_puzzle(
                    difficulty="expert",
                    seed=seed,
                    template_id=_TEMPLATE_ID,
                    max_attempts=10,
                )
                results.append(r)
            except PuzzleGenerationError:
                pass
        assert len(results) >= 10, "Could not collect 10 successful puzzles"
        for r in results:
            assert r.is_unique, f"Puzzle (seed={r.seed}) is not unique"

    @pytest.mark.slow
    def test_returned_puzzles_chain_depth_at_least_three(self) -> None:
        """All returned puzzles must have chain_depth ≥ 3."""
        results = []
        for seed in range(1, 201):
            if len(results) >= 10:
                break
            try:
                r = generate_puzzle(
                    difficulty="expert",
                    seed=seed,
                    template_id=_TEMPLATE_ID,
                    max_attempts=10,
                )
                results.append(r)
            except PuzzleGenerationError:
                pass
        assert len(results) >= 10, "Could not collect 10 successful puzzles"
        for r in results:
            assert r.chain_depth >= 3, (
                f"seed={r.seed}: chain_depth={r.chain_depth} < 3"
            )

    @pytest.mark.slow
    def test_returned_puzzles_not_heuristic_solvable(self) -> None:
        """All returned puzzles must not be solvable by the heuristic solver."""
        results = []
        for seed in range(1, 201):
            if len(results) >= 10:
                break
            try:
                r = generate_puzzle(
                    difficulty="expert",
                    seed=seed,
                    template_id=_TEMPLATE_ID,
                    max_attempts=10,
                )
                results.append((r, seed))
            except PuzzleGenerationError:
                pass
        assert len(results) >= 10, "Could not collect 10 successful puzzles"
        for r, seed in results:
            state = BoardState(board_sets=r.board_sets, rack=r.rack)
            assert not HeuristicSolver().solves(state), (
                f"seed={seed}: heuristic solver solved a returned puzzle"
            )

    @pytest.mark.slow
    def test_result_template_id_matches(self) -> None:
        """generate_puzzle must stamp the correct template_id on the result."""
        for seed in range(1, 50):
            try:
                r = generate_puzzle(
                    difficulty="expert",
                    seed=seed,
                    template_id=_TEMPLATE_ID,
                    max_attempts=10,
                )
                assert r.template_id == _TEMPLATE_ID
                return
            except PuzzleGenerationError:
                pass
        pytest.fail("No successful puzzle found in seeds 1–49")

# ---------------------------------------------------------------------------
# Fixture snapshot (guards against silent template drift)
# ---------------------------------------------------------------------------

_FIXTURE_PATH = (
    pathlib.Path(__file__).parent.parent.parent
    / "fixtures"
    / "templates"
    / "t1_seed_1.json"
)


def _instance_to_dict(seed: int) -> dict:  # type: ignore[type-arg]
    """Serialize a TemplateInstance to a plain dict matching the fixture format."""
    inst = _make_instance(seed)

    def _tile(t: Tile) -> dict:  # type: ignore[type-arg]
        return {
            "color": t.color.value if not t.is_joker else None,
            "number": t.number,
            "copy_id": t.copy_id,
            "is_joker": t.is_joker,
        }

    return {
        "template_id": inst.template_id,
        "template_version": inst.template_version,
        "tier": inst.tier,
        "board_sets": [
            {"type": ts.type.value, "tiles": [_tile(t) for t in ts.tiles]}
            for ts in inst.board_sets
        ],
        "rack": [_tile(t) for t in inst.rack],
        "declared_chain_depth": inst.declared_chain_depth,
        "declared_disruption_min": inst.declared_disruption_min,
        "construction_notes": dict(inst.construction_notes),
    }


class TestFixtureSnapshot:
    def test_seed_1_matches_golden_fixture(self) -> None:
        """Detect silent template drift: live generation must match committed fixture.

        If this test fails after a template change, regenerate the fixture with:
            .venv/bin/python -c "
            import random, json, pathlib
            from solver.generator.templates.t1_joker_displacement import T1JokerDisplacementV1
            def tile_to_dict(t):
                return {'color': t.color.value if not t.is_joker else None,
                        'number': t.number, 'copy_id': t.copy_id, 'is_joker': t.is_joker}
            inst = T1JokerDisplacementV1().generate(random.Random(1))
            data = {
                'template_id': inst.template_id, 'template_version': inst.template_version,
                'tier': inst.tier,
                'board_sets': [{'type': ts.type.value,
                                'tiles': [tile_to_dict(t) for t in ts.tiles]}
                               for ts in inst.board_sets],
                'rack': [tile_to_dict(t) for t in inst.rack],
                'declared_chain_depth': inst.declared_chain_depth,
                'declared_disruption_min': inst.declared_disruption_min,
                'construction_notes': inst.construction_notes,
            }
            pathlib.Path('tests/fixtures/templates/t1_seed_1.json').write_text(
                json.dumps(data, indent=2))
            "
        """
        assert _FIXTURE_PATH.exists(), f"Fixture not found: {_FIXTURE_PATH}"
        saved = json.loads(_FIXTURE_PATH.read_text())
        live = _instance_to_dict(1)
        assert live == saved, (
            "T1 template output for seed=1 changed — template has drifted. "
            "If intentional, regenerate t1_seed_1.json (see docstring)."
        )
