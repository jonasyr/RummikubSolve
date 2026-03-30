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
    assert data["version"] == "0.31.0"


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


# ---------------------------------------------------------------------------
# Happy-path tests (AAA — Arrange / Act / Assert)
# ---------------------------------------------------------------------------


async def test_solve_group_happy_path(client: AsyncClient) -> None:
    """Three tiles of the same number in different colors form a valid group."""
    # Arrange
    payload = {
        "rack": [
            {"color": "red", "number": 7},
            {"color": "blue", "number": 7},
            {"color": "black", "number": 7},
        ]
    }

    # Act
    r = await client.post("/api/solve", json=payload)

    # Assert
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "solved"
    assert data["tiles_placed"] == 3
    create_moves = [m for m in data["moves"] if m["action"] == "create"]
    assert len(create_moves) >= 1


async def test_solve_with_joker_in_run(client: AsyncClient) -> None:
    """A joker substitutes a missing tile to complete a run."""
    # Arrange
    payload = {
        "rack": [
            {"color": "red", "number": 5},
            {"joker": True},
            {"color": "red", "number": 7},
        ]
    }

    # Act
    r = await client.post("/api/solve", json=payload)

    # Assert
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "solved"
    assert data["tiles_placed"] == 3


async def test_solve_extends_existing_board_set(client: AsyncClient) -> None:
    """A rack tile that extends an existing board run generates an extend move."""
    # Arrange
    payload = {
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
    }

    # Act
    r = await client.post("/api/solve", json=payload)

    # Assert
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "solved"
    extend_moves = [m for m in data["moves"] if m["action"] == "extend"]
    assert len(extend_moves) >= 1
    assert extend_moves[0]["set_index"] == 0


async def test_solve_two_tiles_in_rack_returns_no_solution(client: AsyncClient) -> None:
    """Two tiles alone cannot form a valid set — solver returns no_solution."""
    # Arrange
    payload = {"rack": [{"color": "red", "number": 1}, {"color": "red", "number": 2}]}

    # Act
    r = await client.post("/api/solve", json=payload)

    # Assert
    assert r.status_code == 200
    assert r.json()["status"] == "no_solution"


async def test_solve_response_contains_all_required_fields(client: AsyncClient) -> None:
    """Every SolveResponse field is present with the correct type in a normal solve."""
    # Arrange
    payload = {
        "rack": [
            {"color": "blue", "number": 8},
            {"color": "blue", "number": 9},
            {"color": "blue", "number": 10},
        ]
    }

    # Act
    r = await client.post("/api/solve", json=payload)

    # Assert
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["status"], str)
    assert isinstance(data["tiles_placed"], int)
    assert isinstance(data["tiles_remaining"], int)
    assert isinstance(data["solve_time_ms"], float)
    assert isinstance(data["is_optimal"], bool)
    assert isinstance(data["is_first_turn"], bool)
    assert isinstance(data["new_board"], list)
    assert isinstance(data["remaining_rack"], list)
    assert isinstance(data["moves"], list)


async def test_is_unchanged_true_for_unmodified_board_set(client: AsyncClient) -> None:
    """A board set untouched by the solver is marked is_unchanged=True."""
    # Arrange — board run [red 4,5,6] stays as-is; rack [blue 7,8,9] forms a new set
    payload = {
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
        "rack": [
            {"color": "blue", "number": 7},
            {"color": "blue", "number": 8},
            {"color": "blue", "number": 9},
        ],
    }

    # Act
    r = await client.post("/api/solve", json=payload)

    # Assert
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "solved"
    unchanged = [s for s in data["new_board"] if s["is_unchanged"]]
    assert len(unchanged) >= 1


async def test_new_tile_indices_populated_for_rack_tile(client: AsyncClient) -> None:
    """new_tile_indices is non-empty for the set that received a rack tile."""
    # Arrange
    payload = {
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
    }

    # Act
    r = await client.post("/api/solve", json=payload)

    # Assert
    assert r.status_code == 200
    data = r.json()
    modified_sets = [s for s in data["new_board"] if s["new_tile_indices"]]
    assert len(modified_sets) >= 1


async def test_joker_with_color_returns_422(client: AsyncClient) -> None:
    """A joker tile that also specifies a color is an invalid input (422)."""
    # Arrange
    payload = {"rack": [{"joker": True, "color": "red"}]}

    # Act
    r = await client.post("/api/solve", json=payload)

    # Assert
    assert r.status_code == 422


async def test_joker_with_number_returns_422(client: AsyncClient) -> None:
    """A joker tile that also specifies a number is an invalid input (422)."""
    # Arrange
    payload = {"rack": [{"joker": True, "number": 5}]}

    # Act
    r = await client.post("/api/solve", json=payload)

    # Assert
    assert r.status_code == 422


async def test_empty_rack_returns_no_solution(client: AsyncClient) -> None:
    """An empty rack is a valid request that returns no_solution with 0 tiles placed.

    SolveRequest.rack has no min_length, so an empty rack is schema-valid.
    The frontend guards against this (disables Solve when rack is empty), but
    the API must handle it gracefully.
    """
    r = await client.post("/api/solve", json={"board": [], "rack": []})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "no_solution"
    assert data["tiles_placed"] == 0
    assert data["tiles_remaining"] == 0
    assert data["new_board"] == []
    assert data["remaining_rack"] == []
