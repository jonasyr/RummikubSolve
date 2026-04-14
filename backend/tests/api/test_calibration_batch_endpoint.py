"""Tests for calibration batch manifest loading."""

from __future__ import annotations

from api.main import calibration_batch_endpoint


def test_calibration_batch_endpoint_returns_phase6_batch() -> None:
    response = calibration_batch_endpoint("phase6_batch_v1")
    assert response.batch_name == "phase6_batch_v1"
    assert len(response.entries) == 25
    assert response.entries[0].difficulty == "easy"
    assert response.entries[0].seed == 1001
    assert response.entries[-1].difficulty == "nightmare"
    assert response.entries[-1].seed == 5005
