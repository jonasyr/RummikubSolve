"""Template registry for the template-based puzzle generation pipeline.

Provides a global registry (:data:`TEMPLATE_REGISTRY`) that maps
``template_id`` strings to :class:`~solver.generator.templates.base.Template`
instances.  Templates self-register by decorating their class with
:func:`register_template`.

Usage
-----
Defining and registering a template::

    from solver.generator.templates import register_template
    from solver.generator.templates.base import Template, TemplateInstance

    @register_template
    class MyTemplate(Template):
        template_id = "my_template_v1"
        template_version = "1"
        tier = "expert"

        def generate(self, rng):
            ...

Querying the registry::

    from solver.generator.templates import get_template, list_templates

    t = get_template("my_template_v1")
    expert_ids = list_templates("expert")

See ``Puzzle Generation Rebuild Plan.md`` §4.2.1.
"""
from __future__ import annotations

__all__ = [
    "TEMPLATE_REGISTRY",
    "get_template",
    "list_templates",
    "register_template",
]

from solver.generator.templates.base import (  # noqa: F401
    Template,
    TemplateInstance,
    TemplateInvariantError,
)

# ---------------------------------------------------------------------------
# Global registry — populated by @register_template at class-definition time.
# ---------------------------------------------------------------------------

TEMPLATE_REGISTRY: dict[str, Template] = {}


def register_template[T: type[Template]](cls: T) -> T:
    """Class decorator: instantiate *cls* and add it to :data:`TEMPLATE_REGISTRY`.

    Idempotency
    -----------
    Decorating the **same class** more than once (e.g., because the module is
    re-imported during test collection) is silently ignored — the existing
    registry entry is kept unchanged.

    Registering a **different class** with an already-registered
    ``template_id`` raises :exc:`ValueError` immediately.

    Parameters
    ----------
    cls:
        A concrete subclass of :class:`~solver.generator.templates.base.Template`
        with ``template_id``, ``template_version``, and ``tier`` defined as
        class variables.

    Returns
    -------
    The unmodified class (so the decorator is transparent to the rest of the
    codebase and to type-checkers).
    """
    tid = cls.template_id
    if tid in TEMPLATE_REGISTRY:
        if type(TEMPLATE_REGISTRY[tid]) is cls:
            # Same class re-decorated (e.g., module re-import) — idempotent.
            return cls
        raise ValueError(
            f"Duplicate template_id {tid!r}: already registered by "
            f"{type(TEMPLATE_REGISTRY[tid]).__name__}, "
            f"cannot re-register as {cls.__name__}."
        )
    TEMPLATE_REGISTRY[tid] = cls()
    return cls


def get_template(template_id: str) -> Template:
    """Return the registered template with the given *template_id*.

    Parameters
    ----------
    template_id:
        The unique identifier of the desired template.

    Raises
    ------
    KeyError
        If no template with *template_id* is registered.  The error message
        includes the list of currently registered IDs to aid debugging.
    """
    try:
        return TEMPLATE_REGISTRY[template_id]
    except KeyError:
        available = sorted(TEMPLATE_REGISTRY)
        raise KeyError(
            f"No template registered with id={template_id!r}. "
            f"Available: {available}"
        ) from None


def list_templates(tier: str | None = None) -> list[str]:
    """Return a sorted list of registered template IDs.

    Parameters
    ----------
    tier:
        If given, only IDs whose template's :attr:`~Template.tier` matches
        are returned.  Pass ``None`` (the default) to list all registered IDs.

    Returns
    -------
    list[str]
        Sorted list of matching template IDs.
    """
    if tier is None:
        return sorted(TEMPLATE_REGISTRY)
    return sorted(
        t_id for t_id, t in TEMPLATE_REGISTRY.items() if t.tier == tier
    )


# ---------------------------------------------------------------------------
# Template module imports — add one line per template as they are implemented.
# Each import triggers the @register_template decorator and populates the
# registry automatically.  Import order does not matter.
# ---------------------------------------------------------------------------
# from solver.generator.templates import t1_joker_displacement  # noqa: F401
# from solver.generator.templates import t2_false_extension     # noqa: F401
# from solver.generator.templates import t3_multi_group_merge   # noqa: F401
# from solver.generator.templates import t4_run_group_transform # noqa: F401
# from solver.generator.templates import t5_compound            # noqa: F401
# ---------------------------------------------------------------------------
