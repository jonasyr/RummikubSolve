"""Random puzzle generation for practice mode.

Blueprint §9.1 — Puzzle Generation:
  Generate a random valid board, remove a subset of tiles to form the
  rack, solve to verify the rack can be placed, and classify difficulty.

Difficulty is defined by rack size and the kind of placement needed:
  easy:   2–3 tiles, all from run ends (simple extensions)
  medium: 3–6 tiles, from one complete set (player must recreate a set)
  hard:   6–12 tiles, from two complete sets (player must create multiple sets)
  expert: 2 tiles from different board sets, no trivial placement exists —
          player must rearrange the board to find any valid placement

Solvability is guaranteed by construction (all extracted tiles can be
re-placed by the solver). Joker-free in v1.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from typing import Literal

from ..engine.solver import solve
from ..models.board_state import BoardState
from ..models.tile import Color, Tile
from ..models.tileset import SetType, TileSet
from ..validator.rule_checker import is_valid_set
from .set_enumerator import enumerate_groups, enumerate_runs

Difficulty = Literal["easy", "medium", "hard", "expert", "custom"]


class PuzzleGenerationError(Exception):
    """Raised when a puzzle cannot be generated within the attempt limit."""


@dataclass
class PuzzleResult:
    board_sets: list[TileSet]
    rack: list[Tile]
    difficulty: Difficulty


def generate_puzzle(
    difficulty: Difficulty = "medium",
    seed: int | None = None,
    max_attempts: int = 150,
    sets_to_remove: int = 3,
) -> PuzzleResult:
    """Generate a random, pre-verified Rummikub puzzle at the given difficulty.

    Args:
        difficulty:    "easy", "medium", "hard", or "custom".
        seed:          Optional RNG seed for reproducible puzzles.
        max_attempts:  How many boards to try before giving up.
        sets_to_remove: Number of complete sets to remove (only used when
                        difficulty == "custom"; valid range 1–5).

    Returns:
        A PuzzleResult whose rack the solver can fully place.

    Raises:
        ValueError:             If difficulty is not a known value.
        PuzzleGenerationError:  If no suitable puzzle is found.
    """
    if difficulty not in ("easy", "medium", "hard", "expert", "custom"):
        raise ValueError(
            f"Unknown difficulty {difficulty!r}. "
            f"Use 'easy', 'medium', 'hard', 'expert', or 'custom'."
        )

    rng = random.Random(seed)
    for _ in range(max_attempts):
        result = _attempt_generate(rng, difficulty, sets_to_remove)
        if result is not None:
            return result

    raise PuzzleGenerationError(
        f"Could not generate a {difficulty!r} puzzle after {max_attempts} attempts."
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _attempt_generate(
    rng: random.Random, difficulty: Difficulty, sets_to_remove: int = 3
) -> PuzzleResult | None:
    full_pool = _make_full_pool()
    all_sets = enumerate_runs(full_pool) + enumerate_groups(full_pool)
    rng.shuffle(all_sets)

    # Scale the board target for difficulties that need more sets to work with.
    if difficulty == "custom":
        lo = max(5, sets_to_remove + 4)
        hi = max(9, sets_to_remove + 7)
        n_target = rng.randint(lo, hi)
    elif difficulty == "expert":
        # Larger board gives more candidate sets for the extraction pairing search.
        n_target = rng.randint(8, 12)
    else:
        n_target = rng.randint(5, 9)
    board_sets = _pick_compatible_sets(all_sets, n_target)
    if len(board_sets) < 3:
        return None

    board_sets = _assign_copy_ids(board_sets)

    input_board, rack = _extract_rack(board_sets, difficulty, rng, sets_to_remove)
    if len(rack) < 2:
        return None

    # Verify: solver must place ALL rack tiles.
    state = BoardState(board_sets=input_board, rack=rack)
    solution = solve(state, rules=None)
    if solution.tiles_placed < len(rack):
        return None

    return PuzzleResult(board_sets=input_board, rack=rack, difficulty=difficulty)


def _make_full_pool() -> BoardState:
    """104 non-joker tiles (4 colors × 13 numbers × 2 copies), no jokers."""
    rack = [Tile(color, n, copy_id) for color in Color for n in range(1, 14) for copy_id in (0, 1)]
    return BoardState(board_sets=[], rack=rack)


def _pick_compatible_sets(all_sets: list[TileSet], n: int) -> list[TileSet]:
    """Greedily select up to n sets that share no physical tile copies."""
    avail: Counter[tuple[Color | None, int | None]] = Counter()
    for color in Color:
        for num in range(1, 14):
            avail[(color, num)] = 2

    selected: list[TileSet] = []
    for ts in all_sets:
        if len(selected) >= n:
            break
        needed: Counter[tuple[Color | None, int | None]] = Counter(
            (t.color, t.number)
            for t in ts.tiles
            if not t.is_joker and t.color is not None and t.number is not None
        )
        if all(avail[k] >= v for k, v in needed.items()):
            selected.append(ts)
            for k, v in needed.items():
                avail[k] -= v

    return selected


def _assign_copy_ids(board_sets: list[TileSet]) -> list[TileSet]:
    """Assign copy_ids 0/1 to distinguish duplicate (color, number) tiles."""
    seen: Counter[tuple[Color | None, int | None]] = Counter()
    result: list[TileSet] = []
    for ts in board_sets:
        new_tiles: list[Tile] = []
        for t in ts.tiles:
            if t.is_joker:
                new_tiles.append(t)
            else:
                copy_id = seen[(t.color, t.number)]
                new_tiles.append(Tile(color=t.color, number=t.number, copy_id=copy_id))
                seen[(t.color, t.number)] += 1
        result.append(TileSet(type=ts.type, tiles=new_tiles))
    return result


def _extract_rack(
    board_sets: list[TileSet],
    difficulty: Difficulty,
    rng: random.Random,
    sets_to_remove: int = 3,
) -> tuple[list[TileSet], list[Tile]]:
    if difficulty == "easy":
        return _extract_easy(board_sets, rng)
    if difficulty == "medium":
        return _extract_medium(board_sets, rng)
    if difficulty == "expert":
        return _extract_expert(board_sets, rng)
    if difficulty == "custom":
        return _extract_custom(board_sets, rng, sets_to_remove)
    return _extract_hard(board_sets, rng)


def _extract_easy(
    board_sets: list[TileSet], rng: random.Random
) -> tuple[list[TileSet], list[Tile]]:
    """Remove 2–3 tiles from the ends of long runs (≥ 5 tiles).

    Remaining run is always ≥ 3 tiles valid. Rack tiles are trivially
    placeable by extending the shortened run.
    """
    # Only long runs (≥ 5) so we can safely remove 2 end tiles and keep ≥ 3.
    long_runs = [
        i for i, ts in enumerate(board_sets) if ts.type == SetType.RUN and len(ts.tiles) >= 5
    ]
    if not long_runs:
        # Fallback: runs ≥ 4 so we can remove 1 tile and keep ≥ 3.
        long_runs = [
            i for i, ts in enumerate(board_sets) if ts.type == SetType.RUN and len(ts.tiles) >= 4
        ]
    if not long_runs:
        return board_sets, []

    board = list(board_sets)
    rack: list[Tile] = []
    n_to_remove = rng.randint(2, min(3, len(long_runs) * 2))

    for _ in range(n_to_remove):
        eligible = [i for i in long_runs if len(board[i].tiles) >= 4]
        if not eligible:
            break
        idx = rng.choice(eligible)
        # Remove from start or end (whichever keeps the run valid ≥ 3).
        if rng.random() < 0.5:
            rack.append(board[idx].tiles[0])
            board[idx] = TileSet(type=SetType.RUN, tiles=list(board[idx].tiles[1:]))
        else:
            rack.append(board[idx].tiles[-1])
            board[idx] = TileSet(type=SetType.RUN, tiles=list(board[idx].tiles[:-1]))

    return board, rack


def _extract_medium(
    board_sets: list[TileSet], rng: random.Random
) -> tuple[list[TileSet], list[Tile]]:
    """Remove 1 complete set (3–5 tiles). Rack = all its tiles."""
    if not board_sets:
        return board_sets, []
    idx = rng.randrange(len(board_sets))
    rack = list(board_sets[idx].tiles)
    remaining = [ts for i, ts in enumerate(board_sets) if i != idx]
    if len(remaining) < 2:
        return board_sets, []
    return remaining, rack


def _extract_hard(
    board_sets: list[TileSet], rng: random.Random
) -> tuple[list[TileSet], list[Tile]]:
    """Remove 2 complete sets. Rack = all tiles from both sets."""
    if len(board_sets) < 4:
        return board_sets, []
    indices = set(rng.sample(range(len(board_sets)), 2))
    rack = [t for i, ts in enumerate(board_sets) if i in indices for t in ts.tiles]
    remaining = [ts for i, ts in enumerate(board_sets) if i not in indices]
    return remaining, rack


def _any_trivial_extension(rack: list[Tile], board_sets: list[TileSet]) -> bool:
    """Return True if any rack tile can be directly appended to any board set.

    Uses the same rule_checker as the solver, so the check is authoritative.
    A puzzle is disqualified as "expert" if this returns True — the player
    would have an obvious move without needing to rearrange anything.
    """
    for tile in rack:
        for ts in board_sets:
            if is_valid_set(TileSet(type=ts.type, tiles=ts.tiles + [tile])):
                return True
    return False


def _extract_expert(
    board_sets: list[TileSet], rng: random.Random
) -> tuple[list[TileSet], list[Tile]]:
    """Extract 2 rack tiles by completely sacrificing 2 board sets.

    Selects 2 "sacrifice" sets S1 and S2, picks 1 tile from each as a rack
    tile, then drops S1 and S2 entirely from the board (their remaining tiles
    go to the bag — unused in the puzzle). The player's board only contains
    the other sets.

    Why "complete sacrifice" instead of "shorten a set":
        If we merely removed a tile from the end of a run, the shortened run
        would still accept that tile back as a trivial extension. By removing
        the source set entirely, there is no "obvious home" left on the board.
        The tile can only be placed by rearranging other board sets, which is
        the hallmark of expert-level Rummikub play.

    Tries all set-pairs shuffled randomly; returns the first pair where
    neither rack tile can be directly appended to any remaining board set.
    Requires ≥ 4 board sets (2 to sacrifice, ≥ 2 left on the board).
    """
    if len(board_sets) < 4:
        return board_sets, []

    n = len(board_sets)
    pair_indices = [(i, j) for i in range(n) for j in range(i + 1, n)]
    rng.shuffle(pair_indices)

    for idx_a, idx_b in pair_indices:
        # Board = all sets except the two sacrificed ones.
        remaining_board = [ts for k, ts in enumerate(board_sets) if k != idx_a and k != idx_b]
        if len(remaining_board) < 2:
            continue

        # Pick one tile at random from each sacrifice set.
        tile_a = rng.choice(board_sets[idx_a].tiles)
        tile_b = rng.choice(board_sets[idx_b].tiles)
        rack = [tile_a, tile_b]

        if not _any_trivial_extension(rack, remaining_board):
            return remaining_board, rack

    return board_sets, []  # no valid pair found; _attempt_generate will retry


def _extract_custom(
    board_sets: list[TileSet], rng: random.Random, n: int
) -> tuple[list[TileSet], list[Tile]]:
    """Remove n complete sets. Rack = all tiles from the removed sets.

    Requires at least n + 2 sets on the board so that at least 2 remain
    after extraction (giving the solver something to work with).
    """
    if len(board_sets) < n + 2:
        return board_sets, []
    indices = set(rng.sample(range(len(board_sets)), n))
    rack = [t for i, ts in enumerate(board_sets) if i in indices for t in ts.tiles]
    remaining = [ts for i, ts in enumerate(board_sets) if i not in indices]
    return remaining, rack
