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
    # min_length=1 (not 3) to support v2 puzzle boards which may include
    # "orphaned" sets — partial tile groups left after individual tile removal.
    # The ILP solver handles these via its tile-conservation constraints.
    tiles: list[TileInput] = Field(min_length=1, max_length=13)


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


class TileWithOrigin(TileOutput):
    """TileOutput enriched with provenance: where did this tile come from?

    Added in Phase UI-1 (ui_rework.jsx migration step 1).
    """

    origin: Literal["hand"] | int
    # "hand"  → the tile was placed from the player's rack this turn
    # int     → 0-based index of the old board set this tile was taken from


class SetChangeResultSet(BaseModel):
    """The final state of a set after the solver has run."""

    type: Literal["run", "group"]
    tiles: list[TileWithOrigin]


class SetChange(BaseModel):
    """Describes what happened to one set as a result of the solver move.

    Replaces the fake ``moves[]`` step-sequence with a truthful per-set
    change manifest.  Each ``SetChange`` is always in a valid final state;
    the ``action`` field classifies the change type and the ``origin`` on
    every tile records its provenance.

    Added in Phase UI-1 (ui_rework.jsx migration step 1).
    """

    action: Literal["new", "extended", "rearranged", "unchanged"]
    # "new"        → every tile came from the rack (entirely new set)
    # "extended"   → rack tiles added to one existing board set
    # "rearranged" → tiles moved from one or more old sets, possibly with rack tiles
    # "unchanged"  → set identical to an existing board set, nothing added

    result_set: SetChangeResultSet

    source_set_indices: list[int] | None
    # null for "new" and "unchanged"; 0-based old-board-set indices for others

    source_description: str | None
    # Human-readable description of the source set(s), mainly for "rearranged".
    # e.g. "Set 1: Red 3, Red 4, Red 5, Red 6"


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
    # Phase UI-1: per-set change manifest with tile provenance.
    # Kept alongside moves[] / new_board[] for backward compatibility.
    set_changes: list[SetChange] = []


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
    sets_to_remove: int = Field(3, ge=1, le=8)  # sets to sacrifice (expanded from 5 to 8)
    min_board_sets: int = Field(8, ge=5, le=25)  # board sets before sacrifice
    max_board_sets: int = Field(14, ge=5, le=25)  # board sets before sacrifice
    min_chain_depth: int = Field(0, ge=0, le=4)  # minimum solution chain depth
    min_disruption: int = Field(0, ge=0, le=60)  # minimum disruption score


class PuzzleResponse(BaseModel):
    board_sets: list[BoardSetInput]
    rack: list[TileInput]
    difficulty: str
    tile_count: int
    disruption_score: int
    chain_depth: int = 0  # Phase 3: longest rearrangement chain depth
    is_unique: bool = True  # Phase 3: solution uniqueness verified for Expert/Nightmare
    puzzle_id: str = ""  # Phase 5: UUID for pool-drawn puzzles; "" for live-generated
    # Phase 4 (v2 generator) — populated when generator_version="v2"; 0.0/"v1" otherwise.
    composite_score: float = 0.0
    branching_factor: float = 0.0
    deductive_depth: float = 0.0
    red_herring_density: float = 0.0
    working_memory_load: float = 0.0
    tile_ambiguity: float = 0.0
    solution_fragility: float = 0.0
    generator_version: str = "v1"


class TelemetryTileInput(BaseModel):
    color: Literal["blue", "red", "black", "yellow"] | None = None
    number: int | None = None
    joker: bool = False


class TelemetryRequest(BaseModel):
    event_type: Literal[
        "puzzle_loaded",
        "tile_placed",
        "tile_moved",
        "tile_returned_to_rack",
        "undo_pressed",
        "puzzle_solved",
    ]
    event_at: str
    puzzle_id: str = ""
    difficulty: str
    generator_version: str
    composite_score: float
    branching_factor: float
    deductive_depth: float
    red_herring_density: float
    working_memory_load: float
    tile_ambiguity: float
    solution_fragility: float
    disruption_score: int
    chain_depth: int
    tile: TelemetryTileInput | None = None
    from_row: int | None = None
    from_col: int | None = None
    to_row: int | None = None
    to_col: int | None = None
    elapsed_ms: int | None = Field(default=None, ge=0)
    move_count: int | None = Field(default=None, ge=0)
    undo_count: int | None = Field(default=None, ge=0)
    redo_count: int | None = Field(default=None, ge=0)
    commit_count: int | None = Field(default=None, ge=0)
    revert_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_event_payload(self) -> TelemetryRequest:
        if self.event_type == "tile_placed":
            if self.tile is None or self.to_row is None or self.to_col is None:
                raise ValueError("tile_placed requires tile, to_row, and to_col.")
        elif self.event_type == "tile_moved":
            if (
                self.tile is None
                or self.from_row is None
                or self.from_col is None
                or self.to_row is None
                or self.to_col is None
            ):
                raise ValueError(
                    "tile_moved requires tile, from_row, from_col, to_row, and to_col."
                )
        elif self.event_type == "tile_returned_to_rack":
            if self.tile is None:
                raise ValueError("tile_returned_to_rack requires tile.")
        elif self.event_type == "puzzle_solved" and (
            self.elapsed_ms is None or self.move_count is None or self.undo_count is None
        ):
            raise ValueError("puzzle_solved requires elapsed_ms, move_count, and undo_count.")
        return self


class TelemetryResponse(BaseModel):
    status: Literal["ok"]
