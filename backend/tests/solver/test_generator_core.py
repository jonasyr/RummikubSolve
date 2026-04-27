"""Unit tests for solver/generator/generator_core.py.

All tests use mock-based gate implementations to stay fast (no real ILP calls).
Templates are injected via an ``isolated_registry`` fixture so test state never
bleeds into global registry state.

Patch paths target the *import site* inside ``generator_core`` — e.g.
``solver.generator.generator_core.run_pre_ilp_gates`` — not the definition site.
"""
from __future__ import annotations

import random
from unittest.mock import MagicMock, patch

import pytest

import solver.generator.templates as registry_module
from solver.generator.generator_core import generate_puzzle
from solver.generator.puzzle_result import PuzzleGenerationError, PuzzleResult
from solver.generator.templates.base import Template, TemplateInstance, TemplateInvariantError
from solver.models.board_state import Solution

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PATCH_PRE = "solver.generator.generator_core.run_pre_ilp_gates"
_PATCH_ILP = "solver.generator.generator_core.run_ilp_gates"
_PATCH_POST = "solver.generator.generator_core.run_post_ilp_gates"
_PATCH_HS = "solver.generator.generator_core.HeuristicSolver"
_PATCH_DISRUPTION = "solver.generator.generator_core.compute_disruption_score"
_PATCH_ENUM = "solver.generator.generator_core.enumerate_valid_sets"


def _make_minimal_instance(
    tid: str = "t_dummy",
    ver: str = "1",
    declared_chain_depth: int = 0,
) -> TemplateInstance:
    return TemplateInstance(
        template_id=tid,
        template_version=ver,
        tier="expert",
        board_sets=[],
        rack=[],
        declared_chain_depth=declared_chain_depth,
        declared_disruption_min=0,
        construction_notes={},
    )


def _register_dummy(
    registry: dict[str, Template],
    tid: str = "t_dummy",
    ver: str = "1",
    declared_chain_depth: int = 0,
) -> None:
    """Inject a minimal dummy expert template directly into the isolated registry."""

    instance = _make_minimal_instance(tid, ver, declared_chain_depth)

    class _D(Template):
        template_id = tid
        template_version = ver
        tier = "expert"  # type: ignore[assignment]  # ClassVar on ABC, OK in concrete subclass

        def generate(self, rng: random.Random) -> TemplateInstance:
            return instance

    registry[tid] = _D()


def _fake_solution(**overrides: object) -> Solution:
    """Build a minimal valid Solution for mock usage."""
    defaults: dict[str, object] = {
        "new_sets": [],
        "placed_tiles": [],
        "remaining_rack": [],
        "chain_depth": 0,
        "solve_status": "success",
        "is_optimal": True,
        "solve_time_ms": 0.0,
        "active_set_indices": [],
    }
    defaults.update(overrides)
    return Solution(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> dict[str, Template]:
    """Provide a clean, empty TEMPLATE_REGISTRY for the duration of the test."""
    empty: dict[str, Template] = {}
    monkeypatch.setattr(registry_module, "TEMPLATE_REGISTRY", empty)
    return empty


# ---------------------------------------------------------------------------
# Helper: patch all five gate / helper sites to happy-path defaults.
# Callers override individual patches as needed.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNoTemplates:
    def test_empty_registry_raises_generation_error(
        self, isolated_registry: dict[str, Template]
    ) -> None:
        """No registered templates for the tier → PuzzleGenerationError immediately."""
        with pytest.raises(PuzzleGenerationError, match="No templates registered"):
            generate_puzzle("expert", seed=1, max_attempts=5)


class TestAttemptExhaustion:
    def test_exhausted_raises_with_tier_and_count_in_message(
        self, isolated_registry: dict[str, Template]
    ) -> None:
        """When all attempts are exhausted the error message names the tier and count."""
        _register_dummy(isolated_registry)

        # Pre-ILP gate always rejects.
        with patch(_PATCH_ENUM, return_value=[]), patch(
            _PATCH_PRE, return_value=(False, ["trivial_extension:B:1:0:0"])
        ), pytest.raises(PuzzleGenerationError) as exc_info:
            generate_puzzle("expert", seed=1, max_attempts=3)

        msg = str(exc_info.value)
        assert "expert" in msg
        assert "3" in msg

    def test_max_attempts_of_one(
        self, isolated_registry: dict[str, Template]
    ) -> None:
        """max_attempts=1 → exactly one attempt before raising."""
        _register_dummy(isolated_registry)

        with patch(_PATCH_ENUM, return_value=[]), patch(
            _PATCH_PRE, return_value=(False, ["structural_fail"])
        ), pytest.raises(PuzzleGenerationError):
            generate_puzzle("expert", seed=1, max_attempts=1)


class TestTemplateInvariantError:
    def test_chain_too_shallow_is_not_retried(
        self, isolated_registry: dict[str, Template]
    ) -> None:
        """ILP reason 'chain_too_shallow:...' re-raises TemplateInvariantError immediately."""
        _register_dummy(isolated_registry)

        with patch(_PATCH_ENUM, return_value=[]), patch(
            _PATCH_PRE, return_value=(True, [])
        ), patch(_PATCH_ILP, return_value=(False, "chain_too_shallow:0<5", None)), pytest.raises(
            TemplateInvariantError, match="chain_too_shallow"
        ):
            generate_puzzle("expert", seed=1, max_attempts=10)


class TestHappyPath:
    def test_returns_puzzle_result_with_nested_with(
        self, isolated_registry: dict[str, Template]
    ) -> None:
        """Cleaner happy-path using nested with statements."""
        _register_dummy(isolated_registry, tid="t_ok")
        fake_sol = _fake_solution(chain_depth=3)

        with patch(_PATCH_ENUM, return_value=[]), patch(
            _PATCH_PRE, return_value=(True, [])
        ), patch(_PATCH_ILP, return_value=(True, "", fake_sol)), patch(
            _PATCH_POST, return_value=(True, [])
        ), patch(_PATCH_HS, **{"return_value.solves.return_value": False}), patch(
            _PATCH_DISRUPTION, return_value=7
        ):
            result = generate_puzzle("expert", seed=1, template_id="t_ok", max_attempts=1)

        assert result.chain_depth == 3
        assert result.disruption_score == 7
        assert result.is_unique is True


class TestSeedBehaviour:
    def test_explicit_seed_stored_in_result(
        self, isolated_registry: dict[str, Template]
    ) -> None:
        """An explicit seed is propagated to PuzzleResult.seed."""
        _register_dummy(isolated_registry)
        fake_sol = _fake_solution()

        with patch(_PATCH_ENUM, return_value=[]), patch(
            _PATCH_PRE, return_value=(True, [])
        ), patch(_PATCH_ILP, return_value=(True, "", fake_sol)), patch(
            _PATCH_POST, return_value=(True, [])
        ), patch(_PATCH_HS, **{"return_value.solves.return_value": False}), patch(
            _PATCH_DISRUPTION, return_value=0
        ):
            result = generate_puzzle("expert", seed=42, template_id="t_dummy", max_attempts=1)

        assert result.seed == 42

    def test_none_seed_auto_generated_and_stored(
        self, isolated_registry: dict[str, Template]
    ) -> None:
        """seed=None → an auto-generated int seed is stored (not None) in result."""
        _register_dummy(isolated_registry)
        fake_sol = _fake_solution()

        with patch(_PATCH_ENUM, return_value=[]), patch(
            _PATCH_PRE, return_value=(True, [])
        ), patch(_PATCH_ILP, return_value=(True, "", fake_sol)), patch(
            _PATCH_POST, return_value=(True, [])
        ), patch(_PATCH_HS, **{"return_value.solves.return_value": False}), patch(
            _PATCH_DISRUPTION, return_value=0
        ):
            result = generate_puzzle("expert", seed=None, template_id="t_dummy", max_attempts=1)

        assert isinstance(result.seed, int)


class TestTemplateSelection:
    def test_explicit_template_id_routes_to_named_template(
        self, isolated_registry: dict[str, Template]
    ) -> None:
        """template_id kwarg forces selection of exactly that template."""
        _register_dummy(isolated_registry, tid="t_specific")
        fake_sol = _fake_solution()

        with patch(_PATCH_ENUM, return_value=[]), patch(
            _PATCH_PRE, return_value=(True, [])
        ), patch(_PATCH_ILP, return_value=(True, "", fake_sol)), patch(
            _PATCH_POST, return_value=(True, [])
        ), patch(_PATCH_HS, **{"return_value.solves.return_value": False}), patch(
            _PATCH_DISRUPTION, return_value=0
        ):
            result = generate_puzzle(
                "expert", seed=1, template_id="t_specific", max_attempts=1
            )

        assert result.template_id == "t_specific"


class TestGateRetryBehaviour:
    def test_pre_gate_failure_retries_not_raises(
        self, isolated_registry: dict[str, Template]
    ) -> None:
        """A pre-ILP gate failure causes a retry, not an immediate exception."""
        _register_dummy(isolated_registry)
        fake_sol = _fake_solution()

        # First call: pre-gate fails; second call: all pass.
        pre_gate_responses = [
            (False, ["trivial_extension:B:1:0:0"]),
            (True, []),
        ]
        pre_mock = MagicMock(side_effect=pre_gate_responses)

        with patch(_PATCH_ENUM, return_value=[]), patch(_PATCH_PRE, pre_mock), patch(
            _PATCH_ILP, return_value=(True, "", fake_sol)
        ), patch(_PATCH_POST, return_value=(True, [])), patch(
            _PATCH_HS, **{"return_value.solves.return_value": False}
        ), patch(_PATCH_DISRUPTION, return_value=0):
            result = generate_puzzle("expert", seed=1, template_id="t_dummy", max_attempts=3)

        assert pre_mock.call_count == 2
        assert isinstance(result, PuzzleResult)

    def test_heuristic_gate_failure_retries_not_raises(
        self, isolated_registry: dict[str, Template]
    ) -> None:
        """Heuristic solver returning True causes a retry, not an immediate exception."""
        _register_dummy(isolated_registry)
        fake_sol = _fake_solution()

        # First call: heuristic says trivial; second: not trivial.
        hs_solves_responses = [True, False]

        hs_mock = MagicMock()
        hs_mock.return_value.solves.side_effect = hs_solves_responses

        with patch(_PATCH_ENUM, return_value=[]), patch(
            _PATCH_PRE, return_value=(True, [])
        ), patch(_PATCH_ILP, return_value=(True, "", fake_sol)), patch(
            _PATCH_POST, return_value=(True, [])
        ), patch(_PATCH_HS, hs_mock), patch(_PATCH_DISRUPTION, return_value=0):
            result = generate_puzzle("expert", seed=1, template_id="t_dummy", max_attempts=3)

        assert hs_mock.return_value.solves.call_count == 2
        assert isinstance(result, PuzzleResult)

    def test_ilp_non_chain_failure_retries(
        self, isolated_registry: dict[str, Template]
    ) -> None:
        """ILP reason 'not_unique' is a normal rejection that triggers a retry."""
        _register_dummy(isolated_registry)
        fake_sol = _fake_solution()

        ilp_responses = [
            (False, "not_unique", None),
            (True, "", fake_sol),
        ]

        with patch(_PATCH_ENUM, return_value=[]), patch(
            _PATCH_PRE, return_value=(True, [])
        ), patch(_PATCH_ILP, side_effect=ilp_responses), patch(
            _PATCH_POST, return_value=(True, [])
        ), patch(_PATCH_HS, **{"return_value.solves.return_value": False}), patch(
            _PATCH_DISRUPTION, return_value=0
        ):
            result = generate_puzzle("expert", seed=1, template_id="t_dummy", max_attempts=3)

        assert isinstance(result, PuzzleResult)
