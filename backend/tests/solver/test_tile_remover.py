"""Tests for solver/generator/tile_remover.py.

Strategy:
  - Helper functions (estimate_cascade_depth, _apply_removal,
    _score_all_candidates) are tested purely — no solver needed.
  - TileRemover.remove() tests use the real solver (highspy).
"""

from __future__ import annotations

import random

import pytest

from solver.generator.board_builder import BoardBuilder
import solver.generator.tile_remover as tile_remover_module
from solver.generator.tile_remover import (
    RemovalCandidate,
    TileRemover,
    _apply_removal,
    _score_all_candidates,
    estimate_cascade_depth,
)
from solver.models.tile import Color, Tile
from solver.models.tileset import SetType, TileSet

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _tile(color: Color, number: int, copy_id: int = 0) -> Tile:
    return Tile(color=color, number=number, copy_id=copy_id)


def _run(*pairs: tuple[Color, int]) -> TileSet:
    """Build a RUN TileSet from (color, number) pairs."""
    return TileSet(type=SetType.RUN, tiles=[_tile(c, n) for c, n in pairs])


def _group(number: int, *colors: Color) -> TileSet:
    """Build a GROUP TileSet from a number and colors."""
    return TileSet(type=SetType.GROUP, tiles=[_tile(c, number) for c in colors])



# ---------------------------------------------------------------------------
# estimate_cascade_depth — pure logic, no solver
# ---------------------------------------------------------------------------


def test_cascade_survives_set():
    """Removing a tile from a set with ≥4 tiles returns 0.5 (set survives)."""
    ts = _run(
        (Color.RED, 3), (Color.RED, 4), (Color.RED, 5), (Color.RED, 6)
    )
    board = [ts]
    tile = ts.tiles[0]
    result = estimate_cascade_depth(board, tile, 0, [])
    assert result == 0.5


def test_cascade_breaks_set_no_absorbers():
    """Orphans with no absorbers on any other set → cascade = 2.0 per orphan."""
    # 3-tile run [R3, R4, R5]; remove R3 → orphans are [R4, R5]
    # Board has only this one set → absorb_count = 0 for both orphans
    ts = _run((Color.RED, 3), (Color.RED, 4), (Color.RED, 5))
    board = [ts]
    tile = ts.tiles[0]  # Red 3
    result = estimate_cascade_depth(board, tile, 0, [])
    # 2 orphans, 0 absorbers each → 2.0 + 2.0
    assert result == 4.0


def test_cascade_breaks_set_one_absorber_each():
    """Orphans each absorbed by exactly one other set → cascade = 1.0 per orphan."""
    # 3-tile run [R3, R4, R5]; remove R3 → orphans [R4, R5]
    # Board also has [R4, R5, R6] — R4 can extend it? Let's check:
    # [R4, R5, R6] + R4 would be duplicate number in run → NOT valid
    # [R4, R5, R6] + R5 would be duplicate → NOT valid
    # Need a set that R4 or R5 can genuinely extend.
    # [R1, R2, R3] + R4 → [R1,R2,R3,R4] is valid run
    # [R6, R7, R8] + R5 → [R5,R6,R7,R8] is valid run
    ts_main = _run((Color.RED, 3), (Color.RED, 4), (Color.RED, 5))
    ts_absorb_r4 = _run((Color.RED, 1), (Color.RED, 2), (Color.RED, 3))
    ts_absorb_r5 = _run((Color.RED, 6), (Color.RED, 7), (Color.RED, 8))
    board = [ts_main, ts_absorb_r4, ts_absorb_r5]
    tile = ts_main.tiles[0]  # Red 3 — removes it; orphans are Red 4, Red 5

    # Verify absorbers: Red 4 can extend ts_absorb_r4? [R1,R2,R3]+R4 = [R1,R2,R3,R4] valid ✓
    # Red 5 can extend ts_absorb_r5? [R6,R7,R8]+R5 = [R5,R6,R7,R8] valid ✓
    result = estimate_cascade_depth(board, tile, 0, [])
    # 2 orphans, 1 absorber each → 1.0 + 1.0
    assert result == 2.0


def test_cascade_breaks_set_multiple_absorbers():
    """Orphans with multiple absorbers score 0.5 each (ambiguous, not cascading)."""
    # 3-tile group [B5, R5, K5]; remove B5 → orphans [R5, K5]
    # Absorber sets must NOT already contain the orphan tile — otherwise
    # appending it creates a duplicate number which is invalid for a run.
    # [R2,R3,R4] + R5 = [R2,R3,R4,R5] ✓   [R6,R7,R8] + R5 = [R5,R6,R7,R8] ✓
    # [K2,K3,K4] + K5 = [K2,K3,K4,K5] ✓   [K6,K7,K8] + K5 = [K5,K6,K7,K8] ✓
    ts_main = _group(5, Color.BLUE, Color.RED, Color.BLACK)
    ts_r_low  = _run((Color.RED,   2), (Color.RED,   3), (Color.RED,   4))
    ts_r_high = _run((Color.RED,   6), (Color.RED,   7), (Color.RED,   8))
    ts_k_low  = _run((Color.BLACK, 2), (Color.BLACK, 3), (Color.BLACK, 4))
    ts_k_high = _run((Color.BLACK, 6), (Color.BLACK, 7), (Color.BLACK, 8))
    board = [ts_main, ts_r_low, ts_r_high, ts_k_low, ts_k_high]
    tile = ts_main.tiles[0]  # Blue 5; orphans = [Red 5, Black 5]

    result = estimate_cascade_depth(board, tile, 0, [])
    # Both orphans have ≥2 absorbers → 0.5 + 0.5
    assert result == 1.0


def test_cascade_uses_object_identity():
    """estimate_cascade_depth matches tile_to_remove by identity, not value."""
    t1 = _tile(Color.RED, 5, 0)
    t2 = _tile(Color.RED, 5, 0)  # same value, different object
    ts = TileSet(type=SetType.RUN, tiles=[t1, t2, _tile(Color.RED, 6, 0)])
    board = [ts]
    # Remove t1 → remaining should be [t2, Red6]; set has 2 tiles → breaks
    result = estimate_cascade_depth(board, t1, 0, [])
    # Set breaks (2 remaining tiles); both have no absorbers on other sets
    assert result > 0.0  # cascade is positive (not 0.5 which is survive-case)


# ---------------------------------------------------------------------------
# _apply_removal — pure logic, no solver
# ---------------------------------------------------------------------------


def test_apply_removal_removes_correct_tile():
    """The tile at (set_index, tile_index) is removed; others are unchanged."""
    t1, t2, t3 = _tile(Color.RED, 1), _tile(Color.RED, 2), _tile(Color.RED, 3)
    board = [TileSet(type=SetType.RUN, tiles=[t1, t2, t3])]
    cand = RemovalCandidate(
        set_index=0, tile_index=1, tile=t2,
        set_size_after=2, breaks_set=True,
        orphan_count=2, alternative_placements=0, cascade_estimate=1.0,
    )
    result = _apply_removal(board, cand)
    assert len(result) == 1
    assert result[0].tiles == [t1, t3]


def test_apply_removal_drops_empty_set():
    """A set that becomes empty after removal is dropped from the board."""
    t = _tile(Color.RED, 5)
    board = [TileSet(type=SetType.RUN, tiles=[t])]
    cand = RemovalCandidate(
        set_index=0, tile_index=0, tile=t,
        set_size_after=0, breaks_set=True,
        orphan_count=0, alternative_placements=0, cascade_estimate=2.0,
    )
    result = _apply_removal(board, cand)
    assert result == []


def test_apply_removal_orphaned_2tile_set_kept():
    """A 2-tile remnant is kept on the board (solver handles orphaned tiles)."""
    t1, t2, t3 = _tile(Color.RED, 1), _tile(Color.RED, 2), _tile(Color.RED, 3)
    board = [TileSet(type=SetType.RUN, tiles=[t1, t2, t3])]
    cand = RemovalCandidate(
        set_index=0, tile_index=0, tile=t1,
        set_size_after=2, breaks_set=True,
        orphan_count=2, alternative_placements=0, cascade_estimate=2.0,
    )
    result = _apply_removal(board, cand)
    assert len(result) == 1
    assert len(result[0].tiles) == 2  # 2-tile "set" remains


def test_apply_removal_preserves_tile_identity():
    """Tile objects in the result are the same Python objects as in the input."""
    t1, t2, t3 = _tile(Color.RED, 1), _tile(Color.RED, 2), _tile(Color.RED, 3)
    other_t = _tile(Color.BLUE, 7)
    board = [
        TileSet(type=SetType.RUN, tiles=[t1, t2, t3]),
        TileSet(type=SetType.GROUP, tiles=[other_t]),
    ]
    cand = RemovalCandidate(
        set_index=0, tile_index=0, tile=t1,
        set_size_after=2, breaks_set=True,
        orphan_count=2, alternative_placements=0, cascade_estimate=2.0,
    )
    result = _apply_removal(board, cand)
    # t2 and t3 in first set must be the exact same objects
    assert result[0].tiles[0] is t2
    assert result[0].tiles[1] is t3
    # other_t in second set must be the exact same object
    assert result[1].tiles[0] is other_t


def test_apply_removal_other_sets_unchanged():
    """Sets not at set_index are copied unchanged."""
    ts1 = _run((Color.RED, 1), (Color.RED, 2), (Color.RED, 3))
    ts2 = _group(7, Color.BLUE, Color.RED, Color.BLACK)
    board = [ts1, ts2]
    cand = RemovalCandidate(
        set_index=0, tile_index=0, tile=ts1.tiles[0],
        set_size_after=2, breaks_set=True,
        orphan_count=2, alternative_placements=0, cascade_estimate=1.0,
    )
    result = _apply_removal(board, cand)
    # Second set is intact and contains the same tile objects
    assert result[1].type == SetType.GROUP
    assert all(result[1].tiles[i] is ts2.tiles[i] for i in range(len(ts2.tiles)))


# ---------------------------------------------------------------------------
# _score_all_candidates — pure logic, no solver
# ---------------------------------------------------------------------------


def test_score_all_candidates_count():
    """Returns one candidate per board tile."""
    ts1 = _run((Color.RED, 1), (Color.RED, 2), (Color.RED, 3))  # 3 tiles
    ts2 = _group(5, Color.BLUE, Color.RED, Color.BLACK)           # 3 tiles
    board = [ts1, ts2]
    candidates = _score_all_candidates(board, [])
    assert len(candidates) == 6


def test_score_all_candidates_breaks_set_flag():
    """breaks_set is True iff set_size_after < 3."""
    ts = _run((Color.RED, 1), (Color.RED, 2), (Color.RED, 3))  # 3-tile set
    board = [ts]
    candidates = _score_all_candidates(board, [])
    # All 3 tiles: removing any leaves 2 → breaks_set=True
    assert all(c.breaks_set for c in candidates)
    assert all(c.set_size_after == 2 for c in candidates)


def test_score_all_candidates_no_break_large_set():
    """breaks_set is False for tiles from sets with ≥4 tiles."""
    ts = _run(
        (Color.RED, 1), (Color.RED, 2), (Color.RED, 3), (Color.RED, 4)
    )
    board = [ts]
    candidates = _score_all_candidates(board, [])
    assert all(not c.breaks_set for c in candidates)


def test_score_all_candidates_set_index_tile_index():
    """set_index and tile_index correctly identify each tile's position."""
    ts1 = _run((Color.RED, 1), (Color.RED, 2), (Color.RED, 3))
    ts2 = _group(7, Color.BLUE, Color.RED, Color.BLACK)
    board = [ts1, ts2]
    candidates = _score_all_candidates(board, [])

    # Every (set_index, tile_index) pair should be unique
    positions = {(c.set_index, c.tile_index) for c in candidates}
    assert len(positions) == 6

    # Tiles from set 0 should have set_index=0
    set0_cands = [c for c in candidates if c.set_index == 0]
    assert len(set0_cands) == 3
    assert {c.tile_index for c in set0_cands} == {0, 1, 2}


# ---------------------------------------------------------------------------
# TileRemover.remove() — real solver (highspy)
# ---------------------------------------------------------------------------


def _make_board(seed: int = 0, size: tuple[int, int] = (8, 10)) -> list[TileSet]:
    """Build a real board using BoardBuilder."""
    return BoardBuilder.build(random.Random(seed), board_size_range=size)


def test_removal_produces_target_rack_size():
    """Rack has between min and max tiles on success."""
    result = TileRemover.remove(_make_board(0), random.Random(1), rack_size_range=(3, 5))
    assert result is not None
    _, rack, _ = result
    assert 3 <= len(rack) <= 5


def test_removal_log_matches_rack_size():
    """removal_log has exactly one entry per removed tile."""
    result = TileRemover.remove(_make_board(1), random.Random(2), rack_size_range=(2, 4))
    assert result is not None
    _, rack, log = result
    assert len(log) == len(rack)


def test_board_tiles_not_in_rack():
    """No (color, number, copy_id) appears in both remaining board and rack."""
    result = TileRemover.remove(_make_board(2), random.Random(3), rack_size_range=(3, 5))
    assert result is not None
    remaining_board, rack, _ = result
    board_keys = {
        (t.color, t.number, t.copy_id) for ts in remaining_board for t in ts.tiles
    }
    rack_keys = {(t.color, t.number, t.copy_id) for t in rack}
    assert board_keys.isdisjoint(rack_keys), "Tile appears in both board and rack"


def test_removal_preserves_solvability():
    """Each RemovalStep's solver_result confirms all rack tiles were placed."""
    result = TileRemover.remove(_make_board(3), random.Random(4), rack_size_range=(2, 4))
    assert result is not None
    _, rack, log = result
    assert len(rack) > 0
    for step in log:
        assert step.solver_result.tiles_placed == len(step.state_before.rack) + 1


def test_none_returned_when_minimum_unreachable():
    """Returns None when rack_size_range minimum exceeds available board tiles."""
    # A 2-set board has at most ~6-8 tiles; requesting rack_size=50 forces None.
    board = _make_board(4, size=(2, 2))
    result = TileRemover.remove(board, random.Random(5), rack_size_range=(50, 50))
    assert result is None


def test_deterministic_with_seed():
    """Same seed + same board → identical rack."""
    board = _make_board(5)
    result_a = TileRemover.remove(list(board), random.Random(7), rack_size_range=(3, 5))
    result_b = TileRemover.remove(list(board), random.Random(7), rack_size_range=(3, 5))
    assert result_a is not None and result_b is not None
    _, rack_a, _ = result_a
    _, rack_b, _ = result_b
    assert [(t.color, t.number, t.copy_id) for t in rack_a] == [
        (t.color, t.number, t.copy_id) for t in rack_b
    ]


def test_tile_identity_preserved_in_result():
    """Tiles in the returned board/rack are the same Python objects as the input."""
    board = _make_board(6)
    input_ids = {id(t) for ts in board for t in ts.tiles}
    result = TileRemover.remove(board, random.Random(8), rack_size_range=(2, 4))
    assert result is not None
    remaining_board, rack, _ = result
    for ts in remaining_board:
        for t in ts.tiles:
            assert id(t) in input_ids, f"New Tile object created: {t}"
    for t in rack:
        assert id(t) in input_ids, f"New Tile object in rack: {t}"


def test_state_before_is_pre_removal_snapshot():
    """state_before.rack grows by one at each successive RemovalStep."""
    result = TileRemover.remove(_make_board(7), random.Random(9), rack_size_range=(2, 3))
    assert result is not None
    _, _, log = result
    if len(log) >= 2:
        assert len(log[0].state_before.rack) < len(log[1].state_before.rack)


def test_remove_skips_candidates_when_solver_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Solver ValueError during a trial removal is treated as a rejected candidate."""
    board = _make_board(7)
    real_solve = tile_remover_module.solve
    calls = {"count": 0}

    def flaky_solve(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        if calls["count"] == 1:
            raise ValueError("post-verification failed")
        return real_solve(*args, **kwargs)

    monkeypatch.setattr(tile_remover_module, "solve", flaky_solve)

    result = TileRemover.remove(board, random.Random(9), rack_size_range=(2, 3))
    assert result is not None
    _, rack, _ = result
    assert len(rack) >= 2


def test_cascade_estimate_in_candidates():
    """Tiles from 3-tile sets have higher cascade estimates than tiles from large sets."""
    board = [
        _run((Color.RED, 1), (Color.RED, 2), (Color.RED, 3)),           # 3-tile
        _run((Color.BLUE, 5), (Color.BLUE, 6), (Color.BLUE, 7),         # 5-tile
             (Color.BLUE, 8), (Color.BLUE, 9)),
    ]
    candidates = _score_all_candidates(board, [])
    small_set = [c for c in candidates if c.set_index == 0]
    large_set = [c for c in candidates if c.set_index == 1]
    avg_small = sum(c.cascade_estimate for c in small_set) / len(small_set)
    avg_large = sum(c.cascade_estimate for c in large_set) / len(large_set)
    assert avg_small > avg_large
