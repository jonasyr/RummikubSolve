"use client";

import { useTranslations } from "next-intl";
import { usePlayStore } from "../../../store/play";

export default function PlayPage() {
  const t = useTranslations("play");
  const grid = usePlayStore((s) => s.grid);
  const rack = usePlayStore((s) => s.rack);
  const detectedSets = usePlayStore((s) => s.detectedSets);
  const isPuzzleLoading = usePlayStore((s) => s.isPuzzleLoading);
  const error = usePlayStore((s) => s.error);
  const loadPuzzle = usePlayStore((s) => s.loadPuzzle);

  return (
    <main className="h-dvh flex flex-col">
      <header className="p-2 border-b">
        <h1 className="text-lg font-bold">{t("title")}</h1>
      </header>

      {/* Phase 1 replaces this with PlayLayout + PlayGrid + PlayRack + PlayPuzzleControls */}
      <div className="p-4 space-y-2">
        <button
          onClick={() => void loadPuzzle({ difficulty: "easy" })}
          disabled={isPuzzleLoading}
          className="px-4 py-2 bg-blue-500 text-white rounded disabled:opacity-50"
        >
          {isPuzzleLoading ? "Loading…" : "Load Easy Puzzle"}
        </button>

        {error && (
          <p className="text-red-500 text-sm">{error}</p>
        )}

        <p className="text-gray-400">
          {grid.size === 0
            ? t("loadPuzzlePrompt")
            : `Grid: ${grid.size} tiles, Rack: ${rack.length} tiles, Sets: ${detectedSets.length}`}
        </p>
      </div>
    </main>
  );
}
