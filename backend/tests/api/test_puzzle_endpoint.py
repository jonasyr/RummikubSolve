"""FastAPI integration tests for POST /api/puzzle."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from solver.generator.puzzle_generator import _MIN_CHAIN_DEPTHS  # type: ignore[attr-defined]


@pytest.fixture
async def client() -> AsyncClient:  # type: ignore[misc]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_easy_puzzle_200(client: AsyncClient) -> None:
    r = await client.post("/api/puzzle", json={"difficulty": "easy", "seed": 1})
    assert r.status_code == 200
    data = r.json()
    assert data["difficulty"] == "easy"
    assert len(data["rack"]) >= 2
    assert len(data["board_sets"]) >= 2


async def test_medium_puzzle_200(client: AsyncClient) -> None:
    r = await client.post("/api/puzzle", json={"difficulty": "medium", "seed": 2})
    assert r.status_code == 200
    data = r.json()
    assert data["difficulty"] == "medium"
    assert len(data["rack"]) >= 3
    assert len(data["board_sets"]) >= 2


async def test_hard_puzzle_200(client: AsyncClient) -> None:
    r = await client.post("/api/puzzle", json={"difficulty": "hard", "seed": 3})
    assert r.status_code == 200
    data = r.json()
    assert data["difficulty"] == "hard"
    assert 4 <= len(data["rack"]) <= 5


async def test_invalid_difficulty_422(client: AsyncClient) -> None:
    r = await client.post("/api/puzzle", json={"difficulty": "extreme"})
    assert r.status_code == 422


async def test_response_fields_present(client: AsyncClient) -> None:
    r = await client.post("/api/puzzle", json={"difficulty": "medium", "seed": 10})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["board_sets"], list)
    assert isinstance(data["rack"], list)
    assert isinstance(data["difficulty"], str)
    assert isinstance(data["tile_count"], int)
    assert data["tile_count"] == len(data["rack"])
    assert isinstance(data["disruption_score"], int)
    assert data["disruption_score"] >= 0


async def test_seeded_puzzle_is_deterministic(client: AsyncClient) -> None:
    r1 = await client.post("/api/puzzle", json={"difficulty": "medium", "seed": 42})
    r2 = await client.post("/api/puzzle", json={"difficulty": "medium", "seed": 42})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json() == r2.json()


async def test_default_difficulty_uses_medium(client: AsyncClient) -> None:
    """POST with empty body should use the default difficulty of 'medium'."""
    r = await client.post("/api/puzzle", json={})
    assert r.status_code == 200
    assert r.json()["difficulty"] == "medium"


async def test_board_set_min_tiles_count(client: AsyncClient) -> None:
    """Every board_set in the response must have at least 3 tiles (Rummikub minimum)."""
    r = await client.post("/api/puzzle", json={"difficulty": "hard", "seed": 7})
    assert r.status_code == 200
    for bs in r.json()["board_sets"]:
        assert len(bs["tiles"]) >= 3, f"Board set has only {len(bs['tiles'])} tiles: {bs}"


async def test_custom_puzzle_200(client: AsyncClient) -> None:
    r = await client.post(
        "/api/puzzle", json={"difficulty": "custom", "seed": 4, "sets_to_remove": 3}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["difficulty"] == "custom"
    # 3 sets removed → at least 9 tiles in rack.
    assert len(data["rack"]) >= 9
    assert len(data["board_sets"]) >= 2


async def test_custom_sets_to_remove_zero_422(client: AsyncClient) -> None:
    r = await client.post("/api/puzzle", json={"difficulty": "custom", "sets_to_remove": 0})
    assert r.status_code == 422


async def test_custom_sets_to_remove_six_422(client: AsyncClient) -> None:
    r = await client.post("/api/puzzle", json={"difficulty": "custom", "sets_to_remove": 6})
    assert r.status_code == 422


async def test_expert_puzzle_200(client: AsyncClient) -> None:
    r = await client.post("/api/puzzle", json={"difficulty": "expert", "seed": 20})
    assert r.status_code == 200
    data = r.json()
    assert data["difficulty"] == "expert"
    assert 2 <= len(data["rack"]) <= 6
    assert len(data["board_sets"]) >= 2
    assert data["disruption_score"] >= 26  # Expert floor


# ---------------------------------------------------------------------------
# Phase 3: new response fields (chain_depth, is_unique) + nightmare tier
# ---------------------------------------------------------------------------


class TestPuzzleResponseNewFields:
    """chain_depth and is_unique are present in all /api/puzzle responses."""

    async def test_easy_response_has_chain_depth(self, client: AsyncClient) -> None:
        r = await client.post("/api/puzzle", json={"difficulty": "easy", "seed": 1})
        assert r.status_code == 200
        data = r.json()
        assert "chain_depth" in data
        assert isinstance(data["chain_depth"], int)
        assert data["chain_depth"] >= 0

    async def test_easy_response_has_is_unique(self, client: AsyncClient) -> None:
        r = await client.post("/api/puzzle", json={"difficulty": "easy", "seed": 1})
        assert r.status_code == 200
        data = r.json()
        assert "is_unique" in data
        assert isinstance(data["is_unique"], bool)

    async def test_expert_response_chain_depth_and_unique(
        self, client: AsyncClient
    ) -> None:
        r = await client.post("/api/puzzle", json={"difficulty": "expert", "seed": 42})
        assert r.status_code == 200
        data = r.json()
        assert data["chain_depth"] >= _MIN_CHAIN_DEPTHS["expert"]
        assert isinstance(data["is_unique"], bool)  # informational; may be True or False

    async def test_nightmare_endpoint_all_fields(self, client: AsyncClient) -> None:
        """One call covers: 200 status, difficulty, rack size, is_unique, chain_depth."""
        r = await client.post("/api/puzzle", json={"difficulty": "nightmare", "seed": 99})
        assert r.status_code == 200
        data = r.json()
        assert data["difficulty"] == "nightmare"
        assert 5 <= len(data["rack"]) <= 7
        assert isinstance(data["is_unique"], bool)  # informational; may be True or False
        assert data["chain_depth"] >= _MIN_CHAIN_DEPTHS["nightmare"]
