"""Generate a validated calibration batch and store puzzles in the pool.

For each difficulty tier, tries increasing seeds until N puzzles pass ALL
quality gates (including the trivial_extension check from Phase 7).  Each
generated puzzle is stored in the puzzle pool DB so calibration pages can
load it instantly by puzzle_id — no on-the-fly generation required.

Usage::

    # Output goes to solver/generator/calibration_batches/<batch-name>.json by default
    python -m solver.generator.gen_calibration_batch \\
        --batch-name phase8_batch_v1 \\
        --count 5 \\
        --seed-start 10000

    # Or specify an explicit output path:
    python -m solver.generator.gen_calibration_batch \\
        --output /some/other/path/phase8_batch_v1.json \\
        --count 5

Output JSON structure::

    {
        "batch_name": "phase7_batch_v1",
        "entries": [
            {"difficulty": "easy", "seed": 10003, "puzzle_id": "<uuid>"},
            ...
        ]
    }
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .puzzle_generator import PuzzleGenerationError, generate_puzzle
from .puzzle_store import DEFAULT_DB_PATH, PuzzleStore

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_DIFFICULTIES = ["easy", "medium", "hard", "expert", "nightmare"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _default_output_dir = Path(__file__).resolve().parent / "calibration_batches"
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Output path for the batch JSON file. "
            f"Defaults to {_default_output_dir}/<batch-name>.json"
        ),
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of puzzles per difficulty tier (default: 5)",
    )
    parser.add_argument(
        "--seed-start",
        type=int,
        default=10000,
        help="First seed to try for each tier (default: 10000)",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=200,
        help="Max seeds to try per tier before giving up (default: 200)",
    )
    parser.add_argument(
        "--gen-attempts",
        type=int,
        default=2000,
        help="Inner retry limit per seed passed to generate_puzzle() (default: 2000)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to the puzzle pool DB",
    )
    parser.add_argument(
        "--batch-name",
        type=str,
        default=None,
        help="Batch name (defaults to output filename stem)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    _default_output_dir = Path(__file__).resolve().parent / "calibration_batches"

    # Resolve batch_name first (needed to build the default output path).
    # If --output is given, its stem takes precedence over --batch-name when
    # both are omitted; if only --batch-name is given we use it as the stem.
    if args.output is None and args.batch_name is None:
        raise SystemExit(
            "Either --output or --batch-name must be specified.\n"
            "Example: --batch-name phase8_batch_v1"
        )
    batch_name: str = args.batch_name or args.output.stem  # type: ignore[union-attr]
    output_path: Path = args.output or (_default_output_dir / f"{batch_name}.json")

    store = PuzzleStore(args.db)

    entries: list[dict[str, object]] = []

    for difficulty in _DIFFICULTIES:
        logger.info("Generating %d %s puzzles…", args.count, difficulty)
        found = 0
        attempts = 0
        seed = args.seed_start

        while found < args.count and attempts < args.max_attempts:
            attempts += 1
            try:
                result = generate_puzzle(
                    difficulty=difficulty,
                    seed=seed,
                    generator_version="v2",
                    # Use high inner retry counts for offline batch generation.
                    max_attempts=args.gen_attempts,
                )
                puzzle_id = store.store(result, seed=seed)
                entries.append({"difficulty": difficulty, "seed": seed, "puzzle_id": puzzle_id})
                found += 1
                logger.info(
                    "  [%s] seed=%d → puzzle_id=%s (score=%.1f)",
                    difficulty,
                    seed,
                    puzzle_id[:8],
                    result.composite_score,
                )
            except PuzzleGenerationError as exc:
                logger.debug("  [%s] seed=%d failed: %s", difficulty, seed, exc)
            finally:
                seed += 1

        if found < args.count:
            logger.error(
                "  [%s] Only found %d/%d puzzles after %d attempts — "
                "increase --max-attempts or --seed-start",
                difficulty,
                found,
                args.count,
                attempts,
            )
            store.close()
            return 1

        logger.info("  [%s] Done (%d/%d) in %d attempts", difficulty, found, args.count, attempts)

    store.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"batch_name": batch_name, "entries": entries}
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    logger.info("Wrote %d entries to %s", len(entries), output_path)
    logger.info("Batch name: %s", batch_name)
    logger.info("Update BATCH_NAME in calibration/page.tsx to '%s' before deploying.", batch_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
