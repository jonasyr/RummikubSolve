"""Tests for telemetry event persistence."""

from __future__ import annotations

from pathlib import Path

from solver.generator.telemetry_store import TelemetryStore


def _sample_event() -> dict[str, object]:
    return {
        "event_type": "puzzle_solved",
        "event_at": "2026-04-13T12:00:00Z",
        "puzzle_id": "",
        "difficulty": "expert",
        "seed": 123,
        "generator_version": "v2.0.0",
        "composite_score": 55.5,
        "branching_factor": 3.0,
        "deductive_depth": 2.5,
        "red_herring_density": 0.2,
        "working_memory_load": 3.0,
        "tile_ambiguity": 4.0,
        "solution_fragility": 0.1,
        "disruption_score": 22,
        "chain_depth": 2,
        "tile": None,
        "from_row": None,
        "from_col": None,
        "to_row": None,
        "to_col": None,
        "elapsed_ms": 12345,
        "move_count": 9,
        "undo_count": 2,
        "redo_count": 1,
        "commit_count": 1,
        "revert_count": 0,
    }


def test_creates_db_file(tmp_path: Path) -> None:
    db = tmp_path / "telemetry.db"
    store = TelemetryStore(db)
    store.close()
    assert db.exists()


def test_store_increments_count(tmp_path: Path) -> None:
    store = TelemetryStore(tmp_path / "telemetry.db")
    assert store.count() == 0
    store.store(_sample_event())
    assert store.count() == 1
    row = store.conn.execute(
        "SELECT difficulty, seed, elapsed_ms FROM telemetry_events"
    ).fetchone()
    assert row["difficulty"] == "expert"
    assert row["seed"] == 123
    assert row["elapsed_ms"] == 12345
    store.close()
