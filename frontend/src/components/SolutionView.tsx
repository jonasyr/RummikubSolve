"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import type { SolveResponse, SetChange, TileWithOrigin } from "../types/api";
import Tile from "./Tile";

interface Props {
  solution: SolveResponse;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

// Sort priority: new(0) → extended(1) → rearranged(2) → unchanged(3)
const ACTION_ORDER: Record<string, number> = {
  new: 0,
  extended: 1,
  rearranged: 2,
  unchanged: 3,
};

// Border + background per action type (matches existing palette).
const BORDER_BG: Record<string, string> = {
  new:        "border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/30",
  extended:   "border-blue-200 dark:border-blue-800 bg-white dark:bg-gray-800",
  rearranged: "border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/30",
  unchanged:  "border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 opacity-60",
};

// Badge text colour per action type.
const BADGE_CLS: Record<string, string> = {
  new:        "bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300",
  extended:   "bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300",
  rearranged: "bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300",
  unchanged:  "text-gray-400 dark:text-gray-500 italic",
};

type TFunc = ReturnType<typeof useTranslations<"solution">>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Sort tiles by number for runs; preserve order for groups. */
function sortedTiles(sc: SetChange): TileWithOrigin[] {
  if (sc.result_set.type !== "run") return sc.result_set.tiles;
  return [...sc.result_set.tiles].sort(
    (a, b) => (a.number ?? 0) - (b.number ?? 0),
  );
}

// ---------------------------------------------------------------------------
// SetChangeCard — one card per SetChange entry
// ---------------------------------------------------------------------------

interface CardProps {
  sc: SetChange;
  t: TFunc;
  showProvenance: boolean;
}

function SetChangeCard({ sc, t, showProvenance }: CardProps) {
  const tiles = sortedTiles(sc);

  const getLabel = (tile: TileWithOrigin): string | undefined => {
    if (!showProvenance) return undefined;
    if (tile.origin === "hand") return t("originHand");
    return t("originSet", { n: tile.origin + 1 } as Parameters<TFunc>[1]);
  };

  return (
    <div
      className={`rounded-lg border p-3 space-y-2 transition-all ${BORDER_BG[sc.action] ?? BORDER_BG.unchanged}`}
    >
      {/* Header row: action badge + set type */}
      <div className="flex items-center gap-2">
        <span
          title={t(`badge.${sc.action}Title` as Parameters<TFunc>[0])}
          className={`text-xs font-semibold px-1.5 py-0.5 rounded cursor-help ${BADGE_CLS[sc.action] ?? BADGE_CLS.unchanged}`}
        >
          {t(`badge.${sc.action}` as Parameters<TFunc>[0])}
        </span>
        <span className="text-xs text-gray-400 dark:text-gray-500 uppercase tracking-wide">
          {sc.result_set.type}
        </span>
      </div>

      {/* Tiles row — highlighted when the tile came from the player's rack */}
      <div className="flex flex-wrap gap-1">
        {tiles.map((tile, i) => (
          <Tile
            key={i}
            color={tile.color}
            number={tile.number}
            isJoker={tile.joker}
            highlighted={tile.origin === "hand"}
            size="sm"
            label={getLabel(tile)}
          />
        ))}
      </div>

      {/* Source description (rearranged sets only) */}
      {sc.action === "rearranged" && sc.source_description && (
        <p className="text-xs text-gray-400 dark:text-gray-500">
          {t("source", { desc: sc.source_description } as Parameters<TFunc>[1])}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SolutionView
// ---------------------------------------------------------------------------

export default function SolutionView({ solution }: Props) {
  const t = useTranslations("solution");
  const [showUnchanged, setShowUnchanged] = useState(false);
  const [showProvenance, setShowProvenance] = useState(false);

  // Reset display toggles whenever a new solution arrives.
  useEffect(() => {
    setShowUnchanged(false);
    setShowProvenance(false);
  }, [solution]);

  // ── No-solution state ──────────────────────────────────────────────────
  if (solution.status === "no_solution") {
    const reason = solution.is_first_turn
      ? t("noSolutionFirstTurn")
      : t("noSolution");
    return (
      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
          {t("heading")}
        </h2>
        <div className="p-4 bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-800 rounded-lg text-yellow-800 dark:text-yellow-300 text-sm">
          {reason}
        </div>
      </section>
    );
  }

  // ── Build sorted set-change list ───────────────────────────────────────
  const setChanges: SetChange[] = solution.set_changes ?? [];

  const sorted = [...setChanges].sort(
    (a, b) =>
      (ACTION_ORDER[a.action] ?? 99) - (ACTION_ORDER[b.action] ?? 99),
  );

  const unchangedChanges = sorted.filter((c) => c.action === "unchanged");
  const changedChanges   = sorted.filter((c) => c.action !== "unchanged");
  const visible          = showUnchanged ? sorted : changedChanges;

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
        {t("heading")}
      </h2>

      {/* ── Summary bar ─────────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-2 text-sm">
        <span className="px-2 py-1 bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-300 rounded font-medium">
          {t("tilesPlaced", { count: solution.tiles_placed })}
        </span>
        {solution.tiles_remaining > 0 && (
          <span className="px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded">
            {t("tilesRemaining", { count: solution.tiles_remaining })}
          </span>
        )}
        <span className="px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded">
          {t("solveTime", { ms: solution.solve_time_ms })}
        </span>
        {solution.is_optimal && (
          <span className="px-2 py-1 bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 rounded font-medium">
            {t("optimal")}
          </span>
        )}
      </div>

      {/* ── Provenance toggle ───────────────────────────────────────────── */}
      {setChanges.length > 0 && (
        <button
          onClick={() => setShowProvenance((v) => !v)}
          className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
        >
          {showProvenance ? t("hideProvenance") : t("showProvenance")}
        </button>
      )}

      {/* ── Fallback: set_changes absent but tiles were placed ───────────── */}
      {setChanges.length === 0 && solution.tiles_placed > 0 && (
        <div className="p-3 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-sm text-gray-500 dark:text-gray-400">
          {t("heading")}
        </div>
      )}

      {/* ── Set-change cards (sorted: new → extended → rearranged) ───────── */}
      <div className="space-y-2">
        {visible.map((sc, i) => (
          <SetChangeCard key={i} sc={sc} t={t} showProvenance={showProvenance} />
        ))}
      </div>

      {/* ── Unchanged-sets collapse toggle ──────────────────────────────── */}
      {unchangedChanges.length > 0 && (
        <button
          onClick={() => setShowUnchanged((v) => !v)}
          className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
        >
          {showUnchanged
            ? t("hideUnchanged")
            : t("showUnchanged", { n: unchangedChanges.length })}
        </button>
      )}

      {/* ── Remaining rack ──────────────────────────────────────────────── */}
      {(solution.remaining_rack?.length ?? 0) > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">
            {t("remainingHand")}
          </p>
          <div className="flex flex-wrap gap-1">
            {solution.remaining_rack.map((tile, i) => (
              <Tile
                key={i}
                color={tile.color}
                number={tile.number}
                isJoker={tile.joker}
                size="sm"
              />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
