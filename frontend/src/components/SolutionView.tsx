"use client";

import { useTranslations } from "next-intl";
import type { SolveResponse, BoardSetOutput, MoveOutput, TileOutput } from "../types/api";
import Tile from "./Tile";

interface Props {
  solution: SolveResponse;
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

export default function SolutionView({ solution }: Props) {
  const t = useTranslations("solution");

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

      {/* New board sets */}
      <div className="space-y-2">
        {(solution.new_board ?? []).map((set, si) => {
          const isUnchanged  = set.is_unchanged ?? false;
          const newCount     = (set.new_tile_indices ?? []).length;
          const isNew        = !isUnchanged && newCount === set.tiles.length;
          const isExtended   = !isUnchanged && newCount > 0 && !isNew;
          const isRearranged = !isUnchanged && newCount === 0;

          const borderBg = isNew        ? "border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/30"
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
            <div key={si} className={`flex items-start gap-2 p-2 rounded border ${borderBg}`}>
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

      {/* Move instructions */}
      {(solution.moves?.length ?? 0) > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">
            {t("moveInstructions")}
          </p>
          {/* Summary line */}
          {(() => {
            const counts = (solution.moves ?? []).reduce<Record<string, number>>(
              (acc, m) => ({ ...acc, [m.action]: (acc[m.action] ?? 0) + 1 }),
              {},
            );
            const parts: string[] = [];
            if (counts.create)    parts.push(t("moveCreate", { count: counts.create }));
            if (counts.extend)    parts.push(t("moveExtend", { count: counts.extend }));
            if (counts.rearrange) parts.push(t("moveRearrange", { count: counts.rearrange }));
            const total = (solution.moves ?? []).length;
            return (
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {t("moveSummary", { total, parts: parts.join(", ") })}
              </p>
            );
          })()}
          <ol className="space-y-1.5">
            {(solution.moves ?? []).map((move, i) => {
              const bulletClass: Record<string, string> = {
                create:    "bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300",
                extend:    "bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300",
                rearrange: "bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300",
              };
              const desc = changedSets[i]
                ? buildDescription(move, changedSets[i], t)
                : move.description;
              return (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <span className={`shrink-0 w-5 h-5 rounded-full text-xs flex items-center justify-center font-medium mt-0.5 ${bulletClass[move.action] ?? "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300"}`}>
                    {i + 1}
                  </span>
                  <span className="text-gray-700 dark:text-gray-300">{desc}</span>
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </section>
  );
}
