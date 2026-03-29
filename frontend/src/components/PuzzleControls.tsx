"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { useGameStore } from "../store/game";
import type { Difficulty, PuzzleRequest } from "../types/api";

const DIFFICULTIES: Difficulty[] = ["easy", "medium", "hard", "expert", "nightmare", "custom"];

export default function PuzzleControls() {
  const t = useTranslations("puzzle");
  const [selected, setSelected] = useState<Difficulty>("medium");
  const [setsToRemove, setSetsToRemove] = useState(3);
  const isPuzzleLoading = useGameStore((s) => s.isPuzzleLoading);
  const puzzleError = useGameStore((s) => s.error);
  const loadPuzzle = useGameStore((s) => s.loadPuzzle);
  const lastPuzzleMeta = useGameStore((s) => s.lastPuzzleMeta);
  const abortRef = useRef<AbortController | null>(null);
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const wasLoadingRef = useRef(false);

  useEffect(() => {
    // Only collapse on successful load (not on error — user needs to see the error and retry).
    if (wasLoadingRef.current && !isPuzzleLoading && !puzzleError) {
      if (detailsRef.current) detailsRef.current.open = false;
    }
    wasLoadingRef.current = isPuzzleLoading;
  }, [isPuzzleLoading, puzzleError]);

  function handleGetPuzzle() {
    // Cancel any still-in-flight request before starting a new one.
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const request: PuzzleRequest = {
      difficulty: selected,
      ...(selected === "custom" ? { sets_to_remove: setsToRemove } : {}),
    };
    void loadPuzzle(request, controller.signal);
  }

  return (
    <details ref={detailsRef} className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden text-sm">
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

          {selected === "custom" && (
            <div className="flex items-center gap-1 ml-1">
              <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                {t("setsToRemove")}:
              </span>
              <button
                onClick={() => setSetsToRemove((v) => Math.max(1, v - 1))}
                disabled={setsToRemove <= 1}
                className="w-6 h-6 flex items-center justify-center rounded bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed font-mono leading-none"
                aria-label="Decrease sets to remove"
              >
                −
              </button>
              <span className="w-5 text-center text-sm font-medium tabular-nums">
                {setsToRemove}
              </span>
              <button
                onClick={() => setSetsToRemove((v) => Math.min(5, v + 1))}
                disabled={setsToRemove >= 5}
                className="w-6 h-6 flex items-center justify-center rounded bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed font-mono leading-none"
                aria-label="Increase sets to remove"
              >
                +
              </button>
            </div>
          )}

          {lastPuzzleMeta && (
            <div className="w-full mt-1 flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
              <span>{t("chainDepth", { depth: lastPuzzleMeta.chainDepth })}</span>
              {lastPuzzleMeta.isUnique && (
                <span className="text-green-600 dark:text-green-400 font-medium">
                  ✓ {t("uniqueSolution")}
                </span>
              )}
            </div>
          )}
          <button
            onClick={handleGetPuzzle}
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
