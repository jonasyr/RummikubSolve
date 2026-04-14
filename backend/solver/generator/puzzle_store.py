"""SQLite-based storage for pre-generated Rummikub puzzles.

Puzzles are stored with full metadata so the API can filter by
difficulty, exclude already-seen puzzles, and return puzzle IDs
for client-side deduplication tracking.

Default DB path: data/puzzles.db (relative to CWD).
Override via PUZZLE_DB_PATH environment variable.
"""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from ..models.tile import Color, Tile
from ..models.tileset import SetType, TileSet
from .puzzle_generator import PuzzleResult

DEFAULT_DB_PATH = Path(os.getenv("PUZZLE_DB_PATH", "data/puzzles.db"))

_CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS puzzles (
        id               TEXT PRIMARY KEY,
        difficulty       TEXT NOT NULL,
        board_json       TEXT NOT NULL,
        rack_json        TEXT NOT NULL,
        chain_depth      INTEGER NOT NULL,
        disruption       INTEGER NOT NULL,
        rack_size        INTEGER NOT NULL,
        board_size       INTEGER NOT NULL,
        is_unique        INTEGER NOT NULL DEFAULT 0,
        joker_count      INTEGER NOT NULL DEFAULT 0,
        seed             INTEGER,
        created_at       TEXT NOT NULL DEFAULT (datetime('now')),
        generator_version TEXT NOT NULL DEFAULT 'v1',
        composite_score  REAL NOT NULL DEFAULT 0.0,
        branching_factor REAL NOT NULL DEFAULT 0.0,
        deductive_depth REAL NOT NULL DEFAULT 0.0,
        red_herring_density REAL NOT NULL DEFAULT 0.0,
        working_memory_load REAL NOT NULL DEFAULT 0.0,
        tile_ambiguity REAL NOT NULL DEFAULT 0.0,
        solution_fragility REAL NOT NULL DEFAULT 0.0
    )
"""

# Columns added in Phase 0/4 that may not exist in older DBs.
# Using try/except because SQLite < 3.35 does not support ADD COLUMN IF NOT EXISTS.
_MIGRATION_COLUMNS: list[tuple[str, str]] = [
    ("generator_version", "TEXT NOT NULL DEFAULT 'v1'"),
    ("composite_score", "REAL NOT NULL DEFAULT 0.0"),
    ("branching_factor", "REAL NOT NULL DEFAULT 0.0"),
    ("deductive_depth", "REAL NOT NULL DEFAULT 0.0"),
    ("red_herring_density", "REAL NOT NULL DEFAULT 0.0"),
    ("working_memory_load", "REAL NOT NULL DEFAULT 0.0"),
    ("tile_ambiguity", "REAL NOT NULL DEFAULT 0.0"),
    ("solution_fragility", "REAL NOT NULL DEFAULT 0.0"),
]

_CREATE_INDEX = """
    CREATE INDEX IF NOT EXISTS idx_difficulty
    ON puzzles(difficulty)
"""


class PuzzleStore:
    """SQLite-backed pool of pre-generated Rummikub puzzles.

    Typical usage::

        store = PuzzleStore(Path("data/puzzles.db"))
        puzzle_id = store.store(result, seed=42)
        drawn = store.draw("expert", exclude_ids=["old-uuid-1"])
        if drawn is not None:
            result, puzzle_id = drawn
        store.close()
    """

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.execute(_CREATE_TABLE)
        self.conn.execute(_CREATE_INDEX)
        # Phase 0 migration: add columns to existing DBs that pre-date v0.40.
        # contextlib.suppress handles "duplicate column" OperationalError on
        # SQLite versions that lack ADD COLUMN IF NOT EXISTS (< 3.35).
        for col_name, col_def in _MIGRATION_COLUMNS:
            with contextlib.suppress(sqlite3.OperationalError):
                self.conn.execute(
                    f"ALTER TABLE puzzles ADD COLUMN {col_name} {col_def}"
                )
        self.conn.commit()

    def store(self, result: PuzzleResult, seed: int | None = None) -> str:
        """Persist a puzzle and return its UUID."""
        puzzle_id = str(uuid.uuid4())
        effective_seed = seed if seed is not None else result.seed
        self.conn.execute(
            """INSERT INTO puzzles
               (id, difficulty, board_json, rack_json, chain_depth,
                disruption, rack_size, board_size, is_unique,
                joker_count, seed, generator_version, composite_score,
                branching_factor, deductive_depth, red_herring_density,
                working_memory_load, tile_ambiguity, solution_fragility)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                puzzle_id,
                result.difficulty,
                _serialize_board(result.board_sets),
                _serialize_rack(result.rack),
                result.chain_depth,
                result.disruption_score,
                len(result.rack),
                len(result.board_sets),
                int(result.is_unique),
                result.joker_count,
                effective_seed,
                result.generator_version,
                result.composite_score,
                result.branching_factor,
                result.deductive_depth,
                result.red_herring_density,
                result.working_memory_load,
                result.tile_ambiguity,
                result.solution_fragility,
            ),
        )
        self.conn.commit()
        return puzzle_id

    def draw(
        self,
        difficulty: str,
        exclude_ids: list[str] | None = None,
    ) -> tuple[PuzzleResult, str] | None:
        """Return a random unseen puzzle of the given difficulty.

        Returns ``None`` when the pool is empty or every stored puzzle
        has been excluded via *exclude_ids*.

        Args:
            difficulty:  Difficulty tier to draw from.
            exclude_ids: Puzzle UUIDs to skip (already seen by the client).
        """
        exclude = set(exclude_ids or [])
        rows = self.conn.execute(
            "SELECT * FROM puzzles WHERE difficulty = ? ORDER BY RANDOM()",
            (difficulty,),
        ).fetchall()
        for row in rows:
            if row["id"] not in exclude:
                return _deserialize_row(row), row["id"]
        return None

    def count(self, difficulty: str | None = None) -> int:
        """Return the number of stored puzzles, optionally filtered by difficulty."""
        if difficulty is not None:
            row = self.conn.execute(
                "SELECT COUNT(*) FROM puzzles WHERE difficulty = ?",
                (difficulty,),
            ).fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) FROM puzzles").fetchone()
        return int(row[0])

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self.conn.close()


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize_board(board_sets: list[TileSet]) -> str:
    return json.dumps(
        [
            {
                "type": ts.type.value,
                "tiles": [_tile_to_dict(t) for t in ts.tiles],
            }
            for ts in board_sets
        ]
    )


def _serialize_rack(rack: list[Tile]) -> str:
    return json.dumps([_tile_to_dict(t) for t in rack])


def _tile_to_dict(tile: Tile) -> dict[str, Any]:
    return {
        "color": tile.color.value if tile.color is not None else None,
        "number": tile.number,
        "copy_id": tile.copy_id,
        "is_joker": tile.is_joker,
    }


def _dict_to_tile(d: dict[str, Any]) -> Tile:
    if d["is_joker"]:
        return Tile.joker(copy_id=int(d["copy_id"]))
    return Tile(
        color=Color(d["color"]),
        number=int(d["number"]),
        copy_id=int(d["copy_id"]),
    )


def _deserialize_row(row: sqlite3.Row) -> PuzzleResult:
    board_data: list[Any] = json.loads(row["board_json"])
    board_sets = [
        TileSet(
            type=SetType(bs["type"]),
            tiles=[_dict_to_tile(t) for t in bs["tiles"]],
        )
        for bs in board_data
    ]
    rack = [_dict_to_tile(t) for t in json.loads(row["rack_json"])]
    return PuzzleResult(
        board_sets=board_sets,
        rack=rack,
        difficulty=row["difficulty"],
        disruption_score=row["disruption"],
        seed=int(row["seed"]) if "seed" in row.keys() and row["seed"] is not None else None,
        chain_depth=row["chain_depth"],
        is_unique=bool(row["is_unique"]),
        joker_count=row["joker_count"],
        # sqlite3.Row.__contains__ tests VALUES, not column names; use .keys().
        generator_version=row["generator_version"] if "generator_version" in row.keys() else "v1",  # noqa: SIM401,SIM118
        composite_score=float(row["composite_score"]) if "composite_score" in row.keys() else 0.0,  # noqa: SIM401,SIM118
        branching_factor=(
            float(row["branching_factor"]) if "branching_factor" in row.keys() else 0.0  # noqa: SIM401,SIM118
        ),
        deductive_depth=(
            float(row["deductive_depth"]) if "deductive_depth" in row.keys() else 0.0  # noqa: SIM401,SIM118
        ),
        red_herring_density=(
            float(row["red_herring_density"]) if "red_herring_density" in row.keys() else 0.0  # noqa: SIM401,SIM118
        ),
        working_memory_load=(
            float(row["working_memory_load"]) if "working_memory_load" in row.keys() else 0.0  # noqa: SIM401,SIM118
        ),
        tile_ambiguity=(
            float(row["tile_ambiguity"]) if "tile_ambiguity" in row.keys() else 0.0  # noqa: SIM401,SIM118
        ),
        solution_fragility=(
            float(row["solution_fragility"]) if "solution_fragility" in row.keys() else 0.0  # noqa: SIM401,SIM118
        ),
    )
