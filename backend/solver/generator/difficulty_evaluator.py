"""Multi-metric difficulty scoring for puzzle generation.

Phase 3 of the puzzle generation rebuild. Takes a BoardState and its Solution
and computes 8 difficulty dimensions that together predict human-perceived
puzzle hardness better than the old single-metric disruption/chain-depth approach.

Blueprint: "Puzzle Generation System — Full Rebuild Implementation Plan"
           §3 Phase 3 (DifficultyEvaluator — Multi-Metric Scoring)
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from ..engine.objective import compute_chain_depth, compute_disruption_score
from ..engine.solver import solve
from ..generator.set_enumerator import enumerate_valid_sets
from ..models.board_state import BoardState, Solution
from ..models.tileset import TileSet

_WEIGHTS_PATH = Path(__file__).with_name("difficulty_weights.json")


def _load_difficulty_config() -> tuple[dict[str, float], dict[str, float]]:
    raw = json.loads(_WEIGHTS_PATH.read_text(encoding="utf-8"))

    weights = raw.get("weights")
    ceilings = raw.get("normalization_ceilings")
    if not isinstance(weights, dict) or not isinstance(ceilings, dict):
        raise ValueError("difficulty_weights.json must define weights and normalization_ceilings")

    required_weights = {
        "branching",
        "deductive",
        "red_herring",
        "working_memory",
        "ambiguity",
        "fragility",
        "disruption",
        "chain_depth",
    }
    required_ceilings = {
        "branching_factor",
        "deductive_depth",
        "working_memory_load",
        "tile_ambiguity",
        "disruption_score",
        "chain_depth",
    }

    missing_weights = sorted(required_weights - set(weights))
    missing_ceilings = sorted(required_ceilings - set(ceilings))
    if missing_weights or missing_ceilings:
        missing = []
        if missing_weights:
            missing.append(f"weights={missing_weights}")
        if missing_ceilings:
            missing.append(f"normalization_ceilings={missing_ceilings}")
        raise ValueError(
            "difficulty_weights.json is missing required keys: " + ", ".join(missing)
        )

    return (
        {key: float(weights[key]) for key in required_weights},
        {key: float(ceilings[key]) for key in required_ceilings},
    )


_COMPOSITE_WEIGHTS, _NORMALIZATION_CEILINGS = _load_difficulty_config()


@dataclass(frozen=True)
class DifficultyScore:
    """All difficulty dimensions for a single puzzle.

    Fields:
        branching_factor:    Average valid placements per rack tile (§3.1).
        deductive_depth:     chain_depth × log₂(branching_factor + 1) (§3.6).
        red_herring_density: Fraction of placements not in the solution (§3.2).
        working_memory_load: Count of board sets disrupted by the solution (§3.3).
        tile_ambiguity:      Average candidate sets per tile (board + rack) (§3.4).
        solution_fragility:  Sensitivity to single-tile rack changes (§3.5).
        disruption_score:    Board tiles moved to a different group (existing metric).
        chain_depth:         Longest rearrangement dependency chain (existing metric).
        composite_score:     Weighted combination on a 0–100 scale (§3.7).
        classified_tier:     "easy"|"medium"|"hard"|"expert"|"nightmare" (§3.7).
    """

    branching_factor: float
    deductive_depth: float
    red_herring_density: float
    working_memory_load: float
    tile_ambiguity: float
    solution_fragility: float
    disruption_score: int
    chain_depth: int
    composite_score: float
    classified_tier: str


# ---------------------------------------------------------------------------
# Tier thresholds — overlapping bands are intentional (§3.7)
# ---------------------------------------------------------------------------

TIER_THRESHOLDS: dict[str, tuple[int, int]] = {
    "easy": (0, 20),
    "medium": (15, 35),
    "hard": (30, 55),
    "expert": (50, 75),
    "nightmare": (70, 100),
}


# ---------------------------------------------------------------------------
# Private helpers: accept pre-computed candidate list for performance
# ---------------------------------------------------------------------------


def _branching_factor_from_candidates(
    state: BoardState,
    all_candidates: list[TileSet],
) -> float:
    if not state.rack:
        return 0.0
    total = 0
    for rack_tile in state.rack:
        for cs in all_candidates:
            for t in cs.tiles:
                if (
                    not t.is_joker
                    and t.color == rack_tile.color
                    and t.number == rack_tile.number
                ):
                    total += 1
                    break
    return total / len(state.rack)


def _red_herrings_from_candidates(
    state: BoardState,
    solution: Solution,
    all_candidates: list[TileSet],
) -> float:
    if not state.rack:
        return 0.0

    solution_set_keys: set[frozenset[tuple[object, ...]]] = set()
    for ts in solution.new_sets:
        key = frozenset((t.color, t.number, t.copy_id, t.is_joker) for t in ts.tiles)
        solution_set_keys.add(key)

    total = 0
    red_herrings = 0
    for rack_tile in state.rack:
        for cs in all_candidates:
            contains = any(
                not t.is_joker
                and t.color == rack_tile.color
                and t.number == rack_tile.number
                for t in cs.tiles
            )
            if not contains:
                continue
            total += 1
            cs_key = frozenset(
                (t.color, t.number, t.copy_id, t.is_joker) for t in cs.tiles
            )
            if cs_key not in solution_set_keys:
                red_herrings += 1

    return red_herrings / total if total > 0 else 0.0


def _tile_ambiguity_from_candidates(
    state: BoardState,
    all_candidates: list[TileSet],
) -> float:
    all_tiles = list(state.all_tiles)
    if not all_tiles:
        return 0.0
    total = 0
    for tile in all_tiles:
        if tile.is_joker:
            total += len(all_candidates)
        else:
            total += sum(
                1
                for cs in all_candidates
                if any(
                    not t.is_joker
                    and t.color == tile.color
                    and t.number == tile.number
                    for t in cs.tiles
                )
            )
    return total / len(all_tiles)


# ---------------------------------------------------------------------------
# Public metric functions (signatures match §3.1–3.6 spec exactly)
# ---------------------------------------------------------------------------


def compute_branching_factor(state: BoardState) -> float:
    """Average number of valid placements per rack tile (§3.1).

    For each rack tile, count how many distinct candidate sets contain a
    matching (color, number) non-joker tile.  Higher = harder because the
    player must evaluate more options.

    Returns 0.0 if the rack is empty.  Typical range: 1.0–8.0+.
    """
    return _branching_factor_from_candidates(state, enumerate_valid_sets(state))


def compute_red_herrings(state: BoardState, solution: Solution) -> float:
    """Fraction of locally-valid placements that are NOT in the solution (§3.2).

    A "red herring" is a placement that looks valid in isolation but is not
    part of the optimal solution.  Higher density = more wrong turns.

    Returns 0.0 if no placements exist (rack empty or no candidates).
    """
    return _red_herrings_from_candidates(state, solution, enumerate_valid_sets(state))


def compute_working_memory_load(state: BoardState, solution: Solution) -> float:
    """Number of board sets disrupted by the solution (§3.3).

    Counts old board sets whose tile-content signature does not appear
    unchanged in the solution's new sets.  High value = player must
    mentally juggle many sets simultaneously.

    Returns 0.0 when the board is left entirely unchanged.
    """
    old_sigs = [
        frozenset((t.color, t.number, t.is_joker) for t in ts.tiles)
        for ts in state.board_sets
    ]
    new_sigs = set(
        frozenset((t.color, t.number, t.is_joker) for t in ts.tiles)
        for ts in solution.new_sets
    )
    disrupted = sum(1 for sig in old_sigs if sig not in new_sigs)
    return float(disrupted)


def compute_tile_ambiguity(state: BoardState) -> float:
    """Average candidate sets per tile across all tiles (board + rack) (§3.4).

    High ambiguity means the solver and human must consider many possible
    arrangements, directly measuring search-space breadth.

    Returns 0.0 if there are no tiles.
    """
    return _tile_ambiguity_from_candidates(state, enumerate_valid_sets(state))


def compute_solution_fragility(state: BoardState, solution: Solution) -> float:
    """Sensitivity of the solution to single rack-tile removal (§3.5).

    For each rack tile: remove it, re-solve, and check whether the result
    changes significantly (tiles_placed drops OR disruption_score shifts by
    more than 3).  Returns the fraction of tiles whose removal causes a
    significant change.

    This is expensive: runs len(rack) additional solver calls.  Skip for
    easy/medium puzzles by using ``skip_expensive=True`` in evaluate().

    Returns 0.0 if len(rack) <= 1 (nothing to vary).
    """
    if len(state.rack) <= 1:
        return 0.0

    original_disruption = compute_disruption_score(
        state.board_sets, solution.new_sets
    )
    changes = 0

    for i in range(len(state.rack)):
        reduced_rack = [t for j, t in enumerate(state.rack) if j != i]
        reduced_state = BoardState(board_sets=state.board_sets, rack=reduced_rack)
        try:
            reduced_solution = solve(reduced_state, timeout_seconds=2.0)
        except ValueError:
            # Solver post-verification failure on a reduced rack — treat the
            # removal as causing a change (conservative: counts toward fragility).
            changes += 1
            continue

        if reduced_solution.tiles_placed < len(reduced_rack):
            changes += 1
            continue

        new_disruption = compute_disruption_score(
            state.board_sets, reduced_solution.new_sets
        )
        if abs(original_disruption - new_disruption) > 3:
            changes += 1

    return changes / len(state.rack)


def compute_deductive_depth(state: BoardState, solution: Solution) -> float:
    """Sequential reasoning depth estimate (§3.6).

    Approximates how many steps the player must think ahead.
    Heuristic: chain_depth × log₂(branching_factor + 1).

    Returns 0.0 if no tiles were placed (nothing to reason about).
    """
    if not solution.placed_tiles:
        return 0.0
    base_depth = compute_chain_depth(
        state.board_sets, solution.new_sets, solution.placed_tiles
    )
    bf = compute_branching_factor(state)
    return base_depth * math.log2(bf + 1)


def compute_composite_score(
    branching_factor: float,
    deductive_depth: float,
    red_herring_density: float,
    working_memory_load: float,
    tile_ambiguity: float,
    solution_fragility: float,
    disruption_score: int,
    chain_depth: int,
) -> float:
    """Weighted combination of all 8 metrics into a 0–100 composite score (§3.7).

    Each metric is normalised to roughly [0, 1] before weighting.
    Weights (sum to 1.0) reflect estimated cognitive difficulty contribution.
    """
    bf_norm = min(branching_factor / _NORMALIZATION_CEILINGS["branching_factor"], 1.0)
    dd_norm = min(deductive_depth / _NORMALIZATION_CEILINGS["deductive_depth"], 1.0)
    rh_norm = red_herring_density          # already [0, 1]
    wm_norm = min(working_memory_load / _NORMALIZATION_CEILINGS["working_memory_load"], 1.0)
    ta_norm = min(tile_ambiguity / _NORMALIZATION_CEILINGS["tile_ambiguity"], 1.0)
    sf_norm = solution_fragility           # already [0, 1]
    ds_norm = min(disruption_score / _NORMALIZATION_CEILINGS["disruption_score"], 1.0)
    cd_norm = min(chain_depth / _NORMALIZATION_CEILINGS["chain_depth"], 1.0)

    composite = (
        _COMPOSITE_WEIGHTS["branching"] * bf_norm
        + _COMPOSITE_WEIGHTS["deductive"] * dd_norm
        + _COMPOSITE_WEIGHTS["red_herring"] * rh_norm
        + _COMPOSITE_WEIGHTS["working_memory"] * wm_norm
        + _COMPOSITE_WEIGHTS["ambiguity"] * ta_norm
        + _COMPOSITE_WEIGHTS["fragility"] * sf_norm
        + _COMPOSITE_WEIGHTS["disruption"] * ds_norm
        + _COMPOSITE_WEIGHTS["chain_depth"] * cd_norm
    ) * 100.0

    return round(composite, 2)


def classify_tier(composite_score: float) -> str:
    """Map a composite score to the highest-matching difficulty tier (§3.7).

    Tier bands overlap intentionally; the first matching tier (from hardest
    to easiest) is returned so that ambiguous scores get the harder label.

    Falls back to "easy" if no threshold is met (score < 0).
    """
    for tier in ("nightmare", "expert", "hard", "medium", "easy"):
        lo, _ = TIER_THRESHOLDS[tier]
        if composite_score >= lo:
            return tier
    return "easy"


# ---------------------------------------------------------------------------
# Public facade
# ---------------------------------------------------------------------------


class DifficultyEvaluator:
    """Facade that computes all difficulty metrics for a puzzle in one call.

    Usage::

        state = BoardState(board_sets=remaining_board, rack=rack)
        solution = solve(state)
        score = DifficultyEvaluator.evaluate(state, solution)
        print(score.classified_tier, score.composite_score)

    Performance:
        With ``skip_expensive=False`` (default): ~70–700ms depending on rack size
        (one solver call per rack tile for fragility).
        With ``skip_expensive=True``: <5ms for typical boards.
    """

    @staticmethod
    def evaluate(
        state: BoardState,
        solution: Solution,
        skip_expensive: bool = False,
    ) -> DifficultyScore:
        """Compute all difficulty metrics and return a DifficultyScore.

        Args:
            state:           Board + rack state used to generate the solution.
            solution:        A Solution returned by solve().
            skip_expensive:  If True, solution_fragility is set to 0.0 without
                             running the per-tile solver calls.  Recommended
                             for easy and medium puzzle generation.

        Returns:
            DifficultyScore with all fields populated.
        """
        # Cache candidate sets: avoids triple enumeration across bf, rh, ta.
        all_candidates = enumerate_valid_sets(state)

        bf = _branching_factor_from_candidates(state, all_candidates)
        rh = _red_herrings_from_candidates(state, solution, all_candidates)
        wm = compute_working_memory_load(state, solution)
        ta = _tile_ambiguity_from_candidates(state, all_candidates)
        sf = 0.0 if skip_expensive else compute_solution_fragility(state, solution)

        # deductive_depth calls compute_branching_factor internally, but we
        # already have bf — pass it via the public function's call to avoid
        # re-enumeration.  The call is cheap enough that the double-bf cost
        # (one extra enumerate_valid_sets) is acceptable; optimize if needed.
        dd = compute_deductive_depth(state, solution)

        ds = compute_disruption_score(state.board_sets, solution.new_sets)
        cd = compute_chain_depth(state.board_sets, solution.new_sets, solution.placed_tiles)
        cs = compute_composite_score(bf, dd, rh, wm, ta, sf, ds, cd)
        tier = classify_tier(cs)

        return DifficultyScore(
            branching_factor=round(bf, 2),
            deductive_depth=round(dd, 2),
            red_herring_density=round(rh, 4),
            working_memory_load=round(wm, 2),
            tile_ambiguity=round(ta, 2),
            solution_fragility=round(sf, 4),
            disruption_score=ds,
            chain_depth=cd,
            composite_score=cs,
            classified_tier=tier,
        )
