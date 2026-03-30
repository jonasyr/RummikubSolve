"""Pydantic v2 request and response models for the RummikubSolve API.

These are the public contract between the frontend and the backend.
Keep in sync with frontend/src/types/api.ts.

Blueprint §4.3 — API Design.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class TileInput(BaseModel):
    """A single tile in an API request.

    Either (color + number) for a normal tile, or joker=true.
    """

    color: Literal["blue", "red", "black", "yellow"] | None = None
    number: int | None = None
    joker: bool = False

    @model_validator(mode="after")
    def validate_tile(self) -> TileInput:
        if self.joker:
            if self.color is not None or self.number is not None:
                raise ValueError("Joker tiles must not have a color or number.")
        else:
            if self.color is None or self.number is None:
                raise ValueError("Non-joker tiles require both 'color' and 'number'.")
            if not (1 <= (self.number or 0) <= 13):
                raise ValueError("Tile number must be between 1 and 13.")
        return self


class BoardSetInput(BaseModel):
    type: Literal["run", "group"]
    tiles: list[TileInput] = Field(min_length=3, max_length=13)


class RulesInput(BaseModel):
    initial_meld_threshold: int = 30
    is_first_turn: bool = False
    allow_wrap_runs: bool = False
    # joker_retrieval is intentionally omitted from this API model until the
    # ILP formulation implements it (see solver/config/rules.py TODO).
    # Any extra field sent by clients is silently ignored by Pydantic.


class SolveRequest(BaseModel):
    board: list[BoardSetInput] = Field(default=[], max_length=50)
    rack: list[TileInput] = Field(max_length=104)
    rules: RulesInput = RulesInput()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class TileOutput(BaseModel):
    color: Literal["blue", "red", "black", "yellow"] | None
    number: int | None
    joker: bool
    copy_id: int


class BoardSetOutput(BaseModel):
    type: Literal["run", "group"]
    tiles: list[TileOutput]
    new_tile_indices: list[int] = []  # 0-based positions of newly placed tiles
    is_unchanged: bool = False  # True when set is identical to an existing board set


class MoveOutput(BaseModel):
    action: str
    description: str
    set_index: int | None = None


class SolveResponse(BaseModel):
    # "error" is intentionally absent: errors are raised as HTTPException (422/503)
    # and never returned in the response body.
    status: Literal["solved", "no_solution"]
    tiles_placed: int
    tiles_remaining: int
    solve_time_ms: float
    is_optimal: bool
    is_first_turn: bool = False
    new_board: list[BoardSetOutput]
    remaining_rack: list[TileOutput]
    moves: list[MoveOutput]


# ---------------------------------------------------------------------------
# Puzzle models
# ---------------------------------------------------------------------------


class PuzzleRequest(BaseModel):
    difficulty: Literal["easy", "medium", "hard", "expert", "nightmare", "custom"] = "medium"
    seed: int | None = None
    # Phase 5: UUIDs of puzzles the client has already seen; used to avoid duplicates
    # when drawing from the pre-generated pool.  Capped at 500 to bound request size.
    seen_ids: list[str] = Field(default_factory=list, max_length=500)
    # Phase 7a: Custom mode parameters — ignored for all non-custom difficulties.
    sets_to_remove: int = Field(3, ge=1, le=8)    # sets to sacrifice (expanded from 5 to 8)
    min_board_sets: int = Field(8, ge=5, le=25)   # board sets before sacrifice
    max_board_sets: int = Field(14, ge=5, le=25)  # board sets before sacrifice
    min_chain_depth: int = Field(0, ge=0, le=4)   # minimum solution chain depth
    min_disruption: int = Field(0, ge=0, le=60)   # minimum disruption score


class PuzzleResponse(BaseModel):
    board_sets: list[BoardSetInput]
    rack: list[TileInput]
    difficulty: str
    tile_count: int
    disruption_score: int
    chain_depth: int = 0    # Phase 3: longest rearrangement chain depth
    is_unique: bool = True  # Phase 3: solution uniqueness verified for Expert/Nightmare
    puzzle_id: str = ""     # Phase 5: UUID for pool-drawn puzzles; "" for live-generated
