"""Calibration analysis for fixed-seed telemetry batches.

Modes:
  --batch <name>      Per-attempt report for a named telemetry batch (default mode).
  --stats             Score distribution summary from the puzzles DB.
  --fit-weights       Fit linear regression on telemetry to suggest weight updates.
                      Requires --batch and at least 20 solved sessions per tier.
                      Outputs weight recommendations to stdout only — does NOT
                      auto-write difficulty_weights.json.
"""

from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import TypedDict

import numpy as np

from .puzzle_store import DEFAULT_DB_PATH
from .telemetry_store import DEFAULT_TELEMETRY_DB_PATH


class AttemptSummary(TypedDict):
    attempt_id: str
    difficulty: str
    seed: int | None
    batch_run_id: str | None
    batch_index: int | None
    composite_score: float
    branching_factor: float
    disruption_score: int
    chain_depth: int
    solved: bool
    abandoned: bool
    elapsed_ms: int | None
    move_count: int | None
    undo_count: int
    tiles_remaining: int
    tile_returned_count: int
    undo_pressed_count: int
    self_rating: int | None
    self_label: str | None
    stuck_moments: int | None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_TELEMETRY_DB_PATH)
    parser.add_argument("--puzzle-db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--batch", type=str, default=None)
    parser.add_argument(
        "--run-id", type=str, default=None, help="Filter report to one batch_run_id"
    )
    parser.add_argument(
        "--stats", action="store_true", help="Show score distributions from the puzzle pool"
    )
    parser.add_argument(
        "--fit-weights",
        action="store_true",
        help="Fit regression weights from telemetry (requires --batch)",
    )
    return parser.parse_args()


def _safe_mean(values: list[float]) -> float:
    return mean(values) if values else 0.0


_METRIC_COLS = [
    "branching_factor",
    "deductive_depth",
    "red_herring_density",
    "working_memory_load",
    "tile_ambiguity",
    "solution_fragility",
    "disruption_score",
    "chain_depth",
]

_WEIGHT_KEYS = [
    "branching",
    "deductive",
    "red_herring",
    "working_memory",
    "ambiguity",
    "fragility",
    "disruption",
    "chain_depth",
]

_NORMALIZATION_CEILINGS = {
    "branching_factor": 40.0,
    "deductive_depth": 16.0,
    "red_herring_density": 1.0,
    "working_memory_load": 14.0,
    "tile_ambiguity": 32.0,
    "solution_fragility": 1.0,
    "disruption_score": 50.0,
    "chain_depth": 5.0,
}


def _run_stats(puzzle_db: Path) -> int:
    """Print score distribution summary from the puzzle pool DB."""
    if not puzzle_db.exists():
        print(f"Puzzle DB not found: {puzzle_db}")
        return 1
    conn = sqlite3.connect(str(puzzle_db))
    conn.row_factory = sqlite3.Row
    try:
        print("Score distributions (puzzle pool):")
        for diff in ("easy", "medium", "hard", "expert", "nightmare"):
            rows = conn.execute(
                """
                SELECT COUNT(*) as n,
                       MIN(composite_score) as lo,
                       AVG(composite_score) as avg,
                       MAX(composite_score) as hi
                FROM puzzles WHERE difficulty = ?
                """,
                (diff,),
            ).fetchone()
            if rows and rows["n"] > 0:
                print(
                    f"  {diff:>9}: n={rows['n']:>3}  "
                    f"min={rows['lo']:5.1f}  avg={rows['avg']:5.1f}  max={rows['hi']:5.1f}"
                )
            else:
                print(f"  {diff:>9}: (no puzzles)")
    finally:
        conn.close()
    return 0


def _run_fit_weights(telemetry_db: Path, batch: str) -> int:
    """Fit a linear regression of solve_time on normalised metrics and suggest new weights.

    Uses non-negative least squares (via numpy.linalg.lstsq with clipping) to ensure
    all weights stay >= 0.  Outputs recommendations to stdout only — does NOT write
    difficulty_weights.json.  Requires at least 20 solved sessions per tier to be
    meaningful.
    """
    conn = sqlite3.connect(str(telemetry_db))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT * FROM telemetry_events
            WHERE batch_name = ? AND event_type = 'puzzle_solved' AND elapsed_ms IS NOT NULL
            ORDER BY created_at
            """,
            (batch,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        print(f"No solved puzzle_solved events found for batch '{batch}'.")
        return 1

    by_tier: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        by_tier[row["difficulty"]].append(row)

    min_per_tier = 20
    warnings: list[str] = []
    for diff in ("easy", "medium", "hard", "expert", "nightmare"):
        n = len(by_tier.get(diff, []))
        if n < min_per_tier:
            warnings.append(
                f"  WARNING: {diff} has only {n} solved sessions (need {min_per_tier}+)"
            )

    if warnings:
        print("Data quality warnings:")
        for w in warnings:
            print(w)
        print()

    # Build feature matrix X (n_samples × 8) and target y (log solve time in seconds).
    X_rows: list[list[float]] = []
    y_vals: list[float] = []

    for row in rows:
        norm_features = []
        for col in _METRIC_COLS:
            val = float(row[col]) if row[col] is not None else 0.0
            ceiling = _NORMALIZATION_CEILINGS[col]
            norm_features.append(min(val / ceiling, 1.0))
        X_rows.append(norm_features)
        elapsed_s = max(float(row["elapsed_ms"]) / 1000.0, 1.0)
        y_vals.append(float(np.log(elapsed_s)))

    X = np.array(X_rows)
    y = np.array(y_vals)

    # Fit via least squares, then clip negatives and re-normalise.
    coeffs, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    coeffs_clipped = np.maximum(coeffs, 0.0)
    total = coeffs_clipped.sum()
    if total < 1e-9:
        print("Regression produced all-zero weights — not enough signal in the data.")
        return 1

    weights_norm = coeffs_clipped / total
    negatives = [_WEIGHT_KEYS[i] for i, c in enumerate(coeffs) if c < 0]

    print(f"Fit weights from batch '{batch}' ({len(rows)} solved sessions):")
    print()
    if negatives:
        print(f"  Note: {negatives} had negative coefficients → clipped to 0 and renormalised.")
        print()
    print("  Suggested weight updates for difficulty_weights.json:")
    print("  {")
    for key, w in zip(_WEIGHT_KEYS, weights_norm, strict=True):
        print(f'    "{key}": {w:.4f},')
    print("  }")
    print()
    print("  Review and apply manually — this does NOT auto-write the file.")
    return 0


def main() -> int:
    args = _parse_args()

    if args.stats:
        return _run_stats(args.puzzle_db)

    if args.fit_weights:
        if not args.batch:
            print("--fit-weights requires --batch <name>")
            return 1
        return _run_fit_weights(args.db, args.batch)

    if not args.batch:
        print("Specify --batch <name>, --stats, or --fit-weights. Use --help for details.")
        return 1

    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row
    try:
        if args.run_id:
            rows = conn.execute(
                """
                SELECT *
                FROM telemetry_events
                WHERE batch_name = ? AND batch_run_id = ?
                ORDER BY created_at, id
                """,
                (args.batch, args.run_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT *
                FROM telemetry_events
                WHERE batch_name = ?
                ORDER BY created_at, id
                """,
                (args.batch,),
            ).fetchall()
    finally:
        conn.close()

    if not rows:
        qualifier = f" run-id={args.run_id}" if args.run_id else ""
        print(f"No telemetry rows found for batch '{args.batch}'{qualifier}.")
        return 1

    by_attempt: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        by_attempt[row["attempt_id"]].append(row)

    attempts: list[AttemptSummary] = []
    for attempt_id, attempt_events in by_attempt.items():
        solved = next((r for r in attempt_events if r["event_type"] == "puzzle_solved"), None)
        abandoned = next((r for r in attempt_events if r["event_type"] == "puzzle_abandoned"), None)
        rated = next((r for r in attempt_events if r["event_type"] == "puzzle_rated"), None)
        base = solved or abandoned or attempt_events[0]
        outcome = solved if solved is not None else abandoned
        tile_returned_count = sum(
            1 for r in attempt_events if r["event_type"] == "tile_returned_to_rack"
        )
        undo_pressed_count = sum(1 for r in attempt_events if r["event_type"] == "undo_pressed")
        attempts.append(
            {
                "attempt_id": attempt_id,
                "difficulty": str(base["difficulty"]),
                "seed": int(base["seed"]) if base["seed"] is not None else None,
                "batch_run_id": str(base["batch_run_id"]) if base["batch_run_id"] else None,
                "batch_index": int(base["batch_index"])
                if base["batch_index"] is not None
                else None,
                "composite_score": float(base["composite_score"]),
                "branching_factor": float(base["branching_factor"]),
                "disruption_score": int(base["disruption_score"]),
                "chain_depth": int(base["chain_depth"]),
                "solved": solved is not None,
                "abandoned": abandoned is not None,
                "elapsed_ms": int(outcome["elapsed_ms"])
                if outcome is not None and outcome["elapsed_ms"] is not None
                else None,
                "move_count": int(outcome["move_count"])
                if outcome is not None and outcome["move_count"] is not None
                else None,
                "undo_count": int(outcome["undo_count"])
                if outcome is not None and outcome["undo_count"] is not None
                else 0,
                "tiles_remaining": int(abandoned["tiles_remaining"])
                if abandoned and abandoned["tiles_remaining"] is not None
                else 0,
                "tile_returned_count": tile_returned_count,
                "undo_pressed_count": undo_pressed_count,
                "self_rating": int(rated["self_rating"])
                if rated and rated["self_rating"] is not None
                else None,
                "self_label": rated["self_label"] if rated else None,
                "stuck_moments": int(rated["stuck_moments"])
                if rated and rated["stuck_moments"] is not None
                else None,
            }
        )

    print(f"Calibration batch: {args.batch}")
    if args.run_id:
        print(f"Run ID filter: {args.run_id}")
    print(f"Attempts: {len(attempts)}")

    # Per-run breakdown (shows data pollution at a glance when no --run-id filter).
    by_run: dict[str | None, list[AttemptSummary]] = defaultdict(list)
    for attempt in attempts:
        by_run[attempt["batch_run_id"]].append(attempt)
    if len(by_run) > 1:
        print(f"\nRuns ({len(by_run)} distinct batch_run_id values):")
        for run_id, run_attempts in sorted(by_run.items(), key=lambda x: x[0] or ""):
            run_label = run_id[:8] if run_id else "(no run_id)"
            solved_n = sum(1 for a in run_attempts if a["solved"])
            print(f"  {run_label}…  attempts={len(run_attempts)} solved={solved_n}")
        print()
    elif len(by_run) == 1:
        run_id_val = next(iter(by_run))
        print(f"Run ID: {run_id_val or '(no batch_run_id — pre-phase7 data)'}")

    by_difficulty: dict[str, list[AttemptSummary]] = defaultdict(list)
    for attempt in attempts:
        by_difficulty[attempt["difficulty"]].append(attempt)

    print("\nPer-tier summary:")
    for difficulty in ("easy", "medium", "hard", "expert", "nightmare"):
        difficulty_items = by_difficulty.get(difficulty, [])
        if not difficulty_items:
            continue
        solved_items = [a for a in difficulty_items if a["solved"]]
        avg_score = _safe_mean([a["composite_score"] for a in difficulty_items])
        avg_minutes = _safe_mean(
            [a["elapsed_ms"] / 60000 for a in solved_items if a["elapsed_ms"] is not None]
        )
        avg_undos = _safe_mean([float(a["undo_count"]) for a in solved_items])
        avg_return_to_rack = _safe_mean([float(a["tile_returned_count"]) for a in difficulty_items])
        avg_rating = _safe_mean(
            [a["self_rating"] for a in difficulty_items if a["self_rating"] is not None]
        )
        print(
            f"- {difficulty}: count={len(difficulty_items)} solved={len(solved_items)} "
            f"avg_score={avg_score:.2f} "
            f"avg_minutes={avg_minutes:.2f} "
            f"avg_undos={avg_undos:.2f} "
            f"avg_return_to_rack={avg_return_to_rack:.2f} "
            f"avg_rating={avg_rating:.2f}"
        )

    print("\nPotential mismatches:")
    mismatches = 0
    for attempt in sorted(attempts, key=lambda a: (a["difficulty"], a["batch_index"] or 0)):
        difficulty = attempt["difficulty"]
        elapsed_ms = attempt["elapsed_ms"]
        undo_count = attempt["undo_count"]
        self_label = attempt["self_label"]
        score = attempt["composite_score"]
        reasons: list[str] = []
        if difficulty == "nightmare" and elapsed_ms is not None and elapsed_ms < 180000:
            reasons.append("nightmare_under_3m")
        if difficulty in ("expert", "nightmare") and undo_count == 0:
            reasons.append("no_undo_signal")
        if difficulty in ("expert", "nightmare") and self_label in ("trivial", "straightforward"):
            reasons.append(f"self_label={self_label}")
        if difficulty in ("easy", "medium") and score > 70:
            reasons.append("score_too_high_for_low_tier")
        if reasons:
            mismatches += 1
            minutes = f"{elapsed_ms / 60000:.2f}" if elapsed_ms is not None else "n/a"
            print(
                f"- {difficulty} seed={attempt['seed']} score={score:.2f} "
                f"minutes={minutes} "
                f"undos={undo_count} label={self_label} reasons={','.join(reasons)}"
            )
    if mismatches == 0:
        print("- none")

    print("\nAttempts:")
    show_run_col = len(by_run) > 1 and not args.run_id
    for attempt in sorted(attempts, key=lambda a: a["batch_index"] or 0):
        elapsed_ms = attempt["elapsed_ms"]
        minutes = f"{elapsed_ms / 60000:.2f}" if elapsed_ms is not None else "n/a"
        batch_index = attempt["batch_index"] if attempt["batch_index"] is not None else -1
        seed = str(attempt["seed"]) if attempt["seed"] is not None else "-"
        run_abbr = attempt["batch_run_id"][:8] if attempt["batch_run_id"] else "?"
        run_col = f" run={run_abbr}…" if show_run_col else ""
        print(
            f"- #{batch_index:>2} {attempt['difficulty']:>9} seed={seed}{run_col} "
            f"score={attempt['composite_score']:6.2f} minutes={minutes:>5} "
            f"undos={attempt['undo_count']:>2} "
            f"returns={attempt['tile_returned_count']:>2} "
            f"label={attempt['self_label'] or '-'} rating={attempt['self_rating'] or '-'}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
