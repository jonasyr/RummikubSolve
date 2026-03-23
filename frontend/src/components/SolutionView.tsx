"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import type { SolveResponse, BoardSetOutput, MoveOutput, TileOutput, BoardSetInput } from "../types/api";
import Tile from "./Tile";

interface Props {
  solution: SolveResponse;
  originalBoard: BoardSetInput[];
}

// ---------------------------------------------------------------------------
// Helpers for localised move descriptions
// ---------------------------------------------------------------------------

type TFunc = ReturnType<typeof useTranslations<"solution">>;

function formatTiles(tiles: TileOutput[], t: TFunc): string {
  return tiles
    .map((tile) =>
      tile.joker
        ? "Joker"
        : `${t(`colors.${tile.color}` as Parameters<TFunc>[0])} ${tile.number}`,
    )
    .join(", ");
}

function buildDescription(
  move: MoveOutput,
  changedSet: BoardSetOutput,
  t: TFunc,
): string {
  const typeName = t(`types.${changedSet.type}` as Parameters<TFunc>[0]);
  const newIdx = changedSet.new_tile_indices ?? [];
  const rackTiles = changedSet.tiles.filter((_, i) => newIdx.includes(i));
  const boardTiles = changedSet.tiles.filter((_, i) => !newIdx.includes(i));
  const n = (move.set_index ?? 0) + 1;

  if (move.action === "create") {
    return t("moveDesc.create", { type: typeName, tiles: formatTiles(rackTiles, t) });
  }
  if (move.action === "extend") {
    return t("moveDesc.extend", { tiles: formatTiles(rackTiles, t), n });
  }
  if (move.action === "rearrange") {
    if (rackTiles.length > 0) {
      return t("moveDesc.rearrangeWith", {
        tiles: formatTiles(rackTiles, t),
        allTiles: formatTiles(changedSet.tiles, t),
      });
    }
    if (move.set_index !== null) {
      return t("moveDesc.rearrangeFrom", {
        n,
        type: typeName,
        tiles: formatTiles(boardTiles, t),
      });
    }
    return t("moveDesc.rearrange", { type: typeName, tiles: formatTiles(boardTiles, t) });
  }
  // Fallback: use raw backend text
  return move.description;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SolutionView({ solution, originalBoard }: Props) {
  const t = useTranslations("solution");
  const [step, setStep] = useState(0);

  // Reset to step 0 whenever a new solution arrives.
  useEffect(() => {
    setStep(0);
  }, [solution]);

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

  // Changed sets map 1-to-1 with solution.moves (move_generator skips unchanged sets).
  const changedSets = (solution.new_board ?? []).filter((s) => !s.is_unchanged);
  // Absolute indices of changed sets within new_board (for board-row highlighting).
  const changedIndices = (solution.new_board ?? [])
    .map((s, i) => ({ s, i }))
    .filter(({ s }) => !s.is_unchanged)
    .map(({ i }) => i);

  const totalSteps = solution.moves?.length ?? 0;
  const currentMove: MoveOutput | undefined = solution.moves?.[step];
  const currentChangedSet: BoardSetOutput | undefined = changedSets[step];

  // Badge style per action type.
  const badgeCls: Record<string, string> = {
    create:    "bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300",
    extend:    "bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300",
    rearrange: "bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300",
  };
  // Active dot colour per action type.
  const dotActiveCls: Record<string, string> = {
    create:    "bg-green-500",
    extend:    "bg-blue-500",
    rearrange: "bg-amber-500",
  };

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
        {t("heading")}
      </h2>

      {/* Summary bar */}
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

      {/* New board sets — changed set for current step is highlighted */}
      <div className="space-y-2">
        {(solution.new_board ?? []).map((set, si) => {
          const isUnchanged  = set.is_unchanged ?? false;
          const newCount     = (set.new_tile_indices ?? []).length;
          const isNew        = !isUnchanged && newCount === set.tiles.length;
          const isExtended   = !isUnchanged && newCount > 0 && !isNew;
          const isRearranged = !isUnchanged && newCount === 0;
          const isCurrentStep = si === changedIndices[step];

          const borderBg = isCurrentStep
            ? "border-indigo-400 dark:border-indigo-500 bg-indigo-50 dark:bg-indigo-900/30 ring-2 ring-indigo-400/30"
            : isNew        ? "border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/30"
            : isExtended   ? "border-blue-200 dark:border-blue-800 bg-white dark:bg-gray-800"
            : isRearranged ? "border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/30"
            :                "border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 opacity-60";

          const badge = isNew
            ? <span title={t("badge.newTitle")} className="text-xs font-semibold px-1.5 py-0.5 rounded bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 shrink-0 cursor-help">{t("badge.new")}</span>
            : isExtended
            ? <span title={t("badge.extendedTitle")} className="text-xs font-semibold px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 shrink-0 cursor-help">{t("badge.extended")}</span>
            : isRearranged
            ? <span title={t("badge.rearrangedTitle")} className="text-xs font-semibold px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 shrink-0 cursor-help">{t("badge.rearranged")}</span>
            : <span title={t("badge.unchangedTitle")} className="text-xs text-gray-400 dark:text-gray-500 italic shrink-0 pt-1 cursor-help">{t("badge.unchanged")}</span>;

          // Sort tiles by number within runs; preserve original indices for highlighting.
          const sortedEntries = set.tiles
            .map((tile, ti) => ({ tile, ti }))
            .sort((a, b) =>
              set.type === "run" ? (a.tile.number ?? 0) - (b.tile.number ?? 0) : 0,
            );

          return (
            <div key={si} className={`flex items-start gap-2 p-2 rounded border transition-all ${borderBg}`}>
              <span className="text-xs font-bold text-gray-500 dark:text-gray-400 w-6 shrink-0 pt-1">{si + 1}.</span>
              <span className="text-xs text-gray-400 dark:text-gray-500 uppercase w-8 shrink-0 pt-1">{set.type}</span>
              <div className="flex flex-wrap gap-1 flex-1">
                {sortedEntries.map(({ tile, ti }) => (
                  <Tile
                    key={ti}
                    color={tile.color}
                    number={tile.number}
                    isJoker={tile.joker}
                    highlighted={(set.new_tile_indices ?? []).includes(ti)}
                    size="sm"
                  />
                ))}
              </div>
              {badge}
            </div>
          );
        })}
      </div>

      {/* Remaining rack */}
      {(solution.remaining_rack?.length ?? 0) > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">
            {t("remainingHand")}
          </p>
          <div className="flex flex-wrap gap-1">
            {(solution.remaining_rack ?? []).map((tile, i) => (
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

      {/* Step-by-step navigator */}
      {totalSteps > 0 && currentMove && currentChangedSet && (
        <div className="space-y-3">
          {/* Header row: step counter + prev/next */}
          <div className="flex items-center justify-between">
            <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide font-semibold">
              {t("stepOf", { step: step + 1, total: totalSteps })}
            </p>
            <div className="flex gap-1">
              <button
                onClick={() => setStep((s) => Math.max(0, s - 1))}
                disabled={step === 0}
                className="px-2 py-1 text-xs rounded bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                ◀ {t("prev")}
              </button>
              <button
                onClick={() => setStep((s) => Math.min(totalSteps - 1, s + 1))}
                disabled={step === totalSteps - 1}
                className="px-2 py-1 text-xs rounded bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                {t("next")} ▶
              </button>
            </div>
          </div>

          {/* Before → After panel */}
          <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-3 space-y-2.5">
            {/* Action badge */}
            <span className={`inline-block text-xs font-semibold px-2 py-0.5 rounded ${badgeCls[currentMove.action] ?? "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300"}`}>
              {t(`badge.${currentMove.action}` as Parameters<TFunc>[0])}
            </span>

            {/* Before row — only for extend/rearrange where set_index is known */}
            {currentMove.action !== "create" &&
              currentMove.set_index !== null &&
              originalBoard[currentMove.set_index] && (
              <div className="flex items-start gap-2">
                <span className="text-xs text-gray-400 dark:text-gray-500 w-14 shrink-0 pt-1">
                  {t("before")}
                </span>
                <div className="flex flex-wrap gap-1">
                  {originalBoard[currentMove.set_index].tiles.map((tile, i) => (
                    <Tile
                      key={i}
                      color={tile.color ?? null}
                      number={tile.number ?? null}
                      isJoker={tile.joker ?? false}
                      size="sm"
                    />
                  ))}
                </div>
              </div>
            )}

            {/* After row */}
            <div className="flex items-start gap-2">
              <span className="text-xs text-gray-400 dark:text-gray-500 w-14 shrink-0 pt-1">
                {t("after")}
              </span>
              <div className="flex flex-wrap gap-1">
                {currentChangedSet.tiles
                  .map((tile, ti) => ({ tile, ti }))
                  .sort((a, b) =>
                    currentChangedSet.type === "run"
                      ? (a.tile.number ?? 0) - (b.tile.number ?? 0)
                      : 0,
                  )
                  .map(({ tile, ti }) => (
                    <Tile
                      key={ti}
                      color={tile.color}
                      number={tile.number}
                      isJoker={tile.joker}
                      highlighted={(currentChangedSet.new_tile_indices ?? []).includes(ti)}
                      size="sm"
                    />
                  ))}
              </div>
            </div>

            {/* Caption */}
            <p className="text-sm text-gray-700 dark:text-gray-300 pt-0.5">
              {buildDescription(currentMove, currentChangedSet, t)}
            </p>
          </div>

          {/* Progress dots — click to jump directly to a step */}
          <div className="flex gap-1.5 justify-center flex-wrap">
            {(solution.moves ?? []).map((m, i) => (
              <button
                key={i}
                onClick={() => setStep(i)}
                title={`${t("stepOf", { step: i + 1, total: totalSteps })}`}
                className={`w-2.5 h-2.5 rounded-full transition-all ${
                  i === step
                    ? (dotActiveCls[m.action] ?? "bg-gray-500") + " scale-125"
                    : "bg-gray-300 dark:bg-gray-600 hover:bg-gray-400 dark:hover:bg-gray-500"
                }`}
              />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
