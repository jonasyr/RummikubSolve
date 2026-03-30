"""Batch pre-generation CLI for Rummikub puzzles.

Generates puzzles offline and stores them in a SQLite pool so the API
can serve Expert and Nightmare puzzles without blocking on slow ILP solves.

Usage::

    python -m solver.generator.pregenerate --difficulty nightmare --count 200
    python -m solver.generator.pregenerate --difficulty expert --count 500
    python -m solver.generator.pregenerate --all --count 100
    python -m solver.generator.pregenerate --stats
    python -m solver.generator.pregenerate --stats --db /path/to/puzzles.db
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .puzzle_generator import PuzzleGenerationError, generate_puzzle
from .puzzle_store import PuzzleStore

_HARD_PLUS = ["hard", "expert", "nightmare"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pre-generate Rummikub puzzles into a SQLite pool.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--difficulty",
        choices=["hard", "expert", "nightmare"],
        help="Difficulty tier to generate.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate for hard, expert, and nightmare in sequence.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of puzzles to generate per difficulty (default: 100).",
    )
    parser.add_argument(
        "--db",
        type=str,
        default="data/puzzles.db",
        help="Path to the SQLite database (default: data/puzzles.db).",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print pool statistics and exit.",
    )
    args = parser.parse_args()

    store = PuzzleStore(Path(args.db))

    if args.stats:
        print("Puzzle pool statistics:")
        for d in ("easy", "medium", "hard", "expert", "nightmare"):
            print(f"  {d:10s}: {store.count(d):5d} puzzles")
        print(f"  {'total':10s}: {store.count():5d} puzzles")
        store.close()
        return

    if args.all:
        difficulties = _HARD_PLUS
    elif args.difficulty:
        difficulties = [args.difficulty]
    else:
        parser.print_help()
        store.close()
        return

    for diff in difficulties:
        _generate_batch(store, diff, args.count)

    store.close()


def _generate_batch(store: PuzzleStore, difficulty: str, count: int) -> None:
    print(f"\n{'=' * 50}")
    print(f"Generating {count} {difficulty} puzzles …")
    print(f"{'=' * 50}")

    generated = 0
    failed = 0
    t0 = time.monotonic()
    seed = int(t0 * 1_000) % (2**31)

    while generated < count:
        seed += 1
        try:
            result = generate_puzzle(difficulty=difficulty, seed=seed)  # type: ignore[arg-type]
            store.store(result, seed=seed)
            generated += 1
            elapsed = time.monotonic() - t0
            rate = generated / elapsed if elapsed > 0 else 0
            sys.stdout.write(
                f"\r  [{generated}/{count}] "
                f"chain={result.chain_depth} "
                f"disrupt={result.disruption_score} "
                f"unique={result.is_unique} "
                f"rack={len(result.rack)} "
                f"({rate:.2f}/s)   "
            )
            sys.stdout.flush()
        except PuzzleGenerationError:
            failed += 1
            if failed > count * 10:
                print(f"\n  Too many failures ({failed}), stopping early.")
                break

    elapsed = time.monotonic() - t0
    print(f"\n  Done: {generated} puzzles in {elapsed:.1f}s ({failed} failures)")


if __name__ == "__main__":
    main()
