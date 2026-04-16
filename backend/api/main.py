"""FastAPI application entry point.

Phase 2 scope: health check + POST /api/solve.

Run locally:
    uvicorn api.main:app --reload --port 8000

Environment variables (see .env.example at the repo root):
    SENTRY_DSN       — Sentry DSN; leave empty to disable error reporting.
    ENVIRONMENT      — "development" (default) or "production".
    ALLOWED_ORIGIN   — CORS allowed origin; defaults to "*" (all origins).
"""

from __future__ import annotations

import logging
import os
from collections import Counter
from functools import lru_cache
from json import loads
from pathlib import Path
from typing import Literal, cast

import sentry_sdk
import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

_ENV = os.getenv("ENVIRONMENT", "development")
_SENTRY_DSN = os.getenv("SENTRY_DSN", "")

# ---------------------------------------------------------------------------
# Sentry — initialise before anything else so startup errors are captured
# ---------------------------------------------------------------------------

if _SENTRY_DSN:
    sentry_sdk.init(
        dsn=_SENTRY_DSN,
        environment=_ENV,
        traces_sample_rate=0.1,  # sample 10 % of transactions for performance
        send_default_pii=False,
    )

# ---------------------------------------------------------------------------
# Logging (structlog)
# — JSON renderer in production; colored console in development
# ---------------------------------------------------------------------------

logging.basicConfig(format="%(message)s", level=logging.INFO)
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        (
            structlog.dev.ConsoleRenderer()
            if _ENV == "development"
            else structlog.processors.JSONRenderer()
        ),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="RummikubSolve API",
    version="0.31.0",
    description="Optimal Rummikub move solver — ILP-powered via HiGHS.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

# allow_credentials cannot be True when allow_origins is the wildcard "*"
# (CORS specification §3.2 — browsers will reject such responses).
_ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _ALLOWED_ORIGIN == "*" else [_ALLOWED_ORIGIN],
    allow_credentials=(_ALLOWED_ORIGIN != "*"),
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe — used by Docker health checks and uptime monitors."""
    return {"status": "ok", "version": app.version}


# ---------------------------------------------------------------------------
# /api/solve
# ---------------------------------------------------------------------------

from solver.config.rules import RulesConfig  # noqa: E402
from solver.engine.solver import solve as _run_solver  # noqa: E402
from solver.generator.puzzle_generator import (  # noqa: E402
    PuzzleGenerationError,
    PuzzleResult,
    generate_puzzle,
)
from solver.generator.puzzle_store import PuzzleStore  # noqa: E402
from solver.generator.set_changes import (  # noqa: E402
    build_set_changes as _build_set_changes_data,
)
from solver.generator.telemetry_store import TelemetryStore  # noqa: E402
from solver.models.board_state import BoardState  # noqa: E402
from solver.models.tile import Color, Tile  # noqa: E402
from solver.models.tileset import SetType, TileSet  # noqa: E402

from .models import (  # noqa: E402  (import after app init is intentional)
    BoardSetInput,
    BoardSetOutput,
    CalibrationBatchResponse,
    MoveOutput,
    PuzzleRequest,
    PuzzleResponse,
    SetChange,
    SetChangeResultSet,
    SolveRequest,
    SolveResponse,
    TelemetryRequest,
    TelemetryResponse,
    TileInput,
    TileOutput,
    TileWithOrigin,
)

_CALIBRATION_BATCH_DIR = (
    Path(__file__).resolve().parents[1] / "solver" / "generator" / "calibration_batches"
)


@lru_cache(maxsize=8)
def _load_calibration_batch(batch_name: str) -> CalibrationBatchResponse:
    path = _CALIBRATION_BATCH_DIR / f"{batch_name}.json"
    if not path.exists():
        raise FileNotFoundError(batch_name)
    data = loads(path.read_text(encoding="utf-8"))
    return CalibrationBatchResponse(**data)


def _assign_copy_ids(tile_inputs: list[TileInput]) -> list[Tile]:
    """Convert a list of TileInput API models to domain Tiles with correct copy_ids.

    Tiles with the same (color, number, is_joker) are assigned copy_id=0 and
    copy_id=1 in order of appearance so the ILP can treat them as distinct
    physical tiles.
    """
    seen: Counter[tuple[Color | None, int | None, bool]] = Counter()
    result: list[Tile] = []
    for ti in tile_inputs:
        if ti.joker:
            key: tuple[Color | None, int | None, bool] = (None, None, True)
            copy_id = seen[key]
            seen[key] += 1
            result.append(Tile.joker(copy_id=copy_id))
        else:
            assert ti.color is not None and ti.number is not None
            color = Color(ti.color)
            key = (color, ti.number, False)
            copy_id = seen[key]
            seen[key] += 1
            result.append(Tile(color=color, number=ti.number, copy_id=copy_id))
    return result


def _tile_to_output(t: Tile) -> TileOutput:
    return TileOutput(
        color=t.color.value if t.color is not None else None,
        number=t.number,
        joker=t.is_joker,
        copy_id=t.copy_id,
    )


# ---------------------------------------------------------------------------
# Phase UI-1: adapter — convert solver SetChangeData → Pydantic SetChange
# ---------------------------------------------------------------------------


def _build_set_changes(
    old_board_sets: list[TileSet],
    new_sets: list[TileSet],
    placed_tiles: list[Tile],
    old_set_sigs: list[Counter[tuple[Color | None, int | None, bool]]],
) -> list[SetChange]:
    """Thin adapter: call the pure solver logic and convert to Pydantic models."""
    data_list = _build_set_changes_data(old_board_sets, new_sets, placed_tiles, old_set_sigs)
    result: list[SetChange] = []
    for d in data_list:
        tiles_with_origin = [
            TileWithOrigin(
                color=t.color.value if t.color is not None else None,
                number=t.number,
                joker=t.is_joker,
                copy_id=t.copy_id,
                origin=t.origin,
            )
            for t in d.tiles
        ]
        result.append(
            SetChange(
                action=d.action,
                result_set=SetChangeResultSet(
                    type=cast(Literal["run", "group"], d.set_type),
                    tiles=tiles_with_origin,
                ),
                source_set_indices=(
                    list(d.source_set_indices) if d.source_set_indices is not None else None
                ),
                source_description=d.source_description,
            )
        )
    return result


@app.post("/api/solve", response_model=SolveResponse, tags=["solver"])
def solve_endpoint(request: SolveRequest) -> SolveResponse:
    """Solve a Rummikub board state and return the optimal move.

    Places the maximum number of rack tiles while keeping all board tiles in
    valid sets. Returns the new board arrangement and remaining rack tiles.
    Solve time is typically <100 ms.
    """
    logger.info("solve_request", rack_size=len(request.rack), board_sets=len(request.board))

    # Convert API models → domain models.
    try:
        # Assign copy_ids across ALL tiles (board + rack) together so that
        # duplicate (color, number) tiles get distinct copy_ids (0 and 1).
        all_tile_inputs = [t for bs in request.board for t in bs.tiles] + list(request.rack)
        all_domain_tiles = _assign_copy_ids(all_tile_inputs)
        board_tile_count = sum(len(bs.tiles) for bs in request.board)
        board_tiles_flat = all_domain_tiles[:board_tile_count]
        rack = all_domain_tiles[board_tile_count:]
        board_sets: list[TileSet] = []
        offset = 0
        for bs in request.board:
            n = len(bs.tiles)
            tiles_slice = board_tiles_flat[offset : offset + n]
            board_sets.append(TileSet(type=SetType(bs.type), tiles=tiles_slice))
            offset += n
    except (ValueError, AssertionError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    rules = RulesConfig(
        initial_meld_threshold=request.rules.initial_meld_threshold,
        is_first_turn=request.rules.is_first_turn,
        allow_wrap_runs=request.rules.allow_wrap_runs,
    )

    state = BoardState(board_sets=board_sets, rack=rack)

    try:
        solution = _run_solver(state, rules)
    except ValueError as exc:
        logger.error("solve_failed", error=str(exc))
        raw = str(exc).lower()
        if "infeasible" in raw or "invalid" in raw:
            msg = (
                "The board has no valid arrangement — check that every set is a legal run or group."  # noqa: E501
            )
        else:
            msg = str(exc)
        raise HTTPException(status_code=422, detail=msg) from exc

    # Counter of placed-tile keys — consumed one-by-one so duplicate tiles
    # (e.g. two Red 5s, one from rack and one from board) are highlighted correctly.
    placed_key_counter: Counter[tuple[Color | None, int | None, int, bool]] = Counter(
        (t.color, t.number, t.copy_id, t.is_joker) for t in solution.placed_tiles
    )

    # Multiset signatures of the OLD board sets, used to detect unchanged sets.
    old_set_sigs: list[Counter[tuple[Color | None, int | None, bool]]] = [
        Counter((t.color, t.number, t.is_joker) for t in ts.tiles) for ts in state.board_sets
    ]

    new_board: list[BoardSetOutput] = []
    for ts in solution.new_sets:
        tile_outputs = [_tile_to_output(t) for t in ts.tiles]

        # Match each tile against the counter; consume one count per match.
        new_tile_indices: list[int] = []
        for i, t in enumerate(ts.tiles):
            key = (t.color, t.number, t.copy_id, t.is_joker)
            if placed_key_counter.get(key, 0) > 0:
                new_tile_indices.append(i)
                placed_key_counter[key] -= 1

        # Unchanged = no rack tiles added AND tile multiset matches an old board set.
        new_sig = Counter((t.color, t.number, t.is_joker) for t in ts.tiles)
        is_unchanged = (not new_tile_indices) and (new_sig in old_set_sigs)

        new_board.append(
            BoardSetOutput(
                type=ts.type.value,
                tiles=tile_outputs,
                new_tile_indices=new_tile_indices,
                is_unchanged=is_unchanged,
            )
        )

    _status: Literal["solved", "no_solution"] = (
        "solved" if solution.tiles_placed > 0 else "no_solution"
    )

    # Phase UI-1: build the per-set change manifest with tile provenance.
    set_changes = _build_set_changes(
        old_board_sets=state.board_sets,
        new_sets=solution.new_sets,
        placed_tiles=solution.placed_tiles,
        old_set_sigs=old_set_sigs,
    )

    return SolveResponse(
        status=_status,
        tiles_placed=solution.tiles_placed,
        tiles_remaining=solution.tiles_remaining,
        solve_time_ms=round(solution.solve_time_ms, 2),
        is_optimal=solution.is_optimal,
        is_first_turn=request.rules.is_first_turn,
        new_board=new_board,
        remaining_rack=[_tile_to_output(t) for t in solution.remaining_rack],
        moves=[
            MoveOutput(action=m.action, description=m.description, set_index=m.set_index)
            for m in solution.moves
        ],
        set_changes=set_changes,
    )


# ---------------------------------------------------------------------------
# /api/puzzle
# ---------------------------------------------------------------------------


@app.post("/api/puzzle", response_model=PuzzleResponse, tags=["solver"])
def puzzle_endpoint(request: PuzzleRequest) -> PuzzleResponse:
    """Generate a random, pre-verified Rummikub practice puzzle.

    Returns a board state and a rack of tiles that can always be fully placed.
    Difficulty controls how many tiles are in the rack and how complex the
    required placement is.
    """
    logger.info(
        "puzzle_request",
        difficulty=request.difficulty,
        seed=request.seed,
        sets_to_remove=request.sets_to_remove,
        seen_ids=len(request.seen_ids),
    )

    def _tile_to_input(tile: Tile) -> TileInput:
        if tile.is_joker:
            return TileInput(joker=True)
        if tile.color is None or tile.number is None:
            raise ValueError(f"Non-joker tile has no color/number: {tile!r}")
        return TileInput(color=tile.color.value, number=tile.number)

    def _result_to_response(result: PuzzleResult, puzzle_id: str = "") -> PuzzleResponse:
        return PuzzleResponse(
            board_sets=[
                BoardSetInput(
                    type=ts.type.value,
                    tiles=[_tile_to_input(tile) for tile in ts.tiles],
                )
                for ts in result.board_sets
            ],
            rack=[_tile_to_input(tile) for tile in result.rack],
            difficulty=result.difficulty,
            seed=result.seed,
            tile_count=len(result.rack),
            disruption_score=result.disruption_score,
            chain_depth=result.chain_depth,
            is_unique=result.is_unique,
            puzzle_id=puzzle_id,
            composite_score=result.composite_score,
            branching_factor=result.branching_factor,
            deductive_depth=result.deductive_depth,
            red_herring_density=result.red_herring_density,
            working_memory_load=result.working_memory_load,
            tile_ambiguity=result.tile_ambiguity,
            solution_fragility=result.solution_fragility,
            generator_version=result.generator_version,
        )

    # Phase 5: for expert/nightmare try the pre-generated pool first.
    if request.difficulty in ("expert", "nightmare"):
        store = PuzzleStore()
        drawn = store.draw(request.difficulty, exclude_ids=request.seen_ids)
        store.close()
        if drawn is not None:
            result, puzzle_id = drawn
            logger.info(
                "puzzle_pool_hit",
                difficulty=request.difficulty,
                puzzle_id=puzzle_id,
            )
            return _result_to_response(result, puzzle_id)
        logger.info("puzzle_pool_empty", difficulty=request.difficulty)
        # Pool exhausted — fall through to live generation below.

    try:
        result = generate_puzzle(
            difficulty=request.difficulty,
            seed=request.seed,
            sets_to_remove=request.sets_to_remove,
            min_board_sets=request.min_board_sets,
            max_board_sets=request.max_board_sets,
            min_chain_depth=request.min_chain_depth,
            min_disruption=request.min_disruption,
            # Phase 5: use v2 pipeline for standard tiers (§9.6 default switch).
            # "custom" stays on v1 — its fine-grained params are v1-only.
            generator_version="v1" if request.difficulty == "custom" else "v2",
        )
    except PuzzleGenerationError as exc:
        logger.warning("puzzle_generation_failed", error=str(exc))
        raise HTTPException(
            status_code=503,
            detail="Could not generate a puzzle — please try again.",
        ) from exc

    # Persist the live-generated puzzle so telemetry events can be linked by puzzle_id.
    store = PuzzleStore()
    puzzle_id = store.store(result)
    store.close()
    return _result_to_response(result, puzzle_id)


@app.post("/api/telemetry", response_model=TelemetryResponse, tags=["meta"])
def telemetry_endpoint(request: TelemetryRequest) -> TelemetryResponse:
    """Persist one play-mode telemetry event for later difficulty calibration."""
    store = TelemetryStore()
    try:
        event_id = store.store(request.model_dump())
    finally:
        store.close()

    logger.info(
        "telemetry_recorded",
        event_id=event_id,
        event_type=request.event_type,
        puzzle_id=request.puzzle_id,
        attempt_id=request.attempt_id,
        difficulty=request.difficulty,
        seed=request.seed,
        batch_name=request.batch_name,
        batch_index=request.batch_index,
        generator_version=request.generator_version,
    )
    return TelemetryResponse(status="ok")


@app.get(
    "/api/calibration-batch/{batch_name}", response_model=CalibrationBatchResponse, tags=["meta"]
)
def calibration_batch_endpoint(batch_name: str) -> CalibrationBatchResponse:
    """Return a fixed-seed developer calibration batch manifest."""
    try:
        return _load_calibration_batch(batch_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown calibration batch.") from exc
