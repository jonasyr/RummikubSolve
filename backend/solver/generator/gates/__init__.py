"""Structural and ILP gates for the template-based puzzle generation pipeline."""
from solver.generator.gates.structural import (
    check_joker_structural,
    check_no_single_home,
    check_no_trivial_extension,
    run_post_ilp_gates,
    run_pre_ilp_gates,
)

__all__ = [
    "check_joker_structural",
    "check_no_single_home",
    "check_no_trivial_extension",
    "run_post_ilp_gates",
    "run_pre_ilp_gates",
]
