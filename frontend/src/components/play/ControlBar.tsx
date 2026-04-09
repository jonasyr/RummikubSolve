"use client";

import { useState } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { usePlayStore } from "../../store/play";
import { cellKey } from "../../types/play";

export default function ControlBar() {
  const t = useTranslations("play");
  const locale = useLocale();

  const past           = usePlayStore((s) => s.past);
  const future         = usePlayStore((s) => s.future);
  const showValidation = usePlayStore((s) => s.showValidation);
  const selectedTile   = usePlayStore((s) => s.selectedTile);
  const grid           = usePlayStore((s) => s.grid);
  const undo           = usePlayStore((s) => s.undo);
  const redo           = usePlayStore((s) => s.redo);
  const commit         = usePlayStore((s) => s.commit);
  const revert         = usePlayStore((s) => s.revert);
  const returnToRack   = usePlayStore((s) => s.returnToRack);
  const toggleValidation = usePlayStore((s) => s.toggleValidation);
  const detectedSets   = usePlayStore((s) => s.detectedSets);
  const puzzle         = usePlayStore((s) => s.puzzle);

  const [commitFlash, setCommitFlash] = useState(false);

  const handleCommit = () => {
    const result = commit();
    if (result.ok) {
      setCommitFlash(true);
      setTimeout(() => setCommitFlash(false), 2000);
    }
  };

  // Show "Return to Rack" only when a rack-source grid tile is selected
  const canReturn: boolean = (() => {
    if (selectedTile?.source !== "grid") return false;
    const placed = grid.get(cellKey(selectedTile.row, selectedTile.col));
    return placed?.source === "rack";
  })();

  // Translate the commit-blocked reason to a tooltip string (null = not blocked)
  const commitTitle: string | null = (() => {
    if (!puzzle) return null;
    if (detectedSets.some((ds) => ds.tiles.length >= 3 && !ds.validation.isValid)) {
      return t("commitBlocked.invalidSets");
    }
    if (detectedSets.some((ds) => ds.tiles.length > 0 && ds.tiles.length < 3)) {
      return t("commitBlocked.incompleteSets");
    }
    return null;
  })();

  const btnBase =
    "h-11 px-3 rounded text-sm font-medium border border-gray-300 dark:border-gray-600 " +
    "hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Link
        href={`/${locale}`}
        className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
      >
        {t("nav.toSolver")}
      </Link>

      <div className="flex gap-1">
        <button
          className={btnBase}
          onClick={undo}
          disabled={past.length === 0}
        >
          {t("undo")}
        </button>
        <button
          className={btnBase}
          onClick={redo}
          disabled={future.length === 0}
        >
          {t("redo")}
        </button>
      </div>

      {canReturn && (
        <button className={btnBase} onClick={returnToRack}>
          {t("returnToRack")}
        </button>
      )}

      <div className="flex gap-1 ml-auto">
        <button className={btnBase} onClick={toggleValidation}>
          {showValidation ? t("hideValidation") : t("showValidation")}
        </button>
        <button
          className={`h-11 px-3 rounded text-sm font-medium text-white ${
            commitFlash
              ? "bg-green-600"
              : commitTitle
                ? "bg-blue-600/40 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-700"
          }`}
          onClick={handleCommit}
          disabled={!!commitTitle}
          title={commitTitle ?? undefined}
        >
          {commitFlash ? t("commitSuccess") : t("commit")}
        </button>
        <button className={btnBase} onClick={revert}>
          {t("revert")}
        </button>
      </div>
    </div>
  );
}
