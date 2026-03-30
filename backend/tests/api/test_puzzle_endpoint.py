"""FastAPI integration tests for POST /api/puzzle."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from solver.generator.puzzle_generator import (
    _MIN_CHAIN_DEPTHS,  # type: ignore[attr-defined]
    generate_puzzle,
)


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


async def test_custom_sets_to_remove_nine_422(client: AsyncClient) -> None:
    """sets_to_remove max is now 8; 9 must still be rejected."""
    r = await client.post("/api/puzzle", json={"difficulty": "custom", "sets_to_remove": 9})
    assert r.status_code == 422


async def test_expert_puzzle_200(client: AsyncClient) -> None:
    r = await client.post("/api/puzzle", json={"difficulty": "expert", "seed": 20})
    assert r.status_code == 200
    data = r.json()
    assert data["difficulty"] == "expert"
    assert 6 <= len(data["rack"]) <= 10
    assert len(data["board_sets"]) >= 2
    assert data["disruption_score"] >= 32  # Expert floor


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
        assert 10 <= len(data["rack"]) <= 14
        assert isinstance(data["is_unique"], bool)  # informational; may be True or False
        assert data["chain_depth"] >= _MIN_CHAIN_DEPTHS["nightmare"]


# ---------------------------------------------------------------------------
# Phase 5: seen_ids, puzzle_id, and pool integration
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _pool_result():  # type: ignore[return]
    """A medium PuzzleResult reused across Phase-5 pool mock tests."""
    return generate_puzzle(difficulty="medium", seed=1)


class TestSeenIdsValidation:
    """seen_ids is accepted in PuzzleRequest and validated."""

    async def test_seen_ids_absent_ok(self, client: AsyncClient) -> None:
        r = await client.post("/api/puzzle", json={"difficulty": "easy", "seed": 1})
        assert r.status_code == 200

    async def test_seen_ids_empty_list_ok(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/puzzle", json={"difficulty": "easy", "seed": 1, "seen_ids": []}
        )
        assert r.status_code == 200

    async def test_seen_ids_with_strings(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/puzzle",
            json={"difficulty": "easy", "seed": 1, "seen_ids": ["abc", "def"]},
        )
        assert r.status_code == 200

    async def test_seen_ids_too_many_422(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/puzzle",
            json={"difficulty": "easy", "seen_ids": [str(i) for i in range(501)]},
        )
        assert r.status_code == 422


class TestPuzzleIdField:
    """puzzle_id is present in all responses; empty for live-generated puzzles."""

    async def test_puzzle_id_present_in_response(self, client: AsyncClient) -> None:
        r = await client.post("/api/puzzle", json={"difficulty": "easy", "seed": 1})
        assert r.status_code == 200
        assert "puzzle_id" in r.json()

    async def test_easy_puzzle_id_is_empty(self, client: AsyncClient) -> None:
        r = await client.post("/api/puzzle", json={"difficulty": "easy", "seed": 1})
        assert r.status_code == 200
        assert r.json()["puzzle_id"] == ""

    async def test_medium_puzzle_id_is_empty(self, client: AsyncClient) -> None:
        r = await client.post("/api/puzzle", json={"difficulty": "medium", "seed": 2})
        assert r.status_code == 200
        assert r.json()["puzzle_id"] == ""

    async def test_hard_puzzle_id_is_empty(self, client: AsyncClient) -> None:
        r = await client.post("/api/puzzle", json={"difficulty": "hard", "seed": 3})
        assert r.status_code == 200
        assert r.json()["puzzle_id"] == ""


class TestPoolIntegration:
    """Pool draw / fallback logic via monkeypatched PuzzleStore."""

    async def test_expert_draws_from_pool_when_available(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch, _pool_result: object
    ) -> None:
        """When store.draw() returns a result, response.puzzle_id is its UUID."""
        fake_id = "aaaabbbb-1111-1111-1111-000000000001"
        mock_store = MagicMock()
        mock_store.draw.return_value = (_pool_result, fake_id)
        monkeypatch.setattr("api.main.PuzzleStore", lambda *a, **kw: mock_store)

        r = await client.post("/api/puzzle", json={"difficulty": "expert"})
        assert r.status_code == 200
        assert r.json()["puzzle_id"] == fake_id

    async def test_expert_fallback_when_pool_empty(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When store.draw() returns None, live generation is used and puzzle_id is ''."""
        mock_store = MagicMock()
        mock_store.draw.return_value = None
        monkeypatch.setattr("api.main.PuzzleStore", lambda *a, **kw: mock_store)

        r = await client.post("/api/puzzle", json={"difficulty": "expert", "seed": 42})
        assert r.status_code == 200
        assert r.json()["puzzle_id"] == ""

    async def test_seen_ids_forwarded_to_store(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch, _pool_result: object
    ) -> None:
        """seen_ids from the request are forwarded as exclude_ids to store.draw()."""
        fake_id = "aaaabbbb-2222-2222-2222-000000000002"
        seen = ["old-uuid-1", "old-uuid-2"]
        mock_store = MagicMock()
        mock_store.draw.return_value = (_pool_result, fake_id)
        monkeypatch.setattr("api.main.PuzzleStore", lambda *a, **kw: mock_store)

        r = await client.post(
            "/api/puzzle", json={"difficulty": "expert", "seen_ids": seen}
        )
        assert r.status_code == 200
        mock_store.draw.assert_called_once_with("expert", exclude_ids=seen)

    async def test_nightmare_uses_pool(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch, _pool_result: object
    ) -> None:
        """Nightmare difficulty also goes through the pool path."""
        mock_store = MagicMock()
        mock_store.draw.return_value = (_pool_result, "some-uuid")
        monkeypatch.setattr("api.main.PuzzleStore", lambda *a, **kw: mock_store)

        r = await client.post("/api/puzzle", json={"difficulty": "nightmare"})
        assert r.status_code == 200
        assert r.json()["puzzle_id"] == "some-uuid"

    async def test_easy_does_not_use_pool(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Easy difficulty bypasses the pool entirely — PuzzleStore is never instantiated."""
        mock_store = MagicMock()
        monkeypatch.setattr("api.main.PuzzleStore", lambda *a, **kw: mock_store)

        r = await client.post("/api/puzzle", json={"difficulty": "easy", "seed": 1})
        assert r.status_code == 200
        mock_store.draw.assert_not_called()


# ---------------------------------------------------------------------------
# Phase 7a: Custom mode — new generation parameters
# ---------------------------------------------------------------------------


async def test_custom_min_chain_depth_respected(client: AsyncClient) -> None:
    """min_chain_depth=1 is honoured: returned puzzle has chain_depth >= 1."""
    r = await client.post(
        "/api/puzzle", json={"difficulty": "custom", "seed": 5, "min_chain_depth": 1}
    )
    assert r.status_code == 200
    assert r.json()["chain_depth"] >= 1


async def test_custom_min_disruption_respected(client: AsyncClient) -> None:
    """min_disruption=10 is honoured: returned disruption_score >= 10."""
    r = await client.post(
        "/api/puzzle", json={"difficulty": "custom", "seed": 6, "min_disruption": 10}
    )
    assert r.status_code == 200
    assert r.json()["disruption_score"] >= 10


async def test_custom_board_size_params_accepted(client: AsyncClient) -> None:
    """Explicit min/max_board_sets are accepted and produce a valid puzzle."""
    r = await client.post(
        "/api/puzzle",
        json={"difficulty": "custom", "seed": 7, "min_board_sets": 7, "max_board_sets": 10},
    )
    assert r.status_code == 200
    assert r.json()["difficulty"] == "custom"


async def test_custom_sets_to_remove_eight_ok(client: AsyncClient) -> None:
    """sets_to_remove=8 is valid after range was expanded from 5 to 8."""
    r = await client.post(
        "/api/puzzle",
        json={
            "difficulty": "custom",
            "seed": 8,
            "sets_to_remove": 8,
            "min_board_sets": 12,
            "max_board_sets": 20,
        },
    )
    assert r.status_code == 200


async def test_custom_is_unique_field_present(client: AsyncClient) -> None:
    """Custom puzzles always include is_unique (computed, never enforced)."""
    r = await client.post("/api/puzzle", json={"difficulty": "custom", "seed": 4})
    assert r.status_code == 200
    assert "is_unique" in r.json()
    assert isinstance(r.json()["is_unique"], bool)
