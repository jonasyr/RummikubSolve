"""Greedy heuristic solver for puzzle-difficulty gating.

Models a competent-but-not-omniscient human player.  The solver is
intentionally weaker than the ILP engine: it applies four simple rules in
priority order and gives up as soon as none fire.  Any puzzle it *solves* is
by definition trivial.

See PUZZLE_GENERATION_REBUILD_PLAN.md §4.2.5.
"""
from __future__ import annotations

__all__ = ["HeuristicSolver", "SolverMove"]

from copy import deepcopy
from dataclasses import dataclass

from solver.models.board_state import BoardState
from solver.models.tile import Tile
from solver.models.tileset import TileSet
from solver.validator.rule_checker import is_valid_board, is_valid_set


@dataclass
class SolverMove:
    """Describes a single action taken by the heuristic solver.

    Rules 1 & 2 — direct placement:
        ``rack_tile_idx`` → ``board_set_idx`` (destination set).

    Rules 3 & 4 — break then place (atomic):
        Break ``break_set_idx`` by removing tile at ``released_tile_idx``.
        After the break, ``scratch_rack = original_rack + [released_tile]``.
        Place ``scratch_rack[sub_rack_tile_idx]`` into post-break board's
        ``sub_board_set_idx``.

        Rule 4 additionally performs a *second* break before the final
        placement, described by ``inner_break_set_idx``,
        ``inner_released_tile_idx``, ``inner_sub_rack_tile_idx``, and
        ``inner_sub_board_set_idx`` (all operate on the board after the
        first break).
    """

    rule: int

    # Rules 1 & 2
    rack_tile_idx: int = 0
    board_set_idx: int = 0

    # Rules 3 & 4 — outer break
    break_set_idx: int | None = None
    released_tile_idx: int | None = None
    # Tile to place after the outer break (index into scratch_rack = rack + [released])
    sub_rack_tile_idx: int | None = None
    # Destination set in the post-outer-break board
    sub_board_set_idx: int | None = None

    # Rule 4 — inner (second) break before final placement
    inner_break_set_idx: int | None = None
    inner_released_tile_idx: int | None = None
    # Tile to place after both breaks (index into inner_scratch = outer_scratch + [inner_released])
    inner_sub_rack_tile_idx: int | None = None
    # Destination in the post-double-break board
    inner_sub_board_set_idx: int | None = None


# ---------------------------------------------------------------------------
# Internal helpers (module-level to avoid method-call overhead)
# ---------------------------------------------------------------------------


def _copy_board(board: list[TileSet]) -> list[TileSet]:
    return [TileSet(type=ts.type, tiles=list(ts.tiles)) for ts in board]


def _is_valid_extension(ts: TileSet, tile: Tile) -> bool:
    return is_valid_set(TileSet(type=ts.type, tiles=ts.tiles + [tile]))


class HeuristicSolver:
    """Greedy heuristic solver — applies four rules in priority order.

    Rules (applied repeatedly until none fire):

    1. **Single-home placement** — a rack tile has exactly one board set into
       which it trivially extends; place it there.
    2. **Stub completion** — a rack tile completes a 2-tile board stub to a
       valid ≥3-tile set; place it there.
    3. **Single-set break (depth 1)** — remove one tile from a ≥4-tile board
       set such that the remainder stays valid, then check whether the released
       tile enables a Rule 1 or Rule 2 placement.
    4. **Single-set break (depth 2)** — same as Rule 3 but the released tile
       may itself trigger another single break before placement.  Only active
       when ``max_depth >= 2``.

    Explicitly out of scope: multi-set merges, joker displacement chains,
    run-to-group transformations.  Do **not** make this solver smarter.
    """

    def solves(self, state: BoardState, max_depth: int = 2) -> bool:
        """Return ``True`` iff the heuristic solver can empty the rack.

        Works on a deep copy of *state* so the caller's object is never
        mutated.
        """
        working_rack: list[Tile] = deepcopy(state.rack)
        working_board: list[TileSet] = deepcopy(state.board_sets)

        while working_rack:
            move = (
                self._find_single_home(working_rack, working_board)
                or self._find_stub_completion(working_rack, working_board)
                or self._try_single_break(working_rack, working_board, max_depth)
            )
            if move is None:
                return False
            working_rack, working_board = self._apply_move(
                working_rack, working_board, move
            )

        return is_valid_board(BoardState(board_sets=working_board, rack=[]))

    # ------------------------------------------------------------------
    # Rule 1 — Single-home placement
    # ------------------------------------------------------------------

    def _find_single_home(
        self,
        rack: list[Tile],
        board_sets: list[TileSet],
    ) -> SolverMove | None:
        """Return a move if a rack tile has exactly one valid board-set home."""
        for i, tile in enumerate(rack):
            homes: list[int] = [
                j for j, ts in enumerate(board_sets)
                if _is_valid_extension(ts, tile)
            ]
            if len(homes) == 1:
                return SolverMove(rule=1, rack_tile_idx=i, board_set_idx=homes[0])
        return None

    # ------------------------------------------------------------------
    # Rule 2 — Stub completion
    # ------------------------------------------------------------------

    def _find_stub_completion(
        self,
        rack: list[Tile],
        board_sets: list[TileSet],
    ) -> SolverMove | None:
        """Return a move if a rack tile completes a 2-tile board stub."""
        for i, tile in enumerate(rack):
            for j, ts in enumerate(board_sets):
                if len(ts.tiles) == 2 and _is_valid_extension(ts, tile):
                    return SolverMove(rule=2, rack_tile_idx=i, board_set_idx=j)
        return None

    # ------------------------------------------------------------------
    # Rules 3 & 4 — Single-set break (depth-limited)
    # ------------------------------------------------------------------

    def _try_single_break(
        self,
        rack: list[Tile],
        board_sets: list[TileSet],
        depth_remaining: int,
    ) -> SolverMove | None:
        """Return an atomic break+place move if breaking a ≥4-tile set enables a placement."""
        if depth_remaining < 1:
            return None

        for i, ts in enumerate(board_sets):
            if len(ts.tiles) < 4:
                continue

            for j in range(len(ts.tiles)):
                remainder_tiles = [t for k, t in enumerate(ts.tiles) if k != j]
                remainder = TileSet(type=ts.type, tiles=remainder_tiles)
                if not is_valid_set(remainder):
                    continue

                # Post-break board: set i replaced by its remainder.
                broken_board = [
                    remainder if k == i else board_sets[k]
                    for k in range(len(board_sets))
                ]
                released_tile = ts.tiles[j]
                # scratch_rack = original rack + released tile at end.
                scratch_rack = rack + [released_tile]

                # Check Rule 1 on scratch state.
                # sub_rack_tile_idx must be an original rack tile (idx < len(rack));
                # placing the released tile back (idx == len(rack)) makes no progress.
                sub1 = self._find_single_home(scratch_rack, broken_board)
                if sub1 is not None and sub1.rack_tile_idx < len(rack):
                    return SolverMove(
                        rule=3,
                        break_set_idx=i,
                        released_tile_idx=j,
                        sub_rack_tile_idx=sub1.rack_tile_idx,
                        sub_board_set_idx=sub1.board_set_idx,
                    )

                # Check Rule 2 on scratch state (same progress constraint).
                sub2 = self._find_stub_completion(scratch_rack, broken_board)
                if sub2 is not None and sub2.rack_tile_idx < len(rack):
                    return SolverMove(
                        rule=3,
                        break_set_idx=i,
                        released_tile_idx=j,
                        sub_rack_tile_idx=sub2.rack_tile_idx,
                        sub_board_set_idx=sub2.board_set_idx,
                    )

                # Rule 4: allow one more nested break.
                if depth_remaining >= 2:
                    inner = self._try_single_break(
                        scratch_rack, broken_board, depth_remaining - 1
                    )
                    if inner is not None:
                        # inner is a Rule 3 move on (scratch_rack, broken_board).
                        # Encode as Rule 4 with full inner-break info.
                        return SolverMove(
                            rule=4,
                            break_set_idx=i,
                            released_tile_idx=j,
                            # outer scratch info not needed; inner encodes the rest:
                            inner_break_set_idx=inner.break_set_idx,
                            inner_released_tile_idx=inner.released_tile_idx,
                            inner_sub_rack_tile_idx=inner.sub_rack_tile_idx,
                            inner_sub_board_set_idx=inner.sub_board_set_idx,
                        )

        return None

    # ------------------------------------------------------------------
    # Move application (atomic)
    # ------------------------------------------------------------------

    def _apply_move(
        self,
        rack: list[Tile],
        board_sets: list[TileSet],
        move: SolverMove,
    ) -> tuple[list[Tile], list[TileSet]]:
        """Return updated (rack, board_sets) after applying *move* atomically.

        Rules 1 & 2: place one tile from rack onto a board set.
        Rules 3 & 4: break a board set, then place a tile (atomic — no
                     intermediate state is visible to the caller).
        """
        new_rack = list(rack)
        new_board = _copy_board(board_sets)

        if move.rule in (1, 2):
            tile = new_rack.pop(move.rack_tile_idx)
            new_board[move.board_set_idx].tiles.append(tile)
            return new_rack, new_board

        # Rules 3 & 4 — outer break.
        assert move.break_set_idx is not None
        assert move.released_tile_idx is not None
        released = new_board[move.break_set_idx].tiles.pop(move.released_tile_idx)
        scratch_rack = new_rack + [released]

        if move.rule == 3:
            assert move.sub_rack_tile_idx is not None
            assert move.sub_board_set_idx is not None
            tile = scratch_rack.pop(move.sub_rack_tile_idx)
            new_board[move.sub_board_set_idx].tiles.append(tile)
            return scratch_rack, new_board

        # Rule 4 — inner break then placement.
        assert move.inner_break_set_idx is not None
        assert move.inner_released_tile_idx is not None
        assert move.inner_sub_rack_tile_idx is not None
        assert move.inner_sub_board_set_idx is not None

        inner_released = new_board[move.inner_break_set_idx].tiles.pop(
            move.inner_released_tile_idx
        )
        inner_scratch = scratch_rack + [inner_released]
        tile = inner_scratch.pop(move.inner_sub_rack_tile_idx)
        new_board[move.inner_sub_board_set_idx].tiles.append(tile)
        return inner_scratch, new_board
