"""SQLite-backed event storage for play-mode telemetry."""

from __future__ import annotations

import os
import sqlite3
import uuid
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
        difficulty TEXT NOT NULL,
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
        revert_count INTEGER
    )
"""


class TelemetryStore:
    """Persist telemetry events in the puzzle DB under a separate table."""

    def __init__(self, db_path: Path = DEFAULT_TELEMETRY_DB_PATH) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.execute(_CREATE_TABLE)
        self.conn.commit()

    def store(self, event: dict[str, object]) -> str:
        event_id = str(uuid.uuid4())
        tile = event.get("tile")
        self.conn.execute(
            """INSERT INTO telemetry_events (
                id, event_type, event_at, puzzle_id, difficulty, generator_version,
                composite_score, branching_factor, deductive_depth, red_herring_density,
                working_memory_load, tile_ambiguity, solution_fragility,
                disruption_score, chain_depth, tile_color, tile_number, tile_joker,
                from_row, from_col, to_row, to_col, elapsed_ms, move_count,
                undo_count, redo_count, commit_count, revert_count
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )""",
            (
                event_id,
                event["event_type"],
                event["event_at"],
                event["puzzle_id"],
                event["difficulty"],
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
            ),
        )
        self.conn.commit()
        return event_id

    def count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) FROM telemetry_events").fetchone()
        return int(row[0])

    def close(self) -> None:
        self.conn.close()
