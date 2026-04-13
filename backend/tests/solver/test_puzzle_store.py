"""Tests for PuzzleStore — SQLite-backed puzzle pool (Phase 4)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from solver.generator.puzzle_generator import PuzzleResult, generate_puzzle
from solver.generator.puzzle_store import PuzzleStore

pytestmark = pytest.mark.slow

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _medium_result() -> PuzzleResult:
    """One medium puzzle, generated once per module to save time."""
    return generate_puzzle(difficulty="medium", seed=42)


# ---------------------------------------------------------------------------
# TestPuzzleStoreInit
# ---------------------------------------------------------------------------


class TestPuzzleStoreInit:
    def test_creates_db_file(self, tmp_path: Path) -> None:
        db = tmp_path / "puzzles.db"
        store = PuzzleStore(db)
        store.close()
        assert db.exists(), "SQLite file should exist after PuzzleStore.__init__"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        db = tmp_path / "nested" / "sub" / "puzzles.db"
        store = PuzzleStore(db)
        store.close()
        assert db.exists(), "PuzzleStore should create missing parent directories"

    def test_empty_count(self, tmp_path: Path) -> None:
        store = PuzzleStore(tmp_path / "p.db")
        assert store.count() == 0
        store.close()


# ---------------------------------------------------------------------------
# TestStoreAndCount
# ---------------------------------------------------------------------------


class TestStoreAndCount:
    def test_store_returns_uuid(self, tmp_path: Path, _medium_result: PuzzleResult) -> None:
        store = PuzzleStore(tmp_path / "p.db")
        puzzle_id = store.store(_medium_result)
        store.close()
        # Must be a valid UUID4 string
        parsed = uuid.UUID(puzzle_id, version=4)
        assert str(parsed) == puzzle_id

    def test_count_after_store(self, tmp_path: Path, _medium_result: PuzzleResult) -> None:
        store = PuzzleStore(tmp_path / "p.db")
        store.store(_medium_result)
        assert store.count() == 1
        store.close()

    def test_count_by_difficulty(self, tmp_path: Path, _medium_result: PuzzleResult) -> None:
        store = PuzzleStore(tmp_path / "p.db")
        store.store(_medium_result)
        assert store.count("medium") == 1
        assert store.count("easy") == 0
        assert store.count("expert") == 0
        store.close()

    def test_store_multiple(self, tmp_path: Path, _medium_result: PuzzleResult) -> None:
        store = PuzzleStore(tmp_path / "p.db")
        store.store(_medium_result)
        store.store(_medium_result)
        store.store(_medium_result)
        assert store.count() == 3
        assert store.count("medium") == 3
        store.close()

    def test_store_with_seed(self, tmp_path: Path, _medium_result: PuzzleResult) -> None:
        store = PuzzleStore(tmp_path / "p.db")
        puzzle_id = store.store(_medium_result, seed=999)
        store.close()
        assert isinstance(puzzle_id, str)

    def test_store_without_seed(self, tmp_path: Path, _medium_result: PuzzleResult) -> None:
        store = PuzzleStore(tmp_path / "p.db")
        puzzle_id = store.store(_medium_result, seed=None)
        store.close()
        assert isinstance(puzzle_id, str)


# ---------------------------------------------------------------------------
# TestDraw
# ---------------------------------------------------------------------------


class TestDraw:
    def test_draw_returns_result_and_id(
        self, tmp_path: Path, _medium_result: PuzzleResult
    ) -> None:
        store = PuzzleStore(tmp_path / "p.db")
        stored_id = store.store(_medium_result)
        drawn = store.draw("medium")
        store.close()
        assert drawn is not None
        result, puzzle_id = drawn
        assert isinstance(result, PuzzleResult)
        assert isinstance(puzzle_id, str)
        assert puzzle_id == stored_id

    def test_draw_empty_pool_returns_none(self, tmp_path: Path) -> None:
        store = PuzzleStore(tmp_path / "p.db")
        drawn = store.draw("medium")
        store.close()
        assert drawn is None

    def test_draw_excludes_seen_id(
        self, tmp_path: Path, _medium_result: PuzzleResult
    ) -> None:
        store = PuzzleStore(tmp_path / "p.db")
        stored_id = store.store(_medium_result)
        drawn = store.draw("medium", exclude_ids=[stored_id])
        store.close()
        assert drawn is None, "Only puzzle was excluded; pool should appear exhausted"

    def test_draw_skips_excluded_but_returns_other(
        self, tmp_path: Path, _medium_result: PuzzleResult
    ) -> None:
        store = PuzzleStore(tmp_path / "p.db")
        id1 = store.store(_medium_result)
        id2 = store.store(_medium_result)
        # Exclude the first puzzle; the second should be returned
        drawn = store.draw("medium", exclude_ids=[id1])
        store.close()
        assert drawn is not None
        _, returned_id = drawn
        assert returned_id == id2

    def test_draw_result_has_correct_difficulty(
        self, tmp_path: Path, _medium_result: PuzzleResult
    ) -> None:
        store = PuzzleStore(tmp_path / "p.db")
        store.store(_medium_result)
        drawn = store.draw("medium")
        store.close()
        assert drawn is not None
        result, _ = drawn
        assert result.difficulty == "medium"

    def test_draw_none_exclude_list(
        self, tmp_path: Path, _medium_result: PuzzleResult
    ) -> None:
        store = PuzzleStore(tmp_path / "p.db")
        store.store(_medium_result)
        drawn = store.draw("medium", exclude_ids=None)
        store.close()
        assert drawn is not None


# ---------------------------------------------------------------------------
# TestRoundtrip
# ---------------------------------------------------------------------------


class TestRoundtrip:
    @pytest.fixture(autouse=True)
    def _store_and_draw(self, tmp_path: Path, _medium_result: PuzzleResult) -> None:
        store = PuzzleStore(tmp_path / "p.db")
        store.store(_medium_result)
        drawn = store.draw("medium")
        store.close()
        assert drawn is not None
        self.original = _medium_result
        self.result, _ = drawn

    def test_roundtrip_rack_tiles(self) -> None:
        assert len(self.result.rack) == len(self.original.rack)

    def test_roundtrip_board_sets(self) -> None:
        assert len(self.result.board_sets) == len(self.original.board_sets)

    def test_roundtrip_chain_depth(self) -> None:
        assert self.result.chain_depth == self.original.chain_depth

    def test_roundtrip_disruption_score(self) -> None:
        assert self.result.disruption_score == self.original.disruption_score

    def test_roundtrip_is_unique(self) -> None:
        assert isinstance(self.result.is_unique, bool)
        assert self.result.is_unique == self.original.is_unique

    def test_roundtrip_joker_count(self) -> None:
        assert self.result.joker_count == 0  # current puzzles are always joker-free
        assert self.result.joker_count == self.original.joker_count


# ---------------------------------------------------------------------------
# TestV2RoundTrip — Phase 5: verify all v2 fields survive store → draw
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _v2_easy_result() -> PuzzleResult:
    """One v2 easy puzzle, generated once per module."""
    return generate_puzzle(difficulty="easy", seed=99, generator_version="v2")


class TestV2RoundTrip:
    """All v2 PuzzleResult fields (composite_score, branching_factor,
    generator_version) must survive a store → draw round-trip."""

    @pytest.fixture(autouse=True)
    def _store_and_draw(
        self, tmp_path: Path, _v2_easy_result: PuzzleResult
    ) -> None:
        store = PuzzleStore(tmp_path / "v2.db")
        store.store(_v2_easy_result)
        drawn = store.draw("easy")
        store.close()
        assert drawn is not None
        self.original = _v2_easy_result
        self.result, _ = drawn

    def test_roundtrip_generator_version(self) -> None:
        assert self.result.generator_version == "v2.0.0"
        assert self.result.generator_version == self.original.generator_version

    def test_roundtrip_composite_score(self) -> None:
        assert self.result.composite_score == pytest.approx(
            self.original.composite_score, abs=1e-6
        )
        assert self.result.composite_score >= 0.0

    def test_roundtrip_branching_factor(self) -> None:
        assert self.result.branching_factor == pytest.approx(
            self.original.branching_factor, abs=1e-6
        )
        assert self.result.branching_factor >= 0.0
