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
  const [t1Seed, setT1Seed] = useState("1");
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

  const handleLoadT1 = () => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    const parsedSeed = Number.parseInt(t1Seed, 10);
    void loadPuzzle(
      {
        difficulty: "expert",
        seed: Number.isNaN(parsedSeed) ? undefined : parsedSeed,
        template_id: "T1_joker_displacement_v1",
      },
      ctrl.signal,
    );
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

      <div className="flex items-center gap-1 rounded border border-slate-300 bg-slate-50 px-2 py-1 dark:border-slate-700 dark:bg-slate-900">
        <label htmlFor="t1-seed" className="text-xs font-medium text-slate-700 dark:text-slate-200">
          T1 seed
        </label>
        <input
          id="t1-seed"
          type="number"
          min="1"
          value={t1Seed}
          onChange={(event) => setT1Seed(event.target.value)}
          className="w-16 rounded border border-slate-300 bg-white px-2 py-1 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
        />
        <button
          onClick={handleLoadT1}
          disabled={isPuzzleLoading}
          className="rounded bg-slate-800 px-3 py-1 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-slate-200 dark:text-slate-900 dark:hover:bg-white"
        >
          T1 test
        </button>
      </div>

      {error && (
        <p className="w-full text-xs text-red-600 dark:text-red-400">{error}</p>
      )}
    </div>
  );
}
