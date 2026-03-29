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
from typing import Literal

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
    version="0.27.0",
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
    generate_puzzle,
)
from solver.models.board_state import BoardState  # noqa: E402
from solver.models.tile import Color, Tile  # noqa: E402
from solver.models.tileset import SetType, TileSet  # noqa: E402

from .models import (  # noqa: E402  (import after app init is intentional)
    BoardSetInput,
    BoardSetOutput,
    MoveOutput,
    PuzzleRequest,
    PuzzleResponse,
    SolveRequest,
    SolveResponse,
    TileInput,
    TileOutput,
)


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
    )

    try:
        result = generate_puzzle(
            difficulty=request.difficulty,
            seed=request.seed,
            sets_to_remove=request.sets_to_remove,
        )
    except PuzzleGenerationError as exc:
        logger.warning("puzzle_generation_failed", error=str(exc))
        raise HTTPException(
            status_code=503,
            detail="Could not generate a puzzle — please try again.",
        ) from exc

    def _tile_to_input(tile: Tile) -> TileInput:
        if tile.is_joker:
            return TileInput(joker=True)
        if tile.color is None or tile.number is None:
            raise ValueError(f"Non-joker tile has no color/number: {tile!r}")
        return TileInput(color=tile.color.value, number=tile.number)

    board_sets_input: list[BoardSetInput] = [
        BoardSetInput(
            type=ts.type.value,
            tiles=[_tile_to_input(tile) for tile in ts.tiles],
        )
        for ts in result.board_sets
    ]
    rack_input: list[TileInput] = [_tile_to_input(tile) for tile in result.rack]

    return PuzzleResponse(
        board_sets=board_sets_input,
        rack=rack_input,
        difficulty=result.difficulty,
        tile_count=len(result.rack),
        disruption_score=result.disruption_score,
        chain_depth=result.chain_depth,
        is_unique=result.is_unique,
    )
