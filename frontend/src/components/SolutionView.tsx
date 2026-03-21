"use client";

import { useTranslations } from "next-intl";
import type { SolveResponse } from "../types/api";
import Tile from "./Tile";

interface Props {
  solution: SolveResponse;
}

export default function SolutionView({ solution }: Props) {
  const t = useTranslations("solution");

  if (solution.status === "error") {
    return (
      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
          {t("heading")}
        </h2>
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {t("error")}
        </div>
      </section>
    );
  }

  if (solution.status === "no_solution") {
    const reason = solution.is_first_turn
      ? t("noSolutionFirstTurn")
      : t("noSolution");
    return (
      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
          {t("heading")}
        </h2>
        <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-800 text-sm">
          {reason}
        </div>
      </section>
    );
  }

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
        {t("heading")}
      </h2>

      {/* Summary bar */}
      <div className="flex flex-wrap gap-2 text-sm">
        <span className="px-2 py-1 bg-green-100 text-green-800 rounded font-medium">
          {t("tilesPlaced", { count: solution.tiles_placed })}
        </span>
        {solution.tiles_remaining > 0 && (
          <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded">
            {t("tilesRemaining", { count: solution.tiles_remaining })}
          </span>
        )}
        <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded">
          {t("solveTime", { ms: solution.solve_time_ms })}
        </span>
        {solution.is_optimal && (
          <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded font-medium">
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

          const borderBg = isNew        ? "border-green-200 bg-green-50"
                         : isExtended   ? "border-blue-200 bg-white"
                         : isRearranged ? "border-amber-200 bg-amber-50"
                         :                "border-gray-200 bg-gray-50 opacity-60";

          const badge = isNew
            ? <span className="text-xs font-semibold px-1.5 py-0.5 rounded bg-green-100 text-green-700 shrink-0">{t("badge.new")}</span>
            : isExtended
            ? <span className="text-xs font-semibold px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 shrink-0">{t("badge.extended")}</span>
            : isRearranged
            ? <span className="text-xs font-semibold px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 shrink-0">{t("badge.rearranged")}</span>
            : <span className="text-xs text-gray-400 italic shrink-0 pt-1">{t("badge.unchanged")}</span>;

          return (
            <div key={si} className={`flex items-start gap-2 p-2 rounded border ${borderBg}`}>
              <span className="text-xs font-bold text-gray-500 w-6 shrink-0 pt-1">{si + 1}.</span>
              <span className="text-xs text-gray-400 uppercase w-8 shrink-0 pt-1">{set.type}</span>
              <div className="flex flex-wrap gap-1 flex-1">
                {set.tiles.map((tile, ti) => (
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
          <p className="text-xs text-gray-500 uppercase tracking-wide">
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
          <p className="text-xs text-gray-500 uppercase tracking-wide">
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
              <p className="text-xs text-gray-500">
                {t("moveSummary", { total, parts: parts.join(", ") })}
              </p>
            );
          })()}
          <ol className="space-y-1.5">
            {(solution.moves ?? []).map((move, i) => {
              const bulletClass: Record<string, string> = {
                create:    "bg-green-100 text-green-700",
                extend:    "bg-blue-100 text-blue-700",
                rearrange: "bg-amber-100 text-amber-700",
              };
              return (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <span className={`shrink-0 w-5 h-5 rounded-full text-xs flex items-center justify-center font-medium mt-0.5 ${bulletClass[move.action] ?? "bg-gray-100 text-gray-700"}`}>
                    {i + 1}
                  </span>
                  <span className="text-gray-700">{move.description}</span>
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </section>
  );
}
