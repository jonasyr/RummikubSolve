"""FastAPI integration tests for POST /api/puzzle.

Fast tests (no mark): mock generate_puzzle + PuzzleStore — each < 1s.
Slow tests (@pytest.mark.slow): run the real solver to verify content shape / quality gates.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from solver.generator.puzzle_generator import PuzzleResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_result(
    difficulty: str = "medium", seed: int | None = None
) -> PuzzleResult:
    """Build a minimal PuzzleResult without running the solver."""
    return PuzzleResult(
        board_sets=[],
        rack=[],
        difficulty=difficulty,  # type: ignore[arg-type]
        disruption_score=10,
        seed=seed,
        chain_depth=1,
        is_unique=True,
        composite_score=25.0,
        branching_factor=2.0,
        deductive_depth=1.0,
        red_herring_density=0.0,
        working_memory_load=1.0,
        tile_ambiguity=2.0,
        solution_fragility=0.0,
        generator_version="v2.0.0",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:  # type: ignore[misc]
    """Real client — calls the actual solver. Use only for slow tests."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def fast_client() -> AsyncGenerator[AsyncClient, None]:  # type: ignore[misc]
    """Client with generate_puzzle and PuzzleStore mocked — no solver, < 1s per test."""
    mock_store = MagicMock()
    mock_store.draw.return_value = None
    mock_store.store.return_value = "fast-test-uuid"

    def _fake_generate(
        difficulty: str = "medium",
        seed: int | None = None,
        **_: object,
    ) -> PuzzleResult:
        return _make_fake_result(difficulty=difficulty, seed=seed)

    with (
        patch("api.main.generate_puzzle", side_effect=_fake_generate),
        patch("api.main.PuzzleStore", return_value=mock_store),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c


@pytest.fixture(scope="module")
def _pool_result() -> PuzzleResult:
    """Pre-built PuzzleResult for pool mock tests — seed=1 matches assertion in draw test."""
    return _make_fake_result(difficulty="medium", seed=1)


# ---------------------------------------------------------------------------
# Fast tests — schema / routing / field presence
# ---------------------------------------------------------------------------


async def test_invalid_difficulty_422(fast_client: AsyncClient) -> None:
    r = await fast_client.post("/api/puzzle", json={"difficulty": "extreme"})
    assert r.status_code == 422


async def test_custom_sets_to_remove_zero_422(fast_client: AsyncClient) -> None:
    r = await fast_client.post("/api/puzzle", json={"difficulty": "custom", "sets_to_remove": 0})
    assert r.status_code == 422


async def test_custom_sets_to_remove_nine_422(fast_client: AsyncClient) -> None:
    """sets_to_remove max is 8; 9 must be rejected."""
    r = await fast_client.post("/api/puzzle", json={"difficulty": "custom", "sets_to_remove": 9})
    assert r.status_code == 422


async def test_response_fields_present(fast_client: AsyncClient) -> None:
    r = await fast_client.post("/api/puzzle", json={"difficulty": "medium", "seed": 10})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["board_sets"], list)
    assert isinstance(data["rack"], list)
    assert isinstance(data["difficulty"], str)
    assert data["seed"] == 10
    assert isinstance(data["tile_count"], int)
    assert data["tile_count"] == len(data["rack"])
    assert isinstance(data["disruption_score"], int)
    assert data["disruption_score"] >= 0


async def test_default_difficulty_uses_medium(fast_client: AsyncClient) -> None:
    """POST with empty body should use the default difficulty of 'medium'."""
    r = await fast_client.post("/api/puzzle", json={})
    assert r.status_code == 200
    assert r.json()["difficulty"] == "medium"


async def test_custom_board_size_params_accepted(fast_client: AsyncClient) -> None:
    """Explicit min/max_board_sets are accepted and produce a valid puzzle."""
    r = await fast_client.post(
        "/api/puzzle",
        json={"difficulty": "custom", "seed": 7, "min_board_sets": 7, "max_board_sets": 10},
    )
    assert r.status_code == 200
    assert r.json()["difficulty"] == "custom"


async def test_custom_sets_to_remove_eight_ok(fast_client: AsyncClient) -> None:
    """sets_to_remove=8 is valid after range was expanded from 5 to 8."""
    r = await fast_client.post(
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


async def test_custom_is_unique_field_present(fast_client: AsyncClient) -> None:
    """Custom puzzles always include is_unique (computed, never enforced)."""
    r = await fast_client.post("/api/puzzle", json={"difficulty": "custom", "seed": 4})
    assert r.status_code == 200
    assert "is_unique" in r.json()
    assert isinstance(r.json()["is_unique"], bool)


async def test_response_has_v2_fields(fast_client: AsyncClient) -> None:
    """POST /api/puzzle returns the full v2 metric payload."""
    r = await fast_client.post("/api/puzzle", json={"difficulty": "medium", "seed": 55})
    assert r.status_code == 200
    data = r.json()
    assert "composite_score" in data, "composite_score missing from response"
    assert "branching_factor" in data, "branching_factor missing from response"
    assert "deductive_depth" in data, "deductive_depth missing from response"
    assert "red_herring_density" in data, "red_herring_density missing from response"
    assert "working_memory_load" in data, "working_memory_load missing from response"
    assert "tile_ambiguity" in data, "tile_ambiguity missing from response"
    assert "solution_fragility" in data, "solution_fragility missing from response"
    assert "generator_version" in data, "generator_version missing from response"
    assert isinstance(data["composite_score"], float)
    assert isinstance(data["branching_factor"], float)
    assert isinstance(data["deductive_depth"], float)
    assert isinstance(data["red_herring_density"], float)
    assert isinstance(data["working_memory_load"], float)
    assert isinstance(data["tile_ambiguity"], float)
    assert isinstance(data["solution_fragility"], float)
    assert data["composite_score"] >= 0.0
    assert data["branching_factor"] >= 0.0
    assert data["generator_version"] == "v2.0.0"
    assert "template_id" in data, "template_id missing from response"
    assert "template_version" in data, "template_version missing from response"
    assert data["template_id"] == "legacy"
    assert data["template_version"] == "0"


# ---------------------------------------------------------------------------
# Fast — Phase 3: chain_depth / is_unique field presence
# ---------------------------------------------------------------------------


class TestPuzzleResponseNewFields:
    """chain_depth and is_unique are present and typed correctly in all responses."""

    async def test_easy_response_has_chain_depth(self, fast_client: AsyncClient) -> None:
        r = await fast_client.post("/api/puzzle", json={"difficulty": "easy", "seed": 1})
        assert r.status_code == 200
        data = r.json()
        assert "chain_depth" in data
        assert isinstance(data["chain_depth"], int)
        assert data["chain_depth"] >= 0

    async def test_easy_response_has_is_unique(self, fast_client: AsyncClient) -> None:
        r = await fast_client.post("/api/puzzle", json={"difficulty": "easy", "seed": 1})
        assert r.status_code == 200
        data = r.json()
        assert "is_unique" in data
        assert isinstance(data["is_unique"], bool)

    async def test_expert_response_chain_depth_and_unique(
        self, fast_client: AsyncClient
    ) -> None:
        r = await fast_client.post("/api/puzzle", json={"difficulty": "expert", "seed": 42})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data["chain_depth"], int)
        assert data["chain_depth"] >= 0
        assert isinstance(data["is_unique"], bool)

    @pytest.mark.slow
    async def test_nightmare_endpoint_all_fields(self, client: AsyncClient) -> None:
        """One call covers: 200 status, difficulty, rack size, is_unique, chain_depth."""
        r = await client.post("/api/puzzle", json={"difficulty": "nightmare", "seed": 99})
        assert r.status_code == 200
        data = r.json()
        assert data["difficulty"] == "nightmare"
        assert 6 <= len(data["rack"]) <= 8
        assert isinstance(data["is_unique"], bool)
        assert isinstance(data["chain_depth"], int)
        assert data["chain_depth"] >= 0


# ---------------------------------------------------------------------------
# Fast — Phase 5: seen_ids validation
# ---------------------------------------------------------------------------


class TestSeenIdsValidation:
    """seen_ids is accepted in PuzzleRequest and validated."""

    async def test_seen_ids_absent_ok(self, fast_client: AsyncClient) -> None:
        r = await fast_client.post("/api/puzzle", json={"difficulty": "easy", "seed": 1})
        assert r.status_code == 200

    async def test_seen_ids_empty_list_ok(self, fast_client: AsyncClient) -> None:
        r = await fast_client.post(
            "/api/puzzle", json={"difficulty": "easy", "seed": 1, "seen_ids": []}
        )
        assert r.status_code == 200

    async def test_seen_ids_with_strings(self, fast_client: AsyncClient) -> None:
        r = await fast_client.post(
            "/api/puzzle",
            json={"difficulty": "easy", "seed": 1, "seen_ids": ["abc", "def"]},
        )
        assert r.status_code == 200

    async def test_seen_ids_too_many_422(self, fast_client: AsyncClient) -> None:
        r = await fast_client.post(
            "/api/puzzle",
            json={"difficulty": "easy", "seen_ids": [str(i) for i in range(501)]},
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Fast — Phase 5: puzzle_id field
# ---------------------------------------------------------------------------


class TestPuzzleIdField:
    """puzzle_id is present in all responses."""

    async def test_puzzle_id_present_in_response(self, fast_client: AsyncClient) -> None:
        r = await fast_client.post("/api/puzzle", json={"difficulty": "easy", "seed": 1})
        assert r.status_code == 200
        assert "puzzle_id" in r.json()

    async def test_easy_puzzle_id_is_nonempty(self, fast_client: AsyncClient) -> None:
        r = await fast_client.post("/api/puzzle", json={"difficulty": "easy", "seed": 1})
        assert r.status_code == 200
        assert r.json()["puzzle_id"] != ""

    async def test_medium_puzzle_id_is_nonempty(self, fast_client: AsyncClient) -> None:
        r = await fast_client.post("/api/puzzle", json={"difficulty": "medium", "seed": 2})
        assert r.status_code == 200
        assert r.json()["puzzle_id"] != ""

    async def test_hard_puzzle_id_is_nonempty(self, fast_client: AsyncClient) -> None:
        r = await fast_client.post("/api/puzzle", json={"difficulty": "hard", "seed": 3})
        assert r.status_code == 200
        assert r.json()["puzzle_id"] != ""

    async def test_seed_present_for_live_generated_puzzle(
        self, fast_client: AsyncClient
    ) -> None:
        r = await fast_client.post("/api/puzzle", json={"difficulty": "easy", "seed": 44})
        assert r.status_code == 200
        assert r.json()["seed"] == 44


# ---------------------------------------------------------------------------
# Fast — Phase 5: pool draw / fallback logic
# ---------------------------------------------------------------------------


class TestPoolIntegration:
    """Pool draw / fallback logic via monkeypatched PuzzleStore."""

    async def test_expert_draws_from_pool_when_available(
        self,
        fast_client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
        _pool_result: PuzzleResult,
    ) -> None:
        """When store.draw() returns a result, response.puzzle_id is its UUID."""
        fake_id = "aaaabbbb-1111-1111-1111-000000000001"
        mock_store = MagicMock()
        mock_store.draw.return_value = (_pool_result, fake_id)
        monkeypatch.setattr("api.main.PuzzleStore", lambda *a, **kw: mock_store)

        r = await fast_client.post("/api/puzzle", json={"difficulty": "expert"})
        assert r.status_code == 200
        assert r.json()["puzzle_id"] == fake_id
        assert r.json()["seed"] == 1

    async def test_expert_fallback_when_pool_empty(
        self, fast_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When pool is empty, live generation runs and the result is persisted."""
        mock_store = MagicMock()
        mock_store.draw.return_value = None
        mock_store.store.return_value = "test-live-expert-id"
        monkeypatch.setattr("api.main.PuzzleStore", lambda *a, **kw: mock_store)

        r = await fast_client.post("/api/puzzle", json={"difficulty": "expert", "seed": 42})
        assert r.status_code == 200
        assert r.json()["puzzle_id"] == "test-live-expert-id"

    async def test_seen_ids_forwarded_to_store(
        self,
        fast_client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
        _pool_result: PuzzleResult,
    ) -> None:
        """seen_ids from the request are forwarded as exclude_ids to store.draw()."""
        fake_id = "aaaabbbb-2222-2222-2222-000000000002"
        seen = ["old-uuid-1", "old-uuid-2"]
        mock_store = MagicMock()
        mock_store.draw.return_value = (_pool_result, fake_id)
        monkeypatch.setattr("api.main.PuzzleStore", lambda *a, **kw: mock_store)

        r = await fast_client.post(
            "/api/puzzle", json={"difficulty": "expert", "seen_ids": seen}
        )
        assert r.status_code == 200
        mock_store.draw.assert_called_once_with("expert", exclude_ids=seen)

    async def test_nightmare_uses_pool(
        self,
        fast_client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
        _pool_result: PuzzleResult,
    ) -> None:
        """Nightmare difficulty also goes through the pool path."""
        mock_store = MagicMock()
        mock_store.draw.return_value = (_pool_result, "some-uuid")
        monkeypatch.setattr("api.main.PuzzleStore", lambda *a, **kw: mock_store)

        r = await fast_client.post("/api/puzzle", json={"difficulty": "nightmare"})
        assert r.status_code == 200
        assert r.json()["puzzle_id"] == "some-uuid"

    async def test_easy_does_not_use_pool(
        self, fast_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Easy difficulty bypasses the pool draw — store.draw is never called."""
        mock_store = MagicMock()
        mock_store.store.return_value = "test-live-easy-id"
        monkeypatch.setattr("api.main.PuzzleStore", lambda *a, **kw: mock_store)

        r = await fast_client.post("/api/puzzle", json={"difficulty": "easy", "seed": 1})
        assert r.status_code == 200
        mock_store.draw.assert_not_called()


# ---------------------------------------------------------------------------
# Slow tests — real solver, content shape and quality gates
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_easy_puzzle_200(client: AsyncClient) -> None:
    r = await client.post("/api/puzzle", json={"difficulty": "easy", "seed": 1})
    assert r.status_code == 200
    data = r.json()
    assert data["difficulty"] == "easy"
    assert len(data["rack"]) >= 2
    assert len(data["board_sets"]) >= 2


@pytest.mark.slow
async def test_medium_puzzle_200(client: AsyncClient) -> None:
    r = await client.post("/api/puzzle", json={"difficulty": "medium", "seed": 2})
    assert r.status_code == 200
    data = r.json()
    assert data["difficulty"] == "medium"
    assert len(data["rack"]) >= 3
    assert len(data["board_sets"]) >= 2


@pytest.mark.slow
async def test_hard_puzzle_200(client: AsyncClient) -> None:
    r = await client.post("/api/puzzle", json={"difficulty": "hard", "seed": 3})
    assert r.status_code == 200
    data = r.json()
    assert data["difficulty"] == "hard"
    assert 4 <= len(data["rack"]) <= 5


@pytest.mark.slow
async def test_expert_puzzle_200(client: AsyncClient) -> None:
    r = await client.post("/api/puzzle", json={"difficulty": "expert", "seed": 20})
    assert r.status_code == 200
    data = r.json()
    assert data["difficulty"] == "expert"
    assert 5 <= len(data["rack"]) <= 7
    assert len(data["board_sets"]) >= 2
    assert data["disruption_score"] >= 0


@pytest.mark.slow
async def test_board_set_min_tiles_count(client: AsyncClient) -> None:
    """Every board_set in the response must have at least 1 tile."""
    r = await client.post("/api/puzzle", json={"difficulty": "hard", "seed": 7})
    assert r.status_code == 200
    for bs in r.json()["board_sets"]:
        assert len(bs["tiles"]) >= 1, f"Board set is empty: {bs}"


@pytest.mark.slow
async def test_seeded_puzzle_is_deterministic(client: AsyncClient) -> None:
    r1 = await client.post("/api/puzzle", json={"difficulty": "medium", "seed": 42})
    r2 = await client.post("/api/puzzle", json={"difficulty": "medium", "seed": 42})
    assert r1.status_code == 200
    assert r2.status_code == 200
    # puzzle_id is a new UUID on each live-generated call — exclude from comparison.
    d1 = {k: v for k, v in r1.json().items() if k != "puzzle_id"}
    d2 = {k: v for k, v in r2.json().items() if k != "puzzle_id"}
    assert d1 == d2


@pytest.mark.slow
async def test_custom_puzzle_200(client: AsyncClient) -> None:
    r = await client.post(
        "/api/puzzle", json={"difficulty": "custom", "seed": 4, "sets_to_remove": 3}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["difficulty"] == "custom"
    assert len(data["rack"]) >= 9
    assert len(data["board_sets"]) >= 2


@pytest.mark.slow
async def test_custom_min_chain_depth_respected(client: AsyncClient) -> None:
    """min_chain_depth=1 is honoured: returned puzzle has chain_depth >= 1."""
    r = await client.post(
        "/api/puzzle", json={"difficulty": "custom", "seed": 5, "min_chain_depth": 1}
    )
    assert r.status_code == 200
    assert r.json()["chain_depth"] >= 1


@pytest.mark.slow
async def test_custom_min_disruption_respected(client: AsyncClient) -> None:
    """min_disruption=10 is honoured: returned disruption_score >= 10."""
    r = await client.post(
        "/api/puzzle", json={"difficulty": "custom", "seed": 6, "min_disruption": 10}
    )
    assert r.status_code == 200
    assert r.json()["disruption_score"] >= 10
