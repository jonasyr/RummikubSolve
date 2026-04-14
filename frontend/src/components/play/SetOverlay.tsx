"use client";

import { memo } from "react";
import { useTranslations } from "next-intl";
import type { DetectedSet } from "../../types/play";
import { CELL_SIZE_PX, CELL_GAP_PX } from "../../types/play";

interface Props {
  set: DetectedSet;
  /** CELL_SIZE_PX + CELL_GAP_PX — passed from parent to avoid recalculation. */
  cellPx: number;
}

export default memo(function SetOverlay({ set, cellPx }: Props) {
  const t = useTranslations("play");
  const { validation, row, startCol, tiles } = set;

  const isIncomplete = tiles.length < 3;
  const isValid = !isIncomplete && validation.isValid;
  const isInvalid = !isIncomplete && !validation.isValid;

  const borderClass = isIncomplete
    ? "border-amber-300 dark:border-amber-700"
    : isValid
      ? "border-green-400 dark:border-green-600"
      : "border-red-400 dark:border-red-600";

  const bgClass = isIncomplete
    ? "bg-amber-50/40 dark:bg-amber-900/15"
    : isValid
      ? "bg-green-50/40 dark:bg-green-900/15"
      : "bg-red-50/40 dark:bg-red-900/15";

  return (
    <div
      className={`absolute rounded-lg border-2 ${borderClass} ${bgClass} pointer-events-none`}
      style={{
        top: row * cellPx,
        left: startCol * cellPx,
        // span all tiles but omit the trailing gap
        width: tiles.length * cellPx - CELL_GAP_PX,
        height: CELL_SIZE_PX,
      }}
    >
      {isValid && validation.type && (
        <span className="absolute -bottom-4 left-1 text-[9px] font-medium text-green-600 dark:text-green-400">
          {validation.type}
        </span>
      )}
      {isInvalid && validation.reason && (
        <span className="absolute -bottom-4 left-1 text-[9px] font-medium text-red-500 dark:text-red-400 whitespace-nowrap">
          {t(
            validation.reason.replace(/^play\./, "") as Parameters<typeof t>[0],
          )}
        </span>
      )}
    </div>
  );
});
