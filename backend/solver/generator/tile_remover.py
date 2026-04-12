"""Strategic tile removal for puzzle generation.

Phase 2 of the puzzle generation rebuild. Takes a valid board produced by
BoardBuilder and removes individual tiles one at a time to form the rack,
choosing tiles that maximise cascading rearrangement requirements.

This is the key difference from the old "sacrifice" approach:
  - Old: remove complete sets; rack = sample of those sets' tiles
  - New: remove one tile at a time; each removal is verified solvable;
         tiles are chosen to break sets and force orphan rearrangement

Blueprint: "Puzzle Generation System — Full Rebuild Implementation Plan"
           §3 Phase 2 (TileRemover — Strategic Tile Removal)
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

from ..engine.solver import solve
from ..generator.set_enumerator import enumerate_groups, enumerate_runs
from ..models.board_state import BoardState, Solution
from ..models.tile import Tile
from ..models.tileset import TileSet
from ..validator.rule_checker import is_valid_set

# Short timeout for each intermediate solvability check during tile removal.
# Keeps the removal loop fast; a puzzle rejected here is just retried.
_REMOVAL_STEP_TIMEOUT = 2.0  # seconds

# If the whole removal phase takes longer than this, bail out with whatever
# tiles we have (may be below rack_size_range[0], which causes None return).
_TOTAL_ATTEMPT_TIMEOUT = 30.0  # seconds


@dataclass(frozen=True)
class RemovalCandidate:
    """A candidate tile for removal from the board, with pre-computed scores.

    All fields are computed once in _score_all_candidates() before any solver
    call, so the heuristics remain cheap even when the board is large.
    """

    set_index: int           # which board set the tile belongs to
    tile_index: int          # position within that set (used for index-safe removal)
    tile: Tile
    set_size_after: int      # len(parent set) - 1
    breaks_set: bool         # True if set_size_after < 3 (parent becomes invalid)
    orphan_count: int        # tiles left stranded on board if set breaks
    alternative_placements: int  # templates that contain a tile of this (color, number)
    cascade_estimate: float  # heuristic: expected rearrangement depth


@dataclass(frozen=True)
class RemovalStep:
    """Record of one committed tile removal — used for debugging and replay.

    state_before captures the full board + rack immediately before this tile
    was removed, allowing exact replay of the generation process from any step.
    """

    candidate: RemovalCandidate
    state_before: BoardState  # snapshot BEFORE this removal
    solver_result: Solution   # the solve() call that confirmed solvability


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def estimate_cascade_depth(
    board_sets: list[TileSet],
    tile_to_remove: Tile,
    set_index: int,
    all_templates: list[TileSet],
) -> float:
    """Estimate cascading rearrangement depth without running the solver.

    Heuristic: if removing tile_to_remove from board_sets[set_index] makes
    that set invalid (< 3 tiles), the remaining tiles are orphaned and must
    find new homes.  For each orphan, we count how many existing board sets
    can absorb it by simple extension (appending to the set and checking
    is_valid_set).  Fewer absorption options → more forced rearrangements →
    higher cascade estimate.

    Scoring per orphan:
      0 absorbers → +2.0  (must break other sets to place this tile)
      1 absorber  → +1.0  (forced placement, may chain-displace another tile)
      ≥2 absorbers → +0.5 (ambiguous; hard for human but not deeply cascading)

    If the parent set survives removal (≥ 3 tiles remain), cascade is low.

    Args:
        board_sets:      Current board state.
        tile_to_remove:  The tile being considered for removal.
                         Matched by object identity (``is``), not value equality.
        set_index:       Index of the set containing tile_to_remove.
        all_templates:   Valid set templates for the current pool (unused here
                         but kept in signature for consistency with the caller).

    Returns:
        A non-negative float; higher means more cascading rearrangement.
    """
    parent_set = board_sets[set_index]
    # Use object identity to exclude exactly this tile, not a value-equal copy.
    remaining_tiles = [t for t in parent_set.tiles if t is not tile_to_remove]

    if len(remaining_tiles) >= 3:
        # Parent set survives as a smaller (still valid) set — low disruption.
        return 0.5

    # Parent set breaks; remaining_tiles are orphaned on the board.
    orphans = remaining_tiles
    cascade = 0.0

    for orphan in orphans:
        absorb_count = 0
        for i, ts in enumerate(board_sets):
            if i == set_index:
                continue
            # Check whether appending the orphan to this set produces a valid set.
            # We create a temporary TileSet; no Tile objects are copied.
            extended = TileSet(type=ts.type, tiles=ts.tiles + [orphan])
            if is_valid_set(extended):
                absorb_count += 1

        if absorb_count == 0:
            cascade += 2.0
        elif absorb_count == 1:
            cascade += 1.0
        else:
            cascade += 0.5

    return cascade


def _score_all_candidates(
    board_sets: list[TileSet],
    all_templates: list[TileSet],
) -> list[RemovalCandidate]:
    """Score every board tile as a removal candidate.

    Iterates every tile on the board and computes:
      - Whether its removal would break the parent set (< 3 tiles left)
      - How many valid set templates contain a tile with the same (color, number)
      - The estimated cascade depth (via estimate_cascade_depth)

    Args:
        board_sets:    Current board state (no rack tiles included).
        all_templates: Valid set templates from the combined board+rack pool.

    Returns:
        List of RemovalCandidate, one per board tile.
    """
    candidates: list[RemovalCandidate] = []

    for si, ts in enumerate(board_sets):
        for ti, tile in enumerate(ts.tiles):
            set_size_after = len(ts.tiles) - 1
            breaks = set_size_after < 3
            orphan_count = set_size_after if breaks else 0

            # Count templates that contain any non-joker tile matching (color, number).
            alt_count = 0
            for tmpl in all_templates:
                for tmpl_tile in tmpl.tiles:
                    if (
                        not tmpl_tile.is_joker
                        and tmpl_tile.color == tile.color
                        and tmpl_tile.number == tile.number
                    ):
                        alt_count += 1
                        break  # count each template at most once

            cascade = estimate_cascade_depth(board_sets, tile, si, all_templates)

            candidates.append(
                RemovalCandidate(
                    set_index=si,
                    tile_index=ti,
                    tile=tile,
                    set_size_after=set_size_after,
                    breaks_set=breaks,
                    orphan_count=orphan_count,
                    alternative_placements=alt_count,
                    cascade_estimate=cascade,
                )
            )

    return candidates


def _apply_removal(
    board_sets: list[TileSet],
    candidate: RemovalCandidate,
) -> list[TileSet]:
    """Remove the candidate tile from the board, keeping orphaned sets intact.

    The tile is identified by its (set_index, tile_index) position rather than
    by object identity, so only the exact tile at that position is removed even
    if duplicate (color, number) tiles exist elsewhere on the board.

    Sets that become empty are dropped entirely.  Sets reduced to 1 or 2 tiles
    remain on the board as-is — the ILP solver handles orphaned tiles via its
    tile conservation constraints; rule_checker is NOT applied to the input.

    CRITICAL: The returned TileSets contain the same Tile object references as
    the input.  No new Tile instances are created.  This preserves id() identity
    required by the solver's timeout-fallback check (solver.py:132–134).

    Args:
        board_sets: Current board (not mutated).
        candidate:  The tile to remove.

    Returns:
        New list[TileSet] with the tile removed.
    """
    result: list[TileSet] = []
    for i, ts in enumerate(board_sets):
        if i == candidate.set_index:
            remaining = [
                t for j, t in enumerate(ts.tiles) if j != candidate.tile_index
            ]
            if remaining:  # drop the set if it becomes completely empty
                result.append(TileSet(type=ts.type, tiles=remaining))
        else:
            # Preserve the same Tile references; only wrap in a new list.
            result.append(TileSet(type=ts.type, tiles=list(ts.tiles)))
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class TileRemover:
    """Strategically removes tiles from a board to form the puzzle rack.

    Usage::

        board_sets = BoardBuilder.build(rng)
        result = TileRemover.remove(board_sets, rng, rack_size_range=(4, 6))
        if result is None:
            # Could not reach minimum rack size — retry with a new board
            ...
        remaining_board, rack, removal_log = result
    """

    @staticmethod
    def remove(
        board_sets: list[TileSet],
        rng: random.Random,
        rack_size_range: tuple[int, int],
        strategy: str = "maximize_cascade",
        solve_timeout: float = _REMOVAL_STEP_TIMEOUT,
        max_removal_attempts_per_tile: int = 5,
    ) -> tuple[list[TileSet], list[Tile], list[RemovalStep]] | None:
        """Remove tiles one at a time to form the rack.

        For each removal step, candidates are scored by cascade_estimate.  The
        top-30% by score are eligible for weighted-random selection.  The chosen
        tile is removed and solvability is verified with a short solver timeout.
        If the puzzle becomes unsolvable or the solver times out, the candidate
        is skipped and another is tried (up to max_removal_attempts_per_tile
        attempts per step).

        Tile identity is preserved throughout: no new Tile objects are created.
        This is required by the solver's id()-based board-tile tracking.

        Args:
            board_sets:                    A valid board from BoardBuilder.build().
            rng:                           Seeded Random for determinism.
            rack_size_range:               (min, max) tiles to put in the rack.
            strategy:                      "maximize_cascade" (default) or "random".
            solve_timeout:                 Seconds per intermediate solver call.
            max_removal_attempts_per_tile: Max candidates to try per removal step.

        Returns:
            (remaining_board, rack, removal_log) on success, or None if the
            minimum rack size could not be reached.
        """
        target_rack_size = rng.randint(*rack_size_range)

        # Shallow-copy board: new TileSet wrappers, same Tile object references.
        current_board: list[TileSet] = [
            TileSet(type=ts.type, tiles=list(ts.tiles)) for ts in board_sets
        ]
        rack: list[Tile] = []
        removal_log: list[RemovalStep] = []

        # Templates from board-only pool at start; updated after each commit.
        all_templates = (
            enumerate_runs(BoardState(current_board, []))
            + enumerate_groups(BoardState(current_board, []))
        )

        t_start = time.monotonic()

        for _step in range(target_rack_size):
            if time.monotonic() - t_start > _TOTAL_ATTEMPT_TIMEOUT:
                break

            candidates = _score_all_candidates(current_board, all_templates)
            if not candidates:
                break

            # Build the pool to draw from for this step.
            if strategy == "maximize_cascade":
                candidates.sort(key=lambda c: c.cascade_estimate, reverse=True)
                top_n = max(1, len(candidates) // 3)
                draw_pool = candidates[:top_n]
            else:
                draw_pool = list(candidates)

            # Try up to max_removal_attempts_per_tile candidates for this step.
            committed = False
            remaining_pool = list(draw_pool)

            for _ in range(min(max_removal_attempts_per_tile, len(remaining_pool))):
                if not remaining_pool:
                    break

                # Weighted random selection (weights always > 0).
                if strategy == "maximize_cascade":
                    weights = [c.cascade_estimate + 0.1 for c in remaining_pool]
                    chosen = rng.choices(remaining_pool, weights=weights, k=1)[0]
                else:
                    chosen = rng.choice(remaining_pool)

                # Remove chosen from the retry pool so we don't repeat it.
                remaining_pool = [c for c in remaining_pool if c is not chosen]

                new_board = _apply_removal(current_board, chosen)
                new_rack = rack + [chosen.tile]

                state = BoardState(board_sets=new_board, rack=new_rack)
                solution = solve(state, timeout_seconds=solve_timeout)

                # Reject if the solver timed out or couldn't place all rack tiles.
                if solution.solve_status in ("timeout_fallback", "infeasible_fallback"):
                    continue
                if solution.tiles_placed < len(new_rack):
                    continue

                # Commit this removal.
                # Capture state_before BEFORE mutating current_board / rack.
                removal_log.append(
                    RemovalStep(
                        candidate=chosen,
                        state_before=BoardState(current_board, list(rack)),
                        solver_result=solution,
                    )
                )
                current_board = new_board
                rack = new_rack

                # Recompute templates with updated board + accumulated rack so
                # that orphan-absorption counts remain accurate in subsequent steps.
                all_templates = (
                    enumerate_runs(BoardState(current_board, rack))
                    + enumerate_groups(BoardState(current_board, rack))
                )
                committed = True
                break

            if not committed:
                # No viable candidate found for this step; the board is stuck.
                break

        if len(rack) < rack_size_range[0]:
            return None

        return current_board, rack, removal_log
