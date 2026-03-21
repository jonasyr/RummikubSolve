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
        if not self.joker:
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


class SolveRequest(BaseModel):
    board: list[BoardSetInput] = Field(default=[], max_length=50)
    rack: list[TileInput] = Field(max_length=104)
    rules: RulesInput = RulesInput()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class TileOutput(BaseModel):
    color: str | None
    number: int | None
    joker: bool
    copy_id: int


class BoardSetOutput(BaseModel):
    type: str
    tiles: list[TileOutput]
    new_tile_indices: list[int] = []  # 0-based positions of newly placed tiles


class MoveOutput(BaseModel):
    action: str
    description: str
    set_index: int | None = None


class SolveResponse(BaseModel):
    status: Literal["solved", "no_solution", "error"]
    tiles_placed: int
    tiles_remaining: int
    solve_time_ms: float
    is_optimal: bool
    is_first_turn: bool = False
    new_board: list[BoardSetOutput]
    remaining_rack: list[TileOutput]
    moves: list[MoveOutput]
