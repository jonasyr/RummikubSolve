"use client";

import { useTranslations } from "next-intl";
import { usePlayStore } from "../../store/play";

function formatElapsed(seconds: number): string {
  if (seconds >= 60) {
    return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  }
  return `${seconds}s`;
}

export default function SolvedBanner() {
  const t = useTranslations("play");
  const isSolved   = usePlayStore((s) => s.isSolved);
  const solveStart = usePlayStore((s) => s.solveStartTime);
  const solveEnd   = usePlayStore((s) => s.solveEndTime);

  if (!isSolved) return null;

  const elapsed =
    solveStart !== null && solveEnd !== null
      ? Math.round((solveEnd - solveStart) / 1000)
      : null;

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50 pointer-events-none"
      aria-live="polite"
    >
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl border border-green-200 dark:border-green-800 p-8 text-center pointer-events-auto max-w-sm mx-4 animate-pop-in">
        <p className="text-3xl font-bold text-green-600 dark:text-green-400 mb-2">
          🎉 {t("solved")} 🎉
        </p>
        {elapsed !== null && (
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t("solveTime", { time: formatElapsed(elapsed) })}
          </p>
        )}
      </div>
    </div>
  );
}
