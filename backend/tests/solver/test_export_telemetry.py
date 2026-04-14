"""Tests for telemetry CSV export."""

from __future__ import annotations

import csv
from pathlib import Path

from solver.generator.export_telemetry import main
from solver.generator.telemetry_store import TelemetryStore


def _sample_event(seed: int) -> dict[str, object]:
    return {
        "event_type": "puzzle_solved",
        "event_at": "2026-04-13T12:00:00Z",
        "puzzle_id": "",
        "difficulty": "expert",
        "seed": seed,
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


def test_export_solved_rows_to_csv(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "telemetry.db"
    out = tmp_path / "solved.csv"
    store = TelemetryStore(db)
    store.store(_sample_event(123))
    store.store({**_sample_event(456), "difficulty": "hard"})
    store.close()

    monkeypatch.setattr(
        "sys.argv",
        [
            "export_telemetry.py",
            "--db",
            str(db),
            "--out",
            str(out),
            "--solved-only",
            "--difficulty",
            "expert",
        ],
    )
    assert main() == 0

    with out.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 1
    assert rows[0]["difficulty"] == "expert"
    assert rows[0]["seed"] == "123"
    assert rows[0]["event_type"] == "puzzle_solved"
    assert rows[0]["generator_version"] == "v2.0.0"
