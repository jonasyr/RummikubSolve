"""Export telemetry events from SQLite to CSV for calibration analysis."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

from .telemetry_store import DEFAULT_TELEMETRY_DB_PATH

_COLUMNS = [
    "created_at",
    "event_type",
    "event_at",
    "puzzle_id",
    "attempt_id",
    "difficulty",
    "seed",
    "batch_name",
    "batch_index",
    "generator_version",
    "composite_score",
    "branching_factor",
    "deductive_depth",
    "red_herring_density",
    "working_memory_load",
    "tile_ambiguity",
    "solution_fragility",
    "disruption_score",
    "chain_depth",
    "elapsed_ms",
    "move_count",
    "undo_count",
    "redo_count",
    "commit_count",
    "revert_count",
    "tiles_placed",
    "tiles_remaining",
    "self_rating",
    "self_label",
    "stuck_moments",
    "notes",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_TELEMETRY_DB_PATH)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--event-type", type=str, default=None)
    parser.add_argument("--difficulty", type=str, default=None)
    parser.add_argument("--generator-version", type=str, default=None)
    parser.add_argument("--batch-name", type=str, default=None)
    parser.add_argument("--solved-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    where: list[str] = []
    params: list[object] = []
    if args.solved_only:
        where.append("event_type = ?")
        params.append("puzzle_solved")
    elif args.event_type:
        where.append("event_type = ?")
        params.append(args.event_type)
    if args.difficulty:
        where.append("difficulty = ?")
        params.append(args.difficulty)
    if args.generator_version:
        where.append("generator_version = ?")
        params.append(args.generator_version)
    if args.batch_name:
        where.append("batch_name = ?")
        params.append(args.batch_name)

    query = f"SELECT {', '.join(_COLUMNS)} FROM telemetry_events"
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY created_at, id"

    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row[column] for column in _COLUMNS})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
