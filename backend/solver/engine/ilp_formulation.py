"""Construction of the HiGHS ILP model from a BoardState.

Blueprint §2.2 — ILP Formulation:

Decision variables:
  x[t][s] ∈ {0,1}  — tile t is assigned to set s
  h[t]    ∈ {0,1}  — tile t remains in hand (rack tiles only)
  y[s]    ∈ {0,1}  — set s is active (selected in the solution)

Objective: minimise Σ h[t] for t ∈ rack
           (equivalently: maximise tiles placed from rack)

Constraints:
  1. Each tile assigned to exactly one active set or stays in hand.
  2. A set is active only if all its slots are filled by exactly one tile.
  3. Board tiles may not remain in hand (they must all be placed).
  4. Joker slots: filled by physical joker tiles in the pool.

Variable layout
  Columns 0..S-1           : y[s] binary variables (one per candidate set)
  Columns S..              : x[t,s] and h[t] binary variables (sparse)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from ..config.rules import RulesConfig
from ..models.board_state import BoardState
from ..models.tile import Color, Tile
from ..models.tileset import TileSet


@dataclass
class ILPModel:
    """HiGHS model + variable index mappings needed for solution extraction."""

    highs: Any  # highspy.Highs instance (imported lazily to avoid hard dep at module level)
    all_tiles: list[Tile]
    candidate_sets: list[TileSet]
    # y_vars[s] = column index of the y[s] binary variable
    y_vars: list[int]
    # x_vars[(tile_idx, set_idx)] = column index of x[tile_idx][set_idx]
    x_vars: dict[tuple[int, int], int] = field(default_factory=dict)
    # h_vars[tile_idx] = column index of h[tile_idx] (rack tiles only)
    h_vars: dict[int, int] = field(default_factory=dict)
    # Indices into all_tiles that belong to the rack (not the board).
    rack_tile_indices: frozenset[int] = field(default_factory=frozenset)


def build_ilp_model(
    state: BoardState,
    candidate_sets: list[TileSet],
    rules: RulesConfig,
) -> ILPModel:
    """Build and configure the HiGHS ILP model.

    Args:
        state:          Current board + rack state.
        candidate_sets: Pre-enumerated valid set templates (from set_enumerator).
        rules:          Rule variant configuration.

    Returns:
        An ILPModel wrapping a configured highspy.Highs instance.
        Call model.highs.run() to solve, then extract_solution(model) for results.
    """
    import highspy

    highs = highspy.Highs()
    highs.silent()

    all_tiles = list(state.all_tiles)
    n_tiles = len(all_tiles)
    n_sets = len(candidate_sets)

    # Classify tiles: board vs rack.
    board_tile_ids = {id(t) for ts in state.board_sets for t in ts.tiles}
    rack_tile_idx_set: frozenset[int] = frozenset(
        i for i, t in enumerate(all_tiles) if id(t) not in board_tile_ids
    )

    # Build an index from slot key → list of tile indices that can fill it.
    # Joker slots: key = (True, None, None); normal slots: (False, color, number).
    SlotKey = tuple[bool, Color | None, int | None]
    key_to_tile_indices: dict[SlotKey, list[int]] = defaultdict(list)
    for t_idx, tile in enumerate(all_tiles):
        if tile.is_joker:
            key_to_tile_indices[(True, None, None)].append(t_idx)
        else:
            key_to_tile_indices[(False, tile.color, tile.number)].append(t_idx)

    # For each candidate set, compute: list-of-slots → list-of-candidate-tile-indices.
    # template_slot_candidates[s] = [ [tile_indices for slot 0], [... slot 1], ... ]
    template_slot_candidates: list[list[list[int]]] = []
    for tmpl in candidate_sets:
        slots: list[list[int]] = []
        for slot_tile in tmpl.tiles:
            if slot_tile.is_joker:
                key: SlotKey = (True, None, None)
            else:
                key = (False, slot_tile.color, slot_tile.number)
            slots.append(list(key_to_tile_indices[key]))
        template_slot_candidates.append(slots)

    # For each tile, collect the set indices where it could be placed.
    # A tile t_idx can be placed in set s if it appears in any slot of s
    # (at most once, since valid sets have no duplicate (color,number) slots).
    tile_to_sets: list[list[int]] = [[] for _ in range(n_tiles)]
    for s, slot_cands_list in enumerate(template_slot_candidates):
        seen: set[int] = set()
        for slot_cands in slot_cands_list:
            for t_idx in slot_cands:
                if t_idx not in seen:
                    tile_to_sets[t_idx].append(s)
                    seen.add(t_idx)

    # ── Create variables ────────────────────────────────────────────────────

    # y[s]: one binary per candidate set.
    y_vars: list[int] = []
    for _ in range(n_sets):
        v = highs.addBinary()
        y_vars.append(v.index)

    # x[t_idx, s]: one binary per (tile, set) pair where placement is possible.
    x_vars: dict[tuple[int, int], int] = {}
    for t_idx in range(n_tiles):
        for s in tile_to_sets[t_idx]:
            v = highs.addBinary()
            x_vars[(t_idx, s)] = v.index

    # h[t_idx]: one binary per rack tile.
    h_vars: dict[int, int] = {}
    for t_idx in rack_tile_idx_set:
        v = highs.addBinary()
        h_vars[t_idx] = v.index

    # ── Add constraints ─────────────────────────────────────────────────────

    # Constraint 1 — Tile conservation.
    # For a board tile: Σ_s x[t][s] = 1  (must be placed somewhere)
    # For a rack tile:  Σ_s x[t][s] + h[t] = 1  (placed or stays in hand)
    for t_idx in range(n_tiles):
        var_col: list[int] = [x_vars[(t_idx, s)] for s in tile_to_sets[t_idx]]
        coefs: list[float] = [1.0] * len(var_col)

        if t_idx in rack_tile_idx_set:
            var_col.append(h_vars[t_idx])
            coefs.append(1.0)

        if var_col:
            highs.addRow(1.0, 1.0, len(var_col), var_col, coefs)
        elif t_idx not in rack_tile_idx_set:
            # Board tile with zero matching templates → model is infeasible.
            # Encode 0 = 1 to propagate infeasibility to HiGHS.
            highs.addRow(1.0, 1.0, 0, [], [])

    # Constraint 2 — Slot satisfaction.
    # For each set s and each slot p:  Σ_{t ∈ candidates(s,p)} x[t][s] = y[s]
    # Rearranged:  Σ x[t][s] - y[s] = 0
    for s in range(n_sets):
        for slot_cands in template_slot_candidates[s]:
            x_col = [x_vars[(t_idx, s)] for t_idx in slot_cands if (t_idx, s) in x_vars]
            if not x_col:
                # No physical tile can fill this slot → force y[s] = 0.
                highs.addRow(0.0, 0.0, 1, [y_vars[s]], [1.0])
                continue
            cols = x_col + [y_vars[s]]
            cf = [1.0] * len(x_col) + [-1.0]
            highs.addRow(0.0, 0.0, len(cols), cols, cf)

    # Constraint 3 — First-turn meld threshold (when rules.is_first_turn).
    # On the first turn, the player may not rearrange the board (handled by
    # passing a rack-only state in solver.py), and the combined face value of
    # all placed rack tiles must be ≥ initial_meld_threshold.
    #
    # Encoding: Σ_{t ∈ rack, non-joker} number * h[t] ≤ total_rack_value - threshold
    #           ≡ Σ_placed number ≥ threshold
    #
    # If total_rack_value < threshold the upper bound is negative, which is
    # infeasible for a non-negative variable sum → HiGHS returns kInfeasible
    # → solver.py maps this to tiles_placed=0 ("no valid first-turn play").
    if rules.is_first_turn:
        h_cols: list[int] = []
        coeffs: list[float] = []
        total_value = 0.0
        for t_idx in rack_tile_idx_set:
            tile = all_tiles[t_idx]
            if not tile.is_joker and tile.number is not None:
                h_cols.append(h_vars[t_idx])
                val = float(tile.number)
                coeffs.append(val)
                total_value += val
        ub = total_value - float(rules.initial_meld_threshold)
        if h_cols:
            highs.addRow(-1e30, ub, len(h_cols), h_cols, coeffs)

    # ── Objective ───────────────────────────────────────────────────────────

    # Primary:   minimise tiles left in hand (= maximise tiles placed).
    # Secondary: among equal tile-count solutions, minimise the sum of face
    #            values of remaining tiles (prefer keeping low-value tiles).
    #
    # Encoding: cost(h[t]) = 1.0 + tile_value / BIG_M
    # BIG_M > max possible rack value sum (13 tiles × 13 = 169) → the
    # fractional part can never flip the primary ranking.
    BIG_M = 200.0
    for t_idx, h_col in h_vars.items():
        tile = all_tiles[t_idx]
        tile_value = (
            float(tile.number)
            if (not tile.is_joker and tile.number is not None)
            else 0.0
        )
        highs.changeColCost(h_col, 1.0 + tile_value / BIG_M)

    return ILPModel(
        highs=highs,
        all_tiles=all_tiles,
        candidate_sets=candidate_sets,
        y_vars=y_vars,
        x_vars=x_vars,
        h_vars=h_vars,
        rack_tile_indices=rack_tile_idx_set,
    )


def extract_solution(
    model: ILPModel,
) -> tuple[list[TileSet], list[Tile], list[Tile], bool]:
    """Extract a Solution from a solved ILPModel.

    Should be called after model.highs.run().

    Returns:
        (new_sets, placed_tiles, remaining_rack, is_optimal)

    Raises:
        ValueError: If the model status is Infeasible (input was invalid).
    """
    import highspy

    status = model.highs.getModelStatus()

    if status == highspy.HighsModelStatus.kInfeasible:
        raise ValueError(
            "ILP model is infeasible — board tiles cannot all be placed in valid sets. "
            "Check that the input board state is valid."
        )

    # kModelEmpty: no variables were added (empty rack + empty board).
    # Treat as trivially optimal with zero tiles placed.
    is_optimal = status in (
        highspy.HighsModelStatus.kOptimal,
        highspy.HighsModelStatus.kModelEmpty,
    )

    sol = model.highs.getSolution()
    col_value: list[float] = sol.col_value
    EPS = 0.5  # Threshold for treating a binary variable as 1.

    all_tiles = model.all_tiles
    new_sets: list[TileSet] = []
    placed_tile_indices: set[int] = set()

    for s, y_col in enumerate(model.y_vars):
        if col_value[y_col] > EPS:
            template = model.candidate_sets[s]
            assigned: list[Tile] = []
            for t_idx in range(len(all_tiles)):
                if (t_idx, s) in model.x_vars:
                    x_col = model.x_vars[(t_idx, s)]
                    if col_value[x_col] > EPS:
                        assigned.append(all_tiles[t_idx])
                        if t_idx in model.rack_tile_indices:
                            placed_tile_indices.add(t_idx)
            new_sets.append(TileSet(type=template.type, tiles=assigned))

    placed_tiles = [all_tiles[i] for i in sorted(placed_tile_indices)]
    remaining_rack = [
        all_tiles[i] for i in sorted(model.rack_tile_indices) if i not in placed_tile_indices
    ]

    return new_sets, placed_tiles, remaining_rack, is_optimal
