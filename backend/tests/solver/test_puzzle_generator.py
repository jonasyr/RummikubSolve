"""Unit tests for solver/generator/puzzle_generator.py."""

from __future__ import annotations

import pytest

from solver.engine.solver import solve
from solver.generator.puzzle_generator import (
    _COMPUTES_UNIQUE,  # type: ignore[attr-defined]
    _DEFAULT_MAX_ATTEMPTS,  # type: ignore[attr-defined]
    _DISRUPTION_BANDS,  # type: ignore[attr-defined]
    _MIN_CHAIN_DEPTHS,  # type: ignore[attr-defined]
    _PREGEN_CONSTRAINTS,  # type: ignore[attr-defined]
    _PREGEN_MAX_ATTEMPTS,  # type: ignore[attr-defined]
    PuzzleGenerationError,
    PuzzleResult,
    _any_trivial_extension,
    _inject_jokers_into_board,  # type: ignore[attr-defined]
    _make_pool,  # type: ignore[attr-defined]
    generate_puzzle,
)
from solver.models.board_state import BoardState
from solver.validator.rule_checker import is_valid_set

pytestmark = pytest.mark.slow

# ---------------------------------------------------------------------------
# Happy-path: one puzzle per difficulty
# ---------------------------------------------------------------------------


def test_easy_puzzle_generates() -> None:
    result = generate_puzzle(difficulty="easy", seed=1)
    assert isinstance(result, PuzzleResult)
    assert result.difficulty == "easy"
    assert 2 <= len(result.rack) <= 3


def test_medium_puzzle_generates() -> None:
    result = generate_puzzle(difficulty="medium", seed=2)
    assert result.difficulty == "medium"
    assert 3 <= len(result.rack) <= 4


def test_hard_puzzle_generates() -> None:
    result = generate_puzzle(difficulty="hard", seed=3)
    assert result.difficulty == "hard"
    assert 4 <= len(result.rack) <= 5


def test_custom_puzzle_generates() -> None:
    result = generate_puzzle(difficulty="custom", seed=4, sets_to_remove=3)
    assert result.difficulty == "custom"
    # 3 complete sets removed → at least 3 × 3 = 9 tiles.
    assert len(result.rack) >= 9


def test_custom_puzzle_scales_with_sets_removed() -> None:
    result = generate_puzzle(difficulty="custom", seed=7, sets_to_remove=4)
    # 4 complete sets removed → at least 4 × 3 = 12 tiles.
    assert len(result.rack) >= 12


def test_custom_puzzle_is_solvable() -> None:
    result = generate_puzzle(difficulty="custom", seed=10, sets_to_remove=3)
    state = BoardState(board_sets=result.board_sets, rack=result.rack)
    solution = solve(state)
    assert solution.tiles_placed == len(result.rack)


def test_expert_puzzle_generates() -> None:
    result = generate_puzzle(difficulty="expert", seed=20)
    assert result.difficulty == "expert"
    assert 6 <= len(result.rack) <= 10


def test_expert_rack_has_no_trivial_extension() -> None:
    """Neither rack tile can be directly appended to any remaining board set."""
    result = generate_puzzle(difficulty="expert", seed=20)
    assert not _any_trivial_extension(result.rack, result.board_sets), (
        "Expert puzzle has a trivially-extensible tile — board disruption is not required"
    )


def test_expert_puzzle_is_solvable() -> None:
    """Full solve must place all rack tiles (requiring board rearrangement)."""
    result = generate_puzzle(difficulty="expert", seed=20)
    state = BoardState(board_sets=result.board_sets, rack=result.rack)
    solution = solve(state)
    assert solution.tiles_placed == len(result.rack)


def test_expert_is_valid_difficulty() -> None:
    """'expert' must not raise ValueError (regression guard)."""
    result = generate_puzzle(difficulty="expert", seed=99)
    assert result.difficulty == "expert"


# ---------------------------------------------------------------------------
# Disruption score invariants
# ---------------------------------------------------------------------------


def test_puzzle_result_has_disruption_score() -> None:
    """PuzzleResult always includes a disruption_score field."""
    result = generate_puzzle(difficulty="medium", seed=1)
    assert isinstance(result.disruption_score, int)
    assert result.disruption_score >= 0


def test_disruption_score_in_band_easy() -> None:
    lo, hi = _DISRUPTION_BANDS["easy"]
    for seed in range(3):
        result = generate_puzzle(difficulty="easy", seed=seed)
        score = result.disruption_score
        assert score >= lo, f"Easy disruption {score} below floor {lo} (seed={seed})"
        if hi is not None:
            assert score <= hi, f"Easy disruption {score} above ceiling {hi} (seed={seed})"


def test_disruption_score_in_band_medium() -> None:
    lo, hi = _DISRUPTION_BANDS["medium"]
    for seed in range(3):
        result = generate_puzzle(difficulty="medium", seed=seed)
        score = result.disruption_score
        assert score >= lo, f"Medium disruption {score} below floor {lo} (seed={seed})"
        if hi is not None:
            assert score <= hi, f"Medium disruption {score} above ceiling {hi} (seed={seed})"


def test_disruption_score_in_band_hard() -> None:
    lo, hi = _DISRUPTION_BANDS["hard"]
    for seed in range(3):
        result = generate_puzzle(difficulty="hard", seed=seed)
        score = result.disruption_score
        assert score >= lo, f"Hard disruption {score} below floor {lo} (seed={seed})"
        if hi is not None:
            assert score <= hi, f"Hard disruption {score} above ceiling {hi} (seed={seed})"


def test_disruption_score_in_band_expert() -> None:
    lo, hi = _DISRUPTION_BANDS["expert"]
    # Expert floor (29) is strictly above Hard's ceiling (28).
    assert lo > 28, "Expert disruption floor must exceed Hard's ceiling of 28"
    for seed in range(3):
        result = generate_puzzle(difficulty="expert", seed=seed)
        score = result.disruption_score
        assert score >= lo, f"Expert disruption {score} below floor {lo} (seed={seed})"
        if hi is not None:
            assert score <= hi, f"Expert disruption {score} above ceiling {hi} (seed={seed})"


def test_all_difficulties_require_no_trivial_extension() -> None:
    """Every non-custom difficulty must reject trivially-extensible racks."""
    for difficulty in ("easy", "medium", "hard", "expert"):
        result = generate_puzzle(difficulty=difficulty, seed=42)  # type: ignore[arg-type]
        assert not _any_trivial_extension(result.rack, result.board_sets), (
            f"{difficulty} puzzle (seed=42) has a trivially-extensible rack tile"
        )


# ---------------------------------------------------------------------------
# Correctness invariants
# ---------------------------------------------------------------------------


def test_board_sets_all_valid() -> None:
    result = generate_puzzle(difficulty="medium", seed=10)
    for ts in result.board_sets:
        assert is_valid_set(ts), f"Invalid board set: {ts!r}"


def test_puzzle_is_fully_solvable() -> None:
    result = generate_puzzle(difficulty="medium", seed=11)
    state = BoardState(board_sets=result.board_sets, rack=result.rack)
    solution = solve(state)
    assert solution.tiles_placed == len(result.rack)


def test_rack_minimum_size() -> None:
    """Rack size stays within the configured range for each difficulty."""
    rack_ranges = {"easy": (2, 3), "medium": (3, 4), "hard": (4, 5), "expert": (6, 10)}
    for seed in range(5):
        for difficulty, (lo, hi) in rack_ranges.items():
            result = generate_puzzle(difficulty=difficulty, seed=seed)  # type: ignore[arg-type]
            assert lo <= len(result.rack) <= hi, (
                f"Rack size out of range for {difficulty} (seed={seed}): got {len(result.rack)}"
            )


def test_custom_rack_minimum_size() -> None:
    """Custom with sets_to_remove=n always yields at least n×3 tiles (smallest set = 3)."""
    for seed in range(3):
        for n in (1, 2, 3):
            result = generate_puzzle(difficulty="custom", seed=seed, sets_to_remove=n)
            assert len(result.rack) >= n * 3, (
                f"Custom rack too small for n={n} (seed={seed}): got {len(result.rack)}"
            )


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


def test_seeded_puzzle_is_deterministic() -> None:
    a = generate_puzzle(difficulty="medium", seed=42)
    b = generate_puzzle(difficulty="medium", seed=42)

    def tiles_key(ts_list: list) -> list:  # type: ignore[type-arg]
        return [[(t.color, t.number, t.copy_id) for t in ts.tiles] for ts in ts_list]

    assert tiles_key(a.board_sets) == tiles_key(b.board_sets)
    assert [(t.color, t.number, t.copy_id) for t in a.rack] == [
        (t.color, t.number, t.copy_id) for t in b.rack
    ]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_invalid_difficulty_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown difficulty"):
        generate_puzzle(difficulty="extreme")  # type: ignore[arg-type]


def test_custom_is_valid_difficulty() -> None:
    """'custom' must not raise ValueError (regression guard)."""
    result = generate_puzzle(difficulty="custom", seed=99, sets_to_remove=2)
    assert result.difficulty == "custom"


def test_zero_attempts_raises_generation_error() -> None:
    with pytest.raises(PuzzleGenerationError):
        generate_puzzle(difficulty="medium", max_attempts=0)


# ---------------------------------------------------------------------------
# Tile-conservation invariants
# ---------------------------------------------------------------------------


def test_rack_tiles_not_in_board() -> None:
    """No physical tile (color, number, copy_id) appears in both rack and board_sets."""
    result = generate_puzzle(difficulty="medium", seed=10)
    board_keys = {(t.color, t.number, t.copy_id) for ts in result.board_sets for t in ts.tiles}
    rack_keys = {(t.color, t.number, t.copy_id) for t in result.rack}
    assert board_keys.isdisjoint(rack_keys), (
        f"Overlap between board and rack: {board_keys & rack_keys}"
    )


def test_copy_ids_valid() -> None:
    """Every tile in a generated puzzle has copy_id in {0, 1}."""
    result = generate_puzzle(difficulty="hard", seed=5)
    all_tiles = [t for ts in result.board_sets for t in ts.tiles] + result.rack
    invalid = [(t.color, t.number, t.copy_id) for t in all_tiles if t.copy_id not in (0, 1)]
    assert invalid == [], f"Tiles with invalid copy_id: {invalid}"


# ---------------------------------------------------------------------------
# Phase 3: fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _nightmare_result() -> PuzzleResult:
    """Generate a nightmare puzzle once for this entire module.

    Uses scope="module" so the expensive generation (chain_depth ≥ 3 +
    uniqueness check) runs only once regardless of how many test methods
    consume the fixture.
    """
    return generate_puzzle(difficulty="nightmare", seed=99)


# ---------------------------------------------------------------------------
# Phase 3: PuzzleResult new fields (chain_depth + is_unique)
# ---------------------------------------------------------------------------


class TestPuzzleResultNewFields:
    """PuzzleResult carries chain_depth and is_unique after Phase 3."""

    def test_easy_has_chain_depth_field(self) -> None:
        result = generate_puzzle(difficulty="easy", seed=1)
        assert isinstance(result.chain_depth, int)
        assert result.chain_depth >= 0

    def test_medium_has_chain_depth_field(self) -> None:
        result = generate_puzzle(difficulty="medium", seed=2)
        assert isinstance(result.chain_depth, int)
        assert result.chain_depth >= 0

    def test_hard_has_chain_depth_field(self) -> None:
        result = generate_puzzle(difficulty="hard", seed=3)
        assert isinstance(result.chain_depth, int)
        assert result.chain_depth >= _MIN_CHAIN_DEPTHS["hard"]

    def test_expert_has_chain_depth_field(self) -> None:
        result = generate_puzzle(difficulty="expert", seed=42)
        assert isinstance(result.chain_depth, int)
        assert result.chain_depth >= _MIN_CHAIN_DEPTHS["expert"]  # ≥ 1

    def test_easy_has_is_unique_field(self) -> None:
        result = generate_puzzle(difficulty="easy", seed=1)
        assert isinstance(result.is_unique, bool)

    def test_expert_is_unique_field_is_bool(self) -> None:
        # is_unique is informational (not gated): could be True or False.
        result = generate_puzzle(difficulty="expert", seed=42)
        assert isinstance(result.is_unique, bool)

    def test_custom_has_new_fields(self) -> None:
        result = generate_puzzle(difficulty="custom", seed=4, sets_to_remove=3)
        assert isinstance(result.chain_depth, int)
        assert result.chain_depth >= 0
        assert isinstance(result.is_unique, bool)


# ---------------------------------------------------------------------------
# Phase 3: chain_depth filtering
# ---------------------------------------------------------------------------


class TestChainDepthFiltering:
    """_MIN_CHAIN_DEPTHS filters are respected per difficulty tier."""

    def test_hard_multiple_seeds_chain_depth_ge_1(self) -> None:
        for seed in range(3):
            result = generate_puzzle(difficulty="hard", seed=seed)
            assert result.chain_depth >= 1, (
                f"Hard seed={seed}: chain_depth={result.chain_depth} below floor 1"
            )

    def test_expert_multiple_seeds_chain_depth_ge_2(self) -> None:
        for seed in range(3):
            result = generate_puzzle(difficulty="expert", seed=seed)
            floor = _MIN_CHAIN_DEPTHS["expert"]
            assert result.chain_depth >= floor, (
                f"Expert seed={seed}: chain_depth={result.chain_depth} below floor {floor}"
            )

    def test_easy_chain_depth_zero_is_allowed(self) -> None:
        # Easy puzzles have no chain_depth floor; 0 is valid.
        result = generate_puzzle(difficulty="easy", seed=1)
        assert result.chain_depth >= 0

    def test_chain_depth_matches_config_floor(self) -> None:
        """Easy/Medium/Hard/Expert each meet their _MIN_CHAIN_DEPTHS floor.

        Nightmare is excluded here — it is covered in TestNightmareDifficulty
        using a shared fixture to avoid duplicate expensive generation calls.
        """
        for difficulty in ("easy", "medium", "hard", "expert"):
            floor = _MIN_CHAIN_DEPTHS[difficulty]
            result = generate_puzzle(difficulty=difficulty, seed=7)  # type: ignore[arg-type]
            assert result.chain_depth >= floor, (
                f"{difficulty}: chain_depth={result.chain_depth} below configured floor {floor}"
            )

    def test_min_chain_depths_dict_has_all_tiers(self) -> None:
        """_MIN_CHAIN_DEPTHS covers all non-custom difficulties."""
        for tier in ("easy", "medium", "hard", "expert", "nightmare"):
            assert tier in _MIN_CHAIN_DEPTHS, f"Missing tier {tier!r} in _MIN_CHAIN_DEPTHS"


# ---------------------------------------------------------------------------
# Phase 3: Nightmare difficulty tier
# ---------------------------------------------------------------------------


class TestNightmareDifficulty:
    """Nightmare difficulty tier — chain_depth ≥ 3, is_unique=True, disruption ≥ 38.

    All tests that inspect the puzzle content reuse the module-scoped
    _nightmare_result fixture so the expensive generation runs only once.
    """

    def test_nightmare_generates(self, _nightmare_result: PuzzleResult) -> None:
        assert _nightmare_result.difficulty == "nightmare"

    def test_nightmare_rack_size_range(self, _nightmare_result: PuzzleResult) -> None:
        assert 10 <= len(_nightmare_result.rack) <= 14

    def test_nightmare_chain_depth_meets_floor(self, _nightmare_result: PuzzleResult) -> None:
        assert _nightmare_result.chain_depth >= _MIN_CHAIN_DEPTHS["nightmare"]

    def test_nightmare_is_unique_field_is_bool(self, _nightmare_result: PuzzleResult) -> None:
        # is_unique is informational (not gated) — large boards have many equivalent
        # rearrangements so requiring uniqueness would make generation infeasible.
        assert isinstance(_nightmare_result.is_unique, bool)

    def test_nightmare_disruption_floor(self, _nightmare_result: PuzzleResult) -> None:
        lo, _ = _DISRUPTION_BANDS["nightmare"]
        assert _nightmare_result.disruption_score >= lo, (
            f"Nightmare disruption {_nightmare_result.disruption_score} below floor {lo}"
        )

    def test_nightmare_seeded_determinism(self, _nightmare_result: PuzzleResult) -> None:
        # Re-generate with the same seed and verify the rack is identical.
        r2 = generate_puzzle(difficulty="nightmare", seed=99)
        assert [(t.color, t.number, t.copy_id) for t in _nightmare_result.rack] == [
            (t.color, t.number, t.copy_id) for t in r2.rack
        ]

    def test_nightmare_solvable(self, _nightmare_result: PuzzleResult) -> None:
        state = BoardState(board_sets=_nightmare_result.board_sets, rack=_nightmare_result.rack)
        solution = solve(state)
        assert solution.tiles_placed == len(_nightmare_result.rack)

    def test_nightmare_tiles_all_valid_sets(self, _nightmare_result: PuzzleResult) -> None:
        for ts in _nightmare_result.board_sets:
            assert is_valid_set(ts), f"Invalid board set in nightmare puzzle: {ts!r}"

    def test_invalid_difficulty_still_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown difficulty"):
            generate_puzzle(difficulty="extreme")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Phase 3: uniqueness gating
# ---------------------------------------------------------------------------


class TestUniquenessComputation:
    """check_uniqueness is computed for Expert / Nightmare / Custom (informational, not a gate).

    Large boards with many equivalent rearrangements typically yield non-unique
    solutions, so uniqueness is stored in PuzzleResult for API consumers but is
    not used to filter candidates.
    """

    def test_expert_is_unique_is_bool(self) -> None:
        result = generate_puzzle(difficulty="expert", seed=0)
        assert isinstance(result.is_unique, bool)

    def test_computes_unique_dict_has_all_tiers(self) -> None:
        """_COMPUTES_UNIQUE covers all non-custom difficulties."""
        for tier in ("easy", "medium", "hard", "expert", "nightmare"):
            assert tier in _COMPUTES_UNIQUE, f"Missing tier {tier!r} in _COMPUTES_UNIQUE"

    def test_hard_is_unique_field_present(self) -> None:
        result = generate_puzzle(difficulty="hard", seed=3)
        assert isinstance(result.is_unique, bool)

    def test_easy_is_unique_field_is_bool(self) -> None:
        result = generate_puzzle(difficulty="easy", seed=1)
        assert isinstance(result.is_unique, bool)

    def test_computes_unique_false_for_easy_medium_hard(self) -> None:
        """Non-expert tiers do not call check_uniqueness (overhead avoidance)."""
        for tier in ("easy", "medium", "hard"):
            assert _COMPUTES_UNIQUE[tier] is False, (
                f"{tier} unexpectedly computes uniqueness"
            )

    def test_computes_unique_true_for_expert_nightmare(self) -> None:
        for tier in ("expert", "nightmare"):
            assert _COMPUTES_UNIQUE[tier] is True, (
                f"{tier} must compute uniqueness"
            )


# ---------------------------------------------------------------------------
# Phase 7a: Custom mode — new generation parameters
# ---------------------------------------------------------------------------


def test_custom_respects_min_chain_depth() -> None:
    result = generate_puzzle(difficulty="custom", seed=5, min_chain_depth=1)
    assert result.chain_depth >= 1, (
        f"Expected chain_depth >= 1, got {result.chain_depth}"
    )


def test_custom_respects_min_disruption() -> None:
    result = generate_puzzle(difficulty="custom", seed=6, min_disruption=10)
    assert result.disruption_score >= 10, (
        f"Expected disruption_score >= 10, got {result.disruption_score}"
    )


def test_custom_respects_board_size_params() -> None:
    """Explicit board size params are accepted; generation must succeed."""
    result = generate_puzzle(
        difficulty="custom", seed=7, min_board_sets=7, max_board_sets=10
    )
    assert result.difficulty == "custom"


def test_custom_computes_is_unique() -> None:
    """Custom puzzles always compute is_unique (informational, not gated)."""
    result = generate_puzzle(difficulty="custom", seed=4, sets_to_remove=2)
    assert isinstance(result.is_unique, bool)


def test_custom_zero_filters_still_generates() -> None:
    """Default custom params (all zeros) still generates successfully."""
    result = generate_puzzle(
        difficulty="custom", seed=10, sets_to_remove=3,
        min_chain_depth=0, min_disruption=0,
    )
    assert result.difficulty == "custom"
    assert len(result.rack) >= 9  # 3 sets × 3 tiles minimum


# ---------------------------------------------------------------------------
# Phase 1 fixes: joker_count, _make_pool validation, _inject_jokers_into_board
# ---------------------------------------------------------------------------


class TestMakePoolValidation:
    """_make_pool() validates n_jokers is in [0, 2]."""

    def test_zero_jokers_ok(self) -> None:
        pool = _make_pool(0)
        assert len(pool.rack) == 104

    def test_one_joker_ok(self) -> None:
        pool = _make_pool(1)
        assert len(pool.rack) == 105
        jokers = [t for t in pool.rack if t.is_joker]
        assert len(jokers) == 1

    def test_two_jokers_ok(self) -> None:
        pool = _make_pool(2)
        assert len(pool.rack) == 106
        jokers = [t for t in pool.rack if t.is_joker]
        assert len(jokers) == 2

    def test_negative_jokers_raises(self) -> None:
        with pytest.raises(ValueError, match="n_jokers"):
            _make_pool(-1)

    def test_three_jokers_raises(self) -> None:
        with pytest.raises(ValueError, match="n_jokers"):
            _make_pool(3)


class TestJokerCountPopulated:
    """PuzzleResult.joker_count reflects the actual number of jokers used."""

    def test_easy_joker_count_is_zero(self) -> None:
        result = generate_puzzle(difficulty="easy", seed=1)
        assert result.joker_count == 0

    def test_medium_joker_count_is_zero(self) -> None:
        result = generate_puzzle(difficulty="medium", seed=2)
        assert result.joker_count == 0

    def test_joker_count_is_int(self) -> None:
        result = generate_puzzle(difficulty="hard", seed=3)
        assert isinstance(result.joker_count, int)

    def test_expert_joker_count_is_board_joker_count(self) -> None:
        """joker_count == number of joker tiles on the board (0 if joker sets were sacrificed)."""
        result = generate_puzzle(difficulty="expert", seed=20)
        board_jokers = sum(1 for ts in result.board_sets for t in ts.tiles if t.is_joker)
        assert result.joker_count == board_jokers


class TestInjectJokersIntoBoard:
    """_inject_jokers_into_board places jokers in board sets with ≥ 4 tiles."""

    def _make_board_with_4tile_set(self) -> list:
        from solver.models.tile import Color, Tile
        from solver.models.tileset import TileSet
        # A 4-tile run: R1-R2-R3-R4
        tiles_4 = [
            Tile(Color.RED, 1, 0),
            Tile(Color.RED, 2, 0),
            Tile(Color.RED, 3, 0),
            Tile(Color.RED, 4, 0),
        ]
        # A 3-tile run: B5-B6-B7 (ineligible for joker injection)
        tiles_3 = [
            Tile(Color.BLUE, 5, 0),
            Tile(Color.BLUE, 6, 0),
            Tile(Color.BLUE, 7, 0),
        ]
        return [TileSet(type="run", tiles=tiles_4), TileSet(type="run", tiles=tiles_3)]

    def test_zero_jokers_returns_unchanged(self) -> None:
        import random
        board = self._make_board_with_4tile_set()
        result = _inject_jokers_into_board(board, 0, random.Random(1))
        # No jokers injected — tile counts unchanged
        assert sum(len(ts.tiles) for ts in result) == sum(len(ts.tiles) for ts in board)
        assert not any(t.is_joker for ts in result for t in ts.tiles)

    def test_one_joker_injected_in_4tile_set(self) -> None:
        import random
        board = self._make_board_with_4tile_set()
        result = _inject_jokers_into_board(board, 1, random.Random(1))
        jokers = [t for ts in result for t in ts.tiles if t.is_joker]
        assert len(jokers) == 1
        # Joker must be in the 4-tile set (only eligible candidate)
        assert any(t.is_joker for t in result[0].tiles)
        # 3-tile set must remain unchanged
        assert not any(t.is_joker for t in result[1].tiles)

    def test_joker_copy_ids_are_valid(self) -> None:
        import random
        board = self._make_board_with_4tile_set()
        result = _inject_jokers_into_board(board, 1, random.Random(42))
        for ts in result:
            for t in ts.tiles:
                assert t.copy_id in (0, 1)

    def test_no_eligible_sets_returns_unchanged(self) -> None:
        """When all sets have < 4 tiles, no jokers are injected."""
        import random

        from solver.models.tile import Color, Tile
        from solver.models.tileset import TileSet
        board = [
            TileSet(type="run", tiles=[Tile(Color.RED, i, 0) for i in range(1, 4)]),
            TileSet(type="run", tiles=[Tile(Color.BLUE, i, 0) for i in range(5, 8)]),
        ]
        result = _inject_jokers_into_board(board, 2, random.Random(1))
        assert not any(t.is_joker for ts in result for t in ts.tiles)

    def test_joker_count_matches_board_jokers(self) -> None:
        """joker_count equals the number of joker tiles visible on the board.

        Jokers are injected into board sets by _inject_jokers_into_board.
        joker_count is the count of jokers actually on board_sets (not the
        number attempted — jokers in sacrificed sets are excluded).
        """
        for seed in range(5):
            result = generate_puzzle(difficulty="expert", seed=seed)
            board_jokers = sum(1 for ts in result.board_sets for t in ts.tiles if t.is_joker)
            assert result.joker_count == board_jokers, (
                f"Expert seed={seed}: joker_count={result.joker_count} but "
                f"board has {board_jokers} jokers"
            )


# ---------------------------------------------------------------------------
# Phase 2: Pre-generation tier (_PREGEN_CONSTRAINTS, pregen=True)
# ---------------------------------------------------------------------------


class TestPregenTier:
    """pregen=True applies stricter chain_depth and disruption thresholds.

    These tests use fast seeds and low attempt counts to stay under CI timeout.
    The pregen=True path is tested for:
      - Correct constant structure (_PREGEN_CONSTRAINTS / _PREGEN_MAX_ATTEMPTS)
      - Stricter thresholds applied (disruption and chain_depth floors higher)
      - pregen=False (default) still uses live thresholds
    """

    def test_pregen_constraints_dict_structure(self) -> None:
        """_PREGEN_CONSTRAINTS covers expert and nightmare with required keys."""
        for tier in ("expert", "nightmare"):
            assert tier in _PREGEN_CONSTRAINTS, f"Missing tier {tier!r}"
            c = _PREGEN_CONSTRAINTS[tier]
            assert "min_chain_depth" in c
            assert "min_disruption" in c

    def test_pregen_stricter_than_live_expert(self) -> None:
        """Pre-generation thresholds must exceed live generation thresholds."""
        live_chain = _MIN_CHAIN_DEPTHS["expert"]
        live_disrupt, _ = _DISRUPTION_BANDS["expert"]
        pregen = _PREGEN_CONSTRAINTS["expert"]
        assert pregen["min_chain_depth"] > live_chain, (
            f"pregen chain {pregen['min_chain_depth']} must exceed live {live_chain}"
        )
        assert pregen["min_disruption"] > live_disrupt, (
            f"pregen disruption {pregen['min_disruption']} must exceed live {live_disrupt}"
        )

    def test_pregen_stricter_than_live_nightmare(self) -> None:
        """Pre-generation thresholds must exceed live generation thresholds."""
        live_chain = _MIN_CHAIN_DEPTHS["nightmare"]
        live_disrupt, _ = _DISRUPTION_BANDS["nightmare"]
        pregen = _PREGEN_CONSTRAINTS["nightmare"]
        assert pregen["min_chain_depth"] > live_chain
        assert pregen["min_disruption"] > live_disrupt

    def test_pregen_max_attempts_higher_than_default(self) -> None:
        """Pre-generation attempt budget must exceed live budget."""
        for tier in ("expert", "nightmare"):
            assert _PREGEN_MAX_ATTEMPTS[tier] > _DEFAULT_MAX_ATTEMPTS[tier], (  # type: ignore[attr-defined]
                f"{tier}: pregen attempts {_PREGEN_MAX_ATTEMPTS[tier]} "
                f"not > live {_DEFAULT_MAX_ATTEMPTS[tier]}"  # type: ignore[attr-defined]
            )

    def test_pregen_false_uses_live_thresholds(self) -> None:
        """Default pregen=False produces puzzles meeting live (not pregen) thresholds.

        Expert live floor is disruption ≥ 32, chain ≥ 2. Pregen floor is ≥ 38 / ≥ 3.
        A live puzzle may have disruption in [32, 37] or chain == 2 — still valid.
        """
        result = generate_puzzle(difficulty="expert", seed=0)
        live_lo, _ = _DISRUPTION_BANDS["expert"]
        assert result.disruption_score >= live_lo
        assert result.chain_depth >= _MIN_CHAIN_DEPTHS["expert"]

    def test_pregen_true_result_meets_stricter_thresholds(self) -> None:
        """pregen=True puzzle meets _PREGEN_CONSTRAINTS (not just live thresholds).

        Uses a higher max_attempts override to keep test duration bounded.
        Expert pregen requires chain ≥ 3 and disruption ≥ 38.
        """
        result = generate_puzzle(difficulty="expert", seed=7, pregen=True)
        pc = _PREGEN_CONSTRAINTS["expert"]
        assert result.disruption_score >= pc["min_disruption"], (
            f"pregen expert: disruption {result.disruption_score} < {pc['min_disruption']}"
        )
        assert result.chain_depth >= pc["min_chain_depth"], (
            f"pregen expert: chain_depth {result.chain_depth} < {pc['min_chain_depth']}"
        )

    def test_pregen_result_is_solvable(self) -> None:
        """pregen=True puzzle is still fully solvable."""
        from solver.engine.solver import solve
        from solver.models.board_state import BoardState
        result = generate_puzzle(difficulty="expert", seed=7, pregen=True)
        state = BoardState(board_sets=result.board_sets, rack=result.rack)
        solution = solve(state)
        assert solution.tiles_placed == len(result.rack)


# ---------------------------------------------------------------------------
# Phase 4: v2 generator (_attempt_generate_v2, generate_puzzle with generator_version="v2")
# ---------------------------------------------------------------------------


class TestGeneratorV2:
    """Tests for the v2 generation pipeline (BoardBuilder + TileRemover + DifficultyEvaluator)."""

    def test_v2_returns_puzzle_result_easy(self) -> None:
        """generate_puzzle with generator_version='v2' returns a PuzzleResult for easy."""
        result = generate_puzzle(difficulty="easy", seed=0, generator_version="v2")
        assert isinstance(result, PuzzleResult)
        assert result.generator_version == "v2.0.0"
        assert len(result.rack) >= 2
        assert len(result.board_sets) >= 1

    def test_v2_returns_puzzle_result_medium(self) -> None:
        """generate_puzzle with generator_version='v2' returns a PuzzleResult for medium."""
        result = generate_puzzle(difficulty="medium", seed=1, generator_version="v2")
        assert isinstance(result, PuzzleResult)
        assert result.generator_version == "v2.0.0"

    def test_v2_new_fields_populated(self) -> None:
        """v2 result has non-default values for new difficulty metric fields."""
        result = generate_puzzle(difficulty="easy", seed=5, generator_version="v2")
        # At least one metric should be non-zero for any real puzzle
        assert (
            result.branching_factor > 0.0
            or result.tile_ambiguity > 0.0
            or result.composite_score > 0.0
        )
        assert result.composite_score >= 0.0

    def test_v2_composite_score_in_range(self) -> None:
        """v2 composite_score is in [0, 100]."""
        result = generate_puzzle(difficulty="medium", seed=3, generator_version="v2")
        assert 0.0 <= result.composite_score <= 100.0

    def test_v1_fallback_still_works(self) -> None:
        """generator_version='v1' produces the old-style result (no composite_score)."""
        result = generate_puzzle(difficulty="easy", seed=1, generator_version="v1")
        assert result.generator_version == "v1"
        assert result.composite_score == 0.0

    def test_v2_puzzle_is_solvable(self) -> None:
        """v2 puzzle is solvable by the ILP solver."""
        from solver.models.board_state import BoardState
        result = generate_puzzle(difficulty="easy", seed=10, generator_version="v2")
        state = BoardState(board_sets=result.board_sets, rack=result.rack)
        solution = solve(state)
        assert solution.tiles_placed == len(result.rack)
