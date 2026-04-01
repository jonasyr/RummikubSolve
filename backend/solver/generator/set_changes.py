"""Build the per-set change manifest (set_changes) for the solve response.

This module is pure business logic — it has no FastAPI or HTTP dependencies —
so it can be imported both by api.main and by the test suite without pulling
in the entire web stack.

Added in Phase UI-1 (ui_rework.jsx migration step 1).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from solver.models.tile import Color, Tile
from solver.models.tileset import TileSet

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Public types — re-exported so callers can import from here rather than
# duplicating the type definition.
# ---------------------------------------------------------------------------

TileOrigin = Literal["hand"] | int  # "hand" or 0-based old board-set index


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------

# We deliberately use plain dataclasses rather than Pydantic here to keep
# the solver package independent of the API layer.  api.main converts these
# into Pydantic models before serialisation.


@dataclass(frozen=True)
class TileWithOriginData:
    """A resolved tile together with its provenance."""

    color: Color | None
    number: int | None
    is_joker: bool
    copy_id: int
    origin: TileOrigin


@dataclass(frozen=True)
class SetChangeData:
    """Per-set change entry produced by :func:`build_set_changes`."""

    action: Literal["new", "extended", "rearranged", "unchanged"]
    set_type: str  # "run" | "group"
    tiles: tuple[TileWithOriginData, ...]
    source_set_indices: tuple[int, ...] | None
    source_description: str | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def build_old_tile_origin_map(
    old_board_sets: list[TileSet],
) -> dict[tuple[Color | None, int | None, int, bool], int]:
    """Return a map from each board tile's physical key → its old board-set index.

    Each physical Rummikub tile is identified by (color, number, copy_id, is_joker).
    Because every tile appears in exactly one board set, this is a bijection.
    """
    result: dict[tuple[Color | None, int | None, int, bool], int] = {}
    for old_idx, ts in enumerate(old_board_sets):
        for t in ts.tiles:
            key: tuple[Color | None, int | None, int, bool] = (
                t.color,
                t.number,
                t.copy_id,
                t.is_joker,
            )
            result[key] = old_idx
    return result


def _describe_tile(t: Tile) -> str:
    """Human-readable single-tile description, e.g. 'Red 5' or 'Joker'."""
    if t.is_joker:
        return "Joker"
    color_name = t.color.value.capitalize() if t.color is not None else "?"
    return f"{color_name} {t.number}"


def build_set_changes(
    old_board_sets: list[TileSet],
    new_sets: list[TileSet],
    placed_tiles: list[Tile],
    old_set_sigs: list[Counter[tuple[Color | None, int | None, bool]]],
) -> list[SetChangeData]:
    """Build the per-set change manifest for a solver solution.

    For every set in ``new_sets`` the function determines:
    - ``action``              — what type of change occurred
    - per-tile ``origin``     — "hand" if placed from the rack, else old-set index
    - ``source_set_indices``  — which old sets contributed tiles
    - ``source_description``  — human-readable description (for rearranged sets)

    Parameters
    ----------
    old_board_sets:
        The board state *before* the solver ran.
    new_sets:
        The board state *after* the solver ran (from ``Solution.new_sets``).
    placed_tiles:
        Tiles the solver placed from the rack (from ``Solution.placed_tiles``).
    old_set_sigs:
        Pre-computed multiset signatures of ``old_board_sets`` (passed in from
        the caller so they are only computed once across :func:`build_set_changes`
        and the existing ``new_board`` construction logic).
    """
    old_tile_origin = build_old_tile_origin_map(old_board_sets)

    # Independent counter — we consume from a copy so the caller's counter
    # (used for new_tile_indices) is not affected.
    placed_counter: Counter[tuple[Color | None, int | None, int, bool]] = Counter(
        (t.color, t.number, t.copy_id, t.is_joker) for t in placed_tiles
    )

    result: list[SetChangeData] = []

    for ts in new_sets:
        origins: list[TileOrigin] = []
        tiles_with_origin: list[TileWithOriginData] = []

        for t in ts.tiles:
            key: tuple[Color | None, int | None, int, bool] = (
                t.color,
                t.number,
                t.copy_id,
                t.is_joker,
            )
            if placed_counter.get(key, 0) > 0:
                origin: TileOrigin = "hand"
                placed_counter[key] -= 1
            else:
                origin = old_tile_origin.get(key, -1)
            origins.append(origin)
            tiles_with_origin.append(
                TileWithOriginData(
                    color=t.color,
                    number=t.number,
                    is_joker=t.is_joker,
                    copy_id=t.copy_id,
                    origin=origin,
                )
            )

        board_origins: list[int] = [o for o in origins if o != "hand"]
        hand_count = len(origins) - len(board_origins)
        unique_source_sets: list[int] = sorted(set(board_origins))

        new_sig: Counter[tuple[Color | None, int | None, bool]] = Counter(
            (t.color, t.number, t.is_joker) for t in ts.tiles
        )
        is_unch = (hand_count == 0) and (new_sig in old_set_sigs)

        action: Literal["new", "extended", "rearranged", "unchanged"]
        source_set_indices: tuple[int, ...] | None
        source_description: str | None

        if not board_origins:
            action = "new"
            source_set_indices = None
            source_description = None
        elif hand_count == 0:
            if is_unch:
                action = "unchanged"
                source_set_indices = None
                source_description = None
            else:
                action = "rearranged"
                source_set_indices = tuple(unique_source_sets)
                desc_parts = [
                    f"Set {i + 1}: {', '.join(_describe_tile(t) for t in old_board_sets[i].tiles)}"
                    for i in unique_source_sets
                    if i < len(old_board_sets)
                ]
                source_description = "; ".join(desc_parts) or None
        else:
            action = "extended" if len(unique_source_sets) == 1 else "rearranged"
            source_set_indices = tuple(unique_source_sets)
            source_description = None

        result.append(
            SetChangeData(
                action=action,
                set_type=ts.type.value,
                tiles=tuple(tiles_with_origin),
                source_set_indices=source_set_indices,
                source_description=source_description,
            )
        )

    return result
