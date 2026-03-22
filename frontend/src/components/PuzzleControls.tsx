"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { useGameStore } from "../store/game";
import type { Difficulty } from "../types/api";

const DIFFICULTIES: Difficulty[] = ["easy", "medium", "hard"];

export default function PuzzleControls() {
  const t = useTranslations("puzzle");
  const [selected, setSelected] = useState<Difficulty>("medium");
  const isPuzzleLoading = useGameStore((s) => s.isPuzzleLoading);
  const loadPuzzle = useGameStore((s) => s.loadPuzzle);

  return (
    <details className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden text-sm">
      <summary className="px-4 py-2 cursor-pointer font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 select-none list-none flex items-center gap-2">
        <span className="text-base">🎯</span> {t("title")}
      </summary>
      <div className="px-4 py-3 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-2 flex-wrap">
          {DIFFICULTIES.map((d) => (
            <button
              key={d}
              onClick={() => setSelected(d)}
              className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                selected === d
                  ? "bg-blue-600 text-white"
                  : "bg-white dark:bg-gray-700 text-gray-600 dark:text-gray-300 border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-600"
              }`}
            >
              {t(d)}
            </button>
          ))}
          <button
            onClick={() => void loadPuzzle(selected)}
            disabled={isPuzzleLoading}
            className="ml-auto px-4 py-1 rounded bg-green-600 text-white font-medium text-sm hover:bg-green-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-1"
          >
            {isPuzzleLoading ? (
              <>
                <span className="animate-spin text-base">⟳</span>
                {t("loading")}
              </>
            ) : (
              t("getButton")
            )}
          </button>
        </div>
      </div>
    </details>
  );
}
