"""SQLite-backed event storage for play-mode telemetry."""

from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import suppress
from pathlib import Path

from .puzzle_store import DEFAULT_DB_PATH

DEFAULT_TELEMETRY_DB_PATH = Path(os.getenv("PUZZLE_DB_PATH", str(DEFAULT_DB_PATH)))

_CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS telemetry_events (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        event_type TEXT NOT NULL,
        event_at TEXT NOT NULL,
        puzzle_id TEXT NOT NULL,
        attempt_id TEXT NOT NULL DEFAULT '',
        difficulty TEXT NOT NULL,
        seed INTEGER,
        batch_name TEXT,
        batch_index INTEGER,
        generator_version TEXT NOT NULL,
        composite_score REAL NOT NULL,
        branching_factor REAL NOT NULL,
        deductive_depth REAL NOT NULL,
        red_herring_density REAL NOT NULL,
        working_memory_load REAL NOT NULL,
        tile_ambiguity REAL NOT NULL,
        solution_fragility REAL NOT NULL,
        disruption_score INTEGER NOT NULL,
        chain_depth INTEGER NOT NULL,
        tile_color TEXT,
        tile_number INTEGER,
        tile_joker INTEGER,
        from_row INTEGER,
        from_col INTEGER,
        to_row INTEGER,
        to_col INTEGER,
        elapsed_ms INTEGER,
        move_count INTEGER,
        undo_count INTEGER,
        redo_count INTEGER,
        commit_count INTEGER,
        revert_count INTEGER,
        tiles_placed INTEGER,
        tiles_remaining INTEGER,
        self_rating INTEGER,
        self_label TEXT,
        stuck_moments INTEGER,
        notes TEXT
    )
"""

_MIGRATION_COLUMNS: list[tuple[str, str]] = [
    ("seed", "INTEGER"),
    ("attempt_id", "TEXT NOT NULL DEFAULT ''"),
    ("batch_name", "TEXT"),
    ("batch_index", "INTEGER"),
    ("tiles_placed", "INTEGER"),
    ("tiles_remaining", "INTEGER"),
    ("self_rating", "INTEGER"),
    ("self_label", "TEXT"),
    ("stuck_moments", "INTEGER"),
    ("notes", "TEXT"),
]


class TelemetryStore:
    """Persist telemetry events in the puzzle DB under a separate table."""

    def __init__(self, db_path: Path = DEFAULT_TELEMETRY_DB_PATH) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.execute(_CREATE_TABLE)
        for col_name, col_def in _MIGRATION_COLUMNS:
            with suppress(sqlite3.OperationalError):
                self.conn.execute(f"ALTER TABLE telemetry_events ADD COLUMN {col_name} {col_def}")
        self.conn.commit()

    def store(self, event: dict[str, object]) -> str:
        # A user can re-rate a puzzle; keep only the latest rating per attempt.
        if event.get("event_type") == "puzzle_rated":
            self.conn.execute(
                "DELETE FROM telemetry_events WHERE attempt_id=? AND event_type='puzzle_rated'",
                (event.get("attempt_id", ""),),
            )

        event_id = str(uuid.uuid4())
        tile = event.get("tile")
        self.conn.execute(
            """INSERT INTO telemetry_events (
                id, event_type, event_at, puzzle_id, attempt_id, difficulty, seed,
                batch_name, batch_index, generator_version,
                composite_score, branching_factor, deductive_depth, red_herring_density,
                working_memory_load, tile_ambiguity, solution_fragility,
                disruption_score, chain_depth, tile_color, tile_number, tile_joker,
                from_row, from_col, to_row, to_col, elapsed_ms, move_count,
                undo_count, redo_count, commit_count, revert_count,
                tiles_placed, tiles_remaining, self_rating, self_label, stuck_moments, notes
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )""",
            (
                event_id,
                event["event_type"],
                event["event_at"],
                event["puzzle_id"],
                event.get("attempt_id", ""),
                event["difficulty"],
                event.get("seed"),
                event.get("batch_name"),
                event.get("batch_index"),
                event["generator_version"],
                event["composite_score"],
                event["branching_factor"],
                event["deductive_depth"],
                event["red_herring_density"],
                event["working_memory_load"],
                event["tile_ambiguity"],
                event["solution_fragility"],
                event["disruption_score"],
                event["chain_depth"],
                tile["color"] if isinstance(tile, dict) else None,
                tile["number"] if isinstance(tile, dict) else None,
                int(bool(tile["joker"])) if isinstance(tile, dict) else None,
                event.get("from_row"),
                event.get("from_col"),
                event.get("to_row"),
                event.get("to_col"),
                event.get("elapsed_ms"),
                event.get("move_count"),
                event.get("undo_count"),
                event.get("redo_count"),
                event.get("commit_count"),
                event.get("revert_count"),
                event.get("tiles_placed"),
                event.get("tiles_remaining"),
                event.get("self_rating"),
                event.get("self_label"),
                event.get("stuck_moments"),
                event.get("notes"),
            ),
        )
        self.conn.commit()
        return event_id

    def count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) FROM telemetry_events").fetchone()
        return int(row[0])

    def close(self) -> None:
        self.conn.close()
