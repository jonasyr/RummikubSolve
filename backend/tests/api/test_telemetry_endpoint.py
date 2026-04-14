"""Tests for telemetry endpoint validation and persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from api.main import telemetry_endpoint
from api.models import TelemetryRequest
from solver.generator.telemetry_store import TelemetryStore


def _payload() -> dict[str, object]:
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
        "elapsed_ms": 12345,
        "move_count": 9,
        "undo_count": 2,
        "redo_count": 1,
        "commit_count": 1,
        "revert_count": 0,
    }


def test_telemetry_200_and_persists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "telemetry.db"
    monkeypatch.setattr("api.main.TelemetryStore", lambda: TelemetryStore(db))

    response = telemetry_endpoint(TelemetryRequest(**_payload()))
    assert response.status == "ok"

    store = TelemetryStore(db)
    assert store.count() == 1
    row = store.conn.execute(
        "SELECT seed, generator_version FROM telemetry_events"
    ).fetchone()
    assert row["seed"] == 123
    assert row["generator_version"] == "v2.0.0"
    store.close()


def test_telemetry_422_on_missing_required_solved_fields() -> None:
    payload = _payload()
    payload.pop("elapsed_ms")
    with pytest.raises(ValueError):
        TelemetryRequest(**payload)


def test_telemetry_accepts_abandoned_payload() -> None:
    payload = _payload()
    payload.update(
        {
            "event_type": "puzzle_abandoned",
            "elapsed_ms": 5000,
            "tiles_placed": 2,
            "tiles_remaining": 3,
        }
    )
    assert TelemetryRequest(**payload).event_type == "puzzle_abandoned"


def test_telemetry_accepts_rating_payload() -> None:
    payload = _payload()
    payload.update(
        {
            "event_type": "puzzle_rated",
            "self_rating": 8,
            "self_label": "challenging",
            "stuck_moments": 2,
            "notes": "Needed one key insight.",
        }
    )
    assert TelemetryRequest(**payload).event_type == "puzzle_rated"
