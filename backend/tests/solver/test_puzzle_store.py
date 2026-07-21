"""Tests for PuzzleStore — SQLite-backed puzzle pool (Phase 4)."""

from __future__ import annotations

import sqlite3
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
        row = store.conn.execute("SELECT seed FROM puzzles WHERE id = ?", (puzzle_id,)).fetchone()
        store.close()
        assert isinstance(puzzle_id, str)
        assert row["seed"] == 999

    def test_store_without_seed(self, tmp_path: Path, _medium_result: PuzzleResult) -> None:
        store = PuzzleStore(tmp_path / "p.db")
        puzzle_id = store.store(_medium_result, seed=None)
        row = store.conn.execute("SELECT seed FROM puzzles WHERE id = ?", (puzzle_id,)).fetchone()
        store.close()
        assert isinstance(puzzle_id, str)
        assert row["seed"] == 42


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
    """All v2 PuzzleResult fields survive a store → draw round-trip."""

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

    def test_roundtrip_deductive_depth(self) -> None:
        assert self.result.deductive_depth == pytest.approx(
            self.original.deductive_depth, abs=1e-6
        )

    def test_roundtrip_red_herring_density(self) -> None:
        assert self.result.red_herring_density == pytest.approx(
            self.original.red_herring_density, abs=1e-6
        )

    def test_roundtrip_working_memory_load(self) -> None:
        assert self.result.working_memory_load == pytest.approx(
            self.original.working_memory_load, abs=1e-6
        )

    def test_roundtrip_tile_ambiguity(self) -> None:
        assert self.result.tile_ambiguity == pytest.approx(
            self.original.tile_ambiguity, abs=1e-6
        )

    def test_roundtrip_solution_fragility(self) -> None:
        assert self.result.solution_fragility == pytest.approx(
            self.original.solution_fragility, abs=1e-6
        )

    def test_roundtrip_seed(self) -> None:
        assert self.result.seed == self.original.seed


# ---------------------------------------------------------------------------
# TestTemplateMetadata — Issue #28
# ---------------------------------------------------------------------------


@pytest.fixture
def _minimal_result() -> PuzzleResult:
    """Minimal PuzzleResult with no board/rack tiles — sufficient for schema tests."""
    return PuzzleResult(board_sets=[], rack=[], difficulty="easy", disruption_score=0)


class TestTemplateMetadata:
    def test_default_template_id_is_legacy(
        self, tmp_path: Path, _minimal_result: PuzzleResult
    ) -> None:
        store = PuzzleStore(tmp_path / "p.db")
        puzzle_id = store.store(_minimal_result)
        row = store.conn.execute(
            "SELECT template_id, template_version FROM puzzles WHERE id = ?", (puzzle_id,)
        ).fetchone()
        store.close()
        assert row["template_id"] == "legacy"
        assert row["template_version"] == "0"

    def test_template_id_round_trip(
        self, tmp_path: Path, _minimal_result: PuzzleResult
    ) -> None:
        store = PuzzleStore(tmp_path / "p.db")
        puzzle_id = store.store(
            _minimal_result,
            template_id="T1_joker_displacement_v1",
            template_version="1",
        )
        row = store.conn.execute(
            "SELECT template_id, template_version FROM puzzles WHERE id = ?", (puzzle_id,)
        ).fetchone()
        store.close()
        assert row["template_id"] == "T1_joker_displacement_v1"
        assert row["template_version"] == "1"

    def test_list_by_template_returns_matching_ids(
        self, tmp_path: Path, _minimal_result: PuzzleResult
    ) -> None:
        store = PuzzleStore(tmp_path / "p.db")
        id_t1 = store.store(_minimal_result, template_id="T1")
        store.store(_minimal_result, template_id="T2")
        results = store.list_by_template("T1")
        store.close()
        assert results == [id_t1]

    def test_existing_db_gets_columns_via_migration(
        self, tmp_path: Path, _minimal_result: PuzzleResult
    ) -> None:
        db_path = tmp_path / "old.db"
        # Create a DB with the old schema (no template columns).
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE puzzles (
                id TEXT PRIMARY KEY, difficulty TEXT NOT NULL,
                board_json TEXT NOT NULL, rack_json TEXT NOT NULL,
                chain_depth INTEGER NOT NULL, disruption INTEGER NOT NULL,
                rack_size INTEGER NOT NULL, board_size INTEGER NOT NULL,
                is_unique INTEGER NOT NULL DEFAULT 0,
                joker_count INTEGER NOT NULL DEFAULT 0,
                seed INTEGER, created_at TEXT NOT NULL DEFAULT (datetime('now')),
                generator_version TEXT NOT NULL DEFAULT 'v1',
                composite_score REAL NOT NULL DEFAULT 0.0,
                branching_factor REAL NOT NULL DEFAULT 0.0,
                deductive_depth REAL NOT NULL DEFAULT 0.0,
                red_herring_density REAL NOT NULL DEFAULT 0.0,
                working_memory_load REAL NOT NULL DEFAULT 0.0,
                tile_ambiguity REAL NOT NULL DEFAULT 0.0,
                solution_fragility REAL NOT NULL DEFAULT 0.0
            )
        """)
        conn.execute(
            """INSERT INTO puzzles
               (id, difficulty, board_json, rack_json, chain_depth, disruption,
                rack_size, board_size, is_unique, joker_count)
               VALUES ('old-id', 'easy', '[]', '[]', 0, 0, 0, 0, 0, 0)"""
        )
        conn.commit()
        conn.close()

        # Reopen via PuzzleStore — migration should add the new columns.
        store = PuzzleStore(db_path)
        drawn = store.draw_by_id("old-id")
        row = store.conn.execute(
            "SELECT template_id, template_version FROM puzzles WHERE id = 'old-id'"
        ).fetchone()
        store.close()
        assert drawn is not None
        assert row["template_id"] == "legacy"
        assert row["template_version"] == "0"
