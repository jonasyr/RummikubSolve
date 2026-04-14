"""Reporting-only calibration analysis for fixed-seed telemetry batches."""

from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict
from pathlib import Path
from statistics import mean

from .telemetry_store import DEFAULT_TELEMETRY_DB_PATH


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

    attempts: list[dict[str, object]] = []
    for attempt_id, items in by_attempt.items():
        solved = next((r for r in items if r["event_type"] == "puzzle_solved"), None)
        abandoned = next((r for r in items if r["event_type"] == "puzzle_abandoned"), None)
        rated = next((r for r in items if r["event_type"] == "puzzle_rated"), None)
        base = solved or abandoned or items[0]
        tile_returned_count = sum(1 for r in items if r["event_type"] == "tile_returned_to_rack")
        undo_pressed_count = sum(1 for r in items if r["event_type"] == "undo_pressed")
        attempts.append(
            {
                "attempt_id": attempt_id,
                "difficulty": base["difficulty"],
                "seed": base["seed"],
                "batch_index": base["batch_index"],
                "composite_score": float(base["composite_score"]),
                "branching_factor": float(base["branching_factor"]),
                "disruption_score": int(base["disruption_score"]),
                "chain_depth": int(base["chain_depth"]),
                "solved": solved is not None,
                "abandoned": abandoned is not None,
                "elapsed_ms": int((solved or abandoned)["elapsed_ms"]) if (solved or abandoned) and (solved or abandoned)["elapsed_ms"] is not None else None,
                "move_count": int((solved or abandoned)["move_count"]) if (solved or abandoned) and (solved or abandoned)["move_count"] is not None else None,
                "undo_count": int((solved or abandoned)["undo_count"]) if (solved or abandoned) and (solved or abandoned)["undo_count"] is not None else 0,
                "tiles_remaining": int(abandoned["tiles_remaining"]) if abandoned and abandoned["tiles_remaining"] is not None else 0,
                "tile_returned_count": tile_returned_count,
                "undo_pressed_count": undo_pressed_count,
                "self_rating": int(rated["self_rating"]) if rated and rated["self_rating"] is not None else None,
                "self_label": rated["self_label"] if rated else None,
                "stuck_moments": int(rated["stuck_moments"]) if rated and rated["stuck_moments"] is not None else None,
            }
        )

    print(f"Calibration batch: {args.batch}")
    print(f"Attempts: {len(attempts)}")

    by_difficulty: dict[str, list[dict[str, object]]] = defaultdict(list)
    for attempt in attempts:
        by_difficulty[str(attempt["difficulty"])].append(attempt)

    print("\nPer-tier summary:")
    for difficulty in ("easy", "medium", "hard", "expert", "nightmare"):
        items = by_difficulty.get(difficulty, [])
        if not items:
            continue
        solved_items = [a for a in items if a["solved"]]
        print(
            f"- {difficulty}: count={len(items)} solved={len(solved_items)} "
            f"avg_score={_safe_mean([float(a['composite_score']) for a in items]):.2f} "
            f"avg_minutes={_safe_mean([float(a['elapsed_ms']) / 60000 for a in solved_items if a['elapsed_ms'] is not None]):.2f} "
            f"avg_undos={_safe_mean([float(a['undo_count']) for a in solved_items]):.2f} "
            f"avg_return_to_rack={_safe_mean([float(a['tile_returned_count']) for a in items]):.2f} "
            f"avg_rating={_safe_mean([float(a['self_rating']) for a in items if a['self_rating'] is not None]):.2f}"
        )

    print("\nPotential mismatches:")
    mismatches = 0
    for attempt in sorted(attempts, key=lambda a: (str(a["difficulty"]), int(a["batch_index"] or 0))):
        difficulty = str(attempt["difficulty"])
        elapsed_ms = attempt["elapsed_ms"]
        undo_count = int(attempt["undo_count"] or 0)
        self_label = attempt["self_label"]
        score = float(attempt["composite_score"])
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
    for attempt in sorted(attempts, key=lambda a: int(a["batch_index"] or 0)):
        elapsed_ms = attempt["elapsed_ms"]
        minutes = f"{elapsed_ms / 60000:.2f}" if elapsed_ms is not None else "n/a"
        print(
            f"- #{attempt['batch_index']:>2} {attempt['difficulty']:>9} seed={attempt['seed']} "
            f"score={float(attempt['composite_score']):6.2f} minutes={minutes:>5} "
            f"undos={int(attempt['undo_count'] or 0):>2} returns={int(attempt['tile_returned_count'] or 0):>2} "
            f"label={attempt['self_label'] or '-'} rating={attempt['self_rating'] or '-'}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
