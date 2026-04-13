from __future__ import annotations

from solver.generator import pregenerate, puzzle_generator
from solver.generator.pregenerate import _WorkerResult
from solver.models.board_state import Solution
from solver.models.tile import Color, Tile
from solver.models.tileset import SetType, TileSet


def _sample_tileset() -> TileSet:
    return TileSet(
        type=SetType.RUN,
        tiles=[
            Tile(Color.BLUE, 1, 0),
            Tile(Color.BLUE, 2, 0),
            Tile(Color.BLUE, 3, 0),
        ],
    )


def _sample_complexity(
    candidate_set_count: int,
    estimated_ilp_columns: int | None = None,
    estimated_ilp_rows: int | None = None,
    rack_tiles_placeable: int = 6,
    min_rack_tile_coverage: int = 2,
    total_rack_tile_coverage: int = 12,
    multi_option_rack_tiles: int = 3,
) -> puzzle_generator._ComplexityEstimate:
    return puzzle_generator._ComplexityEstimate(
        candidate_set_count=candidate_set_count,
        estimated_ilp_columns=estimated_ilp_columns or candidate_set_count * 10,
        estimated_ilp_rows=estimated_ilp_rows or candidate_set_count * 6,
        board_tile_count=12,
        rack_tile_count=6,
        rack_tiles_placeable=rack_tiles_placeable,
        min_rack_tile_coverage=min_rack_tile_coverage,
        total_rack_tile_coverage=total_rack_tile_coverage,
        multi_option_rack_tiles=multi_option_rack_tiles,
    )


def test_better_rack_candidate_prefers_lower_candidate_count() -> None:
    # Arrange
    board = [_sample_tileset()]
    low = puzzle_generator._RackCandidate(
        remaining_board=board,
        rack=[Tile(Color.RED, 4, 0)],
        complexity=_sample_complexity(candidate_set_count=20, estimated_ilp_columns=200),
    )
    high = puzzle_generator._RackCandidate(
        remaining_board=board,
        rack=[Tile(Color.RED, 5, 0)],
        complexity=_sample_complexity(candidate_set_count=30, estimated_ilp_columns=300),
    )

    # Act / Assert
    assert puzzle_generator._better_rack_candidate(low, high) is True
    assert puzzle_generator._better_rack_candidate(high, low) is False


def test_attempt_rejects_candidate_cap_before_solver(monkeypatch) -> None:
    # Arrange
    board_sets = [_sample_tileset(), _sample_tileset(), _sample_tileset()]
    rack_candidate = puzzle_generator._RackCandidate(
        remaining_board=board_sets,
        rack=[Tile(Color.RED, 4, 0) for _ in range(6)],
        complexity=_sample_complexity(
            candidate_set_count=5_000,
            estimated_ilp_columns=7_000,
            estimated_ilp_rows=4_000,
        ),
    )

    monkeypatch.setattr(puzzle_generator, "_make_pool", lambda n_jokers=0: object())
    monkeypatch.setattr(puzzle_generator, "enumerate_runs", lambda pool: [])
    monkeypatch.setattr(puzzle_generator, "enumerate_groups", lambda pool: [])
    monkeypatch.setattr(puzzle_generator, "_pick_compatible_sets", lambda all_sets, n: board_sets)
    monkeypatch.setattr(puzzle_generator, "_assign_copy_ids", lambda sets: sets)
    monkeypatch.setattr(puzzle_generator, "_extract_rack", lambda *args, **kwargs: rack_candidate)

    def _unexpected_solve(*args, **kwargs):
        raise AssertionError("solve() should not be called once candidate cap is exceeded")

    monkeypatch.setattr(puzzle_generator, "solve", _unexpected_solve)

    # Act
    outcome = puzzle_generator._attempt_generate_with_reason(
        rng=__import__("random").Random(1),
        difficulty="expert",
        pregen=True,
    )

    # Assert
    assert outcome.result is None
    assert outcome.rejection_reason == "candidate_cap_reject"


def test_attempt_rejects_low_coverage_rack_before_solver(monkeypatch) -> None:
    # Arrange
    board_sets = [_sample_tileset(), _sample_tileset(), _sample_tileset()]
    rack_candidate = puzzle_generator._RackCandidate(
        remaining_board=board_sets,
        rack=[Tile(Color.RED, 4, 0) for _ in range(6)],
        complexity=_sample_complexity(
            candidate_set_count=100,
            estimated_ilp_columns=800,
            estimated_ilp_rows=600,
            rack_tiles_placeable=6,
            min_rack_tile_coverage=1,
            total_rack_tile_coverage=6,
            multi_option_rack_tiles=0,
        ),
    )

    monkeypatch.setattr(puzzle_generator, "_make_pool", lambda n_jokers=0: object())
    monkeypatch.setattr(puzzle_generator, "enumerate_runs", lambda pool: [])
    monkeypatch.setattr(puzzle_generator, "enumerate_groups", lambda pool: [])
    monkeypatch.setattr(puzzle_generator, "_pick_compatible_sets", lambda all_sets, n: board_sets)
    monkeypatch.setattr(puzzle_generator, "_assign_copy_ids", lambda sets: sets)
    monkeypatch.setattr(puzzle_generator, "_extract_rack", lambda *args, **kwargs: rack_candidate)

    def _unexpected_solve(*args, **kwargs):
        raise AssertionError("solve() should not be called once rack proxy fails")

    monkeypatch.setattr(puzzle_generator, "solve", _unexpected_solve)

    # Act
    outcome = puzzle_generator._attempt_generate_with_reason(
        rng=__import__("random").Random(1),
        difficulty="expert",
        pregen=True,
    )

    # Assert
    assert outcome.result is None
    assert outcome.rejection_reason == "rack_proxy_fail"


def test_pregen_profiles_disable_jokers_for_expert_and_nightmare() -> None:
    # Arrange / Act / Assert
    assert puzzle_generator._PREGEN_PROFILES["expert"].joker_count_range == (0, 0)
    assert puzzle_generator._PREGEN_PROFILES["nightmare"].joker_count_range == (0, 0)


def test_nightmare_pregen_profile_uses_tighter_rack_and_source_set_caps() -> None:
    # Arrange
    profile = puzzle_generator._PREGEN_PROFILES["nightmare"]

    # Act / Assert
    assert profile.rack_size_range == (6, 7)
    assert profile.sacrifice_count == 3
    assert profile.max_rack_source_sets == 2


def test_extract_by_sacrifice_keeps_lowest_complexity_rack(monkeypatch) -> None:
    # Arrange
    board = [
        TileSet(
            type=SetType.RUN,
            tiles=[Tile(Color.BLUE, 1, 0), Tile(Color.BLUE, 2, 0), Tile(Color.BLUE, 3, 0)],
        ),
        TileSet(
            type=SetType.RUN,
            tiles=[Tile(Color.RED, 1, 0), Tile(Color.RED, 2, 0), Tile(Color.RED, 3, 0)],
        ),
        TileSet(
            type=SetType.RUN,
            tiles=[
                Tile(Color.BLACK, 1, 0),
                Tile(Color.BLACK, 2, 0),
                Tile(Color.BLACK, 3, 0),
            ],
        ),
        TileSet(
            type=SetType.RUN,
            tiles=[
                Tile(Color.YELLOW, 1, 0),
                Tile(Color.YELLOW, 2, 0),
                Tile(Color.YELLOW, 3, 0),
            ],
        ),
    ]

    sampled_racks = [
        [Tile(Color.BLUE, 1, 0), Tile(Color.RED, 1, 0)],
        [Tile(Color.BLUE, 2, 0), Tile(Color.RED, 2, 0)],
        [Tile(Color.BLUE, 3, 0), Tile(Color.RED, 3, 0)],
    ]
    candidate_sizes = {
        tuple((t.color, t.number, t.copy_id) for t in sampled_racks[0]): 50,
        tuple((t.color, t.number, t.copy_id) for t in sampled_racks[1]): 10,
        tuple((t.color, t.number, t.copy_id) for t in sampled_racks[2]): 30,
    }

    class _FakeRandom:
        def sample(self, population, k):
            if population and isinstance(population[0], int):
                return [0]
            return sampled_racks.pop(0)

        def randint(self, lo, hi):
            return 2

    monkeypatch.setattr(puzzle_generator, "_any_trivial_extension", lambda rack, remaining: False)

    def _fake_build_rack_candidate(remaining_board, rack):
        key = tuple((t.color, t.number, t.copy_id) for t in rack)
        return puzzle_generator._RackCandidate(
            remaining_board=remaining_board,
            rack=rack,
            complexity=_sample_complexity(
                candidate_set_count=candidate_sizes[key],
                estimated_ilp_columns=candidate_sizes[key] * 10,
            ),
        )

    monkeypatch.setattr(puzzle_generator, "_build_rack_candidate", _fake_build_rack_candidate)

    # Act
    result = puzzle_generator._extract_by_sacrifice(
        board_sets=board,
        rng=_FakeRandom(),
        num_sacrifice=1,
        rack_size_range=(2, 2),
        max_rack_source_sets=None,
        rack_sample_budget=3,
    )

    # Assert
    assert result is not None
    assert result.complexity.candidate_set_count == 10


def test_sample_rack_from_sacrificed_sets_respects_source_set_cap() -> None:
    # Arrange
    sacrificed_sets = [
        TileSet(type=SetType.RUN, tiles=[Tile(Color.BLUE, 1, 0), Tile(Color.BLUE, 2, 0)]),
        TileSet(type=SetType.RUN, tiles=[Tile(Color.RED, 1, 0), Tile(Color.RED, 2, 0)]),
        TileSet(type=SetType.RUN, tiles=[Tile(Color.BLACK, 1, 0), Tile(Color.BLACK, 2, 0)]),
    ]

    class _FakeRandom:
        def sample(self, population, k):
            return list(population[:k])

    # Act
    rack = puzzle_generator._sample_rack_from_sacrificed_sets(
        sacrificed_sets=sacrificed_sets,
        rack_size=4,
        rng=_FakeRandom(),
        max_rack_source_sets=2,
    )

    # Assert
    rack_colors = {tile.color for tile in rack}
    assert rack_colors <= {Color.BLUE, Color.RED}


def test_attempt_surfaces_split_solve_failure_reason(monkeypatch) -> None:
    # Arrange
    board_sets = [_sample_tileset(), _sample_tileset(), _sample_tileset()]
    rack_candidate = puzzle_generator._RackCandidate(
        remaining_board=board_sets,
        rack=[Tile(Color.RED, 4, 0) for _ in range(6)],
        complexity=_sample_complexity(candidate_set_count=20, estimated_ilp_columns=200),
    )

    monkeypatch.setattr(puzzle_generator, "_make_pool", lambda n_jokers=0: object())
    monkeypatch.setattr(puzzle_generator, "enumerate_runs", lambda pool: [])
    monkeypatch.setattr(puzzle_generator, "enumerate_groups", lambda pool: [])
    monkeypatch.setattr(puzzle_generator, "_pick_compatible_sets", lambda all_sets, n: board_sets)
    monkeypatch.setattr(puzzle_generator, "_assign_copy_ids", lambda sets: sets)
    monkeypatch.setattr(puzzle_generator, "_extract_rack", lambda *args, **kwargs: rack_candidate)
    monkeypatch.setattr(
        puzzle_generator,
        "solve",
        lambda *args, **kwargs: Solution(
            new_sets=[],
            placed_tiles=[],
            remaining_rack=list(rack_candidate.rack),
            solve_status="timeout_fallback",
        ),
    )

    # Act
    outcome = puzzle_generator._attempt_generate_with_reason(
        rng=__import__("random").Random(1),
        difficulty="expert",
        pregen=True,
    )

    # Assert
    assert outcome.result is None
    assert outcome.rejection_reason == "solve_timeout_fallback"


def test_generate_batch_prints_rejection_summary(monkeypatch, capsys) -> None:
    # Arrange
    outcomes = iter(
        [
            _WorkerResult(result=None, rejection_reason="rack_fail"),
            _WorkerResult(result=None, rejection_reason="candidate_cap_reject"),
            _WorkerResult(
                result=None,
                rejection_reason="solve_timeout_fallback",
                rack_size=6,
                tiles_placed=4,
                solve_status="timeout_fallback",
                solve_time_ms=123.0,
                disruption_score=39,
                chain_depth=2,
            ),
            _WorkerResult(
                result=puzzle_generator.PuzzleResult(
                    board_sets=[],
                    rack=[Tile(Color.BLUE, 1, 0)],
                    difficulty="expert",
                    disruption_score=40,
                    chain_depth=3,
                    is_unique=False,
                ),
                rejection_reason=None,
            ),
            _WorkerResult(result=None, rejection_reason="rack_fail"),
        ]
    )

    class _ImmediateFuture:
        def __init__(self, value: _WorkerResult) -> None:
            self.value = value

        def result(self) -> _WorkerResult:
            return self.value

        def __hash__(self) -> int:
            return id(self)

    class _FakePool:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, args):
            return _ImmediateFuture(next(outcomes))

    class _FakeStore:
        def __init__(self) -> None:
            self.stored = []

        def store(self, result, seed=None):
            self.stored.append((result, seed))

    monkeypatch.setattr(pregenerate, "ProcessPoolExecutor", lambda max_workers: _FakePool())
    monkeypatch.setattr(
        pregenerate,
        "wait",
        lambda keys, return_when: ({next(iter(keys))}, set()),
    )

    store = _FakeStore()

    # Act
    pregenerate._generate_batch(
        store=store,
        difficulty="expert",
        count=1,
        workers=1,
        sync_every=10,
        sync_cmd=None,
        progress_every_attempts=100,
        progress_every_seconds=30.0,
        verbose_attempts=False,
    )

    output = capsys.readouterr().out

    # Assert
    assert len(store.stored) == 1
    assert "Rejections:" in output
    assert "rack_fail=1" in output
    assert "candidate_cap_reject=1" in output
    assert "solve_timeout_fallback=1" in output
    assert "Solved failures:" in output
    assert "Best near miss:" in output
