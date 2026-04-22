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
from solver.models.tileset import SetType, TileSet
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


_TileKey = tuple[str, str, int, bool]
_StateKey = tuple[tuple[_TileKey, ...], tuple[tuple[_TileKey, ...], ...]]


def _state_key(
    rack: list[Tile],
    board: list[TileSet],
) -> _StateKey:
    """Return a canonical, hashable key for (rack, board) used for cycle detection.

    Uses sorted tuples so the key is independent of internal list order while
    still distinguishing tile copies (via ``copy_id``).
    """
    def _tile_key(t: Tile) -> tuple[str, str, int, bool]:
        # Use str() so joker's None color/number sort cleanly alongside enums.
        return (str(t.color), str(t.number), t.copy_id, t.is_joker)

    rack_key = tuple(sorted(_tile_key(t) for t in rack))
    board_key = tuple(
        sorted(
            tuple(sorted(_tile_key(t) for t in ts.tiles))
            for ts in board
        )
    )
    return (rack_key, board_key)


def _is_valid_extension(ts: TileSet, tile: Tile) -> bool:
    """Return True if *tile* can be placed into *ts*.

    Both rules use a **relaxed** check for small stubs (< 3 tiles) and
    gap-runs, mirroring how the v2 puzzle generator creates puzzles: it removes
    tiles from valid board sets and places them in the rack, potentially leaving
    gap-runs (e.g. ``[K3..K7, K10, K11]`` when ``K8`` and ``K9`` are removed)
    or single-tile group stubs (e.g. ``[Y11]`` when ``Bl11`` and ``R11`` are
    removed).  Neither ``K8`` nor ``Bl11`` alone would pass a strict validity
    check, yet each is a legitimate intermediate placement.

    **Groups**: strict for sets with ≥ 3 tiles; relaxed for stubs of 1–2 tiles.
    A tile "fits" a small group stub if it shares the same number and introduces
    a *new* colour (groups require all distinct colours).

    **Runs**: always relaxed.  A tile fits a run if it shares the colour, is not
    an exact duplicate (same ``copy_id`` *and* number), and either extends one
    end by 1 or fills an internal gap.

    The final board validity is confirmed by :func:`is_valid_board` once the
    rack is empty; intermediate placements that leave a set temporarily invalid
    are expected.
    """
    extended = TileSet(type=ts.type, tiles=ts.tiles + [tile])
    if is_valid_set(extended):
        return True  # always accept fully valid extensions

    # ------------------------------------------------------------------
    # Group — relaxed stub extension (1 or 2 tiles already in the set).
    # A fully-valid 3-tile group can only be extended to 4 via is_valid_set
    # (handled above), so no further relaxation for len >= 3.
    # ------------------------------------------------------------------
    if ts.type == SetType.GROUP:
        if len(ts.tiles) >= 3:
            return False
        if tile.is_joker:
            return True  # jokers can substitute any colour
        non_jokers = [t for t in ts.tiles if not t.is_joker]
        # Different number → never fits a group.
        if non_jokers and non_jokers[0].number != tile.number:
            return False
        # Same colour already present → groups require all distinct colours.
        return not any(not t.is_joker and t.color == tile.color for t in ts.tiles)

    # ------------------------------------------------------------------
    # Run — relaxed gap-fill check.
    # ------------------------------------------------------------------
    if tile.is_joker:
        return True  # jokers can fill any position in a run

    non_jokers = [t for t in ts.tiles if not t.is_joker]
    # Wrong colour → never fits.
    if non_jokers and tile.color != non_jokers[0].color:
        return False
    # Exact duplicate (same number AND copy_id) → never fits.
    if any(t.number == tile.number and t.copy_id == tile.copy_id for t in ts.tiles):
        return False

    numbers = [t.number for t in non_jokers if t.number is not None]
    if not numbers:
        return True  # set contains only jokers; any tile fits

    if tile.number is None:
        return False  # malformed non-joker tile

    mn, mx = min(numbers), max(numbers)
    n: int = tile.number
    # Fits at lower end, upper end, or fills an internal gap.
    return (n == mn - 1) or (n == mx + 1) or (mn < n < mx and n not in numbers)


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

        **Cycle detection + greedy escape**: Rules 3 & 4 keep the rack size
        constant and can produce reversible swaps, which causes infinite loops
        without a guard.  When a state is revisited, the solver attempts a
        *greedy escape*: it places the first rack tile that has any valid home
        (ignoring uniqueness).  Since greedy placement reduces the rack size,
        the cycle cannot recur.  If no tile has a valid home at all, the solver
        gives up (returns ``False``).

        The same greedy escape fires when all four rules fail to find a move
        but at least one rack tile still has a valid home.  This handles
        positions where all tiles have multiple homes (high branching factor)
        that Rules 1–4 cannot resolve deterministically.  Greedy placement
        succeeds whenever the puzzle has at least one valid solution — because
        Rummikub positions generated by the v2 TileRemover always admit a
        complete restoration (every removed tile has a canonical home), greedy
        will find *a* valid sequence even if not *the* unique one.
        """
        working_rack: list[Tile] = deepcopy(state.rack)
        working_board: list[TileSet] = deepcopy(state.board_sets)

        visited: set[_StateKey] = set()

        while working_rack:
            key = _state_key(working_rack, working_board)
            if key in visited:
                # Cycle — Rules 3/4 are swapping tiles without progress.
                # Fall back to greedy: place the first tile with any home.
                move = self._find_any_placement(working_rack, working_board)
                if move is None:
                    return False
                visited.clear()  # greedy reduces rack size; states won't repeat
                working_rack, working_board = self._apply_move(
                    working_rack, working_board, move
                )
                continue
            visited.add(key)

            move = (
                self._find_single_home(working_rack, working_board)
                or self._find_stub_completion(working_rack, working_board)
                or self._try_single_break(working_rack, working_board, max_depth)
            )
            if move is None:
                # Rules 1–4 exhausted — try greedy fallback before giving up.
                move = self._find_any_placement(working_rack, working_board)
                if move is None:
                    return False  # no tile can be placed anywhere
                visited.clear()
                working_rack, working_board = self._apply_move(
                    working_rack, working_board, move
                )
                continue
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
    # Greedy fallback — place any tile with any valid home
    # ------------------------------------------------------------------

    def _find_any_placement(
        self,
        rack: list[Tile],
        board_sets: list[TileSet],
    ) -> SolverMove | None:
        """Return a move for the first rack tile that extends any board set.

        Unlike Rule 1 (which requires exactly one home), this accepts any
        number of homes ≥ 1 and picks the first available (rack-tile order,
        then board-set order).  Used as a greedy escape from cycle states and
        as a last resort when Rules 1–4 all fail.
        """
        for i, tile in enumerate(rack):
            for j, ts in enumerate(board_sets):
                if _is_valid_extension(ts, tile):
                    return SolverMove(rule=1, rack_tile_idx=i, board_set_idx=j)
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
        """Return an atomic break+place move if breaking a ≥4-tile set enables a placement.

        **Two-phase search** — Rule 3 is fully explored before Rule 4:

        Phase 1 (Rule 3): scan every valid (set, tile) break and check whether the
        released tile gives an *original* rack tile a unique home (Rule 1) or
        completes a 2-tile stub (Rule 2).  Return on the first hit.

        Phase 2 (Rule 4): only if Phase 1 found nothing *and* ``depth_remaining ≥ 2``,
        scan again and recurse into a second break.  Running Phase 2 only after
        Phase 1 is exhausted ensures the solver always prefers shallower moves,
        which prevents premature Rule-4 choices that can strand later rack tiles.
        """
        if depth_remaining < 1:
            return None

        # ------------------------------------------------------------------
        # Phase 1 — Rule 3: one break + direct Rule 1/2 placement.
        # ------------------------------------------------------------------
        for i, ts in enumerate(board_sets):
            if len(ts.tiles) < 4:
                continue

            for j in range(len(ts.tiles)):
                remainder_tiles = [t for k, t in enumerate(ts.tiles) if k != j]
                remainder = TileSet(type=ts.type, tiles=remainder_tiles)
                if not is_valid_set(remainder):
                    continue

                broken_board = [
                    remainder if k == i else board_sets[k]
                    for k in range(len(board_sets))
                ]
                released_tile = ts.tiles[j]
                scratch_rack = rack + [released_tile]

                # sub_rack_tile_idx must be an original rack tile (idx < len(rack));
                # placing the released tile back makes no progress.
                sub1 = self._find_single_home(scratch_rack, broken_board)
                if sub1 is not None and sub1.rack_tile_idx < len(rack):
                    return SolverMove(
                        rule=3,
                        break_set_idx=i,
                        released_tile_idx=j,
                        sub_rack_tile_idx=sub1.rack_tile_idx,
                        sub_board_set_idx=sub1.board_set_idx,
                    )

                sub2 = self._find_stub_completion(scratch_rack, broken_board)
                if sub2 is not None and sub2.rack_tile_idx < len(rack):
                    return SolverMove(
                        rule=3,
                        break_set_idx=i,
                        released_tile_idx=j,
                        sub_rack_tile_idx=sub2.rack_tile_idx,
                        sub_board_set_idx=sub2.board_set_idx,
                    )

        # ------------------------------------------------------------------
        # Phase 2 — Rule 4: one break + nested break.  Only reached when
        # Phase 1 found no direct Rule 1/2 trigger.
        # ------------------------------------------------------------------
        if depth_remaining >= 2:
            for i, ts in enumerate(board_sets):
                if len(ts.tiles) < 4:
                    continue

                for j in range(len(ts.tiles)):
                    remainder_tiles = [t for k, t in enumerate(ts.tiles) if k != j]
                    remainder = TileSet(type=ts.type, tiles=remainder_tiles)
                    if not is_valid_set(remainder):
                        continue

                    broken_board = [
                        remainder if k == i else board_sets[k]
                        for k in range(len(board_sets))
                    ]
                    released_tile = ts.tiles[j]
                    scratch_rack = rack + [released_tile]

                    inner = self._try_single_break(
                        scratch_rack, broken_board, depth_remaining - 1
                    )
                    if inner is not None:
                        return SolverMove(
                            rule=4,
                            break_set_idx=i,
                            released_tile_idx=j,
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
