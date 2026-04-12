"""High-overlap board construction for puzzle generation.

Phase 1 of the puzzle generation rebuild. Replaces the greedy random
_pick_compatible_sets() with an overlap-graph-guided selection that
produces boards where tiles participate in many alternative valid sets.

This structural richness is the foundation for difficult puzzles: when
tiles have more alternative placements, removing one forces the solver
(and the human player) to consider more rearrangement options.

Blueprint: "Puzzle Generation System — Full Rebuild Implementation Plan"
           §3 Phase 1 (BoardBuilder — High-Overlap Board Construction)
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict

from ..models.tile import Color, Tile
from ..models.tileset import TileSet
from .set_enumerator import enumerate_groups, enumerate_runs
from .tile_pool import assign_copy_ids, make_tile_pool

# (color, number) pair — copy_id is irrelevant at the template level because
# enumerate_runs/groups use copy_id=0 as a placeholder for all tiles.
TileKey = tuple[Color, int]


def build_overlap_graph(all_sets: list[TileSet]) -> dict[TileKey, dict[TileKey, int]]:
    """Map each tile key to the other tile keys it co-occurs with in templates.

    An edge (k1, k2) with weight w means that k1 and k2 appear together in
    w distinct set templates. Higher weight = more shared context = more
    rearrangement options when one of those tiles is removed.

    Args:
        all_sets: All valid set templates for the current pool.

    Returns:
        Adjacency dict: {tile_key: {neighbour_key: shared_template_count}}.
    """
    adj: dict[TileKey, dict[TileKey, int]] = defaultdict(lambda: defaultdict(int))
    for ts in all_sets:
        keys = [
            (t.color, t.number)
            for t in ts.tiles
            if not t.is_joker and t.color is not None and t.number is not None
        ]
        for i, k1 in enumerate(keys):
            for k2 in keys[i + 1 :]:
                adj[k1][k2] += 1
                adj[k2][k1] += 1
    return dict(adj)


def score_set_overlap(
    ts: TileSet,
    overlap_graph: dict[TileKey, dict[TileKey, int]],
) -> float:
    """Score a set by the average overlap connectivity of its tiles.

    A high score means the set's tiles are shared across many other valid
    templates — making this set a good candidate for a hard puzzle board.

    Args:
        ts: The set template to score.
        overlap_graph: Precomputed adjacency weights from build_overlap_graph().

    Returns:
        Average sum of adjacency weights across all non-joker tile keys.
        Returns 0.0 for joker-only sets.
    """
    keys = [
        (t.color, t.number)
        for t in ts.tiles
        if not t.is_joker and t.color is not None and t.number is not None
    ]
    if not keys:
        return 0.0
    return sum(sum(overlap_graph.get(k, {}).values()) for k in keys) / len(keys)


def select_high_overlap_sets(
    all_sets: list[TileSet],
    overlap_graph: dict[TileKey, dict[TileKey, int]],
    rng: random.Random,
    target_count: int,
    overlap_bias: float = 0.7,
) -> list[TileSet]:
    """Select non-conflicting sets biased toward high tile overlap.

    Uses weighted random selection: each candidate set's weight is
        (1 - overlap_bias) + overlap_bias * (score / max_score)
    This ensures diversity (randomness floor) while strongly favouring
    sets whose tiles have many alternative placements.

    Tile availability is tracked at the physical-copy level: each
    (color, number) starts with 2 copies. A set is a candidate only if
    all its required tiles are still available.

    Args:
        all_sets: Pre-scored set templates (any order).
        overlap_graph: Adjacency weights from build_overlap_graph().
        rng: Seeded RNG for determinism.
        target_count: Desired number of sets on the board.
        overlap_bias: 0.0 = uniform random, 1.0 = pure overlap-greedy.

    Returns:
        Selected TileSet templates (copy_ids still placeholder=0).
        May be fewer than target_count if the pool is exhausted.
    """
    # Physical copy availability: 2 copies of each (color, number).
    avail: Counter[TileKey] = Counter()
    for color in Color:
        for num in range(1, 14):
            avail[(color, num)] = 2

    # Pre-score all sets once.
    scored = [(ts, score_set_overlap(ts, overlap_graph)) for ts in all_sets]
    max_score = max((s for _, s in scored), default=1.0) or 1.0

    selected: list[TileSet] = []
    remaining = list(scored)

    while len(selected) < target_count and remaining:
        # Filter to sets that don't conflict with already-selected tiles.
        candidates = []
        for ts, score in remaining:
            needed: Counter[TileKey] = Counter(
                (t.color, t.number)
                for t in ts.tiles
                if not t.is_joker and t.color is not None and t.number is not None
            )
            if all(avail[k] >= v for k, v in needed.items()):
                candidates.append((ts, score))

        if not candidates:
            break

        # Weighted random selection (weights always > 0 because bias ∈ [0,1]).
        weights = [
            (1.0 - overlap_bias) + overlap_bias * (s / max_score)
            for _, s in candidates
        ]
        chosen_ts, _ = rng.choices(candidates, weights=weights, k=1)[0]

        selected.append(chosen_ts)

        # Deduct used tile copies.
        for t in chosen_ts.tiles:
            if not t.is_joker and t.color is not None and t.number is not None:
                avail[(t.color, t.number)] -= 1

        # Remove chosen set by object identity (TileSet is mutable, not hashable).
        remaining = [(ts, s) for ts, s in remaining if ts is not chosen_ts]

    return selected


class BoardBuilder:
    """Constructs valid Rummikub boards with high tile-overlap.

    Usage::

        rng = random.Random(seed)
        board_sets = BoardBuilder.build(rng, board_size_range=(10, 15))
        # board_sets is a list[TileSet] with correct copy_ids assigned.
    """

    @staticmethod
    def build(
        rng: random.Random,
        board_size_range: tuple[int, int] = (10, 15),
        overlap_bias: float = 0.7,
        n_jokers: int = 0,
    ) -> list[TileSet]:
        """Build a valid high-overlap board.

        Steps:
          1. Create the full tile pool.
          2. Enumerate all valid run and group templates.
          3. Shuffle to randomise tie-breaking before scoring.
          4. Build the tile-overlap graph.
          5. Pick a random target board size within the given range.
          6. Select sets using weighted overlap-biased random selection.
          7. Assign physical copy_ids (convert placeholder 0s to 0/1).

        Note: n_jokers=0 in Phase 1. Joker support is deferred.

        Args:
            rng: Seeded RNG — same seed always produces the same board.
            board_size_range: (min, max) number of sets on the board.
            overlap_bias: 0.0 = random, 1.0 = pure overlap-greedy.
            n_jokers: Joker tiles to include (Phase 1 always uses 0).

        Returns:
            list[TileSet] with copy_ids correctly assigned, ready for use
            as BoardState.board_sets. May be smaller than board_size_range[1]
            if the pool is exhausted.
        """
        pool = make_tile_pool(n_jokers)
        all_sets = enumerate_runs(pool) + enumerate_groups(pool)
        rng.shuffle(all_sets)  # randomise before scoring to break ties
        overlap_graph = build_overlap_graph(all_sets)
        target = rng.randint(*board_size_range)
        board_sets = select_high_overlap_sets(
            all_sets, overlap_graph, rng, target, overlap_bias
        )
        return assign_copy_ids(board_sets)
