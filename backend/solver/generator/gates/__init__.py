"""Structural, heuristic, and ILP gates for the template-based puzzle generation pipeline."""
from solver.generator.gates.heuristic_solver import HeuristicSolver, SolverMove
from solver.generator.gates.ilp import run_ilp_gates
from solver.generator.gates.structural import (
    check_joker_structural,
    check_no_single_home,
    check_no_trivial_extension,
    run_post_ilp_gates,
    run_pre_ilp_gates,
)

__all__ = [
    "HeuristicSolver",
    "SolverMove",
    "check_joker_structural",
    "check_no_single_home",
    "check_no_trivial_extension",
    "run_ilp_gates",
    "run_post_ilp_gates",
    "run_pre_ilp_gates",
]
