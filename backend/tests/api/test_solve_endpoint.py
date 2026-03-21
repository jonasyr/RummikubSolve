"""FastAPI integration tests for /health and /api/solve.

Uses httpx.AsyncClient against the live ASGI app (no real network).
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app


@pytest.fixture
async def client() -> AsyncClient:  # type: ignore[misc]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_health(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.6.0"


async def test_solve_valid_run(client: AsyncClient) -> None:
    r = await client.post(
        "/api/solve",
        json={
            "rack": [
                {"color": "red", "number": 10},
                {"color": "red", "number": 11},
                {"color": "red", "number": 12},
            ]
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "solved"
    assert data["tiles_placed"] == 3
    assert data["is_optimal"] is True
    assert len(data["moves"]) > 0


async def test_solve_single_tile_returns_no_solution(client: AsyncClient) -> None:
    r = await client.post("/api/solve", json={"rack": [{"color": "red", "number": 5}]})
    assert r.status_code == 200
    assert r.json()["status"] in ("solved", "no_solution")


async def test_solve_invalid_tile_color_returns_422(client: AsyncClient) -> None:
    r = await client.post(
        "/api/solve",
        json={"rack": [{"color": "purple", "number": 5}]},
    )
    assert r.status_code == 422


async def test_solve_tile_number_out_of_range_returns_422(client: AsyncClient) -> None:
    r = await client.post(
        "/api/solve",
        json={"rack": [{"color": "red", "number": 14}]},
    )
    assert r.status_code == 422


async def test_solve_board_set_too_small_returns_422(client: AsyncClient) -> None:
    r = await client.post(
        "/api/solve",
        json={
            "board": [{"type": "run", "tiles": [{"color": "red", "number": 4}]}],
            "rack": [{"color": "red", "number": 5}],
        },
    )
    assert r.status_code == 422


async def test_solve_first_turn_above_threshold(client: AsyncClient) -> None:
    r = await client.post(
        "/api/solve",
        json={
            "rack": [
                {"color": "red", "number": 10},
                {"color": "red", "number": 11},
                {"color": "red", "number": 12},
            ],
            "rules": {"is_first_turn": True},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["tiles_placed"] == 3
    assert data["is_first_turn"] is True


async def test_solve_first_turn_below_threshold(client: AsyncClient) -> None:
    r = await client.post(
        "/api/solve",
        json={
            "rack": [
                {"color": "red", "number": 4},
                {"color": "red", "number": 5},
                {"color": "red", "number": 6},
            ],
            "rules": {"is_first_turn": True},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "no_solution"
    assert data["is_first_turn"] is True


async def test_solve_move_set_index_present(client: AsyncClient) -> None:
    """set_index must be serialised for 'extend' moves."""
    r = await client.post(
        "/api/solve",
        json={
            "board": [
                {
                    "type": "run",
                    "tiles": [
                        {"color": "red", "number": 4},
                        {"color": "red", "number": 5},
                        {"color": "red", "number": 6},
                    ],
                }
            ],
            "rack": [{"color": "red", "number": 7}],
        },
    )
    assert r.status_code == 200
    data = r.json()
    extend_moves = [m for m in data["moves"] if m["action"] == "extend"]
    assert len(extend_moves) == 1
    assert extend_moves[0]["set_index"] == 0
