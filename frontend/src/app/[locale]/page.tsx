"use client";

import { useRef } from "react";
import { useTranslations } from "next-intl";
import { useGameStore } from "../../store/game";
import { solvePuzzle } from "../../lib/api";
import RackSection from "../../components/RackSection";
import BoardSection from "../../components/BoardSection";
import SolutionView from "../../components/SolutionView";
import { TranslatedErrorBoundary } from "../../components/ErrorBoundary";
import RulesPanel from "../../components/RulesPanel";
import LocaleSwitcher from "../../components/LocaleSwitcher";

export default function Home() {
  const t = useTranslations("page");

  const boardSets = useGameStore((s) => s.boardSets);
  const rack = useGameStore((s) => s.rack);
  const isFirstTurn = useGameStore((s) => s.isFirstTurn);
  const isLoading = useGameStore((s) => s.isLoading);
  const isBuildingSet = useGameStore((s) => s.isBuildingSet);
  const solution = useGameStore((s) => s.solution);
  const error = useGameStore((s) => s.error);
  const setIsFirstTurn = useGameStore((s) => s.setIsFirstTurn);
  const setLoading = useGameStore((s) => s.setLoading);
  const setSolution = useGameStore((s) => s.setSolution);
  const setError = useGameStore((s) => s.setError);
  const reset = useGameStore((s) => s.reset);

  // Abort any in-flight request when a new solve is triggered.
  const abortRef = useRef<AbortController | null>(null);

  async function handleSolve() {
    if (rack.length === 0) return;

    // Cancel any previous in-flight request.
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    setSolution(null);
    try {
      const result = await solvePuzzle(
        { board: boardSets, rack, rules: { is_first_turn: isFirstTurn } },
        controller.signal,
      );
      setSolution(result);
    } catch (err) {
      // Ignore cancellations — a new request is already in flight.
      if (err instanceof Error && err.name === "AbortError") return;
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    if (
      (rack.length > 0 || boardSets.length > 0) &&
      !window.confirm(t("resetConfirm"))
    ) {
      return;
    }
    abortRef.current?.abort();
    reset();
  }

  return (
    <main className="max-w-xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">RummikubSolve</h1>
        <div className="flex items-center gap-3">
          <LocaleSwitcher />
          <label className="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
            <input
              type="checkbox"
              checked={isFirstTurn}
              onChange={(e) => setIsFirstTurn(e.target.checked)}
              className="rounded"
            />
            {t("firstTurn")}
          </label>
          <button
            onClick={handleReset}
            className="text-sm px-2 py-1 rounded text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            {t("reset")}
          </button>
        </div>
      </div>

      <RulesPanel />
      <RackSection />
      <BoardSection />

      {/* Solve button */}
      <button
        onClick={() => void handleSolve()}
        disabled={isLoading || rack.length === 0 || isBuildingSet}
        className="w-full py-3 rounded-lg bg-blue-600 text-white font-semibold text-base hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {isLoading
          ? t("solving")
          : isBuildingSet
            ? t("finishEditing")
            : t("solve")}
      </button>

      {/* Error banner */}
      {error && (
        <div
          role="alert"
          aria-live="assertive"
          className="p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-400 text-sm"
        >
          {error}
        </div>
      )}

      {/* Solution */}
      {solution && (
        <TranslatedErrorBoundary>
          <SolutionView solution={solution} />
        </TranslatedErrorBoundary>
      )}
    </main>
  );
}
