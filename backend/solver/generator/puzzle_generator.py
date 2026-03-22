"""Random puzzle generation for practice mode.

Blueprint §9.1 — Puzzle Generation:
  Generate a random valid board, remove a subset of tiles to form the
  rack, solve to verify the rack can be placed, and classify difficulty.

Difficulty is defined by rack size and the kind of placement needed:
  easy:   2–3 tiles, all from run ends (simple extensions)
  medium: 3–6 tiles, from one complete set (player must recreate a set)
  hard:   6–12 tiles, from two complete sets (player must create multiple sets)

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
from .set_enumerator import enumerate_groups, enumerate_runs

Difficulty = Literal["easy", "medium", "hard"]


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
) -> PuzzleResult:
    """Generate a random, pre-verified Rummikub puzzle at the given difficulty.

    Args:
        difficulty:   "easy", "medium", or "hard".
        seed:         Optional RNG seed for reproducible puzzles.
        max_attempts: How many boards to try before giving up.

    Returns:
        A PuzzleResult whose rack the solver can fully place.

    Raises:
        ValueError:             If difficulty is not a known value.
        PuzzleGenerationError:  If no suitable puzzle is found.
    """
    if difficulty not in ("easy", "medium", "hard"):
        raise ValueError(f"Unknown difficulty {difficulty!r}. Use 'easy', 'medium', or 'hard'.")

    rng = random.Random(seed)
    for _ in range(max_attempts):
        result = _attempt_generate(rng, difficulty)
        if result is not None:
            return result

    raise PuzzleGenerationError(
        f"Could not generate a {difficulty!r} puzzle after {max_attempts} attempts."
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _attempt_generate(rng: random.Random, difficulty: Difficulty) -> PuzzleResult | None:
    full_pool = _make_full_pool()
    all_sets = enumerate_runs(full_pool) + enumerate_groups(full_pool)
    rng.shuffle(all_sets)

    n_target = rng.randint(5, 9)
    board_sets = _pick_compatible_sets(all_sets, n_target)
    if len(board_sets) < 3:
        return None

    board_sets = _assign_copy_ids(board_sets)

    input_board, rack = _extract_rack(board_sets, difficulty, rng)
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
    rack = [
        Tile(color, n, copy_id)
        for color in Color
        for n in range(1, 14)
        for copy_id in (0, 1)
    ]
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
) -> tuple[list[TileSet], list[Tile]]:
    if difficulty == "easy":
        return _extract_easy(board_sets, rng)
    if difficulty == "medium":
        return _extract_medium(board_sets, rng)
    return _extract_hard(board_sets, rng)


def _extract_easy(
    board_sets: list[TileSet], rng: random.Random
) -> tuple[list[TileSet], list[Tile]]:
    """Remove 2–3 tiles from the ends of long runs (≥ 5 tiles).

    Remaining run is always ≥ 3 tiles valid. Rack tiles are trivially
    placeable by extending the shortened run.
    """
    # Only long runs (≥ 5) so we can safely remove 2 end tiles and keep ≥ 3.
    long_runs = [i for i, ts in enumerate(board_sets) if ts.type == SetType.RUN and len(ts.tiles) >= 5]
    if not long_runs:
        # Fallback: runs ≥ 4 so we can remove 1 tile and keep ≥ 3.
        long_runs = [i for i, ts in enumerate(board_sets) if ts.type == SetType.RUN and len(ts.tiles) >= 4]
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
