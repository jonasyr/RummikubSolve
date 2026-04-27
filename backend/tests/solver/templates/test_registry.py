"""Unit tests for solver/generator/templates/__init__.py (registry).

All tests run with an isolated (empty) TEMPLATE_REGISTRY via the
``isolated_registry`` fixture, so registration in one test never bleeds into
another.

Each test that needs a concrete Template subclass calls ``_make_dummy``
to get a fresh class object.  Using a fresh class per call is important:
the idempotency guard in ``register_template`` checks ``type(existing) is cls``,
so re-using the same class object across tests that both register it would
silently skip the second registration rather than exercising the expected path.
"""
from __future__ import annotations

import random
from typing import Literal

import pytest

import solver.generator.templates as registry_module
from solver.generator.templates import (
    get_template,
    list_templates,
    register_template,
)
from solver.generator.templates.base import Template, TemplateInstance

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dummy(
    tid: str = "dummy",
    ver: str = "1",
    tier_: Literal["hard", "expert", "nightmare"] = "expert",
) -> type[Template]:
    """Return a fresh concrete Template subclass with the given identity.

    A new class object is created on every call so the idempotency guard in
    ``register_template`` does not interfere between tests.
    """

    class _Dummy(Template):
        template_id = tid
        template_version = ver
        tier = tier_

        def generate(self, rng: random.Random) -> TemplateInstance:
            return TemplateInstance(
                template_id=tid,
                template_version=ver,
                tier=tier_,
                board_sets=[],
                rack=[],
                declared_chain_depth=0,
                declared_disruption_min=0,
                construction_notes={},
            )

    return _Dummy


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> dict[str, Template]:
    """Provide a clean, empty TEMPLATE_REGISTRY for the duration of the test.

    ``monkeypatch`` restores the original registry automatically after the
    test finishes, keeping tests fully isolated.
    """
    empty: dict[str, Template] = {}
    monkeypatch.setattr(registry_module, "TEMPLATE_REGISTRY", empty)
    return empty


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRegisterTemplate:
    def test_register_and_get(
        self, isolated_registry: dict[str, Template]
    ) -> None:
        """@register_template stores an instance; get_template retrieves it."""
        Dummy = _make_dummy("t_reg", tier_="expert")
        register_template(Dummy)

        result = get_template("t_reg")

        assert isinstance(result, Dummy)

    def test_duplicate_id_raises(
        self, isolated_registry: dict[str, Template]
    ) -> None:
        """Registering a different class with an existing ID raises ValueError."""
        register_template(_make_dummy("t_dup", tier_="hard"))

        with pytest.raises(ValueError, match="t_dup"):
            register_template(_make_dummy("t_dup", tier_="expert"))

    def test_idempotent_re_register(
        self, isolated_registry: dict[str, Template]
    ) -> None:
        """Decorating the same class twice (simulate re-import) does not raise."""
        Dummy = _make_dummy("t_idem")
        register_template(Dummy)
        # Second call with the exact same class should be a no-op.
        register_template(Dummy)

        # Still only one entry in the registry.
        assert list(isolated_registry) == ["t_idem"]


class TestGetTemplate:
    def test_get_nonexistent_raises_key_error(
        self, isolated_registry: dict[str, Template]
    ) -> None:
        """get_template raises KeyError with a readable message for unknown IDs."""
        with pytest.raises(KeyError, match="missing_id"):
            get_template("missing_id")

    def test_get_returns_registered_instance(
        self, isolated_registry: dict[str, Template]
    ) -> None:
        """get_template returns the same instance stored by register_template."""
        Dummy = _make_dummy("t_get")
        register_template(Dummy)

        assert get_template("t_get") is isolated_registry["t_get"]


class TestListTemplates:
    def test_list_all(self, isolated_registry: dict[str, Template]) -> None:
        """list_templates() with no argument returns all registered IDs sorted."""
        register_template(_make_dummy("z_tmpl", tier_="hard"))
        register_template(_make_dummy("a_tmpl", tier_="nightmare"))

        assert list_templates() == ["a_tmpl", "z_tmpl"]

    def test_list_filters_by_tier(
        self, isolated_registry: dict[str, Template]
    ) -> None:
        """list_templates(tier) returns only IDs matching that tier."""
        register_template(_make_dummy("expert_one", tier_="expert"))
        register_template(_make_dummy("hard_one", tier_="hard"))
        register_template(_make_dummy("expert_two", tier_="expert"))

        result = list_templates("expert")

        assert result == ["expert_one", "expert_two"]
        assert "hard_one" not in result

    def test_list_empty_registry(
        self, isolated_registry: dict[str, Template]
    ) -> None:
        """list_templates returns [] when the registry is empty."""
        assert list_templates() == []
        assert list_templates("nightmare") == []
