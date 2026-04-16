"""Reporting-only calibration analysis for fixed-seed telemetry batches."""

from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import TypedDict

from .telemetry_store import DEFAULT_TELEMETRY_DB_PATH


class AttemptSummary(TypedDict):
    attempt_id: str
    difficulty: str
    seed: int | None
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_TELEMETRY_DB_PATH)
    parser.add_argument("--batch", type=str, required=True)
    return parser.parse_args()


def _safe_mean(values: list[float]) -> float:
    return mean(values) if values else 0.0


def main() -> int:
    args = _parse_args()
    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row
    try:
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
        print(f"No telemetry rows found for batch '{args.batch}'.")
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
    print(f"Attempts: {len(attempts)}")

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
    for attempt in sorted(attempts, key=lambda a: a["batch_index"] or 0):
        elapsed_ms = attempt["elapsed_ms"]
        minutes = f"{elapsed_ms / 60000:.2f}" if elapsed_ms is not None else "n/a"
        batch_index = attempt["batch_index"] if attempt["batch_index"] is not None else -1
        seed = str(attempt["seed"]) if attempt["seed"] is not None else "-"
        print(
            f"- #{batch_index:>2} {attempt['difficulty']:>9} seed={seed} "
            f"score={attempt['composite_score']:6.2f} minutes={minutes:>5} "
            f"undos={attempt['undo_count']:>2} "
            f"returns={attempt['tile_returned_count']:>2} "
            f"label={attempt['self_label'] or '-'} rating={attempt['self_rating'] or '-'}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
