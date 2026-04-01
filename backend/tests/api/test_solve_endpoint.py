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


# ---------------------------------------------------------------------------
# Phase UI-1: set_changes field — integration tests
# ---------------------------------------------------------------------------


async def test_set_changes_present_in_response(client: AsyncClient) -> None:
    """set_changes key is always present in the response body."""
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
    assert "set_changes" in data
    assert isinstance(data["set_changes"], list)


async def test_set_changes_count_matches_new_board_count(client: AsyncClient) -> None:
    """len(set_changes) == len(new_board) for every solve."""
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
    assert len(data["set_changes"]) == len(data["new_board"])


async def test_set_changes_new_action_all_hand_origins(client: AsyncClient) -> None:
    """When all tiles come from the rack, action='new' and all origins are 'hand'."""
    r = await client.post(
        "/api/solve",
        json={
            "rack": [
                {"color": "blue", "number": 7},
                {"color": "blue", "number": 8},
                {"color": "blue", "number": 9},
            ]
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "solved"
    new_changes = [c for c in data["set_changes"] if c["action"] == "new"]
    assert len(new_changes) >= 1
    for sc in new_changes:
        assert all(tile["origin"] == "hand" for tile in sc["result_set"]["tiles"])
        assert sc["source_set_indices"] is None
        assert sc["source_description"] is None


async def test_set_changes_extended_has_mixed_origins(client: AsyncClient) -> None:
    """An extend scenario produces action='extended' with board and hand origins."""
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
    extended = [c for c in data["set_changes"] if c["action"] == "extended"]
    assert len(extended) >= 1
    sc = extended[0]
    origins = [tile["origin"] for tile in sc["result_set"]["tiles"]]
    assert "hand" in origins
    board_origins = [o for o in origins if o != "hand"]
    assert len(board_origins) > 0  # some tiles from board
    assert sc["source_set_indices"] == [0]


async def test_set_changes_extended_source_index_correct_for_second_set(
    client: AsyncClient,
) -> None:
    """source_set_indices points to the correct old-set index when it's not set 0."""
    r = await client.post(
        "/api/solve",
        json={
            "board": [
                {
                    "type": "run",
                    "tiles": [
                        {"color": "blue", "number": 1},
                        {"color": "blue", "number": 2},
                        {"color": "blue", "number": 3},
                    ],
                },
                {
                    "type": "run",
                    "tiles": [
                        {"color": "red", "number": 4},
                        {"color": "red", "number": 5},
                        {"color": "red", "number": 6},
                    ],
                },
            ],
            "rack": [{"color": "red", "number": 7}],
        },
    )
    assert r.status_code == 200
    data = r.json()
    extended = [c for c in data["set_changes"] if c["action"] == "extended"]
    assert len(extended) >= 1
    # The extended set must reference board set index 1 (the Red run).
    assert extended[0]["source_set_indices"] == [1]


async def test_set_changes_unchanged_action_present(client: AsyncClient) -> None:
    """An untouched board set appears as action='unchanged' in set_changes."""
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
            "rack": [
                {"color": "blue", "number": 7},
                {"color": "blue", "number": 8},
                {"color": "blue", "number": 9},
            ],
        },
    )
    assert r.status_code == 200
    data = r.json()
    unchanged = [c for c in data["set_changes"] if c["action"] == "unchanged"]
    assert len(unchanged) >= 1
    sc = unchanged[0]
    assert sc["source_set_indices"] is None
    assert sc["source_description"] is None
    # All tile origins are int (board set indices), never "hand"
    assert all(tile["origin"] != "hand" for tile in sc["result_set"]["tiles"])


async def test_set_changes_unchanged_tile_origins_are_ints(client: AsyncClient) -> None:
    """Origins in an unchanged set are board-set indices (integers), not 'hand'."""
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
            "rack": [
                {"color": "blue", "number": 7},
                {"color": "blue", "number": 8},
                {"color": "blue", "number": 9},
            ],
        },
    )
    data = r.json()
    unchanged = [c for c in data["set_changes"] if c["action"] == "unchanged"]
    for sc in unchanged:
        for tile in sc["result_set"]["tiles"]:
            assert isinstance(tile["origin"], int)


async def test_moves_still_present_for_backward_compatibility(client: AsyncClient) -> None:
    """moves[] is preserved alongside set_changes for backward compatibility."""
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
    assert "moves" in data
    assert isinstance(data["moves"], list)
    assert len(data["moves"]) > 0


async def test_no_solution_has_empty_set_changes(client: AsyncClient) -> None:
    """A no_solution response has an empty set_changes list."""
    r = await client.post(
        "/api/solve",
        json={"rack": [{"color": "red", "number": 1}, {"color": "red", "number": 2}]},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "no_solution"
    assert data["set_changes"] == []


async def test_set_changes_result_set_type_is_run_or_group(client: AsyncClient) -> None:
    """result_set.type is always 'run' or 'group' for every set_change."""
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
            "rack": [
                {"color": "red", "number": 7},
                {"color": "blue", "number": 1},
                {"color": "blue", "number": 2},
                {"color": "blue", "number": 3},
            ],
        },
    )
    assert r.status_code == 200
    data = r.json()
    for sc in data["set_changes"]:
        assert sc["result_set"]["type"] in ("run", "group")


async def test_set_changes_tiles_have_origin_field(client: AsyncClient) -> None:
    """Every tile in every set_change has an 'origin' field that is 'hand' or int."""
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
    for sc in data["set_changes"]:
        for tile in sc["result_set"]["tiles"]:
            assert "origin" in tile
            assert tile["origin"] == "hand" or isinstance(tile["origin"], int)


async def test_set_changes_tiles_include_standard_tile_fields(
    client: AsyncClient,
) -> None:
    """Every tile in set_changes also carries the standard TileOutput fields."""
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
    for sc in data["set_changes"]:
        for tile in sc["result_set"]["tiles"]:
            assert "color" in tile
            assert "number" in tile
            assert "joker" in tile
            assert "copy_id" in tile
            assert "origin" in tile
