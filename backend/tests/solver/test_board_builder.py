"""Tests for solver/generator/board_builder.py.

Validates board validity, overlap scoring, size constraints, and seed
determinism for the Phase 1 BoardBuilder implementation.
"""

from __future__ import annotations

import random
import time

import pytest

from solver.generator.board_builder import (
    BoardBuilder,
    build_overlap_graph,
    score_set_overlap,
    select_high_overlap_sets,
)
from solver.generator.tile_pool import assign_copy_ids, make_tile_pool
from solver.generator.set_enumerator import enumerate_groups, enumerate_runs
from solver.models.board_state import BoardState
from solver.models.tile import Color, Tile
from solver.models.tileset import SetType, TileSet
from solver.validator.rule_checker import is_valid_board, is_valid_set


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build(seed: int = 42, **kwargs) -> list[TileSet]:
    return BoardBuilder.build(random.Random(seed), **kwargs)


def _full_pool_sets() -> list[TileSet]:
    pool = make_tile_pool()
    return enumerate_runs(pool) + enumerate_groups(pool)


# ---------------------------------------------------------------------------
# Board validity
# ---------------------------------------------------------------------------


def test_board_is_valid():
    """Every set in the built board passes is_valid_set()."""
    board_sets = _build()
    for ts in board_sets:
        assert is_valid_set(ts), f"Invalid set: {ts}"


def test_board_passes_is_valid_board():
    """Full board passes is_valid_board() (valid sets + no duplicate tiles)."""
    board_sets = _build()
    state = BoardState(board_sets=board_sets, rack=[])
    assert is_valid_board(state)


def test_no_duplicate_physical_tiles():
    """No (color, number, copy_id) triple appears in more than one set."""
    board_sets = _build()
    seen: set[tuple] = set()
    for ts in board_sets:
        for t in ts.tiles:
            key = (t.color, t.number, t.copy_id, t.is_joker)
            assert key not in seen, f"Duplicate tile: {t}"
            seen.add(key)


def test_copy_ids_are_valid():
    """All tiles have copy_id 0 or 1 (assign_copy_ids ran correctly)."""
    board_sets = _build()
    for ts in board_sets:
        for t in ts.tiles:
            assert t.copy_id in (0, 1), f"Bad copy_id on {t}"


# ---------------------------------------------------------------------------
# Size constraints
# ---------------------------------------------------------------------------


def test_board_has_target_size_default():
    """Board has between 10 and 15 sets (default board_size_range)."""
    board_sets = _build()
    assert 10 <= len(board_sets) <= 15, f"Board size {len(board_sets)} out of range"


@pytest.mark.parametrize("lo,hi", [(5, 8), (10, 15), (3, 6)])
def test_board_respects_size_range(lo, hi):
    """Board size stays within the requested range."""
    board_sets = _build(board_size_range=(lo, hi))
    assert lo <= len(board_sets) <= hi, f"Board size {len(board_sets)} outside ({lo},{hi})"


def test_small_board_size_range():
    """Works correctly with a narrow (min == max) size range."""
    board_sets = _build(board_size_range=(5, 5))
    assert len(board_sets) == 5


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_deterministic_with_seed():
    """Same seed produces identical board sets."""
    board_a = _build(seed=123)
    board_b = _build(seed=123)
    assert len(board_a) == len(board_b)
    for ts_a, ts_b in zip(board_a, board_b):
        assert ts_a.type == ts_b.type
        assert [(t.color, t.number, t.copy_id) for t in ts_a.tiles] == [
            (t.color, t.number, t.copy_id) for t in ts_b.tiles
        ]


def test_different_seeds_produce_different_boards():
    """Different seeds reliably produce different boards."""
    results = [_build(seed=s) for s in range(10)]
    tile_sets = [
        frozenset((t.color, t.number) for ts in board for t in ts.tiles)
        for board in results
    ]
    # At least some boards should differ
    assert len(set(tile_sets)) > 1, "All seeds produced identical boards"


# ---------------------------------------------------------------------------
# Overlap scoring
# ---------------------------------------------------------------------------


def test_overlap_graph_non_empty():
    """Overlap graph has entries for all colors and numbers."""
    all_sets = _full_pool_sets()
    graph = build_overlap_graph(all_sets)
    assert len(graph) > 0
    # Every (Color, 1..13) pair should have neighbours
    for color in Color:
        for num in range(1, 14):
            key = (color, num)
            assert key in graph, f"Missing key {key} in overlap graph"
            assert len(graph[key]) > 0, f"No neighbours for {key}"


def test_overlap_graph_symmetric():
    """Overlap graph is symmetric: weight(k1,k2) == weight(k2,k1)."""
    all_sets = _full_pool_sets()
    graph = build_overlap_graph(all_sets)
    for k1, neighbours in graph.items():
        for k2, w in neighbours.items():
            assert graph.get(k2, {}).get(k1) == w, f"Asymmetric edge {k1}↔{k2}"


def test_score_set_overlap_positive():
    """score_set_overlap returns a positive value for a real set."""
    all_sets = _full_pool_sets()
    graph = build_overlap_graph(all_sets)
    # A 3-tile run like Red 1-2-3 should have a positive overlap score
    ts = TileSet(
        type=SetType.RUN,
        tiles=[
            Tile(Color.RED, 1, 0),
            Tile(Color.RED, 2, 0),
            Tile(Color.RED, 3, 0),
        ],
    )
    assert score_set_overlap(ts, graph) > 0.0


def test_score_set_overlap_joker_only_returns_zero():
    """Joker-only set scores 0.0 (no tile keys to sum)."""
    ts = TileSet(type=SetType.RUN, tiles=[Tile.joker(0), Tile.joker(1)])
    assert score_set_overlap(ts, {}) == 0.0


def test_high_overlap_bias_produces_higher_avg_score():
    """overlap_bias=0.9 boards have higher average tile overlap than bias=0.1."""
    all_sets = _full_pool_sets()
    graph = build_overlap_graph(all_sets)

    def avg_score(bias: float, n: int = 10) -> float:
        scores = []
        for seed in range(n):
            board = BoardBuilder.build(
                random.Random(seed), board_size_range=(10, 12), overlap_bias=bias
            )
            scores.extend(score_set_overlap(ts, graph) for ts in board)
        return sum(scores) / len(scores) if scores else 0.0

    high = avg_score(0.9)
    low = avg_score(0.1)
    assert high > low, f"High bias ({high:.1f}) not greater than low bias ({low:.1f})"


# ---------------------------------------------------------------------------
# Integration: assign_copy_ids and tile_pool
# ---------------------------------------------------------------------------


def test_assign_copy_ids_produces_correct_ids():
    """First occurrence of (color, number) gets copy_id=0, second gets copy_id=1."""
    ts1 = TileSet(type=SetType.RUN, tiles=[
        Tile(Color.RED, 1, 0), Tile(Color.RED, 2, 0), Tile(Color.RED, 3, 0)
    ])
    ts2 = TileSet(type=SetType.RUN, tiles=[
        Tile(Color.RED, 1, 0), Tile(Color.RED, 2, 0), Tile(Color.RED, 3, 0)
    ])
    result = assign_copy_ids([ts1, ts2])
    # First set: all copy_id=0
    assert all(t.copy_id == 0 for t in result[0].tiles)
    # Second set: all copy_id=1 (second encounter of each key)
    assert all(t.copy_id == 1 for t in result[1].tiles)


def test_make_tile_pool_has_104_tiles():
    """make_tile_pool() with no jokers produces exactly 104 rack tiles."""
    pool = make_tile_pool(0)
    assert len(pool.rack) == 104
    assert len(pool.board_sets) == 0


def test_make_tile_pool_with_jokers():
    """make_tile_pool(2) produces 106 tiles."""
    pool = make_tile_pool(2)
    assert len(pool.rack) == 106
    jokers = [t for t in pool.rack if t.is_joker]
    assert len(jokers) == 2


def test_make_tile_pool_invalid_joker_count():
    """make_tile_pool(3) raises ValueError."""
    with pytest.raises(ValueError):
        make_tile_pool(3)


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


def test_board_builder_under_100ms():
    """BoardBuilder.build() completes in < 100ms."""
    rng = random.Random(0)
    t0 = time.monotonic()
    BoardBuilder.build(rng)
    elapsed_ms = (time.monotonic() - t0) * 1000
    assert elapsed_ms < 100, f"build() took {elapsed_ms:.1f}ms (limit 100ms)"
