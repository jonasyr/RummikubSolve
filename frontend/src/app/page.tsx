"use client";

import { useGameStore } from "../store/game";
import { solvePuzzle } from "../lib/api";
import RackSection from "../components/RackSection";
import BoardSection from "../components/BoardSection";
import SolutionView from "../components/SolutionView";

export default function Home() {
  const boardSets = useGameStore((s) => s.boardSets);
  const rack = useGameStore((s) => s.rack);
  const isFirstTurn = useGameStore((s) => s.isFirstTurn);
  const isLoading = useGameStore((s) => s.isLoading);
  const solution = useGameStore((s) => s.solution);
  const error = useGameStore((s) => s.error);
  const setIsFirstTurn = useGameStore((s) => s.setIsFirstTurn);
  const setLoading = useGameStore((s) => s.setLoading);
  const setSolution = useGameStore((s) => s.setSolution);
  const setError = useGameStore((s) => s.setError);
  const reset = useGameStore((s) => s.reset);

  async function handleSolve() {
    if (rack.length === 0) return;
    setLoading(true);
    setError(null);
    setSolution(null);
    try {
      const result = await solvePuzzle({
        board: boardSets,
        rack,
        rules: { is_first_turn: isFirstTurn },
      });
      setSolution(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="max-w-xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">RummikubSolve</h1>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer">
            <input
              type="checkbox"
              checked={isFirstTurn}
              onChange={(e) => setIsFirstTurn(e.target.checked)}
              className="rounded"
            />
            First turn
          </label>
          <button
            onClick={reset}
            className="text-sm px-2 py-1 rounded text-gray-500 hover:text-gray-700 hover:bg-gray-100"
          >
            Reset
          </button>
        </div>
      </div>

      <RackSection />
      <BoardSection />

      {/* Solve button */}
      <button
        onClick={() => void handleSolve()}
        disabled={isLoading || rack.length === 0}
        className="w-full py-3 rounded-lg bg-blue-600 text-white font-semibold text-base hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {isLoading ? "Solving…" : "Solve"}
      </button>

      {/* Error banner */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Solution */}
      {solution && <SolutionView solution={solution} />}
    </main>
  );
}
