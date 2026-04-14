"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { usePlayStore } from "../../store/play";
import type { Difficulty } from "../../types/api";

const DIFFICULTIES: Difficulty[] = [
  "easy",
  "medium",
  "hard",
  "expert",
  "nightmare",
];

export default function PlayPuzzleControls() {
  const t = useTranslations("play");
  const locale = useLocale();
  const [difficulty, setDifficulty] = useState<Difficulty>("easy");
  const abortRef = useRef<AbortController | null>(null);

  const isPuzzleLoading = usePlayStore((s) => s.isPuzzleLoading);
  const error = usePlayStore((s) => s.error);
  const loadPuzzle = usePlayStore((s) => s.loadPuzzle);

  // Cancel any in-flight request when the component unmounts.
  useEffect(
    () => () => {
      abortRef.current?.abort();
    },
    [],
  );

  const handleLoad = () => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    void loadPuzzle({ difficulty }, ctrl.signal);
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Link
        href={`/${locale}/play/calibration`}
        className="rounded border border-amber-300 bg-amber-50 px-3 py-1.5 text-sm font-medium text-amber-900 hover:bg-amber-100 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100 dark:hover:bg-amber-900"
      >
        {t("calibrationLink")}
      </Link>

      <div className="flex flex-wrap gap-1">
        {DIFFICULTIES.map((d) => (
          <button
            key={d}
            onClick={() => setDifficulty(d)}
            className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
              difficulty === d
                ? "bg-blue-600 text-white"
                : "bg-white dark:bg-gray-700 text-gray-600 dark:text-gray-300 border border-gray-300 dark:border-gray-600"
            }`}
          >
            {d}
          </button>
        ))}
      </div>

      <button
        onClick={handleLoad}
        disabled={isPuzzleLoading}
        className="ml-auto px-4 py-1.5 rounded bg-green-600 text-white font-medium text-sm hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isPuzzleLoading ? t("loading") : t("getPuzzle")}
      </button>

      {error && (
        <p className="w-full text-xs text-red-600 dark:text-red-400">{error}</p>
      )}
    </div>
  );
}
