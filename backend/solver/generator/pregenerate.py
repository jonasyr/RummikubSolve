"""Batch pre-generation CLI for Rummikub puzzles.

Generates puzzles offline and stores them in a SQLite pool so the API
can serve Expert and Nightmare puzzles without blocking on slow ILP solves.
Supports parallel generation across multiple CPU cores and optional
incremental syncing to a remote server after every N accepted puzzles.

Usage::

    python -m solver.generator.pregenerate --difficulty nightmare --count 50
    python -m solver.generator.pregenerate --difficulty expert --count 50 --workers 6
    python -m solver.generator.pregenerate --all --count 100 --workers 4
    python -m solver.generator.pregenerate --stats
    python -m solver.generator.pregenerate --stats --db /path/to/puzzles.db

    # With incremental remote sync every 10 puzzles:
    python -m solver.generator.pregenerate \\
        --difficulty nightmare --count 50 --workers 6 \\
        --sync-every 10 \\
        --sync-cmd "scp /app/data/puzzles.db user@host:/remote/path/puzzles.db"
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from pathlib import Path

from .puzzle_generator import PuzzleGenerationError, PuzzleResult, generate_puzzle
from .puzzle_store import PuzzleStore

_HARD_PLUS = ["hard", "expert", "nightmare"]


# ---------------------------------------------------------------------------
# Worker (module-level so it is picklable by multiprocessing)
# ---------------------------------------------------------------------------


def _worker_generate_one(args: tuple[str, int]) -> PuzzleResult | None:
    """Generate a single puzzle attempt in a worker process; return None on failure."""
    difficulty, seed = args
    try:
        return generate_puzzle(
            difficulty=difficulty,  # type: ignore[arg-type]
            seed=seed,
            pregen=True,
        )
    except PuzzleGenerationError:
        return None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


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
        "--workers",
        type=int,
        default=min(os.cpu_count() or 4, 8),
        help="Number of parallel worker processes (default: min(cpu_count, 8)).",
    )
    parser.add_argument(
        "--sync-every",
        type=int,
        default=10,
        metavar="N",
        help="Run --sync-cmd after every N accepted puzzles (default: 10).",
    )
    parser.add_argument(
        "--sync-cmd",
        type=str,
        default=None,
        metavar="CMD",
        help=(
            "Shell command to run for incremental sync, e.g. "
            "'scp /app/data/puzzles.db user@host:/path/puzzles.db'. "
            "Runs after every --sync-every puzzles and once at the end."
        ),
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
        _generate_batch(
            store=store,
            difficulty=diff,
            count=args.count,
            workers=args.workers,
            sync_every=args.sync_every,
            sync_cmd=args.sync_cmd,
        )

    store.close()


# ---------------------------------------------------------------------------
# Batch generation with multiprocessing
# ---------------------------------------------------------------------------


def _run_sync(sync_cmd: str) -> None:
    print(f"\n  [sync] {sync_cmd}")
    result = subprocess.run(sync_cmd, shell=True)  # noqa: S602
    if result.returncode != 0:
        print(f"  [sync] WARNING: exited with code {result.returncode}")
    else:
        print("  [sync] OK")


def _generate_batch(
    store: PuzzleStore,
    difficulty: str,
    count: int,
    workers: int,
    sync_every: int,
    sync_cmd: str | None,
) -> None:
    print(f"\n{'=' * 60}")
    print(f"Generating {count} {difficulty} puzzles  |  workers={workers}")
    print(f"{'=' * 60}")

    generated = 0
    failed = 0
    t0 = time.monotonic()
    next_seed = int(t0 * 1_000) % (2**31)
    last_sync_at = 0

    in_flight: dict[Future[PuzzleResult | None], int] = {}

    with ProcessPoolExecutor(max_workers=workers) as pool:

        def _submit(n: int = 1) -> None:
            nonlocal next_seed
            for _ in range(n):
                next_seed += 1
                f = pool.submit(_worker_generate_one, (difficulty, next_seed))
                in_flight[f] = next_seed

        # Pre-fill: keep workers*2 futures in flight so workers are never idle
        # while the main process writes to SQLite or runs the sync command.
        _submit(workers * 2)

        while generated < count:
            if not in_flight:
                _submit(workers)

            done, _ = wait(list(in_flight.keys()), return_when=FIRST_COMPLETED)

            for future in done:
                seed_used = in_flight.pop(future)
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001
                    print(f"\n  [worker error] seed={seed_used}: {exc}")
                    failed += 1
                    result = None

                if result is not None:
                    store.store(result, seed=seed_used)
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

                    if sync_cmd and (generated - last_sync_at) >= sync_every:
                        last_sync_at = generated
                        _run_sync(sync_cmd)
                else:
                    failed += 1

                if generated < count:
                    _submit(1)

    elapsed = time.monotonic() - t0
    print(f"\n  Done: {generated} puzzles in {elapsed:.1f}s  ({failed} failed attempts)")

    if sync_cmd:
        _run_sync(sync_cmd)


if __name__ == "__main__":
    main()
