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
import random
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path

from .puzzle_generator import (
    PuzzleGenerationError,
    PuzzleResult,
    _attempt_generate_with_reason,
)
from .puzzle_store import PuzzleStore

_HARD_PLUS = ["hard", "expert", "nightmare"]


# ---------------------------------------------------------------------------
# Worker (module-level so it is picklable by multiprocessing)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _WorkerResult:
    result: PuzzleResult | None
    rejection_reason: str | None
    rack_size: int = 0
    tiles_placed: int = 0
    solve_status: str | None = None
    solve_time_ms: float = 0.0
    disruption_score: int | None = None
    chain_depth: int | None = None


def _worker_generate_one(args: tuple[str, int]) -> _WorkerResult:
    """Generate one pregen attempt and classify rejections for progress reporting."""
    difficulty, seed = args
    try:
        outcome = _attempt_generate_with_reason(
            random.Random(seed),
            difficulty=difficulty,  # type: ignore[arg-type]
            pregen=True,
        )
        return _WorkerResult(
            result=outcome.result,
            rejection_reason=outcome.rejection_reason,
            rack_size=outcome.rack_size,
            tiles_placed=outcome.tiles_placed,
            solve_status=outcome.solve_status,
            solve_time_ms=outcome.solve_time_ms,
            disruption_score=outcome.disruption_score,
            chain_depth=outcome.chain_depth,
        )
    except PuzzleGenerationError:
        return _WorkerResult(result=None, rejection_reason="generation_error")


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
    parser.add_argument(
        "--progress-every-attempts",
        type=int,
        default=100,
        metavar="N",
        help="Print a live summary after every N failed attempts (default: 100).",
    )
    parser.add_argument(
        "--progress-every-seconds",
        type=float,
        default=30.0,
        metavar="S",
        help="Print a live summary at least every S seconds while running (default: 30).",
    )
    parser.add_argument(
        "--verbose-attempts",
        action="store_true",
        help="Print one-line details for every attempt that reaches the solver.",
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
            progress_every_attempts=args.progress_every_attempts,
            progress_every_seconds=args.progress_every_seconds,
            verbose_attempts=args.verbose_attempts,
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
    progress_every_attempts: int,
    progress_every_seconds: float,
    verbose_attempts: bool,
) -> None:
    print(f"\n{'=' * 60}")
    print(f"Generating {count} {difficulty} puzzles  |  workers={workers}")
    print(f"{'=' * 60}")

    generated = 0
    failed = 0
    t0 = time.monotonic()
    next_seed = int(t0 * 1_000) % (2**31)
    last_sync_at = 0
    last_progress_failures = 0
    last_progress_time = t0

    in_flight: dict[Future[_WorkerResult], int] = {}
    rejection_counts: Counter[str] = Counter()
    partial_placement_counts: Counter[str] = Counter()
    solved_failure_counts: Counter[str] = Counter()
    solved_failure_time_ms = 0.0
    solved_failure_attempts = 0
    best_near_miss: _WorkerResult | None = None

    def _update_best_near_miss(worker_result: _WorkerResult) -> None:
        nonlocal best_near_miss
        if worker_result.result is not None:
            return
        if worker_result.disruption_score is None and worker_result.tiles_placed == 0:
            return
        if best_near_miss is None:
            best_near_miss = worker_result
            return
        current_score = (
            worker_result.tiles_placed,
            worker_result.disruption_score or -1,
            worker_result.chain_depth or -1,
        )
        best_score = (
            best_near_miss.tiles_placed,
            best_near_miss.disruption_score or -1,
            best_near_miss.chain_depth or -1,
        )
        if current_score > best_score:
            best_near_miss = worker_result

    def _print_live_summary(prefix: str) -> None:
        elapsed = time.monotonic() - t0
        attempts = generated + failed
        attempt_rate = attempts / elapsed if elapsed > 0 else 0.0
        accept_rate = generated / elapsed if elapsed > 0 else 0.0
        rejection_line = "  ".join(
            f"{reason}={rejection_counts[reason]}"
            for reason in sorted(rejection_counts)
        ) or "none"
        partial_line = "  ".join(
            f"{bucket}={partial_placement_counts[bucket]}"
            for bucket in sorted(partial_placement_counts)
        ) or "none"
        avg_solve_ms = (
            solved_failure_time_ms / solved_failure_attempts
            if solved_failure_attempts > 0
            else 0.0
        )
        print(
            f"\n  [{prefix}] attempts={attempts} accepted={generated} failed={failed} "
            f"attempt_rate={attempt_rate:.2f}/s accept_rate={accept_rate:.3f}/s"
        )
        print(f"  [live] rejections: {rejection_line}")
        print(
            f"  [live] solved_failures={solved_failure_attempts} "
            f"avg_solve_ms={avg_solve_ms:.1f} partials: {partial_line}"
        )
        if best_near_miss is not None:
            print(
                "  [live] best_near_miss: "
                f"reason={best_near_miss.rejection_reason} "
                f"placed={best_near_miss.tiles_placed}/{best_near_miss.rack_size} "
                f"disrupt={best_near_miss.disruption_score} "
                f"chain={best_near_miss.chain_depth}"
            )

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
                    worker_result = future.result()
                except Exception as exc:  # noqa: BLE001
                    print(f"\n  [worker error] seed={seed_used}: {exc}")
                    failed += 1
                    rejection_counts["worker_error"] += 1
                    worker_result = _WorkerResult(result=None, rejection_reason="worker_error")

                result = worker_result.result
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
                    rejection_counts[worker_result.rejection_reason or "unknown_fail"] += 1
                    _update_best_near_miss(worker_result)
                    if worker_result.solve_status is not None:
                        solved_failure_attempts += 1
                        solved_failure_counts[worker_result.solve_status] += 1
                        solved_failure_time_ms += worker_result.solve_time_ms
                        if worker_result.rejection_reason == "solve_partial_placement":
                            bucket = f"{worker_result.tiles_placed}/{worker_result.rack_size}"
                            partial_placement_counts[bucket] += 1
                        if verbose_attempts:
                            print(
                                "\n  [attempt] "
                                f"reason={worker_result.rejection_reason} "
                                f"status={worker_result.solve_status} "
                                f"placed={worker_result.tiles_placed}/{worker_result.rack_size} "
                                f"solve_ms={worker_result.solve_time_ms:.1f} "
                                f"disrupt={worker_result.disruption_score} "
                                f"chain={worker_result.chain_depth}"
                            )

                    now = time.monotonic()
                    should_report_by_attempts = (
                        progress_every_attempts > 0
                        and (failed - last_progress_failures) >= progress_every_attempts
                    )
                    should_report_by_time = (
                        progress_every_seconds > 0
                        and (now - last_progress_time) >= progress_every_seconds
                    )
                    if should_report_by_attempts or should_report_by_time:
                        _print_live_summary("live")
                        last_progress_failures = failed
                        last_progress_time = now

                if generated < count:
                    _submit(1)

    elapsed = time.monotonic() - t0
    print(f"\n  Done: {generated} puzzles in {elapsed:.1f}s  ({failed} failed attempts)")
    if rejection_counts:
        counts = "  ".join(
            f"{reason}={rejection_counts[reason]}"
            for reason in sorted(rejection_counts)
        )
        print(f"  Rejections: {counts}")
    if partial_placement_counts:
        partials = "  ".join(
            f"{bucket}={partial_placement_counts[bucket]}"
            for bucket in sorted(partial_placement_counts)
        )
        print(f"  Partial placements: {partials}")
    if solved_failure_counts:
        solved = "  ".join(
            f"{status}={solved_failure_counts[status]}"
            for status in sorted(solved_failure_counts)
        )
        avg_solve_ms = solved_failure_time_ms / solved_failure_attempts
        print(f"  Solved failures: {solved}  avg_solve_ms={avg_solve_ms:.1f}")
    if best_near_miss is not None:
        print(
            "  Best near miss: "
            f"reason={best_near_miss.rejection_reason} "
            f"placed={best_near_miss.tiles_placed}/{best_near_miss.rack_size} "
            f"disrupt={best_near_miss.disruption_score} "
            f"chain={best_near_miss.chain_depth}"
        )

    if sync_cmd:
        _run_sync(sync_cmd)


if __name__ == "__main__":
    main()
