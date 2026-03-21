"""FastAPI application entry point.

Phase 1 scope: health check only.
Phase 2 will add POST /api/solve.

Run locally:
    uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = structlog.get_logger()

app = FastAPI(
    title="RummikubSolve API",
    version="0.1.0",
    description="Optimal Rummikub move solver — ILP-powered via HiGHS.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten to frontend origin in production
    allow_credentials=True,
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
# /api/solve — NOT YET IMPLEMENTED (Phase 2)
# ---------------------------------------------------------------------------
# from .models import SolveRequest, SolveResponse
# from solver.engine.solver import solve as run_solver
#
# @app.post("/api/solve", response_model=SolveResponse, tags=["solver"])
# async def solve_endpoint(request: SolveRequest) -> SolveResponse:
#     ...
