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
    version="0.6.0",
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
from solver.models.board_state import BoardState  # noqa: E402
from solver.models.tile import Color, Tile  # noqa: E402
from solver.models.tileset import SetType, TileSet  # noqa: E402

from .models import (  # noqa: E402  (import after app init is intentional)
    BoardSetOutput,
    MoveOutput,
    SolveRequest,
    SolveResponse,
    TileOutput,
)


def _tile_input_to_domain(ti: object) -> Tile:
    """Convert a TileInput API model to a domain Tile."""
    from .models import TileInput

    assert isinstance(ti, TileInput)
    if ti.joker:
        return Tile.joker(copy_id=0)
    assert ti.color is not None and ti.number is not None
    return Tile(color=Color(ti.color), number=ti.number, copy_id=0)


def _tile_to_output(t: Tile) -> TileOutput:
    return TileOutput(
        color=t.color.value if t.color is not None else None,
        number=t.number,
        joker=t.is_joker,
        copy_id=t.copy_id,
    )


@app.post("/api/solve", response_model=SolveResponse, tags=["solver"])
async def solve_endpoint(request: SolveRequest) -> SolveResponse:
    """Solve a Rummikub board state and return the optimal move.

    Places the maximum number of rack tiles while keeping all board tiles in
    valid sets. Returns the new board arrangement and remaining rack tiles.
    Solve time is typically <100 ms.
    """
    logger.info("solve_request", rack_size=len(request.rack), board_sets=len(request.board))

    # Convert API models → domain models.
    try:
        rack = [_tile_input_to_domain(t) for t in request.rack]
        board_sets: list[TileSet] = []
        for bs in request.board:
            tiles = [_tile_input_to_domain(t) for t in bs.tiles]
            board_sets.append(TileSet(type=SetType(bs.type), tiles=tiles))
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

    # Build the set of placed-tile keys for new_tile_indices annotation.
    placed_key_set = {(t.color, t.number, t.copy_id, t.is_joker) for t in solution.placed_tiles}

    new_board: list[BoardSetOutput] = []
    for ts in solution.new_sets:
        tile_outputs = [_tile_to_output(t) for t in ts.tiles]
        new_tile_indices = [
            i
            for i, t in enumerate(ts.tiles)
            if (t.color, t.number, t.copy_id, t.is_joker) in placed_key_set
        ]
        new_board.append(
            BoardSetOutput(
                type=ts.type.value,
                tiles=tile_outputs,
                new_tile_indices=new_tile_indices,
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
